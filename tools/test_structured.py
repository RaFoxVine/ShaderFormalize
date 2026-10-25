"""Real DXC inputs exercising records, independent call frames and input identity."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from shader_eval import evaluate_model
from shader_model import ModelError, constraint_spec, import_shader
from shaderformalize import ROOT, validate_dxc


class StructuredTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dxc = validate_dxc()
        cls.source = (ROOT / "examples/structured/original.hlsl").read_text()
        cls.constraints = json.loads((ROOT / "examples/structured/constraints.json").read_text())

    @classmethod
    def compile(cls, source):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            path = Path(directory) / "input.hlsl"
            path.write_bytes(source.encode("utf-8"))
            result = subprocess.run([str(cls.dxc), "-T", "ps_6_0", "-E", "main", "-HV", "2021", "-ast-dump", str(path)],
                                    capture_output=True, text=True, encoding="utf-8", check=True)
        return import_shader(source, result.stdout)

    def values(self, source, inputs=None):
        return evaluate_model(self.compile(source), inputs or [[1, 2, 3, 4]])

    def test_material_matches_independent_formula(self):
        inputs = [[0, 0, -2], [0, 0, -3], [.8, .4, .2, .7], [1, .5, .25, 1], [.2, .8, 1, 1], [0, 0, -4, 0], [.1], [2]]
        expected = [.88, .24, .07, .7]
        for role in ("original", "optimized"):
            model = self.compile((ROOT / f"examples/structured/{role}.hlsl").read_text())
            constraint_spec(self.constraints, model, model)
            for actual, wanted in zip(evaluate_model(model, inputs), expected):
                self.assertAlmostEqual(actual, wanted)
            self.assertEqual(model["interface"][0]["name"], "input.geometry.normalWS")

    def test_copy_and_by_value_parameter_do_not_alias(self):
        source = '''struct S { float4 color; };
S Change(S s) { s.color += 10; return s; }
float4 main(float4 a:COLOR0):SV_Target {
 S original; original.color=a; S copy=original; copy=Change(copy);
 return original.color+copy.color;
}'''
        self.assertEqual(self.values(source), [12, 14, 16, 18])

    def test_nested_copy_updates_only_selected_path(self):
        source = '''struct T {float4 color;}; struct S {T first; T second;};
float4 main(float4 a:COLOR0):SV_Target {
 S x; x.first.color=a; x.second.color=a*2; S y=x;
 y.first.color+=10; return x.first.color+y.second.color;
}'''
        self.assertEqual(self.values(source), [3, 6, 9, 12])

    def test_repeated_calls_and_overloads(self):
        source = '''float Scale(float x) { x+=1; return x; }
float4 Scale(float4 x) { x*=2; return x; }
float4 main(float4 a:COLOR0):SV_Target { return Scale(a)+Scale(a*3)+Scale(0.0); }'''
        self.assertEqual(self.values(source), [9, 17, 25, 33])

    def test_helper_shadowing_and_global_read(self):
        source = '''cbuffer M:register(b0) {float4 color;};
float4 First(float4 color) { return color*2; }
float4 Second(float4 x) {return First(x)+color;}
float4 main(float4 a:COLOR0):SV_Target {return Second(a);}'''
        self.assertEqual(self.values(source, [[1, 2, 3, 4], [10]*4]), [12, 14, 16, 18])

    def test_nested_scope_shadow_and_outer_update(self):
        source = '''float4 main(float4 a:COLOR0):SV_Target {
 float4 result=a; { float4 a=result*2; result+=a; } return result;
}'''
        self.assertEqual(self.values(source), [3, 6, 9, 12])

    def test_partial_record_can_read_initialized_field(self):
        source = '''struct S {float4 color; float unused;};
float4 main(float4 a:COLOR0):SV_Target {S s; s.color=a; return s.color;}'''
        self.assertEqual(self.values(source), [1, 2, 3, 4])

    def test_uninitialized_record_copy_argument_and_return_rejected(self):
        fragments = [
            "S s; s.color=a; S t=s; return t.color;",
            "S s; s.color=a; return Use(s);",
            "S s=Make(a); return s.color;",
            "S s; return s.color;",
        ]
        header = '''struct S {float4 color; float missing;};
float4 Use(S s){return s.color;}
S Make(float4 a){S s; s.color=a; return s;}
float4 main(float4 a:COLOR0):SV_Target {'''
        for fragment in fragments:
            with self.subTest(fragment=fragment), self.assertRaises(ModelError):
                self.compile(header + fragment + "}")

    def test_normalize_in_unused_helper_call_needs_domain(self):
        source = '''float3 Unit(float3 value){return normalize(value);}
float4 main(float4 a:COLOR0):SV_Target {Unit(a.xyz); return a;}'''
        model = self.compile(source)
        data = {"schema": 2, "ranges": {}, "nonzero_vectors": []}
        with self.assertRaises(ModelError):
            constraint_spec(data, model, model)
        data["nonzero_vectors"] = ["a.xyz"]
        constraint_spec(data, model, model)

    def test_structured_domain_selector_and_missing_domain(self):
        model = self.compile(self.source)
        for selector in ("input.geometry.normalWS.xyz", "input.geometry.viewWS"):
            data = copy.deepcopy(self.constraints)
            data["nonzero_vectors"][0] = selector
            with self.assertRaises(ModelError):
                constraint_spec(data, model, model)
        data = copy.deepcopy(self.constraints)
        data["ranges"]["input.geometry.normalWS"] = {"min": "0", "max": "0"}
        with self.assertRaises(ModelError):
            constraint_spec(data, model, model)

    def test_record_leaf_named_like_swizzle_is_not_misparsed(self):
        source = '''struct P {float3 xyz:TEXCOORD0;};
float4 main(P input):SV_Target {return float4(normalize(input.xyz),1);}'''
        model = self.compile(source)
        data = {"schema": 2, "ranges": {}, "nonzero_vectors": ["input.xyz"]}
        constraint_spec(data, model, model)

    def test_interface_record_type_name_is_part_of_contract(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            output = Path(directory)
            path = output / "changed.hlsl"
            path.write_bytes(self.source.replace("PSInput", "DifferentInput").encode("utf-8"))
            result = subprocess.run(["python", str(ROOT / "tools/shaderformalize.py"), "prepare", "--original", str(ROOT / "examples/structured/original.hlsl"),
                                     "--optimized", str(path), "--constraints", str(ROOT / "examples/structured/constraints.json"), "--output", directory], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads((output / "result.json").read_text())["status"], "INVALID_INPUT")

    def test_conditional_helper_body_is_not_dropped(self):
        source = '''float4 Choose(float4 a){if(a.x>0) return a; return -a;}
float4 main(float4 a:COLOR0):SV_Target {return Choose(a);}'''
        self.assertEqual(self.values(source), [1, 2, 3, 4])
        self.assertEqual(self.values(source, [[-1, 2, 3, 4]]), [1, -2, -3, -4])

    def test_recursive_call_is_rejected(self):
        source = '''float4 Again(float4 a){return Again(a);}
float4 main(float4 a:COLOR0):SV_Target {return Again(a);}'''
        # The pinned DXC already rejects recursion before producing an AST.
        with self.assertRaises((ModelError, subprocess.CalledProcessError)):
            self.compile(source)

    def test_out_parameters_and_prototypes_rejected(self):
        sources = [
            "float4 F(inout float4 a){a+=1; return a;} float4 main(float4 a:COLOR0):SV_Target {float4 b=a;return F(b);}",
            "float4 F(float4 a); float4 F(float4 a){return a;} float4 main(float4 a:COLOR0):SV_Target{return F(a);}",
        ]
        for source in sources:
            with self.subTest(source=source), self.assertRaises(ModelError):
                self.compile(source)

    def test_entry_record_is_not_writable(self):
        source = '''struct P {float4 color:COLOR0;};
float4 main(P input):SV_Target {input.color+=1; return input.color;}'''
        with self.assertRaises(ModelError):
            self.compile(source)

    def test_unused_helper_with_unknown_statement_rejected(self):
        source = '''float4 Unused(float4 x){while(x.x>0) x-=1; return x;}
float4 main(float4 a:COLOR0):SV_Target {return a;}'''
        with self.assertRaises(ModelError):
            self.compile(source)

    def test_unused_helper_with_unsupported_operator_rejected(self):
        source = '''float4 Unused(float4 x){return x/2;}
float4 main(float4 a:COLOR0):SV_Target {return a;}'''
        with self.assertRaises(ModelError):
            self.compile(source)

    def test_unused_helper_with_unknown_intrinsic_rejected(self):
        source = '''float4 Unused(float4 x){return sin(x);}
float4 main(float4 a:COLOR0):SV_Target {return a;}'''
        with self.assertRaises(ModelError):
            self.compile(source)

    def test_unused_helpers_obey_statement_and_expression_context(self):
        bodies = ["x.x=1; return x;", "float4 y=(x=x+1); return y;",
                  "x/=2; return x;", "static float4 y=0; return x+y;", "return x; x+=1;"]
        for body in bodies:
            source = "float4 Unused(float4 x){" + body + "}\n"
            source += "float4 main(float4 a:COLOR0):SV_Target{return a;}"
            with self.subTest(body=body), self.assertRaises(ModelError):
                self.compile(source)

    def test_long_alias_chain_resolves_without_python_recursion(self):
        source = "float4 main(float4 a:COLOR0):SV_Target {float3 x=a.xyz;"
        source += "x=x;" * 1050
        source += "return float4(normalize(x),1);}"
        model = self.compile(source)
        constraint_spec({"schema": 2, "ranges": {}, "nonzero_vectors": ["a.xyz"]}, model, model)

    def test_unused_or_overwritten_arguments_still_need_domain(self):
        for body in ("return float4(1,2,3,4);", "x=float3(1,2,3); return float4(x,1);"):
            source = "float4 Ignore(float3 x){" + body + "}\n"
            source += "float4 main(float4 a:COLOR0):SV_Target{return Ignore(normalize(a.xyz));}"
            model = self.compile(source)
            data = {"schema": 2, "ranges": {}, "nonzero_vectors": []}
            with self.subTest(body=body), self.assertRaises(ModelError):
                constraint_spec(data, model, model)
            data["nonzero_vectors"] = ["a.xyz"]
            constraint_spec(data, model, model)

    def test_unused_struct_argument_keeps_normalization(self):
        source = '''struct S {float3 normal;};
S Make(float3 n){S s; s.normal=normalize(n); return s;}
float4 Ignore(S s){return float4(1,2,3,4);}
float4 main(float4 a:COLOR0):SV_Target{return Ignore(Make(a.xyz));}'''
        model = self.compile(source)
        with self.assertRaises(ModelError):
            constraint_spec({"schema": 2, "ranges": {}, "nonzero_vectors": []}, model, model)

    def test_uncalled_normalization_does_not_add_domain_premise(self):
        source = '''float3 Unused(float3 x){return normalize(x);}
float4 main(float4 a:COLOR0):SV_Target{return a;}'''
        model = self.compile(source)
        constraint_spec({"schema": 2, "ranges": {}, "nonzero_vectors": []}, model, model)

    def test_expanding_call_tree_has_explicit_bound(self):
        source = "float4 F0(float4 x){return x;}\n"
        for i in range(1, 14):
            source += f"float4 F{i}(float4 x){{return F{i-1}(x)+F{i-1}(x);}}\n"
        source += "float4 main(float4 a:COLOR0):SV_Target{return F13(a);}"
        with self.assertRaisesRegex(ModelError, "4096 numeric bindings"):
            self.compile(source)

    def test_repeated_record_types_have_pre_expansion_leaf_budget(self):
        source = "struct S0{float leaf;};\n"
        for i in range(1, 11):
            fields = ";".join(f"S{i-1} f{j}" for j in range(8))
            source += f"struct S{i}{{{fields};}};\n"
        source += "float4 main(float4 a:COLOR0):SV_Target{return a;}"
        with self.assertRaisesRegex(ModelError, "4096 numeric leaves"):
            self.compile(source)


if __name__ == "__main__":
    unittest.main()

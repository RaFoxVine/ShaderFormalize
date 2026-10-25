"""Actual DXC shared definitions, independent finite frames and failed references."""
import copy
from pathlib import Path
import subprocess
import unittest

from shader_ast import ModelError
from shader_eval import evaluate_model
from shader_lean import generate_lean
from shader_shared_eval import evaluate_shared
from shader_shared_lean import validate_shared
from shader_control_eval import evaluate_control, no_operations
from test_control import ENTRY, HEADER
from test_fragment import test_operations
import test_structured


class SharedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_structured.StructuredTests.setUpClass()

    def compile(self, source):
        return test_structured.StructuredTests.compile(source, "shared")

    def text(self, model):
        return generate_lean(model, model, spec={"ranges": [], "nonzero": []})

    def test_structured_material_matches_independent_formula(self):
        inputs = [[0,0,-2],[0,0,-3],[.8,.4,.2,.7],[1,.5,.25,1],[.2,.8,1,1],[0,0,-4,0],[.1],[2]]
        for role in ("original", "optimized"):
            model = self.compile(Path(f"examples/structured/{role}.hlsl").read_text())
            self.assertEqual(model["schema"], 6)
            for actual, expected in zip(evaluate_model(model, inputs), [.88,.24,.07,.7]):
                self.assertAlmostEqual(actual, expected)
            self.assertIn("structure original_Result", self.text(model))

    def test_nested_records_booleans_uint_and_overloads(self):
        source = '''struct T{float4 c;uint tag;bool enabled;};
T Change(T t){t.c+=1;t.tag=t.tag&255u;t.enabled=!t.enabled;return t;}
float Scale(float x){return x*2;} float4 Scale(float4 x){return x*3;}
''' + ENTRY + '''T t;t.c=a;t.tag=257u;t.enabled=false;t=Change(t);
return t.enabled?Scale(t.c)+Scale((float)t.tag):a;}'''
        model = self.compile(source)
        self.assertEqual(evaluate_model(model, [[1,2,3,4]]), [8,11,14,17])
        self.text(model)

    def test_complete_derivative_fields_and_masks_match_inline(self):
        inputs = [[[0,2,0,1],[1,4,0,1],[1,8,0,1]]]
        for derivative in ("ddx", "ddy"):
            source = "float F(float x){if(x>3.0)return x;return x;}" + ENTRY + f"return a.x>0.5?float4({derivative}(F(a.y)),0,0,1):a;" + "}"
            direct = source.replace("F(a.y)", "a.y")
            shared = evaluate_shared(self.compile(source), inputs, 3, test_operations)
            inline = evaluate_control(test_structured.StructuredTests.compile(direct), inputs, 3, test_operations)
            self.assertEqual(shared, inline)

    def test_nested_sampling_and_void_discard(self):
        source = HEADER + '''float4 Read(float2 uv){return tex.Sample(samp,uv);}
void Cut(float x){if(x>0.5)return;discard;}
''' + ENTRY + "if(a.x>0.0){Cut(a.y);return Read(a.xy);}return a;}"
        inputs = [[[1,1,0,1],[1,0,0,1],[0,0,0,1]]]
        shared = evaluate_shared(self.compile(source), inputs, 3, test_operations)
        inline = evaluate_control(test_structured.StructuredTests.compile(source), inputs, 3, test_operations)
        self.assertEqual(shared, inline)
        self.text(self.compile(source))

    def test_argument_and_call_domains_even_when_result_ignored(self):
        source = "void Ignore(float3 x){}" + ENTRY + "if(a.x>0.5)Ignore(normalize(a.yzw));return a;}"
        model = self.compile(source)
        self.assertEqual(evaluate_model(model, [[0,0,0,0]]), [0,0,0,0])
        with self.assertRaises(ValueError):
            evaluate_model(model, [[1,0,0,0]])
        text = self.text(model)
        self.assertIn("call0.defined", text)
        self.assertIn("∀ x : E", text)

    def test_unused_illegal_domain_not_main_obligation(self):
        model = self.compile("float3 Bad(float3 x){return normalize(x);}" + ENTRY + "return a;}")
        self.assertEqual(evaluate_model(model, [[0,0,0,0]]), [0,0,0,0])
        main = self.text(model).split("def original {", 1)[1].split("structure optimized_",1)[0]
        self.assertNotIn("call0.defined", main)

    def test_unused_unknown_or_uninitialized_and_recursive_rejected(self):
        for helper in ("float Bad(float x){return sin(x);}",
                       "float Bad(float x){float y;return y;}",
                       "float Bad(float x){return Bad(x);}"):
            with self.subTest(helper=helper), self.assertRaises((ModelError, subprocess.CalledProcessError)):
                self.compile(helper + ENTRY + "return a;}")

    def test_carrier_boundary_still_rejected(self):
        with self.assertRaises(ModelError):
            self.compile("uint Get(float x){return asuint(x);}" + ENTRY + "uint n=Get(asfloat(1u));return a;}")

    @staticmethod
    def diamond(levels):
        source = "void H0(){}"
        for i in range(1, levels):
            source += f"void H{i}(){{H{i-1}();H{i-1}();}}"
        return source + ENTRY + f"H{levels-1}();return a;" + "}"

    def test_shared_graph_has_linear_models_and_generated_definitions(self):
        model = self.compile(self.diamond(13))
        self.assertEqual(len(model["helpers"]), 13)
        self.assertEqual(sum(len(h["calls"]) for h in model["helpers"]), 24)
        text = self.text(model)
        self.assertEqual(text.count("\ndef original_helper"), 13)
        smaller = self.text(self.compile(self.diamond(7)))
        self.assertLess(len(text), len(smaller)*2.5)
        with self.assertRaises(ModelError):
            test_structured.StructuredTests.compile(self.diamond(13))

    def test_invalid_call_reference_order_and_types_rejected(self):
        model = self.compile("float F(float x){return x;}" + ENTRY + "return float4(F(a.x),0,0,1);}")
        for mutation in ("callee", "field", "type", "event", "parameter"):
            bad = copy.deepcopy(model)
            if mutation == "callee":
                bad["calls"][0]["helper"] = 999
            elif mutation == "field":
                bad["expression"] = {"kind":"call_result","width":4,"index":0,"field":99}
            elif mutation == "type":
                bad["calls"][0]["arguments"][0]["width"] = 4
            elif mutation == "parameter":
                bad["helpers"][0]["bindings"][0]["expression"]["index"] = 99
            else:
                bad["events"].insert(0, {"call": 0})
            with self.subTest(mutation=mutation), self.assertRaises(ModelError):
                validate_shared(bad)

    def test_mixed_and_unknown_schema_do_not_fall_through(self):
        source = ENTRY + "return a;}"
        model = self.compile(source)
        legacy = test_structured.StructuredTests.compile(source)
        for a,b in ((model,legacy),(legacy,model),(dict(legacy,schema=999),legacy)):
            with self.assertRaises(ModelError):
                generate_lean(a,b,spec={"ranges":[],"nonzero":[]})

    def test_malformed_tables_and_numeric_predicates_are_controlled(self):
        model = self.compile("float F(float x){return x;}" + ENTRY + "return float4(F(a.x),0,0,1);}")
        for context in ("entry", "guard", "alive", "calls"):
            bad = copy.deepcopy(model)
            number = {"kind":"literal", "width":1, "numerator":1, "denominator":1}
            if context == "entry":
                bad["calls"][0]["entry"] = number
            elif context == "guard":
                bad["bindings"][0]["guard"] = number
            elif context == "alive":
                bad["helpers"][0]["alive"] = number
            else:
                del bad["helpers"][0]["calls"]
            with self.subTest(context=context), self.assertRaises(ModelError):
                self.text(bad)
        # Well-formed references do not make malformed literal data acceptable.
        for numerator, denominator in ((None,1),(1,0)):
            bad = copy.deepcopy(model)
            bad["expression"] = {"kind":"splat", "width":4, "arguments":[
                {"kind":"literal", "width":1, "numerator":numerator, "denominator":denominator}]}
            with self.subTest(literal=(numerator,denominator)), self.assertRaises(ModelError):
                self.text(bad)

    def test_effectful_value_helpers_remain_outside_the_subset(self):
        for helper in ("float Cut(float x){clip(x);return x;}",
                       "float Cut(float x){discard;return x;}",
                       "void V(float x){clip(x);}float Cut(float x){V(x);return x;}"):
            with self.subTest(helper=helper), self.assertRaises(ModelError):
                self.compile(helper + ENTRY + "return a;}")

    def test_pure_sibling_domains_and_ops_remain_composable(self):
        source = "float F(float3 n,float d){return n.x+d;}" + ENTRY + "if(a.w>0.0)return float4(F(normalize(a.xyz),ddx(a.y)),0,0,1);return a;}"
        inputs = [[[1,2,0,1],[1,4,0,1],[1,8,0,1]]]
        actual = evaluate_shared(self.compile(source), inputs, 3, test_operations)
        expected = evaluate_control(test_structured.StructuredTests.compile(source), inputs, 3, test_operations)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()

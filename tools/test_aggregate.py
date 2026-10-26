"""Actual DXC matrices/arrays, typed addresses and independent numeric oracles."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

import test_structured
from test_control import ENTRY
from test_fragment import test_operations
from shader_ast import ModelError
from shader_eval import evaluate_model
from shader_lean import constraint_spec, generate_lean
from shader_shared_eval import evaluate_shared
from shaderformalize import ROOT, prepare


class AggregateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_structured.StructuredTests.setUpClass()

    def compile(self, source):
        return test_structured.StructuredTests.compile(source, "shared")

    def values(self, body, prefix="", inputs=None):
        model = self.compile(prefix + ENTRY + body + "}")
        generate_lean(model, model, spec={"ranges": [], "nonzero": []})
        return evaluate_model(model, inputs or [[1, 2, 3, 4]])

    def test_non_square_multiply_transpose_and_matrix_product(self):
        body = """float2x3 m=float2x3(1,2,3,4,5,6);
float3x2 t=transpose(m);float2x2 p=mul(m,t);
float3 left=mul(float2(1,2),m);float2 right=mul(m,float3(1,2,3));
return float4(left.x,left.z,right.y,p[1][0]);"""
        self.assertEqual(self.values(body), [9, 15, 32, 32])

    def test_normal_material_matches_independent_formula_and_wrong_variant_differs(self):
        models = {}
        for role in ("original", "optimized", "wrong"):
            models[role] = self.compile((ROOT / f"examples/aggregate/{role}.hlsl").read_text(encoding="utf-8"))
        constraints = json.loads((ROOT / "examples/aggregate/constraints.json").read_text(encoding="utf-8"))
        constraint_spec(constraints, models["original"], models["optimized"])
        inputs = [[0, 0, 1], [0, 0, 1], [1, .5], [-.25, 1], [.2, .4, .6], [.8, .4, 0], [.5, .25, 1, .7], [.2]]
        for view, expected in (([0, 0, 1], [.2625, .09375, .6, .7]),
                               ([0, 0, -1], [.4125, .13125, .8, .7])):
            inputs[1] = view
            for role in ("original", "optimized"):
                for actual, wanted in zip(evaluate_model(models[role], inputs), expected):
                    self.assertAlmostEqual(actual, wanted)
            self.assertNotAlmostEqual(evaluate_model(models["wrong"], inputs)[0], expected[0])

    def test_splat_is_full_matrix_and_truncation_preserves_rows(self):
        body = """float3x3 big=float3x3(1,2,3,4,5,6,7,8,9);
float2x2 m=(float2x2)big;m=m*(float2x2)2.0;
float2 r=mul(m,float2(1,1));return float4(r,m[0][1],m[1][0]);"""
        self.assertEqual(self.values(body), [6, 18, 4, 8])

    def test_one_row_or_column_vector1_is_not_scalar_scaling(self):
        cases = [
            "float2x1 m=float2x1(2,3);float1 v=4;float2 r=mul(m,v);return float4(r,0,1);",
            "float1x2 m=float1x2(2,3);float1 v=4;float2 r=mul(v,m);return float4(r,0,1);",
            "float2x1 m=float2x1(2,3);float2x1 r=mul(m,4.0);return float4(r[0][0],r[1][0],0,1);",
        ]
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(self.values(body), [8, 12, 0, 1])

    def test_nested_array_order_and_complete_initializers(self):
        body = "float x[2][3]={{1,2,3},{4,5,6}};return float4(x[1][2],x[0][2],x[1][0],x[0][0]);"
        self.assertEqual(self.values(body), [6, 3, 4, 1])

    def test_array_parameters_out_and_struct_inout(self):
        prefix = """struct S{float2 p;};
void Fill(out float v[2]){v[0]=1;v[1]=2;}
void Edit(inout S values[2]){values[1].p*=2.0;}
"""
        body = "S values[2];values[0].p=a.xy;values[1].p=a.zw;Edit(values);float v[2];Fill(v);return float4(values[1].p,v[0],v[1]);"
        self.assertEqual(self.values(body, prefix), [6, 8, 1, 2])

    def test_matrix_return_out_default_and_temporary_index(self):
        prefix = "float2x2 Scale(float2x2 m){return m*2.0;}void Fill(out float2x2 m,float k=2.0){m=(float2x2)k;m[1][0]=3;}"
        body = "float2x2 m;Fill(m);m=Scale(m);return float4(mul(m,float2(1,2)),m[0][0],m[1][0]);"
        self.assertEqual(self.values(body, prefix), [12, 14, 4, 6])
        prefix = "float2x2 Make(float4 a){return float2x2(a.x,a.y,a.z,a.w);}"
        self.assertEqual(self.values("return float4(Make(a)[1],Make(a)[0]);", prefix), [3, 4, 1, 2])

    def test_typed_zero_initialization(self):
        prefix = "struct S{float2 p;uint tag;bool enabled;float2x2 m;float v[2];};"
        body = "S s=(S)0;return float4(s.p.x,(float)s.tag,s.enabled,s.m[1][1]+s.v[1]);"
        self.assertEqual(self.values(body, prefix), [0, 0, 0, 0])

    def test_uint_and_bool_arrays_keep_their_leaf_types(self):
        prefix = "void Edit(inout uint words[2]){words[1]=words[1]|4u;}"
        body = "uint words[2]={1u,2u};bool flags[2]={true,false};Edit(words);return float4((float)words[0],(float)words[1],flags[0],flags[1]);"
        self.assertEqual(self.values(body, prefix), [1, 6, 1, 0])

    def test_partial_vector_writes_and_simultaneous_swizzle_swap(self):
        body = "float4 v;v.xy=a.yx;v.z=7;v.w=8;v.xy=v.yx;return v;"
        self.assertEqual(self.values(body), [1, 2, 7, 8])
        prefix = "void Fill(out float2 p,out float2 q){p=float2(1,2);q=float2(3,4);}"
        self.assertEqual(self.values("float4 v;Fill(v.yx,v.wz);return v;", prefix), [2, 1, 4, 3])

    def test_index_is_captured_before_copy_out_and_evaluated_once(self):
        prefix = "void Fill(out float x,out uint i){x=9;i=0u;}"
        body = "float v[3]={1,2,3};uint i=1u;Fill(v[i],i);return float4(v[0],v[1],v[2],(float)i);"
        self.assertEqual(self.values(body, prefix), [1, 9, 3, 0])
        prefix = "uint Next(inout uint i){i=i+1u;return i;}void Fill(out float x){x=9;}"
        body = "float v[3]={1,2,3};uint i=0u;Fill(v[Next(i)]);return float4(v[0],v[1],v[2],(float)i);"
        self.assertEqual(self.values(body, prefix), [1, 9, 3, 1])

    def test_dynamic_read_write_and_actual_bounds(self):
        body = "float v[2]={2,3};uint i=(uint)a.x;v[i]+=4;return float4(v[0],v[1],v[i],1);"
        self.assertEqual(self.values(body), [2, 7, 7, 1])
        with self.assertRaises(ValueError):
            self.values(body, inputs=[[2, 0, 0, 0]])
        body = "float v[2]={2,3};if(a.x>0.5){uint i=3u;v[i]=9;}return float4(v[0],v[1],0,1);"
        self.assertEqual(self.values(body, inputs=[[0, 0, 0, 0]]), [2, 3, 0, 1])
        with self.assertRaises(ValueError):
            self.values(body)

    def test_dynamic_struct_field_does_not_read_unrelated_uninitialized_field(self):
        prefix = "struct S{float x;float missing;};"
        body = "S v[2];v[0].x=2;v[1].x=3;uint i=(uint)a.x;v[i].x+=4;return float4(v[0].x,v[1].x,v[i].x,1);"
        self.assertEqual(self.values(body, prefix), [2, 7, 7, 1])

    def test_field_update_before_derivative_preserves_complete_positions(self):
        source = ENTRY + "float v[2]={a.y,a.z};if(a.x>0.5)v[0]=a.y;return float4(ddx(v[0]),0,0,1);}"
        direct = ENTRY + "return float4(ddx(a.y),0,0,1);}"
        inputs = [[[0, 2, 9, 1], [1, 4, 8, 1], [1, 8, 7, 1]]]
        self.assertEqual(evaluate_shared(self.compile(source), inputs, 3, test_operations),
                         evaluate_shared(self.compile(direct), inputs, 3, test_operations))

    def test_disjoint_components_and_static_elements_are_independent(self):
        prefix = "float Fill(out float x){x=2;return 3;}"
        self.assertEqual(self.values("float4 v=a;float s=Fill(v.x)+v.y;return float4(v.x,s,0,1);", prefix), [2, 5, 0, 1])
        prefix = "void Fill(out float x,out float y){x=2;y=3;}"
        self.assertEqual(self.values("float v[2];Fill(v[0],v[1]);return float4(v[0],v[1],0,1);", prefix), [2, 3, 0, 1])

    def test_partial_reads_and_dynamic_initialization_are_rejected(self):
        bodies = ["float2 v;v.x=1;return float4(v,0,1);",
                  "float2 v;v.x=1;return float4(v.y,0,0,1);",
                  "float2 v;if(a.x>0.5)v.x=1;else v.y=2;return float4(v,0,1);",
                  "float v[2];uint i=(uint)a.x;v[i]=2;return a;",
                  "float v[2];v[0]=1;uint i=(uint)a.x;return float4(v[i],0,0,1);"]
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(ModelError):
                self.compile(ENTRY + body + "}")

    def test_aliasing_duplicate_and_dynamic_output_addresses_rejected(self):
        prefix = "void Fill(out float x,out float y){x=2;y=3;}"
        bodies = ["float v[2];Fill(v[0],v[0]);return a;",
                  "float v[2]={1,2};uint i=0u;uint j=1u;Fill(v[i],v[j]);return a;"]
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(ModelError):
                self.compile(prefix + ENTRY + body + "}")
        with self.assertRaises((ModelError, subprocess.CalledProcessError)):
            self.compile("void Fill(out float2 x){x=1.0;}" + ENTRY + "float4 v=a;Fill(v.xx);return v;}")

    def test_index_dependencies_are_checked_in_unordered_siblings(self):
        prefix = "uint G(out uint i){i=1u;return 1u;}void F(out float x,uint y){x=(float)y;}"
        bodies = ["float v[2]={1,2};uint i=0u;F(v[i],G(i));return a;",
                  "float v[2]={1,2};uint i=0u;v[i]=(float)G(i);return a;",
                  "float v[2]={1,2};uint i=0u;v[i]+=(float)G(i);return a;"]
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(ModelError):
                self.compile(prefix + ENTRY + body + "}")

    def test_uniform_layout_range_groups_and_intersections(self):
        prefix = "struct S{row_major float2x3 frame;float weights[2];};cbuffer B:register(b0){S pal;}"
        source = prefix + ENTRY + "return float4(mul(pal.frame,a.xyz),pal.weights[1],1);}"
        model = self.compile(source)
        self.assertEqual([x["name"] for x in model["interface"]],
                         ["a", "pal.frame[0]", "pal.frame[1]", "pal.weights[0]", "pal.weights[1]"])
        data = {"schema": 2, "ranges": {"pal": {"min": "0", "max": "1"},
                "pal.frame[0]": {"min": "0.25", "max": "0.75"}}, "nonzero_vectors": []}
        spec = constraint_spec(data, model, model)
        self.assertEqual(spec["ranges"][0], (1, .25, .75))
        self.assertEqual(self.values("return float4(mul(pal.frame,a.xyz),pal.weights[1],1);", prefix,
                         [[1, 2, 3, 4], [1, 2, 3], [4, 5, 6], [8], [9]]), [14, 32, 9, 1])
        bad = copy.deepcopy(data)
        bad["ranges"]["pal.frame[0]"] = {"min": "2", "max": "3"}
        with self.assertRaises(ModelError):
            constraint_spec(bad, model, model)
        with self.assertRaises(ModelError):
            constraint_spec({"schema": 2, "ranges": {}, "nonzero_vectors": ["pal.frame"]}, model, model)

    def test_matrix_packing_is_compared_by_actual_prepare(self):
        body = ENTRY + "return float4(mul(_M,a.xy),0,1);}"
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            path = Path(directory)
            original, optimized = path / "original.hlsl", path / "optimized.hlsl"
            original.write_text("cbuffer B:register(b0){row_major float2x2 _M;}" + body)
            optimized.write_text("cbuffer B:register(b0){column_major float2x2 _M;}" + body)
            output = path / "output"
            output.mkdir()
            args = SimpleNamespace(original=original, optimized=optimized, frontend="shared", constraints=path / "unused.json")
            with self.assertRaises(ModelError) as error:
                prepare(args, output)
            self.assertEqual(error.exception.status, "INVALID_INPUT")

    def test_readonly_uniform_matrix_index_uses_const_builtin_method(self):
        prefix = "cbuffer B:register(b0){float2x2 m;}"
        body = "return float4(m[0][0],m[0][1],m[1][0],m[1][1]);"
        self.assertEqual(self.values(body, prefix, [[1, 2, 3, 4], [5, 6], [7, 8]]), [5, 6, 7, 8])
        with self.assertRaises((ModelError, subprocess.CalledProcessError)):
            self.compile(prefix + ENTRY + "m[0][0]=2;return a;}")

    def test_metadata_is_bound_and_malformed_groups_are_rejected(self):
        model = self.compile("cbuffer B:register(b0){float2x2 _M;}" + ENTRY + "return float4(mul(_M,a.xy),0,1);}")
        spec = {"ranges": [], "nonzero": []}
        text = generate_lean(model, model, spec=spec)
        changed = copy.deepcopy(model)
        changed["uniform_layout"][0]["layout"]["packing"] = "row_major"
        other = generate_lean(changed, changed, spec=spec)
        self.assertNotEqual(text, other)
        self.assertEqual(text.split("\n", 1)[1], other.split("\n", 1)[1])
        for invalid in ([True], [999], [], [1, 1]):
            changed = copy.deepcopy(model)
            changed["input_groups"]["_M"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ModelError):
                generate_lean(changed, changed, spec=spec)

    def test_bounded_index_data_is_checked_by_both_consumers(self):
        model = self.compile(ENTRY + "float v[2]={1,2};uint i=1u;return float4(v[i],0,0,1);}")
        index = next(i for i, b in enumerate(model["bindings"]) if b["expression"]["kind"] == "bounded_index")
        for size in (True, 0, 65, "2"):
            changed = copy.deepcopy(model)
            changed["bindings"][index]["expression"]["size"] = size
            for action in (generate_lean, evaluate_model):
                with self.subTest(size=size, action=action.__name__), self.assertRaises(ModelError):
                    if action is generate_lean:
                        action(changed, changed, spec={"ranges": [], "nonzero": []})
                    else:
                        action(changed, [[1, 2, 3, 4]])

    def test_unknown_recursive_and_noncanonical_type_metadata_rejected(self):
        model = self.compile(ENTRY + "float v[2]={1,2};return float4(v[0],0,0,1);}")
        invalid_tables = [
            {"$bad": {"kind": "array", "length": 2, "element": "NoSuchType"}},
            {"$array2<NoSuchType>": {"kind": "array", "length": 2, "element": "NoSuchType"}},
            {"$array2<S>": {"kind": "array", "length": 2, "element": "S"},
             "S": {"kind": "struct", "fields": [{"name": "v", "type": "$array2<S>"}]}},
            {"$matrix1x1": {"kind": "matrix", "rows": 2, "columns": 2}},
        ]
        for table in invalid_tables:
            changed = copy.deepcopy(model)
            changed["aggregate_types"] = table
            for action in (generate_lean, evaluate_model):
                with self.subTest(table=table, action=action.__name__), self.assertRaises(ModelError):
                    if action is generate_lean:
                        action(changed, changed, spec={"ranges": [], "nonzero": []})
                    else:
                        action(changed, [[1, 2, 3, 4]])

    def test_budget_carrier_and_legacy_boundaries(self):
        for body in ("float v[65];return a;", "float v[64][64][2];return a;",
                     "float2 v=0;v.x=asfloat(1u);return float4(v,0,1);"):
            with self.subTest(body=body), self.assertRaises(ModelError):
                self.compile(ENTRY + body + "}")
        for declaration in ("uint i;", "bool i;"):
            with self.assertRaises(ModelError):
                self.compile("cbuffer B:register(b0){" + declaration + "}" + ENTRY + "return a;}")
        with self.assertRaises(ModelError):
            test_structured.StructuredTests.compile(ENTRY + "float2x2 m=(float2x2)1;return float4(m[0],0,1);}")

"""Real DXC packing, independent integer results, and fail-closed carrier flow."""
import math
import unittest

from shader_ast import ModelError
from shader_eval import evaluate_model
from shader_lean import constraint_spec, generate_lean
from shaderformalize import ROOT
import test_structured

ENTRY = "float4 main(float4 a:COLOR0):SV_Target{"


class PackingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_structured.StructuredTests.setUpClass()

    def compile(self, body, header=""):
        return test_structured.StructuredTests.compile(header + ENTRY + body + "}")

    def test_material_against_separate_byte_formula_and_wrong_counterexample(self):
        models = {role: test_structured.StructuredTests.compile((ROOT / f"examples/packed/{role}.hlsl").read_text())
                  for role in ("original", "optimized", "wrong")}
        points = (-2, 0, 1/255, .5, 254/255, 1, 2)
        for red in points:
            for green in points:
                color = [red, green, .25, .75]
                expected = [math.trunc(max(0, min(1, v))*255)/256 for v in color[:2]] + color[2:]
                for role in ("original", "optimized"):
                    self.assertEqual(evaluate_model(models[role], [color]), expected)
        color = [0, 1, .25, 1]
        self.assertNotEqual(evaluate_model(models["original"], [color]), evaluate_model(models["wrong"], [color]))

    def test_uint_wrap_masks_and_shifts(self):
        cases = {"0xffffffffu+1u": 0, "0u-1u": 2**32-1, "0xffffffffu*2u": 2**32-2,
                 "~0u": 2**32-1, "-1u": 2**32-1, "(0xff00u^0xf0f0u)&0xffffu": 4080,
                 "(1u<<31u)>>31u": 1, "asuint(17u)": 17}
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                model = self.compile(f"uint u={expression};return float4((float)u,0,0,1);")
                self.assertEqual(evaluate_model(model, [[0,0,0,0]])[0], expected)

    def test_unsigned_literal_can_be_numerically_converted_to_float(self):
        model = self.compile("return a*10u;")
        self.assertEqual(evaluate_model(model, [[1,2,3,4]]), [10,20,30,40])

    def test_real_cast_truncates_and_uint_comparison_is_unsigned(self):
        model = self.compile("uint u=(uint)a.x;bool b=u<0xffffffffu;return b?float4((float)u,0,0,1):a;")
        self.assertEqual(evaluate_model(model, [[3.75,0,0,0]]), [3,0,0,1])
        self.assertEqual(evaluate_model(model, [[4294967295,0,0,0]]), [4294967295,0,0,0])
        for bad in (-.25, 4294967296):
            with self.assertRaises(ValueError):
                evaluate_model(model, [[bad,0,0,0]])

    def test_untaken_invalid_cast_and_shift_use_evaluation_guard(self):
        for expr in ("(uint)(a.x-2.0)", "(1u<<32u)"):
            model = self.compile(f"uint u=a.x>0.5?{expr}:7u;return float4((float)u,0,0,1);")
            self.assertEqual(evaluate_model(model, [[0,0,0,0]])[0], 7)
            with self.assertRaises(ValueError):
                evaluate_model(model, [[1,0,0,0]])
            spec = constraint_spec({"schema":2,"ranges":{},"nonzero_vectors":[]}, model, model)
            text = generate_lean(model, model, spec=spec)
            self.assertIn("→", text)
            self.assertTrue(any(binding["expression"]["kind"] in ("real_to_uint", "uint_shl")
                                and binding["guard"]["kind"] != "boolean" for binding in model["bindings"]))

    def test_ignored_executed_helper_argument_still_checked(self):
        model = self.compile("uint u=Ignore((uint)(a.x-2.0));return float4((float)u,0,0,1);",
                             "uint Ignore(uint value){return 7u;}")
        with self.assertRaises(ValueError):
            evaluate_model(model, [[0,0,0,0]])

    def test_carrier_copies_structs_and_same_category_branch(self):
        body = "S s;s.carrier=asfloat(0xffffffffu);S t=s;float c;if(a.x>0.5)c=t.carrier;else c=asfloat(7u);uint u=asuint(c);return float4((float)u,0,0,1);"
        model = self.compile(body, "struct S{float carrier;};")
        for x, expected in ((0,7),(1,2**32-1)):
            self.assertEqual(evaluate_model(model, [[x,0,0,0]])[0], expected)
        text = generate_lean(model, model, spec={"ranges":[],"nonzero":[]})
        self.assertIn("E → BitVec 32", text)

    def test_payload_misuse_cannot_escape_through_values_or_effects(self):
        bodies = ["float c=asfloat(7u);float x=c+1.0;return a;",
                  "float c=asfloat(7u);return float4(c,0,0,1);",
                  "float c=asfloat(7u);clip(c);return a;",
                  "float c=asfloat(7u);float x=ddx(c);return a;",
                  "float c=asfloat(7u);uint u=(uint)c;return a;",
                  "float c=asfloat(7u);bool b=c==0.0;return a;",
                  "float c=a.x>0.0?asfloat(7u):0.0;return a;",
                  "uint u=asuint(a.x);return a;"]
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(ModelError):
                self.compile(body)

    def test_struct_payload_cannot_cross_helper_boundary(self):
        for header, body in [
            ("struct S{float c;};float F(S s){return 0.0;}", "S s;s.c=asfloat(7u);float f=F(s);return a;"),
            ("struct S{float c;};S F(){S s;s.c=asfloat(7u);return s;}", "S s=F();return a;"),
            ("float F(){return asfloat(7u);}", "float c=F();return a;")]:
            with self.subTest(header=header), self.assertRaises(ModelError):
                self.compile(body, header)

    def test_uncalled_bad_helper_rejected(self):
        with self.assertRaises(ModelError):
            self.compile("return a;", "float Bad(){float c=asfloat(7u);return c*2.0;}")

    def test_new_leaf_is_rejected_at_stage_interface(self):
        with self.assertRaises(ModelError):
            test_structured.StructuredTests.compile("float4 main(uint id:TEXCOORD0):SV_Target{return float4((float)id,0,0,1);}")

    def test_old_and_new_models_can_share_generated_target(self):
        old = self.compile("return a;")
        new = self.compile("uint u=7u;return a;")
        self.assertEqual(old["schema"], 2)
        self.assertEqual(new["schema"], 5)
        self.assertIn("import ShaderFormalize.Packing", generate_lean(old, new, spec={"ranges":[],"nonzero":[]}))


if __name__ == "__main__":
    unittest.main()

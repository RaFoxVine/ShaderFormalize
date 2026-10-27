"""DXC overloads, boundary values and executed domains for seven real operations."""
import copy
import json
from fractions import Fraction
import unittest

import test_structured
from shader_ast import ModelError
from shader_eval import evaluate_model
from shader_lean import generate_lean
from shader_math import evaluate_math, math_imports, valid_math_shape
from shader_shared_lean import validate_shared
from shaderformalize import ROOT


class MathExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_structured.StructuredTests.setUpClass()

    def compile(self, body, frontend="shared", prefix=""):
        source = prefix + "float4 main(float4 a:COLOR0):SV_Target {" + body + "}"
        return test_structured.StructuredTests.compile(source, frontend)

    def values(self, body, values, frontend="shared", prefix=""):
        model = self.compile(body, frontend, prefix)
        generate_lean(model, model, spec={"ranges": [], "nonzero": []})
        return evaluate_model(model, [values])

    def test_negative_fractions_and_integer_boundaries(self):
        values = [-1.25, -1, 0, 2.25]
        for frontend in ("auto", "shared"):
            self.assertEqual(self.values("return floor(a);", values, frontend), [-2, -1, 0, 2])
            self.assertEqual(self.values("return ceil(a);", values, frontend), [-1, -1, 0, 3])
            self.assertEqual(self.values("return frac(a);", values, frontend), [.75, 0, 0, .25])

    def test_step_ties_and_scalar_splat(self):
        for frontend in ("auto", "shared"):
            self.assertEqual(self.values("return step(1.0,a);", [-1, 0, 1, 2], frontend), [0, 0, 1, 1])
            self.assertEqual(self.values("return step(a,a);", [-1, 0, 1, 2], frontend), [1]*4)

    def test_smoothstep_clamps_and_interpolates(self):
        for frontend in ("auto", "shared"):
            self.assertEqual(self.values("return smoothstep(0.0,1.0,a);", [-1, 0, .5, 2], frontend), [0, 0, .5, 1])

    def test_componentwise_widths_and_float1_helper_spelling(self):
        for width, mask in [(1, "x"), (2, "xy"), (3, "xyz"), (4, "xyzw")]:
            suffix = ",0" * (4-width)
            body = f"float{width} v=frac(a.{mask});return float4(v{suffix});"
            self.assertEqual(self.values(body, [-1.25]*4), [.75]*width+[0]*(4-width))
        prefix = "float1 Quantize(float1 x){float1 y=ceil(x);return y;}"
        self.assertEqual(self.values("return float4(Quantize(a.x),0,0,1);", [-1.25]*4, prefix=prefix), [-1, 0, 0, 1])

    def test_cross_is_whole_vector_and_has_independent_sign_witness(self):
        for frontend in ("auto", "shared"):
            self.assertEqual(self.values("return float4(cross(a.xyz,float3(0,1,0)),1);", [1, 2, 3, 0], frontend), [-3, 0, 1, 1])
        self.assertNotEqual(evaluate_math("cross", [[1, 0, 0], [0, 1, 0]]), [0, 0, -1])

    def test_reflect_uses_dot_and_does_not_assume_unit_normal(self):
        for width, mask in [(1, "x"), (2, "xy"), (3, "xyz"), (4, "xyzw")]:
            suffix = ",0" * (4-width)
            normal = ",".join(["2"]*width)
            body = f"float{width} v=reflect(a.{mask},float{width}({normal}));return float4(v{suffix});"
            values = [1, 2, 3, 4]
            dot = sum(values[:width])*2
            self.assertEqual(self.values(body, values), [i-4*dot for i in values[:width]]+[0]*(4-width))

    def test_smoothstep_inactive_zero_domain_is_totalized(self):
        body = "if(a.x>0){float unused=smoothstep(0,0,a.x);}return a;"
        self.assertEqual(self.values(body, [-1, 0, 0, 1]), [-1, 0, 0, 1])
        with self.assertRaisesRegex(ValueError, "smoothstep"):
            self.values(body, [1, 0, 0, 1])
        self.assertEqual(evaluate_math("smoothstep", [[0], [0], [1]], active=False), [0])

    def test_smoothstep_unused_value_and_argument_keep_domains(self):
        for body, prefix in [("float unused=smoothstep(1,0,a.x);return a;", ""),
                             ("float ignored=Ignore(smoothstep(0,0,a.x));return a;", "float Ignore(float x){return 1;}")]:
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, "smoothstep"):
                self.values(body, [0]*4, prefix=prefix)

    def test_short_circuit_and_ternary_guard_the_domain(self):
        body = "float v=a.x>0?smoothstep(0,a.x,a.y):0;return float4(v,v,v,1);"
        self.assertEqual(self.values(body, [0, 2, 0, 0]), [0, 0, 0, 1])
        body = "bool b=a.x>0 && smoothstep(0,a.x,a.y)>0;return b?a:0;"
        self.assertEqual(self.values(body, [0, 2, 0, 0]), [0]*4)

    def test_floor_import_in_uncalled_helper_and_legacy_no_import(self):
        model = self.compile("return a;", prefix="float Unused(float x){return floor(x);}")
        text = generate_lean(model, model, spec={"ranges": [], "nonzero": []})
        self.assertIn("import Mathlib.Algebra.Order.Floor.Ring", text)
        self.assertEqual(math_imports([{"helpers": [{"expression": {"kind": "ceil"}}]}]),
                         "import Mathlib.Data.Real.Archimedean\nimport Mathlib.Algebra.Order.Floor.Ring\n")
        legacy = self.compile("return a;")
        self.assertNotIn("import Mathlib.Algebra.Order.Floor", generate_lean(legacy, legacy, spec={"ranges": [], "nonzero": []}))

    def test_symbolic_fin_emission_has_all_cross_and_reflect_components(self):
        for name, expression in [("cross", "cross(a.xyz,a.zyx)"), ("reflect", "reflect(a.xyz,a.zyx)")]:
            model = self.compile(f"return float4({expression},1);")
            text = generate_lean(model, model, spec={"ranges": [], "nonzero": []})
            for index in (0, 1, 2):
                self.assertIn(f"⟨{index}, by decide⟩", text, name)

    def test_smoothstep_goal_has_strict_executed_domain(self):
        model = self.compile("float unused=smoothstep(a.x,a.y,a.z);return a;")
        text = generate_lean(model, model, spec={"ranges": [], "nonzero": []})
        self.assertIn(" < ", text)
        self.assertIn("→", text)
        self.assertNotIn("inputsValid", text)

    def test_exact_fraction_oracle(self):
        self.assertEqual(evaluate_math("frac", [[Fraction(-5,4)]]), [Fraction(3,4)])
        self.assertEqual(evaluate_math("smoothstep", [[0], [2], [Fraction(1,2)]]), [Fraction(5,32)])

    def test_shapes_and_serialized_tampering(self):
        self.assertFalse(valid_math_shape("cross", 4, [4, 4]))
        self.assertFalse(valid_math_shape("reflect", 3, [3, 2]))
        model = self.compile("return float4(cross(a.xyz,a.zyx),1);")
        bad = copy.deepcopy(model)
        def damage(value):
            if isinstance(value, dict):
                if value.get("kind") == "cross":
                    value["arguments"] = []
                for child in value.values(): damage(child)
            elif isinstance(value, list):
                for child in value: damage(child)
        damage(bad)
        with self.assertRaisesRegex(ModelError, "math operation shape"):
            validate_shared(bad)

    def test_material_controls_have_independent_finite_witnesses(self):
        base = ROOT / "examples/math-extensions"
        cases = json.loads((base / "controls.json").read_text(encoding="utf-8"))["cases"]
        for case in cases:
            left = test_structured.StructuredTests.compile((base / case["original"]).read_text(encoding="utf-8"), case["frontend"])
            right = test_structured.StructuredTests.compile((base / case["optimized"]).read_text(encoding="utf-8"), case["frontend"])
            values = [[-1.25, .5, 2, 0]]
            if len(left["interface"]) == 2:
                values.append([0, 2, 1, 0])
            if case["expected"] == "PROVED":
                self.assertEqual(evaluate_model(left, values), evaluate_model(right, values), case["name"])
            elif case["name"] == "wrong-boundary":
                self.assertNotEqual(evaluate_model(left, values), evaluate_model(right, values))
            else:
                with self.assertRaisesRegex(ValueError, "smoothstep"):
                    evaluate_model(left, values)


if __name__ == "__main__":
    unittest.main()

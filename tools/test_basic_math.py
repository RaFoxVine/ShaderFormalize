"""Typed DXC math imports, guarded domains and independent finite checks."""
import copy
import math
import unittest
import test_structured

from shader_ast import ModelError
from shader_eval import evaluate_model
from shader_lean import generate_lean
from shader_shared_lean import validate_shared
from shaderformalize import ROOT


ENTRY = "float4 main(float4 a:COLOR0):SV_Target {"


class BasicMathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_structured.StructuredTests.setUpClass()

    def compile(self, body, frontend="shared", prefix=""):
        return test_structured.StructuredTests.compile(prefix + ENTRY + body + "}", frontend)

    def values(self, body, values=None, frontend="shared", prefix=""):
        model = self.compile(body, frontend, prefix)
        generate_lean(model, model, spec={"ranges": [], "nonzero": []})
        return evaluate_model(model, values or [[1, 4, 9, 16]])

    def test_all_componentwise_intrinsics_and_scalar_splats(self):
        cases = [
            ("min(a,5.0)", [1, 4, 5, 5]),
            ("max(a,5.0)", [5, 5, 9, 16]),
            ("abs(-a)", [1, 4, 9, 16]),
            ("clamp(a,2.0,10.0)", [2, 4, 9, 10]),
            ("sqrt(a)", [1, 2, 3, 4]),
            ("rcp(a)", [1, .25, 1 / 9, .0625]),
            ("rsqrt(a)", [1, .5, 1 / 3, .25]),
            ("a/2.0", [.5, 2, 4.5, 8]),
        ]
        for expression, expected in cases:
            for frontend in ("auto", "shared"):
                with self.subTest(expression=expression, frontend=frontend):
                    self.assertEqual(self.values(f"return {expression};", frontend=frontend), expected)

    def test_scalar_and_float2_float3_widths(self):
        for width, selection in ((1, "x"), (2, "xy"), (3, "xyz")):
            body = f"float{width if width > 1 else ''} x=sqrt(a.{selection});return float4(x,0,0,0);"
            # Build exactly four constructor components for each width.
            body = body.replace("x,0,0,0", "x" + ",0" * (4 - width))
            self.assertEqual(self.values(body), [1, 2, 3][:width] + [0] * (4 - width))
        self.assertEqual(self.values("return float4(min(a.x,2.0),max(a.x,2.0),abs(-a.x),rcp(a.x));"), [1, 2, 1, 1])

    def test_float1_spelling_in_local_parameter_and_helper_call(self):
        prefix = "float1 Radius(float1 value){float1 root=sqrt(abs(value));return root;}"
        body = "float1 radius=Radius(a.x);return float4(radius,radius,radius,1);"
        for frontend in ("auto", "shared"):
            with self.subTest(frontend=frontend):
                self.assertEqual(self.values(body, [[4, 0, 0, 0]], frontend, prefix), [2, 2, 2, 1])

    def test_length_and_distance_include_scalar_and_zero(self):
        expected = [math.sqrt(98), 3, 1, 0]
        for frontend in ("auto", "shared"):
            actual = self.values("return float4(length(a.xyz),distance(a.xy,float2(1,1)),length(-a.x),distance(a.x,a.x));", frontend=frontend)
            for value, wanted in zip(actual, expected):
                self.assertAlmostEqual(value, wanted)
        self.assertEqual(self.values("return float4(length(a.xyz),distance(a.xy,a.xy),0,1);", [[0, 0, 0, 0]]), [0, 0, 0, 1])

    def test_helper_struct_and_shared_definitions(self):
        prefix = "struct S {float3 value;}; S Shade(S s){s.value=clamp(sqrt(abs(s.value)),0,1);return s;}"
        body = "S s;s.value=a.xyz;S t=Shade(s);return float4(t.value,distance(s.value,t.value));"
        result = self.values(body, prefix=prefix)
        self.assertEqual(result[:3], [1, 1, 1])
        self.assertAlmostEqual(result[3], math.sqrt(73))

    def test_domains_are_guarded_and_retained_when_result_unused(self):
        body = "if(a.x>=0){float unused=sqrt(a.x);}return a;"
        model = self.compile(body)
        generated = generate_lean(model, model, spec={"ranges": [], "nonzero": []})
        self.assertIn("Real.sqrt", generated)
        self.assertIn("→ ((0 : ℝ) ≤", generated)
        self.assertEqual(evaluate_model(model, [[-4, 0, 0, 1]]), [-4, 0, 0, 1])
        with self.assertRaisesRegex(ValueError, "sqrt"):
            self.values("float unused=sqrt(a.x);return a;", [[-4, 0, 0, 1]])

    def test_short_circuit_ternary_preserves_domains(self):
        body = "float x=a.x>0?sqrt(a.x)+rcp(a.x):0;return float4(x,x,x,1);"
        self.assertEqual(self.values(body, [[0, 0, 0, 0]]), [0, 0, 0, 1])
        self.assertEqual(self.values(body, [[-1, 0, 0, 0]]), [0, 0, 0, 1])
        body = "bool positive=a.x>0 && rcp(a.x)>0;return positive?a:0;"
        self.assertEqual(self.values(body, [[0, 0, 0, 0]]), [0, 0, 0, 0])

    def test_nonzero_and_ordered_bounds_obligations(self):
        cases = ["return a/a.x;", "return rcp(a);", "return rsqrt(a);", "return clamp(a,1.0,0.0);"]
        for body in cases:
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.values(body, [[0, -1, 1, 2]])
        text = generate_lean(self.compile("return a/a;"), self.compile("return a/a;"), spec={"ranges": [], "nonzero": []})
        self.assertEqual(text.count("≠ (0 : ℝ)"), 8)

    def test_unused_helper_argument_still_requires_domain(self):
        prefix = "float Ignore(float unused){return 1;}"
        with self.assertRaisesRegex(ValueError, "divide"):
            self.values("float ignored=Ignore(a.x/0.0);return a;", prefix=prefix)

    def test_uninvoked_helper_adds_no_runtime_domain(self):
        prefix = "float Unused(float x){return sqrt(x)/0.0;}"
        self.assertEqual(self.values("return a;", [[-1, 0, 1, 2]], prefix=prefix), [-1, 0, 1, 2])

    def test_new_auto_uses_guarded_model_and_old_target_stays_plain(self):
        self.assertEqual(self.compile("return min(a,a);", "auto")["schema"], 4)
        self.assertEqual(self.compile("return a*2;", "auto")["schema"], 2)
        old = self.compile("return a;", "auto")
        new = self.compile("return min(a,a);", "auto")
        self.assertIn("Control.finish", generate_lean(old, new, spec={"ranges": [], "nonzero": []}))

    def test_material_pair_and_wrong_color_have_independent_oracle(self):
        models = {}
        for role in ("original", "optimized", "wrong"):
            source = (ROOT / "examples/basic-math" / f"{role}.hlsl").read_text(encoding="utf-8")
            models[role] = test_structured.StructuredTests.compile(source, "shared")
        for tint, height in (([.2, .4, .8], 0), ([-.5, 2, -.3], -4), ([1, 0, 3], 16)):
            inputs = [tint, [height]]
            radial = math.sqrt(max(height, 0) + 1)
            expected = [min(abs(value), 1) / (radial + 1) / 2 for value in tint] + [1 / radial]
            for role in ("original", "optimized"):
                with self.subTest(role=role, tint=tint, height=height):
                    for actual, wanted in zip(evaluate_model(models[role], inputs), expected):
                        self.assertAlmostEqual(actual, wanted)
        witness = [[1, .5, .25], [0]]
        self.assertNotEqual(evaluate_model(models["original"], witness), evaluate_model(models["wrong"], witness))

    def test_integer_matrix_and_compound_division_are_rejected(self):
        cases = [
            "uint n=1u;uint m=max(n,2u);return a;",
            "float2x2 m=float2x2(1,2,3,4);float2x2 n=sqrt(m);return a;",
            "float4 x=a;x/=2;return x;",
        ]
        for body in cases:
            with self.subTest(body=body), self.assertRaises(ModelError):
                self.compile(body)

    def test_serialized_math_shape_tampering_is_rejected(self):
        model = self.compile("return sqrt(a);")
        malformed = copy.deepcopy(model)
        operation = next(binding["expression"] for binding in malformed["bindings"] if binding["expression"]["kind"] == "sqrt")
        operation["arguments"] = []
        with self.assertRaisesRegex(ModelError, "math operation shape"):
            validate_shared(malformed)


if __name__ == "__main__":
    unittest.main()

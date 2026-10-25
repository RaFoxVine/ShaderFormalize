"""Real DXC source tests for opaque whole fields and ordered clipping effects."""
import copy
import json
import unittest

from shader_ast import ModelError
from shader_fragment import FragmentEmitter
from shader_fragment_eval import evaluate_fragment
from shader_lean import constraint_spec, generate_lean
from shaderformalize import ROOT
import test_structured

HEADER = "Texture2D<float4> tex:register(t0); SamplerState samp:register(s0); "
ENTRY = "float4 main(float2 uv:TEXCOORD0):SV_Target {"


def test_operations(kind, expr, context, arguments):
    # Deliberately depends on all locations and on operation identity/context.
    # This catches a mistaken scalar-only lifting independently of GPU derivatives.
    field = arguments[0]
    if kind == "derivative":
        sign = 1 if expr["mode"].startswith("ddx") else -2
        return [[sign * (field[-1][i] - field[0][i]) + len(context) for i in range(len(field[0]))] for _ in field]
    values = []
    for point, uv in enumerate(field):
        lod = arguments[1][point][0] if expr["mode"] == "SampleLevel" else 0
        grad = sum(arguments[1][point]) + sum(arguments[2][point]) if expr["mode"] == "SampleGrad" else 0
        sampler = .2 if expr["sampler"] == "sampler_LinearClamp" else 0
        values.append([uv[0] + lod + sampler, uv[1] + grad, .4, uv[0]])
    return values


class FragmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_structured.StructuredTests.setUpClass()

    def compile(self, source):
        return test_structured.StructuredTests.compile(source)

    def render(self, body, uv=None):
        model = self.compile(ENTRY + body + "}")
        return evaluate_fragment(model, [uv or [[0, 0], [.5, .25], [1, 1]]], 3, test_operations)

    def test_all_derivative_modes_keep_identity(self):
        for name in ("ddx", "ddy", "ddx_fine", "ddy_fine", "ddx_coarse", "ddy_coarse"):
            model = self.compile(ENTRY + f"float2 d={name}(uv); return float4(d,0,1);" + "}")
            self.assertEqual(model["schema"], 3)
            self.assertEqual(model["bindings"][0]["expression"]["mode"], name)
            text = generate_lean(model, model, spec={"ranges": [], "nonzero": []})
            self.assertIn(f'ops.derivative "{name}" []', text)
            self.assertIn("∀ (E : Type) (ops : Fragment.Ops E)", text)

    def test_scalar_derivative_and_complete_input_field(self):
        a = self.render("return float4(ddx(uv.x),0,0,1);", [[0, 0], [.5, .25], [1, 1]])
        b = self.render("return float4(ddx(uv.x),0,0,1);", [[0, 0], [.5, .25], [2, 1]])
        self.assertEqual(a[1][0], 1)
        self.assertEqual(b[1][0], 2)

    def test_sampling_modes_and_resources(self):
        for expression, mode in (("tex.Sample(samp,uv)", "Sample"), ("tex.SampleLevel(samp,uv,1.0)", "SampleLevel"), ("tex.SampleGrad(samp,uv,ddx(uv),ddy(uv))", "SampleGrad")):
            model = self.compile(HEADER + ENTRY + "return " + expression + ";}")
            samples = [binding["expression"] for binding in model["bindings"] if binding["expression"]["kind"] == "sample"]
            self.assertEqual(samples[-1]["mode"], mode)
            self.assertEqual(model["resources"], [{"name": "tex", "type": "Texture2D", "register": "t0"}, {"name": "samp", "type": "SamplerState", "register": "s0"}])
            self.assertEqual(evaluate_fragment(model, [[[0, 0], [.5, .25], [1, 1]]], 3, test_operations)[1][3], .5)

    def test_clip_zero_boundary_and_vector_any_negative(self):
        values = self.render("clip(uv.x-0.5); return float4(1,0,0,1);")
        self.assertIsNone(values[0])
        self.assertIsNotNone(values[1])
        self.assertIsNotNone(values[2])
        vector = self.render("clip(uv-float2(0.5,0.5)); return float4(1,0,0,1);")
        self.assertIsNone(vector[1])
        self.assertIsNotNone(vector[2])

    def test_discard_comparison_operators(self):
        expected = {"<": [False, True, True], "<=": [False, False, True], ">": [True, True, False], ">=": [True, False, False], "==": [True, False, True], "!=": [False, True, False]}
        for operator, mask in expected.items():
            values = self.render(f"if(uv.x {operator} 0.5) {{discard;}} return float4(1,0,0,1);")
            self.assertEqual([value is not None for value in values], mask)
        self.assertEqual(self.render("discard; return float4(1,0,0,1);"), [None]*3)

    def test_void_helper_return_and_parameter_snapshot(self):
        source = "void Cut(float x){ {clip(x); return;} } " + ENTRY + "Cut(uv.x-0.5); float x=1; clip(x); x=-1.0; return float4(1,0,0,1);}"
        model = self.compile(source)
        values = evaluate_fragment(model, [[[0, 0], [.5, .25], [1, 1]]], 3, test_operations)
        self.assertEqual([value is not None for value in values], [False, True, True])
        self.assertEqual(len(model["effects"]), 2)

    def test_context_is_captured_at_operation_not_assignment(self):
        model = self.compile(HEADER + ENTRY + "float2 a=ddx(uv); clip(uv.x); float4 b=tex.Sample(samp,uv); float2 c=ddy(uv); return b+float4(a+c,0,0);}")
        contexts = []
        for binding in model["bindings"]:
            expr = binding["expression"]
            if expr["kind"] in ("sample", "derivative"):
                contexts.append(expr["context"])
        self.assertEqual(contexts, [0, 1, 1])
        text = generate_lean(model, model, spec={"ranges": [], "nonzero": []})
        self.assertLess(text.index("let c0"), text.index('ops.sample "tex" "samp" [c0]'))

    def test_bad_context_fails_closed(self):
        model = self.compile(ENTRY + "return float4(ddx(uv),0,1);}")
        broken = copy.deepcopy(model)
        broken["bindings"][0]["expression"]["context"] = 1
        with self.assertRaises(ModelError):
            FragmentEmitter(broken).definition("invalid", "(p0 : E → Vec 2)")

    def test_unsupported_resources_overloads_and_control_flow(self):
        fragments = [
            HEADER + ENTRY + "return tex.SampleBias(samp,uv,0.0);}",
            HEADER + ENTRY + "return tex.Sample(samp,uv,int2(1,0));}",
            "Texture2D<float> tex:register(t0); SamplerState samp:register(s0);" + ENTRY + "return tex.Sample(samp,uv);}",
            "Texture2D tex; SamplerState samp;" + ENTRY + "return tex.Sample(samp,uv);}",
            ENTRY + "if(uv.x<0.5) discard; else discard; return float4(1,0,0,1);}",
            ENTRY + "if(uv.x<0.5) {float x=1; discard;} return float4(1,0,0,1);}",
            ENTRY + "if(uv.x) discard; return float4(1,0,0,1);}",
            ENTRY + "bool x=uv.x<0.5; if(x) discard; return float4(1,0,0,1);}",
            "void Cut(){discard;} float F(){Cut();return 1;} " + ENTRY + "return float4(F(),0,0,1);}",
            "float F(){clip(1.0);return 1;} " + ENTRY + "return float4(F(),0,0,1);}",
        ]
        for source in fragments:
            with self.subTest(source=source), self.assertRaises(ModelError):
                self.compile(source)

    def test_uncalled_helpers_statically_checked(self):
        for helper in ("void Bad(float x){if(x<1) {x=2;discard;}}", "float Bad(float x){clip(x);return x;}"):
            with self.assertRaises(ModelError):
                self.compile(helper + ENTRY + "return float4(1,0,0,1);}")

    def test_sample_and_derivative_rvalue_swizzles(self):
        for expression in ("tex.Sample(samp,uv).rgba", "ddx(float4(uv,0,1)).xyzw"):
            model = self.compile(HEADER + ENTRY + "return " + expression + ";}")
            values = evaluate_fragment(model, [[[0, 0], [.5, .25], [1, 1]]], 3, test_operations)
            self.assertEqual(len(values[0]), 4)
        # Rvalue component syntax is statically checked even in an uncalled helper.
        self.compile(HEADER + "float2 Read(float2 uv){return tex.Sample(samp,uv).xy;} " + ENTRY + "return float4(uv,0,1);}")

    def test_nested_opaque_fields_emit_once_and_grow_linearly(self):
        uv = "uv"
        for _ in range(10):
            uv = "tex.Sample(samp," + uv + ").xy"
        model = self.compile(HEADER + ENTRY + "return tex.Sample(samp," + uv + ");}")
        self.assertEqual(len(model["bindings"]), 11)
        text = generate_lean(model, model, spec={"ranges": [], "nonzero": []})
        self.assertEqual(text.count('ops.sample "tex" "samp"'), 22)
        self.assertLess(len(text), 20000)
        model = self.compile(ENTRY + "return float4(ddx(ddy(ddx(uv))),0,1);}")
        self.assertEqual(len(model["bindings"]), 3)

    def test_unused_opaque_call_arguments_retain_normalization_domain(self):
        source = HEADER + "void Ignore(float4 color){} " + ENTRY + "Ignore(tex.Sample(samp,normalize(uv))); return float4(uv,0,1);}"
        model = self.compile(source)
        with self.assertRaises(ModelError):
            constraint_spec({"schema": 2, "ranges": {}, "nonzero_vectors": []}, model, model)
        constraint_spec({"schema": 2, "ranges": {}, "nonzero_vectors": ["uv"]}, model, model)

    def test_uncalled_recursion_is_rejected_for_void_and_numeric_helpers(self):
        for helper in ("void Bad(){Bad();}", "float Bad(float x){return Bad(x);}"):
            with self.subTest(helper=helper), self.assertRaisesRegex(ModelError, "Recursive helper definitions"):
                self.compile(helper + ENTRY + "return float4(uv,0,1);}")

    def test_normalize_inside_clip_still_requires_explicit_domain(self):
        model = self.compile(ENTRY + "clip(normalize(uv));return float4(1,0,0,1);}")
        with self.assertRaises(ModelError):
            constraint_spec({"schema": 2, "ranges": {}, "nonzero_vectors": []}, model, model)
        constraint_spec({"schema": 2, "ranges": {}, "nonzero_vectors": ["uv"]}, model, model)

    def test_effect_budget(self):
        with self.assertRaisesRegex(ModelError, "128 clipping"):
            self.compile(ENTRY + "clip(uv);"*129 + "return float4(1,0,0,1);}")

    def test_material_positive_and_concrete_negative_witnesses(self):
        inputs = [[[.1, .1], [.4, .6], [.8, .8]], [.8, .5, .2, 1], [1, 2, .1, .1], [.3], [.2], [1], [.5]]
        material = ROOT / "examples/textured"
        original = self.compile((material / "original.hlsl").read_text(encoding="utf-8-sig"))
        expected = evaluate_fragment(original, inputs, 3, test_operations)
        self.assertTrue(any(value is None for value in expected))
        self.assertTrue(any(value is not None for value in expected))
        for role in ("optimized", "wrong", "wrong-uv", "wrong-derivative", "wrong-lod", "wrong-sampler"):
            model = self.compile((material / (role + ".hlsl")).read_text(encoding="utf-8-sig"))
            actual = evaluate_fragment(model, inputs, 3, test_operations)
            if role == "optimized":
                for a, b in zip(actual, expected):
                    if a is None or b is None:
                        self.assertEqual(a, b)
                    else:
                        for x, y in zip(a, b):
                            self.assertAlmostEqual(x, y)
            else:
                self.assertNotEqual(actual, expected, role)
        spec = constraint_spec(json.loads((material / "constraints.json").read_text(encoding="utf-8-sig")), original, original)
        text = generate_lean(original, original, spec=spec)
        self.assertIn("(p1 : Vec4)", text)
        self.assertIn("(p0 : E → Vec 2)", text)


if __name__ == "__main__":
    unittest.main()

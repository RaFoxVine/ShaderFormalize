"""Actual DXC scalar control flow, independent values, masks and domain checks."""
import unittest
import subprocess

import test_structured
from shader_ast import ModelError
from shader_control_eval import evaluate_control, no_operations
from shader_eval import evaluate_model
from shader_lean import constraint_spec, generate_lean
from test_fragment import test_operations

ENTRY = "float4 main(float4 a:COLOR0):SV_Target{"
HEADER = "Texture2D<float4> tex:register(t0);SamplerState samp:register(s0);"


class ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_structured.StructuredTests.setUpClass()

    def compile(self, source):
        return test_structured.StructuredTests.compile(source)

    def values(self, body, a):
        return evaluate_model(self.compile(ENTRY + body + "}"), [a])

    def test_bool_and_nested_branches(self):
        body = "bool b=a.x>0.5; float4 c; if(b && !(a.y<0.0)){if(a.z>=0.0)c=a*2;else c=a*3;}else c=a;return c;"
        self.assertEqual(self.values(body, [1,0,1,1]), [2,0,2,2])
        self.assertEqual(self.values(body, [1,0,-1,1]), [3,0,-3,3])
        self.assertEqual(self.values(body, [.5,0,1,1]), [.5,0,1,1])

    def test_boolean_cast_without_named_bool_variable(self):
        self.assertEqual(self.values("return float4(a.x>0.5,0,0,1);", [1,0,0,0]), [1,0,0,1])
        self.assertEqual(self.values("const bool b=a.x>0.5;return float4(b,0,0,1);", [0,0,0,0]), [0,0,0,1])

    def test_scalar_ternary_vector_and_boolean_helpers(self):
        source = "bool Enabled(float x){if(x>0.5)return true;return false;}" + ENTRY + "bool flag=Enabled(a.x);return flag?a:a*2;}"
        self.assertEqual(evaluate_model(self.compile(source), [[1,2,3,4]]), [1,2,3,4])
        self.assertEqual(evaluate_model(self.compile(source), [[0,2,3,4]]), [0,4,6,8])

    def test_record_fields_copies_and_branch_assignment(self):
        source = "struct S{float4 c;bool enabled;};" + ENTRY + "S s;s.c=a;s.enabled=a.x>0.5;S t=s;if(s.enabled){t.c*=2;}else{t.c+=1;}return s.c+t.c;}"
        self.assertEqual(evaluate_model(self.compile(source), [[1,2,3,4]]), [3,6,9,12])
        self.assertEqual(evaluate_model(self.compile(source), [[0,2,3,4]]), [1,5,7,9])

    def test_returned_branch_does_not_require_continuing_initialization(self):
        body = "float4 c;if(a.x>0.5){return a;}else{c=a*2;}return c;"
        self.assertEqual(self.values(body, [1,2,3,4]), [1,2,3,4])
        self.assertEqual(self.values(body, [0,2,3,4]), [0,4,6,8])

    def test_missing_return_and_partial_initialization_rejected(self):
        for body in ("if(a.x>0.5)return a;", "float4 c;if(a.x>0.5)c=a;return c;", "return a;a*=2;"):
            with self.subTest(body=body), self.assertRaises((ModelError, subprocess.CalledProcessError)):
                self.compile(ENTRY + body + "}")

    def test_void_return_restores_caller_and_discard_remains_dead(self):
        source = "void Cut(float x){if(x>0.5)return;discard;}" + ENTRY + "Cut(a.x);if(a.y>0.5)return a;return a*2;}"
        model = self.compile(source)
        inputs = [[[1,1,0,1],[1,0,0,1],[0,1,0,1]]]
        self.assertEqual(evaluate_control(model, inputs, 3, no_operations), [[1,1,0,1],[2,0,0,2],None])

    def test_then_clip_does_not_drop_else_and_masked_opaque_context(self):
        source = HEADER + ENTRY + "bool b=a.x>0.5;float4 c;if(b){clip(a.y);c=a;}else{c=tex.Sample(samp,a.xy)+float4(ddx(a.xy),0,0);}return c;}"
        model = self.compile(source)
        inputs = [[[1,-1,0,1],[.25,-1,0,1],[1,1,0,1]]]
        result = evaluate_control(model, inputs, 3, test_operations)
        self.assertIsNone(result[0])
        self.assertIsNotNone(result[1])
        self.assertEqual(result[2], [1,1,0,1])

    def test_conditional_and_logical_short_circuit_normalization(self):
        for expression in ("a.x>0.5 ? normalize(a.yzw) : a.yzw",):
            model = self.compile(ENTRY + "return float4(" + expression + ",1);}")
            self.assertEqual(evaluate_model(model, [[0,0,0,0]]), [0,0,0,1])
            with self.assertRaises(ValueError):
                evaluate_model(model, [[1,0,0,0]])
        for operator, x in (("&&",0),("||",1)):
            source = ENTRY + f"bool b=(a.x>0.5) {operator} (dot(normalize(a.yzw),a.yzw)>0.0);return b?a:a*2;" + "}"
            model = self.compile(source)
            self.assertIsNotNone(evaluate_model(model, [[x,0,0,0]]))

    def test_domains_are_conclusion_not_undeclared_assumptions(self):
        model = self.compile(ENTRY + "return a.x>0.5 ? float4(normalize(a.yzw),1) : a;}")
        spec = constraint_spec({"schema":2,"ranges":{},"nonzero_vectors":[]}, model, model)
        text = generate_lean(model, model, spec=spec)
        self.assertIn("(original ops p0).2", text)
        self.assertIn("→ (0 : ℝ) < dot", text)
        self.assertNotIn("nonzero_vectors", text)

    def test_branch_alias_keeps_complete_field(self):
        source = ENTRY + "bool b=a.x>0.5;float4 c;if(b){float4 t=a;c=ddx(t);}else{c=a;}return c;}"
        model = self.compile(source)
        inputs = [[[0,1,0,1],[1,2,0,1],[2,4,0,1]]]
        result = evaluate_control(model, inputs, 3, test_operations)
        # The derivative must still see the first point, even though b is false there.
        self.assertEqual(result[1][1], 4)

    def test_helpers_preserve_complete_return_field_under_caller_mask(self):
        variants = [
            ("float F(float x){return x;}", "", "F(a.y)"),
            ("float G(float x){return x;}float F(float x){return G(x);}", "", "F(a.y)"),
            ("float F(float x){if(x>3.0)return x;return x;}", "", "F(a.y)"),
            ("struct S{float c;};S F(float x){S s;s.c=x;return s;}", "S s=F(a.y);", "s.c")]
        inputs = [[[0,2,0,1],[1,4,0,1],[1,8,0,1]]]
        for mode in ("ddx", "ddy"):
            direct = self.compile(ENTRY + f"if(a.x>0.5)return float4({mode}(a.y),0,0,1);return a;" + "}")
            expected = evaluate_control(direct, inputs, 3, test_operations)
            self.assertEqual(expected[1][0], 7 if mode == "ddx" else -11)
            for header, setup, value in variants:
                with self.subTest(mode=mode, header=header):
                    model = self.compile(header + ENTRY + f"if(a.x>0.5){{{setup}return float4({mode}({value}),0,0,1);}}return a;" + "}")
                    self.assertEqual(evaluate_control(model, inputs, 3, test_operations), expected)

    def test_helper_domains_use_actual_call_entry(self):
        cases = [("float3 F(float3 v){return normalize(v);}", "float4(F(a.yzw),1)"),
                 ("float F(float v){uint n=(uint)v;return (float)n;}", "float4(F(a.y-2.0),0,0,1)")]
        for header, value in cases:
            with self.subTest(header=header):
                model = self.compile(header + ENTRY + f"if(a.x>0.5)return {value};return a;" + "}")
                self.assertEqual(evaluate_model(model, [[0,0,0,0]]), [0,0,0,0])
                with self.assertRaises(ValueError):
                    evaluate_model(model, [[1,0,0,0]])

    def test_void_helper_discard_only_affects_calling_positions(self):
        header = "void Cut(float y){if(y>0.5)return;discard;}"
        model = self.compile(header + ENTRY + "if(a.x>0.5){Cut(a.y);}return a;}")
        inputs = [[[0,0,0,1],[1,0,0,1],[1,1,0,1]]]
        self.assertEqual(evaluate_control(model, inputs, 3, test_operations), [inputs[0][0],None,inputs[0][2]])

    def test_scopes_and_shadowing_do_not_leak(self):
        body = "float4 c=a;if(a.x>0.5){float4 a=c*3;c=a;}else{float4 a=c*2;c=a;}return c;"
        self.assertEqual(self.values(body, [1,2,3,4]), [3,6,9,12])
        with self.assertRaises((ModelError, subprocess.CalledProcessError)):
            self.compile(ENTRY + "if(a.x>0.5){float x=1;}return float4(x,0,0,1);}")

    def test_unsupported_body_still_checked_when_uncalled(self):
        for helper in ("void F(){while(true){return;}}", "float4 F(float4 x){if(x.x>0)return x/2;return x;}",
                       "float F(){float x;return x;}"):
            for body in ("return a;}", "bool b=true;return a;}"):
                with self.assertRaises(ModelError):
                    self.compile(helper + ENTRY + body)

    def test_branch_depth_budget(self):
        with self.assertRaisesRegex(ModelError, "nesting exceeds 32"):
            self.compile(ENTRY + "if(a.x>0){"*33 + "return a;" + "}"*33 + "return a;}")

    def test_empty_helper_expansion_is_bounded_on_both_paths(self):
        helpers = "void F0(){}"
        for index in range(1, 13):
            helpers += f"void F{index}(){{F{index-1}();F{index-1}();}}"
        for body in ("F12();return a;", "bool b=true;F12();return a;"):
            with self.assertRaisesRegex(ModelError, "excessive helper expansion"):
                self.compile(helpers + ENTRY + body + "}")

    def test_mixed_schema_domain_uses_old_effect_prefix(self):
        old = self.compile(ENTRY + "if(a.x<=0.0)discard;return float4(normalize(a.yzw),1);}")
        new = self.compile(ENTRY + "bool b=a.x<=0.0;if(b)discard;return float4(normalize(a.yzw),1);}")
        self.assertEqual((old["schema"], new["schema"]), (3, 4))
        spec = constraint_spec({"schema":2,"ranges":{},"nonzero_vectors":[]}, old, new)
        text = generate_lean(old, new, spec=spec)
        self.assertNotIn("(∀ x, ((fun _ => True) x) →", text)


if __name__ == "__main__":
    unittest.main()

"""Real DXC argument defaults, independent output copies and expression effects."""
import unittest

import test_structured
from test_control import ENTRY, HEADER
from test_fragment import test_operations
from shader_ast import ModelError
from shader_eval import evaluate_model
from shader_lean import generate_lean
from shader_shared_eval import evaluate_shared


class CopybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_structured.StructuredTests.setUpClass()

    def compile(self, source):
        return test_structured.StructuredTests.compile(source, "shared")

    def values(self, source, inputs=None):
        model = self.compile(source)
        generate_lean(model, model, spec={"ranges":[],"nonzero":[]})
        return evaluate_model(model, inputs or [[1,2,3,4]])

    def test_default_constant_and_explicit_override(self):
        source = "float F(float x,float k=2.0){return x*k;}" + ENTRY + "float k=99.0;return float4(F(a.x)+F(a.y,3.0),0,0,1);}"
        self.assertEqual(self.values(source), [8,0,0,1])

    def test_default_global_uses_declaration_scope_and_pure_call(self):
        source = "cbuffer B:register(b0){float gain;}float K(){return gain+1.0;}float F(float x,float k=K()){return x*k;}" + ENTRY + "float gain=99.0;return float4(F(a.x)+F(a.y),0,0,1);}"
        self.assertEqual(self.values(source, [[1,2,3,4],[2]]), [9,0,0,1])

    def test_record_out_inout_and_void_fallthrough(self):
        source = '''struct S{float4 c;uint tag;bool enabled;};
void Build(float4 a,out S s,inout float gain,float k=2.0){s.c=a*gain;s.tag=257u&255u;s.enabled=true;gain+=k;}
''' + ENTRY + "S s;float gain=1.0;Build(a,s,gain);return s.enabled?s.c+gain+(float)s.tag:a;}"
        self.assertEqual(self.values(source), [5,6,7,8])

    def test_early_return_writes_and_inout_untouched(self):
        source = "void F(bool b,out float x){if(b){x=2.0;return;}x=3.0;}void Keep(inout float x){}" + ENTRY + "float x;F(a.x>0.5,x);Keep(x);return float4(x,0,0,1);}"
        self.assertEqual(self.values(source), [2,0,0,1])
        self.assertEqual(self.values(source, [[0,2,3,4]]), [3,0,0,1])

    def test_numeric_helper_calls_pure_void_builder(self):
        source = "struct S{float4 c;};void Set(float4 a,out S s){s.c=a*2.0;}S Read(float4 a){S s;Set(a,s);return s;}" + ENTRY + "S s=Read(a);return s.c+a;}"
        self.assertEqual(self.values(source), [3,6,9,12])

    def test_nested_record_copies_and_independent_field_outputs(self):
        source = '''struct T{float4 c;};struct S{T first;T second;};
void Change(inout T t){t.c*=2.0;}void Set(out float x,out float y){x=2.0;y=3.0;}
''' + ENTRY + "S s;s.first.c=a;s.second.c=a;S t=s;Change(t.first);return s.first.c+t.first.c;}"
        self.assertEqual(self.values(source), [3,6,9,12])
        source = "struct S{float x;float y;};void Set(out float x,out float y){x=2.0;y=3.0;}" + ENTRY + "S s;Set(s.x,s.y);return float4(s.x,s.y,0,1);}"
        self.assertEqual(self.values(source), [2,3,0,1])

    def test_conditional_expression_merges_caller_variables(self):
        source = "float Set(out float x,float v){x=v;return v;}" + ENTRY + "float x=5.0;float y=a.x>0.5?Set(x,2.0):Set(x,3.0);return float4(x,y,0,1);}"
        self.assertEqual(self.values(source), [2,2,0,1])
        self.assertEqual(self.values(source, [[0,2,3,4]]), [3,3,0,1])

    def test_short_circuit_updates_only_selected_rhs(self):
        for operator in ("&&", "||"):
            source = "bool Set(out float x){x=7.0;return true;}" + ENTRY + f"float x=2.0;bool b=(a.x>0.5){operator}Set(x);return float4(x,b,0,1);" + "}"
            expected_yes = [7,1,0,1] if operator == "&&" else [2,1,0,1]
            expected_no = [2,0,0,1] if operator == "&&" else [7,1,0,1]
            self.assertEqual(self.values(source), expected_yes)
            self.assertEqual(self.values(source, [[0,2,3,4]]), expected_no)

    def test_out_field_derivative_keeps_complete_positions(self):
        source = "void Identity(float x,out float y){y=x;}" + ENTRY + "float v=a.y;if(a.x>0.5)Identity(a.y,v);return float4(ddx(v),0,0,1);}"
        direct = ENTRY + "return float4(ddx(a.y),0,0,1);}"
        inputs = [[[0,2,0,1],[1,4,0,1],[1,8,0,1]]]
        actual = evaluate_shared(self.compile(source), inputs, 3, test_operations)
        expected = evaluate_shared(self.compile(direct), inputs, 3, test_operations)
        self.assertEqual(actual, expected)

    def test_default_domain_only_when_argument_used_and_call_executed(self):
        prefix = "void Set(out float x,float3 v=normalize(float3(0.0,0.0,0.0))){x=1.0;}"
        source = prefix + ENTRY + "float x=0.0;if(a.x>0.5)Set(x);return float4(x,0,0,1);}"
        self.assertEqual(self.values(source, [[0,0,0,0]]), [0,0,0,1])
        with self.assertRaises(ValueError):
            self.values(source, [[1,0,0,0]])
        source = prefix + ENTRY + "float x;Set(x,a.xyz);return float4(x,0,0,1);}"
        self.assertEqual(self.values(source, [[0,0,0,0]]), [1,0,0,1])

    def test_old_value_is_not_read_by_out_but_is_copied_to_input(self):
        source = "void F(out float x,float y){x=y+1.0;}" + ENTRY + "float x=2.0;F(x,x);return float4(x,0,0,1);}"
        self.assertEqual(self.values(source), [3,0,0,1])

    def test_missing_writes_and_read_before_out_assignment_rejected(self):
        for helper in ("void F(out float x){x=x+1.0;}",
                       "void F(out float x){}",
                       "void F(out float x){if(true)return;x=1.0;}",
                       "void F(out float x){if(true)x=1.0;}"):
            with self.subTest(helper=helper), self.assertRaises(ModelError):
                self.compile(helper + ENTRY + "return a;}")

    def test_alias_and_nested_argument_order_conflicts_rejected(self):
        sources = [
            "void F(out float x,out float y){x=1.0;y=2.0;}" + ENTRY + "float x;F(x,x);return a;}",
            "void F(inout float x,float y){x+=y;}float G(out float x){x=3.0;return 4.0;}" + ENTRY + "float x=2.0;F(x,G(x));return a;}",
        ]
        for source in sources:
            with self.subTest(source=source), self.assertRaises(ModelError):
                self.compile(source)

    def test_sibling_call_binary_constructor_sample_and_compound_conflicts(self):
        prefix = HEADER + "float F(out float x){x=1.0;return 2.0;}float G(float x,float y){return x+y;}"
        statements = ("float y=F(x)+x;", "float4 y=float4(F(x),x,0,1);",
                      "float y=G(F(x),x);", "float4 y=tex.SampleLevel(samp,float2(F(x),0.0),x);", "x+=F(x);")
        for statement in statements:
            with self.subTest(statement=statement), self.assertRaises(ModelError):
                self.compile(prefix + ENTRY + "float x=0.0;" + statement + "return a;}")

    def test_independent_sibling_writes_are_accepted(self):
        source = "struct S{float x;float y;};float F(out float x){x=3.0;return 2.0;}" + ENTRY + "S s;float z=F(s.x)+F(s.y);return float4(z,s.x,s.y,1);}"
        self.assertEqual(self.values(source), [4,3,3,1])

    def test_out_clip_works_but_transitive_discard_and_numeric_clip_rejected(self):
        source = "void F(float v,out float x){clip(v);x=v*2.0;}" + ENTRY + "float x;F(a.x,x);return float4(x,0,0,1);}"
        self.assertEqual(self.values(source), [2,0,0,1])
        self.assertIsNone(self.values(source, [[-1,2,3,4]]))
        for prefix in ("void D(){discard;}void F(out float x){D();x=1.0;}",
                       "void D(){clip(-1.0);}void V(){D();}float F(){V();return 1.0;}"):
            with self.subTest(prefix=prefix), self.assertRaises(ModelError):
                self.compile(prefix + ENTRY + "return a;}")

    def test_bool_uint_outputs_and_carrier_swizzle_boundaries(self):
        source = "void Set(out bool b,inout uint x){b=true;x=x+1u;}" + ENTRY + "bool b;uint x=2u;Set(b,x);return float4(b,(float)x,0,1);}"
        self.assertEqual(self.values(source), [1,3,0,1])
        for prefix, body in (("void Set(out float x){x=1.0;}","float4 x=a;Set(x.y);return x;"),
                             ("void Set(out float x){x=asfloat(1u);}","float x;Set(x);return a;")):
            with self.subTest(body=body), self.assertRaises(ModelError):
                self.compile(prefix + ENTRY + body + "}")

    def test_auto_still_rejects_new_parameter_syntax(self):
        for source in ("void F(out float x){x=1.0;}" + ENTRY + "float x;F(x);return a;}",
                       "float F(float x=1.0){return x;}" + ENTRY + "return a;}"):
            with self.assertRaises(ModelError):
                test_structured.StructuredTests.compile(source)

    def test_unused_defaults_do_not_share_an_imaginary_caller_budget(self):
        parameters = ",".join(f"float p{i}=K()" for i in range(64))
        source = "float K(){return 1.0;}" + "".join(f"float F{i}({parameters}){{return 1.0;}}" for i in range(65))
        model = self.compile(source + ENTRY + "return a;}")
        self.assertEqual(len(model["helpers"]), 66)
        self.assertEqual(model["calls"], [])


if __name__ == "__main__":
    unittest.main()

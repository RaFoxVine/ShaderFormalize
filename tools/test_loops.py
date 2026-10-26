"""DXC-only isolated loop regressions; no CLI, Lean build or shared writes."""
import copy
import json
import subprocess
import unittest

import test_structured
from test_control import ENTRY
from test_fragment import test_operations
from shader_ast import ModelError
from shader_eval import evaluate_model
from shader_lean import generate_lean
from shader_shared_eval import evaluate_shared
from shaderformalize import ROOT


class LoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_structured.StructuredTests.setUpClass()

    def compile(self, body, prefix=""):
        return test_structured.StructuredTests.compile(prefix + ENTRY + body + "}", "shared")

    def values(self, body, prefix="", inputs=None):
        model = self.compile(body, prefix)
        generate_lean(model, model, spec={"ranges": [], "nonzero": []})
        return evaluate_model(model, inputs or [[1, 2, 3, 4]])

    def test_zero_one_and_multiple_iterations(self):
        for count in (0, 1, 3):
            body = f"float3 sum=0;for(uint i=0u;i<{count}u;++i){{sum+=a.xyz;}}return float4(sum,1);"
            with self.subTest(count=count):
                self.assertEqual(self.values(body), [count, count * 2, count * 3, 1])

    def test_nonzero_start_and_start_after_end(self):
        body = "float sum=0;for(uint i=2u;i<5u;++i){sum+=(float)i;}return float4(sum,0,0,1);"
        self.assertEqual(self.values(body), [9, 0, 0, 1])
        body = "float sum=0;for(uint i=6u;i<4u;++i){sum+=1;}return float4(sum,0,0,1);"
        self.assertEqual(self.values(body), [0, 0, 0, 1])

    def test_uint_maximum_is_not_wrapped_by_increment(self):
        body = "float sum=0;for(uint i=4294967294u;i<4294967295u;++i){sum+=(float)(i&3u);}return float4(sum,0,0,1);"
        self.assertEqual(self.values(body), [2, 0, 0, 1])

    def test_constant_expressions_use_uint32_wrap(self):
        body = "float sum=0;for(uint i=0u;i<(1u+2u);i++){sum+=1;}return float4(sum,0,0,1);"
        self.assertEqual(self.values(body), [3, 0, 0, 1])
        model = self.compile("for(uint i=0u;i<(4294967295u+1u);++i){}return a;")
        self.assertEqual(model["loops"][0]["regions"][0]["end"], 0)
        self.assertEqual(evaluate_model(model, [[1, 2, 3, 4]]), [1, 2, 3, 4])
        with self.assertRaises(ModelError):
            self.compile("for(uint i=0u;i<(1u<<32u);++i){}return a;")

    def test_unroll_hint_does_not_override_exact_count(self):
        body = "float sum=0;[unroll(2)]for(uint i=0;i<3;i++){sum+=1;}return float4(sum,0,0,1);"
        self.assertEqual(self.values(body), [3, 0, 0, 1])

    def test_nested_counts_include_outer_and_inner_bodies(self):
        body = "float sum=0;for(uint i=0u;i<2u;++i){for(uint j=0u;j<3u;++j){sum+=1;}}return float4(sum,0,0,1);"
        model = self.compile(body)
        self.assertEqual(evaluate_model(model, [[1, 2, 3, 4]]), [6, 0, 0, 1])
        self.assertEqual(sum(r["count"] for r in model["loops"][0]["regions"]), 8)

    def test_empty_nested_body_still_consumes_expansion_budget(self):
        accepted = self.compile("for(uint i=0u;i<63u;++i){for(uint j=0u;j<63u;++j){}}return a;")
        self.assertEqual(sum(r["count"] for r in accepted["loops"][0]["regions"]), 4032)
        generate_lean(accepted, accepted, spec={"ranges": [], "nonzero": []})
        for body in ("for(uint i=0u;i<64u;++i){for(uint j=0u;j<64u;++j){}}return a;",
                     "for(uint i=0u;i<65u;++i){}return a;"):
            with self.subTest(body=body), self.assertRaises(ModelError):
                self.compile(body)

    def test_each_iteration_has_fresh_body_locals(self):
        body = "float x=10;float sum=0;for(uint i=0u;i<3u;++i){float x=2;sum+=x;}return float4(x,sum,0,1);"
        self.assertEqual(self.values(body), [10, 6, 0, 1])

    def test_each_known_iteration_initializes_its_exact_array_element(self):
        body = "float v[3];for(uint i=0u;i<3u;++i){v[i]=(float)i+1;}return float4(v[0],v[1],v[2],1);"
        self.assertEqual(self.values(body), [1, 2, 3, 1])
        with self.assertRaises(ModelError):
            self.compile(body.replace("i<3u", "i<2u"))

    def test_output_array_and_default_parameter_inside_shared_helper(self):
        prefix = "void Fill(out float v[3],float gain=2.0){for(uint i=0u;i<3u;++i){v[i]=((float)i+1)*gain;}}"
        self.assertEqual(self.values("float v[3];Fill(v);return float4(v[0],v[1],v[2],1);", prefix), [2, 4, 6, 1])

    def test_branch_state_is_carried_between_iterations(self):
        body = "float sum=0;for(uint i=0u;i<3u;++i){if(a.x>0.5)sum+=(float)i;else sum-=1;}return float4(sum,0,0,1);"
        self.assertEqual(self.values(body), [3, 0, 0, 1])
        self.assertEqual(self.values(body, inputs=[[0, 2, 3, 4]]), [-3, 0, 0, 1])

    def test_zero_loop_has_no_body_domain_obligation(self):
        body = "float3 v=a.xyz;for(uint i=0u;i<0u;++i){v=normalize(float3(0,0,0));}return float4(v,a.w);"
        self.assertEqual(self.values(body), [1, 2, 3, 4])
        with self.assertRaises(ValueError):
            self.values(body.replace("i<0u", "i<1u"))
        with self.assertRaises(ModelError):
            self.compile("for(uint i=0u;i<0u;++i){float x=sin(a.x);}return a;")

    def test_loop_derivative_inputs_match_two_explicit_calls(self):
        loop = "float sum=0;for(uint i=0u;i<2u;++i){sum+=ddx(a.y+(float)i);}return float4(sum,0,0,1);"
        direct = "float sum=ddx(a.y)+ddx(a.y+1.0);return float4(sum,0,0,1);"
        inputs = [[[0, 2, 0, 1], [1, 4, 0, 1], [1, 8, 0, 1]]]
        self.assertEqual(evaluate_shared(self.compile(loop), inputs, 3, test_operations),
                         evaluate_shared(self.compile(direct), inputs, 3, test_operations))

    def test_branch_called_loop_helper_preserves_complete_derivative_field(self):
        prefix = "void Copy(float x,out float y){float sum=0;for(uint i=0u;i<1u;++i){sum+=x;}y=sum;}"
        source = "float v=a.y;if(a.x>0.5)Copy(a.y,v);return float4(ddx(v),0,0,1);"
        direct = "return float4(ddx(a.y),0,0,1);"
        inputs = [[[0, 2, 0, 1], [1, 4, 0, 1], [1, 8, 0, 1]]]
        self.assertEqual(evaluate_shared(self.compile(source, prefix), inputs, 3, test_operations),
                         evaluate_shared(self.compile(direct), inputs, 3, test_operations))

    def test_clip_and_domain_follow_actual_iteration_state(self):
        body = "float sum=1;for(uint i=0u;i<2u;++i){clip(a.x-(float)i);sum+=1;}return float4(sum,0,0,1);"
        self.assertEqual(self.values(body, inputs=[[2, 0, 0, 0]]), [3, 0, 0, 1])
        self.assertIsNone(self.values(body, inputs=[[.5, 0, 0, 0]]))
        body = "for(uint i=0u;i<2u;++i){if(i==1u){clip(-1.0);float3 v=normalize(float3(0,0,0));}}return a;"
        self.assertIsNone(self.values(body))

    def test_counter_writes_direct_nested_or_through_output_are_rejected(self):
        prefix = "void Change(inout uint x){x=x+1u;}"
        bodies = ["for(uint i=0u;i<2u;++i){i=i+1u;}return a;",
                  "for(uint i=0u;i<2u;++i){Change(i);}return a;",
                  "for(uint i=0u;i<2u;++i){for(uint j=0u;j<2u;++j){i=i+1u;}}return a;"]
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(ModelError):
                self.compile(body, prefix)

    def test_symbolic_bounds_and_noncanonical_control_are_rejected(self):
        prefix = "cbuffer B:register(b0){float count;}"
        bodies = ["for(uint i=0u;i<(uint)count;++i){}return a;",
                  "for(uint i=0u;i<=2u;++i){}return a;",
                  "for(uint i=0u;i<2u;i+=1u){}return a;",
                  "for(float i=0;i<2;++i){}return a;",
                  "for(uint i=0u;i<2u;--i){}return a;",
                  "uint i=0u;while(i<2u){i=i+1u;}return a;"]
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(ModelError):
                self.compile(body, prefix)

    def test_early_termination_in_body_or_callee_is_rejected(self):
        prefix = "void Kill(){discard;}"
        for statement in ("return a;", "discard;", "break;", "continue;", "Kill();"):
            body = "for(uint i=0u;i<2u;++i){" + statement + "}return a;"
            with self.subTest(statement=statement), self.assertRaises(ModelError):
                self.compile(body, prefix)

    def test_loop_scope_and_default_frontend_remain_explicit(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.compile("for(uint i=0u;i<2u;++i){}return float4((float)i,0,0,1);")
        with self.assertRaises(ModelError):
            test_structured.StructuredTests.compile(ENTRY + "for(uint i=0u;i<2u;++i){}return a;}")

    def test_loop_metadata_is_bound_to_generated_target(self):
        zero = self.compile("for(uint i=0u;i<0u;++i){}return a;")
        two = self.compile("for(uint i=0u;i<2u;++i){}return a;")
        spec = {"ranges": [], "nonzero": []}
        zero_text = generate_lean(zero, zero, spec=spec)
        two_text = generate_lean(two, two, spec=spec)
        self.assertTrue(zero_text.startswith("-- Loop and logical layouts SHA256:"))
        self.assertNotEqual(zero_text.splitlines()[0], two_text.splitlines()[0])
        self.assertEqual(zero_text.splitlines()[1:], two_text.splitlines()[1:])

    def test_malformed_loop_metadata_is_rejected_by_both_consumers(self):
        model = self.compile("for(uint i=0u;i<2u;++i){}return a;")
        variants = []
        for name, value in (("count", True), ("count", 1), ("start", -1),
                            ("end", 2**32), ("line", 0)):
            changed = copy.deepcopy(model)
            changed["loops"][0]["regions"][0][name] = value
            variants.append(changed)
        for key, value in (("loop_semantics", "fuel-v1"), ("loops", [])):
            changed = copy.deepcopy(model)
            changed[key] = value
            variants.append(changed)
        changed = copy.deepcopy(model)
        changed["loops"][0]["frame"] = True
        variants.append(changed)
        changed = copy.deepcopy(model)
        changed["loops"] *= 2
        variants.append(changed)
        changed = copy.deepcopy(model)
        region = changed["loops"][0]["regions"][0]
        region.update(start=0, end=64, count=64)
        changed["loops"][0]["regions"] = [dict(region) for _ in range(65)]
        variants.append(changed)
        for changed in variants:
            with self.subTest(metadata=changed["loops"][:1]):
                with self.assertRaises(ModelError):
                    generate_lean(changed, model, spec={"ranges": [], "nonzero": []})
                with self.assertRaises(ModelError):
                    evaluate_model(changed, [[1, 2, 3, 4]])

    def test_normal_helper_return_and_uncalled_loop_still_compile(self):
        prefix = "void Copy(float x,out float y){if(x>0){y=x;return;}y=0;} float Unused(){float v=0;for(uint i=0u;i<2u;++i){v+=1;}return v;}"
        body = "float sum=0;for(uint i=0u;i<2u;++i){float v;Copy(a.x,v);sum+=v;}return float4(sum,0,0,1);"
        model = self.compile(body, prefix)
        self.assertEqual(evaluate_model(model, [[2, 0, 0, 1]]), [4, 0, 0, 1])
        self.assertEqual(len(model["loops"]), 2)

    def test_complete_material_matches_independent_formula_and_wrong_variant_differs(self):
        folder = ROOT / "examples/complete"
        models = {role: test_structured.StructuredTests.compile(
            (folder / (role + ".hlsl")).read_text(), "shared")
            for role in ("original", "optimized", "wrong")}
        from shader_lean import constraint_spec
        constraints = json.loads((folder / "constraints.json").read_text())
        spec = constraint_spec(constraints, models["original"], models["optimized"])
        generate_lean(models["original"], models["optimized"], spec=spec)
        inputs = [
            [[.2, .3], [.5, .4], [.8, .7]],
            [[0, 0, 2]] * 3, [[0, 0, -3]] * 3,
            [1, 0], [0, 1], [.1, .2, .3], [.2, .1, .4],
            [.8, .6, .4, .5], [.25], [.4],
        ]
        # test_operations: sample=(u,v,.4,u); ddx=(last-first)+one active context.
        # Both loop iterations have gradient=(1.6,1.4), weights .25+.5.
        # Opposite normal/view gives edge=1, light sum=(.3,.3,.7), rim=.25.
        # Resulting lighting=(1.75,1.6,.95); first location clipped at u=.2<.4.
        expected = [None, [.7, .384, .152, .25], [1.12, .672, .152, .4]]
        for role in ("original", "optimized"):
            actual = evaluate_shared(models[role], inputs, 3, test_operations)
            self.assertIsNone(actual[0])
            for value, wanted in zip(actual[1:], expected[1:]):
                for component, reference in zip(value, wanted):
                    self.assertAlmostEqual(component, reference)
        wrong = evaluate_shared(models["wrong"], inputs, 3, test_operations)
        self.assertGreater(abs(wrong[1][0] - expected[1][0]), .1)

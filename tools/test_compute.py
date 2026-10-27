"""Real DXC Compute imports and independent finite memory/safety controls."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import unittest

from shader_ast import ModelError
from shader_compute import compute_contract, evaluate_compute, generate_compute, import_compute
from shaderformalize import ROOT, local_environment, validate_dxc
from shader_compute_math import evaluate_expression as evaluate_texture_expression, signed


class ComputeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dxc = validate_dxc()
        cls.directory = ROOT / "artifacts/compute/unit"
        cls.directory.mkdir(parents=True, exist_ok=True)
        cls.original = (ROOT / "examples/compute/original.hlsl").read_text()
        cls.optimized = (ROOT / "examples/compute/optimized.hlsl").read_text()
        cls.contract = json.loads((ROOT / "examples/compute/constraints.json").read_text())

    def compile(self, source):
        path = self.directory / "input.hlsl"
        path.write_bytes(source.encode("utf-8"))
        result = subprocess.run([str(self.dxc), "-T", "cs_6_0", "-E", "main", "-HV", "2021", "-ast-dump", str(path)],
                                env=local_environment(), capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return import_compute(source, result.stdout)

    def memory(self):
        memory = {}
        for resource in range(4):
            for index in range(20):
                memory[resource, index] = tuple(Fraction(resource * 100 + index * 4 + c) for c in range(4))
        return memory

    def test_two_inputs_two_outputs_and_untouched_memory(self):
        original = self.compile(self.original)
        optimized = self.compile(self.optimized)
        initial = self.memory()
        for count in (0, 1, 7, 16):
            left = evaluate_compute(original, self.contract, initial, count)
            self.assertEqual(left, evaluate_compute(optimized, self.contract, initial, count))
            for index in range(20):
                expected_sum = tuple((a + b) / 2 for a, b in zip(initial[0, index], initial[1, index]))
                expected_difference = tuple(a - b for a, b in zip(initial[0, index], initial[1, index]))
                self.assertEqual(left[2, index], expected_sum if index < count else initial[2, index])
                self.assertEqual(left[3, index], expected_difference if index < count else initial[3, index])
                self.assertEqual(left[0, index], initial[0, index])

    def test_store_load_alias_forwarding_and_last_store(self):
        body = """uint index=threadId.x;if(index>=Count)return;
float4 a=SourceA[index];float4 b=SourceB[index];
Sum[index]=a+b;Sum[index]=SourceA[index]*2.0;
Difference[index]=SourceA[index]-b;"""
        source = self.original[:self.original.index("    uint index")] + body + "\n}\n"
        model = self.compile(source)
        contract = copy.deepcopy(self.contract)
        contract["bindings"]["Sum"]["identity"] = 0
        compute_contract(contract, model, model)
        initial = self.memory()
        final = evaluate_compute(model, contract, initial, 16)
        for index in range(16):
            expected = tuple((a + b) * 2 for a, b in zip(initial[0, index], initial[1, index]))
            self.assertEqual(final[0, index], expected)
            self.assertEqual(final[3, index], tuple(value - b for value, b in zip(expected, initial[1, index])))

    def test_changed_math_has_a_concrete_counterexample(self):
        left = self.compile(self.original)
        right = self.compile(self.optimized.replace("a * 0.5 + b * 0.5", "a * 0.5 - b * 0.5"))
        initial = self.memory()
        self.assertNotEqual(evaluate_compute(left, self.contract, initial, 16), evaluate_compute(right, self.contract, initial, 16))

    def test_out_of_bounds_write(self):
        model = self.compile(self.original.replace("Sum[index]", "Sum[index+1u]"))
        with self.assertRaisesRegex(ValueError, "Out of bounds"):
            evaluate_compute(model, self.contract, self.memory(), 16)

    def test_constant_address_write_write_conflict(self):
        model = self.compile(self.original.replace("Sum[index]", "Sum[0u]"))
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            evaluate_compute(model, self.contract, self.memory(), 16)

    def test_hidden_alias_cross_thread_write_read_conflict(self):
        model = self.compile(self.original.replace("Sum[index]", "Sum[index ^ 1u]"))
        contract = copy.deepcopy(self.contract)
        contract["bindings"]["Sum"]["identity"] = 0
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            evaluate_compute(model, contract, self.memory(), 16)

    def test_aliased_outputs_observe_their_last_store(self):
        left = self.compile(self.original)
        right = self.compile(self.optimized)
        contract = copy.deepcopy(self.contract)
        contract["bindings"]["Difference"]["identity"] = 2
        initial = self.memory()
        # Both programs are race-free, but swapping writes is no longer valid
        # when their two output names denote the same physical resource.
        original_result = evaluate_compute(left, contract, initial, 16)
        optimized_result = evaluate_compute(right, contract, initial, 16)
        self.assertNotEqual(original_result[2, 0], optimized_result[2, 0])

    def test_dead_branch_access_does_not_require_bounds(self):
        source = self.original.replace("Sum[index] =", "if(false) Sum[index+100u] =")
        model = self.compile(source)
        final = evaluate_compute(model, self.contract, self.memory(), 16)
        self.assertEqual(final[2, 0], self.memory()[2, 0])

    def test_alias_capacity_mismatch_rejected(self):
        model = self.compile(self.original)
        contract = copy.deepcopy(self.contract)
        contract["bindings"]["Sum"] = {"identity": 0, "capacity": 8}
        with self.assertRaisesRegex(ModelError, "same physical capacity"):
            compute_contract(contract, model, model)

    def test_missing_binding_rejected(self):
        model = self.compile(self.original)
        contract = copy.deepcopy(self.contract)
        del contract["bindings"]["SourceA"]
        with self.assertRaisesRegex(ModelError, "every resource"):
            compute_contract(contract, model, model)

    def test_interface_mismatch_rejected(self):
        original = self.compile(self.original)
        optimized = self.compile(self.optimized.replace("register(u1)", "register(u2)"))
        with self.assertRaisesRegex(ModelError, "interfaces differ"):
            compute_contract(self.contract, original, optimized)

    def test_general_helpers_rejected_explicitly(self):
        source = "float4 Helper(float4 a){return a;}\n" + self.original
        with self.assertRaisesRegex(ModelError, "main"):
            self.compile(source)

    def test_loops_rejected_explicitly(self):
        source = self.original.replace("    uint index", "    for(uint j=0u;j<2u;++j){}\n    uint index")
        with self.assertRaisesRegex(ModelError, "ForStmt"):
            self.compile(source)

    def test_generated_goal_includes_safety_and_memory(self):
        model = self.compile(self.original)
        text = generate_compute(model, model, self.contract)
        self.assertIn("safe threads (original initial count)", text)
        self.assertIn("safe threads (optimized initial count)", text)
        self.assertIn("finish threads initial", text)
        self.assertIn("store m0", text)

    def test_sequential_conditions_keep_bounded_shared_state(self):
        conditions = "if(Count>0u){index=index+0u;}" * 20
        source = self.original.replace("    float4 a", conditions + "\n    float4 a")
        model = self.compile(source)
        self.assertLess(len(json.dumps(model)), 200000)
        self.assertEqual(evaluate_compute(model, self.contract, self.memory(), 7),
                         evaluate_compute(self.compile(self.original), self.contract, self.memory(), 7))


class TextureComputeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dxc = validate_dxc()
        cls.directory = ROOT / "artifacts/compute-texture/unit"
        cls.directory.mkdir(parents=True, exist_ok=True)
        cls.original = (ROOT / "examples/compute-texture/original.hlsl").read_text()
        cls.optimized = (ROOT / "examples/compute-texture/optimized.hlsl").read_text()
        cls.contract = json.loads((ROOT / "examples/compute-texture/constraints.json").read_text())

    def compile(self, source):
        path = self.directory / "input.hlsl"
        path.write_text(source, encoding="utf-8")
        result = subprocess.run([str(self.dxc), "-T", "cs_6_0", "-E", "main", "-HV", "2021", "-ast-dump", str(path)],
                                env=local_environment(), capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return import_compute(source, result.stdout, 2)

    def source(self, body, helper=""):
        prefix = self.original[:self.original.index("float3 ToneMap")]
        return prefix + helper + "\n[numthreads(8,8,1)] void main(uint3 threadId : SV_DispatchThreadID) {\n" + body + "\n}\n"

    def memory(self):
        return {(r, i): tuple(Fraction(r * 7 + i - c - 100) for c in range(4)) for r in range(4) for i in range(230)}

    def uniforms(self, width=17, height=13):
        return {"Width": width, "Height": height, "Exposure": Fraction(2), "BloomStrength": Fraction(1, 2)}

    def test_texture_tonemap_and_untouched_pixels(self):
        original, optimized = self.compile(self.original), self.compile(self.optimized)
        compute_contract(self.contract, original, optimized)
        memory = self.memory()
        for width, height in [(0, 0), (1, 1), (16, 12), (17, 13)]:
            uniforms = self.uniforms(width, height)
            left = evaluate_compute(original, self.contract, memory, uniforms)
            self.assertEqual(left, evaluate_compute(optimized, self.contract, memory, uniforms))
            for (r, i), value in memory.items():
                if r < 2 or i >= 221 or i % 17 >= width or i // 17 >= height:
                    self.assertEqual(left[r, i], value)

    def test_signed_wrap_and_exact_bit_cast(self):
        self.assertEqual(signed(0xffffffff), -1)
        self.assertEqual(signed(0x80000000), -(2**31))
        source = self.source("int a=(int)0xffffffffu; int b=(int)0x80000000u; uint c=(uint)a; bool negative=-1<0;")
        model = self.compile(source)
        values = {}
        for event in model["events"]:
            if event["kind"] == "binding":
                index = event["index"]
                values[index] = evaluate_texture_expression(model["bindings"][index]["expression"], values, {}, self.uniforms(), 0, 24)
        self.assertIn(0xffffffff, values.values())
        self.assertIn(0x80000000, values.values())
        self.assertIn(True, values.values())

    def test_out_of_bounds_load_zero_and_no_false_conflict(self):
        source = self.source("uint2 p=threadId.xy;if(p.x>=Width||p.y>=Height)return; float4 a=Scene.Load(int3(-1,0,0));Color[p]=a;")
        model = self.compile(source)
        contract = copy.deepcopy(self.contract)
        contract["bindings"]["Color"]["identity"] = 0
        final = evaluate_compute(model, contract, self.memory(), self.uniforms())
        self.assertEqual(final[0, 0], (Fraction(0),) * 4)
        target = generate_compute(model, model, contract)
        self.assertIn("else (fun _ => 0)", target)
        self.assertIn("allValid threads", target)

    def test_store_two_dimensional_bounds_not_flat_address(self):
        source = self.source("if(threadId.x!=0u||threadId.y!=0u)return;Color[uint2(17u,0u)]=float4(1,1,1,1);")
        model = self.compile(source)
        with self.assertRaisesRegex(ValueError, "two-dimensional Store"):
            evaluate_compute(model, self.contract, self.memory(), self.uniforms())

    def test_alias_forwarding_and_last_store(self):
        source = self.source("uint2 p=threadId.xy;if(p.x>=Width||p.y>=Height)return;Color[p]=float4(1,2,3,4);Color[p]=Scene.Load(int3(p,0))*2.0;Auxiliary[p]=Scene.Load(int3(p,0));")
        model = self.compile(source)
        contract = copy.deepcopy(self.contract)
        contract["bindings"]["Color"]["identity"] = 0
        compute_contract(contract, model, model)
        final = evaluate_compute(model, contract, self.memory(), self.uniforms())
        self.assertEqual(final[0, 0], (Fraction(2), Fraction(4), Fraction(6), Fraction(8)))
        self.assertEqual(final[3, 0], final[0, 0])

    def test_alias_shape_mismatch_rejected(self):
        model = self.compile(self.original)
        contract = copy.deepcopy(self.contract)
        contract["bindings"]["Color"] = {"identity": 0, "dimensions": [13, 17]}
        with self.assertRaisesRegex(ModelError, "same physical kind and shape"):
            compute_contract(contract, model, model)

    def test_write_write_and_read_write_conflicts(self):
        body = "uint2 p=threadId.xy;if(p.x>=Width||p.y>=Height)return;Color[uint2(0u,0u)]=float4(1,1,1,1);"
        with self.assertRaisesRegex(ValueError, "Conflicting physical"):
            evaluate_compute(self.compile(self.source(body)), self.contract, self.memory(), self.uniforms())
        body = "uint2 p=threadId.xy;if(p.x>=Width||p.y>=Height)return;float4 a=Scene.Load(int3(0,0,0));Color[p]=a;"
        contract = copy.deepcopy(self.contract)
        contract["bindings"]["Color"]["identity"] = 0
        with self.assertRaisesRegex(ValueError, "Conflicting physical"):
            evaluate_compute(self.compile(self.source(body)), contract, self.memory(), self.uniforms())

    def test_unused_division_and_helper_argument_preserve_domain(self):
        helper = "float Ignore(float x){return 1.0;}\n"
        source = self.source("float x=Ignore(1.0/(Exposure-Exposure));", helper)
        model = self.compile(source)
        self.assertTrue(any(e["kind"] == "domain" for e in model["events"]))
        with self.assertRaisesRegex(ValueError, "real domain"):
            evaluate_compute(model, self.contract, self.memory(), self.uniforms())

    def test_inactive_and_short_circuit_domains(self):
        source = self.source("if(Exposure<0.0){float x=1.0/(Exposure-Exposure);} bool b=Exposure<0.0 && (1.0/(Exposure-Exposure)>0.0);float y=Exposure>=0.0?1.0:1.0/(Exposure-Exposure);")
        model = self.compile(source)
        self.assertEqual(evaluate_compute(model, self.contract, self.memory(), self.uniforms()), self.memory())

    def test_helper_if_and_nested_call(self):
        helper = "float Twice(float x){return x*2.0;} float F(float x){float y=x;if(x<0.0){y=0.0;}return Twice(y);}\n"
        source = self.source("uint2 p=threadId.xy;if(p.x>=Width||p.y>=Height)return;Color[p]=float4(F(Exposure),0,0,1);", helper)
        final = evaluate_compute(self.compile(source), self.contract, self.memory(), self.uniforms())
        self.assertEqual(final[2, 0], (Fraction(4), Fraction(0), Fraction(0), Fraction(1)))

    def test_nonzero_mip_and_new_intrinsic_rejected(self):
        source = self.source("float4 a=Scene.Load(int3(0,0,1));")
        model = self.compile(source)
        with self.assertRaisesRegex(ModelError, "mip0"):
            generate_compute(model, model, self.contract)
        with self.assertRaisesRegex(ModelError, "Unsupported Compute intrinsic"):
            self.compile(self.source("float x=sqrt(Exposure);"))

    def test_unused_impure_helper_rejected(self):
        helper = "float F(float x){return Scene.Load(int3(0,0,0)).x;}\n"
        with self.assertRaisesRegex(ModelError, "Pure Compute helpers"):
            self.compile(self.source("", helper))


if __name__ == "__main__":
    unittest.main()

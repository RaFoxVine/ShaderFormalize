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


if __name__ == "__main__":
    unittest.main()

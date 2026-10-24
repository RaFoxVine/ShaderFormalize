import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from shader_eval import evaluate_model
from shader_model import ModelError, constraint_spec, import_shader
from shaderformalize import ROOT, validate_dxc


class MaterialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dxc = validate_dxc()
        cls.source = (ROOT / "examples/unlit/original.hlsl").read_text(encoding="utf-8")
        cls.constraints = json.loads((ROOT / "examples/unlit/constraints.json").read_text())
        cls.original = cls.compile(cls.source)

    @classmethod
    def compile(cls, source):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            path = Path(directory) / "input.hlsl"
            path.write_bytes(source.encode("utf-8"))
            result = subprocess.run([str(cls.dxc), "-T", "ps_6_0", "-E", "main", "-HV", "2021", "-ast-dump", str(path)],
                                    capture_output=True, text=True, encoding="utf-8", check=True)
        return import_shader(source, result.stdout)

    def test_material_interface_and_matching_domain(self):
        self.assertEqual(len(self.original["interface"]), 8)
        self.assertEqual(self.original["buffer"], {"name": "UnityPerMaterial", "register": "b0"})
        self.assertEqual(len(constraint_spec(self.constraints, self.original, self.original)["nonzero"]), 3)

    def test_missing_normalization_premise(self):
        data = copy.deepcopy(self.constraints)
        data["nonzero_vectors"].pop()
        with self.assertRaises(ModelError):
            constraint_spec(data, self.original, self.original)

    def test_zero_only_input_conflicts_with_nonzero(self):
        data = copy.deepcopy(self.constraints)
        data["ranges"]["normalWS"] = {"min": "0", "max": "0"}
        with self.assertRaises(ModelError):
            constraint_spec(data, self.original, self.original)

    def test_unknown_domain_fields_and_names(self):
        for name in ("unknown", "_LightDirection.z", "normalWS.w", "normalWS.xyzw"):
            data = copy.deepcopy(self.constraints)
            data["nonzero_vectors"] = [name]
            with self.subTest(name=name), self.assertRaises(ModelError):
                constraint_spec(data, self.original, self.original)

    def test_dead_and_overwritten_normalization_still_needs_domain(self):
        source = "float4 main(float4 a:COLOR0, float4 b:COLOR1, float t:TEXCOORD0):SV_Target { float3 dead=normalize(a.xyz); dead=b.xyz; return a; }"
        model = self.compile(source)
        data = {"schema": 2, "ranges": {}, "nonzero_vectors": ["b.xyz"]}
        with self.assertRaises(ModelError):
            constraint_spec(data, model, model)
        data["nonzero_vectors"] = ["a.xyz"]
        self.assertEqual(len(constraint_spec(data, model, model)["nonzero"]), 1)

    def test_normalize_local_alias_is_input_domain(self):
        model = self.compile(self.source.replace("float3 n = normalize(normalWS);", "float3 alias = normalWS; float3 n = normalize(alias);"))
        constraint_spec(self.constraints, model, model)

    def test_computed_normalization_domain_is_not_guessed(self):
        model = self.compile(self.source.replace("normalize(normalWS)", "normalize(normalWS + viewWS)"))
        with self.assertRaises(ModelError):
            constraint_spec(self.constraints, model, model)

    def test_uninitialized_read_rejected(self):
        source = self.source.replace("float3 n = normalize(normalWS);", "float3 n;")
        with self.assertRaises(ModelError):
            self.compile(source)

    def test_branch_not_dropped(self):
        source = self.source.replace("color +=", "if (_Ambient > 0) color +=")
        with self.assertRaises(ModelError):
            self.compile(source)

    def test_uniform_write_rejected_by_dxc(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.compile(self.source.replace("float3 n =", "_Ambient = 0; float3 n ="))

    def test_constructor_and_swizzle_order(self):
        model = self.compile("float4 main(float4 a:COLOR0, float4 b:COLOR1, float t:TEXCOORD0):SV_Target { return float4(a.zyx, b.x); }")
        self.assertEqual(evaluate_model(model, [[1, 2, 3, 4], [5, 6, 7, 8], [0]]), [3, 2, 1, 5])

    def test_shadowed_uniform_uses_declaration_identity(self):
        source = "cbuffer M:register(b0){float4 color;}; float4 main(float4 a:COLOR0,float4 b:COLOR1,float t:TEXCOORD0):SV_Target { float4 color=a; color+=b; return color; }"
        model = self.compile(source)
        self.assertEqual(evaluate_model(model, [[1, 2, 3, 4], [5, 6, 7, 8], [0], [99]*4]), [6, 8, 10, 12])

    def test_material_cpu_value_and_rewrite(self):
        optimized = self.compile((ROOT / "examples/unlit/optimized.hlsl").read_text())
        inputs = [[0, 0, -2], [0, 0, -3], [.8, .4, .2, .7], [1, .5, .25, 1], [.2, .8, 1, 1], [0, 0, -4, 0], [.1], [2]]
        expected = [.8 * 1.1, .4 * .6, .2 * .35, .7]
        for model in (self.original, optimized):
            for actual, wanted in zip(evaluate_model(model, inputs), expected):
                self.assertAlmostEqual(actual, wanted)

    def test_cbuffer_reordering_is_interface_mismatch(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            path = Path(directory) / "changed.hlsl"
            changed = self.source.replace("float4 _LightColor;\n    float4 _RimColor;", "float4 _RimColor;\n    float4 _LightColor;")
            path.write_bytes(changed.encode("utf-8"))
            result = subprocess.run(["python", str(ROOT / "tools/shaderformalize.py"), "prepare", "--original", str(ROOT / "examples/unlit/original.hlsl"),
                                     "--optimized", str(path), "--constraints", str(ROOT / "examples/unlit/constraints.json"), "--output", directory], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads((Path(directory)/"result.json").read_text())["status"], "INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()

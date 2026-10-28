"""Host Lean editor settings must not change the pinned command-line environment."""
import os
import unittest
from unittest.mock import patch

from shaderformalize import ROOT, local_environment
from lean_environment import lean_bin, toolchain_lock
import ieeeformalize
import shaderformalize
from proof_contract import verification_module


class EnvironmentTests(unittest.TestCase):
    def test_external_lean_paths_are_cleared_only_in_child_environment(self):
        values = {name: "external-editor-path" for name in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT")}
        with patch.dict(os.environ, values):
            environment = local_environment()
            for name in values:
                self.assertNotIn(name, environment)
                self.assertEqual(os.environ[name], values[name])
            self.assertTrue(environment["PATH"].startswith(str(lean_bin())))
            self.assertEqual(environment["MATHLIB_CACHE_DIR"], str(ROOT / ".cache/mathlib"))

    def test_numeric_paths_share_toolchain_environment_and_workspace_lock(self):
        self.assertIs(ieeeformalize.workspace_lock, shaderformalize.workspace_lock)
        self.assertEqual(ieeeformalize.LEAN_BIN, lean_bin())
        self.assertEqual(ieeeformalize.LEAN_LOCK, toolchain_lock()["binaries"])
        self.assertEqual(ieeeformalize.local_environment(), shaderformalize.local_environment())
        self.assertEqual(ieeeformalize.PROOF, shaderformalize.PROOF)

    def test_shared_environment_clears_floatlib_and_all_lean_overrides(self):
        with patch.dict(os.environ, {"FLOATLIB_BUILD_DIR": "foreign", "LEAN_EXTRA": "foreign"}):
            environment = local_environment()
            self.assertNotIn("FLOATLIB_BUILD_DIR", environment)
            self.assertNotIn("LEAN_EXTRA", environment)
            self.assertEqual(os.environ["FLOATLIB_BUILD_DIR"], "foreign")

    def test_ieee_binding_uses_independent_modules_and_namespace(self):
        binding = verification_module("ShaderIeee.GeneratedModel", "ShaderIeee.SubmittedProof", "ShaderIeee")
        self.assertIn("import ShaderIeee.GeneratedModel", binding)
        self.assertIn("ShaderIeee.Generated.expected", binding)
        self.assertIn("ShaderIeee.AgentProof.equivalent", binding)
        self.assertIn("#print axioms ShaderIeee.Verification.checked", binding)
        self.assertIn("import GeneratedModel\nimport SubmittedProof", verification_module())


if __name__ == "__main__":
    unittest.main()

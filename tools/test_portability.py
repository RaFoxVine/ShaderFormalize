"""Host Lean editor settings must not change the pinned command-line environment."""
import os
import unittest
from unittest.mock import patch

from shaderformalize import ROOT, local_environment


class EnvironmentTests(unittest.TestCase):
    def test_external_lean_paths_are_cleared_only_in_child_environment(self):
        values = {name: "external-editor-path" for name in ("LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT")}
        with patch.dict(os.environ, values):
            environment = local_environment()
            for name in values:
                self.assertNotIn(name, environment)
                self.assertEqual(os.environ[name], values[name])
            self.assertTrue(environment["PATH"].startswith(str(ROOT / ".tools/lean-4.24.0-windows/bin")))
            self.assertEqual(environment["MATHLIB_CACHE_DIR"], str(ROOT / ".cache/mathlib"))


if __name__ == "__main__":
    unittest.main()

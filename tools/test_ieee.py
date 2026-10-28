"""Unit and infrastructure controls for the independent IEEE HLSL frontend."""
import ctypes
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import ieeeformalize
import run_ieee_suite
from ieeeformalize import ROOT, workspace_lock
from shader_ast import ModelError
from shader_ieee_frontend import import_ieee
from shader_ieee_lean import empty_constraints, scientific_arguments
from shaderformalize import validate_dxc


BASE = "float4 main(float4 a : COLOR0, float t : TEXCOORD0) : SV_Target { return a * t; }\n"


def process_active(pid):
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    exit_code = ctypes.c_ulong()
    found = kernel32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(exit_code))
    kernel32.CloseHandle(ctypes.c_void_p(handle))
    return bool(found and exit_code.value == 259)


class IeeeFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dxc = validate_dxc()

    def compile_model(self, source):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            path = Path(directory) / "input.hlsl"
            path.write_bytes(source.encode("utf-8"))
            result = subprocess.run([str(self.dxc), "-T", "ps_6_0", "-E", "main", "-HV", "2021", "-ast-dump", str(path)],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace")
            if result.returncode:
                raise ModelError("DXC rejected test input", "INVALID_INPUT")
            return import_ieee(source, result.stdout)

    def assert_rejected(self, source):
        with self.assertRaises(ModelError):
            self.compile_model(source)

    def test_literal_preserves_exact_decimal_scientific_form(self):
        token = "0.123456789123456789e-7"
        model = self.compile_model(BASE.replace("a * t", "a * " + token))
        expression = model["expression"]["arguments"][1]["arguments"][0]
        self.assertEqual(expression["token"], token)
        self.assertEqual(scientific_arguments(expression), ("123456789123456789", "true", 25))

    def test_uncalled_helper_is_checked_for_initialization(self):
        self.assert_rejected("float unused() { float x; return x; }\n" + BASE)

    def test_uncalled_helper_is_checked_for_intrinsic_whitelist(self):
        self.assert_rejected("float unused(float x) { return fmod(x, 2); }\n" + BASE)

    def test_nonempty_constraints_rejected(self):
        valid = {"schema": 2, "ranges": {}, "nonzero_vectors": []}
        self.assertEqual(empty_constraints(valid), valid)
        invalid = [
            {"schema": 2, "ranges": {"a": {"min": "0", "max": "1"}}, "nonzero_vectors": []},
            {"schema": 2, "ranges": {}, "nonzero_vectors": ["a"]},
            {"schema": True, "ranges": {}, "nonzero_vectors": []},
            {"schema": 2, "ranges": {}},
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ModelError):
                empty_constraints(value)

    def test_excluded_syntax_and_effects_rejected(self):
        sources = {
            "if": BASE.replace("return a * t;", "if (t > 0) { return a; } return a * t;"),
            "loop": BASE.replace("return a * t;", "while (t > 0) { t -= 1; } return a;"),
            "intrinsic": BASE.replace("a * t", "fmod(a, t)"),
            "conversion": BASE.replace("a * t", "a * (float)(int)t"),
            "uint-arithmetic": BASE.replace("return a * t;", "uint x = asuint(t); x += 1u; return a * asfloat(x);"),
            "uint-shift": BASE.replace("return a * t;", "uint x = asuint(t) << 1u; return a * asfloat(x);"),
            "matrix": BASE.replace("return a * t;", "float2x2 m; return a * t;"),
            "array": BASE.replace("return a * t;", "float x[2]; return a * t;"),
            "out": "void helper(out float x) { x = 1; }\n" + BASE,
            "default": "float helper(float x = 1) { return x; }\n" + BASE,
            "resource": "Texture2D<float4> image : register(t0);\n" + BASE,
        }
        for name, source in sources.items():
            with self.subTest(name=name):
                self.assert_rejected(source)

    def test_profile_and_storage_equality_metadata(self):
        model = self.compile_model(BASE)
        self.assertEqual(model["schema"], "ieee-1")
        self.assertEqual(model["profile"], "binary32-rne-preserve-subnormals-separate-ops-v1")


class IeeeInfrastructureTests(unittest.TestCase):
    def test_concurrent_writer_rejected(self):
        with workspace_lock():
            with self.assertRaises(ModelError) as caught:
                with workspace_lock():
                    pass
            self.assertEqual(caught.exception.status, "INCONCLUSIVE")

    def test_busy_run_does_not_overwrite_owner_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            report = Path(directory) / "result.json"
            report.write_text('{"status":"IN_PROGRESS","owner":true}', encoding="utf-8")
            with workspace_lock():
                result = subprocess.run(["python", str(ROOT / "tools/ieeeformalize.py"), "prepare", "--output", directory],
                                        capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(json.loads(result.stdout)["status"], "INCONCLUSIVE")
            self.assertTrue(json.loads(report.read_text())["owner"])

    def test_stale_success_overwritten_by_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            output = Path(directory)
            bad = output / "bad.hlsl"
            bad.write_text(BASE.replace("a * t", "fmod(a, t)"), encoding="utf-8")
            (output / "result.json").write_text('{"status":"IEEE_PROVED"}', encoding="utf-8")
            result = subprocess.run(["python", str(ROOT / "tools/ieeeformalize.py"), "prepare", "--optimized", str(bad),
                                     "--output", directory], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads((output / "result.json").read_text())["status"], "UNSUPPORTED")

    def test_target_and_proof_changes_are_unproved(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            root = Path(directory)
            generated = root / "GeneratedModel.lean"
            proof = root / "SubmittedProof.lean"
            generated.write_text("target", encoding="utf-8")
            proof.write_text("proof", encoding="utf-8")
            target_hash = ieeeformalize.sha256(generated)
            hashes = {"SubmittedProof": ieeeformalize.sha256(proof)}
            modules = (("SubmittedProof", root),)
            ieeeformalize.ensure_unchanged(generated, target_hash, hashes, modules)
            generated.write_text("changed target", encoding="utf-8")
            with self.assertRaises(ModelError) as caught:
                ieeeformalize.ensure_unchanged(generated, target_hash, hashes, modules)
            self.assertEqual(caught.exception.status, "UNPROVED")
            generated.write_text("target", encoding="utf-8")
            proof.write_text("changed proof", encoding="utf-8")
            with self.assertRaises(ModelError) as caught:
                ieeeformalize.ensure_unchanged(generated, target_hash, hashes, modules)
            self.assertEqual(caught.exception.status, "UNPROVED")

    def test_prototype_replaced_binaries_fail_before_invocation(self):
        output = ROOT / "artifacts/ieee-hlsl/infrastructure"
        output.mkdir(parents=True, exist_ok=True)
        report_path = ROOT / "artifacts/ieee/result.json"
        log_path = ROOT / "artifacts/ieee/probe.log"
        saved_report = report_path.read_bytes()
        saved_log = log_path.read_bytes()
        try:
            for name in ("lean.exe", "lake.exe"):
                with self.subTest(binary=name):
                    binary = ieeeformalize.LEAN_BIN / name
                    backup = binary.with_suffix(".q-backup")
                    self.assertFalse(backup.exists())
                    binary.rename(backup)
                    try:
                        binary.write_bytes(b"intentionally invalid IEEE toolchain control")
                        result = subprocess.run(["pwsh", "-File", str(ROOT / "prototypes/ieee/run.ps1")],
                                                cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                                                errors="replace", timeout=60)
                    finally:
                        if binary.exists():
                            binary.unlink()
                        backup.rename(binary)
                    self.assertEqual(ieeeformalize.sha256(binary), ieeeformalize.LEAN_LOCK[name])
                    (output / f"toolchain-{name}.log").write_text(
                        result.stdout + "\n--- stderr ---\n" + result.stderr, encoding="utf-8")
                    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
                    (output / f"toolchain-{name}-result.json").write_text(json.dumps(report, indent=2) + "\n",
                                                                           encoding="utf-8")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(report["status"], "FAILED")
                    self.assertIn("ENVIRONMENT_ERROR", report["message"])
                    self.assertIn(name, report["message"])
        finally:
            report_path.write_bytes(saved_report)
            log_path.write_bytes(saved_log)

    def test_suite_timeout_kills_process_tree(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            root = Path(directory)
            ready = root / "pids.json"
            program = (
                "import json,os,pathlib,subprocess,sys;"
                "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
                "pathlib.Path(sys.argv[1]).write_text(json.dumps({'parent':os.getpid(),'child':child.pid}),encoding='utf-8');"
                "child.wait()"
            )
            output = ROOT / "artifacts/ieee-hlsl/infrastructure"
            log = output / "timeout-control.log"
            result = run_ieee_suite.run(["python", "-c", program, ready], log,
                                        ieeeformalize.local_environment(), timeout=2)
            self.assertEqual(result.returncode, 124)
            self.assertIn("IEEE_SUITE_TIMEOUT", log.read_text(encoding="utf-8"))
            pids = json.loads(ready.read_text(encoding="utf-8"))
            parent_active = process_active(pids["parent"])
            child_active = process_active(pids["child"])
            ieeeformalize.write_json(output / "timeout-control-result.json", {
                "status": "TIMEOUT_CONTROL_PASSED", "returncode": result.returncode,
                "parent_pid": pids["parent"], "child_pid": pids["child"],
                "parent_active": parent_active, "child_active": child_active,
            })
            self.assertFalse(parent_active)
            self.assertFalse(child_active)

    def test_suite_timeout_overwrites_stale_success(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            output = Path(directory)
            (output / "result.json").write_text('{"status":"IEEE_SUITE_PASSED"}', encoding="utf-8")
            timeout = subprocess.CompletedProcess(["timeout"], 124, "", "IEEE_SUITE_TIMEOUT")
            with mock.patch.object(run_ieee_suite, "DIRECTORY", output), mock.patch.object(
                    run_ieee_suite, "run", return_value=timeout), mock.patch("builtins.print"):
                result = run_ieee_suite.main()
            self.assertEqual(result, 1)
            self.assertEqual(json.loads((output / "result.json").read_text())["status"], "FAILED")

    def test_missing_or_changed_pinned_lean_is_environment_error(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            with mock.patch.object(ieeeformalize, "LEAN_BIN", Path(directory)):
                with self.assertRaises(ModelError) as caught:
                    ieeeformalize.validate_lean()
                self.assertEqual(caught.exception.status, "ENVIRONMENT_ERROR")


if __name__ == "__main__":
    (ROOT / "artifacts").mkdir(exist_ok=True)
    unittest.main()

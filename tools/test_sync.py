"""Typed AST, uint32 wrapping and contract checks for HLSL synchronization import."""
import argparse
import copy
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from shader_ast import ModelError
from shader_sync import generate_pvl, import_sync, sync_contract
from shaderformalize import ROOT, sha256, validate_dxc
import run_sync_suite
from syncformalize import java_environment, prepare, run_process, synchronization_lock, validate_vercors_payload


class SynchronizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dxc = validate_dxc()
        cls.base = ROOT / "examples" / "synchronization-hlsl"
        cls.contract = json.loads((cls.base / "constraints.json").read_text(encoding="utf-8"))

    def compile(self, source):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            path = Path(directory) / "input.hlsl"
            path.write_text(source, encoding="utf-8")
            result = subprocess.run([str(self.dxc), "-T", "cs_6_0", "-E", "main", "-HV", "2021", "-ast-dump", str(path)],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return import_sync(source, result.stdout)

    def original(self):
        return (self.base / "original.hlsl").read_text(encoding="utf-8")

    def test_every_access_and_barrier_becomes_an_ordered_event(self):
        model = self.compile(self.original())
        self.assertEqual([event["kind"] for event in model["events"]], ["load", "store", "barrier", "load", "store"])
        self.assertEqual([event.get("resource") for event in model["events"]], ["Input", "shared", None, "shared", "Output"])
        pvl = generate_pvl(model)
        self.assertNotIn("assume", pvl)
        self.assertIn("barrier(lanes)", pvl)
        self.assertIn("requires Perm(shared[tid], write)", pvl)
        self.assertIn("ensures Perm(shared[1-tid], write)", pvl)

    def test_missing_barrier_removes_permission_reallocation(self):
        source = (self.base / "missing-barrier.hlsl").read_text(encoding="utf-8")
        pvl = generate_pvl(self.compile(source))
        self.assertNotIn("barrier(lanes)", pvl)
        self.assertIn("ensures Perm(shared[tid], write)", pvl)
        self.assertNotIn("ensures Perm(shared[1-tid], write)", pvl)

    def test_shared_literal_index_is_not_dropped(self):
        source = (self.base / "shared-conflict.hlsl").read_text(encoding="utf-8")
        pvl = generate_pvl(self.compile(source))
        self.assertIn("shared[0] = input[tid]", pvl)

    def test_uint_addition_and_subtraction_are_explicitly_modular(self):
        model = self.compile(self.original().replace("uint i = tid.x;", "uint i = tid.x + 0u;"))
        pvl = generate_pvl(model)
        self.assertEqual(pvl.count("4294967296"), 16)
        self.assertIn("((tid % 4294967296) + (0 % 4294967296)) % 4294967296", pvl)
        self.assertIn("1 % 4294967296", pvl)

    def test_contract_requires_distinct_physical_identities(self):
        model = self.compile(self.original())
        aliased = copy.deepcopy(self.contract)
        aliased["bindings"]["Output"]["identity"] = aliased["bindings"]["Input"]["identity"]
        with self.assertRaisesRegex(ModelError, "Aliased") as caught:
            sync_contract(aliased, model)
        self.assertEqual(caught.exception.status, "UNSUPPORTED")

    def test_contract_rejects_non_two_capacity_and_missing_binding(self):
        model = self.compile(self.original())
        invalid = copy.deepcopy(self.contract)
        invalid["bindings"]["Input"]["capacity"] = 3
        with self.assertRaises(ModelError):
            sync_contract(invalid, model)
        invalid = copy.deepcopy(self.contract)
        del invalid["bindings"]["Output"]
        with self.assertRaises(ModelError):
            sync_contract(invalid, model)

    def test_control_flow_and_helpers_are_rejected(self):
        with self.assertRaisesRegex(ModelError, "Unsupported synchronization statement"):
            self.compile(self.original().replace("uint i = tid.x;", "uint i = tid.x; if (i > 0u) { i = 0u; }"))
        with self.assertRaisesRegex(ModelError, "only one main"):
            self.compile("float4 Helper(float4 x) { return x; }\n" + self.original())

    def test_wrong_entry_and_barrier_count_are_rejected(self):
        with self.assertRaisesRegex(ModelError, "numthreads"):
            self.compile(self.original().replace("[numthreads(2, 1, 1)]", "[numthreads(4, 1, 1)]"))
        with self.assertRaisesRegex(ModelError, "at most one barrier"):
            self.compile(self.original().replace("Output[i] = Shared", "GroupMemoryBarrierWithGroupSync();\n    Output[i] = Shared"))

    def test_float_locals_and_extra_resources_are_rejected(self):
        with self.assertRaisesRegex(ModelError, "Only initialized uint locals"):
            self.compile(self.original().replace("uint i = tid.x;", "uint i = tid.x; float4 v = Input[0];").replace("Shared[i] = Input[i];", "Shared[i] = v;"))
        with self.assertRaisesRegex(ModelError, "requires shared"):
            self.compile(self.original() + "StructuredBuffer<float4> Extra : register(t1);\n")

    def test_prepare_binds_source_ast_contract_and_pvl_hashes(self):
        args = argparse.Namespace(original=self.base / "original.hlsl", constraints=self.base / "constraints.json")
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            output = Path(directory)
            summary = prepare(args, output)
            self.assertEqual(summary["status"], "PREPARED")
            self.assertEqual(summary["source"]["sha256"], sha256(self.base / "original.hlsl"))
            self.assertEqual(summary["constraints_sha256"], sha256(self.base / "constraints.json"))
            self.assertEqual(summary["ast_sha256"], sha256(output / "original.dxc.log"))
            self.assertEqual(summary["pvl_sha256"], sha256(output / "Generated.pvl"))

    def test_java_failure_is_an_environment_error(self):
        with self.assertRaises(ModelError) as caught:
            java_environment(ROOT / "artifacts" / "missing-java-home")
        self.assertEqual(caught.exception.status, "ENVIRONMENT_ERROR")

    def test_wrong_resource_kinds_are_rejected_during_import(self):
        two_inputs = self.original().replace("RWStructuredBuffer<float4> Output : register(u0)", "StructuredBuffer<float4> Output : register(t1)")
        two_inputs = two_inputs.replace("Output[i] = Shared[1u - i];", "Shared[i] = Shared[1u - i];")
        with self.assertRaisesRegex(ModelError, "one input buffer, one output buffer"):
            self.compile(two_inputs)
        two_outputs = self.original().replace("StructuredBuffer<float4> Input : register(t0)", "RWStructuredBuffer<float4> Input : register(u1)")
        with self.assertRaisesRegex(ModelError, "one input buffer, one output buffer"):
            self.compile(two_outputs)

    def test_timeout_after_lock_writes_final_inconclusive(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            output = Path(directory)
            result = subprocess.run([sys.executable, str(ROOT / "tools" / "syncformalize.py"), "check",
                                     "--original", str(self.base / "original.hlsl"), "--constraints", str(self.base / "constraints.json"),
                                     "--output", str(output), "--timeout", "0"], capture_output=True, text=True, timeout=60)
            report = json.loads((output / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["status"], "INCONCLUSIVE")

    def test_timeout_stops_parent_and_child_and_saves_log(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            output = Path(directory)
            pids_path = output / "pids.json"
            program = (
                "import json,os,pathlib,subprocess,sys;"
                "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
                "pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(),child.pid]));"
                "print('child started',flush=True);child.wait()"
            )
            with self.assertRaises(ModelError) as caught:
                run_process([sys.executable, "-c", program, pids_path], output / "timeout.log", None, 2)
            self.assertEqual(caught.exception.status, "INCONCLUSIVE")
            self.assertIn("child started", (output / "timeout.log").read_text(encoding="utf-8"))
            self.assertIn("process tree terminated", (output / "timeout.log").read_text(encoding="utf-8"))
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            for pid in json.loads(pids_path.read_text()):
                handle = kernel.OpenProcess(0x00100000, False, pid)
                if handle:
                    try:
                        self.assertEqual(kernel.WaitForSingleObject(handle, 0), 0, f"Process {pid} still running")
                    finally:
                        kernel.CloseHandle(handle)

    def test_suite_timeout_replaces_stale_success_with_terminal_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            output = Path(directory)
            (output / "result.json").write_text('{"status":"PASSED"}', encoding="utf-8")
            with mock.patch.object(run_sync_suite, "DIRECTORY", output), mock.patch.object(
                    run_sync_suite, "run", side_effect=ModelError("controlled timeout", "INCONCLUSIVE")):
                self.assertEqual(run_sync_suite.main(), 2)
            self.assertEqual(json.loads((output / "result.json").read_text())["status"], "INCONCLUSIVE")

    def test_lock_contention_does_not_create_or_replace_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            output = Path(directory)
            with synchronization_lock():
                result = subprocess.run([sys.executable, str(ROOT / "tools" / "syncformalize.py"), "prepare",
                                         "--original", str(self.base / "original.hlsl"), "--constraints", str(self.base / "constraints.json"),
                                         "--output", str(output)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 2)
            self.assertFalse((output / "result.json").exists())

    def test_installed_vercors_payload_must_match_locked_zip(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            root = Path(directory)
            installation = root / "install"
            installation.mkdir()
            archive = root / "tool.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("vercors.bat", "expected payload")
            (installation / "vercors.bat").write_text("expected payload", encoding="utf-8")
            self.assertEqual(validate_vercors_payload(installation, archive), 1)
            (installation / "vercors.bat").write_text("changed payload!", encoding="utf-8")
            with self.assertRaises(ModelError) as caught:
                validate_vercors_payload(installation, archive)
            self.assertEqual(caught.exception.status, "ENVIRONMENT_ERROR")


if __name__ == "__main__":
    unittest.main()

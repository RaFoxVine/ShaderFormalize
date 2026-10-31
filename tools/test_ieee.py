"""Unit and infrastructure controls for the independent IEEE HLSL frontend."""
import ctypes
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import ieeeformalize
import run_ieee_suite
import run_ieee_probe
import shaderformalize
from ieeeformalize import ROOT, workspace_lock
from shader_ast import ModelError
from shader_ieee_frontend import IeeeControlProgram, import_ieee
from shader_ieee_lean import empty_constraints, scientific_arguments, generate_ieee
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
            "loop": BASE.replace("return a * t;", "while (t > 0) { t -= 1; } return a;"),
            "intrinsic": BASE.replace("a * t", "fmod(a, t)"),
            "conversion": BASE.replace("a * t", "a * (float)(int)t"),
            "uint-to-float-cast": BASE.replace("a * t", "a * (float)asuint(t)"),
            "float-to-uint-cast": BASE.replace("a * t", "a * asfloat((uint)t)"),
            "mixed-float-uint-arithmetic": BASE.replace("a * t", "a * (asuint(t) + t)"),
            "uint-division": BASE.replace("return a * t;", "uint x = asuint(t) / 2u; return a * asfloat(x);"),
            "uint-remainder": BASE.replace("return a * t;", "uint x = asuint(t) % 2u; return a * asfloat(x);"),
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

    def test_uint_operators_compile_to_integer_semantics(self):
        operators = {"+": "uintAdd", "-": "uintSubtract", "*": "uintMultiply",
                     "&": "uintAnd", "|": "uintOr", "^": "uintXor",
                     "<<": "uintShiftLeft", ">>": "uintShiftRight"}
        for operator, function in operators.items():
            with self.subTest(operator=operator):
                source = BASE.replace("a * t", "a * asfloat(asuint(t) " + operator + " 0xFFFFFFFFu)")
                model = self.compile_model(source)
                generated = generate_ieee(model, model)
                self.assertIn("ShaderIeee.Model." + function, generated)
                self.assertIn("(4294967295 : UInt32)", generated)

    def test_uint_comparisons_do_not_use_float_comparisons(self):
        for operator in ("<", "<=", ">", ">=", "==", "!="):
            with self.subTest(operator=operator):
                value = "asuint(t) " + operator + " 0x80000000u ? 0xFFFFFFFFu : 0u"
                model = self.compile_model(BASE.replace("a * t", "a * asfloat(" + value + ")"))
                generated = generate_ieee(model, model)
                self.assertIn("(2147483648 : UInt32)", generated)
                self.assertNotIn("ShaderIeee.Model.compare", generated)
                self.assertIn("if ", generated)

    def test_float_comparison_keeps_ieee_semantics(self):
        model = self.compile_model(BASE.replace("a * t", "a * (t == t ? t : 0.0f)"))
        self.assertIn("ShaderIeee.Model.compareEqual", generate_ieee(model, model))

    def test_uint_unary_and_boolean_selection(self):
        source = BASE.replace("return a * t;", "uint x = asuint(t); bool b = x == 0u ? true : false; "
                              "uint y = b ? ~x : -x; return a * asfloat(y);")
        model = self.compile_model(source)
        generated = generate_ieee(model, model)
        self.assertIn("ShaderIeee.Model.uintNot", generated)
        self.assertIn("ShaderIeee.Model.uintNegate", generated)

    def test_bit_values_cross_helpers_and_struct_fields(self):
        helper = "struct Bits { uint word; float payload; }; "
        helper += "Bits save(uint x) { Bits b; b.word = asuint(x); b.payload = asfloat(x); return b; } "
        source = helper + BASE.replace("return a * t;", "Bits b = save(asuint(t)); "
                                      "return a * asfloat(b.word ^ asuint(b.payload));")
        model = self.compile_model(source)
        generated = generate_ieee(model, model)
        self.assertIn("ShaderIeee.Model.uintXor", generated)

    def test_uint_hex_literal_value_is_checked_against_dxc(self):
        source = BASE.replace("a * t", "a * asfloat(0x1234ABCDu)")
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            path = Path(directory) / "input.hlsl"
            path.write_text(source, encoding="utf-8")
            result = subprocess.run([str(self.dxc), "-T", "ps_6_0", "-E", "main", "-HV", "2021",
                                     "-ast-dump", str(path)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0)
            with self.assertRaises(ModelError):
                import_ieee(source, result.stdout.replace(" 305441741", " 305441742"))

    def test_uint_compound_assignments_in_both_execution_paths(self):
        operators = {"+=": "uintAdd", "-=": "uintSubtract", "*=": "uintMultiply",
                     "&=": "uintAnd", "|=": "uintOr", "^=": "uintXor",
                     "<<=": "uintShiftLeft", ">>=": "uintShiftRight"}
        for operator, function in operators.items():
            for branching in (False, True):
                with self.subTest(operator=operator, branching=branching):
                    assignment = "x " + operator + " 33u;"
                    if branching:
                        assignment = "if (t > 0.0f) { " + assignment + " }"
                    source = BASE.replace("return a * t;", "uint x = asuint(t); " + assignment +
                                          " return a * asfloat(x);")
                    model = self.compile_model(source)
                    self.assertIn("ShaderIeee.Model." + function, generate_ieee(model, model))

    def test_uint_compound_computation_metadata_is_checked(self):
        source = BASE.replace("return a * t;", "uint x = asuint(t); x += 1u; return a * asfloat(x);")
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            path = Path(directory) / "input.hlsl"
            path.write_bytes(source.encode("utf-8"))
            result = subprocess.run([str(self.dxc), "-T", "ps_6_0", "-E", "main", "-HV", "2021",
                                     "-ast-dump", str(path)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0)
            for field in ("ComputeLHSTy", "ComputeResultTy"):
                with self.subTest(field=field), self.assertRaises(ModelError):
                    import_ieee(source, result.stdout.replace(field + "='uint'", field + "='float'"))

    def test_control_examples_import_original_and_rewrites(self):
        for name in ("branch-record", "helper-return", "float-branches"):
            for role in ("original", "optimized", "wrong"):
                with self.subTest(name=name, role=role):
                    source = (ROOT / "examples/ieee-control" / (name + "." + role + ".hlsl")).read_text(encoding="utf-8")
                    model = self.compile_model(source)
                    generated = generate_ieee(model, model)
                    self.assertIn("def expected : Prop :=", generated)
                    self.assertNotIn("ShaderFormalize", generated)

    def test_control_rejects_partial_initialization_and_readonly_writes(self):
        bodies = [
            "uint x; if (t > 0.0f) { x = 1u; } return a * asfloat(x);",
            "uint x; if (t > 0.0f) { x += 1u; } return a;",
            "if (t > 0.0f) { a = a * t; } return a;",
            "if (t > 0.0f) { uint x = 1u; } return a * asfloat(x);",
            "if (t) { return a; } return a * t;",
            "if (asuint(t)) { return a; } return a * t;",
            "if (t > 0.0f) { discard; } return a;",
        ]
        for body in bodies:
            with self.subTest(body=body):
                self.assert_rejected(BASE.replace("return a * t;", body))
        prefix = "struct Data { uint word; float value; }; "
        self.assert_rejected(prefix + BASE.replace("return a * t;", "Data d; "
                             "if (t > 0.0f) { d.word = 1u; } else { d.value = t; } "
                             "return a * asfloat(d.word);"))

    def test_uncalled_branch_helpers_are_checked(self):
        self.compile_model("float unused(float x) { if (x > 0.0f) { return x; } return -x; }\n" + BASE)
        self.assert_rejected("float unused(float x) { float y; if (x > 0.0f) { y = x; } return y; }\n" + BASE)
        self.assert_rejected("float unused(float x) { if (x > 0.0f) { return x; } }\n" + BASE)

    def test_guarded_helper_precheck_restores_caller_state(self):
        source = "float helper(float x) { if (x > 0.0f) { return x; } return -x; }\n" + BASE
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            path = Path(directory) / "input.hlsl"
            path.write_bytes(source.encode("utf-8"))
            result = subprocess.run([str(self.dxc), "-T", "ps_6_0", "-E", "main", "-HV", "2021",
                                     "-ast-dump", str(path)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0)
            program = IeeeControlProgram(source, result.stdout)
            names = ("bindings", "events", "effects", "stack", "fragment", "invocations",
                     "current_guard", "alive", "frame", "branches")
            before = {name: getattr(program, name) for name in names}
            program.validate_helper_initialization()
            for name, value in before.items():
                self.assertIs(getattr(program, name), value, name)

    def test_branch_and_return_limits(self):
        for count, accepted in ((32, True), (33, False)):
            source = BASE.replace("return a * t;", "if (t > 0.0f) {" * count +
                                  "uint x = 1u;" + "}" * count + "return a;")
            if accepted:
                self.compile_model(source)
            else:
                self.assert_rejected(source)
        for count, accepted in ((127, True), (128, False)):
            branches = " ".join("if (t == " + str(i) + ".0f) { return a; }" for i in range(count))
            source = BASE.replace("return a * t;", branches + " return a * t;")
            if accepted:
                self.compile_model(source)
            else:
                self.assert_rejected(source)


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

    def prototype_fixture(self, directory):
        fixture = Path(directory)
        (fixture / "tools").mkdir()
        for source in (ROOT / "tools").glob("*.py"):
            shutil.copy2(source, fixture / "tools" / source.name)
        shutil.copy2(ROOT / "dependencies.lock.json", fixture / "dependencies.lock.json")
        wrapper = fixture / "prototypes/ieee/run.ps1"
        wrapper.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "prototypes/ieee/run.ps1", wrapper)
        binaries = fixture / ieeeformalize.LEAN_BIN.relative_to(ROOT)
        binaries.mkdir(parents=True)
        for name in ieeeformalize.LEAN_LOCK:
            shutil.copy2(ieeeformalize.LEAN_BIN / name, binaries / name)
        output = fixture / "artifacts/ieee"
        output.mkdir(parents=True)
        return fixture, binaries, output, wrapper

    def run_prototype_fixture(self, wrapper):
        return subprocess.run(["pwsh", "-File", str(wrapper)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60)

    def test_prototype_replaced_binaries_fail_before_invocation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            fixture, binaries, output, wrapper = self.prototype_fixture(directory)
            for name in ieeeformalize.LEAN_LOCK:
                with self.subTest(binary=name):
                    (binaries / name).write_bytes(b"intentionally invalid isolated toolchain control")
                    result = self.run_prototype_fixture(wrapper)
                    shutil.copy2(ieeeformalize.LEAN_BIN / name, binaries / name)
                    report = json.loads((output / "result.json").read_text(encoding="utf-8"))
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(report["status"], "FAILED")
                    self.assertIn("ENVIRONMENT_ERROR", report["message"])
                    self.assertIn(name, report["message"])
                    self.assertNotIn("Traceback", result.stderr)

    def test_busy_prototype_with_damaged_tool_preserves_owner_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            fixture, binaries, output, wrapper = self.prototype_fixture(directory)
            (binaries / "lean.exe").write_bytes(b"damaged isolated tool")
            report, log = output / "result.json", output / "probe.log"
            report.write_bytes(b'{"status":"IN_PROGRESS","owner":true}')
            log.write_bytes(b"active owner log")
            before = report.read_bytes(), log.read_bytes()
            with mock.patch.object(shaderformalize, "ROOT", fixture), workspace_lock():
                result = self.run_prototype_fixture(wrapper)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)["status"], "INCONCLUSIVE")
            self.assertEqual((report.read_bytes(), log.read_bytes()), before)

    def test_damaged_prototype_tool_writes_terminal_without_invoking_lean(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            fixture = Path(directory)
            output = fixture / "artifacts/ieee"
            output.mkdir(parents=True)
            (output / "result.json").write_text('{"status":"EXTERNAL_LIBRARY_PROTOTYPE_PASSED"}', encoding="utf-8")
            error = ModelError("Pinned Lean file missing/changed: lean.exe", "ENVIRONMENT_ERROR")
            with mock.patch.object(shaderformalize, "ROOT", fixture), mock.patch.object(
                    run_ieee_probe, "ROOT", fixture), mock.patch.object(run_ieee_probe, "validate_lean",
                    side_effect=error), mock.patch.object(run_ieee_probe, "run_lean") as invoked, mock.patch("builtins.print"):
                result = run_ieee_probe.main()
            self.assertEqual(result, 1)
            final = json.loads((output / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(final["status"], "FAILED")
            self.assertIn("ENVIRONMENT_ERROR", final["message"])
            invoked.assert_not_called()

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

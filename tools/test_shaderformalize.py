"""Regression tests for real-source import and false-proof prevention."""
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from shader_model import ModelError, exact_number, import_shader, load_constraints
from shaderformalize import ROOT, audit_axioms, validate_dxc, workspace_lock


class SourceImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dxc = validate_dxc()
        cls.source = (ROOT / "examples/lerp/original.hlsl").read_text(encoding="utf-8")
        cls.original, cls.dump = cls.compile_model(cls.source)

    @classmethod
    def compile_model(cls, source):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            path = Path(directory) / "input.hlsl"
            path.write_bytes(source.encode("utf-8"))
            result = subprocess.run([str(cls.dxc), "-T", "ps_6_0", "-E", "main", "-HV", "2021", "-ast-dump", str(path)],
                                    capture_output=True, text=True, encoding="utf-8", check=True)
        return import_shader(source, result.stdout), result.stdout

    def test_intrinsics_and_interface(self):
        self.assertEqual(self.original["expression"]["kind"], "lerp")
        self.assertEqual([p["width"] for p in self.original["interface"]], [4, 4, 1])

    def test_literal_uses_source_spelling(self):
        number = "0.123456789123456789"
        model, _ = self.compile_model(self.source.replace("lerp(a, b, saturate(t))", "a * " + number))
        literal = model["expression"]["arguments"][1]["arguments"][0]
        self.assertEqual(Fraction(literal["numerator"], literal["denominator"]), Fraction(number))

    def test_integer_and_unary(self):
        model, _ = self.compile_model(self.source.replace("lerp(a, b, saturate(t))", "-a * 2"))
        self.assertEqual(model["expression"]["kind"], "multiply")

    def test_unsupported_division(self):
        with self.assertRaises(ModelError):
            self.compile_model(self.source.replace("lerp(a, b, saturate(t))", "a / t"))

    def test_octal_integers_not_read_as_decimal(self):
        for number in ("010", "077", "00", "0x10"):
            with self.subTest(number=number), self.assertRaises(ModelError):
                self.compile_model(self.source.replace("lerp(a, b, saturate(t))", "a * " + number))

    def test_locals_not_silently_dropped(self):
        from shader_eval import evaluate_model
        source = self.source.replace("return lerp(a, b, saturate(t));", "float x = t; x += 1; x *= 2; return a * x;")
        model, _ = self.compile_model(source)
        self.assertEqual(evaluate_model(model, [[1, 2, 3, 4], [0, 0, 0, 0], [.25]]), [2.5, 5, 7.5, 10])

    def test_user_intrinsic_spoof_rejected(self):
        with self.assertRaises(ModelError):
            self.compile_model("float saturate(float x) { return x + 10; }\n" + self.source)

    def test_macro_rejected(self):
        with self.assertRaises(ModelError):
            self.compile_model("#define FACTOR 0.5\n" + self.source.replace("lerp(a, b, saturate(t))", "a * FACTOR"))

    def test_directive_after_comment_rejected(self):
        with self.assertRaises(ModelError):
            self.compile_model("/* 10 */ #define FACTOR 8\n" + self.source.replace("lerp(a, b, saturate(t))", "a * FACTOR"))

    def test_line_splicing_rejected(self):
        with self.assertRaises(ModelError):
            self.compile_model(self.source.replace("lerp(a, b, saturate(t))", "a * 1\\\n0"))

    def test_nonphysical_line_breaks_rejected(self):
        for character in ("\v", "\f", "\x85", "\u2028", "\u2029"):
            source = self.source.replace("{\n", "{\n/*" + character + "               10*/\n").replace("lerp(a, b, saturate(t))", "a * 8")
            with self.subTest(character=repr(character)), self.assertRaises(ModelError):
                self.compile_model(source)

    def test_utf8_comment_and_crlf_literal_locations(self):
        source = self.source.replace("lerp(a, b, saturate(t))", "/*颜色*/ a * 0.123456789123456789f").replace("\n", "\r\n")
        model, _ = self.compile_model(source)
        literal = model["expression"]["arguments"][1]["arguments"][0]
        self.assertEqual(Fraction(literal["numerator"], literal["denominator"]), Fraction("0.123456789123456789"))

    def test_multiline_literal_location_tracks_dump_state(self):
        source = self.source.replace("lerp(a, b, saturate(t))", "lerp(a, /*0.9*/\n b,                  0.3)")
        model, _ = self.compile_model(source)
        literal = model["expression"]["arguments"][2]["arguments"][0]
        self.assertEqual(Fraction(literal["numerator"], literal["denominator"]), Fraction("0.3"))

    def test_nested_multiline_literal_positions(self):
        source = self.source.replace("lerp(a, b, saturate(t))", "lerp(\n a * 0.125, /* 0.9 */\n b * (0.25\n + 0.375), /* 0.8 */\n saturate(t * 0.5 + 0.75))")
        model, _ = self.compile_model(source)
        def numbers(expr):
            if expr["kind"] == "literal":
                return [Fraction(expr["numerator"], expr["denominator"])]
            result = []
            for child in expr.get("arguments", []):
                result.extend(numbers(child))
            return result
        self.assertEqual(numbers(model["expression"]), [Fraction(s) for s in ("0.125", "0.25", "0.375", "0.5", "0.75")])

    def test_interface_mismatch_is_invalid(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            output = Path(directory)
            changed = output / "changed.hlsl"
            changed.write_bytes(self.source.replace("COLOR1", "COLOR2").encode("utf-8"))
            result = subprocess.run(["python", str(ROOT / "tools/shaderformalize.py"), "prepare", "--optimized", str(changed), "--output", str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads((output / "result.json").read_text())["status"], "INVALID_INPUT")

    def test_bom_columns_use_original_bytes(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            output = Path(directory)
            source = " ".join(self.source.replace("lerp(a, b, saturate(t))", "a * 1001").splitlines())
            path = output / "bom.hlsl"
            path.write_bytes(b"\xef\xbb\xbf" + source.encode("utf-8"))
            result = subprocess.run(["python", str(ROOT / "tools/shaderformalize.py"), "prepare", "--original", str(path), "--optimized", str(path), "--output", str(output)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            model = json.loads((output / "original.model.json").read_text())
            literal = model["expression"]["arguments"][1]["arguments"][0]
            self.assertEqual(literal["numerator"], 1001)

    def test_apostrophe_in_source_path(self):
        with tempfile.TemporaryDirectory(prefix="audit'case,", dir=ROOT / "artifacts") as directory:
            source = " " * 100 + "/*10*/\n" + " ".join(self.source.replace("lerp(a, b, saturate(t))", "a * 8").splitlines())
            path = Path(directory) / "input.hlsl"
            path.write_bytes(source.encode("utf-8"))
            result = subprocess.run([str(self.dxc), "-T", "ps_6_0", "-E", "main", "-HV", "2021", "-ast-dump", str(path)],
                                    capture_output=True, text=True, encoding="utf-8", check=True)
            model = import_shader(source, result.stdout)
            self.assertEqual(model["expression"]["arguments"][1]["arguments"][0]["numerator"], 8)

    def test_unknown_ast_rejected(self):
        with self.assertRaises(ModelError):
            import_shader(self.source, self.dump.replace("ReturnStmt", "UnknownStmt"))

    def test_constraints_strict_and_nonempty(self):
        good = {"schema": 1, "ranges": {"t": {"min": "0", "max": "1"}}}
        self.assertEqual(load_constraints(good, self.original["interface"]), (Fraction(0), Fraction(1)))
        changes = [
            {"schema": True, "ranges": good["ranges"]},
            {"schema": 1, "ranges": {"t": {"min": "1", "max": "0"}}},
            {"schema": 1, "ranges": {"t": {"min": 0, "max": "1"}}},
            {"schema": 1, "ranges": {"unknown": {"min": "0", "max": "1"}}},
            dict(good, extra=True),
        ]
        for invalid in changes:
            with self.subTest(invalid=invalid), self.assertRaises(ModelError):
                load_constraints(invalid, self.original["interface"])

    def test_stale_success_overwritten(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            output = Path(directory)
            bad = output / "bad.hlsl"
            bad.write_text(self.source.replace("lerp(a, b, saturate(t))", "a / t"), encoding="utf-8")
            (output / "result.json").write_text('{"status":"PROVED"}', encoding="utf-8")
            result = subprocess.run(["python", str(ROOT / "tools/shaderformalize.py"), "prepare", "--optimized", str(bad), "--output", str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads((output / "result.json").read_text())["status"], "UNSUPPORTED")


class ProofInfrastructureTests(unittest.TestCase):
    def test_no_extra_axioms(self):
        name = "ShaderFormalize.Verification.checked"
        self.assertEqual(audit_axioms("'" + name + "' depends on axioms: [propext, Classical.choice, Quot.sound]"), ["propext", "Classical.choice", "Quot.sound"])
        for axiom in ("sorryAx", "myLie"):
            with self.assertRaises(ModelError):
                audit_axioms("'" + name + "' depends on axioms: [" + axiom + "]")

    def test_missing_audit_is_failure(self):
        with self.assertRaises(ModelError):
            audit_axioms("all fine")

    def test_concurrent_writer_rejected(self):
        with workspace_lock():
            with self.assertRaises(ModelError):
                with workspace_lock():
                    self.fail("lock should not be acquired twice")

    def test_busy_run_does_not_overwrite_owner_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            report = Path(directory) / "result.json"
            report.write_text('{"status":"IN_PROGRESS","owner":true}', encoding="utf-8")
            with workspace_lock():
                result = subprocess.run(["python", str(ROOT / "tools/shaderformalize.py"), "prepare", "--output", directory],
                                        capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(json.loads(result.stdout)["status"], "INCONCLUSIVE")
            self.assertTrue(json.loads(report.read_text())["owner"])

    def test_invalid_decimal_values(self):
        for text in ("nan", "inf", "0x1", "1/3", "1e1001", 0.1):
            with self.subTest(text=text), self.assertRaises(ModelError):
                exact_number(text)


if __name__ == "__main__":
    (ROOT / "artifacts").mkdir(exist_ok=True)
    unittest.main()

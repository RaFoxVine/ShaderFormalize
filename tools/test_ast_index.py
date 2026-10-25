"""DXC-backed closure checks for a metadata tool, independent of Lean models."""
import contextlib
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from analyze_shader import main, provenance
from dxc_ast_index import AnalysisError, Analyzer, DumpIndex
from shaderformalize import ROOT, validate_dxc

ENTRY = "float4 main(float2 uv:TEXCOORD0):SV_Target{"


class IndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dxc = validate_dxc()
        (ROOT / "artifacts").mkdir(exist_ok=True)

    def compile(self, source):
        # An apostrophe in a path must not be confused with a type quote.
        with tempfile.TemporaryDirectory(prefix="index'", dir=ROOT / "artifacts") as directory:
            path = Path(directory) / "shader.hlsl"
            path.write_bytes(source.encode("utf-8"))
            result = subprocess.run([str(self.dxc), "-T", "ps_6_0", "-E", "main", "-HV", "2021", "-ast-dump", str(path)],
                                    capture_output=True, text=True, encoding="utf-8", check=True)
        return result.stdout

    def analyze(self, source):
        return Analyzer(DumpIndex(self.compile(source)), "main").run()

    def test_overloads_use_declaration_ids_and_skip_unused_bodies(self):
        source = "float F(float x){return x;}float2 F(float2 x){return x;}float Unused(){return 7;}" + ENTRY + "return F(uv.x); }"
        report = self.analyze(source)
        self.assertEqual(report["status"], "ANALYZED")
        self.assertEqual(report["definition_count"], 4)
        self.assertEqual(report["reachable_definitions"], 2)
        self.assertEqual([item["signature"] for item in report["functions"] if item["name"] == "F"], ["float (float)"])
        index = DumpIndex(self.compile(source))
        with self.assertRaisesRegex(AnalysisError, "one declaration group"):
            Analyzer(index, "F")

    def test_default_call_and_unreferenced_global_initialization(self):
        source = "float Seed(){return 1;}float F(float x=Seed()){return x;}float G(){return 2;}static float K=G();" + ENTRY + "return F();}"
        report = self.analyze(source)
        self.assertEqual(report["status"], "ANALYZED")
        self.assertEqual({item["name"] for item in report["functions"]}, {"main", "Seed", "F", "G"})
        self.assertEqual(len(report["default_arguments"]), 1)
        self.assertTrue(any(edge["name"] == "G" and edge["owner"].startswith("global:") for edge in report["calls"]))
        self.assertTrue(any(edge["name"] == "Seed" and edge["owner"].startswith("default:") for edge in report["calls"]))

    def test_explicit_argument_does_not_execute_default(self):
        source = "float Seed(){return 1;}float F(float x=Seed()){return x;}" + ENTRY + "return F(2); }"
        report = self.analyze(source)
        self.assertEqual({item["name"] for item in report["functions"]}, {"main", "F"})
        self.assertFalse(report["default_arguments"])

    def test_previous_declaration_and_nested_default_closure(self):
        source = "float Seed(){return 1;}float Inner(float x=Seed()){return x;}float F(float x=Inner());float F(float x){return x;}" + ENTRY + "return F();}"
        report = self.analyze(source)
        self.assertEqual(report["status"], "ANALYZED")
        self.assertEqual(len(report["default_arguments"]), 2)
        self.assertEqual({item["name"] for item in report["functions"]}, {"main", "F", "Inner", "Seed"})
        self.assertTrue(any(edge["raw_id"] != edge["canonical_id"] for edge in report["calls"]))

    def test_conflicting_previous_signature_is_incomplete(self):
        dump = self.compile("float F(float x=1);float F(float x){return x;}" + ENTRY + "return F();}")
        changed = dump.replace("F 'float (float)'", "F 'float (float2)'", 1)
        report = Analyzer(DumpIndex(changed), "main").run()
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertIn("DECLARATION_SIGNATURE_MISMATCH", [item["code"] for item in report["issues"]])
        self.assertIsNone(report["default_arguments"][0]["initializer_line"])

    def test_resources_matrix_operators_and_null_branches(self):
        source = "Texture2D<float4> t:register(t0);SamplerState s:register(s0);cbuffer B:register(b0){float4x4 M;}" + ENTRY + "if(uv.x>0)return t.SampleLevel(s,uv,0);return M[0];}"
        report = self.analyze(source)
        self.assertEqual(report["status"], "ANALYZED")
        self.assertEqual({item["name"] for item in report["external_calls"]}, {"SampleLevel", "operator[]"})
        self.assertGreater(report["node_counts_by_origin"]["body"]["Null"], 0)
        self.assertTrue({"t", "s", "M"}.issubset({item["name"] for item in report["referenced_globals"]}))

    def test_external_resource_overloads_are_not_merged_by_name(self):
        source = "Texture2D<float4> a:register(t0);Texture2D<float> b:register(t1);SamplerState s:register(s0);" + ENTRY + "return a.SampleLevel(s,uv,0)+b.SampleLevel(s,uv,0); }"
        report = self.analyze(source)
        methods = [item for item in report["external_calls"] if item["name"] == "SampleLevel"]
        self.assertEqual(len(methods), 2)
        self.assertEqual(len({item["canonical_id"] for item in methods}), 2)

    def test_unknown_callee_constructor_and_missing_default_are_incomplete(self):
        dump = self.compile("float F(float x=1){return x;}" + ENTRY + "return F();}")
        unknown = dump.replace("DeclRefExpr", "UnresolvedLookupExpr", 1)
        self.assertEqual(Analyzer(DumpIndex(unknown), "main").run()["status"], "INCOMPLETE")
        constructor = dump.replace("IntegerLiteral", "CXXConstructExpr", 1)
        self.assertEqual(Analyzer(DumpIndex(constructor), "main").run()["status"], "INCOMPLETE")
        missing = re.sub(r"\bFunction 0x[0-9a-fA-F]+ 'F'", "Function 0xdead 'F'", dump)
        report = Analyzer(DumpIndex(missing), "main").run()
        self.assertIn("UNRESOLVED_DEFAULT_ARGUMENT", [item["code"] for item in report["issues"]])

    def test_nested_invalid_sloc_is_metadata_not_a_semantic_import(self):
        dump = self.compile(ENTRY + "return 1;}")
        nested = dump.replace("<<invalid sloc>>", "<col:8, <invalid sloc>>")
        self.assertEqual(Analyzer(DumpIndex(nested), "main").run()["status"], "ANALYZED")

    def test_cycle_graph_terminates_and_bad_previous_chain_fails(self):
        dump = self.compile("float F(){return 1;}" + ENTRY + "return F();}")
        function = re.search(r"FunctionDecl (0x[0-9a-fA-F]+).*? F 'float \(\)'", dump).group(1)
        # A synthetic extra call with an existing target tests graph termination.
        index = DumpIndex(dump)
        group = index.canonical[function]
        body = index.bodies[group][0]
        call = next(i for i, node in enumerate(index.nodes) if node.kind == "CallExpr")
        self.assertEqual(index.nodes[call+2].kind, "DeclRefExpr")
        shift = len(index.nodes) - call
        copied_call = len(index.nodes)
        for current in range(call, call+3):
            node = index.nodes[current]
            index.nodes.append(replace(node, parent=body if current == call else node.parent+shift,
                                       children=[child+shift for child in node.children]))
        index.nodes[body].children.append(copied_call)
        self.assertEqual(Analyzer(index, "main").run()["reachable_definitions"], 2)
        cyclic = dump.replace(f"FunctionDecl {function} ", f"FunctionDecl {function} prev {function} ", 1)
        with self.assertRaisesRegex(AnalysisError, "Cyclic"):
            DumpIndex(cyclic)

    def test_budgets_missing_entry_and_malformed_tree(self):
        dump = self.compile("float F(){return 1;}" + ENTRY + "return F();}")
        for options in ({"max_nodes": 2}, {"max_depth": 1}, {"max_definitions": 1}):
            with self.subTest(options=options), self.assertRaises(AnalysisError):
                DumpIndex(dump, **options)
        with self.assertRaises(AnalysisError):
            Analyzer(DumpIndex(dump), "missing")
        with self.assertRaises(AnalysisError):
            Analyzer(DumpIndex(dump), "main", max_edges=0).run()
        with self.assertRaises(AnalysisError):
            DumpIndex("TranslationUnitDecl 0x1 <<invalid sloc>>\n|     `-NullStmt 0x2 <col:1>\n")

    def test_missing_declaration_signature_writes_error(self):
        dump = "TranslationUnitDecl 0x1 <<invalid sloc>> <invalid sloc>\n`-FunctionDecl 0x2 <col:1> main\n  `-CompoundStmt 0x3 <col:2>\n"
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            base = Path(directory)
            ast = base / "input.ast"
            ast.write_text(dump, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = main(["--ast", str(ast), "--entry", "main", "--output", str(base / "report")])
            report = json.loads((base / "report/result.json").read_text(encoding="utf-8"))
            self.assertEqual(result, 1)
            self.assertEqual((report["status"], report["code"]), ("ERROR", "INVALID_DECLARATION"))

    def test_cli_exit_codes_provenance_and_stale_success(self):
        dump = self.compile(ENTRY + "return 1;}")
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            base = Path(directory)
            ast = base / "input.ast"
            ast.write_bytes(dump.encode("utf-8"))
            arguments = ["--ast", str(ast), "--entry", "main", "--output", str(base / "report")]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(arguments), 0)
                self.assertFalse(json.loads((base / "report/result.json").read_text(encoding="utf-8"))["provenance"]["verified"])
                ast.write_bytes(dump.replace("IntegerLiteral", "CXXConstructExpr").encode("utf-8"))
                self.assertEqual(main(arguments), 2)
                ast.write_text("broken", encoding="utf-8")
                self.assertEqual(main(arguments), 1)
            self.assertEqual(json.loads((base / "report/result.json").read_text(encoding="utf-8"))["status"], "ERROR")
            ast.write_bytes(dump.encode("utf-8"))
            preprocessed = b"fixture preprocessed bytes"
            (base / "Forward.preprocessed.hlsl").write_bytes(preprocessed)
            manifest = {"status":"INVESTIGATED", "preprocess_status":"PREPROCESSED", "ast_probe_status":"PARSED",
                        "ast_sha256":hashlib.sha256(ast.read_bytes()).hexdigest(), "ast_bytes":ast.stat().st_size,
                        "preprocessed_sha256":hashlib.sha256(preprocessed).hexdigest(), "package":{}, "defines":{}}
            inventory = base / "inventory.json"
            inventory.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertTrue(provenance(ast.read_bytes(), inventory)["verified"])
            (base / "Forward.preprocessed.hlsl").write_bytes(b"changed")
            with self.assertRaises(AnalysisError):
                provenance(ast.read_bytes(), inventory)

    def test_non_object_inventory_has_error_report_and_exit_one(self):
        dump = self.compile(ENTRY + "return 1;}")
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            base = Path(directory)
            ast = base / "input.ast"
            ast.write_text(dump, encoding="utf-8")
            inventory = base / "inventory.json"
            arguments = ["--ast", str(ast), "--entry", "main", "--inventory", str(inventory), "--output", str(base / "report")]
            for data in ([], None, 1, "text"):
                inventory.write_text(json.dumps(data), encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(arguments), 1)
                report = json.loads((base / "report/result.json").read_text(encoding="utf-8"))
                self.assertEqual((report["status"], report["code"]), ("ERROR", "INPUT_MISMATCH"))

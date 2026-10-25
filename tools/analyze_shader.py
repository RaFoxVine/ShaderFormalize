"""Inspect a DXC AST dump without importing shader semantics or running Unity/Lean."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from dxc_ast_index import AnalysisError, Analyzer, DumpIndex


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_report(path, value):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def provenance(ast_bytes, inventory_path):
    if inventory_path is None:
        return {"verified": False, "scope": "AST bytes only; Unity source provenance not verified"}
    raw = inventory_path.read_bytes()
    inventory = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(inventory, dict):
        raise AnalysisError("INPUT_MISMATCH", "Inventory must be a JSON object")
    if (inventory.get("status") != "INVESTIGATED" or inventory.get("preprocess_status") != "PREPROCESSED"
            or inventory.get("ast_probe_status") != "PARSED" or inventory.get("ast_sha256") != sha(ast_bytes)
            or inventory.get("ast_bytes") != len(ast_bytes)):
        raise AnalysisError("INPUT_MISMATCH", "Inventory status or AST hash/size does not match")
    if not isinstance(inventory.get("package"), dict) or not isinstance(inventory.get("defines"), dict):
        raise AnalysisError("INPUT_MISMATCH", "Inventory package/defines must be JSON objects")
    preprocessed = inventory_path.parent / "Forward.preprocessed.hlsl"
    if sha(preprocessed.read_bytes()) != inventory.get("preprocessed_sha256"):
        raise AnalysisError("INPUT_MISMATCH", "Preprocessed artifact hash does not match inventory")
    return {"verified": True, "scope": "AST and preprocessed artifacts match supplied inventory; external source files were not reopened",
            "inventory_sha256": sha(raw), "package": inventory["package"], "defines": inventory["defines"],
            "preprocessed_sha256": inventory["preprocessed_sha256"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ast", required=True, type=Path)
    parser.add_argument("--entry", required=True)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    target = args.output / "result.json"
    try:
        args.output.mkdir(parents=True, exist_ok=True)
        write_report(target, {"status": "IN_PROGRESS", "schema": 1})
        if args.ast.stat().st_size > 32 * 1024 * 1024:
            raise AnalysisError("BUDGET_EXCEEDED", "AST exceeds 32 MiB")
        raw = args.ast.read_bytes()
        if len(raw) > 32 * 1024 * 1024:
            raise AnalysisError("BUDGET_EXCEEDED", "AST exceeds 32 MiB")
        origin = provenance(raw, args.inventory)
        report = Analyzer(DumpIndex(raw.decode("utf-8-sig")), args.entry).run()
        report.update(ast_sha256=sha(raw), ast_bytes=len(raw), provenance=origin)
        write_report(target, report)
        print(json.dumps({key: report[key] for key in ("status", "definition_count", "reachable_definitions", "ast_nodes")}, indent=2))
        return 0 if report["status"] == "ANALYZED" else 2
    except (AnalysisError, OSError, UnicodeError, ValueError, KeyError) as error:
        code = error.code if isinstance(error, AnalysisError) else "INPUT_ERROR"
        report = {"status": "ERROR", "schema": 1, "code": code, "message": str(error)}
        try:
            write_report(target, report)
        except OSError as output_error:
            print(f"Cannot save analysis report: {output_error}", file=sys.stderr)
        print(json.dumps(report), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

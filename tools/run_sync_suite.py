"""Run the HLSL synchronization unit and real external-verifier controls."""
import json
from pathlib import Path
import re
import sys

from shaderformalize import ROOT, local_environment, read_json, write_json
from shader_ast import ModelError
from syncformalize import run_process


DIRECTORY = ROOT / "artifacts" / "synchronization-hlsl" / "acceptance"


def run(arguments, log):
    return run_process(arguments, log, local_environment(), 900)


def run_suite():
    directory = DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "result.json", {"status": "IN_PROGRESS", "kind": "EXTERNAL_VERIFIER"})
    units = run([sys.executable, "-m", "unittest", "discover", "-s", "tools", "-p", "test_sync.py"], directory / "unit.log")
    if units.returncode:
        write_json(directory / "result.json", {"status": "FAILED", "message": "Synchronization unit regressions failed"})
        return 1
    base = ROOT / "examples" / "synchronization-hlsl"
    cases = [
        {"name": "original", "source": "original.hlsl", "expected": "EXTERNAL_SAFETY_VERIFIED"},
        {"name": "missing-barrier", "source": "missing-barrier.hlsl", "expected": "EXTERNAL_SAFETY_UNPROVED", "marker": "insufficient permission"},
        {"name": "shared-conflict", "source": "shared-conflict.hlsl", "expected": "EXTERNAL_SAFETY_UNPROVED", "marker": "insufficient permission"},
        {"name": "out-of-bounds", "source": "out-of-bounds.hlsl", "expected": "EXTERNAL_SAFETY_UNPROVED", "marker": "#arraybounds"},
        {"name": "aliased-contract", "source": "original.hlsl", "constraints": "aliased-constraints.json", "expected": "UNSUPPORTED"},
    ]
    reports = []
    for case in cases:
        case_directory = directory / case["name"]
        proof_directory = case_directory / "proof"
        proof_directory.mkdir(parents=True, exist_ok=True)
        constraints = base / case.get("constraints", "constraints.json")
        command = [sys.executable, ROOT / "tools" / "syncformalize.py", "check", "--original", base / case["source"],
                   "--constraints", constraints, "--output", proof_directory]
        result = run(command, case_directory / "command.log")
        report = read_json(proof_directory / "result.json")
        matches = report["status"] == case["expected"] and result.returncode == (0 if case["expected"] == "EXTERNAL_SAFETY_VERIFIED" else 1)
        if case["expected"] == "EXTERNAL_SAFETY_UNPROVED":
            log = (proof_directory / "vercors.log").read_text(encoding="utf-8")
            matches = matches and case["marker"] in log.lower()
        reports.append({"case": case["name"], "expected": case["expected"], "actual": report["status"],
                        "matches": matches, "report": str(proof_directory / "result.json")})
        print(case["name"] + ": " + report["status"] + (" (expected)" if matches else " (UNEXPECTED)"), flush=True)
        if not matches:
            break
    unit_count = re.search(r"Ran ([0-9]+) tests?", units.stdout + units.stderr)
    passed = len(reports) == len(cases) and all(item["matches"] for item in reports)
    summary = {"status": "PASSED" if passed else "FAILED", "kind": "EXTERNAL_VERIFIER",
               "unit_tests": int(unit_count.group(1)) if unit_count else None, "controls": reports,
               "scope": "two-lane HLSL access safety through DXC and VerCors; not Lean or value equivalence"}
    write_json(directory / "result.json", summary)
    print("SYNCHRONIZATION_HLSL_" + summary["status"])
    return 0 if passed else 1


def main():
    try:
        return run_suite()
    except ModelError as error:
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        write_json(DIRECTORY / "result.json", {"status": error.status, "kind": "EXTERNAL_VERIFIER",
                                                "message": str(error)})
        print("SYNCHRONIZATION_HLSL_" + error.status + ": " + str(error))
        return 2


if __name__ == "__main__":
    sys.exit(main())

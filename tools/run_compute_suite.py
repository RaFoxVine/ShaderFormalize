"""Run the independent experimental Compute regression and formal controls."""
import json
from pathlib import Path
import re
import subprocess
import sys

from shaderformalize import ROOT, local_environment, read_json, write_json


def run(arguments, log):
    result = subprocess.run([str(arg) for arg in arguments], cwd=ROOT, env=local_environment(),
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    log.write_text(result.stdout + "\n--- stderr ---\n" + result.stderr, encoding="utf-8")
    return result


def main():
    directory = ROOT / "artifacts/compute/acceptance"
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "result.json", {"status": "IN_PROGRESS", "scope": "experimental Compute"})
    units = run([sys.executable, "-m", "unittest", "discover", "-s", "tools", "-p", "test_compute.py"], directory / "unit.log")
    if units.returncode:
        write_json(directory / "result.json", {"status": "FAILED", "message": "Compute unit regressions failed"})
        print("COMPUTE_FAILED: unit regressions; see artifacts/compute/acceptance/unit.log")
        return 1
    cases = read_json(ROOT / "examples/compute/controls.json")["cases"]
    reports = []
    for case in cases:
        name, expected = case["name"], case["expected"]
        case_directory = directory / name
        case_directory.mkdir(exist_ok=True)
        command = [sys.executable, ROOT / "tools/computeformalize.py", "check", "--original", ROOT / case["original"],
                   "--optimized", ROOT / case["optimized"], "--constraints", ROOT / case["constraints"],
                   "--agent-proof", ROOT / case["proof"], "--output", case_directory / "proof"]
        result = run(command, case_directory / "command.log")
        report = read_json(case_directory / "proof/result.json")
        matches = report["status"] == expected
        if expected == "UNPROVED":
            # A generator/type error is not evidence that the intended false
            # target was checked and refused by the supplied agent proof.
            matches = matches and "lean-SubmittedProof.log" in report.get("message", "")
        matches = matches and result.returncode == (0 if expected == "PROVED" else 1)
        reports.append({"case": name, "expected": expected, "actual": report["status"], "matches": matches,
                        "report": str(case_directory / "proof/result.json")})
        print(name + ": " + report["status"] + (" (expected)" if matches else " (UNEXPECTED)"), flush=True)
        if not matches:
            break
    passed = len(reports) == len(cases) and all(item["matches"] for item in reports)
    unit_count = re.search(r"Ran ([0-9]+) tests?", units.stdout + units.stderr)
    summary = {"status": "PASSED" if passed else "FAILED", "unit_tests": int(unit_count.group(1)) if unit_count else None, "controls": reports,
               "scope": "experimental ideal-real Compute buffers; no Unity or IEEE hardware claim"}
    write_json(directory / "result.json", summary)
    print("COMPUTE_" + summary["status"])
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

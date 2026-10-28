"""Run independent IEEE unit, formal, negative, and legacy-core controls."""
import json
from pathlib import Path
import re
import subprocess
import sys

import ieeeformalize
from ieeeformalize import ROOT
from shaderformalize import local_environment as core_environment, read_json, write_json


DIRECTORY = ROOT / "artifacts/ieee-hlsl/acceptance"


def run(arguments, log, environment, timeout=3600):
    command = [str(argument) for argument in arguments]
    process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
        stdout, stderr = process.communicate()
    if timed_out:
        stderr += "\nIEEE_SUITE_TIMEOUT: process tree terminated\n"
    result = subprocess.CompletedProcess(command, 124 if timed_out else process.returncode, stdout, stderr)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout + "\n--- stderr ---\n" + result.stderr, encoding="utf-8")
    return result


def main():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    write_json(DIRECTORY / "result.json", {"status": "IN_PROGRESS", "scope": "independent IEEE HLSL"})
    ieee_environment = ieeeformalize.local_environment()
    units = run([sys.executable, "-m", "unittest", "discover", "-s", "tools", "-p", "test_ieee.py"],
                DIRECTORY / "unit.log", ieee_environment)
    if units.returncode:
        write_json(DIRECTORY / "result.json", {"status": "FAILED", "message": "IEEE unit controls failed"})
        print("IEEE_SUITE_FAILED: unit controls; see artifacts/ieee-hlsl/acceptance/unit.log")
        return 1
    reports = []
    cases = read_json(ROOT / "examples/ieee/controls.json")["cases"]
    for case in cases:
        name, expected = case["name"], case["expected"]
        case_directory = DIRECTORY / name
        case_directory.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, ROOT / "tools/ieeeformalize.py", "check",
                   "--original", ROOT / case["original"], "--optimized", ROOT / case["optimized"],
                   "--constraints", ROOT / "examples/ieee/constraints.json",
                   "--agent-proof", ROOT / case["proof"], "--output", case_directory / "proof"]
        result = run(command, case_directory / "command.log", ieee_environment)
        report = read_json(case_directory / "proof/result.json")
        matches = report["status"] == expected
        if "message" in case:
            matches = matches and case["message"] in report.get("message", "")
        matches = matches and result.returncode == (0 if expected == "IEEE_PROVED" else 1)
        if expected == "IEEE_PROVED":
            matches = matches and report.get("gpu_profile_matched") is False and set(report.get("axioms", [])) <= {
                "propext", "Classical.choice", "Quot.sound"}
        reports.append({"case": name, "expected": expected, "actual": report["status"], "matches": matches,
                        "report": str(case_directory / "proof/result.json")})
        print(name + ": " + report["status"] + (" (expected)" if matches else " (UNEXPECTED)"), flush=True)
        if not matches:
            break
    passed = len(reports) == len(cases) and all(item["matches"] for item in reports)
    core = None
    if passed:
        core = run([sys.executable, ROOT / "tools/shaderformalize.py", "check",
                    "--output", DIRECTORY / "legacy-core"], DIRECTORY / "legacy-core.log", core_environment())
        core_report = read_json(DIRECTORY / "legacy-core/result.json")
        passed = core.returncode == 0 and core_report.get("status") == "PROVED"
    unit_count = re.search(r"Ran ([0-9]+) tests?", units.stdout + units.stderr)
    summary = {
        "status": "IEEE_SUITE_PASSED" if passed else "FAILED",
        "unit_tests": int(unit_count.group(1)) if unit_count else None,
        "controls": reports,
        "legacy_core": None if core is None else read_json(DIRECTORY / "legacy-core/result.json"),
        "profile": ieeeformalize.PROFILE,
        "gpu_profile_matched": False,
        "scope": "restricted HLSL to FloatLib binary32; no GPU implementation match claim",
    }
    write_json(DIRECTORY / "result.json", summary)
    print("IEEE_SUITE_PASSED" if passed else "IEEE_SUITE_FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

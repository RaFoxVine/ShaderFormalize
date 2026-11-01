"""Serial actual-HLSL acceptance. Every report belongs to the invoked run."""
import json
from pathlib import Path
import re
import sys

from shaderformalize import ROOT, read_json, write_json, run_tool
from shader_ast import ModelError


def read_run_result(process, container):
    envelope = json.loads(process.stdout.strip().splitlines()[-1])
    run_id = envelope.get("run_id", "")
    if not re.fullmatch("[0-9a-f]{32}", run_id):
        raise ValueError("Invalid current run identity")
    expected = Path(container).resolve() / run_id / "result.json"
    if Path(envelope.get("result_path", "")).resolve() != expected:
        raise ValueError("Current result path mismatch")
    report = read_json(expected)
    if (report.get("run_id") != run_id or report.get("result_path") != str(expected)
            or report.get("status") != envelope.get("status")):
        raise ValueError("Current result identity/status mismatch")
    expected_exit = 0 if report["status"] in ("PREPARED", "PROVED") else 1
    if process.returncode != expected_exit:
        raise ValueError("Exit/result mismatch")
    return report


def standard_axiom_audit(log, theorem):
    """Require the actual Lean audit for this declaration and exclude extra axioms."""
    audit = re.search(re.escape(theorem) + r"' depends on axioms:\s*\[([^]]*)\]", log)
    allowed = {"propext", "Classical.choice", "Quot.sound"}
    if audit:
        return {name.strip() for name in audit[1].split(",")} <= allowed
    return theorem + "' does not depend on any axioms" in log


def main(names=None, directory=None):
    directory = Path(directory) if directory else ROOT / "artifacts/compute-uint/acceptance"
    directory.mkdir(parents=True, exist_ok=True)
    cases = read_json(ROOT / "examples/compute-uint/controls.json")["cases"]
    if names is not None:
        cases = [case for case in cases if case["name"] in names]
        if {case["name"] for case in cases} != set(names):
            raise ValueError("Unknown acceptance case")
    reports = []
    write_json(directory / "result.json", {"status": "IN_PROGRESS"})
    for case in cases:
        output = directory / case["name"]
        script = ROOT / "tools/computeformalize.py"
        command = [sys.executable, "-X", "utf8", str(script)]
        if case.get("tamper"):
            command = [sys.executable, "-X", "utf8", str(ROOT / "tools/compute_uint_tamper_fixture.py"), case["tamper"]]
        command += ["check", "--model", "uint32-buffer",
                    "--original", str(ROOT / case["original"]),
                    "--optimized", str(ROOT / case["optimized"]),
                    "--constraints", str(ROOT / case["constraints"]),
                    "--agent-proof", str(ROOT / case["proof"]), "--output", str(output)]
        try:
            process, _ = run_tool(command, ROOT, directory / (case["name"] + ".command.log"), timeout=1800)
            report = read_run_result(process, output)
        except (ModelError, OSError, ValueError, KeyError, IndexError) as error:
            reports.append({"case": case["name"], "matches": False, "error": str(error)})
            break
        # The CLI owns this directory; runner logs use the current identity too.
        run_directory = Path(report["result_path"]).parent
        (run_directory / "command.log").write_text(process.stdout + "\n--- stderr ---\n" + process.stderr, encoding="utf-8")
        match = report["status"] == case["expected"]
        if case["expected"] == "UNPROVED":
            reason = case.get("failure_reason", "lean-ShaderComputeUint-SubmittedProof.log")
            match = match and reason in report.get("message", "")
        if case.get("isolation"):
            log = (run_directory / "lean-ShaderComputeUint-SubmittedProof.log").read_text(encoding="utf-8")
            isolated = standard_axiom_audit(log, "conditions")
            report["isolation_proved"] = isolated
            match = match and isolated
            if case.get("residual_goal"):
                match = match and case["residual_goal"] in log
        if case.get("observability"):
            log = (run_directory / "lean-ShaderComputeUint-SubmittedProof.log").read_text(encoding="utf-8")
            audits = {name: standard_axiom_audit(log, name) for name in case["observability"]}
            report["observability_audits"] = audits
            match = match and all(audits.values())
        reports.append({"case": case["name"], "matches": match, "report": report})
        print(case["name"] + ": " + report["status"], flush=True)
        if not match:
            break
    passed = len(reports) == len(cases) and all(item["matches"] for item in reports)
    write_json(directory / "result.json", {"status": "PASSED" if passed else "FAILED", "controls": reports})
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

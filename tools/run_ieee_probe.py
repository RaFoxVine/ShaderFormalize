"""Run the FloatLib probe inside the shared repository Lake workspace."""
import json
import re
import sys

from ieeeformalize import run_lean, validate_lean
from shaderformalize import ROOT, PROOF, ModelError, workspace_lock, sha256, write_json, write_text


def main():
    output = ROOT / "artifacts/ieee"
    output.mkdir(parents=True, exist_ok=True)
    report = output / "result.json"
    log = output / "probe.log"
    try:
        with workspace_lock():
            write_json(report, {"schema": 1, "status": "IN_PROGRESS"})
            write_text(log, "IN_PROGRESS\n")
            try:
                validate_lean()
                result, _ = run_lean(["--run", "ShaderIeee/Probe.lean"], PROOF, log, 900)
                if result.returncode or "IEEE_PROTOTYPE_PASSED" not in result.stdout.splitlines():
                    raise ModelError("IEEE probe failed; see artifacts/ieee/probe.log", "UNPROVED")
                version, _ = run_lean(["--version"], PROOF, output / "lean-version.log")
                if version.returncode:
                    raise ModelError("Cannot read shared Lean version", "ENVIRONMENT_ERROR")
                summary = {
                    "schema": 1, "status": "EXTERNAL_LIBRARY_PROTOTYPE_PASSED", "exit_code": 0,
                    "command": "lake env lean --run ShaderIeee/Probe.lean", "lean_version": version.stdout.strip(),
                    "shader_cli_ieee_integrated": True, "checks_passed": len(re.findall(r"^PASS ", result.stdout, re.MULTILINE)),
                    "main_sha256": sha256(PROOF / "ShaderIeee/Probe.lean"),
                    "lake_manifest_sha256": sha256(PROOF / "lake-manifest.json"),
                    "dependency_lock_sha256": sha256(ROOT / "dependencies.lock.json"), "log_sha256": sha256(log),
                    "interpretation": "FloatLib binary32 reference operations, nearest ties-to-even; GPU profile not matched",
                }
            except (ModelError, OSError, ValueError) as error:
                message = (error.status + ": " if isinstance(error, ModelError) else "") + str(error)
                summary = {"schema": 1, "status": "FAILED", "message": message, "exit_code": 1}
            write_json(report, summary)
    except ModelError as error:
        summary = {"schema": 1, "status": error.status, "message": str(error), "exit_code": 1}
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "EXTERNAL_LIBRARY_PROTOTYPE_PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())

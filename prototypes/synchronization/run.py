"""Run small parallel and barrier examples with the pinned external VerCors."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def java_environment(java_home):
    environment = os.environ.copy()
    if java_home:
        selected = Path(java_home).resolve()
    elif environment.get("JAVA_HOME"):
        selected = Path(environment["JAVA_HOME"])
    else:
        command = shutil.which("java")
        if command is None:
            raise RuntimeError("Java 17+ is required; supply --java-home or run bootstrap.ps1.")
        selected = Path(command).resolve().parent.parent
    java = selected / "bin/java.exe"
    result = subprocess.run([str(java), "-version"], capture_output=True, text=True, timeout=30)
    version = result.stdout + result.stderr
    match = re.search(r'version "(\d+)', version)
    if result.returncode or match is None or int(match.group(1)) < 17:
        raise RuntimeError("The selected Java runtime must be version 17 or later.")
    environment["JAVA_HOME"] = str(selected)
    environment["PATH"] = str(java.parent) + os.pathsep + environment.get("PATH", "")
    return environment, version.strip()


def find_launcher():
    path = ROOT / ".tools/vercors-2.4.0/vercors.bat"
    if path.is_file():
        return path
    raise RuntimeError("Pinned VerCors is missing; run prototypes/synchronization/bootstrap.ps1.")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check_case(name, source, expected, launcher, environment, output, timeout):
    case_source = output / (name + ".pvl")
    case_source.write_text(source, encoding="utf-8")
    command = [str(launcher), "--backend", "silicon", str(case_source)]
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=timeout)
    log = result.stdout + "\n--- stderr ---\n" + result.stderr
    log_path = output / (name + ".log")
    log_path.write_text(log, encoding="utf-8")
    success = result.returncode == 0 and "Verification completed successfully" in log
    permission_failure = result.returncode != 0 and re.search(r"insufficient\s+permission", log, re.IGNORECASE)
    matches = success if expected == "VERIFIED" else bool(permission_failure)
    return {
        "case": name, "expected": expected,
        "actual": "VERIFIED" if success else "PERMISSION_REJECTED" if permission_failure else "UNEXPECTED_RESULT",
        "matched": matches, "exit_code": result.returncode,
        "seconds": round(time.monotonic() - started, 3),
        "source_sha256": sha256(case_source), "log_sha256": sha256(log_path),
        "command": command,
    }


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    environment, java_version = java_environment(args.java_home)
    launcher = find_launcher()
    lock_path = HERE / "dependencies.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    archive = ROOT / ".cache/downloads/vercors-2.4.0-win.zip"
    if not archive.is_file() or sha256(archive) != lock["vercors"]["sha256"]:
        raise RuntimeError("Pinned VerCors archive is missing or its checksum changed.")
    parallel = (HERE / "ParallelAdd.pvl").read_text(encoding="utf-8")
    barrier = (HERE / "SharedExchange.pvl").read_text(encoding="utf-8")
    # These mutations keep the parser input valid, while breaking access permissions.
    collision = parallel.replace("output[tid] = a[tid] + b[tid];", "output[0] = a[tid] + b[tid];")
    barrier_start = barrier.index("      barrier(lanes)")
    barrier_end = barrier.index("      output[tid]", barrier_start)
    missing_barrier = barrier[:barrier_start] + barrier[barrier_end:]
    cases = [("parallel-add", parallel, "VERIFIED"),
             ("parallel-conflict", collision, "PERMISSION_REJECTED"),
             ("shared-exchange", barrier, "VERIFIED"),
             ("missing-barrier", missing_barrier, "PERMISSION_REJECTED")]
    report = {"status": "IN_PROGRESS", "verifier": "VerCors 2.4.0", "kind": "EXTERNAL_VERIFIER",
              "scope": "PVL parallel/permission/barrier examples; not HLSL import or Lean proof",
              "java_version": java_version, "dependency_lock_sha256": sha256(lock_path),
              "launcher_sha256": sha256(launcher), "cases": []}
    write_json(output / "result.json", report)
    for name, source, expected in cases:
        report["cases"].append(check_case(name, source, expected, launcher, environment, output, args.timeout))
        write_json(output / "result.json", report)
        print(name + ": " + report["cases"][-1]["actual"], flush=True)
    report["status"] = "PASSED" if all(case["matched"] for case in report["cases"]) else "FAILED"
    write_json(output / "result.json", report)
    return 0 if report["status"] == "PASSED" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-home")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/synchronization")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output / "result.json", {"status": "IN_PROGRESS", "kind": "EXTERNAL_VERIFIER"})
    try:
        return run(args)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        args.output.mkdir(parents=True, exist_ok=True)
        write_json(args.output / "result.json", {"status": "ENVIRONMENT_ERROR", "message": str(error),
                                                "kind": "EXTERNAL_VERIFIER"})
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

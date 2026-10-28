"""Check the restricted two-lane HLSL synchronization subset with pinned VerCors."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile

from shader_ast import ModelError, validate_source
from shader_sync import generate_pvl, import_sync, sync_contract
from shaderformalize import ROOT, read_json, run_tool, sha256, validate_dxc, write_json, write_text


@contextmanager
def synchronization_lock():
    import msvcrt
    path = ROOT / ".cache" / "synchronization-hlsl-verification.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise ModelError("Another synchronization check owns the workspace", "INCONCLUSIVE") from error
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def java_environment(java_home=None):
    environment = os.environ.copy()
    if java_home:
        selected = Path(java_home).resolve()
    elif environment.get("JAVA_HOME"):
        selected = Path(environment["JAVA_HOME"])
    else:
        command = shutil.which("java")
        if command is None:
            raise ModelError("Java 17+ is required for VerCors", "ENVIRONMENT_ERROR")
        selected = Path(command).resolve().parent.parent
    java = selected / "bin" / "java.exe"
    try:
        result = subprocess.run([str(java), "-version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ModelError(f"Cannot start the selected Java runtime: {error}", "ENVIRONMENT_ERROR") from error
    version = result.stdout + result.stderr
    match = re.search(r'version "(\d+)', version)
    if result.returncode or match is None or int(match.group(1)) < 17:
        raise ModelError("The selected Java runtime must be version 17 or later", "ENVIRONMENT_ERROR")
    environment["JAVA_HOME"] = str(selected)
    environment["PATH"] = str(java.parent) + os.pathsep + environment.get("PATH", "")
    return environment, version.strip()


def stream_sha256(stream):
    digest = hashlib.sha256()
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def validate_vercors_payload(installation, archive):
    with zipfile.ZipFile(archive) as bundle:
        entries = [entry for entry in bundle.infolist() if not entry.is_dir()]
        expected = {entry.filename for entry in entries}
        actual = {path.relative_to(installation).as_posix() for path in installation.rglob("*") if path.is_file()}
        if actual != expected:
            raise ModelError("Installed VerCors payload differs from the locked archive", "ENVIRONMENT_ERROR")
        for entry in entries:
            path = installation.joinpath(*entry.filename.split("/"))
            if not path.is_file() or path.stat().st_size != entry.file_size:
                raise ModelError(f"Installed VerCors file missing/changed: {entry.filename}", "ENVIRONMENT_ERROR")
            with bundle.open(entry) as source, path.open("rb") as installed:
                if stream_sha256(source) != stream_sha256(installed):
                    raise ModelError(f"Installed VerCors file missing/changed: {entry.filename}", "ENVIRONMENT_ERROR")
    return len(entries)


def validate_vercors():
    lock_path = ROOT / "prototypes" / "synchronization" / "dependencies.lock.json"
    lock = read_json(lock_path)
    installation = ROOT / ".tools" / "vercors-2.4.0"
    launcher = installation / "vercors.bat"
    archive = ROOT / ".cache" / "downloads" / "vercors-2.4.0-win.zip"
    if not launcher.is_file() or not archive.is_file() or sha256(archive) != lock["vercors"]["sha256"]:
        raise ModelError("Pinned VerCors installation/archive is missing or changed", "ENVIRONMENT_ERROR")
    validate_vercors_payload(installation, archive)
    return lock_path, launcher


def prepare(args, output):
    dxc = validate_dxc()
    source_path = Path(args.original).resolve()
    source_bytes = source_path.read_bytes()
    source = source_bytes.decode("utf-8-sig")
    validate_source(source)
    snapshot = output / "original.hlsl"
    snapshot.write_bytes(source_bytes)
    result, seconds = run_tool([dxc, "-T", "cs_6_0", "-E", "main", "-HV", "2021", "-ast-dump", snapshot],
                               output, output / "original.dxc.log")
    if result.returncode:
        raise ModelError(f"DXC rejected the synchronization source (exit {result.returncode}); see its log", "INVALID_INPUT")
    model = import_sync(source, result.stdout)
    contract = sync_contract(read_json(args.constraints), model)
    pvl = generate_pvl(model)
    write_json(output / "original.model.json", model)
    write_text(output / "Generated.pvl", pvl)
    return {
        "status": "PREPARED", "model_schema": model["schema"],
        "source": {"path": str(source_path), "sha256": sha256(snapshot), "dxc_seconds": seconds},
        "constraints": contract, "constraints_sha256": sha256(args.constraints),
        "ast_sha256": sha256(output / "original.dxc.log"), "pvl_sha256": sha256(output / "Generated.pvl"),
        "dxc_files": read_json(ROOT / "dependencies.lock.json")["dxc"]["binaries"],
        "scope": "two-lane access bounds, permissions and one real barrier; no value equivalence or Lean theorem",
    }


def run_process(command, log, environment, timeout, cwd=ROOT):
    """Stop the whole Windows process tree on timeout and preserve tool output."""
    command = [str(argument) for argument in command]
    try:
        process = subprocess.Popen(command, cwd=cwd, env=environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    except OSError as error:
        raise ModelError(f"Cannot start synchronization tool: {error}", "ENVIRONMENT_ERROR") from error
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        try:
            stopped = subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                                     capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
            stdout, stderr = process.communicate(timeout=15)
        except (OSError, subprocess.TimeoutExpired) as cleanup_error:
            if process.poll() is None:
                process.kill()
            process.stdout.close()
            process.stderr.close()
            write_text(log, f"Synchronization timeout; process-tree cleanup failed: {cleanup_error}\n")
            raise ModelError("Synchronization timeout cleanup failed; see tool log", "ENVIRONMENT_ERROR") from cleanup_error
        if stopped.returncode:
            write_text(log, stdout + "\n--- stderr ---\n" + stderr + "\n" + stopped.stdout + stopped.stderr)
            raise ModelError("Synchronization timeout cleanup was not confirmed; see tool log", "ENVIRONMENT_ERROR") from error
        write_text(log, stdout + "\n--- stderr ---\n" + stderr + "\nSYNCHRONIZATION_TIMEOUT: process tree terminated\n")
        raise ModelError("Synchronization tool timed out; its process tree was stopped", "INCONCLUSIVE") from error
    write_text(log, stdout + "\n--- stderr ---\n" + stderr)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def check(args, output):
    summary = prepare(args, output)
    lock_path, launcher = validate_vercors()
    environment, java_version = java_environment(args.java_home)
    command = [str(launcher), "--backend", "silicon", str(output / "Generated.pvl")]
    started = time.monotonic()
    result = run_process(command, output / "vercors.log", environment, args.timeout)
    log = result.stdout + "\n--- stderr ---\n" + result.stderr
    summary.update({
        "verifier": "VerCors 2.4.0", "kind": "EXTERNAL_VERIFIER", "java_version": java_version,
        "command": command, "exit_code": result.returncode, "seconds": round(time.monotonic() - started, 3),
        "vercors_lock_sha256": sha256(lock_path), "launcher_sha256": sha256(launcher),
        "vercors_log_sha256": sha256(output / "vercors.log"),
    })
    if result.returncode == 0 and "Verification completed successfully" in log:
        summary["status"] = "EXTERNAL_SAFETY_VERIFIED"
        return summary
    safety_diagnostics = ("insufficient permission", "verification failed", "#arraybounds", "index may be negative")
    if result.returncode != 0 and any(diagnostic in log.lower() for diagnostic in safety_diagnostics):
        summary["status"] = "EXTERNAL_SAFETY_UNPROVED"
        summary["message"] = "VerCors rejected the generated access-safety model; see vercors.log"
        return summary
    raise ModelError("VerCors did not produce a recognizable safety verdict; see vercors.log", "ENVIRONMENT_ERROR")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "check"))
    parser.add_argument("--original", type=Path, default=ROOT / "examples/synchronization-hlsl/original.hlsl")
    parser.add_argument("--constraints", type=Path, default=ROOT / "examples/synchronization-hlsl/constraints.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/synchronization-hlsl/proof")
    parser.add_argument("--java-home")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    lock_acquired = False
    try:
        with synchronization_lock():
            lock_acquired = True
            write_json(output / "result.json", {"status": "IN_PROGRESS", "kind": "EXTERNAL_VERIFIER"})
            result = prepare(args, output) if args.command == "prepare" else check(args, output)
            write_json(output / "result.json", result)
    except ModelError as error:
        result = {"status": error.status, "message": str(error), "kind": "EXTERNAL_VERIFIER"}
        if error.status != "INCONCLUSIVE" or lock_acquired:
            write_json(output / "result.json", result)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        result = {"status": "INVALID_INPUT", "message": str(error), "kind": "EXTERNAL_VERIFIER"}
        write_json(output / "result.json", result)
    print(result["status"] + (": " + result["message"] if "message" in result else ""))
    if result["status"] in ("PREPARED", "EXTERNAL_SAFETY_VERIFIED"):
        return 0
    return 2 if result["status"] in ("ENVIRONMENT_ERROR", "INCONCLUSIVE") else 1


if __name__ == "__main__":
    sys.exit(main())

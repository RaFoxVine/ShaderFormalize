"""Prepare/check one restricted HLSL pair. Proof search is deliberately agent-owned."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from contextlib import contextmanager

from shader_model import ModelError, generate_lean, import_shader, constraint_spec, validate_source


ROOT = Path(__file__).resolve().parent.parent
PROOF = ROOT / "proof"


@contextmanager
def workspace_lock():
    """Generated Lean modules have one owner across all CLI output directories."""
    import msvcrt
    lock_path = ROOT / ".cache" / "verification.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise ModelError("Another verification owns the workspace", "INCONCLUSIVE") from error
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def write_json(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def local_environment():
    environment = os.environ.copy()
    lean_bin = ROOT / ".tools" / "lean-4.24.0-windows" / "bin"
    environment["PATH"] = str(lean_bin) + os.pathsep + environment.get("PATH", "")
    environment["MATHLIB_CACHE_DIR"] = str(ROOT / ".cache" / "mathlib")
    environment["LAKE_HOME"] = str(ROOT / ".cache" / "lake")
    environment["ELAN_HOME"] = str(ROOT / ".tools" / "elan")
    environment["MATHLIB_NO_CACHE_ON_UPDATE"] = "1"
    environment["CURL_HOME"] = str(ROOT / ".cache" / "curl")
    count = int(environment.get("GIT_CONFIG_COUNT", "0"))
    for key, value in (("http.sslBackend", "schannel"), ("http.version", "HTTP/1.1")):
        environment[f"GIT_CONFIG_KEY_{count}"] = key
        environment[f"GIT_CONFIG_VALUE_{count}"] = value
        count += 1
    environment["GIT_CONFIG_COUNT"] = str(count)
    return environment


def run_tool(arguments, cwd, log, timeout=180):
    started = time.monotonic()
    try:
        result = subprocess.run(
            [str(argument) for argument in arguments], cwd=cwd,
            env=local_environment(), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise ModelError(f"Tool timed out: {arguments[0]}", "INCONCLUSIVE") from error
    write_text(log, result.stdout + "\n--- stderr ---\n" + result.stderr)
    return result, round(time.monotonic() - started, 3)


def validate_dxc():
    lock = read_json(ROOT / "dependencies.lock.json")
    binaries = lock["dxc"].get("binaries", {})
    if not binaries:
        raise ModelError("Missing DXC binary lock; run bootstrap", "ENVIRONMENT_ERROR")
    for name, expected in binaries.items():
        path = ROOT / ".tools" / "dxc" / "bin" / "x64" / name
        if not path.is_file() or sha256(path) != expected:
            raise ModelError(f"Pinned DXC file missing/changed: {name}", "ENVIRONMENT_ERROR")
    return ROOT / ".tools" / "dxc" / "bin" / "x64" / "dxc.exe"


def prepare(args, output):
    dxc = validate_dxc()
    models = []
    inputs = []
    for label, filename in (("original", args.original), ("optimized", args.optimized)):
        path = Path(filename).resolve()
        source_bytes = path.read_bytes()
        source = source_bytes.decode("utf-8-sig")
        validate_source(source)
        snapshot = output / f"{label}.input.hlsl"
        snapshot.write_bytes(source_bytes)
        result, duration = run_tool(
            [dxc, "-T", "ps_6_0", "-E", "main", "-HV", "2021", "-ast-dump", snapshot],
            output, output / f"{label}.dxc.log",
        )
        if result.returncode:
            raise ModelError(f"DXC rejected {label}; see its log", "INVALID_INPUT")
        model = import_shader(source, result.stdout)
        models.append(model)
        inputs.append({"role": label, "path": str(path), "sha256": hashlib.sha256(source_bytes).hexdigest(), "dxc_seconds": duration})
        write_json(output / f"{label}.model.json", model)
    if (models[0]["interface"] != models[1]["interface"] or models[0]["buffer"] != models[1]["buffer"]
            or models[0]["output_semantic"] != models[1]["output_semantic"]
            or models[0]["entry_layout"] != models[1]["entry_layout"]):
        raise ModelError("The two source interfaces differ", "INVALID_INPUT")
    constraints = read_json(args.constraints)
    spec = constraint_spec(constraints, models[0], models[1])
    generated = generate_lean(models[0], models[1], spec=spec)
    write_text(PROOF / "GeneratedModel.lean", generated)
    write_text(output / "GeneratedModel.lean", generated)
    return {
        "status": "PREPARED", "inputs": inputs, "constraints": constraints,
        "generated_sha256": sha256(PROOF / "GeneratedModel.lean"),
        "dxc_files": read_json(ROOT / "dependencies.lock.json")["dxc"]["binaries"],
        "guarantee": "ideal real-number model of the accepted source subset; translator and DXC remain trusted",
    }


def audit_axioms(text):
    name = "ShaderFormalize.Verification.checked"
    found = re.findall(re.escape(name) + r"'? depends on axioms:\s*\[([^]]*)\]", text)
    if len(found) == 1:
        names = []
        for item in found[0].split(","):
            if item.strip():
                names.append(item.strip())
        allowed = {"propext", "Classical.choice", "Quot.sound"}
        if not set(names).issubset(allowed):
            raise ModelError(f"Proof depends on unapproved axioms: {names}", "UNPROVED")
        return names
    if name + "' does not depend on any axioms" in text or name + " does not depend on any axioms" in text:
        return []
    raise ModelError("Lean did not produce an unambiguous audit of the bound theorem", "UNPROVED")


def check(args, output):
    summary = prepare(args, output)
    lake = ROOT / ".tools" / "lean-4.24.0-windows" / "bin" / "lake.exe"
    if not lake.exists():
        raise ModelError("Local Lean/Lake missing; run tools/bootstrap.ps1", "ENVIRONMENT_ERROR")
    lock = read_json(ROOT / "dependencies.lock.json")
    for name, expected in lock["lean"]["binaries"].items():
        path = lake.parent / name
        if not path.is_file() or sha256(path) != expected:
            raise ModelError(f"Pinned Lean file missing/changed: {name}", "ENVIRONMENT_ERROR")
    version, _ = run_tool([lake.parent / "lean.exe", "--version"], PROOF, output / "lean-version.log")
    if version.returncode or "version 4.24.0," not in version.stdout:
        raise ModelError("Unexpected local Lean version", "ENVIRONMENT_ERROR")
    proof_bytes = Path(args.agent_proof).read_bytes()
    write_text(PROOF / "SubmittedProof.lean", proof_bytes.decode("utf-8-sig"))
    verify = '''import GeneratedModel
import SubmittedProof

namespace ShaderFormalize.Verification
theorem checked : ShaderFormalize.Generated.expected :=
  ShaderFormalize.AgentProof.equivalent
end ShaderFormalize.Verification

#print axioms ShaderFormalize.Verification.checked
'''
    write_text(PROOF / "Verify.lean", verify)
    result, build_seconds = run_tool([lake, "--no-cache", "build"], PROOF, output / "lean-build.log", 600)
    if result.returncode:
        raise ModelError("Agent proof did not check against the generated Shader model; see lean-build.log", "UNPROVED")
    result, verify_seconds = run_tool([lake, "env", "lean", "Verify.lean"], PROOF, output / "lean-verify.log", 180)
    if result.returncode:
        raise ModelError("The independent target-binding module failed", "UNPROVED")
    axioms = audit_axioms(result.stdout + "\n" + result.stderr)
    if sha256(PROOF / "GeneratedModel.lean") != summary["generated_sha256"]:
        raise ModelError("Generated target changed during proof checking", "UNPROVED")
    summary.update({
        "status": "PROVED", "theorem": "ShaderFormalize.Verification.checked", "axioms": axioms,
        "agent_proof_sha256": hashlib.sha256(proof_bytes).hexdigest(),
        "semantic_model_sha256": sha256(PROOF / "ShaderFormalize" / "Model.lean"),
        "lake_manifest_sha256": sha256(PROOF / "lake-manifest.json"),
        "lean_build_seconds": build_seconds, "lean_verify_seconds": verify_seconds,
        "lean_version": version.stdout.strip(),
    })
    return summary


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "check"))
    parser.add_argument("--original", default=ROOT / "examples/lerp/original.hlsl", type=Path)
    parser.add_argument("--optimized", default=ROOT / "examples/lerp/optimized.hlsl", type=Path)
    parser.add_argument("--constraints", default=ROOT / "examples/lerp/constraints.json", type=Path)
    parser.add_argument("--agent-proof", default=ROOT / "proof/AgentProof.lean", type=Path)
    parser.add_argument("--output", default=ROOT / "artifacts/current", type=Path)
    return parser.parse_args()


def main():
    args = parse_arguments()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    try:
        with workspace_lock():
            # The owner alone writes shared output, including failed reruns.
            write_json(output / "result.json", {"status": "IN_PROGRESS"})
            try:
                if args.command == "prepare":
                    summary = prepare(args, output)
                else:
                    summary = check(args, output)
            except ModelError as error:
                summary = {"status": error.status, "message": str(error)}
            except (OSError, UnicodeError, ValueError, KeyError) as error:
                summary = {"status": "INVALID_INPUT", "message": str(error)}
            write_json(output / "result.json", summary)
    except ModelError as error:
        # Do not overwrite the active owner's report if the lock is busy.
        summary = {"status": error.status, "message": str(error)}
    except (OSError, UnicodeError, ValueError, KeyError) as error:
        summary = {"status": "INVALID_INPUT", "message": str(error)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] in ("PREPARED", "PROVED") else 1


if __name__ == "__main__":
    sys.exit(main())

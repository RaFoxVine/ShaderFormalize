"""Prepare/check restricted HLSL against the independent FloatLib binary32 model."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from proof_contract import audit_axioms, verification_module
from shader_ast import ModelError
from shader_ieee_frontend import import_ieee
from shader_ieee_lean import PROFILE, empty_constraints, generate_ieee
from shaderformalize import ROOT, read_json, sha256, validate_dxc, write_json, write_text


PROTOTYPE = ROOT / "prototypes/ieee"
PROOF = PROTOTYPE / "proof"
LEAN_BIN = ROOT / ".tools/lean-4.35.0-windows/bin"
LEAN_LOCK = {
    "lean.exe": "ec7a472d1c12a09b0c0c718f7427c2be527b3f5f07810fdbe076c2507c7a91ea",
    "lake.exe": "023feb24d3e7244fe671dba79f1cd1affc6c7a7cacfe497bf3675febb506578c",
}


@contextmanager
def workspace_lock():
    import msvcrt
    lock_path = ROOT / ".cache/ieee-verification.lock"
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
            raise ModelError("Another IEEE verification owns the workspace", "INCONCLUSIVE") from error
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def local_environment():
    environment = os.environ.copy()
    for name in list(environment):
        if name.startswith("LEAN_") or name == "FLOATLIB_BUILD_DIR":
            environment.pop(name, None)
    environment["PATH"] = str(LEAN_BIN) + os.pathsep + environment.get("PATH", "")
    environment["ELAN_HOME"] = str(ROOT / ".tools/ieee-elan")
    environment["LAKE_HOME"] = str(ROOT / ".cache/ieee/lake")
    environment["MATHLIB_CACHE_DIR"] = str(ROOT / ".cache/ieee/mathlib")
    environment["MATHLIB_NO_CACHE_ON_UPDATE"] = "1"
    environment["CURL_HOME"] = str(ROOT / ".cache/ieee/curl")
    return environment


def run_tool(arguments, cwd, log, timeout=180):
    started = time.monotonic()
    command = [str(argument) for argument in arguments]
    process = subprocess.Popen(command, cwd=cwd, env=local_environment(), stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
        stdout, stderr = process.communicate()
        write_text(log, stdout + "\n--- stderr ---\n" + stderr)
        raise ModelError(f"Tool timed out and its process tree was stopped: {arguments[0]}",
                         "INCONCLUSIVE") from error
    write_text(log, stdout + "\n--- stderr ---\n" + stderr)
    result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    return result, round(time.monotonic() - started, 3)


def validate_lean():
    for name, expected in LEAN_LOCK.items():
        path = LEAN_BIN / name
        if not path.is_file() or sha256(path) != expected:
            raise ModelError(f"Pinned IEEE Lean file missing/changed: {name}", "ENVIRONMENT_ERROR")
    return LEAN_BIN / "lake.exe"


def run_lean(arguments, cwd, log, timeout=180):
    lake = validate_lean()
    return run_tool([lake, "--dir", PROTOTYPE, "env", "lean"] + list(arguments), cwd, log, timeout)


def prepare(args, output):
    dxc = validate_dxc()
    models = []
    inputs = []
    for role, filename in (("original", args.original), ("optimized", args.optimized)):
        source_path = Path(filename).resolve()
        source_bytes = source_path.read_bytes()
        source = source_bytes.decode("utf-8-sig")
        snapshot = output / f"{role}.input.hlsl"
        snapshot.write_bytes(source_bytes)
        result, seconds = run_tool([dxc, "-T", "ps_6_0", "-E", "main", "-HV", "2021", "-ast-dump", snapshot],
                                   output, output / f"{role}.dxc.log")
        if result.returncode:
            raise ModelError(f"DXC rejected {role}; see its log", "INVALID_INPUT")
        model = import_ieee(source, result.stdout)
        models.append(model)
        write_json(output / f"{role}.model.json", model)
        inputs.append({"role": role, "path": str(source_path), "sha256": hashlib.sha256(source_bytes).hexdigest(),
                       "ast_sha256": sha256(output / f"{role}.dxc.log"), "ir_sha256": sha256(output / f"{role}.model.json"),
                       "dxc_seconds": seconds})
    if any(models[0][name] != models[1][name] for name in
           ("interface", "buffer", "output_semantic", "entry_layout", "profile")):
        raise ModelError("The two IEEE source interfaces differ", "INVALID_INPUT")
    constraints = empty_constraints(read_json(args.constraints))
    generated = generate_ieee(models[0], models[1])
    write_text(PROOF / "GeneratedModel.lean", generated)
    write_text(output / "GeneratedModel.lean", generated)
    return {
        "schema": "ieee-hlsl-1", "status": "PREPARED", "model_schema": "ieee-1", "profile": PROFILE,
        "gpu_profile_matched": False, "inputs": inputs, "constraints": constraints,
        "generated_sha256": sha256(PROOF / "GeneratedModel.lean"),
        "dxc_files": read_json(ROOT / "dependencies.lock.json")["dxc"]["binaries"],
        "dxc_version": read_json(ROOT / "dependencies.lock.json")["dxc"]["version"],
        "lean_files": dict(LEAN_LOCK),
        "guarantee": "forall arbitrary binary32 inputs, full stored-value equality under separate nearest-even operations with subnormals; translator and pinned DXC remain trusted",
    }


def ensure_unchanged(generated_path, generated_sha256, source_hashes, modules):
    if sha256(generated_path) != generated_sha256:
        raise ModelError("IEEE generated target changed during checking", "UNPROVED")
    for module, cwd in modules:
        if sha256(cwd / (module + ".lean")) != source_hashes[module]:
            raise ModelError("IEEE semantic/proof source changed during checking", "UNPROVED")


def check(args, output):
    summary = prepare(args, output)
    version, _ = run_lean(["--version"], PROTOTYPE, output / "lean-version.log")
    if version.returncode or "version 4.35.0," not in version.stdout:
        raise ModelError("Unexpected independent IEEE Lean version", "ENVIRONMENT_ERROR")
    proof_bytes = Path(args.agent_proof).read_bytes()
    write_text(PROOF / "SubmittedProof.lean", proof_bytes.decode("utf-8-sig"))
    write_text(output / "SubmittedProof.lean", proof_bytes.decode("utf-8-sig"))
    write_text(PROOF / "Verify.lean", verification_module())
    write_text(output / "Verify.lean", verification_module())
    build_seconds = 0
    source_hashes = {}
    cache_path = ROOT / ".cache/ieee-compiled-modules.json"
    cache = read_json(cache_path) if cache_path.is_file() else {}
    modules = (("ShaderIeee/Model", PROTOTYPE), ("GeneratedModel", PROOF), ("SubmittedProof", PROOF))
    for module, cwd in modules:
        source = cwd / (module + ".lean")
        source_hashes[module] = sha256(source)
        dependency_hashes = dict(source_hashes)
        dependency_hashes["manifest"] = sha256(PROTOTYPE / "lake-manifest.json")
        dependency_hashes["tool_lock"] = hashlib.sha256(json.dumps(LEAN_LOCK, sort_keys=True).encode("utf-8")).hexdigest()
        target = PROTOTYPE / ".lake/build/lib/lean" / (module + ".olean")
        target.parent.mkdir(parents=True, exist_ok=True)
        log = output / ("lean-" + module.replace("/", "-") + ".log")
        cached = cache.get(module, {})
        if (cached.get("inputs") == dependency_hashes and target.is_file() and
                cached.get("output_sha256") == sha256(target)):
            write_text(log, "Reused own compiled module; source/dependency/tool/olean hashes match.\n")
            continue
        result, seconds = run_lean(["-o", target, module + ".lean"], cwd, log, 900)
        build_seconds += seconds
        if result.returncode:
            raise ModelError(f"IEEE target/proof failed Lean; see {log.name}", "UNPROVED")
        cache[module] = {"inputs": dependency_hashes, "output_sha256": sha256(target)}
        write_json(cache_path, cache)
    result, verify_seconds = run_lean(["Verify.lean"], PROOF, output / "lean-verify.log", 900)
    if result.returncode:
        raise ModelError("Independent IEEE target binding failed; see lean-verify.log", "UNPROVED")
    axioms = audit_axioms(result.stdout + "\n" + result.stderr)
    ensure_unchanged(PROOF / "GeneratedModel.lean", summary["generated_sha256"], source_hashes, modules)
    artifact_paths = {
        "generated_target": output / "GeneratedModel.lean",
        "agent_proof": output / "SubmittedProof.lean",
        "verification": output / "Verify.lean",
        "semantic_model": PROTOTYPE / "ShaderIeee/Model.lean",
        "lake_manifest": PROTOTYPE / "lake-manifest.json",
        "dependency_lock": PROTOTYPE / "dependencies.lock.json",
        "lean_build_log": output / "lean-SubmittedProof.log",
        "lean_verify_log": output / "lean-verify.log",
    }
    summary.update({
        "status": "IEEE_PROVED", "theorem": "ShaderFormalize.Verification.checked", "axioms": axioms,
        "agent_proof_sha256": hashlib.sha256(proof_bytes).hexdigest(),
        "semantic_model_sha256": sha256(PROTOTYPE / "ShaderIeee/Model.lean"),
        "lake_manifest_sha256": sha256(PROTOTYPE / "lake-manifest.json"),
        "dependency_lock_sha256": sha256(PROTOTYPE / "dependencies.lock.json"),
        "artifact_sha256": {name: sha256(path) for name, path in artifact_paths.items()},
        "lean_build_seconds": round(build_seconds, 3), "lean_verify_seconds": verify_seconds,
        "lean_version": version.stdout.strip(),
    })
    return summary


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "check"))
    parser.add_argument("--original", type=Path, default=ROOT / "examples/ieee/original.hlsl")
    parser.add_argument("--optimized", type=Path, default=ROOT / "examples/ieee/optimized.hlsl")
    parser.add_argument("--constraints", type=Path, default=ROOT / "examples/ieee/constraints.json")
    parser.add_argument("--agent-proof", type=Path, default=PROOF / "IdentityProof.lean")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/ieee-hlsl/current")
    return parser.parse_args()


def main():
    args = parse_arguments()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    try:
        with workspace_lock():
            write_json(output / "result.json", {"schema": "ieee-hlsl-1", "status": "IN_PROGRESS",
                                               "profile": PROFILE, "gpu_profile_matched": False})
            try:
                summary = prepare(args, output) if args.command == "prepare" else check(args, output)
            except ModelError as error:
                summary = {"schema": "ieee-hlsl-1", "status": error.status, "message": str(error),
                           "profile": PROFILE, "gpu_profile_matched": False}
            except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
                summary = {"schema": "ieee-hlsl-1", "status": "INVALID_INPUT", "message": str(error),
                           "profile": PROFILE, "gpu_profile_matched": False}
            write_json(output / "result.json", summary)
    except ModelError as error:
        summary = {"schema": "ieee-hlsl-1", "status": error.status, "message": str(error),
                   "profile": PROFILE, "gpu_profile_matched": False}
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        summary = {"schema": "ieee-hlsl-1", "status": "INVALID_INPUT", "message": str(error),
                   "profile": PROFILE, "gpu_profile_matched": False}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] in ("PREPARED", "IEEE_PROVED") else 1


if __name__ == "__main__":
    sys.exit(main())

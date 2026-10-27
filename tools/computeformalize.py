"""Experimental DXC Compute pair -> Lean preparation/check, independent of Unity."""
import argparse
import hashlib
from pathlib import Path
import sys

from shader_ast import ModelError, validate_source
from shader_compute import compute_contract, generate_compute, import_compute
from shaderformalize import (ROOT, PROOF, audit_axioms, read_json, run_tool, sha256,
                            validate_dxc, workspace_lock, write_json, write_text)


def prepare(args, output):
    dxc = validate_dxc()
    supplied_contract = read_json(args.constraints)
    models = []
    inputs = []
    for role, filename in (("original", args.original), ("optimized", args.optimized)):
        source_path = Path(filename).resolve()
        source_bytes = source_path.read_bytes()
        source = source_bytes.decode("utf-8-sig")
        validate_source(source)
        snapshot = output / f"{role}.input.hlsl"
        snapshot.write_bytes(source_bytes)
        result, seconds = run_tool([dxc, "-T", "cs_6_0", "-E", "main", "-HV", "2021", "-ast-dump", snapshot],
                                   output, output / f"{role}.dxc.log")
        if result.returncode:
            raise ModelError(f"DXC rejected {role} (exit {result.returncode}); see its log", "INVALID_INPUT")
        model = import_compute(source, result.stdout, supplied_contract.get("schema", 1))
        models.append(model)
        write_json(output / f"{role}.model.json", model)
        inputs.append({"role": role, "path": str(source_path), "sha256": sha256(snapshot), "dxc_seconds": seconds})
    contract = compute_contract(supplied_contract, models[0], models[1])
    generated = generate_compute(models[0], models[1], contract)
    write_text(PROOF / "GeneratedModel.lean", generated)
    write_text(output / "GeneratedModel.lean", generated)
    return {"status": "PREPARED", "model_schema": models[0]["schema"], "inputs": inputs, "constraints": contract,
            "generated_sha256": sha256(output / "GeneratedModel.lean"),
            "guarantee": "ideal real values, exact uint32, guarded thread-local forwarding and proved race-free unique-writer final memory; experimental typed AST translator remains trusted",
            "dxc_files": read_json(ROOT / "dependencies.lock.json")["dxc"]["binaries"]}


def check(args, output):
    summary = prepare(args, output)
    lake = ROOT / ".tools" / "lean-4.24.0-windows" / "bin" / "lake.exe"
    lock = read_json(ROOT / "dependencies.lock.json")
    for name, expected in lock["lean"]["binaries"].items():
        if not (lake.parent / name).is_file() or sha256(lake.parent / name) != expected:
            raise ModelError(f"Pinned Lean file missing/changed: {name}", "ENVIRONMENT_ERROR")
    proof_bytes = Path(args.agent_proof).read_bytes()
    write_text(PROOF / "SubmittedProof.lean", proof_bytes.decode("utf-8-sig"))
    write_text(output / "SubmittedProof.lean", proof_bytes.decode("utf-8-sig"))
    verify = """import GeneratedModel
import SubmittedProof
namespace ShaderFormalize.Verification
theorem checked : ShaderFormalize.GeneratedCompute.expected :=
  ShaderFormalize.AgentProof.equivalent
end ShaderFormalize.Verification
#print axioms ShaderFormalize.Verification.checked
"""
    write_text(PROOF / "Verify.lean", verify)
    # Direct Lean compilation consumes installed dependency oleans read-only.
    # Unlike `lake build`, it never starts missing mathlib source builds.
    build_seconds = 0
    cache_path = ROOT / ".cache" / "compute-compiled-modules.json"
    cache = read_json(cache_path) if cache_path.is_file() else {}
    module_hashes = {}
    semantic_names = ["Model.lean", "Compute.lean"]
    modules = ["ShaderFormalize/Model", "ShaderFormalize/Compute"]
    if summary["model_schema"] == "compute-2":
        semantic_names.append("ComputeTexture.lean")
        modules.append("ShaderFormalize/ComputeTexture")
    modules.extend(["GeneratedModel", "SubmittedProof"])
    for module in modules:
        module_hashes[module] = sha256(PROOF / (module + ".lean"))
        dependency_hashes = dict(module_hashes)
        dependency_hashes["manifest"] = sha256(PROOF / "lake-manifest.json")
        dependency_hashes["tool_lock"] = sha256(ROOT / "dependencies.lock.json")
        target = PROOF / ".lake" / "build" / "lib" / "lean" / (module + ".olean")
        target.parent.mkdir(parents=True, exist_ok=True)
        log = output / ("lean-" + module.replace("/", "-") + ".log")
        cached = cache.get(module, {})
        if (cached.get("inputs") == dependency_hashes and target.is_file()
                and cached.get("output_sha256") == sha256(target)):
            write_text(log, "Reused own compiled module; source/dependency/tool/olean hashes match.\n")
            continue
        result, seconds = run_tool([lake, "env", "lean", "-o", target, module + ".lean"], PROOF, log, 180)
        build_seconds += seconds
        if result.returncode:
            raise ModelError(f"Compute target/proof failed Lean; see {log.name}", "UNPROVED")
        cache[module] = {"inputs": dependency_hashes, "output_sha256": sha256(target)}
        write_json(cache_path, cache)
    result, verify_seconds = run_tool([lake, "env", "lean", "Verify.lean"], PROOF, output / "lean-verify.log", 180)
    if result.returncode:
        raise ModelError("Independent Compute target binding failed", "UNPROVED")
    axioms = audit_axioms(result.stdout + "\n" + result.stderr)
    if sha256(PROOF / "GeneratedModel.lean") != summary["generated_sha256"]:
        raise ModelError("Compute target changed during checking", "UNPROVED")
    if any(sha256(PROOF / (module + ".lean")) != expected for module, expected in module_hashes.items()):
        raise ModelError("Compute semantic/proof source changed during checking", "UNPROVED")
    summary.update(status="PROVED", theorem="ShaderFormalize.Verification.checked", axioms=axioms,
                   agent_proof_sha256=hashlib.sha256(proof_bytes).hexdigest(),
                    semantic_modules={name: sha256(PROOF / "ShaderFormalize" / name) for name in semantic_names},
                   lake_manifest_sha256=sha256(PROOF / "lake-manifest.json"),
                   lean_build_seconds=build_seconds, lean_verify_seconds=verify_seconds)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "check"))
    parser.add_argument("--original", type=Path, default=ROOT / "examples/compute/original.hlsl")
    parser.add_argument("--optimized", type=Path, default=ROOT / "examples/compute/optimized.hlsl")
    parser.add_argument("--constraints", type=Path, default=ROOT / "examples/compute/constraints.json")
    parser.add_argument("--agent-proof", type=Path, default=PROOF / "ComputePostProof.lean")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/compute/proof")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    try:
        with workspace_lock():
            write_json(output / "result.json", {"status": "IN_PROGRESS"})
            result = prepare(args, output) if args.command == "prepare" else check(args, output)
            write_json(output / "result.json", result)
    except ModelError as error:
        result = {"status": error.status, "message": str(error)}
        if error.status != "INCONCLUSIVE":
            write_json(output / "result.json", result)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        result = {"status": "INVALID_INPUT", "message": str(error)}
        write_json(output / "result.json", result)
    print(result["status"] + (": " + result["message"] if "message" in result else ""))
    return 0 if result["status"] in ("PREPARED", "PROVED") else 1


if __name__ == "__main__":
    sys.exit(main())

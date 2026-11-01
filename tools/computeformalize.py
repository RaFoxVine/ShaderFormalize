"""Experimental DXC Compute pair -> Lean preparation/check, independent of Unity."""
import argparse
import hashlib
from pathlib import Path
import sys
import json
import os
import uuid
from proof_contract import verification_module

from shader_ast import ModelError, validate_source
from lean_environment import validate_lean
from shader_compute import compute_contract, generate_compute, import_compute
from shaderformalize import (ROOT, PROOF, audit_axioms, read_json, run_tool, sha256,
                            validate_dxc, workspace_lock, write_json, write_text)


class Backend:
    def __init__(self, uint=False):
        self.uint = uint
        self.prefix = "ShaderComputeUint/" if uint else ""
        self.theorem = "ShaderComputeUint.Verification.checked" if uint else "ShaderFormalize.Verification.checked"

LEGACY = Backend()
UINT = Backend(True)


def prepare(args, output, *, backend=LEGACY):
    if backend.uint:
        source = Path(args.constraints).read_bytes()
        (output / "constraints.input.json").write_bytes(source)
        supplied_contract = json.loads(source.decode("utf-8-sig"))
        if not isinstance(supplied_contract, dict) or type(supplied_contract.get("schema")) is not int or supplied_contract["schema"] != 3:
            raise ModelError("uint32-buffer requires schema 3", "INVALID_INPUT")
        from shader_compute_uint import import_uint_compute, uint_contract
        from shader_compute_uint_lean import generate_uint_compute
        importer = lambda source, dump, schema: import_uint_compute(source, dump)
        contract_fn, generator = uint_contract, generate_uint_compute
    else:
        dxc = validate_dxc()
        supplied_contract = read_json(args.constraints)
        if isinstance(supplied_contract, dict) and supplied_contract.get("schema") == 3:
            raise ModelError("schema 3 requires --model uint32-buffer", "INVALID_INPUT")
        importer, contract_fn, generator = import_compute, compute_contract, generate_compute
    if backend.uint:
        dxc = validate_dxc()
    if not isinstance(supplied_contract, dict):
        raise ModelError("Compute contract must be a JSON object", "INVALID_INPUT")
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
        model = importer(source, result.stdout, supplied_contract.get("schema", 1))
        models.append(model)
        write_json(output / f"{role}.model.json", model)
        input_info = {"role": role, "path": str(source_path), "sha256": sha256(snapshot), "dxc_seconds": seconds}
        if backend.uint:
            input_info.update(ast_sha256=sha256(output / f"{role}.dxc.log"), ir_sha256=sha256(output / f"{role}.model.json"))
        inputs.append(input_info)
    contract = contract_fn(supplied_contract, models[0], models[1])
    generated = generator(models[0], models[1], contract)
    write_text(PROOF / (backend.prefix + "GeneratedModel.lean"), generated)
    write_text(output / "GeneratedModel.lean", generated)
    return {"status": "PREPARED", "model_schema": models[0]["schema"], "inputs": inputs, "constraints": contract,
            "generated_sha256": sha256(output / "GeneratedModel.lean"),
            "gpu_profile_matched": False,
            "guarantee": "exact uint32 modular values, guarded ordered overlay, bounds and race-free complete final memory" if backend.uint else "ideal real values, exact uint32, guarded thread-local forwarding and proved race-free unique-writer final memory; experimental typed AST translator remains trusted",
            "dxc_files": read_json(ROOT / "dependencies.lock.json")["dxc"]["binaries"]}


def hash_matches(path, expected, *, missing_is_mismatch=False):
    try:
        return sha256(path) == expected
    except OSError:
        if missing_is_mismatch:
            return False
        raise


def check(args, output, *, backend=LEGACY):
    summary = prepare(args, output, backend=backend)
    lake = validate_lean()
    proof_bytes = Path(args.agent_proof).read_bytes()
    write_text(PROOF / (backend.prefix + "SubmittedProof.lean"), proof_bytes.decode("utf-8-sig"))
    write_text(output / "SubmittedProof.lean", proof_bytes.decode("utf-8-sig"))
    verify = """import GeneratedModel
import SubmittedProof
namespace ShaderFormalize.Verification
theorem checked : ShaderFormalize.GeneratedCompute.expected :=
  ShaderFormalize.AgentProof.equivalent
end ShaderFormalize.Verification
#print axioms ShaderFormalize.Verification.checked
"""
    if backend.uint:
        verify = verification_module("ShaderComputeUint.GeneratedModel", "ShaderComputeUint.SubmittedProof", "ShaderComputeUint")
    write_text(PROOF / (backend.prefix + "Verify.lean"), verify)
    write_text(output / "Verify.lean", verify)
    # Direct Lean compilation consumes installed dependency oleans read-only.
    # Unlike `lake build`, it never starts missing mathlib source builds.
    build_seconds = 0
    cache_path = ROOT / ".cache" / ("compute-uint-compiled-modules.json" if backend.uint else "compute-compiled-modules.json")
    cache = read_json(cache_path) if cache_path.is_file() else {}
    module_hashes = {}
    modules = (["ShaderFormalize/ComputeMemory", "ShaderIeee/Model", "ShaderComputeUint/Model"] if backend.uint
               else ["ShaderFormalize/Model", "ShaderFormalize/ComputeMemory", "ShaderFormalize/Compute"])
    if summary["model_schema"] == "compute-2":
        modules.append("ShaderFormalize/ComputeTexture")
    semantic_modules = list(modules)
    modules.extend([backend.prefix + "GeneratedModel", backend.prefix + "SubmittedProof"])
    baseline_paths = [PROOF / (module + ".lean") for module in modules]
    baseline_paths += [PROOF / (backend.prefix + "Verify.lean"), PROOF / "lake-manifest.json", PROOF / "lakefile.lean", PROOF / "lean-toolchain", ROOT / "dependencies.lock.json"]
    if backend.uint:
        baseline_paths += [output / name for name in ("constraints.input.json", "original.input.hlsl", "optimized.input.hlsl", "original.model.json", "optimized.model.json", "original.dxc.log", "optimized.dxc.log", "GeneratedModel.lean", "SubmittedProof.lean", "Verify.lean")]
    baseline = {str(path): sha256(path) for path in baseline_paths}
    for module in modules:
        module_hashes[module] = sha256(PROOF / (module + ".lean"))
        dependency_hashes = dict(module_hashes)
        dependency_hashes["manifest"] = sha256(PROOF / "lake-manifest.json")
        dependency_hashes["lakefile"] = sha256(PROOF / "lakefile.lean")
        dependency_hashes["lean_toolchain"] = sha256(PROOF / "lean-toolchain")
        dependency_hashes["tool_lock"] = sha256(ROOT / "dependencies.lock.json")
        target = PROOF / ".lake" / "build" / "lib" / "lean" / (module + ".olean")
        target.parent.mkdir(parents=True, exist_ok=True)
        log = output / ("lean-" + module.replace("/", "-") + ".log")
        cached = cache.get(module, {})
        if (cached.get("inputs") == dependency_hashes and target.is_file()
                and cached.get("output_sha256") == sha256(target)):
            write_text(log, "Reused own compiled module; source/dependency/tool/olean hashes match.\n")
            continue
        result, seconds = run_tool([lake, "env", "lean", "-o", target, module + ".lean"], PROOF, log, 900 if backend.uint else 180)
        build_seconds += seconds
        if result.returncode:
            raise ModelError(f"Compute target/proof failed Lean; see {log.name}", "UNPROVED")
        cache[module] = {"inputs": dependency_hashes, "output_sha256": sha256(target)}
        write_json(cache_path, cache)
    result, verify_seconds = run_tool([lake, "env", "lean", backend.prefix + "Verify.lean"], PROOF, output / "lean-verify.log", 900 if backend.uint else 180)
    if result.returncode:
        raise ModelError("Independent Compute target binding failed", "UNPROVED")
    axioms = audit_axioms(result.stdout + "\n" + result.stderr, backend.theorem)
    if not hash_matches(PROOF / (backend.prefix + "GeneratedModel.lean"), summary["generated_sha256"], missing_is_mismatch=backend.uint):
        raise ModelError("Compute target changed during checking", "UNPROVED")
    if any(not hash_matches(PROOF / (module + ".lean"), expected, missing_is_mismatch=backend.uint) for module, expected in module_hashes.items()):
        raise ModelError("Compute semantic/proof source changed during checking", "UNPROVED")
    if any(not hash_matches(path, digest, missing_is_mismatch=backend.uint) for path, digest in baseline.items()):
        raise ModelError("Compute target/input/semantic binding changed during checking", "UNPROVED")
    summary.update(status="PROVED", theorem=backend.theorem, axioms=axioms,
                   agent_proof_sha256=hashlib.sha256(proof_bytes).hexdigest(),
                    semantic_modules={name: module_hashes[name] for name in semantic_modules},
                   lake_manifest_sha256=sha256(PROOF / "lake-manifest.json"),
                   lean_build_seconds=build_seconds, lean_verify_seconds=verify_seconds)
    if backend.uint:
        paths = [output / "constraints.input.json", output / "original.input.hlsl", output / "optimized.input.hlsl",
                 output / "original.model.json", output / "optimized.model.json", output / "original.dxc.log", output / "optimized.dxc.log", output / "GeneratedModel.lean",
                 output / "SubmittedProof.lean", output / "Verify.lean", PROOF / "lake-manifest.json", PROOF / "lakefile.lean", PROOF / "lean-toolchain", ROOT / "dependencies.lock.json"]
        summary["artifact_sha256"] = {str(path): sha256(path) for path in paths}
    return summary


def atomic_result(path, result):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def uint_main(args):
    identity = None
    try:
        run_id = uuid.uuid4().hex
        container = args.output.resolve()
        container.mkdir(parents=True, exist_ok=True)
        candidate = container / run_id
        candidate.mkdir(exist_ok=False)
        report = candidate / "result.json"
        identity = dict(run_id=run_id, result_path=str(report), model_schema="compute-uint-1", gpu_profile_matched=False)
        atomic_result(report, dict(identity, status="IN_PROGRESS"))
        with workspace_lock():
            result = (prepare if args.command == "prepare" else check)(args, candidate, backend=UINT)
    except ModelError as error:
        result = dict(status=error.status, message=str(error))
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        result = dict(status="INVALID_INPUT", message=str(error))
    except KeyboardInterrupt:
        result = dict(status="INCONCLUSIVE", message="Interrupted")
    except Exception as error:
        result = dict(status="INTERNAL_ERROR", message=str(error))
    if identity is None:
        print("Cannot save uint Compute result: " + result.get("message", "output is unavailable"), file=sys.stderr)
        return 1
    result.update(identity)
    try:
        atomic_result(report, result)
    except (Exception, KeyboardInterrupt) as error:
        print("Cannot save uint Compute result: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] in ("PREPARED", "PROVED") else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "check"))
    parser.add_argument("--model", choices=("legacy", "uint32-buffer"), default="legacy")
    parser.add_argument("--original", type=Path)
    parser.add_argument("--optimized", type=Path)
    parser.add_argument("--constraints", type=Path)
    parser.add_argument("--agent-proof", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    defaults = ({"original": ROOT / "examples/compute-uint/hash.original.hlsl", "optimized": ROOT / "examples/compute-uint/hash.optimized.hlsl",
                 "constraints": ROOT / "examples/compute-uint/hash.constraints.json", "agent_proof": PROOF / "ComputeUintHashProof.lean", "output": ROOT / "artifacts/compute-uint"}
                if args.model == "uint32-buffer" else
                {"original": ROOT / "examples/compute/original.hlsl", "optimized": ROOT / "examples/compute/optimized.hlsl", "constraints": ROOT / "examples/compute/constraints.json",
                 "agent_proof": PROOF / "ComputePostProof.lean", "output": ROOT / "artifacts/compute/proof"})
    for key, value in defaults.items():
        if getattr(args, key) is None:
            setattr(args, key, value)
    if args.model == "uint32-buffer":
        return uint_main(args)
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

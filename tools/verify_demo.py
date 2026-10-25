"""Check the positive demo and deliberately broken proof/input controls."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import unittest

from shaderformalize import ROOT, write_json, write_text


def check_case(name, expected, *extra):
    output = ROOT / "artifacts/acceptance" / name
    result = subprocess.run([sys.executable, str(ROOT / "tools/shaderformalize.py"), "check", "--output", str(output), *map(str, extra)],
                            capture_output=True, text=True, encoding="utf-8", timeout=900)
    summary = json.loads((output / "result.json").read_text(encoding="utf-8"))
    if summary["status"] != expected or (result.returncode == 0) != (expected == "PROVED"):
        raise RuntimeError(f"{name}: expected {expected}, got {summary}")
    if name in ("custom-axiom", "sorry-proof") and not summary.get("message", "").startswith("Proof depends on unapproved axioms:"):
        raise RuntimeError(f"{name}: did not reach the intended axiom audit: {summary}")
    if name == "forged-target" and summary.get("message") != "The independent target-binding module failed":
        raise RuntimeError(f"{name}: did not reach independent target binding: {summary}")
    print(name + ": " + expected, flush=True)
    return {"case": name, "expected": expected, "actual": summary["status"]}


def lerp_controls(output):
    controls = []
    controls.append(check_case("wrong-expression", "UNPROVED", "--optimized", ROOT / "examples/lerp/wrong.hlsl"))
    wide = output / "wide.json"
    write_json(wide, {"schema": 1, "ranges": {"t": {"min": "-1", "max": "2"}}})
    controls.append(check_case("missing-range-premise", "UNPROVED", "--constraints", wide))
    fake = output / "Fake.lean"
    write_text(fake, '''import GeneratedModel
namespace ShaderFormalize.AgentProof
axiom lie : ShaderFormalize.Generated.expected
theorem equivalent : ShaderFormalize.Generated.expected := lie
end ShaderFormalize.AgentProof
''')
    controls.append(check_case("custom-axiom", "UNPROVED", "--agent-proof", fake))
    write_text(fake, '''import GeneratedModel
namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := by sorry
end ShaderFormalize.AgentProof
''')
    controls.append(check_case("sorry-proof", "UNPROVED", "--agent-proof", fake))
    write_text(fake, '''namespace ShaderFormalize.Generated
def expected : Prop := True
end ShaderFormalize.Generated
namespace ShaderFormalize.AgentProof
theorem equivalent : ShaderFormalize.Generated.expected := True.intro
end ShaderFormalize.AgentProof
''')
    controls.append(check_case("forged-target", "UNPROVED", "--agent-proof", fake))
    # Leave the working generated model/proof in the successful, canonical state.
    controls.append(check_case("positive", "PROVED"))
    return controls


def material_controls(example):
    material = ROOT / "examples" / example
    proof = {"unlit": "UnlitProof", "structured": "StructuredProof", "textured": "TexturedProof"}[example]
    arguments = ["--original", material / "original.hlsl", "--constraints", material / "constraints.json", "--agent-proof", ROOT / "proof" / (proof + ".lean")]
    controls = []
    if example in ("unlit", "structured"):
        missing = ROOT / "artifacts/acceptance/missing-direction-domain.json"
        write_json(missing, {"schema": 2, "ranges": {}, "nonzero_vectors": []})
        controls.append(check_case(example + "-missing-domain", "INVALID_INPUT", *arguments, "--optimized", material / "optimized.hlsl", "--constraints", missing))
    roles = ["wrong", "wrong-uv", "wrong-derivative", "wrong-lod", "wrong-sampler"] if example == "textured" else ["wrong"]
    for role in roles:
        controls.append(check_case(example + "-" + role, "UNPROVED", *arguments, "--optimized", material / (role + ".hlsl")))
    controls.append(check_case(example + "-positive", "PROVED", *arguments, "--optimized", material / "optimized.hlsl"))
    return controls


def control_controls():
    material = ROOT / "examples/control"
    controls = []
    for name, proof in (("alias", "ControlAliasProof"), ("else", "ControlElseProof"), ("return", "ControlReturnProof"), ("domain", "ControlDomainProof")):
        arguments = ["--original", material / (name + ".original.hlsl"), "--constraints", material / "constraints.json", "--agent-proof", ROOT / "proof" / (proof + ".lean")]
        if name == "domain":
            controls.append(check_case("control-domain-wrong", "UNPROVED", *arguments, "--optimized", material / "domain.wrong.hlsl"))
        controls.append(check_case("control-" + name, "PROVED", *arguments, "--optimized", material / (name + ".optimized.hlsl")))
    material = ROOT / "examples/branched"
    controls.append(check_case("control-mixed", "PROVED",
        "--original", ROOT / "examples/control/mixed.original.hlsl",
        "--optimized", ROOT / "examples/control/mixed.optimized.hlsl",
        "--constraints", ROOT / "examples/control/zero-constraints.json",
        "--agent-proof", ROOT / "proof/ControlMixedProof.lean"))
    arguments = ["--original", material / "original.hlsl", "--constraints", material / "constraints.json", "--agent-proof", ROOT / "proof/BranchedProof.lean"]
    for role in ("wrong", "wrong-cutoff"):
        controls.append(check_case("branched-" + role, "UNPROVED", *arguments, "--optimized", material / (role + ".hlsl")))
    controls.append(check_case("branched-positive", "PROVED", *arguments, "--optimized", material / "optimized.hlsl"))
    return controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", choices=("all", "lerp", "unlit", "structured", "textured", "branched"), default="all")
    args = parser.parse_args()
    output = ROOT / "artifacts" / ("acceptance" if args.example == "all" else "acceptance-" + args.example)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "result.json", {"status": "IN_PROGRESS", "layer": "core", "example": args.example})
    patterns = {"lerp": "test_shaderformalize.py", "unlit": "test_unlit.py", "structured": "test_structured.py", "textured": "test_fragment.py", "branched": "test_control.py"}
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tools"), pattern=patterns.get(args.example, "test_*.py"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        write_json(output / "result.json", {"status": "FAILED", "layer": "core", "message": "Importer/infrastructure regression failed"})
        return 1
    controls = []
    try:
        if args.example in ("all", "lerp"):
            controls.extend(lerp_controls(output))
        for example in ("unlit", "structured", "textured"):
            if args.example in ("all", example):
                controls.extend(material_controls(example))
        if args.example in ("all", "branched"):
            controls.extend(control_controls())
        write_json(output / "result.json", {"status": "PASSED", "layer": "core", "example": args.example, "regression_tests": result.testsRun, "controls": controls})
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        write_json(output / "result.json", {"status": "FAILED", "layer": "core", "controls": controls, "message": str(error)})
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

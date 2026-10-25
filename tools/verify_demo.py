"""Check the positive demo and deliberately broken proof/input controls."""
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


def main():
    output = ROOT / "artifacts/acceptance"
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "result.json", {"status": "IN_PROGRESS"})
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tools"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        write_json(output / "result.json", {"status": "FAILED", "message": "Importer/infrastructure regression failed"})
        return 1
    controls = []
    try:
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
        material = ROOT / "examples/unlit"
        material_args = ["--original", material / "original.hlsl", "--constraints", material / "constraints.json", "--agent-proof", ROOT / "proof/UnlitProof.lean"]
        missing = output / "missing-direction-domain.json"
        write_json(missing, {"schema": 2, "ranges": {}, "nonzero_vectors": []})
        controls.append(check_case("unlit-missing-domain", "INVALID_INPUT", *material_args, "--optimized", material / "optimized.hlsl", "--constraints", missing))
        controls.append(check_case("unlit-wrong", "UNPROVED", *material_args, "--optimized", material / "wrong.hlsl"))
        controls.append(check_case("unlit-positive", "PROVED", *material_args, "--optimized", material / "optimized.hlsl"))
        structured = ROOT / "examples/structured"
        structured_args = ["--original", structured / "original.hlsl", "--constraints", structured / "constraints.json", "--agent-proof", ROOT / "proof/StructuredProof.lean"]
        controls.append(check_case("structured-missing-domain", "INVALID_INPUT", *structured_args, "--optimized", structured / "optimized.hlsl", "--constraints", missing))
        controls.append(check_case("structured-wrong", "UNPROVED", *structured_args, "--optimized", structured / "wrong.hlsl"))
        controls.append(check_case("structured-positive", "PROVED", *structured_args, "--optimized", structured / "optimized.hlsl"))
        textured = ROOT / "examples/textured"
        textured_args = ["--original", textured / "original.hlsl", "--constraints", textured / "constraints.json", "--agent-proof", ROOT / "proof/TexturedProof.lean"]
        for role in ("wrong", "wrong-uv", "wrong-derivative", "wrong-lod", "wrong-sampler"):
            controls.append(check_case("textured-" + role, "UNPROVED", *textured_args, "--optimized", textured / (role + ".hlsl")))
        controls.append(check_case("textured-positive", "PROVED", *textured_args, "--optimized", textured / "optimized.hlsl"))
        write_json(output / "result.json", {"status": "PASSED", "regression_tests": result.testsRun, "controls": controls})
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        write_json(output / "result.json", {"status": "FAILED", "controls": controls, "message": str(error)})
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

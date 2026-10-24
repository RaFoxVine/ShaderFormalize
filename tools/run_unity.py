"""Execute the demo's exact HLSL files in an existing Unity Editor via Unity CLI."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from shaderformalize import ROOT, read_json, sha256, write_json, write_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--example", choices=("lerp", "unlit"), default="lerp")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = (args.output or ROOT / ("artifacts/unlit/unity" if args.example == "unlit" else "artifacts/unity")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = output / "result.json"
    write_json(report, {"status": "IN_PROGRESS"})
    try:
        cli = shutil.which("unity")
        if cli is None:
            raise RuntimeError("Unity CLI is not on PATH; an existing connected Editor is required")
        source = "unity/RunUnlit.cs" if args.example == "unlit" else "unity/RunProbe.cs"
        script = (ROOT / source).read_text(encoding="utf-8")
        script = script.replace("__WORKSPACE__", str(ROOT).replace('"', '""'))
        script = script.replace("__OUTPUT__", str(output).replace('"', '""'))
        generated = output / "UnityProbe.generated.cs"
        write_text(generated, script)
        result = subprocess.run([cli, "command", "eval_file", str(generated), "300000",
                                 "--project-path", str(args.project.resolve()), "--format", "json", "--timeout", "360"],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=390)
        write_text(output / "unity-cli.log", result.stdout + "\n--- stderr ---\n" + result.stderr)
        if result.returncode:
            raise RuntimeError("Unity command failed; see unity-cli.log")
        envelope = json.loads(result.stdout)
        # Unity CLI transports the Roslyn result in its own command envelope.
        if not envelope.get("success"):
            raise RuntimeError("Unity CLI reported failure; see unity-cli.log")
        payload = envelope.get("data", {}).get("result", {})
        if not payload.get("success"):
            raise RuntimeError("Unity script reported failure; see unity-cli.log")
        summary = payload.get("result")
        if isinstance(summary, str):
            summary = json.loads(summary)
        if not isinstance(summary, dict) or summary.get("status") != "PASSED":
            raise RuntimeError("Missing GPU success report; see unity-cli.log")
        for role in ("original", "optimized", "wrong"):
            if summary["hashes"][role] != sha256(ROOT / "examples" / args.example / (role + ".hlsl")):
                raise RuntimeError("GPU/source hash mismatch")
        if args.example == "unlit":
            summary["shader_template_sha256"] = sha256(ROOT / "unity/Unlit.shader.template")
        write_json(report, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        summary = {"status": "FAILED", "message": str(error)}
        write_json(report, summary)
        print(json.dumps(summary, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())

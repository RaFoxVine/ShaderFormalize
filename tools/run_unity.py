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
    parser.add_argument("--example", choices=("lerp", "unlit", "structured", "textured", "branched"), default="lerp")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    default_output = ROOT / "artifacts/unity" if args.example == "lerp" else ROOT / "artifacts" / args.example / "unity"
    output = (args.output or default_output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = output / "result.json"
    write_json(report, {"status": "IN_PROGRESS"})
    try:
        cli = shutil.which("unity")
        if cli is None:
            raise RuntimeError("Unity CLI is not on PATH; an existing connected Editor is required")
        source = "unity/RunProbe.cs" if args.example == "lerp" else "unity/RunUnlit.cs"
        if args.example in ("textured", "branched"):
            source = "unity/RunTextured.cs"
        script = (ROOT / source).read_text(encoding="utf-8")
        script = script.replace("__WORKSPACE__", str(ROOT).replace('"', '""'))
        script = script.replace("__OUTPUT__", str(output).replace('"', '""'))
        template = None
        if args.example in ("textured", "branched"):
            title = "Textured" if args.example == "textured" else "Branched"
            template = "unity/" + title + ".shader.template"
            script = script.replace("__ASSET_FOLDER__", "ShaderFormalize" + title).replace("__SCENE_NAME__", title + "Comparison")
            script = script.replace("__SHADER_TEMPLATE__", template).replace("__EXAMPLE__", args.example)
        if args.example in ("unlit", "structured"):
            if args.example == "unlit":
                asset_folder, scene_name, template = "ShaderFormalizeUnlit", "UnlitComparison", "unity/Unlit.shader.template"
            else:
                asset_folder, scene_name, template = "ShaderFormalizeStructured", "StructuredComparison", "unity/Structured.shader.template"
            script = script.replace("__ASSET_FOLDER__", asset_folder).replace("__SCENE_NAME__", scene_name)
            script = script.replace("__SHADER_TEMPLATE__", template).replace("__EXAMPLE__", args.example)
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
        roles = ["original", "optimized", "wrong"]
        if args.example == "textured":
            roles.extend(["wrong-uv", "wrong-derivative", "wrong-lod", "wrong-sampler"])
        elif args.example == "branched":
            roles.append("wrong-cutoff")
        for role in roles:
            if summary["hashes"][role] != sha256(ROOT / "examples" / args.example / (role + ".hlsl")):
                raise RuntimeError("GPU/source hash mismatch")
        if template is not None:
            summary["shader_template_sha256"] = sha256(ROOT / template)
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

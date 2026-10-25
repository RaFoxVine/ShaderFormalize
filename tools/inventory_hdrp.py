"""Optional developer investigation of a fixed external HDRP/Lit Forward variant.

Never imported by bootstrap, shader conversion, or the default core checks.
Generated Unity source mirrors remain in the requested ignored output directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from shaderformalize import ROOT, validate_dxc, write_json, write_text

DEFINES = {"SHADER_API_D3D11": "1", "SHADER_STAGE_FRAGMENT": "1", "UNITY_COMPILER_DXC": "1", "SHADER_TARGET": "45",
           "_ALPHATEST_ON": "1", "_DISABLE_DECALS": "1", "DECALS_OFF": "1", "USE_FPTL_LIGHTLIST": "1",
           "SCREEN_SPACE_SHADOWS_OFF": "1", "PUNCTUAL_SHADOW_LOW": "1", "DIRECTIONAL_SHADOW_LOW": "1", "AREA_SHADOW_MEDIUM": "1"}
INCLUDE = re.compile(r'^([ \t]*#[ \t]*include(?:_with_pragmas)?[ \t]+)"([^"]+)"', re.MULTILINE)


def package_paths(project):
    result = {}
    for directory in (project / "Library/PackageCache").iterdir():
        metadata = directory / "package.json"
        if not metadata.is_file():
            continue
        data = json.loads(metadata.read_text(encoding="utf-8-sig"))
        if data["name"] in result:
            raise RuntimeError("Ambiguous cached package: " + data["name"])
        result[data["name"]] = directory
    return result


def source_blocks(text):
    shared = re.search(r"\bHLSLINCLUDE\b(.*?)\bENDHLSL\b", text, re.DOTALL)
    forward = re.search(r'\bName\s+"Forward".*?\bHLSLPROGRAM\b(.*?)\bENDHLSL\b', text, re.DOTALL)
    if shared is None or forward is None:
        raise RuntimeError("Expected the pinned Lit shared block and Forward Pass")
    return shared.group(1) + "\n" + forward.group(1)


class SourceMirror:
    def __init__(self, packages, output):
        self.packages, self.output = packages, output
        self.sources, self.unresolved = {}, []
        self.total_bytes = 0

    def resolve(self, name, owner):
        if name.startswith("Packages/"):
            parts = name.split("/", 2)
            if len(parts) == 3 and parts[1] in self.packages:
                candidate = self.packages[parts[1]] / parts[2]
                return candidate.resolve() if candidate.is_file() else None
        candidate = owner.parent / name
        return candidate.resolve() if candidate.is_file() else None

    def rewrite(self, text, owner):
        pieces = []
        previous = 0
        for match in INCLUDE.finditer(text):
            pieces.append(text[previous:match.start()])
            target = self.resolve(match.group(2), owner)
            if target is None:
                self.unresolved.append({"owner": str(owner), "include": match.group(2)})
                pieces.append(match.group(0))
            else:
                prefix = match.group(1).replace("include_with_pragmas", "include")
                pieces.append(prefix + '"' + self.copy(target).as_posix() + '"')
            previous = match.end()
        pieces.append(text[previous:])
        return "".join(pieces)

    def copy(self, source):
        if source in self.sources:
            return self.sources[source]["mirror"]
        raw = source.read_bytes()
        self.total_bytes += len(raw)
        if len(self.sources) >= 1024 or self.total_bytes > 64*1024*1024:
            raise RuntimeError("Optional HDRP source mirror exceeds its investigation budget")
        name = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:24] + ".hlsl"
        target = self.output / name
        self.sources[source] = {"mirror": target, "sha256": hashlib.sha256(raw).hexdigest()}
        write_text(target, self.rewrite(raw.decode("utf-8-sig"), source))
        return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/hdrp")
    args = parser.parse_args()
    project, output = args.project.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {"status": "IN_PROGRESS", "layer": "optional-development", "project": str(project)}
    write_json(output / "result.json", report)
    try:
        packages = package_paths(project)
        hdrp = packages["com.unity.render-pipelines.high-definition"]
        shader = hdrp / "Runtime/Material/Lit/Lit.shader"
        package = json.loads((hdrp / "package.json").read_text(encoding="utf-8-sig"))
        raw = shader.read_bytes()
        source = source_blocks(raw.decode("utf-8-sig"))
        write_text(output / "Forward.unity.hlsl", source)
        mirror = SourceMirror(packages, output / "sources")
        mirror.output.mkdir(exist_ok=True)
        rewritten = mirror.rewrite(source, shader)
        # Unity pragmas select engine variants and are retained separately as provenance.
        pragmas = re.findall(r"^[ \t]*#pragma[^\r\n]*", rewritten, re.MULTILINE)
        rewritten = re.sub(r"^[ \t]*#pragma[^\r\n]*", "", rewritten, flags=re.MULTILINE)
        definitions = "\n".join(f"#define {name} {value}" for name, value in DEFINES.items()) + "\n"
        generated = output / "Forward.input.hlsl"
        write_text(generated, definitions + rewritten)
        preprocessed = output / "Forward.preprocessed.hlsl"
        if preprocessed.exists():
            preprocessed.unlink()
        result = subprocess.run([str(validate_dxc()), "-P", "-Fi", str(preprocessed), "-HV", "2021", str(generated)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        write_text(output / "preprocess.log", result.stdout + "\n" + result.stderr)
        preprocess_ok = result.returncode == 0 and preprocessed.is_file() and re.search(r"\berror:", result.stderr) is None
        report.update(status="INVESTIGATED", package={"name": package["name"], "version": package["version"], "cache_directory": hdrp.name},
                      pass_name="Forward", source_sha256=hashlib.sha256(raw).hexdigest(), defines=DEFINES, unity_pragmas=pragmas,
                      preprocess_status="PREPROCESSED" if preprocess_ok else "BLOCKED", preprocess_exit_code=result.returncode,
                      diagnostic_tail=(result.stdout + result.stderr)[-5000:], unresolved_literal_includes=mirror.unresolved,
                      sources={str(path): item["sha256"] for path, item in mirror.sources.items()},
                      guarantee="Developer source/variant investigation only; no successful AST translation or Lit equivalence is claimed.")
        if preprocess_ok:
            report["preprocessed_sha256"] = hashlib.sha256(preprocessed.read_bytes()).hexdigest()
            probe = subprocess.run([str(validate_dxc()), "-T", "ps_6_0", "-E", "Frag", "-HV", "2021", "-ast-dump", str(preprocessed)],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            write_text(output / "typed-ast.log", probe.stdout + "\n" + probe.stderr)
            ast_bytes = (output / "typed-ast.log").read_bytes()
            report["ast_sha256"] = hashlib.sha256(ast_bytes).hexdigest()
            report["ast_bytes"] = len(ast_bytes)
            report["ast_probe_status"] = "PARSED" if probe.returncode == 0 else "BLOCKED"
            report["ast_diagnostic_tail"] = probe.stderr[-4000:]
        write_json(output / "result.json", report)
        print(json.dumps({key: report[key] for key in ("status", "package", "pass_name", "preprocess_status")}, indent=2))
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as error:
        write_json(output / "result.json", dict(report, status="FAILED", message=str(error)))
        print(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

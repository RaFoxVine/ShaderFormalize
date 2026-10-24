"""Materialize the committed Lake manifest without fetching unbounded Git history."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

from shaderformalize import ROOT, local_environment


def materialize(entry):
    name = entry["name"]
    path = ROOT / "proof/.lake/packages" / name
    log_path = ROOT / "artifacts/bootstrap" / (name + ".log")
    path.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        def git(*args, check=True):
            result = subprocess.run(["git", "-C", str(path), *args], env=local_environment(),
                                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
            log.write(result.stdout + result.stderr)
            log.flush()
            if check and result.returncode:
                raise RuntimeError(f"{name}: git failed; see {log_path}")
            return result
        if not (path / ".git").exists():
            git("init", "--quiet")
            git("remote", "add", "origin", entry["url"])
        head = git("rev-parse", "--verify", "HEAD", check=False)
        if head.returncode or head.stdout.strip() != entry["rev"]:
            git("fetch", "--depth", "1", "origin", entry["rev"])
            git("checkout", "--detach", entry["rev"])
        # Lake's ProofWidgets release target discovers the matching Git tag.
        # A SHA-only shallow fetch does not create it; retain locked tag metadata.
        if name == "proofwidgets":
            tag = entry["inputRev"]
            tagged = git("rev-parse", "--verify", "refs/tags/" + tag + "^{commit}", check=False)
            if tagged.returncode:
                git("fetch", "--depth", "1", "origin", "tag", tag)
                tagged = git("rev-parse", "--verify", "refs/tags/" + tag + "^{commit}")
            if tagged.stdout.strip() != entry["rev"]:
                raise RuntimeError("ProofWidgets release tag does not match the committed revision")
    print(name + ": " + entry["rev"], flush=True)


if __name__ == "__main__":
    manifest = json.loads((ROOT / "proof/lake-manifest.json").read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(materialize, manifest["packages"]))

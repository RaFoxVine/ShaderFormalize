"""Materialize exactly the independent prototype's pinned Lake sources."""
import json
from pathlib import Path
import subprocess

PROJECT = Path(__file__).resolve().parent


def git(arguments, directory):
    subprocess.run(["git", "-c", "http.sslBackend=schannel", "-c", "http.version=HTTP/1.1",
                    "-c", "http.lowSpeedLimit=1024", "-c", "http.lowSpeedTime=30"] + arguments,
                   cwd=directory, check=True, timeout=1800)


def ensure_clean(destination):
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                           cwd=destination, text=True, capture_output=True, check=True)
    if dirty.stdout.strip():
        raise RuntimeError(f"Pinned dependency has local changes: {destination}")


def materialize(package):
    destination = PROJECT / ".lake/packages" / package["name"]
    destination.mkdir(parents=True, exist_ok=True)
    if not (destination / ".git").exists():
        git(["init", "--quiet"], destination)
        git(["remote", "add", "origin", package["url"]], destination)
    ensure_clean(destination)
    current = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=destination,
                             text=True, capture_output=True)
    if current.returncode == 0 and current.stdout.strip() == package["rev"]:
        return
    print(f"Fetching {package['name']} at {package['rev']}", flush=True)
    git(["fetch", "--depth", "1", "--filter=blob:none", "origin", package["rev"]], destination)
    if package["name"] == "mathlib":
        git(["sparse-checkout", "init", "--cone"], destination)
        git(["sparse-checkout", "set", "Mathlib", "Cache"], destination)
    git(["checkout", "--detach", package["rev"]], destination)
    ensure_clean(destination)


def main():
    manifest = json.loads((PROJECT / "lake-manifest.json").read_text(encoding="utf-8"))
    for package in manifest["packages"]:
        materialize(package)


if __name__ == "__main__":
    main()

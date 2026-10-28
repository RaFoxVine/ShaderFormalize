"""One repository-local Lean toolchain and environment for every numeric model."""
import hashlib
import json
import os
from pathlib import Path

from shader_ast import ModelError


ROOT = Path(__file__).resolve().parent.parent
PROOF = ROOT / "proof"


def toolchain_lock():
    return json.loads((ROOT / "dependencies.lock.json").read_text(encoding="utf-8-sig"))["lean"]


def lean_bin():
    return ROOT / ".tools" / ("lean-" + toolchain_lock()["version"] + "-windows") / "bin"


def validate_lean(directory=None):
    directory = lean_bin() if directory is None else Path(directory)
    for name, expected in toolchain_lock()["binaries"].items():
        path = directory / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ModelError(f"Pinned Lean file missing/changed: {name}", "ENVIRONMENT_ERROR")
    return directory / "lake.exe"


def local_environment():
    environment = os.environ.copy()
    for name in list(environment):
        if name.startswith("LEAN_") or name == "FLOATLIB_BUILD_DIR":
            environment.pop(name, None)
    environment["PATH"] = str(lean_bin()) + os.pathsep + environment.get("PATH", "")
    environment["MATHLIB_CACHE_DIR"] = str(ROOT / ".cache/mathlib")
    environment["LAKE_HOME"] = str(ROOT / ".cache/lake")
    environment["ELAN_HOME"] = str(ROOT / ".tools/elan")
    environment["MATHLIB_NO_CACHE_ON_UPDATE"] = "1"
    environment["CURL_HOME"] = str(ROOT / ".cache/curl")
    count = int(environment.get("GIT_CONFIG_COUNT", "0"))
    for key, value in (("http.sslBackend", "schannel"), ("http.version", "HTTP/1.1")):
        environment[f"GIT_CONFIG_KEY_{count}"] = key
        environment[f"GIT_CONFIG_VALUE_{count}"] = value
        count += 1
    environment["GIT_CONFIG_COUNT"] = str(count)
    return environment

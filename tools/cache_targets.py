"""Find the Mathlib import roots needed by both shader models and their proofs."""
from pathlib import Path
import re

from lean_environment import ROOT, PROOF


IMPORT = re.compile(r"^(?:public\s+)?(?:meta\s+)?import\s+([A-Za-z0-9_.]+)", re.MULTILINE)


def cache_targets():
    floatlib = PROOF / ".lake/packages/floatlib"
    pending = list(PROOF.glob("*.lean")) + list((PROOF / "ShaderFormalize").glob("*.lean"))
    pending += list((PROOF / "ShaderIeee").glob("*.lean"))
    # These imports are emitted conditionally by the real-number generator.
    targets = {"Mathlib.Data.Real.Archimedean", "Mathlib.Algebra.Order.Floor.Ring"}
    seen = set()
    while pending:
        path = pending.pop()
        if path in seen or path.name in ("GeneratedModel.lean", "SubmittedProof.lean", "Verify.lean"):
            continue
        seen.add(path)
        for module in IMPORT.findall(path.read_text(encoding="utf-8")):
            if module == "Mathlib" or module.startswith("Mathlib."):
                targets.add(module)
            elif module.startswith("FloatLib."):
                pending.append(floatlib / (module.replace(".", "/") + ".lean"))
    return sorted(targets)


if __name__ == "__main__":
    for module in cache_targets():
        print(module)

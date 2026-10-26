"""List Mathlib cache roots required by the prototype's narrow FloatLib imports."""
from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parent
FLOATLIB = PROJECT / ".lake/packages/floatlib"
IMPORT = re.compile(r"^(?:public\s+)?(?:meta\s+)?import\s+([A-Za-z0-9_.]+)", re.MULTILINE)


def main():
    pending = [PROJECT / "Main.lean"]
    seen = set()
    targets = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        for name in IMPORT.findall(path.read_text(encoding="utf-8")):
            if name == "Mathlib" or name.startswith("Mathlib."):
                targets.add(name)
            elif name.startswith("FloatLib."):
                pending.append(FLOATLIB / (name.replace(".", "/") + ".lean"))
    for name in sorted(targets):
        print(name)


if __name__ == "__main__":
    main()

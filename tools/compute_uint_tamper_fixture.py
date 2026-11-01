"""Acceptance mutation after actual Verify; restoration stays under workspace lock."""
import sys

import computeformalize as cf


def main():
    mode = sys.argv.pop(1)
    if mode not in ("target", "semantic"):
        raise ValueError("Expected target or semantic mutation")
    relative = "ShaderComputeUint/GeneratedModel.lean" if mode == "target" else "ShaderFormalize/ComputeMemory.lean"
    target = cf.PROOF / relative
    saved = None
    run = cf.run_tool
    check = cf.check

    def mutate_after_verify(arguments, *args, **kwargs):
        nonlocal saved
        result = run(arguments, *args, **kwargs)
        if str(arguments[-1]) == "ShaderComputeUint/Verify.lean" and result[0].returncode == 0:
            saved = target.read_bytes()
            target.write_bytes(saved + b"\n-- acceptance mutation\n")
        return result

    def restoring_check(*args, **kwargs):
        # uint_main calls check inside workspace_lock, so recovery precedes release.
        try:
            return check(*args, **kwargs)
        finally:
            if saved is not None:
                target.write_bytes(saved)

    cf.run_tool = mutate_after_verify
    cf.check = restoring_check
    return cf.main()


if __name__ == "__main__":
    sys.exit(main())

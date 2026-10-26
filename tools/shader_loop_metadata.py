"""Audit exact static expansion counts; never use them as value assumptions."""
from shader_ast import ModelError


def validate_loops(model):
    if "loops" not in model and "loop_semantics" not in model:
        return
    if model.get("loop_semantics") != "exact-static-uint-for-v1":
        raise ModelError("Unknown loop semantics")
    frames = model.get("loops")
    if not isinstance(frames, list) or not 1 <= len(frames) <= 128:
        raise ModelError("Invalid loop frame metadata")
    seen = set()
    for frame in frames:
        if not isinstance(frame, dict) or set(frame) != {"frame", "regions"}:
            raise ModelError("Invalid loop frame")
        key = frame["frame"]
        if not (key == "main" or (type(key) is int and 0 <= key < len(model["helpers"]))):
            raise ModelError("Invalid loop helper reference")
        if key in seen or not isinstance(frame["regions"], list) or not frame["regions"]:
            raise ModelError("Repeated or empty loop frame")
        seen.add(key)
        steps = 0
        for region in frame["regions"]:
            if not isinstance(region, dict) or set(region) != {"line", "column", "start", "end", "count"}:
                raise ModelError("Invalid static loop region")
            if any(type(region[name]) is not int for name in region):
                raise ModelError("Loop metadata numbers must be integers")
            if (region["line"] < 1 or region["column"] < 1
                    or not 0 <= region["start"] < 2**32 or not 0 <= region["end"] < 2**32
                    or region["count"] != max(region["end"] - region["start"], 0)
                    or not 0 <= region["count"] <= 64):
                raise ModelError("Loop count does not describe exact terminating uint iterations")
            steps += region["count"]
        if steps > 4096:
            raise ModelError("Loop metadata exceeds frame expansion budget")

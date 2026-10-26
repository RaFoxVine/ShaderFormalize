"""Validate and bind logical aggregate input layouts, independently of values."""
import re

from shader_ast import ModelError


def integer(value, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ModelError("Invalid aggregate dimension")


def validate_metadata(model):
    shapes = model.get("aggregate_types", {})
    if not isinstance(shapes, dict) or len(shapes) > 320:
        raise ModelError("Invalid aggregate type table")
    for name, shape in shapes.items():
        if not isinstance(name, str) or not isinstance(shape, dict):
            raise ModelError("Invalid aggregate type declaration")
        if shape.get("kind") == "matrix" and set(shape) == {"kind", "rows", "columns"}:
            integer(shape["rows"], 1, 4)
            integer(shape["columns"], 1, 4)
            if name != f"$matrix{shape['rows']}x{shape['columns']}":
                raise ModelError("Noncanonical matrix type identity")
        elif shape.get("kind") == "array" and set(shape) == {"kind", "length", "element"}:
            integer(shape["length"], 1, 64)
            element = shape["element"]
            if not ((type(element) is int and 1 <= element <= 4) or (isinstance(element, str) and len(element) <= 4096)):
                raise ModelError("Invalid array element metadata")
            if name != f"$array{shape['length']}<{element}>":
                raise ModelError("Noncanonical array type identity")
        elif shape.get("kind") == "struct" and set(shape) == {"kind", "fields"}:
            if (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None
                    or not isinstance(shape["fields"], list) or not 1 <= len(shape["fields"]) <= 64):
                raise ModelError("Invalid record type identity/fields")
            names = set()
            for field in shape["fields"]:
                if (not isinstance(field, dict) or set(field) != {"name", "type"}
                        or not isinstance(field["name"], str)
                        or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field["name"]) is None or field["name"] in names):
                    raise ModelError("Invalid record field identity")
                names.add(field["name"])
        else:
            raise ModelError("Unknown aggregate type shape")
    if sum(s["kind"] == "struct" for s in shapes.values()) > 64 or sum(s["kind"] != "struct" for s in shapes.values()) > 256:
        raise ModelError("Aggregate/source record type budget exceeded")
    completed = {}
    for name in shapes:
        check_shape(name, shapes, set(), completed)
    layouts, groups = model.get("uniform_layout", []), model.get("input_groups", {})
    if not isinstance(layouts, list) or len(layouts) > 64 or not isinstance(groups, dict):
        raise ModelError("Invalid aggregate input metadata")
    for path, indices in groups.items():
        if (not isinstance(path, str) or not isinstance(indices, list) or not indices
                or any(type(i) is not int or not 0 <= i < len(model["interface"]) for i in indices)
                or len(set(indices)) != len(indices)):
            raise ModelError("Invalid flattened input group")
    if not layouts:
        if groups:
            raise ModelError("Input groups require an explicit uniform layout")
        return
    inputs = [item for item in model["interface"] if item["storage"] == "uniform"]
    actual_groups, leaves = {}, []
    for field in layouts:
        if not isinstance(field, dict) or set(field) != {"name", "layout"} or not isinstance(field["name"], str):
            raise ModelError("Invalid uniform field layout")
        flatten_layout(field["layout"], field["name"], inputs, leaves, actual_groups, 0)
    if leaves != [(item["name"], item["width"]) for item in inputs] or groups != actual_groups:
        raise ModelError("Uniform layout/groups disagree with flattened inputs")


def check_shape(kind, shapes, ancestors, completed):
    if (type(kind) is int and 1 <= kind <= 4) or kind in ("bool", "uint"):
        return 0, 1
    if not isinstance(kind, str) or kind not in shapes or kind in ancestors:
        raise ModelError("Unknown or recursive aggregate type reference")
    if kind in completed:
        return completed[kind]
    if len(ancestors) >= 16:
        raise ModelError("Aggregate type depth exceeded")
    shape = shapes[kind]
    if shape["kind"] == "matrix":
        depth, leaves = 1, shape["rows"]
    elif shape["kind"] == "array":
        depth, leaves = check_shape(shape["element"], shapes, ancestors | {kind}, completed)
        depth, leaves = depth + 1, leaves * shape["length"]
    else:
        children = [check_shape(field["type"], shapes, ancestors | {kind}, completed) for field in shape["fields"]]
        depth, leaves = 1 + max(item[0] for item in children), sum(item[1] for item in children)
    if depth > 16 or leaves > 4096:
        raise ModelError("Aggregate shape depth/leaf budget exceeded")
    completed[kind] = depth, leaves
    return depth, leaves


def flatten_layout(layout, path, inputs, leaves, groups, depth):
    if depth > 16 or not isinstance(layout, dict) or path in groups:
        raise ModelError("Invalid or duplicate nested uniform layout")
    start = len(leaves)
    kind = layout.get("kind")
    if kind == "float" and set(layout) == {"kind", "width"}:
        integer(layout["width"], 1, 4)
        if len(leaves) >= 64:
            raise ModelError("Excessive flattened uniform layout")
        leaves.append((path, layout["width"]))
    elif kind == "matrix" and set(layout) == {"kind", "rows", "columns", "packing"}:
        integer(layout["rows"], 1, 4)
        integer(layout["columns"], 1, 4)
        if layout["packing"] not in ("row_major", "column_major"):
            raise ModelError("Unknown matrix packing")
        for i in range(layout["rows"]):
            flatten_layout({"kind": "float", "width": layout["columns"]}, f"{path}[{i}]", inputs, leaves, groups, depth + 1)
    elif kind == "array" and set(layout) == {"kind", "length", "element"}:
        integer(layout["length"], 1, 64)
        for i in range(layout["length"]):
            flatten_layout(layout["element"], f"{path}[{i}]", inputs, leaves, groups, depth + 1)
    elif kind == "struct" and set(layout) == {"kind", "type", "fields"}:
        if not isinstance(layout["type"], str) or not isinstance(layout["fields"], list) or not 1 <= len(layout["fields"]) <= 64:
            raise ModelError("Invalid uniform struct layout")
        names = set()
        for field in layout["fields"]:
            if (not isinstance(field, dict) or set(field) != {"name", "layout"}
                    or not isinstance(field["name"], str) or field["name"] in names):
                raise ModelError("Invalid uniform struct field")
            names.add(field["name"])
            flatten_layout(field["layout"], path + "." + field["name"], inputs, leaves, groups, depth + 1)
    else:
        raise ModelError("Unknown uniform logical layout")
    if len(leaves) > len(inputs):
        raise ModelError("Uniform layout has too many leaves")
    groups[path] = [item["index"] for item in inputs[start:len(leaves)]]

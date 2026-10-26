"""Typed source destinations with indices captured once before copy-out."""
import re

from shader_ast import ModelError, quoted, source_header
from shader_aggregate_values import components, constant_ast, constant_value, vector
from shader_frontend import swizzle_indices
from shader_packing import has_payload
from shader_types import component_mask, initialized, operation, value_type


def index_parts(node, types):
    if node.kind == "ArraySubscriptExpr" and len(node.children) == 2:
        receiver, index = node.children
        owner = types.node_type(receiver)
        if owner not in types.aggregates or types.aggregates[owner]["kind"] != "array":
            raise ModelError("ArraySubscriptExpr must index a fixed array")
    elif node.kind == "CXXOperatorCallExpr" and len(node.children) == 3:
        callee, receiver, index = node.children
        owner = types.node_type(receiver)
        if not (isinstance(owner, int) or (owner in types.aggregates and types.aggregates[owner]["kind"] == "matrix")):
            raise ModelError("Only DXC vector/matrix builtin operator[] is supported")
        if (callee.kind != "ImplicitCastExpr" or not callee.text.endswith("<FunctionToPointerDecay>")
                or len(callee.children) != 1):
            raise ModelError("Malformed builtin indexing callee")
        method = callee.children[0]
        signature = quoted(method.text)
        if (method.kind != "DeclRefExpr" or method.children or len(signature) != 3
                or signature[1] != "operator[]" or signature[0] != signature[2]
                or not re.search(r"\bCXXMethod 0x[0-9a-fA-F]+ ", method.text)):
            raise ModelError("Index callee is not the pinned DXC builtin method")
        match = re.fullmatch(r"(.+) &\((?:unsigned int|uint)\)( const)?", signature[0])
        if match is None or types.named_type(match.group(1)) != types.node_type(node):
            raise ModelError("Builtin index method result/signature mismatch")
        expected_pointer = match.group(1) + " &(*)(unsigned int)" + (match.group(2) or "")
        if quoted(callee.text)[0].replace("uint", "unsigned int") != expected_pointer:
            raise ModelError("Builtin index method decay mismatch")
    else:
        raise ModelError("Unsupported index syntax")
    size, child_type = types.element_type(owner)
    if types.node_type(node) != child_type or types.node_type(index) not in ("uint", "literal_int"):
        raise ModelError("Index result or index type mismatch")
    return receiver, index, owner, size, child_type


class AddressSpec:
    def __init__(self, root, root_type, steps, kind, program, identity=None):
        self.root, self.root_type, self.steps, self.kind = root, root_type, steps, kind
        self.program = program
        self.identity = identity

    def index_nodes(self):
        return [step["node"] for step in self.steps if step["kind"] == "index"]

    def paths(self):
        paths, component_view = [()], False
        for step in self.steps:
            if step["kind"] == "field":
                paths = [path + (step["name"],) for path in paths]
                component_view = False
            elif step["kind"] == "components":
                if component_view:
                    paths = [paths[i] for i in step["indices"]]
                else:
                    paths = [path + (f"@{i}",) for path in paths for i in step["indices"]]
                component_view = len(step["indices"]) > 1
            else:
                constant = constant_ast(step["node"], self.program.source)
                if component_view:
                    paths = [paths[constant]] if constant is not None and constant < len(paths) else paths
                else:
                    segment = "@*" if constant is None else f"@{constant}"
                    paths = [path + (segment,) for path in paths]
                component_view = False
        return {(self.root, path) for path in paths}

    def capture(self, symbols):
        if self.root not in symbols:
            raise ModelError("Unknown address declaration")
        symbol = symbols[self.root]
        if symbol["type"] != self.root_type or (self.identity is not None and self.identity != (symbol["tag"], symbol["name"])):
            raise ModelError("Address root type mismatch")
        steps = []
        for step in self.steps:
            if step["kind"] != "index":
                steps.append(step)
                continue
            index = self.program.index_value(step["node"], symbols)
            constant = constant_value(index, self.program.bindings)
            checked = self.program.snapshot(dict(operation("bounded_index", "uint", [index]), size=step["size"]), "index.checked")
            steps.append(dict(step, value=checked, constant=constant))
        return CapturedAddress(self.program, symbol, steps, self.kind)


def describe(node, program, writable=False):
    types = program.types
    if node.kind == "ParenExpr" and len(node.children) == 1:
        return describe(node.children[0], program, writable)
    if (node.kind == "ImplicitCastExpr" and node.text.endswith("<LValueToRValue>") and len(node.children) == 1
            and types.node_type(node) == types.node_type(node.children[0])):
        return describe(node.children[0], program, writable)
    if node.kind == "DeclRefExpr" and not node.children:
        match = re.search(r"\b(ParmVar|Var) (0x[0-9a-fA-F]+) '([A-Za-z_][A-Za-z0-9_]*)'", source_header(node.text).group("tail"))
        if match is None:
            raise ModelError("Address root is not a variable")
        kind = types.node_type(node)
        return AddressSpec(match.group(2), kind, [], kind, program, (match.group(1), match.group(3)))
    if node.kind == "MemberExpr" and len(node.children) == 1:
        base = describe(node.children[0], program, writable)
        field = types.member(node, base.kind)
        return AddressSpec(base.root, base.root_type, base.steps + [
            {"kind": "field", "owner": base.kind, "name": field["name"], "type": field["type"]}], field["type"], program, base.identity)
    if node.kind in ("ArraySubscriptExpr", "CXXOperatorCallExpr"):
        receiver, index, owner, size, kind = index_parts(node, types)
        base = describe(receiver, program, writable)
        return AddressSpec(base.root, base.root_type, base.steps + [
            {"kind": "index", "owner": owner, "node": index, "size": size, "type": kind}], kind, program, base.identity)
    if node.kind == "HLSLVectorElementExpr" and len(node.children) == 1:
        base = describe(node.children[0], program, writable)
        if not isinstance(base.kind, int):
            raise ModelError("Component address receiver is not a float vector")
        indices = swizzle_indices(component_mask(node), base.kind)
        if writable and len(set(indices)) != len(indices):
            raise ModelError("Writable swizzles cannot repeat components")
        kind = types.node_type(node)
        if kind != len(indices):
            raise ModelError("Component address type mismatch")
        return AddressSpec(base.root, base.root_type, base.steps + [
            {"kind": "components", "owner": base.kind, "indices": indices, "type": kind}], kind, program, base.identity)
    raise ModelError("Expected a typed local/field/element destination")


class CapturedAddress:
    def __init__(self, program, symbol, steps, kind):
        self.program, self.symbol, self.steps, self.kind = program, symbol, steps, kind

    def name(self):
        return self.symbol["name"]

    def condition(self, step, index):
        value = {"kind": "uint_literal", "width": "uint", "value": index}
        return dict(operation("compare", "bool", [step["value"], value]), operator="==")

    def element(self, value, owner, index):
        if isinstance(owner, int):
            return components(value, owner)[index]
        return value["fields"][self.program.types.element_name(owner, index)]

    def replace_element(self, value, owner, index, replacement):
        if isinstance(owner, int):
            if has_payload(replacement):
                raise ModelError("Bit carriers cannot be vector components")
            values = list(components(value, owner))
            values[index] = replacement
            return vector(values)
        fields = dict(value["fields"])
        fields[self.program.types.element_name(owner, index)] = replacement
        return dict(value, fields=fields)

    def read_from(self, value, steps):
        if not steps:
            return initialized(value)
        step, rest = steps[0], steps[1:]
        if step["kind"] == "field":
            return self.read_from(value["fields"][step["name"]], rest)
        if step["kind"] == "components":
            if not rest and value is not None and value["kind"] != "partial_vector":
                return dict(operation("swizzle", len(step["indices"]), [initialized(value)]), indices=step["indices"])
            parts = components(value, step["owner"])
            return self.read_from(vector([parts[i] for i in step["indices"]]), rest)
        constant = step["constant"]
        if constant is not None:
            # The captured bounded_index separately proves this fallback unused.
            index = constant if constant < step["size"] else 0
            return self.read_from(self.element(value, step["owner"], index), rest)
        result = self.read_from(self.element(value, step["owner"], step["size"] - 1), rest)
        for i in reversed(range(step["size"] - 1)):
            item = self.read_from(self.element(value, step["owner"], i), rest)
            result = self.program.select(self.condition(step, i), item, result, "index.read")
        return result

    def ensure_target_initialized(self, value, steps):
        if not steps:
            initialized(value)
            return
        step, rest = steps[0], steps[1:]
        if step["kind"] == "field":
            self.ensure_target_initialized(value["fields"][step["name"]], rest)
        elif step["kind"] == "components":
            parts = components(value, step["owner"])
            self.ensure_target_initialized(vector([parts[i] for i in step["indices"]]), rest)
        else:
            indices = range(step["size"]) if step["constant"] is None else [min(step["constant"], step["size"] - 1)]
            for index in indices:
                self.ensure_target_initialized(self.element(value, step["owner"], index), rest)

    def write_to(self, value, steps, replacement):
        if not steps:
            return replacement
        step, rest = steps[0], steps[1:]
        if step["kind"] == "field":
            fields = dict(value["fields"])
            fields[step["name"]] = self.write_to(fields[step["name"]], rest, replacement)
            return dict(value, fields=fields)
        if step["kind"] == "components":
            if has_payload(replacement):
                raise ModelError("Bit carriers cannot be vector components")
            parts = list(components(value, step["owner"]))
            selected = vector([parts[i] for i in step["indices"]])
            changed = self.write_to(selected, rest, replacement)
            writes = components(changed, len(step["indices"]))
            for index, item in zip(step["indices"], writes):
                parts[index] = item
            return vector(parts)
        constant = step["constant"]
        if constant is not None:
            if constant >= step["size"]:
                return value
            old = self.element(value, step["owner"], constant)
            return self.replace_element(value, step["owner"], constant, self.write_to(old, rest, replacement))
        result = value
        for i in range(step["size"]):
            old = self.element(value, step["owner"], i)
            self.ensure_target_initialized(old, rest)
            changed = self.write_to(old, rest, replacement)
            selected = self.program.select(self.condition(step, i), changed, old, "index.write")
            result = self.replace_element(result, step["owner"], i, selected)
        return result

    def read(self):
        return self.read_from(self.symbol["value"], self.steps)

    def write(self, value):
        if not self.symbol["writable"] or value_type(initialized(value)) != self.kind:
            raise ModelError("Address is read-only or replacement has another type")
        self.symbol["value"] = self.write_to(self.symbol["value"], self.steps, value)

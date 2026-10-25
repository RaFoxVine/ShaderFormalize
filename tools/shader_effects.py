"""Typed resource/method and clipping rules shared by validation and execution."""
import re

from shader_ast import ModelError, quoted, source_header
from shader_types import declaration_name, identifier

DERIVATIVES = {"ddx", "ddy", "ddx_fine", "ddy_fine", "ddx_coarse", "ddy_coarse"}
COMPARISONS = {"<", "<=", ">", ">=", "==", "!="}
SAMPLE_ARGUMENTS = {"Sample": [2], "SampleLevel": [2, 1], "SampleGrad": [2, 2, 2]}


class Resources:
    def __init__(self, nodes, types):
        self.by_id = {}
        self.layout = []
        slots, names = set(), set()
        for node in nodes:
            kind = types.node_type(node)
            if kind not in ("Texture2D", "SamplerState") or len(node.children) != 1:
                raise ModelError("Only global Texture2D<float4>/SamplerState resources are supported")
            register = node.children[0]
            match = re.fullmatch(r" register\(([ts])([0-9]+)\)", source_header(register.text).group("tail"))
            if register.kind != "RegisterAssignment" or register.children or match is None:
                raise ModelError("Resources require explicit register(tN)/register(sN)")
            slot = match.group(1) + str(int(match.group(2)))
            if match.group(1) != ("t" if kind == "Texture2D" else "s") or slot in slots:
                raise ModelError("Resource register kind/identity mismatch")
            name = declaration_name(node)
            if name in names or sum(item["type"] == kind for item in self.layout) >= 16:
                raise ModelError("Repeated or excessive resource declarations")
            # A declaration with initialization/other flags is not a plain resource.
            if source_header(node.text).group("tail").rpartition("'")[2].strip():
                raise ModelError("Unsupported resource declaration flags")
            item = {"name": name, "type": kind, "register": slot}
            slots.add(slot)
            names.add(name)
            self.by_id[identifier(node)] = item
            self.layout.append(item)

    def reference(self, node, expected, types):
        if expected == "SamplerState":
            if node.kind != "ImplicitCastExpr" or len(node.children) != 1 or not node.text.endswith("<LValueToRValue>"):
                raise ModelError("Expected a global sampler reference")
            if types.node_type(node) != expected:
                raise ModelError("Sampler conversion type mismatch")
            node = node.children[0]
        match = re.search(r"\blvalue Var (0x[0-9a-fA-F]+) '([A-Za-z_][A-Za-z0-9_]*)'", source_header(node.text).group("tail"))
        if node.kind != "DeclRefExpr" or node.children or match is None:
            raise ModelError("Resource aliases/parameters are unsupported")
        item = self.by_id.get(match.group(1))
        if item is None or item["name"] != match.group(2) or item["type"] != expected or types.node_type(node) != expected:
            raise ModelError("Resource reference identity/type mismatch")
        return item["name"]

    def sample(self, node, types):
        if node.kind != "CXXMemberCallExpr" or not node.children or types.node_type(node) != 4:
            raise ModelError("Expected a float4 texture sampling call")
        member = node.children[0]
        match = re.search(r" '<bound member function type>' \.([A-Za-z_][A-Za-z0-9_]*) 0x[0-9a-fA-F]+$", member.text)
        if member.kind != "MemberExpr" or len(member.children) != 1 or match is None:
            raise ModelError("Unsupported texture member reference")
        mode = match.group(1)
        if mode not in SAMPLE_ARGUMENTS or len(node.children) != len(SAMPLE_ARGUMENTS[mode]) + 2:
            raise ModelError("Unsupported sampling method/overload")
        texture = self.reference(member.children[0], "Texture2D", types)
        sampler = self.reference(node.children[1], "SamplerState", types)
        arguments = node.children[2:]
        if [types.node_type(child) for child in arguments] != SAMPLE_ARGUMENTS[mode]:
            raise ModelError("Unsupported texture sampling argument types")
        return mode, texture, sampler, arguments


def discard_condition(node, program):
    if node.kind != "IfStmt" or len(node.children) != 4:
        raise ModelError("Only if(comparison) discard is supported")
    initializer, condition, body, otherwise = node.children
    if initializer.kind != "Null" or otherwise.kind != "Null":
        raise ModelError("If initializers and else branches are unsupported")
    if body.kind == "CompoundStmt" and len(body.children) == 1:
        body = body.children[0]
    if body.kind != "DiscardStmt" or body.children:
        raise ModelError("Only a single discard is supported in a branch")
    if condition.kind != "BinaryOperator" or len(condition.children) != 2 or program.types.node_type(condition) != "bool":
        raise ModelError("Discard condition requires one scalar real comparison")
    if quoted(condition.text)[-1] not in COMPARISONS or any(program.types.node_type(c) != 1 for c in condition.children):
        raise ModelError("Discard condition requires one scalar real comparison")
    return condition

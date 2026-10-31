"""Shared persistent local destinations, partial joins and fixed-array values."""
import re
from shader_ast import ModelError
from shader_addresses import describe, index_parts
from shader_aggregate_values import components, vector
from shader_types import value_type


def rooted(node):
    if node.kind == "DeclRefExpr":
        return re.search(r"\b(?:ParmVar|Var) 0x[0-9a-fA-F]+ ", node.text) is not None
    if node.kind in ("ParenExpr", "ImplicitCastExpr", "MemberExpr", "HLSLVectorElementExpr") and len(node.children) == 1:
        return rooted(node.children[0])
    if node.kind == "ArraySubscriptExpr" and len(node.children) == 2:
        return rooted(node.children[0])
    if node.kind == "CXXOperatorCallExpr" and len(node.children) == 3:
        return rooted(node.children[1])
    return False


class LocalValues:
    def address_spec(self, node, writable=False):
        return describe(node, self, writable)

    def access_address(self, node):
        if node.kind in ("DeclRefExpr", "MemberExpr", "HLSLVectorElementExpr", "ArraySubscriptExpr", "CXXOperatorCallExpr") and rooted(node):
            return self.address_spec(node)
        return None

    def index_operands(self, node):
        receiver, index, _, _, _ = index_parts(node, self.types)
        return [receiver, index]

    def address_type(self, node):
        spec = self.address_spec(node, True)
        for index in spec.index_nodes():
            self.validate_index(index)
        return spec.kind

    def validate_index(self, node):
        from shader_validation import validate_expression
        validate_expression(node, self)

    def capture_destination(self, node, symbols):
        return self.address_spec(node, True).capture(symbols)

    def select(self, condition, yes, no, name):
        if (yes is not None and no is not None and
                (yes["kind"] == "partial_vector" or no["kind"] == "partial_vector")):
            if value_type(yes) != value_type(no):
                raise ModelError("Partial vector join type mismatch")
            parts = [self.select(condition, a, b, name + f".{i}")
                     for i, (a, b) in enumerate(zip(components(yes, value_type(yes)), components(no, value_type(no))))]
            return vector(parts, value_type(yes))
        return super().select(condition, yes, no, name)

    def validate_array_initializer(self, node, kind):
        from shader_validation import validate_expression
        shape = self.types.aggregates.get(kind)
        if shape is not None and shape["kind"] == "array":
            if node.kind != "InitListExpr" or len(node.children) != shape["length"]:
                raise ModelError("Arrays require one complete initializer per element")
            # Pinned DXC marks nested array InitListExpr as void: the checked
            # parent shape supplies the element type, never a guessed source cast.
            for child in node.children:
                if shape["element"] in self.types.aggregates and self.types.aggregates[shape["element"]]["kind"] == "array":
                    self.validate_array_initializer(child, shape["element"])
                else:
                    validate_expression(child, self)
                    if self.types.node_type(child) != shape["element"]:
                        raise ModelError("Array initializer element type mismatch")
            return
        raise ModelError("Unsupported array initializer")

    def array_initializer(self, node, kind, symbols):
        shape = self.types.aggregates[kind]
        if shape["kind"] == "array":
            fields = {}
            for i, child in enumerate(node.children):
                child_kind = shape["element"]
                fields[f"e{i}"] = (self.array_initializer(child, child_kind, symbols)
                    if child_kind in self.types.aggregates and self.types.aggregates[child_kind]["kind"] == "array"
                    else self.expression(child, symbols))
        return {"kind": "record", "type": kind, "fields": fields}

"""Logical matrix/array shapes lowered to the existing numeric record leaves."""
import re

from shader_ast import ModelError, quoted
from shader_array_types import FixedArrayTypes
from shader_copyback import CopybackTypes
from shader_types import identifier


def packing(node):
    name = quoted(node.text)[0]
    return "row_major" if re.search(r"\brow_major\b", name) else "column_major"


def clean_type(name):
    return re.sub(r"\s+", " ", re.sub(r"\b(const|row_major|column_major|__restrict)\b", "", name)).strip()


class AggregateTypes(FixedArrayTypes, CopybackTypes):
    def __init__(self, declarations, allow_bool=False):
        self.aggregates = {}
        self.ready_shapes = False
        super().__init__(declarations, allow_bool)
        for record in list(self.records.values()):
            if record["node"] is not None:
                nodes = {identifier(n): n for n in record["node"].children if n.kind == "FieldDecl"}
                for field in record["fields"]:
                    field["packing"] = packing(nodes[field["id"]])
        self.ready_shapes = True

    def named_type(self, name):
        name = clean_type(name)
        if "[" in name:
            return self.array_type(name)
        matrix = re.fullmatch(r"float([1-4])x([1-4])|matrix<\s*float\s*,\s*([1-4])\s*,\s*([1-4])\s*>", name)
        if matrix:
            rows, columns = int(matrix.group(1) or matrix.group(3)), int(matrix.group(2) or matrix.group(4))
            return self.register(f"$matrix{rows}x{columns}", {"kind": "matrix", "rows": rows, "columns": columns},
                                 [(f"r{i}", columns) for i in range(rows)])
        vector = re.fullmatch(r"float([1-4])|vector<\s*float\s*,\s*([1-4])\s*>", name)
        if vector:
            return int(vector.group(1) or vector.group(2))
        if name in ("Texture2D", "Texture2D<float4>"):
            return "Texture2D"
        if name == "SamplerState":
            return name
        return super().named_type(name)

    def node_type(self, node):
        types = quoted(node.text)
        if not types:
            raise ModelError("Missing aggregate value type")
        name = clean_type(types[0])
        if "&" in name:
            if (node.kind != "ParmVarDecl" or not name.endswith("&")
                    or not any(n.kind in ("HLSLOutAttr", "HLSLInOutAttr") for n in node.children)):
                raise ModelError("Unexpected aggregate reference type")
            name = name[:-1].strip()
        if name == "literal int" and node.kind == "IntegerLiteral":
            return "literal_int"
        if name == "literal float" and node.kind in ("FloatingLiteral", "ParenExpr", "BinaryOperator", "UnaryOperator"):
            return 1
        return self.named_type(name)

    def layout(self, kind):
        if kind in self.aggregates:
            raise ModelError("Matrix/array stage inputs are not supported")
        return super().layout(kind)

    def empty(self, kind):
        if isinstance(kind, int) and kind > 1:
            return {"kind": "partial_vector", "width": kind, "components": [None] * kind}
        return super().empty(kind)

    def uniform_layout(self, kind, order="column_major"):
        shape = self.aggregates.get(kind)
        if shape is not None:
            if shape["kind"] == "matrix":
                return dict(shape, packing=order)
            return {"kind": "array", "length": shape["length"], "element": self.uniform_layout(shape["element"], order)}
        if isinstance(kind, int):
            return {"kind": "float", "width": kind}
        if kind not in self.records:
            raise ModelError("Uniform leaves must be float/vector values")
        return {"kind": "struct", "type": kind, "fields": [
            {"name": field["name"], "layout": self.uniform_layout(field["type"], field.get("packing", order))}
            for field in self.records[kind]["fields"]]}

    def element_type(self, kind):
        if isinstance(kind, int):
            return kind, 1
        shape = self.aggregates.get(kind)
        if shape is None:
            raise ModelError("Index receiver must be a vector, matrix or fixed array")
        return ((shape["rows"], shape["columns"]) if shape["kind"] == "matrix"
                else (shape["length"], shape["element"]))

    def element_name(self, kind, index):
        return ("r" if self.aggregates[kind]["kind"] == "matrix" else "e") + str(index)

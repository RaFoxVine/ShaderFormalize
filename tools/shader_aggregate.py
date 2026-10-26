"""Shared HLSL aggregates, numeric lowering and captured local destinations."""
import re

from shader_ast import ModelError, literal, quoted
from shader_addresses import CapturedAddress, describe, index_parts
from shader_aggregate_types import AggregateTypes, packing
from shader_aggregate_values import components, constant_ast, constant_value, vector
from shader_copyback import CopybackProgram
from shader_frontend import buffer_declaration, callee_reference, make_symbol, swizzle_indices
from shader_packing import uint_literal
from shader_control_values import zero_value
from shader_types import component_mask, declaration_name, identifier, initialized, operation, reference, value_type


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


class AggregateProgram(CopybackProgram):
    type_registry = AggregateTypes

    def __init__(self, source, dump):
        self.uniform_layouts, self.input_groups = [], {}
        super().__init__(source, dump)

    def read_buffer(self, node):
        return buffer_declaration(node, check_numeric=False)

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
        from shader_validation import validate_expression
        spec = self.address_spec(node, True)
        for index in spec.index_nodes():
            validate_expression(index, self)
        return spec.kind

    def capture_destination(self, node, symbols):
        return self.address_spec(node, True).capture(symbols)

    def index_value(self, node, symbols):
        if self.types.node_type(node) == "literal_int":
            value = constant_ast(node, self.source)
            if value is None:
                raise ModelError("Only unsigned or literal indices are supported")
            return {"kind": "uint_literal", "width": "uint", "value": value}
        value = self.expression(node, symbols)
        if value_type(initialized(value)) != "uint":
            raise ModelError("Index expression must be uint")
        return value

    def prepare_function_validation(self):
        super().prepare_function_validation()
        self.types.shapes = {}
        for kind in list(self.types.records):
            self.types.check_shape(kind, [])

    def uniform_value(self, kind, path, interface):
        start = len(interface)
        if isinstance(kind, int):
            if len(interface) >= 64:
                raise ModelError("More than 64 flattened input leaves")
            index = len(interface)
            interface.append({"index": index, "name": path, "width": kind, "semantic": None,
                              "storage": "uniform", "buffer": self.buffer["name"], "register": self.buffer["register"]})
            value = reference("parameter", kind, index)
        elif kind in self.types.records:
            shape = self.types.aggregates.get(kind)
            fields = {}
            for i, field in enumerate(self.types.records[kind]["fields"]):
                child_path = path + (f"[{i}]" if shape else "." + field["name"])
                fields[field["name"]] = self.uniform_value(field["type"], child_path, interface)
            value = {"kind": "record", "type": kind, "fields": fields}
        else:
            raise ModelError("Only float/vector leaves are supported in uniform aggregates")
        self.input_groups[path] = list(range(start, len(interface)))
        return value

    def uniform_inputs(self, interface):
        kinds = [self.types.node_type(field) for field in self.fields]
        if all(isinstance(kind, int) for kind in kinds):
            return super().uniform_inputs(interface)
        for field, kind in zip(self.fields, kinds):
            name = declaration_name(field)
            self.types.check_shape(kind, [])
            layout = self.types.uniform_layout(kind, packing(field))
            self.uniform_layouts.append({"name": name, "layout": layout})
            value = self.uniform_value(kind, name, interface)
            self.globals[identifier(field)] = make_symbol(name, kind, "Var", False, value)

    def model(self):
        model = super().model()
        if self.types.aggregates:
            shapes = dict(self.types.aggregates)
            for name, record in self.types.records.items():
                if record["node"] is not None:
                    shapes[name] = {"kind": "struct", "fields": [
                        {"name": field["name"], "type": field["type"]} for field in record["fields"]]}
            model["aggregate_types"] = shapes
        if self.uniform_layouts:
            model.update(uniform_layout=self.uniform_layouts, input_groups=self.input_groups)
        return model

    def select(self, condition, yes, no, name):
        if (yes is not None and no is not None and
                (yes["kind"] == "partial_vector" or no["kind"] == "partial_vector")):
            if value_type(yes) != value_type(no):
                raise ModelError("Partial vector join type mismatch")
            parts = [self.select(condition, a, b, name + f".{i}")
                     for i, (a, b) in enumerate(zip(components(yes, value_type(yes)), components(no, value_type(no))))]
            return vector(parts)
        return super().select(condition, yes, no, name)

    def validate_statement(self, node, result_type, effects_allowed):
        from shader_validation import validate_expression
        if node.kind not in ("BinaryOperator", "CompoundAssignOperator") or len(node.children) != 2:
            return None
        kind = self.address_type(node.children[0])
        validate_expression(node.children[1], self)
        if self.types.node_type(node) != kind or self.types.node_type(node.children[1]) != kind:
            raise ModelError("Assignment source/destination types differ")
        if node.kind == "BinaryOperator":
            if quoted(node.text)[-1] != "=":
                raise ModelError("Only assignment is a supported expression statement")
        elif (not (isinstance(kind, int) or self.is_matrix(kind))
              or self.compound_operator(node) is None):
            raise ModelError("Unsupported aggregate compound assignment")
        return False

    def compound_operator(self, node):
        match = re.search(r" lvalue '(\+=|-=|\*=)' ComputeLHSTy=", node.text)
        return None if match is None else {"+=": "add", "-=": "subtract", "*=": "multiply"}[match.group(1)]

    def assign_statement(self, node, symbols):
        if node.kind not in ("BinaryOperator", "CompoundAssignOperator") or len(node.children) != 2:
            return False
        destination = self.capture_destination(node.children[0], symbols)
        if not destination.symbol["writable"]:
            raise ModelError("Cannot assign an input or uniform")
        value = self.expression(node.children[1], symbols)
        if node.kind == "CompoundAssignOperator":
            value = self.numeric_operation(self.compound_operator(node), destination.kind, [destination.read(), value])
        value = self.snapshot(initialized(value), self.assignment_name(destination))
        destination.write(value)
        return True

    def assignment_name(self, destination):
        if all(step["kind"] == "field" for step in destination.steps):
            return ".".join([destination.name()] + [step["name"] for step in destination.steps])
        return destination.name() + ".element"

    def is_matrix(self, kind):
        return kind in self.types.aggregates and self.types.aggregates[kind]["kind"] == "matrix"

    def numeric_operation(self, operator, kind, arguments):
        if self.is_matrix(kind):
            return {"kind": "record", "type": kind, "fields": {
                field["name"]: operation(operator, field["type"], [arg["fields"][field["name"]] for arg in arguments])
                for field in self.types.records[kind]["fields"]}}
        return operation(operator, kind, arguments)

    def validate_initializer(self, node, kind):
        from shader_validation import validate_expression
        shape = self.types.aggregates.get(kind)
        if shape is not None and shape["kind"] == "array":
            if node.kind != "InitListExpr" or len(node.children) != shape["length"]:
                raise ModelError("Arrays require one complete initializer per element")
            # Pinned DXC marks nested array InitListExpr as void: the checked
            # parent shape supplies the element type, never a guessed source cast.
            for child in node.children:
                if shape["element"] in self.types.aggregates and self.types.aggregates[shape["element"]]["kind"] == "array":
                    self.validate_initializer(child, shape["element"])
                else:
                    validate_expression(child, self)
                    if self.types.node_type(child) != shape["element"]:
                        raise ModelError("Array initializer element type mismatch")
            return
        if self.is_matrix(kind):
            sizes = []
            for child in node.children:
                validate_expression(child, self)
                sizes.append(self.types.node_type(child))
            if not all(isinstance(size, int) for size in sizes) or sum(sizes) != shape["rows"] * shape["columns"]:
                raise ModelError("Matrix initializer component count mismatch")
            return
        raise ModelError("Unsupported aggregate initializer")

    def initializer(self, node, kind, symbols):
        shape = self.types.aggregates[kind]
        if shape["kind"] == "array":
            fields = {}
            for i, child in enumerate(node.children):
                child_kind = shape["element"]
                fields[f"e{i}"] = (self.initializer(child, child_kind, symbols)
                    if child_kind in self.types.aggregates and self.types.aggregates[child_kind]["kind"] == "array"
                    else self.expression(child, symbols))
        else:
            values = []
            for child in node.children:
                value = self.expression(child, symbols)
                values.extend(components(value, value_type(value)))
            columns = shape["columns"]
            fields = {f"r{i}": vector(values[i * columns:(i + 1) * columns]) for i in range(shape["rows"])}
        return {"kind": "record", "type": kind, "fields": fields}

    def zero_initializer(self, node):
        if node.kind == "IntegerLiteral":
            return uint_literal(node, self.source)["value"] == 0
        if node.kind == "FloatingLiteral":
            return literal(node, self.source)["numerator"] == 0
        if (node.kind == "ImplicitCastExpr" and len(node.children) == 1
                and node.text.endswith(("<FloatingCast>", "<IntegralToFloating>"))):
            return self.zero_initializer(node.children[0])
        return False

    def validate_extension(self, node):
        from shader_validation import validate_expression
        kind, children = self.types.node_type(node), node.children
        valid = False
        if node.kind == "InitListExpr" and kind in self.types.aggregates:
            self.validate_initializer(node, kind)
            return True
        if node.kind in ("ArraySubscriptExpr", "CXXOperatorCallExpr"):
            receiver, index, _, _, _ = index_parts(node, self.types)
            validate_expression(receiver, self)
            validate_expression(index, self)
            return True
        if node.kind == "HLSLVectorElementExpr" and len(children) == 1:
            owner = self.types.node_type(children[0])
            valid = isinstance(owner, int) and isinstance(kind, int)
            if valid and len(swizzle_indices(component_mask(node), owner)) != kind:
                raise ModelError("Swizzle result type mismatch")
        if node.kind in ("CStyleCastExpr", "CXXFunctionalCastExpr") and len(children) == 1 and node.text.endswith("<NoOp>"):
            valid = self.types.is_value_type(kind) and self.types.node_type(children[0]) == kind
        if node.kind == "ImplicitCastExpr" and len(children) == 1:
            child_type = self.types.node_type(children[0])
            if node.text.endswith("<FlatConversion>") and kind in self.types.records and self.zero_initializer(children[0]):
                return True
            if node.text.endswith("<HLSLMatrixSplat>"):
                valid = self.is_matrix(kind) and child_type == 1
            if node.text.endswith("<HLSLMatrixTruncationCast>"):
                if not (self.is_matrix(kind) and self.is_matrix(child_type)):
                    raise ModelError("Matrix truncation requires two matrix shapes")
                a, b = self.types.aggregates[kind], self.types.aggregates[child_type]
                valid = a["rows"] <= b["rows"] and a["columns"] <= b["columns"]
            if node.text.endswith("<HLSLVectorSplat>") and kind == child_type == 1:
                valid = True
        if node.kind == "UnaryOperator" and self.is_matrix(kind) and len(children) == 1:
            valid = quoted(node.text)[-1] == "-" and self.types.node_type(children[0]) == kind
        if node.kind == "BinaryOperator" and self.is_matrix(kind) and len(children) == 2:
            valid = quoted(node.text)[-1] in ("+", "-", "*") and all(self.types.node_type(child) == kind for child in children)
        if valid:
            for child in children:
                validate_expression(child, self)
            return True
        return super().validate_extension(node)

    def matrix_type(self, rows, columns):
        return self.types.named_type(f"float{rows}x{columns}")

    def mul_type(self, kinds, result_kind):
        if len(kinds) != 2:
            raise ModelError("mul requires two operands")
        a, b = kinds
        if isinstance(a, int) and isinstance(b, int):
            if a == 1 or b == 1:
                return max(a, b)
            if a == b:
                return 1
        elif self.is_matrix(a) and isinstance(b, int):
            shape = self.types.aggregates[a]
            if b == 1 and result_kind == a:
                return a
            if b == shape["columns"]:
                return shape["rows"]
        elif isinstance(a, int) and self.is_matrix(b):
            shape = self.types.aggregates[b]
            if a == 1 and result_kind == b:
                return b
            if a == shape["rows"]:
                return shape["columns"]
        elif self.is_matrix(a) and self.is_matrix(b):
            lhs, rhs = self.types.aggregates[a], self.types.aggregates[b]
            if lhs["columns"] == rhs["rows"]:
                return self.matrix_type(lhs["rows"], rhs["columns"])
        raise ModelError("mul operand dimensions do not match")

    def math_name(self, kind):
        if isinstance(kind, int):
            return "float" if kind == 1 else f"float{kind}"
        if self.is_matrix(kind):
            shape = self.types.aggregates[kind]
            return f"float{shape['rows']}x{shape['columns']}"
        raise ModelError("Matrix intrinsics require float values")

    def checked_call(self, node):
        key, name, signature = callee_reference(node)
        if key in self.functions or name not in ("mul", "transpose"):
            return super().checked_call(node)
        kind = self.types.node_type(node)
        kinds = [self.types.node_type(child) for child in node.children[1:]]
        if name == "mul":
            expected = self.mul_type(kinds, kind)
        else:
            if len(kinds) != 1 or not self.is_matrix(kinds[0]):
                raise ModelError("transpose requires one float matrix")
            shape = self.types.aggregates[kinds[0]]
            expected = self.matrix_type(shape["columns"], shape["rows"])
        if kind != expected:
            raise ModelError("Matrix intrinsic return shape mismatch")
        canonical = re.sub(r"matrix<\s*float\s*,\s*([1-4])\s*,\s*([1-4])\s*>", r"float\1x\2", signature)
        canonical = re.sub(r"vector<\s*float\s*,\s*([1-4])\s*>", r"float\1", canonical)
        canonical = re.sub(r"\bfloat1\b", "float", canonical).replace(" ", "")
        wanted = self.math_name(kind) + "(" + ",".join(self.math_name(k) for k in kinds) + ")"
        if canonical != wanted:
            raise ModelError("Unrecognized matrix intrinsic overload")
        return None, name, kind

    def scale(self, scalar, value):
        kind = value_type(value)
        if self.is_matrix(kind):
            return {"kind": "record", "type": kind, "fields": {name: self.scale(scalar, row) for name, row in value["fields"].items()}}
        repeated = scalar if kind == 1 else operation("splat", kind, [scalar])
        return operation("multiply", kind, [repeated, value])

    def matrix_cell(self, value, row, column):
        shape = self.types.aggregates[value_type(value)]
        return components(value["fields"][f"r{row}"], shape["columns"])[column]

    def product_sum(self, terms):
        result = terms[0]
        for term in terms[1:]:
            result = operation("add", 1, [result, term])
        return result

    def mul(self, lhs, rhs, kind):
        a, b = value_type(lhs), value_type(rhs)
        if a == 1 and (not self.is_matrix(b) or kind == b):
            return self.scale(lhs, rhs)
        if b == 1 and (not self.is_matrix(a) or kind == a):
            return self.scale(rhs, lhs)
        if isinstance(a, int) and isinstance(b, int):
            return operation("dot", 1, [lhs, rhs])
        if self.is_matrix(a) and isinstance(b, int):
            shape = self.types.aggregates[a]
            values = components(rhs, b)
            return vector([self.product_sum([operation("multiply", 1, [self.matrix_cell(lhs, i, k), values[k]])
                           for k in range(shape["columns"])]) for i in range(shape["rows"])])
        if isinstance(a, int) and self.is_matrix(b):
            shape = self.types.aggregates[b]
            values = components(lhs, a)
            return vector([self.product_sum([operation("multiply", 1, [values[k], self.matrix_cell(rhs, k, j)])
                           for k in range(shape["rows"])]) for j in range(shape["columns"])])
        aa, bb = self.types.aggregates[a], self.types.aggregates[b]
        fields = {}
        for i in range(aa["rows"]):
            fields[f"r{i}"] = vector([self.product_sum([operation("multiply", 1, [self.matrix_cell(lhs, i, k), self.matrix_cell(rhs, k, j)])
                                      for k in range(aa["columns"])]) for j in range(bb["columns"])])
        return {"kind": "record", "type": kind, "fields": fields}

    def transpose(self, value, kind):
        shape = self.types.aggregates[value_type(value)]
        return {"kind": "record", "type": kind, "fields": {
            f"r{j}": vector([self.matrix_cell(value, i, j) for i in range(shape["rows"])])
            for j in range(shape["columns"])}}

    def call(self, node, symbols):
        function, name, kind = self.checked_call(node)
        if function is None and name in ("mul", "transpose"):
            arguments = [self.expression(child, symbols) for child in node.children[1:]]
            return self.mul(*arguments, kind) if name == "mul" else self.transpose(arguments[0], kind)
        return super().call(node, symbols)

    def expression(self, node, symbols):
        kind = self.types.node_type(node)
        if node.kind in ("DeclRefExpr", "MemberExpr") and rooted(node):
            return self.address_spec(node).capture(symbols).read()
        if node.kind == "InitListExpr" and kind in self.types.aggregates:
            return self.initializer(node, kind, symbols)
        if node.kind in ("ArraySubscriptExpr", "CXXOperatorCallExpr"):
            if rooted(node):
                return self.address_spec(node).capture(symbols).read()
            receiver, index, owner, size, _ = index_parts(node, self.types)
            value = self.expression(receiver, symbols)
            index_value = self.index_value(index, symbols)
            constant = constant_value(index_value, self.bindings)
            checked = self.snapshot(dict(operation("bounded_index", "uint", [index_value]), size=size), "index.checked")
            address = CapturedAddress(self, make_symbol("temporary", owner, "Var", False, value),
                [{"kind": "index", "owner": owner, "size": size, "type": kind, "value": checked, "constant": constant}], kind)
            return address.read()
        if node.kind == "HLSLVectorElementExpr":
            if rooted(node):
                return self.address_spec(node).capture(symbols).read()
            value = self.expression(node.children[0], symbols)
            indices = swizzle_indices(component_mask(node), value_type(value))
            return initialized(vector([components(value, value_type(value))[i] for i in indices]))
        if node.kind in ("CStyleCastExpr", "CXXFunctionalCastExpr") and len(node.children) == 1 and node.text.endswith("<NoOp>"):
            return self.expression(node.children[0], symbols)
        if node.kind == "ImplicitCastExpr" and len(node.children) == 1:
            if node.text.endswith("<FlatConversion>"):
                return zero_value(kind, self.types)
            if node.text.endswith("<HLSLMatrixSplat>"):
                value = self.expression(node.children[0], symbols)
                shape = self.types.aggregates[kind]
                row = value if shape["columns"] == 1 else operation("splat", shape["columns"], [value])
                return {"kind": "record", "type": kind, "fields": {f"r{i}": row for i in range(shape["rows"])}}
            if node.text.endswith("<HLSLMatrixTruncationCast>"):
                value = self.expression(node.children[0], symbols)
                shape = self.types.aggregates[kind]
                return {"kind": "record", "type": kind, "fields": {
                    f"r{i}": vector([self.matrix_cell(value, i, j) for j in range(shape["columns"])]) for i in range(shape["rows"])}}
            if node.text.endswith("<HLSLVectorSplat>") and kind == self.types.node_type(node.children[0]) == 1:
                return self.expression(node.children[0], symbols)
        if self.is_matrix(kind) and node.kind == "UnaryOperator":
            return self.numeric_operation("negate", kind, [self.expression(node.children[0], symbols)])
        if self.is_matrix(kind) and node.kind == "BinaryOperator":
            operator = {"+": "add", "-": "subtract", "*": "multiply"}[quoted(node.text)[-1]]
            return self.numeric_operation(operator, kind, [self.expression(child, symbols) for child in node.children])
        return super().expression(node, symbols)

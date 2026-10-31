"""IEEE typed local vectors and fixed arrays on shared destinations and loops."""
import re
from shader_ast import ModelError, quoted
from shader_array_types import FixedArrayTypes
from shader_ieee_frontend import IeeeTypeRegistry, IeeeSemantics, UINT_OPERATORS, uint_literal
from shader_flow import GuardedProgram
from shader_loops import StaticLoopMixin, loop_node
from shader_local_values import LocalValues, rooted
from shader_addresses import index_parts
from shader_aggregate_values import components, vector
from shader_types import initialized, value_type, lane_count, scalar_type, vector_type, identifier, operation


class IeeeDataTypes(FixedArrayTypes, IeeeTypeRegistry):
    def __init__(self, declarations, allow_bool=False):
        self.aggregates, self.ready_shapes = {}, False
        super().__init__(declarations, allow_bool)
        for record in self.records.values():
            if record["node"] is not None and any(f["type"] in self.aggregates for f in record["fields"]):
                raise ModelError("Array struct fields are outside the IEEE subset")
        self.ready_shapes = True

    def named_type(self, name):
        if "[" in name:
            return self.array_type(name)
        return super().named_type(name)

    def node_type(self, node):
        name = quoted(node.text)[0].removeprefix("const ")
        if "[" in name:
            return self.named_type(name)
        if node.kind == "IntegerLiteral" and name == "literal int":
            return "literal_int"
        return super().node_type(node)

    def parameter_metadata(self, node):
        result = super().parameter_metadata(node)
        if result["type"] in self.aggregates:
            raise ModelError("Array parameters are outside the IEEE subset")
        return result

    def empty(self, kind):
        if kind in self.extra_leaves or isinstance(kind, int):
            if lane_count(kind) > 1:
                return {"kind": "partial_vector", "width": kind, "components": [None] * lane_count(kind)}
        return super().empty(kind)

    def element_type(self, kind):
        if kind in self.aggregates:
            shape = self.aggregates[kind]
            return shape["length"], shape["element"]
        return lane_count(kind), scalar_type(kind)

    def element_name(self, kind, index):
        return "e" + str(index)


class IeeeLocalValues(LocalValues):
    type_registry = IeeeDataTypes
    branching = True

    def __init__(self, source, dump):
        self.active_counters = set()
        self.validation_counters = {}
        super().__init__(source, dump)
        if any(f["type"] in self.types.aggregates for f in self.functions.values()):
            raise ModelError("Array returns are outside the IEEE subset")

    def loop_frame_name(self, key):
        helpers = [k for k, f in self.functions.items() if f is not self.main]
        return "main" if self.functions[key] is self.main else helpers.index(key)

    def loop_terminal_effect(self, function):
        return False

    def static_constant(self, node, symbols=None):
        if node.kind == "IntegerLiteral":
            return uint_literal(node, self.source)["value"]
        if node.kind == "DeclRefExpr" and symbols is not None:
            match = re.search(r"\bVar (0x[0-9a-fA-F]+) ", node.text)
            if match and match.group(1) in self.active_counters:
                symbol, path, kind = self.lvalue(node, symbols)
                if path or kind != "uint":
                    raise ModelError("Static counter identity/type mismatch")
                return symbol["value"]["value"]
        if node.kind == "ParenExpr" or (node.kind == "ImplicitCastExpr" and node.text.endswith(("<LValueToRValue>", "<IntegralCast>"))):
            if len(node.children) == 1:
                return self.static_constant(node.children[0], symbols)
        if node.kind in ("UnaryOperator", "BinaryOperator"):
            op = quoted(node.text)[-1]
            values = [self.static_constant(c, symbols) for c in node.children]
            if any(v is None for v in values):
                return None
            a = values[0]
            if len(values) == 1:
                return ((~a) if op == "~" else -a) & 0xffffffff if op in ("~", "-") else None
            b = values[1]
            operations = {"+": lambda: a+b, "-": lambda: a-b, "*": lambda: a*b,
                          "&": lambda: a&b, "|": lambda: a|b, "^": lambda: a^b,
                          "<<": lambda: a << (b&31), ">>": lambda: a >> (b&31)}
            return operations[op]() & 0xffffffff if op in operations else None
        return None

    def loop_constant(self, node):
        return self.static_constant(node)

    def validate_index(self, node):
        if self.types.node_type(node) not in ("uint", "literal_int"):
            raise ModelError("IEEE index must have uint or literal integer type")
        if node.kind == "IntegerLiteral":
            uint_literal(node, self.source)
            return
        if node.kind == "DeclRefExpr":
            match = re.search(r"\bVar (0x[0-9a-fA-F]+) ", node.text)
            if match and match.group(1) in self.validation_counters:
                self.counter_reference(node, self.validation_counters[match.group(1)])
                return
        if node.kind == "ParenExpr" or (node.kind == "ImplicitCastExpr" and node.text.endswith(("<LValueToRValue>", "<IntegralCast>"))):
            if len(node.children) == 1:
                return self.validate_index(node.children[0])
        if node.kind in ("UnaryOperator", "BinaryOperator"):
            op = quoted(node.text)[-1]
            allowed = ("~", "-") if node.kind == "UnaryOperator" else tuple(UINT_OPERATORS)
            if op in allowed and len(node.children) == (1 if node.kind == "UnaryOperator" else 2):
                for child in node.children:
                    self.validate_index(child)
                return
        raise ModelError("IEEE index source must be literal or static loop counter expression")

    def capture_index(self, node, index, size, symbols):
        constant = self.static_constant(node, symbols)
        if constant is None or not 0 <= constant < size:
            raise ModelError("IEEE index must be an in-range source constant or active loop counter expression")
        return constant, {"kind": "uint_literal", "width": "uint", "value": constant}

    def index_value(self, node, symbols):
        value = self.static_constant(node, symbols)
        if value is None:
            raise ModelError("IEEE index is not statically supported")
        return {"kind": "uint_literal", "width": "uint", "value": value}

    def execute_statement(self, node, state):
        loop = loop_node(node)
        if loop is None:
            return super().execute_statement(node, state)
        key = identifier(self.loop_specs[id(loop)]["counter"])
        saved = self.active_counters.copy()
        self.active_counters.add(key)
        try:
            return super().execute_statement(node, state)
        finally:
            self.active_counters = saved

    def validate_statement(self, node, result_type, effects_allowed):
        loop = loop_node(node)
        if loop is not None:
            spec = self.parse_loop(loop)
            saved = self.validation_counters.copy()
            self.validation_counters[identifier(spec["counter"])] = spec["counter"]
            try:
                return super().validate_statement(node, result_type, effects_allowed)
            finally:
                self.validation_counters = saved
        if node.kind in ("BinaryOperator", "CompoundAssignOperator") and len(node.children) == 2:
            from shader_validation import validate_expression
            kind = self.address_type(node.children[0])
            validate_expression(node.children[1], self)
            if self.types.node_type(node) != kind or self.types.node_type(node.children[1]) != kind:
                raise ModelError("Assignment type mismatch")
            if node.kind == "CompoundAssignOperator":
                self.uint_compound_operator(node) if kind in self.types.extra_leaves else self.float_compound(node, kind)
            elif quoted(node.text)[-1] != "=":
                raise ModelError("Only assignment statements are supported")
            return False
        return super().validate_statement(node, result_type, effects_allowed)

    def float_compound(self, node, kind):
        match = re.search(r" lvalue '(\+=|-=|\*=)' ComputeLHSTy=", node.text)
        if not isinstance(kind, int) or match is None:
            raise ModelError("Unsupported float compound")
        return {"+=": "add", "-=": "subtract", "*=": "multiply"}[match.group(1)]

    def assign_statement(self, node, symbols):
        if node.kind not in ("BinaryOperator", "CompoundAssignOperator"):
            return False
        destination = self.capture_destination(node.children[0], symbols)
        value = self.expression(node.children[1], symbols)
        if node.kind == "CompoundAssignOperator":
            op = self.uint_compound_operator(node) if destination.kind in self.types.extra_leaves else self.float_compound(node, destination.kind)
            value = operation(op, destination.kind, [destination.read(), value])
        destination.write(self.snapshot(initialized(value), destination.name()))
        return True

    def validate_ieee_expression(self, node):
        from shader_validation import validate_expression
        kind = self.types.node_type(node)
        if node.kind == "InitListExpr" and kind in self.types.aggregates:
            return self.validate_array_initializer(node, kind)
        if node.kind in ("ArraySubscriptExpr", "CXXOperatorCallExpr"):
            receiver, index, _, _, _ = index_parts(node, self.types)
            validate_expression(receiver, self)
            self.validate_index(index)
            # Range is checked on each complete static expansion.
            return
        return super().validate_ieee_expression(node)

    def expression(self, node, symbols):
        kind = self.types.node_type(node)
        if node.kind in ("DeclRefExpr", "MemberExpr", "HLSLVectorElementExpr", "ArraySubscriptExpr", "CXXOperatorCallExpr") and rooted(node):
            return self.address_spec(node).capture(symbols).read()
        if node.kind in ("ArraySubscriptExpr", "CXXOperatorCallExpr"):
            receiver, index, owner, size, _ = index_parts(node, self.types)
            value = self.expression(receiver, symbols)
            constant, _ = self.capture_index(index, self.index_value(index, symbols), size, symbols)
            return initialized(components(value, owner)[constant])
        if node.kind == "InitListExpr" and kind in self.types.aggregates:
            return self.array_initializer(node, kind, symbols)
        return super().expression(node, symbols)


class IeeeDataProgram(IeeeLocalValues, StaticLoopMixin, IeeeSemantics, GuardedProgram):
    pass

"""DXC default arguments and typed copy-in/copy-out on shared function frames."""
import re

from shader_ast import ModelError, quoted
from shader_access import AccessChecker
from shader_control_values import clone_symbols, logical, truth, zero_value
from shader_frontend import make_symbol
from shader_packing import PackingTypes, has_payload
from shader_shared import SharedProgram, leaves
from shader_types import declaration_name, identifier, initialized, read_path, replace_path, semantic, value_type


def output_parameters(function):
    return [param for param in function["parameters"] if param.get("mode", "in") != "in"]


class CopybackTypes(PackingTypes):
    def node_type(self, node):
        name = quoted(node.text)[0].removeprefix("const ")
        if node.kind == "ParmVarDecl" and any(child.kind in ("HLSLOutAttr", "HLSLInOutAttr") for child in node.children):
            if name.startswith("__restrict ") and name[len("__restrict "):] in self.records:
                return name[len("__restrict "):]
            if not name.endswith(" &__restrict"):
                raise ModelError("Out/inout needs the pinned DXC reference type")
            name = name[:-len(" &__restrict")]
            vector = re.fullmatch(r"vector<float, ([234])>", name)
            return self.named_type("float" + vector.group(1) if vector else name)
        if name.startswith("__restrict "):
            name = name[len("__restrict "):]
            vector = re.fullmatch(r"vector<float, ([234])>", name)
            return self.named_type("float" + vector.group(1) if vector else name)
        return super().node_type(node)

    def parameter_metadata(self, node):
        mode, default, field_semantic, qualifier = "in", None, None, False
        for child in node.children:
            if child.kind in ("HLSLInAttr", "HLSLOutAttr", "HLSLInOutAttr"):
                if qualifier or child.children:
                    raise ModelError("Repeated or malformed parameter direction")
                qualifier = True
                mode = {"HLSLInAttr": "in", "HLSLOutAttr": "out", "HLSLInOutAttr": "inout"}[child.kind]
            elif child.kind == "SemanticDecl" and field_semantic is None:
                field_semantic = semantic(child)
            elif default is None:
                default = child
            else:
                raise ModelError("Repeated parameter initializer")
        if default is not None and mode != "in":
            raise ModelError("Only input parameters may have defaults")
        return {"id": identifier(node), "name": declaration_name(node), "type": self.node_type(node),
                "semantic": field_semantic, "mode": mode, "default": default}


class CopybackProgram(SharedProgram):
    type_registry = CopybackTypes

    def __init__(self, source, dump):
        self.default_nodes = {}
        self.function_effects = {}
        super().__init__(source, dump)

    def function_roots(self, function):
        return [function["body"]] + [param["default"] for param in function["parameters"] if param.get("default") is not None]

    def checked_call(self, node):
        result = super().checked_call(node)
        function = result[0]
        if function is not None:
            for argument, param in zip(node.children[1:], function["parameters"]):
                if argument.kind == "CXXDefaultArgExpr":
                    if argument.children or param["default"] is None or param["mode"] != "in":
                        raise ModelError("Default argument is not bound to this callee declaration")
                    self.default_nodes[id(argument)] = param["default"]
        return result

    def default_expression(self, node):
        if id(node) not in self.default_nodes:
            raise ModelError("Unbound default argument expression")
        return self.default_nodes[id(node)]

    def output_argument(self, node, param):
        # DXC represents record outputs as restricted values, and wraps the
        # destination in a read-looking cast. That cast is address plumbing.
        if (param["type"] in self.types.records and node.kind == "ImplicitCastExpr"
                and node.text.endswith("<LValueToRValue>") and len(node.children) == 1
                and self.types.node_type(node) == self.types.node_type(node.children[0]) == param["type"]):
            return node.children[0]
        return node

    def validate_extension(self, node):
        if node.kind == "CXXDefaultArgExpr":
            from shader_validation import validate_expression
            default = self.default_expression(node)
            validate_expression(default, self)
            if self.types.node_type(default) != self.types.node_type(node):
                raise ModelError("Default argument type mismatch")
            return True
        return super().validate_extension(node)

    def prepare_function_validation(self):
        graph = {}
        for key, function in self.functions.items():
            targets, clip, discard = set(), False, False
            nodes = list(self.function_roots(function))
            for index, param in enumerate(function["parameters"]):
                if param["default"] is not None and any(other["default"] is None for other in function["parameters"][index + 1:]):
                    raise ModelError("Default parameters must form a trailing suffix")
            while nodes:
                node = nodes.pop()
                if node.kind == "DiscardStmt":
                    discard = True
                if node.kind == "CallExpr":
                    called, name, _ = self.checked_call(node)
                    if called is None and name == "clip":
                        clip = True
                    elif called is not None:
                        targets.add(called["id"])
                nodes.extend(node.children)
            graph[key] = targets
            self.function_effects[key] = {"clip": clip or discard, "discard": discard}
        # Defaults can recursively invoke defaults before body validation; reject
        # that graph before recursively validating a CXXDefaultArgExpr.
        from shader_validation import visit_calls
        completed = set()
        for key in graph:
            visit_calls(key, graph, set(), completed)
        changed = True
        while changed:
            changed = False
            for key, targets in graph.items():
                for effect in ("clip", "discard"):
                    if not self.function_effects[key][effect] and any(self.function_effects[target][effect] for target in targets):
                        self.function_effects[key][effect] = True
                        changed = True
        for key, function in self.functions.items():
            if output_parameters(function) and self.function_effects[key]["discard"]:
                raise ModelError("Copy-out helpers cannot reach a terminal discard")

    def allows_void_call(self, node):
        function, _, _ = self.checked_call(node)
        return function is not None and not self.function_effects[function["id"]]["clip"]

    def validate_extra_definitions(self):
        from shader_validation import validate_expression
        checker = AccessChecker(self)
        for function in self.functions.values():
            for param in function["parameters"]:
                if param["default"] is not None:
                    validate_expression(param["default"], self)
                    if self.types.node_type(param["default"]) != param["type"]:
                        raise ModelError("Default initializer has a different type")
            for root in self.function_roots(function):
                checker.scan(root)

    def validate_helper_initialization(self):
        super().validate_helper_initialization()
        names = ("bindings", "events", "effects", "stack", "current_guard", "alive", "frame", "calls")
        saved = {name: getattr(self, name) for name in names}
        try:
            for function in self.functions.values():
                for param in function["parameters"]:
                    if param["default"] is not None:
                        # Defaults belong to separate declaration checks, not one
                        # imaginary caller accumulating every unused default.
                        self.bindings, self.events, self.effects, self.stack, self.calls = [], [], [], [], []
                        self.current_guard, self.alive, self.frame = truth(False), truth(True), None
                        value = initialized(self.expression(param["default"], dict(self.globals)))
                        if value_type(value) != param["type"] or has_payload(value):
                            raise ModelError("Default parameter has invalid value/carrier type")
        finally:
            for name, value in saved.items():
                setattr(self, name, value)

    def compile_arguments(self, function, parameters):
        return [zero_value(param["type"], self.types) if param["mode"] == "out"
                else self.shape(param["type"], "helper_parameter", parameters) for param in function["parameters"]]

    def parameter_symbol(self, function, param, argument):
        if param.get("mode") == "out":
            return make_symbol(param["name"], param["type"], "ParmVar", True, self.types.empty(param["type"]))
        return super().parameter_symbol(function, param, argument)

    def capture_return(self, value, symbols):
        function = self.frame["function"]
        outputs = output_parameters(function)
        if not outputs:
            return super().capture_return(value, symbols)
        fields = {} if function["type"] == "void" else {"value": value}
        if function["type"] != "void" and (value is None or value_type(value) != function["type"]):
            raise ModelError("Copy-out function return type mismatch")
        for index, param in enumerate(outputs):
            fields[f"out{index}"] = self.snapshot(initialized(symbols[param["id"]]["value"]), "return." + param["name"])
        return {"kind": "record", "type": "$copyback", "fields": fields}

    def function_result(self, function, frame, flow):
        outputs = output_parameters(function)
        if not outputs:
            return super().function_result(function, frame, flow)
        if function["type"] == "void" and not flow.stopped:
            self.current_guard = flow.mask
            frame["returns"].append((flow.mask, self.capture_return(None, flow.symbols)))
        fields = {} if function["type"] == "void" else {"value": zero_value(function["type"], self.types)}
        for index, param in enumerate(outputs):
            fields[f"out{index}"] = zero_value(param["type"], self.types)
        result = {"kind": "record", "type": "$copyback", "fields": fields}
        self.current_guard = truth(True)
        for mask, value in reversed(frame["returns"]):
            result = self.select(mask, value, result, function["name"] + ".result")
        return result

    def helper_result(self, function, result):
        outputs = output_parameters(function)
        if not outputs:
            return super().helper_result(function, result)
        expression = {"kind": "void", "width": "void"} if function["type"] == "void" else result["fields"]["value"]
        return {"expression": expression, "outputs": [result["fields"][f"out{i}"] for i in range(len(outputs))]}

    def call(self, node, symbols):
        function, _, _ = self.checked_call(node)
        if function is None:
            return super().call(node, symbols)
        flattened, destinations = [], []
        for argument, param in zip(node.children[1:], function["parameters"]):
            if param["mode"] != "in":
                symbol, path, kind = self.lvalue(self.output_argument(argument, param), symbols)
                if not symbol["writable"] or kind != param["type"]:
                    raise ModelError("Copy-out requires a writable local with matching type")
                destinations.append((symbol, path, kind))
                if param["mode"] == "out":
                    continue
                value = initialized(read_path(symbol["value"], path))
            else:
                value = self.expression(argument, symbols)
            if value_type(initialized(value)) != param["type"] or has_payload(value):
                raise ModelError("Copy-in parameter type/carrier mismatch")
            flattened.extend(leaves(self.snapshot(value, function["name"] + ".argument")))
        index = self.call_event(function, flattened)
        fields = []
        result = self.shape(function["type"], "call_result", fields, index)
        writes = []
        for symbol, path, kind in destinations:
            value = self.shape(kind, "call_result", fields, index)
            writes.append((symbol, path, self.snapshot(value, "copyout." + symbol["name"])))
        for symbol, path, value in writes:
            symbol["value"] = replace_path(symbol["value"], path, value)
        return result

    def expression(self, node, symbols):
        if node.kind == "CXXDefaultArgExpr":
            return self.expression(self.default_expression(node), dict(self.globals))
        if node.kind == "ConditionalOperator":
            condition = self.snapshot(self.expression(node.children[0], symbols), "conditional.condition")
            entry = self.current_guard
            yes_symbols, no_symbols = clone_symbols(symbols), clone_symbols(symbols)
            try:
                self.current_guard = logical("and", entry, condition)
                yes = self.expression(node.children[1], yes_symbols)
                self.current_guard = logical("and", entry, logical("not", condition))
                no = self.expression(node.children[2], no_symbols)
            finally:
                self.current_guard = entry
            self.merge_symbols(condition, symbols, yes_symbols, no_symbols)
            return self.select(condition, yes, no, "conditional.value")
        if node.kind == "BinaryOperator" and quoted(node.text)[-1] in ("&&", "||"):
            operator = quoted(node.text)[-1]
            lhs = self.snapshot(self.expression(node.children[0], symbols), "boolean.left")
            before, after = clone_symbols(symbols), clone_symbols(symbols)
            enabled = lhs if operator == "&&" else logical("not", lhs)
            entry = self.current_guard
            try:
                self.current_guard = logical("and", entry, enabled)
                rhs = self.expression(node.children[1], after)
            finally:
                self.current_guard = entry
            self.merge_symbols(enabled, symbols, after, before)
            return self.snapshot(logical("and" if operator == "&&" else "or", lhs, rhs), "boolean.logical")
        return super().expression(node, symbols)

    def merge_symbols(self, condition, symbols, yes, no):
        for key, symbol in symbols.items():
            if symbol["writable"] and yes[key]["value"] != no[key]["value"]:
                symbol["value"] = self.select(condition, yes[key]["value"], no[key]["value"], symbol["name"] + ".expression.join")

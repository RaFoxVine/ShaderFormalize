"""Guarded SSA execution of typed scalar control flow, without enumerating paths."""
from shader_ast import ModelError, quoted
from shader_frontend import Program, make_symbol
from shader_types import initialized, operation, value_type
from shader_effects import DERIVATIVES
from shader_validation import control_branches, statement_block
from shader_control_values import choose, clone_symbols, logical, truth, zero_value
from shader_math import has_math_domain


class Flow:
    def __init__(self, symbols, mask):
        self.symbols = symbols
        self.mask = mask
        self.stopped = False


class ControlProgram(Program):
    control = True

    def execute_statement(self, node, state):
        return False

    def __init__(self, source, dump):
        super().__init__(source, dump)
        self.fragment = True
        self.current_guard = truth(True)
        self.alive = truth(True)
        self.frame = None
        self.branches = 0
        self.invocations = 0

    def guard(self):
        entry = truth(True) if self.frame is None else self.frame["entry"]
        return logical("and", entry, logical("and", self.current_guard, self.alive))

    def snapshot(self, value, name):
        result = super().snapshot(value, name)
        if value["kind"] != "record":
            self.bindings[result["index"]]["guard"] = self.guard()
        return result

    def select(self, condition, yes, no, name):
        value = choose(condition, yes, no)
        if value is None:
            return None
        if value["kind"] == "record":
            fields = {}
            for field_name in value["fields"]:
                fields[field_name] = self.select(condition, yes["fields"][field_name], no["fields"][field_name], name + "." + field_name)
            return dict(value, fields=fields)
        return self.snapshot(value, name)

    def sample(self, node, symbols):
        mode, texture, sampler, nodes = self.resources.sample(node, self.types)
        arguments = [self.expression(child, symbols) for child in nodes]
        value = dict(operation("sample", 4, arguments), mode=mode, texture=texture,
                     sampler=sampler, context_mask=self.guard())
        return self.snapshot(value, "texture." + mode)

    def clipping(self, predicate):
        predicate = dict(predicate, guard=self.guard())
        self.effect(predicate)
        effect = {"kind": "effect", "width": "bool", "index": len(self.effects) - 1}
        self.alive = self.snapshot(logical("and", self.alive, effect), "shader.alive")

    def call(self, node, symbols):
        function, name, size = self.checked_call(node)
        arguments = [self.expression(child, symbols) for child in node.children[1:]]
        if function is not None:
            return self.invoke(function, arguments)
        if name == "clip":
            argument = self.snapshot(arguments[0], "clip.argument")
            self.clipping(operation("keep", "bool", [argument]))
            return {"kind": "void", "width": "void"}
        if name in DERIVATIVES:
            value = dict(operation("derivative", size, arguments), mode=name, context_mask=self.guard())
            return self.snapshot(value, name)
        value = operation(name, size, arguments)
        return self.snapshot(value, name) if name == "normalize" or has_math_domain(name) else value

    def expression(self, node, symbols):
        kind = self.types.node_type(node)
        if node.kind == "CXXBoolLiteralExpr":
            return truth(node.text.endswith(" true"))
        if node.kind == "ConditionalOperator":
            condition = self.snapshot(self.expression(node.children[0], symbols), "conditional.condition")
            entry = self.current_guard
            try:
                self.current_guard = logical("and", entry, condition)
                yes = self.expression(node.children[1], symbols)
                self.current_guard = logical("and", entry, logical("not", condition))
                no = self.expression(node.children[2], symbols)
            finally:
                self.current_guard = entry
            return self.select(condition, yes, no, "conditional.value")
        if node.kind == "BinaryOperator" and kind == "bool":
            operator = quoted(node.text)[-1]
            lhs = self.snapshot(self.expression(node.children[0], symbols), "boolean.left")
            entry = self.current_guard
            try:
                if operator in ("&&", "||"):
                    enabled = lhs if operator == "&&" else logical("not", lhs)
                    self.current_guard = logical("and", entry, enabled)
                rhs = self.expression(node.children[1], symbols)
            finally:
                self.current_guard = entry
            if operator in ("&&", "||"):
                return self.snapshot(logical("and" if operator == "&&" else "or", lhs, rhs), "boolean.logical")
            return self.snapshot(dict(operation("compare", "bool", [lhs, rhs]), operator=operator), "boolean.compare")
        if node.kind == "UnaryOperator" and kind == "bool":
            return self.snapshot(logical("not", self.expression(node.children[0], symbols)), "boolean.not")
        if node.kind == "ImplicitCastExpr" and node.text.endswith("<FloatingToBoolean>"):
            zero = zero_value(1, self.types)
            return self.snapshot(dict(operation("compare", "bool", [self.expression(node.children[0], symbols), zero]), operator="!="), "boolean.cast")
        if (node.kind == "ImplicitCastExpr" and node.text.endswith("<IntegralToFloating>")
                and quoted(node.children[0].text)[:1] in (["bool"], ["const bool"])):
            condition = self.expression(node.children[0], symbols)
            one = {"kind": "literal", "width": 1, "numerator": 1, "denominator": 1}
            return self.select(condition, one, zero_value(1, self.types), "boolean.to_float")
        return super().expression(node, symbols)

    def branch(self, node, state):
        if self.branches >= 32:
            raise ModelError("Control-flow nesting exceeds 32 levels")
        condition_node, yes_node, no_node = control_branches(node, self)
        condition = self.snapshot(self.expression(condition_node, state.symbols), "if.condition")
        entry = self.snapshot(self.current_guard, "if.entry")
        yes_mask = self.snapshot(logical("and", entry, condition), "if.true")
        no_mask = self.snapshot(logical("and", entry, logical("not", condition)), "if.false")
        yes = Flow(clone_symbols(state.symbols), yes_mask)
        no = Flow(clone_symbols(state.symbols), no_mask)
        self.branches += 1
        try:
            self.execute(statement_block(yes_node), yes)
            if no_node.kind != "Null":
                self.execute(statement_block(no_node), no)
        finally:
            self.branches -= 1
            self.current_guard = state.mask
        state.stopped = yes.stopped and no.stopped
        if state.stopped:
            state.mask = truth(False)
            return
        for key, symbol in state.symbols.items():
            if not symbol["writable"]:
                continue
            a, b = yes.symbols[key]["value"], no.symbols[key]["value"]
            if yes.stopped:
                symbol["value"] = b
            elif no.stopped:
                symbol["value"] = a
            else:
                symbol["value"] = self.select(condition, a, b, symbol["name"] + ".join")
        state.mask = self.snapshot(logical("or", yes.mask, no.mask), "if.continue")

    def execute(self, body, state):
        for statement in body.children:
            if state.stopped:
                raise ModelError("Statements after a terminal return/discard are unsupported")
            self.current_guard = state.mask
            if self.execute_statement(statement, state):
                continue
            if statement.kind == "CompoundStmt":
                scope = Flow(dict(state.symbols), state.mask)
                self.execute(statement, scope)
                state.mask, state.stopped = scope.mask, scope.stopped
            elif statement.kind == "IfStmt":
                self.branch(statement, state)
            elif statement.kind == "ReturnStmt":
                if len(self.frame["returns"]) >= 128:
                    raise ModelError("Function exceeds 128 return cases")
                value = None
                if statement.children:
                    value = self.snapshot(initialized(self.expression(statement.children[0], state.symbols)), "return.value")
                mask = self.snapshot(self.current_guard, "return.mask")
                self.frame["returns"].append((mask, self.capture_return(value, state.symbols)))
                state.mask, state.stopped = truth(False), True
            elif statement.kind == "DiscardStmt":
                self.clipping(operation("never", "bool", []))
                state.mask, state.stopped = truth(False), True
            else:
                # Ordinary declarations/assignments/calls retain the old value semantics.
                super().block(statement_block(statement), state.symbols)

    def invoke(self, function, arguments):
        self.check_invocation(function)
        if len(arguments) != len(function["parameters"]):
            raise ModelError("Function argument count mismatch")
        caller_guard, caller_frame = self.current_guard, self.frame
        entry = self.guard()
        symbols = dict(self.globals)
        for param, argument in zip(function["parameters"], arguments):
            symbols[param["id"]] = self.parameter_symbol(function, param, argument)
        frame = {"returns": [], "entry": entry, "function": function}
        self.frame = frame
        self.current_guard = truth(True)
        self.stack.append(function["id"])
        try:
            flow = Flow(symbols, truth(True))
            self.execute(function["body"], flow)
            return self.function_result(function, frame, flow)
        finally:
            self.stack.pop()
            self.frame = caller_frame
            self.current_guard = caller_guard

    def parameter_symbol(self, function, param, argument):
        if value_type(initialized(argument)) != param["type"]:
            raise ModelError("Function argument type mismatch")
        if function is not self.main:
            argument = self.snapshot(argument, function["name"] + "." + param["name"])
        return make_symbol(param["name"], param["type"], "ParmVar", function is not self.main, argument)

    def capture_return(self, value, symbols):
        return value

    def function_result(self, function, frame, flow):
        self.current_guard = truth(True)
        if function["type"] == "void":
            return {"kind": "void", "width": "void"}
        result = zero_value(function["type"], self.types)
        for mask, value in reversed(frame["returns"]):
            if value is None or value_type(value) != function["type"]:
                raise ModelError("Control return type mismatch")
            result = self.select(mask, value, result, function["name"] + ".result")
        return result

    def model(self):
        model = super().model()
        model.update(schema=4, alive=self.alive, control_semantics="scalar-hlsl-2021-execution-mask")
        return model

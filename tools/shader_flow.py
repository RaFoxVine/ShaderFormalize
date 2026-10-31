"""Shared guarded SSA and call frames; numeric operations belong to each frontend."""
from shader_ast import ModelError
from shader_frontend import Program, make_symbol
from shader_types import initialized, value_type
from shader_validation import control_branches, statement_block
from shader_control_values import choose, clone_symbols, logical, truth


class Flow:
    def __init__(self, symbols, mask):
        self.symbols = symbols
        self.mask = mask
        self.stopped = False


class GuardedProgram(Program):
    control = True

    def execute_statement(self, node, state):
        return False

    def __init__(self, source, dump):
        super().__init__(source, dump)
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
                self.discard(state)
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
        result = self.zero_value(function["type"])
        for mask, value in reversed(frame["returns"]):
            if value is None or value_type(value) != function["type"]:
                raise ModelError("Control return type mismatch")
            result = self.select(mask, value, result, function["name"] + ".result")
        return result

    def discard(self, state):
        raise ModelError("Discard is outside this flow backend")

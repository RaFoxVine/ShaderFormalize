"""Exact, statically terminating uint for loops; never a fuel truncation."""
import re

from shader_access import AccessChecker
from shader_aggregate import AggregateProgram
from shader_aggregate_values import constant_ast
from shader_ast import ModelError, quoted, source_header
from shader_control import Flow
from shader_frontend import make_symbol
from shader_types import declaration_name, identifier


def loop_node(node):
    if node.kind == "ForStmt":
        return node
    if node.kind != "AttributedStmt":
        return None
    if len(node.children) != 2:
        raise ModelError("Only one unroll hint on a canonical for loop is supported")
    attribute, body = node.children
    text = source_header(attribute.text).group("tail").strip()
    if (attribute.kind != "HLSLUnrollAttr" or attribute.children or body.kind != "ForStmt"
            or re.fullmatch(r"[0-9]+", text) is None or not 0 <= int(text) < 2**32):
        raise ModelError("Unknown loop hint or unsupported attributed statement")
    return body


def frame_order(entry):
    return (1, 0) if entry["frame"] == "main" else (0, entry["frame"])


class LoopProgram(AggregateProgram):
    def __init__(self, source, dump):
        self.loop_specs, self.function_loops = {}, {}
        super().__init__(source, dump)

    def counter_reference(self, node, counter):
        while node.kind == "ParenExpr" or (node.kind == "ImplicitCastExpr" and node.text.endswith("<LValueToRValue>")):
            if len(node.children) != 1 or self.types.node_type(node) != "uint":
                raise ModelError("Unexpected counter conversion")
            node = node.children[0]
        if node.kind != "DeclRefExpr" or node.children or self.types.node_type(node) != "uint":
            raise ModelError("Expected a direct uint counter reference")
        match = re.search(r"\bVar (0x[0-9a-fA-F]+) '([A-Za-z_][A-Za-z0-9_]*)'", source_header(node.text).group("tail"))
        if match is None or match.group(1) != identifier(counter) or match.group(2) != declaration_name(counter):
            raise ModelError("Loop condition/increment references a different counter")

    def parse_loop(self, node):
        from shader_validation import validate_declaration, validate_expression
        if len(node.children) != 5:
            raise ModelError("Expected five canonical for-loop slots")
        init, condition_variable, condition, increment, body = node.children
        if init.kind != "DeclStmt" or len(init.children) != 1 or condition_variable.kind != "Null":
            raise ModelError("For loop needs one declared uint counter and no condition variable")
        counter = init.children[0]
        validate_declaration(counter, self)
        if self.types.node_type(counter) != "uint" or len(counter.children) != 1:
            raise ModelError("For loop counter must be an initialized uint")
        if (condition.kind != "BinaryOperator" or len(condition.children) != 2
                or quoted(condition.text)[-1] != "<" or self.types.node_type(condition) != "bool"):
            raise ModelError("Only strict uint counter < constant loops are supported")
        self.counter_reference(condition.children[0], counter)
        end_node = condition.children[1]
        validate_expression(end_node, self)
        if self.types.node_type(end_node) != "uint":
            raise ModelError("Loop upper bound must be uint")
        if (increment.kind != "UnaryOperator" or len(increment.children) != 1
                or self.types.node_type(increment) != "uint"
                or re.search(r" (?:lvalue )?(?:prefix|postfix) '\+\+'$", increment.text) is None):
            raise ModelError("Only unit prefix/postfix uint increment is supported")
        self.counter_reference(increment.children[0], counter)
        start = constant_ast(counter.children[0], self.source)
        end = constant_ast(end_node, self.source)
        if start is None or end is None:
            raise ModelError("For-loop bounds must be statically known pure uint constants")
        count = max(end - start, 0)
        if count > 64:
            raise ModelError("For loop exceeds the 64-iteration static budget")
        return {"counter": counter, "body": body, "start": start, "end": end, "count": count}

    def validate_statement(self, node, result_type, effects_allowed):
        from shader_validation import statement_block, validate_block
        loop = loop_node(node)
        if loop is None:
            return super().validate_statement(node, result_type, effects_allowed)
        spec = self.parse_loop(loop)
        pending = [spec["body"]]
        while pending:
            child = pending.pop()
            if child.kind in ("ReturnStmt", "DiscardStmt"):
                raise ModelError("Loop bodies cannot return or terminate the Shader")
            if child.kind == "CallExpr":
                function, _, _ = self.checked_call(child)
                if function is not None and self.function_effects[function["id"]]["discard"]:
                    raise ModelError("Loop helper cannot reach a terminal discard")
            pending.extend(child.children)
        validate_block(statement_block(spec["body"]), result_type, self, effects_allowed)
        _, writes = AccessChecker(self).scan(spec["body"])
        if any(root == identifier(spec["counter"]) for root, _ in writes):
            raise ModelError("Loop body modifies its termination counter")
        self.loop_specs[id(loop)] = spec
        return False

    def execute_statement(self, node, state):
        from shader_validation import statement_block
        loop = loop_node(node)
        if loop is None:
            return super().execute_statement(node, state)
        if id(loop) not in self.loop_specs:
            raise ModelError("Loop has not passed static validation")
        spec = self.loop_specs[id(loop)]
        self.frame.setdefault("loops", []).append({
            "line": loop.line, "column": loop.column,
            "start": spec["start"], "end": spec["end"], "count": spec["count"]})
        scope = dict(state.symbols)
        counter = spec["counter"]
        symbol = make_symbol(declaration_name(counter), "uint", "Var", False, None)
        scope[identifier(counter)] = symbol
        mask = state.mask
        for value in range(spec["start"], spec["end"]):
            steps = self.frame.get("loop_steps", 0) + 1
            if steps > 4096:
                raise ModelError("Frame exceeds 4096 statically expanded loop-body executions")
            self.frame["loop_steps"] = steps
            symbol["value"] = {"kind": "uint_literal", "width": "uint", "value": value}
            iteration = Flow(dict(scope), mask)
            self.execute(statement_block(spec["body"]), iteration)
            if iteration.stopped:
                raise ModelError("Loop body unexpectedly terminated its enclosing frame")
            mask = iteration.mask
        state.mask = mask
        self.current_guard = mask
        return True

    def function_result(self, function, frame, flow):
        result = super().function_result(function, frame, flow)
        self.function_loops[function["id"]] = frame.get("loops", [])
        return result

    def model(self):
        model = super().model()
        frames = []
        for key, regions in self.function_loops.items():
            if regions:
                frame = "main" if self.functions[key] is self.main else self.helper_indices[key]
                frames.append({"frame": frame, "regions": regions})
        if frames:
            frames.sort(key=frame_order)
            model.update(loop_semantics="exact-static-uint-for-v1", loops=frames)
        return model

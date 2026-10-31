"""Real-valued expressions and fragment effects over the shared guarded flow."""
from shader_ast import quoted
from shader_flow import Flow, GuardedProgram
from shader_types import operation
from shader_effects import DERIVATIVES
from shader_control_values import logical, truth, zero_value
from shader_math import has_math_domain


class ControlProgram(GuardedProgram):
    def __init__(self, source, dump):
        super().__init__(source, dump)
        self.fragment = True

    def discard(self, state):
        self.clipping(operation("never", "bool", []))
        state.mask, state.stopped = truth(False), True

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

    def model(self):
        model = super().model()
        model.update(schema=4, alive=self.alive, control_semantics="scalar-hlsl-2021-execution-mask")
        return model

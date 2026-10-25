"""Recursive finite call frames; no generated Lean text is interpreted here."""
from shader_control_eval import control_events, control_field
from shader_shared import result_leaves
from shader_shared_lean import validate_shared


class SharedFrame:
    def __init__(self, model, helpers, inputs, count, operations, entry=None, parameters=None):
        self.model = dict(model, _shared_runtime=self)
        self.helpers, self.inputs, self.count, self.operations = helpers, inputs, count, operations
        self.entry, self.parameters = entry, parameters
        self.results = []

    def field(self, expr):
        kind = expr["kind"]
        if kind == "helper_entry":
            return self.entry
        if kind == "helper_parameter":
            return self.parameters[expr["index"]]
        value = self.results[expr["index"]]
        return value[1] if kind == "call_alive" else value[0][expr["field"]]

    def value(self, expr, locals_, effects):
        return control_field(expr, self.model, self.inputs, locals_, effects, self.count, self.operations)

    def call(self, index, locals_, effects):
        call = self.model["calls"][index]
        entry = self.value(call["entry"], locals_, effects)
        parameters = [self.value(arg, locals_, effects) for arg in call["arguments"]]
        frame = SharedFrame(self.helpers[call["helper"]], self.helpers, self.inputs,
                            self.count, self.operations, entry, parameters)
        self.results.append(frame.run())

    def run(self):
        locals_, effects = control_events(self.model, self.inputs, self.count, self.operations)
        values = [self.value(leaf, locals_, effects) for leaf in result_leaves(self.model)]
        return values, self.value(self.model["alive"], locals_, effects)


def evaluate_shared(model, inputs, count, operations):
    validate_shared(model)
    values, alive = SharedFrame(model, model["helpers"], inputs, count, operations).run()
    return [values[0][point] if alive[point][0] else None for point in range(count)]

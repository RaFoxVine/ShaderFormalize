"""Typed, nonrecursive helper bodies retained once with explicit call events."""
from shader_ast import ModelError
from shader_control_values import logical, truth
from shader_packing import PackingProgram, has_payload
from shader_types import initialized, value_type


def leaves(value):
    if value["kind"] == "record":
        return [leaf for field in value["fields"].values() for leaf in leaves(field)]
    return [] if value["kind"] == "void" else [value]


def result_leaves(frame):
    return leaves(frame["expression"]) + [leaf for value in frame.get("outputs", []) for leaf in leaves(value)]


class SharedProgram(PackingProgram):
    def __init__(self, source, dump):
        super().__init__(source, dump)
        self.helpers, self.helper_indices, self.compiling = [], {}, []
        self.calls = []
        self.total_bindings = 0

    def shape(self, kind, leaf_kind, leaf_values, call_index=None):
        if kind == "void":
            return {"kind": "void", "width": "void"}
        if kind not in self.types.records:
            value = {"kind": leaf_kind, "width": kind,
                     "index": len(leaf_values) if call_index is None else call_index}
            if call_index is not None:
                value["field"] = len(leaf_values)
            leaf_values.append(value)
            return value
        return {"kind": "record", "type": kind, "fields": {
            field["name"]: self.shape(field["type"], leaf_kind, leaf_values, call_index)
            for field in self.types.records[kind]["fields"]}}

    def helper(self, function):
        key = function["id"]
        if key in self.compiling or len(self.compiling) >= 32:
            raise ModelError("Recursive or excessive shared helper depth")
        if key in self.helper_indices:
            return self.helper_indices[key]
        names = ("bindings", "events", "effects", "stack", "fragment", "invocations",
                 "current_guard", "alive", "frame", "branches", "calls")
        saved = {name: getattr(self, name) for name in names}
        self.compiling.append(key)
        try:
            self.bindings, self.events, self.effects, self.stack, self.calls = [], [], [], [], []
            self.fragment, self.invocations, self.branches, self.frame = True, 0, 0, None
            self.alive = truth(True)
            self.current_guard = {"kind": "helper_entry", "width": "bool"}
            parameters = []

            arguments = self.compile_arguments(function, parameters)
            result = PackingProgram.invoke(self, function, arguments)
            depth = 1 + max([self.helpers[call["helper"]]["depth"] for call in self.calls] or [0])
            if depth >= 32:
                raise ModelError("Shared helper graph exceeds depth 31")
            self.total_bindings += len(self.bindings)
            if self.total_bindings > 65536:
                raise ModelError("Shared program exceeds 65536 helper bindings")
            index = len(self.helpers)
            self.helpers.append(dict({"name": function["name"], "parameters": parameters,
                                 "depth": depth, "interface": self.interface,
                                 "bindings": self.bindings, "events": self.events,
                                 "effects": self.effects, "calls": self.calls,
                                 "alive": self.alive}, **self.helper_result(function, result)))
            self.helper_indices[key] = index
            return index
        finally:
            self.compiling.pop()
            for name, value in saved.items():
                setattr(self, name, value)

    def compile_arguments(self, function, parameters):
        return [self.shape(param["type"], "helper_parameter", parameters) for param in function["parameters"]]

    def helper_result(self, function, result):
        return {"expression": result}

    def validate_helper_initialization(self):
        for function in self.functions.values():
            if function is not self.main:
                self.helper(function)

    def invoke(self, function, arguments):
        if function is self.main:
            return super().invoke(function, arguments)
        if len(arguments) != len(function["parameters"]):
            raise ModelError("Shared argument count mismatch")
        flattened = []
        for param, argument in zip(function["parameters"], arguments):
            if value_type(initialized(argument)) != param["type"] or has_payload(argument):
                raise ModelError("Shared helper argument type/carrier mismatch")
            flattened.extend(leaves(self.snapshot(argument, function["name"] + ".argument")))
        index = self.call_event(function, flattened)
        return self.shape(function["type"], "call_result", [], index)

    def call_event(self, function, flattened):
        helper = self.helper(function)
        if len(self.calls) >= 4096:
            raise ModelError("Function exceeds 4096 shared call events")
        index = len(self.calls)
        self.calls.append({"helper": helper, "arguments": flattened, "entry": self.guard()})
        self.events.append({"call": index})
        self.alive = self.snapshot(logical("and", self.alive,
            {"kind": "call_alive", "width": "bool", "index": index}), "call.alive")
        return index

    def model(self):
        model = super().model()
        model.update(schema=6, helpers=self.helpers, calls=self.calls,
                     function_semantics="shared-complete-fields-guarded-calls")
        return model

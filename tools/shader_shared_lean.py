"""Shared helper definitions, concrete call results and guarded domain conclusions."""
from shader_ast import ModelError
from shader_packing_lean import PackingEmitter
from shader_shared import leaves
from shader_lean import fin_index
from shader_control_lean import generate_control
from shader_packing import has_payload


def validate_shared(model):
    try:
        _validate_shared(model)
    except (KeyError, TypeError, IndexError, AttributeError, ValueError, RecursionError) as error:
        raise ModelError("Malformed shared model: " + type(error).__name__, "INVALID_INPUT") from error


def _validate_shared(model):
    helpers = model["helpers"]
    if not isinstance(helpers, list) or len(helpers) > 127:
        raise ModelError("Invalid shared helper table")
    if sum(len(frame["bindings"]) for frame in helpers) > 65536:
        raise ModelError("Shared helper binding budget exceeded")
    for ordinal, frame in enumerate(helpers + [model]):
        SharedFrameValidator(model, frame, ordinal).validate()


def check_reference(index, limit):
    if type(index) is not int or not 0 <= index < limit:
        raise ModelError("Invalid or forward shared reference")


class SharedFrameValidator:
    """One explicit event cursor per frame; references cannot see future events."""
    def __init__(self, model, frame, ordinal):
        self.model, self.frame, self.ordinal = model, frame, ordinal
        self.helpers = model["helpers"]
        self.bindings, self.effects, self.calls = frame["bindings"], frame["effects"], frame["calls"]
        self.available = {"local": 0, "effect": 0, "call": 0}

    def check(self, expr, predicate=False):
        if predicate and expr["width"] != "bool":
            raise ModelError("Shared predicate must have Boolean type")
        kind = expr["kind"]
        if kind == "record":
            for value in expr["fields"].values():
                self.check(value)
            return
        expected = None
        if kind in ("local", "effect"):
            check_reference(expr["index"], self.available[kind])
            expected = self.bindings[expr["index"]]["width"] if kind == "local" else "bool"
        elif kind == "parameter":
            check_reference(expr["index"], len(self.model["interface"]))
            expected = self.model["interface"][expr["index"]]["width"]
        elif kind in ("helper_entry", "helper_parameter"):
            if self.ordinal == len(self.helpers):
                raise ModelError("Helper reference in main")
            if kind == "helper_entry":
                expected = "bool"
            else:
                check_reference(expr["index"], len(self.frame["parameters"]))
                expected = self.frame["parameters"][expr["index"]]["width"]
        elif kind in ("call_result", "call_alive"):
            check_reference(expr["index"], self.available["call"])
            if kind == "call_alive":
                expected = "bool"
            else:
                result = leaves(self.helpers[self.calls[expr["index"]]["helper"]]["expression"])
                check_reference(expr["field"], len(result))
                expected = result[expr["field"]]["width"]
        payload = kind == "local" and self.bindings[expr["index"]]["expression"].get("payload", False)
        if expected is not None and (expr["width"] != expected or bool(expr.get("payload", False)) != bool(payload)):
            raise ModelError("Shared reference type mismatch")
        for child in expr.get("arguments", []):
            self.check(child)
        for name in ("guard", "context_mask"):
            if name in expr:
                self.check(expr[name], True)

    def validate(self):
        frame, model = self.frame, self.model
        bindings, effects, calls = self.bindings, self.effects, self.calls
        available = self.available
        if frame["interface"] != model["interface"]:
            raise ModelError("Shared frame interface mismatch")
        if not all(isinstance(table, list) for table in (bindings, effects, calls, frame["events"])):
            raise ModelError("Invalid shared frame table")
        if max(len(bindings), len(effects), len(calls)) > 4096:
            raise ModelError("Shared frame budget exceeded")
        for event in frame["events"]:
            if set(event) == {"call"} and event["call"] == available["call"]:
                check_reference(event["call"], len(calls))
                call = calls[event["call"]]
                check_reference(call["helper"], self.ordinal)
                target = self.helpers[call["helper"]]
                if [arg["width"] for arg in call["arguments"]] != [p["width"] for p in target["parameters"]]:
                    raise ModelError("Shared call parameter mismatch")
                self.check(call["entry"], True)
                for arg in call["arguments"]:
                    if has_payload(arg):
                        raise ModelError("Carrier passed to shared helper")
                    self.check(arg)
                available["call"] += 1
            elif set(event) == {"binding"} and event["binding"] == available["local"]:
                check_reference(event["binding"], len(bindings))
                binding = bindings[event["binding"]]
                self.check(binding["expression"])
                self.check(binding["guard"], True)
                if binding["width"] != binding["expression"]["width"]:
                    raise ModelError("Shared binding type mismatch")
                available["local"] += 1
            elif set(event) == {"effect"} and event["effect"] == available["effect"]:
                check_reference(event["effect"], len(effects))
                self.check(effects[event["effect"]])
                available["effect"] += 1
            else:
                raise ModelError("Invalid shared event ordering")
        if list(available.values()) != [len(bindings), len(effects), len(calls)]:
            raise ModelError("Incomplete shared events")
        self.check(frame["expression"])
        if has_payload(frame["expression"]):
            raise ModelError("Shared return cannot be a carrier")
        self.check(frame["alive"], True)


class SharedEmitter(PackingEmitter):
    def __init__(self, model, helpers=None, prefix="", helper_index=None):
        self.helpers = model.get("helpers", []) if helpers is None else helpers
        self.prefix, self.helper_index, self.available_calls = prefix, helper_index, 0
        super().__init__(model)

    def field(self, expr):
        if expr["kind"] in ("helper_parameter", "helper_entry", "call_result", "call_alive"):
            return super().field(expr) if expr["width"] == "bool" else self.raw_field(expr)
        return super().field(expr)

    def raw_field(self, expr):
        kind = expr["kind"]
        if kind == "helper_entry":
            return "entry"
        if kind == "helper_parameter":
            return f"hp{expr['index']}"
        if kind in ("call_result", "call_alive"):
            if not 0 <= expr["index"] < self.available_calls:
                raise ModelError("Unavailable shared call result")
            field = "alive" if kind == "call_alive" else f"r{expr['field']}"
            return f"call{expr['index']}.{field}"
        return super().raw_field(expr)

    def element(self, expr, index, position):
        if expr["kind"] in ("helper_parameter", "call_result"):
            value = f"({self.field(expr)} {position})"
            return value if expr["width"] in (1, "uint", "bool") else f"({value} {fin_index(index)})"
        return super().element(expr, index, position)

    def collect_domains(self, expr, guard):
        if expr["kind"] == "normalize":
            arg = self.field(expr["arguments"][0])
            self.domains.append(f"(∀ x : E, ({self.field(guard)} x) → (0 : ℝ) < dot ({arg} x) ({arg} x))")
            for child in expr.get("arguments", []):
                self.collect_domains(child, guard)
            return
        super().collect_domains(expr, guard)

    def extra_event(self, event, lines):
        if set(event) != {"call"} or event["call"] != self.available_calls:
            return False
        call = self.model["calls"][self.available_calls]
        entry = self.field(call["entry"])
        args = " ".join(self.field(arg) for arg in call["arguments"])
        globals_ = " ".join(f"p{i['index']}" for i in self.model["interface"])
        self.flush(lines)
        lines.append(f"    let call{self.available_calls} := {self.prefix}helper{call['helper']} ops {globals_} {entry} {args}")
        self.domains.append(f"call{self.available_calls}.defined")
        self.available_calls += 1
        return True

    def result_type(self):
        return super().result_type() if self.helper_index is None else f"{self.prefix}Result{self.helper_index} E"

    def finish_definition(self, lines):
        if self.available_calls != len(self.model["calls"]):
            raise ModelError("Incomplete shared calls")
        if self.helper_index is None:
            return super().finish_definition(lines)
        values = []
        for leaf in leaves(self.model["expression"]):
            self.collect_domains(leaf, {"kind": "boolean", "width": "bool", "value": True})
            values.append(self.field(leaf))
        values.append(self.field(self.model["alive"]))
        values.append(" ∧ ".join(self.domains + ["True"]))
        self.flush(lines)
        lines.append("    ⟨" + ", ".join(values) + "⟩")

    def definition(self, name, parameters):
        if self.helper_index is not None:
            return super().definition(name, parameters)
        self.prefix = name + "_"
        definitions = []
        for index, helper in enumerate(self.helpers):
            result = [f"structure {self.prefix}Result{index} (E : Type) where"]
            for i, leaf in enumerate(leaves(helper["expression"])):
                result.append(f"  r{i} : E → {self.value_type(leaf)}")
            result += ["  alive : E → Prop", "  defined : Prop"]
            definitions.append("\n".join(result))
            args = parameters + " (entry : E → Prop) " + " ".join(
                f"(hp{i} : E → {self.value_type(param)})" for i, param in enumerate(helper["parameters"]))
            definitions.append(SharedEmitter(helper, self.helpers, self.prefix, index).definition(
                f"{self.prefix}helper{index}", args))
        definitions.append(super().definition(name, parameters))
        return "\n\n".join(definitions)


def generate_shared(original, optimized, spec):
    if original["schema"] != 6 or optimized["schema"] != 6:
        raise ModelError("Shared schema 6 cannot mix with legacy models", "INVALID_INPUT")
    validate_shared(original)
    validate_shared(optimized)
    text = generate_control(original, optimized, spec, SharedEmitter, "import ShaderFormalize.Packing\n")
    # Explicit E is necessary even when a uniform field ignores its position.
    return text.replace("∀ x,", "∀ x : E,")

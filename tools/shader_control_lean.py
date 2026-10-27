"""Complete-field selection, execution masks, and definedness proof obligations."""
from shader_ast import ModelError
from shader_fragment import FragmentEmitter
from shader_lean import lean_number, lean_type
from shader_control_values import logical, truth
from shader_boolean import BooleanDAG
from shader_math import has_math_domain, lean_domain_condition, math_imports


def effects_mask(count):
    result = truth(True)
    for index in range(count):
        result = logical("and", result, {"kind": "effect", "width": "bool", "index": index})
    return result


class ControlEmitter(FragmentEmitter):
    def value_type(self, expr):
        return lean_type(expr["width"])

    def __init__(self, model):
        super().__init__(model)
        self.boolean_dag = BooleanDAG(model)
        self.boolean_names, self.extra_lines = {}, []

    def field(self, expr):
        if expr["width"] == "bool":
            return self.boolean_name(self.boolean_dag.convert(expr))
        return self.raw_field(expr)

    def boolean_name(self, index):
        if index < 2:
            return "(fun _ => " + ("True" if index else "False") + ")"
        if index not in self.boolean_names:
            atom, no, yes = self.boolean_dag.nodes[index]
            predicate = self.raw_field(self.boolean_dag.atoms[atom])
            low, high = self.boolean_name(no), self.boolean_name(yes)
            name = f"q{index}"
            self.extra_lines.append(f"    let {name} : E → Prop := (fun x => if {predicate} x then {high} x else {low} x)")
            self.boolean_names[index] = name
        return self.boolean_names[index]

    def flush(self, lines):
        lines.extend(self.extra_lines)
        self.extra_lines.clear()

    def raw_field(self, expr):
        kind = expr["kind"]
        if kind == "boolean":
            return "(fun _ => " + ("True" if expr["value"] else "False") + ")"
        if kind == "effect":
            if not 0 <= expr["index"] < self.available_effects:
                raise ModelError("Control expression refers to an unavailable effect")
            return f"c{expr['index']}"
        if kind in ("and", "or", "not"):
            args = [f"({self.field(arg)} x)" for arg in expr["arguments"]]
            value = f"¬ {args[0]}" if kind == "not" else f"{args[0]} " + ("∧" if kind == "and" else "∨") + f" {args[1]}"
            return f"(fun x => {value})"
        if kind == "compare":
            args = []
            for arg in expr["arguments"]:
                args.append(f"({self.field(arg)} x)" if arg["width"] == "bool" else self.element(arg, None, "x"))
            symbol = {"<": "<", "<=": "≤", ">": ">", ">=": "≥", "==": "=", "!=": "≠"}[expr["operator"]]
            return f"(fun x => {args[0]} {symbol} {args[1]})"
        if kind == "choose":
            condition, yes, no = [self.field(arg) for arg in expr["arguments"]]
            return f"(fun x => if {condition} x then {yes} x else {no} x)"
        if kind in ("sample", "derivative"):
            mask = expr.get("context_mask")
            if mask is None:
                self.context(expr["context"])
                mask = effects_mask(expr["context"])
            context = "[" + self.field(mask) + "]"
            if kind == "sample":
                method = {"Sample": "sample", "SampleLevel": "sampleLevel", "SampleGrad": "sampleGrad"}[expr["mode"]]
                args = " ".join(self.field(child) for child in expr["arguments"])
                return f'(ops.{method} "{expr["texture"]}" "{expr["sampler"]}" {context} {args})'
            argument = self.field(expr["arguments"][0])
            prefix = f'ops.derivative "{expr["mode"]}" {context}'
            if expr["width"] == 1:
                return f"({prefix} {argument})"
            return f"(fun x i => {prefix} (fun y => {argument} y i) x)"
        return super().field(expr)

    def element(self, expr, index, position):
        if expr["kind"] == "choose":
            value = f"({self.field(expr)} {position})"
            if expr["width"] == 1:
                return value
            from shader_lean import fin_index
            return f"({value} {fin_index(index)})"
        return super().element(expr, index, position)

    def predicate(self, expr):
        predicate = super().predicate(expr)
        if "guard" in expr:
            return f"(fun x => ({self.field(expr['guard'])} x) → {predicate} x)"
        return predicate

    def definition(self, name, parameters):
        self.domains = []
        lines = [f"def {name} {{E : Type}} (ops : Fragment.Ops E) {parameters} : {self.result_type()} := by", "  classical", "  exact"]
        bindings, effects = self.model["bindings"], self.model.get("effects", [])
        events = self.model.get("events", [{"binding": i} for i in range(len(bindings))])
        next_binding = 0
        for event in events:
            if set(event) == {"binding"} and event["binding"] == next_binding:
                binding = bindings[next_binding]
                value = self.field(binding["expression"])
                self.collect_domains(binding["expression"], binding.get("guard", effects_mask(self.available_effects)))
                self.flush(lines)
                lines.append(f"    let l{next_binding} : E → {self.value_type(binding['expression'])} := {value}")
                next_binding += 1
            elif set(event) == {"effect"} and event["effect"] == self.available_effects:
                index = self.available_effects
                predicate = self.predicate(effects[index])
                self.collect_domains(effects[index], effects[index].get("guard", effects_mask(self.available_effects)))
                self.flush(lines)
                lines.append(f"    let c{index} : E → Prop := {predicate}")
                self.available_effects += 1
            elif not self.extra_event(event, lines):
                raise ModelError("Invalid control event ordering")
        if next_binding != len(bindings) or self.available_effects != len(effects):
            raise ModelError("Incomplete control events")
        self.finish_definition(lines)
        return "\n".join(lines)

    def result_type(self):
        return "(E → Option Vec4) × Prop"

    def extra_event(self, event, lines):
        return False

    def finish_definition(self, lines):
        self.collect_domains(self.model["expression"], effects_mask(self.available_effects))
        alive = self.field(self.model.get("alive", effects_mask(self.available_effects)))
        color = self.field(self.model["expression"])
        defined = " ∧ ".join(self.domains + ["True"])
        self.flush(lines)
        lines.append(f"    (Control.finish {alive} {color}, {defined})")

    def collect_domains(self, expr, guard):
        if has_math_domain(expr["kind"]):
            conditions = []
            for index in range(expr["width"]):
                arguments = [self.element(child, None if child["width"] == 1 else index, "x") for child in expr["arguments"]]
                conditions.append(lean_domain_condition(expr["kind"], arguments))
            condition = " ∧ ".join(f"({value})" for value in conditions)
            self.domains.append(f"(∀ x : E, ({self.field(guard)} x) → {condition})")
        if expr["kind"] == "normalize":
            argument = self.field(expr["arguments"][0])
            self.domains.append(f"(∀ x, ({self.field(guard)} x) → (0 : ℝ) < dot ({argument} x) ({argument} x))")
        for child in expr.get("arguments", []):
            self.collect_domains(child, guard)


def generate_control(original, optimized, spec, emitter_type=ControlEmitter, extra_import=""):
    extra_import += math_imports([original, optimized])
    interface = original["interface"]
    parameters = " ".join(f"(p{x['index']} : " + ("E → " if x["storage"] == "parameter" else "") + lean_type(x["width"]) + ")" for x in interface)
    names = " ".join(f"p{x['index']}" for x in interface)
    emitter = emitter_type(original)
    premises = []
    for index, lo, hi in spec["ranges"]:
        item = interface[index]
        varying = item["storage"] == "parameter"
        value = f"p{index}" + (" x" if varying else "")
        prefix = "∀ x, " if varying else ""
        if item["width"] > 1:
            prefix += f"∀ i : Fin {item['width']}, "
            value = "(" + value + ") i"
        premises.append(f"({prefix}{lean_number(lo)} ≤ {value} ∧ {value} ≤ {lean_number(hi)})")
    for expr in spec["nonzero"]:
        value = emitter.field(expr)
        premises.append(f"(∀ x, (0 : ℝ) < dot ({value} x) ({value} x))")
    a, b = f"original ops {names}", f"optimized ops {names}"
    goal = f"({a}).2 ∧ ({b}).2 ∧ ({a}).1 = ({b}).1"
    implication = " →\n  ".join(premises + [goal])
    return ("import ShaderFormalize.Control\n" + extra_import + "\nnoncomputable section\nnamespace ShaderFormalize.Generated\nopen ShaderFormalize ShaderFormalize.Model\n\n"
            + emitter_type(original).definition("original", parameters) + "\n\n"
            + emitter_type(optimized).definition("optimized", parameters)
            + f"\n\ndef expected : Prop := ∀ (E : Type) (ops : Fragment.Ops E) {parameters},\n  {implication}\n\nend ShaderFormalize.Generated\n")

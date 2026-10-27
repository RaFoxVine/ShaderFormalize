"""Lift numeric SSA to whole fragment fields and preserve ordered clipping contexts."""
from fractions import Fraction

from shader_ast import ModelError
from shader_lean import fin_index, lean_number, lean_type, vector_literal
from shader_math import MATH_OPERATIONS, lean_scalar_math, lean_vector_components


class FragmentEmitter:
    def __init__(self, model):
        self.model = model
        self.available_effects = 0

    def context(self, count):
        if type(count) is not int or not 0 <= count <= self.available_effects:
            raise ModelError("Opaque operation refers to an unavailable clipping context")
        return "[" + ", ".join(f"c{i}" for i in range(count)) + "]"

    def field(self, expr):
        kind = expr["kind"]
        if kind == "local":
            return f"l{expr['index']}"
        if kind == "parameter" and self.model["interface"][expr["index"]]["storage"] == "parameter":
            return f"p{expr['index']}"
        if kind == "sample":
            method = {"Sample": "sample", "SampleLevel": "sampleLevel", "SampleGrad": "sampleGrad"}[expr["mode"]]
            args = " ".join(self.field(child) for child in expr["arguments"])
            return f'(ops.{method} "{expr["texture"]}" "{expr["sampler"]}" {self.context(expr["context"])} {args})'
        if kind == "derivative":
            argument = self.field(expr["arguments"][0])
            prefix = f'ops.derivative "{expr["mode"]}" {self.context(expr["context"])}'
            if expr["width"] == 1:
                return f"({prefix} {argument})"
            return f"(fun x i => {prefix} (fun y => {argument} y i) x)"
        if expr["width"] == 1:
            return f"(fun x => {self.element(expr, None, 'x')})"
        return f"(fun x i => {self.element(expr, 'i', 'x')})"

    def components(self, expr, position):
        if expr["kind"] == "construct":
            result = []
            for child in expr["arguments"]:
                result.extend(self.components(child, position))
            return result
        if expr["kind"] == "swizzle":
            values = self.components(expr["arguments"][0], position)
            return [values[i] for i in expr["indices"]]
        return [self.element(expr, None if expr["width"] == 1 else i, position) for i in range(expr["width"])]

    def element(self, expr, index, position):
        kind, size = expr["kind"], expr["width"]
        if kind in ("parameter", "local", "sample", "derivative"):
            if kind == "parameter" and self.model["interface"][expr["index"]]["storage"] == "uniform":
                name = f"p{expr['index']}"
            else:
                name = f"({self.field(expr)} {position})"
            return name if size == 1 else f"({name} {fin_index(index)})"
        if kind == "literal":
            return lean_number(Fraction(expr["numerator"], expr["denominator"]))
        if kind in ("construct", "swizzle"):
            components = self.components(expr, position)
            if size == 1:
                return components[0]
            if isinstance(index, int):
                return components[index]
            return f"({vector_literal(components)} {index})"
        arguments = expr["arguments"]
        if kind in ("cross", "reflect"):
            values = lean_vector_components(kind, [self.components(arg, position) for arg in arguments])
            if size == 1:
                return values[0]
            if isinstance(index, int):
                return values[index]
            return f"({vector_literal(values)} {index})"
        if kind == "normalize":
            return f"(normalize ({self.field(arguments[0])} {position}) {fin_index(index)})"
        if kind == "dot":
            return f"(dot ({self.field(arguments[0])} {position}) ({self.field(arguments[1])} {position}))"
        if kind in ("length", "distance"):
            components = self.components(arguments[0], position)
            if kind == "distance":
                other = self.components(arguments[1], position)
                components = [f"({a} - {b})" for a, b in zip(components, other)]
            squared = " + ".join(f"({value} * {value})" for value in components)
            return f"(Real.sqrt ({squared}))"
        if kind == "splat":
            return self.element(arguments[0], None, position)
        args = [self.element(child, index if child["width"] > 1 else None, position) for child in arguments]
        if kind in MATH_OPERATIONS:
            return lean_scalar_math(kind, args)
        if kind == "negate":
            return f"(-{args[0]})"
        if kind in ("add", "subtract", "multiply"):
            symbol = {"add": "+", "subtract": "-", "multiply": "*"}[kind]
            return f"({args[0]} {symbol} {args[1]})"
        if kind in ("lerp", "saturate"):
            return f"(ShaderFormalize.Model.{kind} {' '.join(args)})"
        raise ModelError(f"Unknown fragment IR operation: {kind}")

    def predicate(self, expr):
        if expr["kind"] == "never":
            return "(fun _ => False)"
        if expr["kind"] == "keep":
            components = self.components(expr["arguments"][0], "x")
            return "(fun x => " + " ∧ ".join(f"(0 : ℝ) ≤ {value}" for value in components) + ")"
        if expr["kind"] == "unless":
            lhs, rhs = [self.element(child, None, "x") for child in expr["arguments"]]
            symbol = {"<": "<", "<=": "≤", ">": ">", ">=": "≥", "==": "=", "!=": "≠"}[expr["operator"]]
            return f"(fun x => ¬ ({lhs} {symbol} {rhs}))"
        raise ModelError("Unknown clipping predicate")

    def definition(self, name, parameters):
        lines = [f"def {name} {{E : Type}} (ops : Fragment.Ops E) {parameters} : E → Option Vec4 :="]
        bindings, effects = self.model["bindings"], self.model.get("effects", [])
        events = self.model.get("events", [{"binding": i} for i in range(len(bindings))])
        next_binding = 0
        for event in events:
            if set(event) == {"binding"} and event["binding"] == next_binding:
                binding = bindings[next_binding]
                lines.append(f"  let l{next_binding} : E → {lean_type(binding['width'])} := {self.field(binding['expression'])}")
                next_binding += 1
            elif set(event) == {"effect"} and event["effect"] == self.available_effects:
                index = self.available_effects
                lines.append(f"  let c{index} : E → Prop := {self.predicate(effects[index])}")
                self.available_effects += 1
            else:
                raise ModelError("Invalid fragment event ordering")
        if next_binding != len(bindings) or self.available_effects != len(effects):
            raise ModelError("Incomplete fragment events")
        lines.append(f"  Fragment.finish {self.context(len(effects))} {self.field(self.model['expression'])}")
        return "\n".join(lines)


def generate_fragment(original, optimized, spec):
    interface = original["interface"]
    parameters = " ".join(f"(p{x['index']} : " + ("E → " if x["storage"] == "parameter" else "") + lean_type(x["width"]) + ")" for x in interface)
    names = " ".join(f"p{x['index']}" for x in interface)
    emitter = FragmentEmitter(original)
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
    goal = f"original ops {names} = optimized ops {names}"
    implication = " →\n  ".join(premises + [goal])
    return ("import ShaderFormalize.Fragment\n\nnoncomputable section\nnamespace ShaderFormalize.Generated\nopen ShaderFormalize ShaderFormalize.Model\n\n"
            + FragmentEmitter(original).definition("original", parameters) + "\n\n"
            + FragmentEmitter(optimized).definition("optimized", parameters)
            + f"\n\ndef expected : Prop := ∀ (E : Type) (ops : Fragment.Ops E) {parameters},\n  {implication}\n\nend ShaderFormalize.Generated\n")

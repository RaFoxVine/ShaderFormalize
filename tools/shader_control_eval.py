"""Finite guarded-field interpreter, independent of Lean proof construction."""
import math
from shader_eval import evaluate


def compare(operator, lhs, rhs):
    return {"<": lhs < rhs, "<=": lhs <= rhs, ">": lhs > rhs, ">=": lhs >= rhs, "==": lhs == rhs, "!=": lhs != rhs}[operator]


def control_field(expr, model, inputs, locals_, effects, count, operations, guard=None):
    kind = expr["kind"]
    if kind == "parameter":
        value = inputs[expr["index"]]
        return [list(value) for _ in range(count)] if model["interface"][expr["index"]]["storage"] == "uniform" else value
    if kind == "local":
        return locals_[expr["index"]]
    if kind == "effect":
        return effects[expr["index"]]
    if kind == "literal":
        return [evaluate(expr, [], []) for _ in range(count)]
    if kind == "uint_literal":
        return [[expr["value"]] for _ in range(count)]
    if kind == "boolean":
        return [[expr["value"]] for _ in range(count)]
    args = [control_field(child, model, inputs, locals_, effects, count, operations, guard) for child in expr["arguments"]]
    if kind in ("sample", "derivative"):
        if "context_mask" in expr:
            active = control_field(expr["context_mask"], model, inputs, locals_, effects, count, operations)
            context = [[bool(value[0]) for value in active]]
        else:
            context = [[bool(value[0]) for value in field] for field in effects[:expr["context"]]]
        return operations(kind, expr, context, args)
    result = []
    for point in range(count):
        values = [arg[point] for arg in args]
        if kind == "choose":
            result.append(values[1] if values[0][0] else values[2])
        elif kind.startswith("uint_") or kind in ("real_to_uint", "carrier", "recover"):
            from shader_packing_eval import packing_scalar
            active = guard is None or guard[point]
            result.append([packing_scalar(kind, [value[0] for value in values], active)])
        elif kind == "compare":
            result.append([compare(expr["operator"], values[0][0], values[1][0])])
        elif kind == "not":
            result.append([not values[0][0]])
        elif kind in ("and", "or"):
            result.append([values[0][0] and values[1][0] if kind == "and" else values[0][0] or values[1][0]])
        elif kind == "normalize":
            length = math.sqrt(sum(value*value for value in values[0]))
            if length == 0 and (guard is None or guard[point]):
                raise ValueError("Executed normalize(0) has no specified HLSL result")
            result.append([value/length for value in values[0]] if length else [0]*len(values[0]))
        else:
            rewritten = dict(expr, arguments=[{"kind": "parameter", "index": i, "width": child["width"]} for i, child in enumerate(expr["arguments"])])
            result.append(evaluate(rewritten, values, []))
    return result


def evaluate_control(model, inputs, count, operations):
    locals_, effects = [], []
    for event in model["events"]:
        if "binding" in event:
            binding = model["bindings"][event["binding"]]
            mask = binding.get("guard")
            active = [True]*count if mask is None else [value[0] for value in control_field(mask, model, inputs, locals_, effects, count, operations)]
            locals_.append(control_field(binding["expression"], model, inputs, locals_, effects, count, operations, active))
        else:
            predicate = model["effects"][event["effect"]]
            args = [control_field(child, model, inputs, locals_, effects, count, operations) for child in predicate["arguments"]]
            mask = predicate.get("guard")
            active = [True]*count if mask is None else [value[0] for value in control_field(mask, model, inputs, locals_, effects, count, operations)]
            values = []
            for point in range(count):
                keep = False
                if predicate["kind"] == "keep":
                    keep = all(value >= 0 for value in args[0][point])
                elif predicate["kind"] == "unless":
                    keep = not compare(predicate["operator"], args[0][point][0], args[1][point][0])
                values.append([not active[point] or keep])
            effects.append(values)
    colors = control_field(model["expression"], model, inputs, locals_, effects, count, operations)
    alive = control_field(model["alive"], model, inputs, locals_, effects, count, operations)
    return [colors[point] if alive[point][0] else None for point in range(count)]


def no_operations(kind, expr, context, arguments):
    raise ValueError("Whole-field operations require an explicit finite oracle")

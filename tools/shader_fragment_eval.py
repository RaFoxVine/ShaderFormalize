"""Finite whole-field interpretation for counterexamples; not a formal proof."""
from shader_eval import evaluate


def field_value(expr, model, inputs, locals_, effects, count, operations):
    kind = expr["kind"]
    if kind == "parameter":
        index = expr["index"]
        value = inputs[index]
        if model["interface"][index]["storage"] == "uniform":
            return [list(value) for _ in range(count)]
        return [list(point) for point in value]
    if kind == "local":
        return locals_[expr["index"]]
    if kind == "literal":
        return [evaluate(expr, [], []) for _ in range(count)]
    arguments = [field_value(child, model, inputs, locals_, effects, count, operations) for child in expr["arguments"]]
    if kind in ("derivative", "sample"):
        context = effects[:expr["context"]]
        return operations(kind, expr, context, arguments)
    result = []
    rewritten = dict(expr, arguments=[{"kind": "parameter", "index": i, "width": child["width"]} for i, child in enumerate(expr["arguments"])])
    for point in range(count):
        result.append(evaluate(rewritten, [arg[point] for arg in arguments], []))
    return result


def evaluate_fragment(model, inputs, count, operations):
    locals_, effects = [], []
    for event in model["events"]:
        if "binding" in event:
            binding = model["bindings"][event["binding"]]
            locals_.append(field_value(binding["expression"], model, inputs, locals_, effects, count, operations))
        else:
            predicate = model["effects"][event["effect"]]
            arguments = [field_value(child, model, inputs, locals_, effects, count, operations) for child in predicate["arguments"]]
            values = []
            for point in range(count):
                if predicate["kind"] == "never":
                    keep = False
                elif predicate["kind"] == "keep":
                    keep = all(value >= 0 for value in arguments[0][point])
                else:
                    lhs, rhs = [arg[point][0] for arg in arguments]
                    operator = predicate["operator"]
                    compared = {"<": lhs < rhs, "<=": lhs <= rhs, ">": lhs > rhs, ">=": lhs >= rhs, "==": lhs == rhs, "!=": lhs != rhs}[operator]
                    keep = not compared
                values.append(keep)
            effects.append(values)
    colors = field_value(model["expression"], model, inputs, locals_, effects, count, operations)
    return [colors[point] if all(effect[point] for effect in effects) else None for point in range(count)]

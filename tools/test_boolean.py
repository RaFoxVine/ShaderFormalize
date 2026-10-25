"""Independent truth tables for the Boolean sharing used by Lean emission."""
import itertools
import unittest

from shader_ast import ModelError
from shader_boolean import BooleanDAG


def atom(index):
    return {"kind": "compare", "width": "bool", "operator": ">", "arguments": [
        {"kind": "parameter", "width": 1, "index": index},
        {"kind": "literal", "width": 1, "numerator": 0, "denominator": 1}]}


def expression(kind, *arguments):
    return {"kind": kind, "width": "bool", "arguments": list(arguments)}


def direct(expr, values):
    kind = expr["kind"]
    if kind == "compare" and expr["arguments"][0]["width"] == 1:
        return values[expr["arguments"][0]["index"]]
    args = [direct(child, values) for child in expr["arguments"]]
    if kind == "not":
        return not args[0]
    if kind == "and":
        return args[0] and args[1]
    if kind == "or":
        return args[0] or args[1]
    if kind == "choose":
        return args[1] if args[0] else args[2]
    return (args[0] == args[1]) if expr["operator"] == "==" else (args[0] != args[1])


class BooleanTests(unittest.TestCase):
    def test_truth_tables_and_shared_subexpressions(self):
        a, b, c = [atom(index) for index in range(3)]
        compound = expression("choose", a, expression("and", b, c), expression("or", b, expression("not", c)))
        cases = [compound, expression("not", compound), expression("and", compound, a), expression("or", compound, a)]
        for operator in ("==", "!="):
            cases.append(dict(expression("compare", compound, b), operator=operator))
        for case in cases:
            dag = BooleanDAG({"bindings": []})
            root = dag.convert(case)
            for values in itertools.product((False, True), repeat=3):
                assignment = {key: values[value["arguments"][0]["index"]] for key, value in dag.atoms.items()}
                self.assertEqual(dag.evaluate(root, assignment), direct(case, values))
            self.assertEqual(dag.apply("and", root, root), root)

    def test_long_alias_chain_and_forward_reference_rejection(self):
        bindings = [{"width": "bool", "expression": atom(0)}]
        for index in range(1, 4096):
            bindings.append({"width": "bool", "expression": {"kind": "local", "width": "bool", "index": index - 1}})
        dag = BooleanDAG({"bindings": bindings})
        self.assertEqual(len(dag.nodes), 3)
        self.assertEqual(dag.locals[0], dag.locals[4095])
        with self.assertRaises(ModelError):
            dag.convert({"kind": "local", "width": "bool", "index": 4096})

    def test_depth_and_node_budgets_fail_explicitly(self):
        dag = BooleanDAG({"bindings": []})
        current = 1
        with self.assertRaisesRegex(ModelError, "depth 256"):
            for index in range(257):
                current = dag.node(str(index), 0, current)
        dag = BooleanDAG({"bindings": []})
        with self.assertRaisesRegex(ModelError, "4096 nodes"):
            for index in range(4096):
                dag.atom(atom(index))

    def test_guarded_effect_events_match_independent_truth_tables(self):
        for kind in ("never", "unless", "keep"):
            predicate = {"kind": kind, "width": "bool", "guard": atom(0), "arguments": []}
            if kind == "unless":
                predicate.update(operator=">", arguments=atom(1)["arguments"])
            if kind == "keep":
                predicate["arguments"] = [{"kind": "parameter", "width": 1, "index": 1}]
            model = {"bindings": [], "effects": [predicate], "events": [{"effect": 0}]}
            dag = BooleanDAG(model)
            root = dag.convert({"kind": "effect", "width": "bool", "index": 0})
            for x, y in itertools.product((-1, 0, 1), repeat=2):
                values = (x, y)
                assignment = {}
                for key, value in dag.atoms.items():
                    lhs = values[value["arguments"][0]["index"]]
                    assignment[key] = lhs > 0 if value["operator"] == ">" else lhs >= 0
                keep = False if kind == "never" else (y <= 0 if kind == "unless" else y >= 0)
                self.assertEqual(dag.evaluate(root, assignment), x <= 0 or keep)

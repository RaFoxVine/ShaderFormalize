"""Bounded reduced decision DAGs for propositional SSA sharing in Lean output."""
import json

from shader_ast import ModelError
from shader_lean import resolve_alias


class BooleanDAG:
    def __init__(self, model):
        self.model = model
        self.nodes = [None, None]  # False and True terminals.
        self.unique, self.atoms, self.memo, self.locals, self.effects = {}, {}, {}, {}, {}
        self.depths = [0, 0]
        # Bindings are ordered SSA. Resolve aliases once, without recursive
        # traversal of a potentially 4096-binding Boolean alias chain.
        events = model.get("events", [{"binding": i} for i in range(len(model["bindings"]))])
        for event in events:
            if "binding" in event:
                index = event["binding"]
                binding = model["bindings"][index]
                if binding["width"] == "bool":
                    self.locals[index] = self.convert(binding["expression"])
            elif "effect" in event:
                index = event["effect"]
                self.effects[index] = self.effect(model["effects"][index])

    def effect(self, expr):
        kind = expr["kind"]
        if kind == "never":
            result = 0
        elif kind == "unless":
            comparison = dict(expr, kind="compare")
            result = self.negate(self.convert(comparison))
        elif kind == "keep":
            result = 1
            argument = expr["arguments"][0]
            for index in range(argument["width"]):
                scalar = argument if argument["width"] == 1 else {"kind": "swizzle", "width": 1, "indices": [index], "arguments": [argument]}
                zero = {"kind": "literal", "width": 1, "numerator": 0, "denominator": 1}
                comparison = {"kind": "compare", "width": "bool", "operator": ">=", "arguments": [scalar, zero]}
                result = self.apply("and", result, self.convert(comparison))
        else:
            raise ModelError("Unknown Boolean effect")
        if "guard" in expr:
            result = self.apply("or", self.negate(self.convert(expr["guard"])), result)
        return result

    def node(self, atom, no, yes):
        if no == yes:
            return yes
        key = (atom, no, yes)
        if key not in self.unique:
            depth = 1 + max(self.depths[no], self.depths[yes])
            if depth > 256:
                raise ModelError("Boolean decision DAG exceeds depth 256")
            if len(self.nodes) >= 4096:
                raise ModelError("Boolean decision DAG exceeds 4096 nodes")
            self.unique[key] = len(self.nodes)
            self.nodes.append(key)
            self.depths.append(depth)
        return self.unique[key]

    def atom(self, expr):
        key = json.dumps(expr, sort_keys=True)
        self.atoms[key] = expr
        return self.node(key, 0, 1)

    def apply(self, operator, lhs, rhs):
        key = (operator, lhs, rhs)
        if key in self.memo:
            return self.memo[key]
        if lhs < 2 and rhs < 2:
            result = int((bool(lhs) and bool(rhs)) if operator == "and" else (bool(lhs) or bool(rhs)))
        else:
            atoms = [self.nodes[index][0] for index in (lhs, rhs) if index >= 2]
            atom = min(atoms)
            low, high = [], []
            for index in (lhs, rhs):
                if index >= 2 and self.nodes[index][0] == atom:
                    low.append(self.nodes[index][1])
                    high.append(self.nodes[index][2])
                else:
                    low.append(index)
                    high.append(index)
            result = self.node(atom, self.apply(operator, *low), self.apply(operator, *high))
        self.memo[key] = result
        return result

    def negate(self, index):
        key = ("not", index)
        if key not in self.memo:
            if index < 2:
                result = 1 - index
            else:
                atom, no, yes = self.nodes[index]
                result = self.node(atom, self.negate(no), self.negate(yes))
            self.memo[key] = result
        return self.memo[key]

    def convert(self, expr):
        kind = expr["kind"]
        if kind in ("helper_entry", "helper_parameter", "call_result", "call_alive"):
            return self.atom(expr)
        if kind == "boolean":
            return int(expr["value"])
        if kind == "local":
            index = expr["index"]
            if index not in self.locals:
                raise ModelError("Boolean local is not a preceding Boolean binding")
            return self.locals[index]
        if kind == "effect":
            if expr["index"] not in self.effects:
                raise ModelError("Boolean effect is not a preceding event")
            return self.effects[expr["index"]]
        if kind == "not":
            return self.negate(self.convert(expr["arguments"][0]))
        if kind in ("and", "or"):
            return self.apply(kind, *[self.convert(arg) for arg in expr["arguments"]])
        if kind == "choose":
            condition, yes, no = [self.convert(arg) for arg in expr["arguments"]]
            return self.apply("or", self.apply("and", condition, yes), self.apply("and", self.negate(condition), no))
        if kind == "compare":
            arguments = expr["arguments"]
            if arguments[0]["width"] == "bool":
                lhs, rhs = [self.convert(arg) for arg in arguments]
                same = self.apply("or", self.apply("and", lhs, rhs), self.apply("and", self.negate(lhs), self.negate(rhs)))
                return same if expr["operator"] == "==" else self.negate(same)
            normalized = dict(expr, arguments=[resolve_alias(arg, self.model["bindings"]) for arg in arguments])
            return self.atom(normalized)
        raise ModelError(f"Unsupported Boolean field in decision DAG: {kind}")

    def evaluate(self, index, values):
        while index >= 2:
            atom, no, yes = self.nodes[index]
            index = yes if values[atom] else no
        return bool(index)

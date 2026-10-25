"""Packing operations and their guarded legality obligations, checked by Lean."""
from shader_control_lean import ControlEmitter


class PackingEmitter(ControlEmitter):
    def value_type(self, expr):
        if expr["width"] == "uint" or expr.get("payload"):
            return "BitVec 32"
        return super().value_type(expr)

    def field(self, expr):
        if expr["width"] == "uint" or expr.get("payload"):
            if expr["kind"] == "local":
                return f"l{expr['index']}"
            if expr["kind"] == "choose":
                condition, yes, no = [self.field(arg) for arg in expr["arguments"]]
                return f"(fun x => if {condition} x then {yes} x else {no} x)"
            return f"(fun x => {self.element(expr, None, 'x')})"
        return super().field(expr)

    def raw_field(self, expr):
        if expr["kind"] == "compare" and expr["arguments"][0]["width"] == "uint":
            lhs, rhs = [f"({self.element(arg, None, 'x')}).toNat" for arg in expr["arguments"]]
            symbol = {"<": "<", "<=": "≤", ">": ">", ">=": "≥", "==": "=", "!=": "≠"}[expr["operator"]]
            return f"(fun x => {lhs} {symbol} {rhs})"
        return super().raw_field(expr)

    def element(self, expr, index, position):
        kind = expr["kind"]
        if kind == "uint_literal":
            return f"({expr['value']} : BitVec 32)"
        if (expr["width"] == "uint" or expr.get("payload")) and kind in ("local", "choose"):
            return f"({self.field(expr)} {position})"
        if kind in ("carrier", "recover"):
            return self.element(expr["arguments"][0], None, position)
        if kind in ("real_to_uint", "uint_to_real"):
            value = self.element(expr["arguments"][0], None, position)
            return f"(Packing.ofReal {value})" if kind == "real_to_uint" else f"((({value}).toNat : ℕ) : ℝ)"
        if kind.startswith("uint_"):
            args = [self.element(arg, None, position) for arg in expr["arguments"]]
            if kind in ("uint_not", "uint_neg"):
                return f"({'~~~' if kind == 'uint_not' else '-'} {args[0]})"
            if kind in ("uint_shl", "uint_shr"):
                method = "shiftLeft" if kind == "uint_shl" else "shiftRight"
                return f"(Packing.{method} {args[0]} {args[1]})"
            symbol = {"uint_add": "+", "uint_sub": "-", "uint_mul": "*", "uint_and": "&&&", "uint_or": "|||", "uint_xor": "^^^", "uint_shl": "<<<", "uint_shr": ">>>"}[kind]
            return f"({args[0]} {symbol} {args[1]})"
        return super().element(expr, index, position)

    def collect_domains(self, expr, guard):
        condition = None
        if expr["kind"] == "real_to_uint":
            value = self.element(expr["arguments"][0], None, "x")
            condition = f"(0 : ℝ) ≤ {value} ∧ {value} < (4294967296 : ℝ)"
        if expr["kind"] in ("uint_shl", "uint_shr"):
            value = self.element(expr["arguments"][1], None, "x")
            condition = f"({value}).toNat < 32"
        if condition:
            self.domains.append(f"(∀ x : E, ({self.field(guard)} x) → {condition})")
        super().collect_domains(expr, guard)

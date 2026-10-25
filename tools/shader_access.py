"""Conservative source-address dependencies where HLSL does not specify order."""
import re

from shader_ast import ModelError, quoted, source_header


def overlaps(lhs, rhs):
    return lhs[0] == rhs[0] and (lhs[1][:len(rhs[1])] == rhs[1] or rhs[1][:len(lhs[1])] == lhs[1])


def conflict(writes, accesses):
    return any(overlaps(write, access) for write in writes for access in accesses)


def source_address(node, program):
    from shader_validation import lvalue_type
    lvalue_type(node, program)
    if node.kind == "ParenExpr":
        return source_address(node.children[0], program)
    if node.kind == "MemberExpr":
        root, path = source_address(node.children[0], program)
        owner = program.types.node_type(node.children[0])
        return root, path + (program.types.member(node, owner)["name"],)
    match = re.search(r"\b(?:ParmVar|Var) (0x[0-9a-fA-F]+) '", source_header(node.text).group("tail"))
    if match is None:
        raise ModelError("Only whole variables or struct fields are copy-out addresses")
    return match.group(1), ()


def combined(parts, unordered=False):
    if unordered:
        for index, (reads, writes) in enumerate(parts):
            for other_reads, other_writes in parts[index + 1:]:
                if conflict(writes, other_reads | other_writes) or conflict(other_writes, reads | writes):
                    raise ModelError("Order-dependent sibling expressions read/write overlapping addresses")
    reads, writes = set(), set()
    for part_reads, part_writes in parts:
        reads.update(part_reads)
        writes.update(part_writes)
    return reads, writes


class AccessChecker:
    def __init__(self, program):
        self.program = program

    def call(self, node):
        function, _, _ = self.program.checked_call(node)
        nodes = node.children[1:]
        parts, outputs = [], []
        for index, argument in enumerate(nodes):
            mode = "in" if function is None else function["parameters"][index]["mode"]
            if mode != "in":
                address = source_address(self.program.output_argument(argument, function["parameters"][index]), self.program)
                if any(overlaps(address, other) for other in outputs):
                    raise ModelError("Overlapping copy-out addresses have unspecified restoration order")
                outputs.append(address)
                parts.append(({address} if mode == "inout" else set(), set()))
            else:
                parts.append(self.scan(argument))
        reads, writes = combined(parts, unordered=True)
        # The callee writes its output copies after all arguments are evaluated.
        return reads, writes | set(outputs)

    def scan(self, node):
        if node.kind in ("DeclRefExpr", "MemberExpr"):
            return {source_address(node, self.program)}, set()
        if node.kind == "CXXDefaultArgExpr":
            return self.scan(self.program.default_expression(node))
        if node.kind == "CallExpr":
            return self.call(node)
        if node.kind == "CXXMemberCallExpr":
            _, _, _, arguments = self.program.resources.sample(node, self.program.types)
            return combined([self.scan(arg) for arg in arguments], unordered=True)
        if node.kind in ("BinaryOperator", "CompoundAssignOperator"):
            operator = quoted(node.text)[-1] if node.kind == "BinaryOperator" else "compound"
            if operator in ("=", "compound"):
                address = source_address(node.children[0], self.program)
                reads, writes = self.scan(node.children[1])
                if operator == "compound":
                    if conflict(writes, {address}):
                        raise ModelError("Compound assignment depends on an unordered RHS write")
                    reads.add(address)
                return reads, writes | {address}
            return combined([self.scan(child) for child in node.children], unordered=operator not in ("&&", "||"))
        # Conditions/short circuit and statements are sequenced; constructor
        # components are conservatively required to be order independent.
        return combined([self.scan(child) for child in node.children], unordered=node.kind == "InitListExpr")

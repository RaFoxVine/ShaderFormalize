"""Conservative source-address dependencies where HLSL does not specify order."""
import re

from shader_ast import ModelError, quoted, source_header


def overlaps(lhs, rhs):
    if lhs[0] != rhs[0]:
        return False
    for a, b in zip(lhs[1], rhs[1]):
        if a != b and not ((a == "@*" and b.startswith("@")) or (b == "@*" and a.startswith("@"))):
            return False
    return True


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

    def address(self, node, writable=False):
        if hasattr(self.program, "address_spec"):
            spec = self.program.address_spec(node, writable)
            evaluations = combined([self.scan(part) for part in spec.index_nodes()], unordered=True)
            return spec.paths(), evaluations
        return {source_address(node, self.program)}, (set(), set())

    def call(self, node):
        function, _, _ = self.program.checked_call(node)
        nodes = node.children[1:]
        parts, outputs = [], []
        for index, argument in enumerate(nodes):
            mode = "in" if function is None else function["parameters"][index]["mode"]
            if mode != "in":
                addresses, (reads, writes) = self.address(self.program.output_argument(argument, function["parameters"][index]), True)
                if any(overlaps(address, other) for address in addresses for other in outputs):
                    raise ModelError("Overlapping copy-out addresses have unspecified restoration order")
                outputs.extend(addresses)
                parts.append((reads | (addresses if mode == "inout" else set()), writes))
            else:
                parts.append(self.scan(argument))
        reads, writes = combined(parts, unordered=True)
        # The callee writes its output copies after all arguments are evaluated.
        return reads, writes | set(outputs)

    def scan(self, node):
        if hasattr(self.program, "access_address"):
            spec = self.program.access_address(node)
            if spec is not None:
                reads, writes = combined([self.scan(part) for part in spec.index_nodes()], unordered=True)
                return reads | spec.paths(), writes
            if node.kind in ("ArraySubscriptExpr", "CXXOperatorCallExpr"):
                return combined([self.scan(part) for part in self.program.index_operands(node)], unordered=True)
        elif node.kind in ("DeclRefExpr", "MemberExpr"):
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
                addresses, address_access = self.address(node.children[0], True)
                rhs = self.scan(node.children[1])
                reads, writes = combined([address_access, rhs], unordered=True)
                if operator == "compound":
                    if conflict(rhs[1], addresses):
                        raise ModelError("Compound assignment depends on an unordered RHS write")
                    reads.update(addresses)
                return reads, writes | addresses
            return combined([self.scan(child) for child in node.children], unordered=operator not in ("&&", "||"))
        # Conditions/short circuit and statements are sequenced; constructor
        # components are conservatively required to be order independent.
        return combined([self.scan(child) for child in node.children], unordered=node.kind == "InitListExpr")

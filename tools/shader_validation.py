"""Check every function's supported syntax without evaluating uncalled code."""
import re

from shader_ast import ModelError, literal, quoted, source_header
from shader_types import declaration_name


def lvalue_type(node, program):
    kind = program.types.node_type(node)
    if node.kind == "DeclRefExpr" and not node.children:
        if re.search(r"\b(ParmVar|Var) 0x[0-9a-fA-F]+ '", source_header(node.text).group("tail")) is None:
            raise ModelError("Expected a variable declaration reference")
        return kind
    if node.kind == "ParenExpr" and len(node.children) == 1:
        return lvalue_type(node.children[0], program)
    if node.kind == "MemberExpr" and len(node.children) == 1:
        owner = lvalue_type(node.children[0], program)
        return program.types.member(node, owner)["type"]
    raise ModelError("Only whole variables or struct fields are assignable")


def validate_declaration(node, program):
    if node.kind != "VarDecl" or len(node.children) > 1:
        raise ModelError("Unsupported local declaration")
    kind = program.types.node_type(node)
    declaration_name(node)
    flags = source_header(node.text).group("tail").rpartition("'")[2].strip()
    allowed = ("cinit", "nrvo cinit") if node.children else ("", "nrvo")
    if flags not in allowed:
        raise ModelError("Unsupported local declaration flags/initializer")
    if node.children:
        validate_expression(node.children[0], program)
        if program.types.node_type(node.children[0]) != kind:
            raise ModelError("Initializer type mismatch")


def validate_expression(node, program):
    kind = program.types.node_type(node)
    if node.kind in ("DeclRefExpr", "MemberExpr"):
        lvalue_type(node, program)
        return
    if node.kind == "CallExpr":
        program.checked_call(node)
        for argument in node.children[1:]:
            validate_expression(argument, program)
        return
    if node.kind == "ImplicitCastExpr" and len(node.children) == 1:
        match = re.search(r"<([A-Za-z]+)>$", node.text)
        cast = match.group(1) if match else None
        child = node.children[0]
        if cast == "IntegralToFloating" and kind == 1 and child.kind == "IntegerLiteral" and not child.children:
            literal(child, program.source)
            return
        validate_expression(child, program)
        child_type = program.types.node_type(child)
        if cast == "LValueToRValue" and child_type == kind:
            return
        if cast == "FloatingCast" and kind == 1 and quoted(child.text)[:1] == ["literal float"]:
            return
        if cast == "HLSLVectorSplat" and child_type == 1 and isinstance(kind, int) and kind > 1:
            return
        raise ModelError("Unsupported implicit conversion in helper body")
    if node.kind in ("ParenExpr", "CXXFunctionalCastExpr") and len(node.children) == 1:
        if node.kind == "CXXFunctionalCastExpr" and (not isinstance(kind, int) or not node.text.endswith("<NoOp>")):
            raise ModelError("Unsupported constructor")
        validate_expression(node.children[0], program)
        if program.types.node_type(node.children[0]) != kind:
            raise ModelError("Constructor/parenthesis type mismatch")
        return
    if node.kind == "FloatingLiteral" and kind == 1 and not node.children:
        literal(node, program.source)
        return
    if node.kind == "InitListExpr" and isinstance(kind, int) and kind > 1:
        sizes = []
        for child in node.children:
            validate_expression(child, program)
            sizes.append(program.types.node_type(child))
        if not all(isinstance(size, int) for size in sizes) or sum(sizes) != kind:
            raise ModelError("Constructor component count mismatch")
        return
    if node.kind == "HLSLVectorElementExpr" and len(node.children) == 1:
        validate_expression(node.children[0], program)
        owner = program.types.node_type(node.children[0])
        match = re.search(r"\bvectorcomponent ([xyzwrgba]+)$", node.text)
        if match is None or not isinstance(owner, int) or owner == 1 or len(match.group(1)) != kind:
            raise ModelError("Unsupported vector component expression")
        mask = match.group(1)
        alphabet = "xyzw" if mask[0] in "xyzw" else "rgba"
        if any(c not in alphabet or alphabet.index(c) >= owner for c in mask):
            raise ModelError("Invalid vector component mask")
        return
    if node.kind == "UnaryOperator" and len(node.children) == 1 and quoted(node.text)[-1] == "-":
        validate_expression(node.children[0], program)
        if program.types.node_type(node.children[0]) == kind and isinstance(kind, int):
            return
    if node.kind == "BinaryOperator" and len(node.children) == 2 and quoted(node.text)[-1] in ("+", "-", "*"):
        for child in node.children:
            validate_expression(child, program)
        if isinstance(kind, int) and all(program.types.node_type(child) == kind for child in node.children):
            return
    raise ModelError(f"Unsupported expression: {node.kind}")


def validate_block(body, result_type, program):
    returned = False
    for statement in body.children:
        if returned:
            raise ModelError("Statements after return are outside the straight-line subset")
        if statement.kind == "CompoundStmt":
            returned = validate_block(statement, result_type, program)
        elif statement.kind == "DeclStmt" and statement.children:
            for child in statement.children:
                validate_declaration(child, program)
        elif statement.kind in ("BinaryOperator", "CompoundAssignOperator") and len(statement.children) == 2:
            kind = lvalue_type(statement.children[0], program)
            validate_expression(statement.children[1], program)
            if program.types.node_type(statement.children[1]) != kind or program.types.node_type(statement) != kind:
                raise ModelError("Assignment type mismatch")
            if statement.kind == "BinaryOperator":
                if quoted(statement.text)[-1] != "=":
                    raise ModelError("Only assignment is allowed as an expression statement")
            elif not isinstance(kind, int) or re.search(r" lvalue '(\+=|-=|\*=)' ComputeLHSTy='[^']+'(?::'[^']+')? ComputeResultTy='[^']+'(?::'[^']+')?$", statement.text) is None:
                raise ModelError("Unsupported compound assignment")
        elif statement.kind == "ReturnStmt" and len(statement.children) == 1:
            validate_expression(statement.children[0], program)
            if program.types.node_type(statement.children[0]) != result_type:
                raise ModelError("Function return type mismatch")
            returned = True
        elif statement.kind == "CallExpr":
            validate_expression(statement, program)
        else:
            raise ModelError(f"Unsupported statement: {statement.kind}")
    return returned

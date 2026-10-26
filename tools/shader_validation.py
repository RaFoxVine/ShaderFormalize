"""Check every function's supported syntax without evaluating uncalled code."""
import re

from shader_ast import AstNode, ModelError, literal, quoted, source_header
from shader_types import component_mask, declaration_name
from shader_effects import discard_condition


def lvalue_type(node, program):
    extension = program.address_type(node)
    if extension is not None:
        return extension
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
    if not program.types.is_value_type(kind):
        raise ModelError("Local declarations must be numeric or plain records")
    declaration_name(node)
    flags = source_header(node.text).group("tail").rpartition("'")[2].strip()
    allowed = ("cinit", "nrvo cinit") if node.children else ("", "nrvo")
    if flags not in allowed:
        raise ModelError("Unsupported local declaration flags/initializer")
    if node.children:
        validate_expression(node.children[0], program)
        if program.types.node_type(node.children[0]) != kind:
            raise ModelError("Initializer type mismatch")


def validate_expression(node, program, allow_void=False):
    kind = program.types.node_type(node)
    if program.validate_extension(node):
        return
    if program.control and validate_control_expression(node, kind, program):
        return
    if kind == "void" and not allow_void:
        raise ModelError("Void calls are only supported as statements")
    if node.kind == "CXXMemberCallExpr":
        _, _, _, arguments = program.resources.sample(node, program.types)
        for argument in arguments:
            validate_expression(argument, program)
        return
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
        if cast == "HLSLVectorSplat" and child_type == 1 and isinstance(kind, int):
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
        mask = component_mask(node)
        if not isinstance(owner, int) or owner == 1 or len(mask) != kind:
            raise ModelError("Unsupported vector component expression")
        alphabet = "xyzw" if mask[0] in "xyzw" else "rgba"
        if any(c not in alphabet or alphabet.index(c) >= owner for c in mask):
            raise ModelError("Invalid vector component mask")
        return
    if node.kind == "UnaryOperator" and len(node.children) == 1 and quoted(node.text)[-1] == "-":
        validate_expression(node.children[0], program)
        if program.types.node_type(node.children[0]) == kind and isinstance(kind, int):
            return
    operators = ("+", "-", "*", "/") if program.control else ("+", "-", "*")
    if node.kind == "BinaryOperator" and len(node.children) == 2 and quoted(node.text)[-1] in operators:
        for child in node.children:
            validate_expression(child, program)
        if isinstance(kind, int) and all(program.types.node_type(child) == kind for child in node.children):
            return
    raise ModelError(f"Unsupported expression: {node.kind}")


def validate_block(body, result_type, program, effects_allowed=False):
    returned = False
    for statement in body.children:
        if returned:
            raise ModelError("Statements after return are outside the straight-line subset")
        extension = program.validate_statement(statement, result_type, effects_allowed)
        if extension is not None:
            returned = extension
            continue
        if statement.kind == "IfStmt" and program.control:
            condition, yes, no = control_branches(statement, program)
            validate_expression(condition, program)
            yes_return = validate_block(statement_block(yes), result_type, program, effects_allowed)
            no_return = no.kind != "Null" and validate_block(statement_block(no), result_type, program, effects_allowed)
            returned = yes_return and no_return
        elif statement.kind == "DiscardStmt" and program.control and effects_allowed and not statement.children:
            returned = True
        elif statement.kind == "CompoundStmt":
            returned = validate_block(statement, result_type, program, effects_allowed)
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
        elif statement.kind == "ReturnStmt" and not statement.children and result_type == "void":
            returned = True
        elif statement.kind == "CallExpr":
            if program.types.node_type(statement) == "void" and not effects_allowed and not program.allows_void_call(statement):
                raise ModelError("Numeric/record helpers must not change clipping state")
            validate_expression(statement, program, allow_void=True)
        elif statement.kind == "CXXMemberCallExpr":
            validate_expression(statement, program)
        elif statement.kind in ("IfStmt", "DiscardStmt") and effects_allowed:
            if statement.kind == "IfStmt":
                condition = discard_condition(statement, program)
                for child in condition.children:
                    validate_expression(child, program)
            elif statement.children:
                raise ModelError("Unexpected discard children")
        else:
            raise ModelError(f"Unsupported statement: {statement.kind}")
    return returned


def statement_block(node):
    return node if node.kind == "CompoundStmt" else AstNode("CompoundStmt", "", node.line, node.column, [node])


def control_branches(node, program):
    if len(node.children) != 4 or node.children[0].kind != "Null":
        raise ModelError("Unsupported if initializer/attributes")
    _, condition, yes, no = node.children
    if program.types.node_type(condition) != "bool":
        raise ModelError("If conditions must resolve to scalar bool")
    return condition, yes, no


def validate_control_expression(node, kind, program):
    if node.kind == "CXXBoolLiteralExpr" and kind == "bool" and not node.children and node.text.endswith((" true", " false")):
        return True
    if node.kind == "ConditionalOperator" and len(node.children) == 3:
        condition, yes, no = node.children
        if program.types.node_type(condition) != "bool" or kind in ("void", "Texture2D", "SamplerState"):
            raise ModelError("Only scalar bool conditional selection is supported")
        for child in node.children:
            validate_expression(child, program)
        if program.types.node_type(yes) != kind or program.types.node_type(no) != kind:
            raise ModelError("Conditional arm type mismatch")
        return True
    if node.kind == "BinaryOperator" and len(node.children) == 2 and kind == "bool":
        operator = quoted(node.text)[-1]
        kinds = [program.types.node_type(child) for child in node.children]
        valid = (operator in ("&&", "||") and kinds == ["bool", "bool"])
        valid = valid or (operator in ("<", "<=", ">", ">=", "==", "!=") and kinds == [1, 1])
        valid = valid or (operator in ("==", "!=") and kinds == ["bool", "bool"])
        if not valid:
            raise ModelError("Unsupported scalar Boolean operator/types")
        for child in node.children:
            validate_expression(child, program)
        return True
    if node.kind == "UnaryOperator" and kind == "bool" and len(node.children) == 1 and quoted(node.text)[-1] == "!":
        validate_expression(node.children[0], program)
        if program.types.node_type(node.children[0]) != "bool":
            raise ModelError("Boolean negation requires scalar bool")
        return True
    if node.kind == "ImplicitCastExpr" and len(node.children) == 1:
        child = node.children[0]
        if node.text.endswith("<FloatingToBoolean>") and kind == "bool" and program.types.node_type(child) == 1:
            validate_expression(child, program)
            return True
        if node.text.endswith("<IntegralToFloating>") and kind == 1 and quoted(child.text)[:1] in (["bool"], ["const bool"]):
            validate_expression(child, program)
            return True
    return False


def visit_calls(key, graph, active, completed):
    if key in active:
        raise ModelError("Recursive helper definitions are unsupported, including uncalled helpers")
    if key in completed:
        return
    active.add(key)
    for target in graph[key]:
        visit_calls(target, graph, active, completed)
    active.remove(key)
    completed.add(key)


def validate_call_graph(program):
    # Grammar checks cover every definition; so must the nonrecursive subset rule.
    graph = {}
    for key, function in program.functions.items():
        targets = set()
        nodes = list(program.function_roots(function))
        while nodes:
            node = nodes.pop()
            if node.kind == "CallExpr":
                called, _, _ = program.checked_call(node)
                if called is not None:
                    targets.add(called["id"])
            nodes.extend(node.children)
        graph[key] = targets
    completed = set()
    for key in graph:
        visit_calls(key, graph, set(), completed)

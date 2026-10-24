"""Lower typed DXC expressions and straight-line statements into immutable values."""
import re

from shader_ast import ModelError, literal, parse_tree, quoted, source_header, validate_source, width


def reference(kind, size, index):
    return {"kind": kind, "width": size, "index": index}


def operation(kind, size, arguments):
    return {"kind": kind, "width": size, "arguments": arguments}


def identifier(node):
    match = re.match(r" (0x[0-9a-fA-F]+) ", node.text)
    if match is None:
        raise ModelError("Missing declaration identity")
    return match.group(1)


def declaration_name(node):
    head = source_header(node.text).group("tail").split("'")[0].strip()
    match = re.fullmatch(r"(?:used )?([A-Za-z_][A-Za-z0-9_]*)", head)
    if match is None:
        raise ModelError("Unsupported declaration flags")
    return match.group(1)


def symbol_reference(node, symbols, initialized=True):
    match = re.search(r"\b(ParmVar|Var) (0x[0-9a-fA-F]+) '([A-Za-z_][A-Za-z0-9_]*)'", source_header(node.text).group("tail"))
    if node.kind != "DeclRefExpr" or match is None or node.children or match.group(2) not in symbols:
        raise ModelError("Unknown variable reference")
    symbol = symbols[match.group(2)]
    expected_tag = "ParmVar" if symbol["storage"] == "parameter" else "Var"
    if match.group(1) != expected_tag or match.group(3) != symbol["name"] or width(node) != symbol["width"]:
        raise ModelError("Variable reference type/identity mismatch")
    if initialized and symbol["value"] is None:
        raise ModelError(f"Read before initialization: {symbol['name']}")
    return symbol


def swizzle_indices(mask, size):
    alphabet = "xyzw" if all(c in "xyzw" for c in mask) else "rgba"
    if not 1 <= len(mask) <= 4 or any(c not in alphabet or alphabet.index(c) >= size for c in mask):
        raise ModelError("Invalid vector component mask")
    return [alphabet.index(c) for c in mask]


def expression(node, source, symbols):
    size = width(node)
    if node.kind == "DeclRefExpr":
        return symbol_reference(node, symbols)["value"]
    if node.kind == "FloatingLiteral" and size == 1 and not node.children:
        return literal(node, source)
    if node.kind == "ImplicitCastExpr" and len(node.children) == 1:
        match = re.search(r"<([A-Za-z]+)>$", node.text)
        if match is None:
            raise ModelError("Unknown implicit conversion")
        cast = match.group(1)
        child_node = node.children[0]
        if cast == "IntegralToFloating" and child_node.kind == "IntegerLiteral" and not child_node.children and size == 1:
            return literal(child_node, source)
        if cast == "FloatingCast" and quoted(child_node.text)[:1] == ["literal float"] and size == 1:
            return expression(child_node, source, symbols)
        child = expression(child_node, source, symbols)
        if cast == "LValueToRValue" and child["width"] == size:
            return child
        if cast == "HLSLVectorSplat" and child["width"] == 1 and size > 1:
            return operation("splat", size, [child])
        raise ModelError(f"Unsupported conversion: {cast}")
    if node.kind in ("ParenExpr", "CXXFunctionalCastExpr") and len(node.children) == 1:
        if node.kind == "CXXFunctionalCastExpr" and not node.text.endswith("<NoOp>"):
            raise ModelError("Only component-preserving vector constructors are supported")
        child = expression(node.children[0], source, symbols)
        if child["width"] != size:
            raise ModelError("Constructor/parenthesis type mismatch")
        return child
    if node.kind == "InitListExpr" and size > 1:
        arguments = [expression(child, source, symbols) for child in node.children]
        if sum(arg["width"] for arg in arguments) != size:
            raise ModelError("Constructor component count mismatch")
        return operation("construct", size, arguments)
    if node.kind == "HLSLVectorElementExpr" and len(node.children) == 1:
        match = re.search(r"\bvectorcomponent ([xyzwrgba]+)$", node.text)
        child = expression(node.children[0], source, symbols)
        if match is None or child["width"] == 1:
            raise ModelError("Unsupported vector component expression")
        indices = swizzle_indices(match.group(1), child["width"])
        if len(indices) != size:
            raise ModelError("Component selection type mismatch")
        result = operation("swizzle", size, [child])
        result["indices"] = indices
        return result
    if node.kind == "UnaryOperator" and len(node.children) == 1 and quoted(node.text)[-1] == "-":
        child = expression(node.children[0], source, symbols)
        if child["width"] != size:
            raise ModelError("Unary type mismatch")
        return operation("negate", size, [child])
    if node.kind == "BinaryOperator" and len(node.children) == 2:
        operator = quoted(node.text)[-1]
        names = {"+": "add", "-": "subtract", "*": "multiply"}
        if operator not in names:
            raise ModelError(f"Unsupported operator in expression: {operator}")
        arguments = [expression(child, source, symbols) for child in node.children]
        if any(arg["width"] != size for arg in arguments):
            raise ModelError("Binary operand type mismatch")
        return operation(names[operator], size, arguments)
    if node.kind == "CallExpr" and node.children:
        return intrinsic(node, source, symbols)
    raise ModelError(f"Unsupported AST node: {node.kind}")


def float_type(size):
    return "float" if size == 1 else f"vector<float,{size}>"


def intrinsic(node, source, symbols):
    size = width(node)
    callee = node.children[0]
    if callee.kind != "ImplicitCastExpr" or not callee.text.endswith("<FunctionToPointerDecay>") or len(callee.children) != 1:
        raise ModelError("Unsupported callee")
    target = callee.children[0]
    match = re.search(r"\bFunction 0x[0-9a-fA-F]+ '(lerp|saturate|dot|normalize)' '([^']+)'$", source_header(target.text).group("tail"))
    if target.kind != "DeclRefExpr" or target.children or match is None:
        raise ModelError("Only whitelisted compiler-provided intrinsics are supported")
    name, signature = match.groups()
    arguments = [expression(child, source, symbols) for child in node.children[1:]]
    widths = [arg["width"] for arg in arguments]
    valid = False
    if name in ("lerp", "saturate"):
        count = 3 if name == "lerp" else 1
        valid = widths == [size] * count
    elif name == "normalize":
        valid = size > 1 and widths == [size]
    elif name == "dot":
        valid = size == 1 and len(widths) == 2 and widths[0] > 1 and widths[0] == widths[1]
    expected = float_type(size) + "(" + ",".join(float_type(w) for w in widths) + ")"
    if not valid or signature.replace(" ", "") != expected:
        raise ModelError("Unsupported intrinsic overload")
    return operation(name, size, arguments)


def bind_value(symbol, value, bindings):
    if symbol["width"] != value["width"]:
        raise ModelError("Assignment type mismatch")
    index = len(bindings)
    bindings.append({"index": index, "name": symbol["name"], "width": symbol["width"], "expression": value})
    symbol["value"] = reference("local", symbol["width"], index)


def lower_body(body, source, symbols):
    bindings = []
    returned = None
    for statement in body.children:
        if returned is not None:
            raise ModelError("Statements after return are outside the straight-line subset")
        if statement.kind == "DeclStmt":
            if not statement.children:
                raise ModelError("Empty declaration statement")
            for declaration in statement.children:
                if declaration.kind != "VarDecl" or len(declaration.children) > 1:
                    raise ModelError("Unsupported local declaration")
                name = declaration_name(declaration)
                tail = source_header(declaration.text).group("tail")
                if declaration.children and not tail.endswith(" cinit"):
                    raise ModelError("Unsupported initializer")
                symbol = {"name": name, "width": width(declaration), "storage": "local", "value": None}
                key = identifier(declaration)
                if key in symbols:
                    raise ModelError("Repeated declaration identity")
                symbols[key] = symbol
                if declaration.children:
                    bind_value(symbol, expression(declaration.children[0], source, symbols), bindings)
        elif statement.kind in ("BinaryOperator", "CompoundAssignOperator") and len(statement.children) == 2:
            symbol = symbol_reference(statement.children[0], symbols, initialized=statement.kind == "CompoundAssignOperator")
            if symbol["storage"] != "local":
                raise ModelError("Only local variables may be assigned")
            value = expression(statement.children[1], source, symbols)
            if value["width"] != symbol["width"]:
                raise ModelError("Assignment operand width mismatch")
            if statement.kind == "CompoundAssignOperator":
                match = re.search(r" lvalue '(\+=|-=|\*=)' ComputeLHSTy='[^']+'(?::'[^']+')? ComputeResultTy='[^']+'(?::'[^']+')?$", statement.text)
                if match is None or width(statement) != symbol["width"]:
                    raise ModelError("Unsupported compound assignment")
                value = operation({"+=": "add", "-=": "subtract", "*=": "multiply"}[match.group(1)], symbol["width"], [symbol["value"], value])
            elif quoted(statement.text)[-1] != "=":
                raise ModelError("Only assignment is allowed as an expression statement")
            bind_value(symbol, value, bindings)
        elif statement.kind == "ReturnStmt" and len(statement.children) == 1:
            returned = expression(statement.children[0], source, symbols)
        else:
            raise ModelError(f"Unsupported statement: {statement.kind}")
    if returned is None or returned["width"] != 4:
        raise ModelError("Expected a terminal float4 return")
    return bindings, returned


def semantic(node):
    match = re.search(r'"([A-Za-z_][A-Za-z0-9_]*)"$', node.text)
    if node.kind != "SemanticDecl" or node.children or match is None:
        raise ModelError("Unsupported semantic")
    return match.group(1).upper()


def buffer_declaration(node):
    name_match = re.fullmatch(r" cbuffer ([A-Za-z_][A-Za-z0-9_]*)", source_header(node.text).group("tail"))
    if name_match is None or not node.children or node.children[0].kind != "RegisterAssignment":
        raise ModelError("Expected one explicitly registered cbuffer")
    register = node.children[0]
    if register.children or source_header(register.text).group("tail").strip() != "register(b0)":
        raise ModelError("Only register(b0) is currently supported")
    fields = []
    for field in node.children[1:]:
        if field.kind != "VarDecl" or field.children:
            raise ModelError("Only plain float/vector cbuffer fields are supported")
        parent = re.search(r" parent cbuffer (0x[0-9a-fA-F]+) ", field.text)
        if parent is None or parent.group(1) != identifier(node):
            raise ModelError("Cbuffer field owner mismatch")
        fields.append(field)
    if not fields:
        raise ModelError("Empty cbuffer")
    return {"name": name_match.group(1), "register": "b0"}, fields


def import_shader(source, dump):
    validate_source(source)
    root = parse_tree(dump)
    function = None
    buffer = None
    fields = []
    for node in root.children:
        if node.kind == "HLSLBufferDecl" and buffer is None:
            buffer, fields = buffer_declaration(node)
        elif node.kind == "FunctionDecl" and function is None:
            function = node
        elif node.kind == "EmptyDecl" and not node.children and not source_header(node.text).group("tail").strip():
            continue
        else:
            raise ModelError("Only one main and one optional cbuffer are supported; no user functions")
    if function is None or not re.search(r"\bmain 'float4 \([^']*\)'$", source_header(function.text).group("tail")):
        raise ModelError("Expected a float4 main entry")
    interface = []
    symbols = {}
    body = None
    output = None
    stages = 0
    for node in function.children:
        if node.kind == "ParmVarDecl":
            if len(node.children) != 1:
                raise ModelError("Each value parameter needs exactly one semantic")
            name = declaration_name(node)
            item = {"index": len(interface), "name": name, "width": width(node), "semantic": semantic(node.children[0]), "storage": "parameter"}
            interface.append(item)
            symbols[identifier(node)] = dict(item, value=reference("parameter", item["width"], item["index"]))
        elif node.kind == "CompoundStmt" and body is None:
            body = node
        elif node.kind == "SemanticDecl" and output is None:
            output = semantic(node)
        elif node.kind == "HLSLShaderAttr" and node.text.endswith('Implicit "pixel"') and not node.children:
            stages += 1
        else:
            raise ModelError(f"Unsupported function declaration child: {node.kind}")
    for field in fields:
        name = declaration_name(field)
        item = {"index": len(interface), "name": name, "width": width(field), "semantic": None, "storage": "uniform", "buffer": buffer["name"], "register": buffer["register"]}
        interface.append(item)
        symbols[identifier(field)] = dict(item, value=reference("parameter", item["width"], item["index"]))
    if not 1 <= len(interface) <= 24 or len({item["name"] for item in interface}) != len(interface):
        raise ModelError("Invalid/ambiguous input declarations")
    if body is None or output not in ("SV_TARGET", "SV_TARGET0") or stages != 1:
        raise ModelError("Expected a single pixel color output")
    bindings, value = lower_body(body, source, symbols)
    return {"schema": 2, "interface": interface, "buffer": buffer, "output_semantic": output, "bindings": bindings, "expression": value}

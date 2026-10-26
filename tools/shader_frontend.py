"""Interpret typed DXC declarations into immutable numeric bindings, over reals."""
import re

from shader_validation import validate_block, validate_call_graph, validate_declaration
from shader_ast import ModelError, literal, parse_tree, quoted, source_header, validate_source, width
from shader_types import (TypeRegistry, component_mask, declaration_name, identifier, initialized, numeric_type,
                          operation, read_path, reference, replace_path, semantic, value_type)
from shader_effects import DERIVATIVES, Resources, discard_condition
from shader_math import MATH_INTRINSICS, valid_math_shape

INTRINSICS = {"lerp", "saturate", "dot", "normalize", "clip", "asuint", "asfloat"} | DERIVATIVES | MATH_INTRINSICS


def swizzle_indices(mask, size):
    alphabet = "xyzw" if all(c in "xyzw" for c in mask) else "rgba"
    if not 1 <= len(mask) <= 4 or any(c not in alphabet or alphabet.index(c) >= size for c in mask):
        raise ModelError("Invalid vector component mask")
    return [alphabet.index(c) for c in mask]


def buffer_declaration(node, check_numeric=True):
    match = re.fullmatch(r" cbuffer ([A-Za-z_][A-Za-z0-9_]*)", source_header(node.text).group("tail"))
    if match is None or not node.children or node.children[0].kind != "RegisterAssignment":
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
        if check_numeric:
            width(field)
        fields.append(field)
    if not fields:
        raise ModelError("Empty cbuffer")
    return {"name": match.group(1), "register": "b0"}, fields


def function_declaration(node, types):
    name = declaration_name(node)
    if name in INTRINSICS:
        raise ModelError("User functions may not redefine reserved intrinsics")
    signature = quoted(node.text)[0]
    match = re.fullmatch(r"(.+) \((.*)\)", signature)
    if match is None:
        raise ModelError("Unsupported function signature")
    tail = source_header(node.text).group("tail")
    suffix = tail[tail.index("'" + signature + "'") + len(signature) + 2:].strip()
    if suffix not in ("", "static", "inline", "static inline"):
        raise ModelError("Unsupported function qualifiers")
    result_type = types.named_type(match.group(1))
    parameters, body, output, stages = [], None, None, 0
    for child in node.children:
        if child.kind == "ParmVarDecl":
            parameters.append(types.parameter_metadata(child))
            if not types.is_value_type(parameters[-1]["type"]):
                raise ModelError("Helper/entry parameters must be numeric or plain records")
        elif child.kind == "CompoundStmt" and body is None:
            body = child
        elif child.kind == "SemanticDecl" and output is None:
            output = semantic(child)
        elif child.kind == "HLSLShaderAttr" and child.text.endswith('Implicit "pixel"') and not child.children:
            stages += 1
        else:
            raise ModelError(f"Unsupported function declaration child: {child.kind}")
    if body is None or len(parameters) > 64:
        raise ModelError("Function must have a definition; prototypes are unsupported")
    if name == "main":
        if any(p.get("mode", "in") != "in" or p.get("default") is not None for p in parameters):
            raise ModelError("Entry parameters must be ordinary inputs without defaults")
        if result_type != 4 or output not in ("SV_TARGET", "SV_TARGET0") or stages != 1:
            raise ModelError("Expected a float4 pixel main with one color output")
    elif output is not None or stages or any(p["semantic"] is not None for p in parameters):
        raise ModelError("Helpers must have ordinary by-value parameters and result")
    return {"id": identifier(node), "name": name, "type": result_type, "parameters": parameters,
            "body": body, "output": output, "signature": signature}


def make_symbol(name, kind, tag, writable, value):
    return {"name": name, "type": kind, "tag": tag, "writable": writable, "value": value}


def callee_reference(node):
    if not node.children:
        raise ModelError("Missing callee")
    callee = node.children[0]
    if callee.kind != "ImplicitCastExpr" or not callee.text.endswith("<FunctionToPointerDecay>") or len(callee.children) != 1:
        raise ModelError("Unsupported callee")
    target = callee.children[0]
    match = re.search(r"\bFunction (0x[0-9a-fA-F]+) '([A-Za-z_][A-Za-z0-9_]*)' '([^']+)'$", source_header(target.text).group("tail"))
    if target.kind != "DeclRefExpr" or target.children or match is None:
        raise ModelError("Unsupported function reference")
    return match.groups()


class Program:
    control = False
    packing = False
    type_registry = TypeRegistry

    def read_buffer(self, node):
        return buffer_declaration(node)

    def address_type(self, node):
        return None

    def validate_statement(self, node, result_type, effects_allowed):
        return None

    def assign_statement(self, node, symbols):
        return False

    def validate_extension(self, node):
        return False

    def prepare_function_validation(self):
        pass

    def validate_extra_definitions(self):
        pass

    def function_roots(self, function):
        return [function["body"]]

    def allows_void_call(self, node):
        return False

    def __init__(self, source, dump):
        validate_source(source)
        self.source = source
        root = parse_tree(dump)
        records, functions, resources = [], [], []
        self.buffer, self.fields = None, []
        for node in root.children:
            if node.kind == "CXXRecordDecl":
                records.append(node)
            elif node.kind == "FunctionDecl":
                functions.append(node)
            elif node.kind == "HLSLBufferDecl" and self.buffer is None:
                self.buffer, self.fields = self.read_buffer(node)
            elif node.kind == "VarDecl":
                resources.append(node)
            elif node.kind == "EmptyDecl" and not node.children and not source_header(node.text).group("tail").strip():
                continue
            else:
                raise ModelError(f"Unsupported top-level declaration: {node.kind}")
        self.types = self.type_registry(records, allow_bool=self.control)
        self.resources = Resources(resources, self.types)
        self.functions, self.main = {}, None
        for node in functions:
            function = function_declaration(node, self.types)
            if function["id"] in self.functions or len(self.functions) >= 128:
                raise ModelError("Repeated or excessive function definitions")
            self.functions[function["id"]] = function
            if function["name"] == "main":
                if self.main is not None:
                    raise ModelError("Repeated main entry")
                self.main = function
        if self.main is None:
            raise ModelError("Missing main entry")
        self.prepare_function_validation()
        for function in self.functions.values():
            if not validate_block(function["body"], function["type"], self,
                                  function is self.main or function["type"] == "void") and function["type"] != "void":
                raise ModelError("Every function requires a terminal return")
        validate_call_graph(self)
        self.validate_extra_definitions()
        self.bindings, self.stack = [], []
        self.invocations = 0
        self.effects, self.events = [], []
        self.fragment = bool(resources)
        self.globals = {}

    def snapshot(self, value, name):
        initialized(value)
        if value["kind"] == "record":
            fields = {}
            for field_name, field in value["fields"].items():
                fields[field_name] = self.snapshot(field, name + "." + field_name)
            return dict(value, fields=fields)
        if len(self.bindings) >= 4096:
            raise ModelError("Program exceeds 4096 numeric bindings")
        index = len(self.bindings)
        self.bindings.append({"index": index, "name": name, "width": value["width"], "expression": value})
        self.events.append({"binding": index})
        return reference("local", value["width"], index)

    def effect(self, value):
        if len(self.effects) >= 128:
            raise ModelError("Program exceeds 128 clipping events")
        self.fragment = True
        self.events.append({"effect": len(self.effects)})
        self.effects.append(value)

    def sample(self, node, symbols):
        mode, texture, sampler, nodes = self.resources.sample(node, self.types)
        arguments = [self.expression(child, symbols) for child in nodes]
        self.fragment = True
        value = dict(operation("sample", 4, arguments), mode=mode, texture=texture,
                     sampler=sampler, context=len(self.effects))
        return self.snapshot(value, "texture." + mode)

    def lvalue(self, node, symbols):
        if node.kind == "ParenExpr" and len(node.children) == 1:
            return self.lvalue(node.children[0], symbols)
        if node.kind == "DeclRefExpr" and not node.children:
            match = re.search(r"\b(ParmVar|Var) (0x[0-9a-fA-F]+) '([A-Za-z_][A-Za-z0-9_]*)'", source_header(node.text).group("tail"))
            if match is None or match.group(2) not in symbols:
                raise ModelError("Unknown variable reference")
            symbol = symbols[match.group(2)]
            if match.group(1) != symbol["tag"] or match.group(3) != symbol["name"] or self.types.node_type(node) != symbol["type"]:
                raise ModelError("Variable reference type/identity mismatch")
            return symbol, [], symbol["type"]
        if node.kind == "MemberExpr" and len(node.children) == 1:
            symbol, path, owner_type = self.lvalue(node.children[0], symbols)
            field = self.types.member(node, owner_type)
            return symbol, path + [field["name"]], field["type"]
        raise ModelError("Only whole variables or struct fields are assignable")

    def expression(self, node, symbols):
        kind = self.types.node_type(node)
        if node.kind == "CXXMemberCallExpr":
            return self.sample(node, symbols)
        if node.kind in ("DeclRefExpr", "MemberExpr"):
            symbol, path, expected = self.lvalue(node, symbols)
            value = initialized(read_path(symbol["value"], path))
            if value_type(value) != expected:
                raise ModelError("Read value type mismatch")
            return value
        if node.kind == "CallExpr" and node.children:
            return self.call(node, symbols)
        if node.kind == "ImplicitCastExpr" and len(node.children) == 1:
            match = re.search(r"<([A-Za-z]+)>$", node.text)
            if match is None:
                raise ModelError("Unknown implicit conversion")
            cast, child_node = match.group(1), node.children[0]
            if cast == "IntegralToFloating" and child_node.kind == "IntegerLiteral" and not child_node.children and kind == 1:
                return literal(child_node, self.source)
            if cast == "FloatingCast" and quoted(child_node.text)[:1] == ["literal float"] and kind == 1:
                return self.expression(child_node, symbols)
            child = self.expression(child_node, symbols)
            if cast == "LValueToRValue" and value_type(child) == kind:
                return child
            if cast == "HLSLVectorSplat" and value_type(child) == 1 and isinstance(kind, int):
                return child if kind == 1 else operation("splat", kind, [child])
            raise ModelError(f"Unsupported conversion: {cast}")
        if node.kind in ("ParenExpr", "CXXFunctionalCastExpr") and len(node.children) == 1:
            if node.kind == "CXXFunctionalCastExpr" and (not isinstance(kind, int) or not node.text.endswith("<NoOp>")):
                raise ModelError("Only component-preserving vector constructors are supported")
            child = self.expression(node.children[0], symbols)
            if value_type(child) != kind:
                raise ModelError("Constructor/parenthesis type mismatch")
            return child
        if not isinstance(kind, int):
            raise ModelError(f"Unsupported record expression: {node.kind}")
        if node.kind == "FloatingLiteral" and kind == 1 and not node.children:
            return literal(node, self.source)
        if node.kind == "InitListExpr" and kind > 1:
            arguments = [self.expression(child, symbols) for child in node.children]
            if any(not isinstance(value_type(arg), int) for arg in arguments) or sum(arg["width"] for arg in arguments) != kind:
                raise ModelError("Constructor component count mismatch")
            return operation("construct", kind, arguments)
        if node.kind == "HLSLVectorElementExpr" and len(node.children) == 1:
            mask = component_mask(node)
            child = self.expression(node.children[0], symbols)
            if not isinstance(value_type(child), int) or child["width"] == 1:
                raise ModelError("Unsupported vector component expression")
            indices = swizzle_indices(mask, child["width"])
            if len(indices) != kind:
                raise ModelError("Component selection type mismatch")
            return dict(operation("swizzle", kind, [child]), indices=indices)
        if node.kind == "UnaryOperator" and len(node.children) == 1 and quoted(node.text)[-1] == "-":
            child = self.expression(node.children[0], symbols)
            if value_type(child) != kind:
                raise ModelError("Unary type mismatch")
            return operation("negate", kind, [child])
        if node.kind == "BinaryOperator" and len(node.children) == 2:
            names = {"+": "add", "-": "subtract", "*": "multiply", "/": "divide"}
            operator = quoted(node.text)[-1]
            if operator not in names:
                raise ModelError(f"Unsupported operator in expression: {operator}")
            if operator == "/" and not self.control:
                raise ModelError("Real division requires the guarded frontend")
            arguments = [self.expression(child, symbols) for child in node.children]
            if any(value_type(arg) != kind for arg in arguments):
                raise ModelError("Binary operand type mismatch")
            value = operation(names[operator], kind, arguments)
            return self.snapshot(value, "divide") if operator == "/" else value
        raise ModelError(f"Unsupported AST node: {node.kind}")

    def checked_call(self, node):
        key, name, signature = callee_reference(node)
        size = self.types.node_type(node)
        widths = [self.types.node_type(child) for child in node.children[1:]]
        if key in self.functions:
            function = self.functions[key]
            if function["name"] != name or function["signature"] != signature or function is self.main:
                raise ModelError("Function reference identity/signature mismatch")
            if size != function["type"] or widths != [param["type"] for param in function["parameters"]]:
                raise ModelError("Function call argument/result type mismatch")
            return function, name, size
        valid = False
        if name in MATH_INTRINSICS:
            valid = self.control and valid_math_shape(name, size, widths)
        elif name in ("lerp", "saturate"):
            valid = widths == [size] * (3 if name == "lerp" else 1)
        elif name == "normalize":
            valid = isinstance(size, int) and size > 1 and widths == [size]
        elif name == "dot":
            valid = size == 1 and len(widths) == 2 and isinstance(widths[0], int) and widths[0] > 1 and widths[0] == widths[1]
        elif name in DERIVATIVES:
            valid = isinstance(size, int) and widths == [size]
        elif name == "clip":
            valid = size == "void" and len(widths) == 1 and isinstance(widths[0], int)
        if not valid or (not isinstance(size, int) and size != "void"):
            raise ModelError("Only defined helpers and whitelisted compiler intrinsics are supported")
        expected = ("void" if size == "void" else numeric_type(size)) + "(" + ",".join(numeric_type(w) for w in widths) + ")"
        signature = signature.replace(" ", "")
        for n in (1, 2, 3, 4):
            signature = signature.replace(f"vector<float,{n}>", f"float{n}")
        signature = re.sub(r"\bfloat1\b", "float", signature)
        if signature != expected:
            raise ModelError("Unsupported intrinsic overload")
        return None, name, size

    def call(self, node, symbols):
        function, name, size = self.checked_call(node)
        arguments = [self.expression(child, symbols) for child in node.children[1:]]
        if function is not None:
            return self.invoke(function, arguments)
        if name == "clip":
            argument = self.snapshot(arguments[0], "clip.argument")
            self.effect(operation("keep", "bool", [argument]))
            return {"kind": "void", "width": "void"}
        if name in DERIVATIVES:
            self.fragment = True
            value = dict(operation("derivative", size, arguments), mode=name, context=len(self.effects))
            return self.snapshot(value, name)
        return operation(name, size, arguments)

    def invoke(self, function, arguments):
        self.check_invocation(function)
        if len(arguments) != len(function["parameters"]):
            raise ModelError("Function argument count mismatch")
        symbols = dict(self.globals)
        for param, argument in zip(function["parameters"], arguments):
            initialized(argument)
            if value_type(argument) != param["type"]:
                raise ModelError("Function argument type mismatch")
            if function is not self.main:
                # HLSL evaluates all arguments, even ones the callee ignores or overwrites.
                argument = self.snapshot(argument, function["name"] + "." + param["name"])
            symbols[param["id"]] = make_symbol(param["name"], param["type"], "ParmVar", function is not self.main, argument)
        self.stack.append(function["id"])
        try:
            returned, result = self.block(function["body"], symbols)
            if function["type"] == "void":
                return {"kind": "void", "width": "void"}
            if result is None or value_type(initialized(result)) != function["type"]:
                raise ModelError("Function needs a terminal return with matching type")
            # Every call leaves bindings, including calls whose results are unused.
            return result if function is self.main else self.snapshot(result, function["name"] + ".return")
        finally:
            self.stack.pop()

    def check_invocation(self, function):
        self.invocations += 1
        if self.invocations > 4096 or function["id"] in self.stack or len(self.stack) >= 32:
            raise ModelError("Recursive or excessive helper expansion")

    def validate_helper_initialization(self):
        # Run the same symbolic value rules for uncalled definitions as well.
        # Constant placeholders are initialized typed values; no arithmetic is
        # evaluated here. Discard temporary bindings/effects/domain expressions.
        from shader_control_values import zero_value
        names = ("bindings", "events", "effects", "stack", "fragment", "invocations")
        if self.control:
            names += ("current_guard", "alive", "frame", "branches")
        saved = {name: getattr(self, name) for name in names}
        try:
            for function in self.functions.values():
                if function is self.main:
                    continue
                self.bindings, self.events, self.effects, self.stack = [], [], [], []
                self.invocations = 0
                if self.control:
                    from shader_control_values import truth
                    self.current_guard, self.alive, self.frame, self.branches = truth(True), truth(True), None, 0
                arguments = [zero_value(param["type"], self.types) for param in function["parameters"]]
                self.invoke(function, arguments)
        finally:
            for name, value in saved.items():
                setattr(self, name, value)

    def block(self, body, symbols):
        did_return = False
        returned = None
        for statement in body.children:
            if did_return:
                raise ModelError("Statements after return are outside the straight-line subset")
            if statement.kind == "CompoundStmt":
                did_return, returned = self.block(statement, dict(symbols))
            elif statement.kind == "DeclStmt" and statement.children:
                for declaration in statement.children:
                    validate_declaration(declaration, self)
                    kind, name = self.types.node_type(declaration), declaration_name(declaration)
                    key = identifier(declaration)
                    if key in symbols:
                        raise ModelError("Repeated declaration identity")
                    symbol = make_symbol(name, kind, "Var", True, self.types.empty(kind))
                    symbols[key] = symbol
                    if declaration.children:
                        value = self.expression(declaration.children[0], symbols)
                        if value_type(value) != kind:
                            raise ModelError("Initializer type mismatch")
                        symbol["value"] = self.snapshot(value, name)
            elif self.assign_statement(statement, symbols):
                continue
            elif statement.kind in ("BinaryOperator", "CompoundAssignOperator") and len(statement.children) == 2:
                symbol, path, kind = self.lvalue(statement.children[0], symbols)
                if not symbol["writable"]:
                    raise ModelError("Only locals and by-value helper parameters may be assigned")
                value = self.expression(statement.children[1], symbols)
                if value_type(value) != kind:
                    raise ModelError("Assignment operand type mismatch")
                if statement.kind == "CompoundAssignOperator":
                    match = re.search(r" lvalue '(\+=|-=|\*=)' ComputeLHSTy='[^']+'(?::'[^']+')? ComputeResultTy='[^']+'(?::'[^']+')?$", statement.text)
                    if match is None or not isinstance(kind, int) or self.types.node_type(statement) != kind:
                        raise ModelError("Unsupported compound assignment")
                    old = initialized(read_path(symbol["value"], path))
                    value = operation({"+=": "add", "-=": "subtract", "*=": "multiply"}[match.group(1)], kind, [old, value])
                elif quoted(statement.text)[-1] != "=":
                    raise ModelError("Only assignment is allowed as an expression statement")
                value = self.snapshot(value, ".".join([symbol["name"]] + path))
                symbol["value"] = replace_path(symbol["value"], path, value)
            elif statement.kind == "ReturnStmt" and len(statement.children) == 1:
                returned = initialized(self.expression(statement.children[0], symbols))
                did_return = True
            elif statement.kind == "ReturnStmt" and not statement.children:
                did_return = True
            elif statement.kind in ("CallExpr", "CXXMemberCallExpr"):
                value = self.expression(statement, symbols)
                if value_type(value) != "void":
                    self.snapshot(value, "unused.call")
            elif statement.kind == "DiscardStmt":
                self.effect(operation("never", "bool", []))
            elif statement.kind == "IfStmt":
                condition = discard_condition(statement, self)
                arguments = [self.snapshot(self.expression(child, symbols), "discard.argument") for child in condition.children]
                self.effect(dict(operation("unless", "bool", arguments), operator=quoted(condition.text)[-1]))
            else:
                raise ModelError(f"Unsupported statement: {statement.kind}")
        return did_return, returned

    def uniform_inputs(self, interface):
        for field in self.fields:
            name, size = declaration_name(field), width(field)
            index = len(interface)
            interface.append({"index": index, "name": name, "width": size, "semantic": None,
                              "storage": "uniform", "buffer": self.buffer["name"], "register": self.buffer["register"]})
            self.globals[identifier(field)] = make_symbol(name, size, "Var", False, reference("parameter", size, index))

    def model(self):
        interface, entry_layout, arguments = [], [], []
        for param in self.main["parameters"]:
            entry_layout.append(dict(self.types.layout(param["type"]), name=param["name"], semantic=param["semantic"]))
            arguments.append(self.types.input_value(param["type"], param["name"], param["semantic"], interface))
        self.uniform_inputs(interface)
        if not 1 <= len(interface) <= 64 or len({item["name"] for item in interface}) != len(interface):
            raise ModelError("Invalid/ambiguous input declarations")
        self.interface = interface
        self.validate_helper_initialization()
        result = self.invoke(self.main, arguments)
        model = {"schema": 3 if self.fragment else 2, "interface": interface, "entry_layout": entry_layout, "buffer": self.buffer,
                 "output_semantic": self.main["output"], "bindings": self.bindings, "expression": result}
        if self.fragment:
            model.update(resources=self.resources.layout, events=self.events, effects=self.effects)
        return model


def import_shader(source, dump, frontend="auto"):
    if frontend == "shared":
        from shader_loops import LoopProgram
        return LoopProgram(source, dump).model()
    if frontend != "auto":
        raise ModelError("Unknown frontend", "INVALID_INPUT")
    from shader_control_values import uses_control
    from shader_packing import PackingProgram, uses_packing
    from shader_math import uses_basic_math
    root = parse_tree(dump)
    if uses_packing(root):
        return PackingProgram(source, dump).model()
    if uses_control(root) or uses_basic_math(root):
        from shader_control import ControlProgram
        return ControlProgram(source, dump).model()
    return Program(source, dump).model()

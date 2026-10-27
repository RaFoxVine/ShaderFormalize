"""Typed DXC Compute texture profile, with guarded domains and 2D addresses."""
import copy
from fractions import Fraction
import re

from shader_ast import ModelError, exact_number, parse_tree, quoted, source_header, validate_source
from shader_compute import ComputeProgram, boolean, logical, variable_reference
from shader_compute_math import (COMPUTE_MATH, evaluate_expression, integer_type, lanes,
                                 lean_expression, lean_type, scalar_type, signed)
from shader_frontend import Program, buffer_declaration, callee_reference, function_declaration, make_symbol, swizzle_indices
from shader_packing import PackingTypes, uint_literal
from shader_types import component_mask, declaration_name, identifier, initialized, operation, semantic, value_type
from shader_lean import lean_number


class TextureTypes(PackingTypes):
    extra_leaves = ("uint", "uint2", "uint3", "int", "int2", "int3")

    def named_type(self, name):
        name = name.removeprefix("const ")
        match = re.fullmatch(r"vector<(unsigned int|uint|int), ([23])>", name)
        if match:
            return ("uint" if match.group(1) in ("unsigned int", "uint") else "int") + match.group(2)
        if name in self.extra_leaves:
            return name
        return super().named_type(name)

    def node_type(self, node):
        names = quoted(node.text)
        if not names:
            raise ModelError("Missing typed texture expression")
        if names[0] == "literal int":
            return "literal_int"
        name = names[0].removeprefix("const ")
        if name in self.extra_leaves or re.fullmatch(r"vector<(unsigned int|uint|int), ([23])>", name):
            return self.named_type(name)
        return super().node_type(node)


class TextureProgram(ComputeProgram):
    control = True

    def __init__(self, source, dump):
        validate_source(source)
        self.source = source
        self.types = TextureTypes([], allow_bool=True)
        self.resources, self.resource_ids = [], {}
        self.uniform, self.entry = None, None
        self.bindings, self.events = [], []
        self.functions, self.symbols = {}, {}
        self.main = None
        self.guard = boolean(True)
        self.stack = []
        self.helper_returns = []
        self.invocations = 0
        root = parse_tree(dump)
        for node in root.children:
            if node.kind == "VarDecl":
                self.resource_declaration(node)
            elif node.kind == "HLSLBufferDecl" and self.uniform is None:
                self.uniform_declaration(node)
            elif node.kind == "FunctionDecl":
                if declaration_name(node) == "main" and self.entry is None:
                    self.entry_declaration(node)
                else:
                    function = function_declaration(node, self.types)
                    if function["type"] not in (1, 2, 3, 4) or any(p["type"] not in (1, 2, 3, 4) or p["semantic"] is not None for p in function["parameters"]):
                        raise ModelError("Compute helpers require float by-value parameters and result")
                    self.functions[function["id"]] = function
            elif node.kind != "EmptyDecl" or node.children:
                raise ModelError(f"Unsupported texture declaration: {node.kind}")
        if self.entry is None or self.uniform is None or not self.resources:
            raise ModelError("Texture Compute requires main, cbuffer and resources")
        self.globals = copy.deepcopy(self.symbols)
        # Validate every helper, including unused definitions, in an isolated SSA run.
        for function in self.functions.values():
            saved_bindings, saved_events = self.bindings, self.events
            self.bindings, self.events = [], []
            arguments = [operation("literal", p["type"], []) for p in function["parameters"]]
            for argument in arguments:
                argument.update(numerator=0, denominator=1)
                if argument["width"] > 1:
                    argument.update(kind="splat", arguments=[dict(argument, width=1)])
            self.invoke_helper(function, arguments)
            self.bindings, self.events = saved_bindings, saved_events
        self.guard = boolean(True)
        self.execute(self.entry, self.symbols, self.guard)

    def resource_declaration(self, node):
        names = quoted(node.text)
        allowed = {"Texture2D<float4>", "RWTexture2D<float4>", "StructuredBuffer<float4>", "RWStructuredBuffer<float4>"}
        if not names or names[0] not in allowed:
            raise ModelError("Compute texture resources require float4 elements")
        if len(node.children) != 1 or node.children[0].kind != "RegisterAssignment":
            raise ModelError("Compute resources require explicit registers")
        register = source_header(node.children[0].text).group("tail").strip()
        writable = names[0].startswith("RW")
        if not re.fullmatch(r"register\(" + ("u" if writable else "t") + r"[0-9]+\)", register):
            raise ModelError("Compute resource permission/register mismatch")
        name = declaration_name(node)
        if any(r["name"] == name or r["register"] == register for r in self.resources):
            raise ModelError("Duplicate Compute resource", "INVALID_INPUT")
        self.resource_ids[identifier(node)] = len(self.resources)
        self.resources.append({"name": name, "type": names[0], "register": register, "writable": writable,
                               "physical_kind": "texture2d" if "Texture2D" in names[0] else "buffer"})

    def uniform_declaration(self, node):
        metadata, fields = buffer_declaration(node, check_numeric=False)
        self.uniform = {"buffer": metadata, "fields": []}
        for field in fields:
            kind = self.types.node_type(field)
            if kind not in (1, "uint"):
                raise ModelError("Texture Compute uniforms are scalar uint or float")
            name = declaration_name(field)
            index = len(self.uniform["fields"])
            self.uniform["fields"].append({"name": name, "type": kind})
            self.symbols[identifier(field)] = make_symbol(name, kind, "Var", False,
                {"kind": "uniform", "width": kind, "index": index, "name": name})

    def entry_declaration(self, node):
        # Reuse entry validation, replacing only the supported 2D numthreads attr.
        attr = next((c for c in node.children if c.kind == "HLSLNumThreadsAttr"), None)
        match = None if attr is None else re.fullmatch(r" ([0-9]+) ([0-9]+) ([0-9]+)", source_header(attr.text).group("tail"))
        if match is None:
            raise ModelError("Missing numthreads")
        dimensions = list(map(int, match.groups()))
        if dimensions[2] != 1 or not all(1 <= d <= 1024 for d in dimensions) or dimensions[0] * dimensions[1] > 1024:
            raise ModelError("Compute texture requires numthreads(x,y,1), total ≤1024")
        original_text = attr.text
        attr.text = re.sub(r" [0-9]+ [0-9]+ [0-9]+$", " 1 1 1", attr.text)
        try:
            super().entry_declaration(node)
        finally:
            attr.text = original_text
        self.numthreads = dimensions

    def access(self, node, writing=False):
        if self.stack:
            raise ModelError("Pure Compute helpers cannot access resources")
        if node.kind == "CXXMemberCallExpr" and len(node.children) == 2:
            member, index = node.children
            if member.kind != "MemberExpr" or len(member.children) != 1 or not re.search(r" \.Load 0x[0-9a-fA-F]+$", member.text):
                raise ModelError("Only Load without offset is supported")
            owner = member.children[0]
        elif node.kind == "CXXOperatorCallExpr" and len(node.children) == 3:
            callee, owner, index = node.children
            if callee.kind != "ImplicitCastExpr" or len(callee.children) != 1 or "'operator[]'" not in callee.children[0].text:
                raise ModelError("Unknown resource subscript")
            if owner.kind == "ImplicitCastExpr" and owner.text.endswith("<NoOp>"):
                owner = owner.children[0]
        else:
            raise ModelError("Expected texture Load or resource subscript")
        tag, key, name = variable_reference(owner)
        if tag != "Var" or key not in self.resource_ids:
            raise ModelError("Resource reference is not global")
        ordinal = self.resource_ids[key]
        resource = self.resources[ordinal]
        if resource["name"] != name or resource["writable"] != writing:
            raise ModelError("Resource reference permission/identity mismatch")
        expected = ("uint2" if writing else "int3") if resource["physical_kind"] == "texture2d" else "uint"
        if resource["physical_kind"] == "buffer" and not writing and index.kind == "ImplicitCastExpr" and index.text.endswith("<IntegralCast>"):
            index = index.children[0]
        if self.types.node_type(index) != expected:
            raise ModelError(f"Compute resource index requires {expected}")
        return ordinal, index, not writing

    def expression(self, node, symbols):
        kind = self.types.node_type(node)
        if node.kind == "HLSLVectorElementExpr" and integer_type(self.types.node_type(node.children[0])):
            child = self.expression(node.children[0], symbols)
            indices = swizzle_indices(component_mask(node), lanes(child["width"]))
            if len(indices) != lanes(kind):
                raise ModelError("Integer swizzle width mismatch")
            return dict(operation("swizzle", kind, [child]), indices=indices)
        if node.kind == "IntegerLiteral" and (integer_type(kind) or kind == "literal_int"):
            value = uint_literal(node, self.source)
            return dict(value, width="int" if kind == "literal_int" else kind)
        if node.kind == "ImplicitCastExpr" and len(node.children) == 1:
            child_type = self.types.node_type(node.children[0])
            if node.text.endswith("<LValueToRValue>") and (integer_type(kind) or kind == "bool"):
                return self.expression(node.children[0], symbols)
            if node.text.endswith("<IntegralCast>") and integer_type(kind) and (integer_type(child_type) or child_type == "literal_int"):
                child = self.expression(node.children[0], symbols)
                if lanes(kind) != lanes(child["width"]):
                    raise ModelError("Integer cast changes vector width")
                return operation("integer_cast", kind, [child])
            if node.text.endswith("<HLSLVectorSplat>") and integer_type(kind):
                child = self.expression(node.children[0], symbols)
                if lanes(child["width"]) != 1 or scalar_type(child["width"]) != scalar_type(kind):
                    raise ModelError("Invalid integer splat")
                return operation("splat", kind, [child])
        if node.kind in ("ParenExpr", "CXXFunctionalCastExpr", "CStyleCastExpr") and len(node.children) == 1 and integer_type(kind):
            child = self.expression(node.children[0], symbols)
            if child["width"] != kind:
                raise ModelError("Unsupported integer constructor conversion")
            return child
        if node.kind == "InitListExpr" and integer_type(kind):
            args = [self.expression(child, symbols) for child in node.children]
            if (sum(lanes(arg["width"]) for arg in args) != lanes(kind)
                    or any(not integer_type(arg["width"]) for arg in args)):
                raise ModelError("Integer constructor shape mismatch")
            converted = []
            for arg in args:
                width = scalar_type(kind) + (str(lanes(arg["width"])) if lanes(arg["width"]) > 1 else "")
                converted.append(arg if arg["width"] == width else operation("integer_cast", width, [arg]))
            return operation("construct", kind, converted)
        if node.kind == "UnaryOperator" and (integer_type(kind) or kind == "literal_int") and quoted(node.text)[-1] == "-":
            width = "int" if kind == "literal_int" else kind
            return operation("integer_negate", width, [self.expression(node.children[0], symbols)])
        if node.kind == "BinaryOperator" and integer_type(kind):
            operator = quoted(node.text)[-1]
            allowed = {"+": "uint_add", "-": "uint_sub"}
            if scalar_type(kind) == "uint":
                allowed.update({"*": "uint_mul", "&": "uint_and", "|": "uint_or", "^": "uint_xor"})
            if operator not in allowed:
                raise ModelError("Unsupported texture integer operator")
            args = [self.expression(c, symbols) for c in node.children]
            if len(args) != 2 or any(a["width"] != kind for a in args):
                raise ModelError("Integer operand types mismatch")
            return operation(allowed[operator], kind, args)
        if node.kind == "BinaryOperator" and kind == "bool" and quoted(node.text)[-1] not in ("&&", "||"):
            args = [self.snapshot(self.expression(c, symbols), "compare") for c in node.children]
            if len(args) != 2 or args[0]["width"] != args[1]["width"] or args[0]["width"] not in (1, "uint", "int", "bool"):
                raise ModelError("Unsupported scalar comparison")
            return dict(operation("compare", "bool", args), operator=quoted(node.text)[-1])
        if node.kind == "ConditionalOperator" and len(node.children) == 3:
            condition = self.snapshot(self.expression(node.children[0], symbols), "select.condition")
            if condition["width"] != "bool":
                raise ModelError("Ternary condition must be bool")
            old_guard = self.guard
            self.guard = logical("and", old_guard, condition)
            yes = self.expression(node.children[1], symbols)
            self.guard = logical("and", old_guard, logical("not", condition))
            no = self.expression(node.children[2], symbols)
            self.guard = old_guard
            if yes["width"] != kind or no["width"] != kind:
                raise ModelError("Ternary branch types mismatch")
            return operation("choose", kind, [condition, yes, no])
        return super().expression(node, symbols)

    def snapshot(self, value, name):
        if value["kind"] == "divide":
            # Snapshot the denominator before recording the obligation, even if
            # the result is overwritten or the caller ignores its parameter.
            denominator = super().snapshot(value["arguments"][1], "divide.denominator")
            value = dict(value, arguments=[value["arguments"][0], denominator])
            self.events.append({"kind": "domain", "guard": self.guard, "denominator": denominator})
        return super().snapshot(value, name)

    def call(self, node, symbols):
        key, name, signature = callee_reference(node)
        if key not in self.functions and name not in COMPUTE_MATH:
            raise ModelError(f"Unsupported Compute intrinsic: {name}")
        if name == "divide":
            raise ModelError("divide is an IR operator, not an HLSL intrinsic")
        function, checked_name, size = self.checked_call(node)
        arguments = [self.snapshot(self.expression(c, symbols), "call.argument") for c in node.children[1:]]
        if function is not None:
            return self.invoke_helper(function, arguments)
        return operation(checked_name, size, arguments)

    def invoke_helper(self, function, arguments):
        self.invocations += 1
        if function["id"] in self.stack or len(self.stack) >= 32 or self.invocations > 512:
            raise ModelError("Recursive/excessive Compute helper calls")
        symbols = copy.deepcopy(self.globals)
        if len(arguments) != len(function["parameters"]):
            raise ModelError("Helper argument count mismatch")
        for parameter, argument in zip(function["parameters"], arguments):
            if parameter["type"] != argument["width"]:
                raise ModelError("Helper argument type mismatch")
            symbols[parameter["id"]] = make_symbol(parameter["name"], parameter["type"], "ParmVar", True, argument)
        old_guard = self.guard
        self.stack.append(function["id"])
        self.helper_returns.append([])
        alive = self.execute(function["body"], symbols, old_guard)
        returns = self.helper_returns.pop()
        self.stack.pop()
        self.guard = old_guard
        if not returns:
            raise ModelError("Pure helper requires terminal return")
        # Require an unconditional syntactic terminal return; earlier returns
        # remain represented by their captured guards.
        if not function["body"].children or function["body"].children[-1].kind != "ReturnStmt":
            raise ModelError("Pure helper requires terminal return")
        result = returns[-1][1]
        for guard, value in reversed(returns[:-1]):
            result = operation("choose", function["type"], [guard, value, result])
        return self.snapshot(result, function["name"] + ".return")

    def execute(self, body, symbols, guard, depth=0):
        if depth > 32:
            raise ModelError("Compute control nesting exceeded")
        nodes = body.children if body.kind == "CompoundStmt" else [body]
        local_keys = set(symbols)
        for node in nodes:
            self.guard = guard
            if node.kind == "ReturnStmt" and node.children:
                if not self.stack or len(node.children) != 1:
                    raise ModelError("Only helper returns may carry values")
                result = self.snapshot(self.expression(node.children[0], symbols), "return")
                if result["width"] != self.functions[self.stack[-1]]["type"]:
                    raise ModelError("Helper return type mismatch")
                self.helper_returns[-1].append((guard, result))
                guard = boolean(False)
            elif node.kind == "DeclStmt":
                for declaration in node.children:
                    if declaration.kind != "VarDecl" or len(declaration.children) > 1:
                        raise ModelError("Unsupported Compute local declaration")
                    kind = self.types.node_type(declaration)
                    if kind not in (1, 2, 3, 4, "bool", "uint", "uint2", "uint3", "int", "int2", "int3"):
                        raise ModelError("Unsupported Compute local type")
                    value = None if not declaration.children else self.snapshot(self.expression(declaration.children[0], symbols), declaration_name(declaration))
                    if value is not None and value["width"] != kind:
                        raise ModelError("Compute local initializer type mismatch")
                    symbols[identifier(declaration)] = make_symbol(declaration_name(declaration), kind, "Var", True, value)
            elif node.kind == "CompoundStmt":
                guard = self.execute(node, symbols, guard, depth + 1)
            else:
                # The legacy statement interpreter dynamically calls this
                # expression/access/execute implementation for nested branches.
                guard = super().execute(node, symbols, guard, depth)
        if body.kind == "CompoundStmt":
            for key in set(symbols) - local_keys:
                del symbols[key]
        self.guard = guard
        return guard

    def model(self):
        return {"schema": "compute-2", "resources": self.resources, "uniform": self.uniform,
                "parameter": self.parameter, "numthreads": self.numthreads,
                "bindings": self.bindings, "events": self.events}


def compute_contract(data, original, optimized):
    for field in ("resources", "uniform", "parameter", "numthreads"):
        if original[field] != optimized[field]:
            raise ModelError(f"Compute interfaces differ: {field}", "INVALID_INPUT")
    if not isinstance(data, dict) or set(data) != {"schema", "dispatch_groups", "uniform_ranges", "bindings"} or data["schema"] != 2:
        raise ModelError("Invalid texture Compute contract", "INVALID_INPUT")
    groups = data["dispatch_groups"]
    if not isinstance(groups, list) or len(groups) != 3 or groups[2] != 1 or any(type(x) is not int or x < 1 for x in groups):
        raise ModelError("Invalid 2D dispatch", "INVALID_INPUT")
    if any(g * n > 2**32 for g, n in zip(groups, original["numthreads"])):
        raise ModelError("Dispatch IDs exceed uint32", "INVALID_INPUT")
    fields = original["uniform"]["fields"]
    ranges = data["uniform_ranges"]
    if not isinstance(ranges, dict) or set(ranges) != {f["name"] for f in fields}:
        raise ModelError("Every uniform requires an explicit range", "INVALID_INPUT")
    for field in fields:
        limits = ranges[field["name"]]
        if not isinstance(limits, list) or len(limits) != 2 or any(type(x) not in (int, str) for x in limits):
            raise ModelError("Uniform bounds must be exact integers/decimal strings", "INVALID_INPUT")
        lower, upper = [exact_number(str(x)) for x in limits]
        if lower > upper or (field["type"] == "uint" and (any(type(x) is not int for x in limits) or not 0 <= lower <= upper < 2**32)):
            raise ModelError("Invalid typed uniform bounds", "INVALID_INPUT")
    bindings = data["bindings"]
    if not isinstance(bindings, dict) or set(bindings) != {r["name"] for r in original["resources"]}:
        raise ModelError("Every resource needs a physical binding", "INVALID_INPUT")
    identities = {}
    for resource in original["resources"]:
        binding = bindings[resource["name"]]
        texture = resource["physical_kind"] == "texture2d"
        required = {"identity", "dimensions"} if texture else {"identity", "capacity"}
        if not isinstance(binding, dict) or set(binding) != required or type(binding["identity"]) is not int or not 0 <= binding["identity"] <= 65535:
            raise ModelError("Invalid physical binding", "INVALID_INPUT")
        shape = binding["dimensions"] if texture else [binding["capacity"]]
        if not isinstance(shape, list) or len(shape) != (2 if texture else 1) or any(type(x) is not int or not (1 if texture else 0) <= x <= 2**31 for x in shape):
            raise ModelError("Invalid resource dimensions", "INVALID_INPUT")
        if texture and shape[0] * shape[1] > 2**32:
            raise ModelError("Texture address extent exceeds profile", "INVALID_INPUT")
        physical = (resource["physical_kind"], tuple(shape))
        identity = binding["identity"]
        if identity in identities and identities[identity] != physical:
            raise ModelError("Aliased views require the same physical kind and shape", "INVALID_INPUT")
        identities[identity] = physical
    return data


def address_terms(event, resource, binding):
    expression = event["address"]
    if resource["physical_kind"] == "buffer":
        address = f"({lean_expression(expression)}).toNat"
        return address, f"{address} < {binding['capacity']}", binding["capacity"]
    width, height = binding["dimensions"]
    signed_index = scalar_type(expression["width"]) == "int"
    coordinates = [f"({lean_expression(expression, i)}).{'toInt' if signed_index else 'toNat'}" for i in range(2)]
    x, y = coordinates
    bounds = f"0 ≤ {x} ∧ {x} < {width} ∧ 0 ≤ {y} ∧ {y} < {height}"
    address = f"({y}.toNat * {width} + {x}.toNat)" if signed_index else f"({y} * {width} + {x})"
    return address, bounds, width * height


def definition(name, model, contract):
    lines = [f"noncomputable def {name} (initial : Memory) (uniforms : Uniforms) (thread : Nat) : Execution := by",
             "  classical", "  exact Id.run do", "    let m0 : Memory := initial"]
    memory = 0
    accesses, domains, store_bounds = [], [], []
    for event in model["events"]:
        kind = event["kind"]
        if kind == "binding":
            index = event["index"]
            binding = model["bindings"][index]
            lines.append(f"    let v{index} : {lean_type(binding['width'])} := {lean_expression(binding['expression'])}")
            continue
        guard = lean_expression(event["guard"])
        if kind == "domain":
            denominator = event["denominator"]
            for component in range(lanes(denominator["width"])):
                domains.append(f"({guard} → {lean_expression(denominator, component)} ≠ 0)")
            continue
        resource = model["resources"][event["resource"]]
        binding = contract["bindings"][resource["name"]]
        identity = binding["identity"]
        address, bounds, capacity = address_terms(event, resource, binding)
        if resource["physical_kind"] == "texture2d" and kind == "load":
            # Only mip0 is modelled; it must be statically zero in the imported IR.
            mip = event["address"]
            if not mip_is_zero(mip, model["bindings"]):
                raise ModelError("Texture Load requires constant mip0")
        lines.append(f"    let b{len(accesses)} : Prop := {bounds}")
        bound_name = f"b{len(accesses)}"
        enabled = f"({guard} ∧ {bound_name})"
        accesses.append(f"⟨{identity}, {address}, {capacity}, {enabled}, {'true' if kind == 'store' else 'false'}⟩")
        if kind == "load":
            lines.append(f"    let l{event['index']} : Color := if {bound_name} then m{memory} {identity} {address} else (fun _ => 0)")
        else:
            store_bounds.append(f"({guard} → {bound_name})")
            lines.append(f"    let m{memory + 1} := store m{memory} {enabled} {identity} {address} {lean_expression(event['value'])}")
            memory += 1
    math = " ∧ ".join(domains) or "True"
    bounds = " ∧ ".join(store_bounds) or "True"
    lines.append(f"    return ⟨⟨m{memory}, [{', '.join(accesses)}]⟩, {math}, {bounds}⟩")
    return "\n".join(lines)


def mip_is_zero(expr, bindings):
    # Resolve SSA aliases and constructors rather than matching shader text.
    if expr["kind"] == "local":
        return mip_is_zero(bindings[expr["index"]]["expression"], bindings)
    if expr["kind"] == "integer_cast":
        return mip_is_zero(expr["arguments"][0], bindings)
    if expr["kind"] == "construct":
        flattened = []
        for arg in expr["arguments"]:
            flattened.extend((arg, i) for i in range(lanes(arg["width"])))
        value, lane = flattened[2]
        return scalar_zero(value, lane, bindings)
    return False


def scalar_zero(expr, component, bindings):
    if expr["kind"] == "local":
        return scalar_zero(bindings[expr["index"]]["expression"], component, bindings)
    if expr["kind"] in ("integer_cast", "splat"):
        return scalar_zero(expr["arguments"][0], component, bindings)
    return expr["kind"] == "uint_literal" and expr["value"] == 0


def generate_compute(original, optimized, contract):
    compute_contract(contract, original, optimized)
    extent = [g * n for g, n in zip(contract["dispatch_groups"], original["numthreads"])]
    lines = ["import ShaderFormalize.ComputeTexture", "import Mathlib.Tactic.Ring", "",
             "namespace ShaderFormalize.GeneratedCompute", "open ShaderFormalize ShaderFormalize.Compute ShaderFormalize.ComputeTexture", "",
             "structure Uniforms where"]
    conditions = []
    for index, field in enumerate(original["uniform"]["fields"]):
        lines.append(f"  u{index} : {lean_type(field['type'])}")
        lower, upper = [exact_number(str(x)) for x in contract["uniform_ranges"][field["name"]]]
        value = f"uniforms.u{index}" + (".toNat" if field["type"] == "uint" else "")
        lo = str(int(lower)) if field["type"] == "uint" else lean_number(lower)
        hi = str(int(upper)) if field["type"] == "uint" else lean_number(upper)
        conditions.extend([f"{lo} ≤ {value}", f"{value} ≤ {hi}"])
    lines.extend([f"def extentX : Nat := {extent[0]}", f"def threads : Nat := {extent[0] * extent[1]}", "",
                  "def inputsValid (uniforms : Uniforms) : Prop := " + " ∧ ".join(conditions), "",
                  definition("original", original, contract), "", definition("optimized", optimized, contract), "",
                  "def expected : Prop := ∀ (initial : Memory) (uniforms : Uniforms), inputsValid uniforms →",
                  "  allValid threads (original initial uniforms) ∧ allValid threads (optimized initial uniforms) ∧",
                  "  finish threads initial (fun t => (original initial uniforms t).result) =",
                  "    finish threads initial (fun t => (optimized initial uniforms t).result)",
                  "end ShaderFormalize.GeneratedCompute", ""])
    return "\n".join(lines)


def evaluate_compute(model, contract, initial, uniforms):
    for field in model["uniform"]["fields"]:
        lower, upper = [exact_number(str(x)) for x in contract["uniform_ranges"][field["name"]]]
        if not lower <= uniforms[field["name"]] <= upper:
            raise ValueError("Uniform outside contract")
    extent_x = model["numthreads"][0] * contract["dispatch_groups"][0]
    threads = extent_x * model["numthreads"][1] * contract["dispatch_groups"][1]
    accesses, final_writes = [], []
    zero = (Fraction(0),) * 4
    for thread in range(threads):
        values, loads = {}, {}
        memory = dict(initial)
        for event in model["events"]:
            kind = event["kind"]
            if kind == "binding":
                index = event["index"]
                values[index] = evaluate_expression(model["bindings"][index]["expression"], values, loads, uniforms, thread, extent_x)
                continue
            enabled = evaluate_expression(event["guard"], values, loads, uniforms, thread, extent_x)
            if kind == "domain":
                denominator = evaluate_expression(event["denominator"], values, loads, uniforms, thread, extent_x)
                components = denominator if isinstance(denominator, tuple) else (denominator,)
                if enabled and any(value == 0 for value in components):
                    raise ValueError("Executed division outside real domain")
                continue
            resource = model["resources"][event["resource"]]
            binding = contract["bindings"][resource["name"]]
            index = evaluate_expression(event["address"], values, loads, uniforms, thread, extent_x)
            if resource["physical_kind"] == "texture2d":
                if kind == "load" and not mip_is_zero(event["address"], model["bindings"]):
                    raise ModelError("Texture Load requires constant mip0")
                x, y = index[:2]
                if scalar_type(event["address"]["width"]) == "int":
                    x, y = signed(x), signed(y)
                width, height = binding["dimensions"]
                inbounds = 0 <= x < width and 0 <= y < height
                address = y * width + x
            else:
                address = index
                inbounds = 0 <= address < binding["capacity"]
            key = binding["identity"], address
            if kind == "store" and enabled and not inbounds:
                raise ValueError("Out of bounds two-dimensional Store")
            if enabled and inbounds:
                accesses.append((thread, key, kind == "store"))
            if kind == "load":
                loads[event["index"]] = memory.get(key, zero) if inbounds else zero
            elif enabled and inbounds:
                value = evaluate_expression(event["value"], values, loads, uniforms, thread, extent_x)
                memory[key] = value
                final_writes.append((thread, key, value))
    for thread, key, writing in accesses:
        for other, other_key, other_writing in accesses:
            if thread != other and key == other_key and (writing or other_writing):
                raise ValueError("Conflicting physical accesses across threads")
    result = dict(initial)
    for _, key, value in final_writes:
        result[key] = value
    return result

"""Experimental typed-AST Compute subset with ordered per-thread memory effects.

DXC owns HLSL parsing/types. This adapter reuses its existing AST reader and
numeric expression interpreter, and adds entry, buffer access and memory events.
"""
import copy
from fractions import Fraction
import re

from shader_ast import ModelError, literal, parse_tree, quoted, source_header, validate_source
from shader_frontend import Program, make_symbol, swizzle_indices
from shader_packing import PackingTypes, uint_literal
from shader_types import component_mask, declaration_name, identifier, initialized, operation, semantic, value_type
from shader_lean import lean_number


def boolean(value):
    return {"kind": "boolean", "width": "bool", "value": value}


def logical(kind, *arguments):
    if kind == "not" and arguments[0]["kind"] == "boolean":
        return boolean(not arguments[0]["value"])
    if kind in ("and", "or"):
        left, right = arguments
        if left["kind"] == "boolean":
            return right if left["value"] == (kind == "and") else left
        if right["kind"] == "boolean":
            return left if right["value"] == (kind == "and") else right
    return operation(kind, "bool", list(arguments))


class ComputeTypes(PackingTypes):
    def node_type(self, node):
        names = quoted(node.text)
        if names and names[0].removeprefix("const ") in ("uint3", "vector<unsigned int, 3>"):
            return "uint3"
        return super().node_type(node)


def variable_reference(node):
    if node.kind != "DeclRefExpr" or node.children:
        raise ModelError("Expected an identified variable reference")
    match = re.search(r"\b(ParmVar|Var) (0x[0-9a-fA-F]+) '([A-Za-z_][A-Za-z0-9_]*)'", node.text)
    if match is None:
        raise ModelError("Unrecognized variable reference")
    return match.groups()


class ComputeProgram(Program):
    """Guarded SSA values and ordered load/store events for one thread."""

    def __init__(self, source, dump):
        validate_source(source)
        self.source = source
        self.types = ComputeTypes([], allow_bool=True)
        self.resources = []
        self.resource_ids = {}
        self.uniform = None
        self.entry = None
        self.bindings = []
        self.events = []
        self.functions = {}
        self.guard = boolean(True)
        self.symbols = {}
        root = parse_tree(dump)
        for node in root.children:
            if node.kind == "VarDecl":
                self.resource_declaration(node)
            elif node.kind == "HLSLBufferDecl" and self.uniform is None:
                self.uniform_declaration(node)
            elif node.kind == "FunctionDecl" and self.entry is None:
                self.entry_declaration(node)
            elif node.kind == "EmptyDecl" and not node.children:
                continue
            else:
                raise ModelError(f"Unsupported Compute declaration: {node.kind}")
        if self.entry is None or self.uniform is None or not self.resources:
            raise ModelError("Compute requires one main, one uint cbuffer field and buffers")
        self.execute(self.entry, self.symbols, boolean(True))

    def resource_declaration(self, node):
        names = quoted(node.text)
        if not names or names[0] not in ("StructuredBuffer<float4>", "RWStructuredBuffer<float4>"):
            raise ModelError("Compute currently accepts StructuredBuffer/RWStructuredBuffer<float4>")
        if len(node.children) != 1 or node.children[0].kind != "RegisterAssignment":
            raise ModelError("Compute buffers require explicit registers and no initializer")
        register = source_header(node.children[0].text).group("tail").strip()
        writable = names[0].startswith("RW")
        if not re.fullmatch(r"register\(" + ("u" if writable else "t") + r"[0-9]+\)", register):
            raise ModelError("Compute buffer register/type mismatch")
        name = declaration_name(node)
        if name in [item["name"] for item in self.resources] or register in [item["register"] for item in self.resources]:
            raise ModelError("Repeated Compute resource name/register", "INVALID_INPUT")
        ordinal = len(self.resources)
        self.resource_ids[identifier(node)] = ordinal
        self.resources.append({"name": name, "type": names[0], "register": register, "writable": writable})

    def uniform_declaration(self, node):
        if len(node.children) != 2 or node.children[0].kind != "RegisterAssignment":
            raise ModelError("Compute supports one uint cbuffer field")
        register = source_header(node.children[0].text).group("tail").strip()
        field = node.children[1]
        if register != "register(b0)" or field.kind != "VarDecl" or field.children or self.types.node_type(field) != "uint":
            raise ModelError("Compute supports one uint cbuffer field in b0")
        name = declaration_name(field)
        self.uniform = {"name": name, "type": "uint", "buffer": source_header(node.text).group("tail").strip()}
        self.symbols[identifier(field)] = make_symbol(name, "uint", "Var", False, {"kind": "count", "width": "uint"})

    def entry_declaration(self, node):
        if declaration_name(node) != "main" or quoted(node.text)[:1] != ["void (uint3)"]:
            raise ModelError("Compute requires void main(uint3)")
        parameter, body, dimensions, stage = None, None, None, False
        for child in node.children:
            if child.kind == "ParmVarDecl" and parameter is None:
                if (self.types.node_type(child) != "uint3" or len(child.children) != 1
                        or semantic(child.children[0]) != "SV_DISPATCHTHREADID"):
                    raise ModelError("Compute main requires uint3 SV_DispatchThreadID")
                parameter = child
            elif child.kind == "CompoundStmt" and body is None:
                body = child
            elif child.kind == "HLSLNumThreadsAttr" and dimensions is None:
                match = re.fullmatch(r" ([0-9]+) ([0-9]+) ([0-9]+)", source_header(child.text).group("tail"))
                if match is None or match.group(2, 3) != ("1", "1") or not 1 <= int(match.group(1)) <= 1024:
                    raise ModelError("Compute prototype requires numthreads(x,1,1)")
                dimensions = int(match.group(1))
            elif child.kind == "HLSLShaderAttr" and child.text.endswith('Implicit "compute"') and not stage:
                stage = True
            else:
                raise ModelError(f"Unsupported Compute entry child: {child.kind}")
        if parameter is None or body is None or dimensions is None or not stage:
            raise ModelError("Incomplete Compute main entry")
        self.entry = body
        self.numthreads = dimensions
        self.parameter = {"name": declaration_name(parameter), "semantic": "SV_DISPATCHTHREADID", "type": "uint3"}
        self.symbols[identifier(parameter)] = make_symbol(self.parameter["name"], "uint3", "ParmVar", False,
                                                        {"kind": "dispatch_id", "width": "uint3"})

    def snapshot(self, value, name):
        initialized(value)
        if len(self.bindings) >= 2048:
            raise ModelError("Compute binding limit exceeded")
        index = len(self.bindings)
        self.bindings.append({"name": name, "width": value["width"], "expression": value})
        self.events.append({"kind": "binding", "index": index})
        return {"kind": "local", "width": value["width"], "index": index}

    def access(self, node, writing=False):
        signed = False
        if node.kind == "CXXMemberCallExpr" and len(node.children) == 2:
            member, index_node = node.children
            if member.kind != "MemberExpr" or len(member.children) != 1 or not re.search(r" \.Load 0x[0-9a-fA-F]+$", member.text):
                raise ModelError("Only buffer.Load(index) is supported")
            owner = member.children[0]
            # DXC selects Load(int); valid nonnegative indices have identical bits.
            if (index_node.kind != "ImplicitCastExpr" or not index_node.text.endswith("<IntegralCast>")
                    or quoted(index_node.text)[:1] != ["int"] or len(index_node.children) != 1):
                raise ModelError("Compute Load requires the DXC uint-to-int index conversion")
            index_node = index_node.children[0]
            signed = True
        elif node.kind == "CXXOperatorCallExpr" and len(node.children) == 3:
            callee, owner, index_node = node.children
            if (callee.kind != "ImplicitCastExpr" or not callee.text.endswith("<FunctionToPointerDecay>")
                    or len(callee.children) != 1 or callee.children[0].kind != "DeclRefExpr"
                    or "'operator[]'" not in callee.children[0].text):
                raise ModelError("Unknown Compute resource index operator")
            if owner.kind == "ImplicitCastExpr" and owner.text.endswith("<NoOp>") and len(owner.children) == 1:
                owner = owner.children[0]
        else:
            raise ModelError("Expected a typed buffer access")
        tag, key, name = variable_reference(owner)
        if tag != "Var" or key not in self.resource_ids:
            raise ModelError("Buffer access must reference a global resource")
        resource = self.resource_ids[key]
        metadata = self.resources[resource]
        if name != metadata["name"]:
            raise ModelError("Resource declaration identity mismatch")
        if writing != metadata["writable"]:
            raise ModelError("Loads require StructuredBuffer; stores require RWStructuredBuffer")
        if self.types.node_type(index_node) != "uint":
            raise ModelError("Compute buffer indices must be uint32")
        return resource, index_node, signed

    def call(self, node, symbols):
        raise ModelError("Compute helper/intrinsic calls are not supported by this first memory slice")

    def expression(self, node, symbols):
        kind = self.types.node_type(node)
        if node.kind in ("CXXMemberCallExpr", "CXXOperatorCallExpr"):
            resource, index_node, signed = self.access(node)
            address = self.snapshot(self.expression(index_node, symbols), "load.address")
            index = len(self.events)
            self.events.append({"kind": "load", "resource": resource, "address": address,
                                "guard": self.guard, "signed_index": signed, "index": index})
            return {"kind": "load", "width": 4, "index": index}
        if node.kind == "HLSLVectorElementExpr" and self.types.node_type(node.children[0]) == "uint3":
            mask = component_mask(node)
            child = self.expression(node.children[0], symbols)
            if child["kind"] != "dispatch_id" or mask not in ("x", "y", "z"):
                raise ModelError("Compute dispatch vector accepts scalar x/y/z reads")
            return {"kind": "thread", "width": "uint"} if mask == "x" else {"kind": "uint_literal", "width": "uint", "value": 0}
        if node.kind == "IntegerLiteral" and kind in ("uint", "literal_int"):
            return uint_literal(node, self.source)
        if node.kind == "CXXBoolLiteralExpr" and not node.children:
            return boolean(node.text.endswith(" true"))
        if node.kind == "ImplicitCastExpr" and len(node.children) == 1:
            child_type = self.types.node_type(node.children[0])
            if node.text.endswith("<IntegralCast>") and kind == "uint" and child_type == "literal_int":
                return self.expression(node.children[0], symbols)
            if node.text.endswith("<LValueToRValue>") and kind in ("uint", "bool", "uint3"):
                return self.expression(node.children[0], symbols)
        if node.kind in ("ParenExpr", "CStyleCastExpr", "CXXFunctionalCastExpr") and kind in ("uint", "bool"):
            if len(node.children) == 1 and self.types.node_type(node.children[0]) == kind:
                return self.expression(node.children[0], symbols)
        if node.kind == "BinaryOperator" and kind == "uint":
            operator = quoted(node.text)[-1]
            names = {"+": "uint_add", "-": "uint_sub", "*": "uint_mul", "&": "uint_and", "|": "uint_or", "^": "uint_xor"}
            if operator not in names or len(node.children) != 2:
                raise ModelError("Unsupported Compute uint operator")
            args = [self.expression(child, symbols) for child in node.children]
            if any(value_type(arg) != "uint" for arg in args):
                raise ModelError("Compute uint operands differ")
            return operation(names[operator], "uint", args)
        if node.kind == "BinaryOperator" and kind == "bool":
            operator = quoted(node.text)[-1]
            left = self.snapshot(self.expression(node.children[0], symbols), "condition.left")
            old_guard = self.guard
            if operator in ("&&", "||"):
                self.guard = logical("and", old_guard, left if operator == "&&" else logical("not", left))
            try:
                right = self.expression(node.children[1], symbols)
            finally:
                self.guard = old_guard
            if operator in ("&&", "||") and left["width"] == right["width"] == "bool":
                return logical("and" if operator == "&&" else "or", left, right)
            if operator not in ("<", "<=", ">", ">=", "==", "!=") or left["width"] != right["width"] or left["width"] not in ("uint", 1, "bool"):
                raise ModelError("Unsupported Compute comparison")
            return dict(operation("compare", "bool", [left, right]), operator=operator)
        if node.kind == "UnaryOperator" and kind == "bool" and quoted(node.text)[-1] == "!":
            return logical("not", self.expression(node.children[0], symbols))
        return super().expression(node, symbols)

    def execute(self, body, symbols, guard, depth=0):
        if depth > 32:
            raise ModelError("Compute control nesting exceeded")
        nodes = body.children if body.kind == "CompoundStmt" else [body]
        local_keys = set(symbols)
        for node in nodes:
            self.guard = guard
            if node.kind == "DeclStmt":
                for declaration in node.children:
                    if declaration.kind != "VarDecl" or len(declaration.children) > 1:
                        raise ModelError("Unsupported Compute local declaration")
                    kind = self.types.node_type(declaration)
                    if kind not in (1, 2, 3, 4, "uint", "bool"):
                        raise ModelError("Unsupported Compute local type")
                    value = None
                    if declaration.children:
                        value = self.snapshot(self.expression(declaration.children[0], symbols), declaration_name(declaration))
                        if value_type(value) != kind:
                            raise ModelError("Compute initializer type differs")
                    symbols[identifier(declaration)] = make_symbol(declaration_name(declaration), kind, "Var", True, value)
            elif node.kind == "BinaryOperator" and quoted(node.text)[-1] == "=" and len(node.children) == 2:
                target, rhs = node.children
                if target.kind == "CXXOperatorCallExpr":
                    resource, address_node, signed = self.access(target, writing=True)
                    address = self.snapshot(self.expression(address_node, symbols), "store.address")
                    value = self.snapshot(self.expression(rhs, symbols), "store.value")
                    if value["width"] != 4:
                        raise ModelError("Compute Store requires float4")
                    self.events.append({"kind": "store", "resource": resource, "address": address,
                                        "value": value, "guard": guard, "signed_index": signed})
                else:
                    symbol, path, kind = self.lvalue(target, symbols)
                    if path or not symbol["writable"]:
                        raise ModelError("Only local whole-value assignment is supported")
                    value = self.snapshot(self.expression(rhs, symbols), symbol["name"])
                    if value_type(value) != kind:
                        raise ModelError("Compute assignment type differs")
                    symbol["value"] = value
            elif node.kind == "IfStmt":
                if len(node.children) != 4 or node.children[0].kind != "Null":
                    raise ModelError("Unsupported Compute if AST")
                _, condition_node, yes_node, no_node = node.children
                condition = self.snapshot(self.expression(condition_node, symbols), "if.condition")
                if condition["width"] != "bool":
                    raise ModelError("Compute if requires scalar bool")
                yes_symbols = copy.deepcopy(symbols)
                no_symbols = copy.deepcopy(symbols)
                yes_alive = self.execute(yes_node, yes_symbols, logical("and", guard, condition), depth + 1)
                no_alive = logical("and", guard, logical("not", condition))
                if no_node.kind != "Null":
                    no_alive = self.execute(no_node, no_symbols, no_alive, depth + 1)
                for key, symbol in symbols.items():
                    yes = yes_symbols[key]["value"]
                    no = no_symbols[key]["value"]
                    if yes == no:
                        symbol["value"] = yes
                    elif yes is None or no is None:
                        symbol["value"] = None
                    else:
                        symbol["value"] = self.snapshot(operation("choose", symbol["type"], [condition, yes, no]), symbol["name"])
                # Keep the execution condition in SSA too: sequential branches
                # otherwise duplicate their complete preceding mask tree.
                guard = self.snapshot(logical("or", yes_alive, no_alive), "if.alive")
            elif node.kind == "CompoundStmt":
                guard = self.execute(node, symbols, guard, depth + 1)
            elif node.kind == "ReturnStmt" and not node.children:
                guard = boolean(False)
            elif node.kind == "NullStmt" and not node.children:
                continue
            else:
                raise ModelError(f"Unsupported Compute statement: {node.kind}")
        if body.kind == "CompoundStmt":
            for key in set(symbols) - local_keys:
                del symbols[key]
        return guard

    def model(self):
        return {"schema": "compute-1", "resources": self.resources, "uniform": self.uniform,
                "parameter": self.parameter, "numthreads": self.numthreads,
                "bindings": self.bindings, "events": self.events}


def import_compute(source, dump, schema=1):
    if schema == 2:
        from shader_compute_texture import TextureProgram
        return TextureProgram(source, dump).model()
    return ComputeProgram(source, dump).model()


def compute_contract(data, original, optimized):
    if original["schema"] == "compute-2":
        from shader_compute_texture import compute_contract as texture_contract
        return texture_contract(data, original, optimized)
    for field in ("resources", "uniform", "parameter", "numthreads"):
        if original[field] != optimized[field]:
            raise ModelError(f"Compute interfaces differ: {field}", "INVALID_INPUT")
    if (not isinstance(data, dict) or set(data) != {"schema", "dispatch_groups", "count_range", "bindings"}
            or type(data["schema"]) is not int or data["schema"] != 1):
        raise ModelError("Invalid Compute contract fields", "INVALID_INPUT")
    groups = data["dispatch_groups"]
    if type(groups) is not int or not 1 <= groups <= (2**32 // original["numthreads"]):
        raise ModelError("Compute dispatch exceeds uint32 IDs", "INVALID_INPUT")
    limits = data["count_range"]
    if (not isinstance(limits, list) or len(limits) != 2 or any(type(x) is not int for x in limits)
            or not 0 <= limits[0] <= limits[1] < 2**32):
        raise ModelError("Invalid Count uint32 range", "INVALID_INPUT")
    bindings = data["bindings"]
    if not isinstance(bindings, dict) or set(bindings) != {r["name"] for r in original["resources"]}:
        raise ModelError("Compute contract must bind every resource explicitly", "INVALID_INPUT")
    capacities = {}
    for resource in original["resources"]:
        item = bindings[resource["name"]]
        if not isinstance(item, dict) or set(item) != {"identity", "capacity"}:
            raise ModelError("Invalid Compute resource binding", "INVALID_INPUT")
        identity, capacity = item["identity"], item["capacity"]
        if type(identity) is not int or not 0 <= identity <= 65535 or type(capacity) is not int or not 0 <= capacity <= 2**31:
            raise ModelError("Invalid resource identity/capacity", "INVALID_INPUT")
        if identity in capacities and capacities[identity] != capacity:
            raise ModelError("Aliased bindings must have the same physical capacity", "INVALID_INPUT")
        capacities[identity] = capacity
    return data


def lean_expression(expr, component=None):
    kind, width = expr["kind"], expr["width"]
    if width not in ("uint", "bool") and component is None:
        if width == 1:
            component = 0
        else:
            return "(fun c => " + lean_expression(expr, "c") + ")"
    if kind == "local":
        result = f"v{expr['index']}"
        return result if width in (1, "uint", "bool") else f"({result} {component})"
    if kind == "load":
        return f"(l{expr['index']} {component})"
    if kind == "thread":
        return "(BitVec.ofNat 32 thread)"
    if kind == "count":
        return "count"
    if kind == "uint_literal":
        return f"(BitVec.ofNat 32 {expr['value']})"
    if kind == "literal":
        return lean_number(Fraction(expr["numerator"], expr["denominator"]))
    if kind == "boolean":
        return "True" if expr["value"] else "False"
    args = expr.get("arguments", [])
    if kind in ("and", "or", "not"):
        values = [lean_expression(arg) for arg in args]
        if kind == "not":
            return f"(¬ {values[0]})"
        return f"({values[0]} {'∧' if kind == 'and' else '∨'} {values[1]})"
    if kind == "compare":
        values = []
        for arg in args:
            value = lean_expression(arg)
            values.append(f"({value}).toNat" if arg["width"] == "uint" else value)
        op = {"<": "<", "<=": "≤", ">": ">", ">=": "≥", "==": "=", "!=": "≠"}[expr["operator"]]
        return f"({values[0]} {op} {values[1]})"
    if kind == "choose":
        return f"(if {lean_expression(args[0])} then {lean_expression(args[1], component)} else {lean_expression(args[2], component)})"
    if kind == "splat":
        return lean_expression(args[0], 0)
    if kind == "swizzle":
        if width == 1:
            return lean_expression(args[0], expr["indices"][0])
        if isinstance(component, int):
            return lean_expression(args[0], expr["indices"][component])
        values = [lean_expression(args[0], index) for index in expr["indices"]]
        return "(![" + ", ".join(values) + f"] {component})"
    if kind == "construct":
        values = []
        for arg in args:
            for index in range(arg["width"]):
                values.append(lean_expression(arg, index))
        if isinstance(component, int):
            return values[component]
        return "![" + ", ".join(values) + f"] {component}"
    if kind in ("add", "subtract", "multiply", "uint_add", "uint_sub", "uint_mul", "uint_and", "uint_or", "uint_xor"):
        op = {"add": "+", "subtract": "-", "multiply": "*", "uint_add": "+", "uint_sub": "-", "uint_mul": "*", "uint_and": "&&&", "uint_or": "|||", "uint_xor": "^^^"}[kind]
        return f"({lean_expression(args[0], component)} {op} {lean_expression(args[1], component)})"
    if kind == "negate":
        return f"(-{lean_expression(args[0], component)})"
    raise ModelError(f"Unsupported Compute IR expression: {kind}")


def compute_definition(name, model, contract):
    lines = [f"noncomputable def {name} (initial : Memory) (count : BitVec 32) (thread : Nat) : ThreadResult := by",
             "  classical", "  exact Id.run do", "    let m0 : Memory := initial"]
    memory = 0
    accesses = []
    for event in model["events"]:
        kind = event["kind"]
        if kind == "binding":
            index = event["index"]
            binding = model["bindings"][index]
            width = binding["width"]
            lean_type = "BitVec 32" if width == "uint" else "Prop" if width == "bool" else "ℝ" if width == 1 else f"Model.Vec {width}"
            lines.append(f"    let v{index} : {lean_type} := {lean_expression(binding['expression'])}")
            continue
        binding = contract["bindings"][model["resources"][event["resource"]]["name"]]
        identity, capacity = binding["identity"], binding["capacity"]
        address = f"({lean_expression(event['address'])}).toNat"
        guard = lean_expression(event["guard"])
        accesses.append(f"⟨{identity}, {address}, {capacity}, {guard}, {'true' if kind == 'store' else 'false'}⟩")
        if kind == "load":
            lines.append(f"    let l{event['index']} : Color := m{memory} {identity} {address}")
        else:
            value = lean_expression(event["value"])
            lines.append(f"    let m{memory + 1} := store m{memory} {guard} {identity} {address} {value}")
            memory += 1
    lines.append(f"    return ⟨m{memory}, [{', '.join(accesses)}]⟩")
    return "\n".join(lines)


def generate_compute(original, optimized, contract):
    if original["schema"] == "compute-2":
        from shader_compute_texture import generate_compute as texture_generate
        return texture_generate(original, optimized, contract)
    contract = compute_contract(contract, original, optimized)
    threads = original["numthreads"] * contract["dispatch_groups"]
    lower, upper = contract["count_range"]
    return "\n".join([
        "import ShaderFormalize.Compute", "import Mathlib.Tactic.Ring", "",
        "namespace ShaderFormalize.GeneratedCompute", "open ShaderFormalize ShaderFormalize.Compute", "",
        compute_definition("original", original, contract), "",
        compute_definition("optimized", optimized, contract), "",
        f"def threads : Nat := {threads}",
        f"def inputsValid (count : BitVec 32) : Prop := {lower} ≤ count.toNat ∧ count.toNat ≤ {upper}", "",
        "def expected : Prop := ∀ (initial : Memory) (count : BitVec 32), inputsValid count →",
        "  safe threads (original initial count) ∧ safe threads (optimized initial count) ∧",
        "  finish threads initial (original initial count) = finish threads initial (optimized initial count)",
        "end ShaderFormalize.GeneratedCompute", "",
    ])


def evaluate_expression(expr, values, loads, count, thread):
    """Finite regression evaluator; it is not used to discharge Lean goals."""
    kind = expr["kind"]
    if kind == "local":
        return values[expr["index"]]
    if kind == "load":
        return loads[expr["index"]]
    if kind == "thread":
        return thread % 2**32
    if kind == "count":
        return count
    if kind == "uint_literal":
        return expr["value"]
    if kind == "literal":
        return Fraction(expr["numerator"], expr["denominator"])
    if kind == "boolean":
        return expr["value"]
    args = [evaluate_expression(arg, values, loads, count, thread) for arg in expr.get("arguments", [])]
    if kind == "not":
        return not args[0]
    if kind in ("and", "or"):
        return (args[0] and args[1]) if kind == "and" else (args[0] or args[1])
    if kind == "compare":
        left, right = args
        operator = expr["operator"]
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        if operator == ">=":
            return left >= right
        return (left == right) if operator == "==" else (left != right)
    if kind == "choose":
        return args[1] if args[0] else args[2]
    if kind == "splat":
        return tuple(args[0] for _ in range(expr["width"]))
    if kind == "swizzle":
        result = tuple(args[0][index] for index in expr["indices"])
        return result[0] if expr["width"] == 1 else result
    if kind == "construct":
        result = []
        for value in args:
            result.extend(value if isinstance(value, tuple) else [value])
        return tuple(result)
    if kind.startswith("uint_"):
        left, right = args
        if kind == "uint_add":
            result = left + right
        elif kind == "uint_sub":
            result = left - right
        elif kind == "uint_mul":
            result = left * right
        elif kind == "uint_and":
            result = left & right
        elif kind == "uint_or":
            result = left | right
        else:
            result = left ^ right
        return result % 2**32
    if kind == "negate":
        return tuple(-value for value in args[0]) if isinstance(args[0], tuple) else -args[0]
    if kind in ("add", "subtract", "multiply"):
        if expr["width"] == 1:
            left, right = args
            return left + right if kind == "add" else left - right if kind == "subtract" else left * right
        result = []
        for left, right in zip(args[0], args[1]):
            result.append(left + right if kind == "add" else left - right if kind == "subtract" else left * right)
        return tuple(result)
    raise ModelError(f"Unknown finite Compute operation: {kind}")


def evaluate_compute(model, contract, initial, count):
    if model["schema"] == "compute-2":
        from shader_compute_texture import evaluate_compute as texture_evaluate
        return texture_evaluate(model, contract, initial, count)
    if not contract["count_range"][0] <= count <= contract["count_range"][1]:
        raise ValueError("Count outside the supplied contract")
    accesses = []
    final_writes = []
    zero = (Fraction(0),) * 4
    threads = model["numthreads"] * contract["dispatch_groups"]
    for thread in range(threads):
        memory = dict(initial)
        values, loads = {}, {}
        for event in model["events"]:
            kind = event["kind"]
            if kind == "binding":
                index = event["index"]
                values[index] = evaluate_expression(model["bindings"][index]["expression"], values, loads, count, thread)
                continue
            resource = contract["bindings"][model["resources"][event["resource"]]["name"]]
            address = evaluate_expression(event["address"], values, loads, count, thread)
            enabled = evaluate_expression(event["guard"], values, loads, count, thread)
            key = resource["identity"], address
            if enabled:
                if not 0 <= address < resource["capacity"]:
                    raise ValueError("Out of bounds Compute access")
                accesses.append((thread, key, kind == "store"))
            if kind == "load":
                loads[event["index"]] = memory.get(key, zero)
            elif enabled:
                value = evaluate_expression(event["value"], values, loads, count, thread)
                memory[key] = value
                final_writes.append((thread, key, value))
    for thread, key, writing in accesses:
        for other_thread, other_key, other_writing in accesses:
            if thread != other_thread and key == other_key and (writing or other_writing):
                raise ValueError("Conflicting accesses across Compute threads")
    result = dict(initial)
    for _, key, value in final_writes:
        result[key] = value
    return result

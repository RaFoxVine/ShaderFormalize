"""Scalar uint single-pass buffers on the shared guarded IEEE interpreter."""
import re
from shader_ast import ModelError, quoted, source_header
from shader_frontend import buffer_declaration, function_declaration, make_symbol
from shader_ieee_frontend import IeeeSemantics, IeeeTypeRegistry
from shader_flow import GuardedProgram
from shader_types import declaration_name, identifier, semantic, component_mask, value_type
from shader_control_values import logical


class UintComputeTypes(IeeeTypeRegistry):
    def __init__(self, declarations, allow_bool=False):
        if declarations:
            raise ModelError("Structs are outside uint Compute")
        super().__init__(declarations, allow_bool)

    def is_value_type(self, kind):
        return kind in ("uint", "bool")

    def node_type(self, node):
        kind = super().node_type(node)
        if kind not in ("uint", "bool", "uint3", "void"):
            raise ModelError("Only scalar uint/bool and dispatch uint3 are supported")
        return kind


class BufferResources:
    def __init__(self, nodes):
        self.layout, self.ids = [], {}
        for node in nodes:
            names = quoted(node.text)
            if not names or names[0] not in ("StructuredBuffer<uint>", "RWStructuredBuffer<uint>"):
                raise ModelError("uint Compute requires uint StructuredBuffer resources")
            writable = names[0].startswith("RW")
            if len(node.children) != 1 or node.children[0].kind != "RegisterAssignment" or node.children[0].children:
                raise ModelError("Buffers require explicit registers and no initializer")
            register = source_header(node.children[0].text).group("tail").strip()
            if not re.fullmatch(r"register\(" + ("u" if writable else "t") + r"[0-9]+\)", register):
                raise ModelError("Buffer register/type mismatch")
            name = declaration_name(node)
            if any(r["name"] == name or r["register"] == register for r in self.layout):
                raise ModelError("Repeated resource name/register", "INVALID_INPUT")
            self.ids[identifier(node)] = len(self.layout)
            self.layout.append(dict(name=name, type=names[0], register=register, writable=writable))
        if not self.layout:
            raise ModelError("uint Compute requires buffers")


class UintComputeProgram(IeeeSemantics, GuardedProgram):
    branching = True
    type_registry = UintComputeTypes

    def make_resources(self, nodes):
        return BufferResources(nodes)

    def read_buffer(self, node):
        return buffer_declaration(node, check_numeric=False)

    def read_function(self, node):
        if declaration_name(node) != "main":
            if any(re.search(r"\b(?:out|inout)\b", child.text) for child in node.children if child.kind == "ParmVarDecl"):
                raise ModelError("Helpers require ordinary by-value parameters")
            result = function_declaration(node, self.types)
            if result["type"] not in ("uint", "bool"):
                raise ModelError("Helpers require scalar uint/bool results")
            return result
        if quoted(node.text)[:1] != ["void (uint3)"]:
            raise ModelError("Expected void main(uint3)")
        params, body, dims, stage = [], None, None, False
        for child in node.children:
            if child.kind == "ParmVarDecl":
                if (self.types.node_type(child) != "uint3" or len(child.children) != 1
                        or semantic(child.children[0]) != "SV_DISPATCHTHREADID"):
                    raise ModelError("main requires uint3 SV_DispatchThreadID")
                params.append(self.types.parameter_metadata(child))
            elif child.kind == "CompoundStmt" and body is None:
                body = child
            elif child.kind == "HLSLNumThreadsAttr" and dims is None:
                match = re.fullmatch(r" ([0-9]+) 1 1", source_header(child.text).group("tail"))
                if not match or not 1 <= int(match[1]) <= 1024:
                    raise ModelError("Expected numthreads(n,1,1), n=1..1024")
                dims = int(match[1])
            elif child.kind == "HLSLShaderAttr" and child.text.endswith('Implicit "compute"') and not stage:
                stage = True
            else:
                raise ModelError("Unsupported Compute entry attribute")
        if len(params) != 1 or body is None or dims is None or not stage:
            raise ModelError("Incomplete Compute entry")
        self.numthreads = dims
        return dict(id=identifier(node), name="main", type="void", parameters=params,
                    body=body, output=None, signature="void (uint3)")

    def validate_extra_definitions(self):
        if self.buffer is None or len(self.fields) != 1 or self.types.node_type(self.fields[0]) != "uint":
            raise ModelError("Expected one uint Count field in b0")
        # Helpers may read Count, but resource access belongs to main only.
        for fn in self.functions.values():
            if fn is self.main:
                continue
            pending = [fn["body"]]
            while pending:
                node = pending.pop()
                if node.kind == "DeclRefExpr" and any(re.search(r"\bVar " + re.escape(key) + r" ", node.text) for key in self.resources.ids):
                    raise ModelError("Buffer access is main-only")
                pending.extend(node.children)

    def resource_access(self, node, writing=False):
        if node.kind != "CXXOperatorCallExpr" or len(node.children) != 3:
            raise ModelError("Expected buffer[index]")
        callee, owner, index = node.children
        if (callee.kind != "ImplicitCastExpr" or not callee.text.endswith("<FunctionToPointerDecay>")
                or len(callee.children) != 1 or callee.children[0].kind != "DeclRefExpr"
                or callee.children[0].children or "'operator[]'" not in callee.children[0].text):
            raise ModelError("Unknown buffer subscript operator")
        if owner.kind == "ImplicitCastExpr" and owner.text.endswith("<NoOp>") and len(owner.children) == 1:
            owner = owner.children[0]
        match = re.search(r"\bVar (0x[0-9a-fA-F]+) '([A-Za-z_][A-Za-z0-9_]*)'", owner.text)
        if owner.kind != "DeclRefExpr" or owner.children or not match or match[1] not in self.resources.ids:
            raise ModelError("Buffer owner must be a declared resource")
        ordinal = self.resources.ids[match[1]]
        resource = self.resources.layout[ordinal]
        if resource["name"] != match[2] or (writing and not resource["writable"]):
            raise ModelError("Resource identity/write permission mismatch")
        if self.types.node_type(index) != "uint" or self.types.node_type(node) != "uint":
            raise ModelError("Buffer index/value must be uint")
        return ordinal, index

    def dispatch_component(self, node):
        if node.kind != "HLSLVectorElementExpr" or len(node.children) != 1:
            return None
        owner = node.children[0]
        if self.types.node_type(owner) != "uint3":
            return None
        while owner.kind in ("ImplicitCastExpr", "ParenExpr") and len(owner.children) == 1:
            if owner.kind == "ImplicitCastExpr" and not owner.text.endswith("<LValueToRValue>"):
                raise ModelError("Unsupported dispatch conversion")
            owner = owner.children[0]
        param = self.main["parameters"][0]
        if owner.kind != "DeclRefExpr" or not re.search(r"\bParmVar " + re.escape(param["id"]) + " '" + re.escape(param["name"]) + "'", owner.text):
            raise ModelError("Dispatch parameter identity mismatch")
        mask = component_mask(node)
        if mask not in ("x", "y", "z") or self.types.node_type(node) != "uint":
            raise ModelError("Dispatch supports single x/y/z only")
        return mask

    def validate_ieee_expression(self, node):
        if node.kind == "CXXOperatorCallExpr":
            _, index = self.resource_access(node)
            self.validate_ieee_expression(index)
            return
        if self.dispatch_component(node) is not None:
            return
        if self.types.node_type(node) not in ("uint", "bool"):
            raise ModelError("Ordinary expressions must be scalar uint/bool")
        return super().validate_ieee_expression(node)

    def checked_call(self, node):
        result = super().checked_call(node)
        if result[0] is None:
            raise ModelError("Only defined pure helpers are supported")
        return result

    def address_type(self, node):
        if node.kind == "CXXOperatorCallExpr":
            _, index = self.resource_access(node, writing=True)
            self.validate_ieee_expression(index)
            return "uint"
        return None

    def validate_statement(self, node, result_type, effects_allowed):
        if node.kind in ("BinaryOperator", "CompoundAssignOperator") and node.children and node.children[0].kind == "CXXOperatorCallExpr":
            if node.kind != "BinaryOperator" or quoted(node.text)[-1] != "=":
                raise ModelError("Resource writes require plain assignment")
            self.address_type(node.children[0])
            self.validate_ieee_expression(node.children[1])
            if self.types.node_type(node.children[1]) != "uint":
                raise ModelError("Store value must be uint")
            return False
        return super().validate_statement(node, result_type, effects_allowed)

    def execute_statement(self, node, state):
        if node.kind == "BinaryOperator" and node.children[0].kind == "CXXOperatorCallExpr":
            ordinal, index = self.resource_access(node.children[0], writing=True)
            address = self.snapshot(self.expression(index, state.symbols), "store.address")
            value = self.snapshot(self.expression(node.children[1], state.symbols), "store.value")
            self.events.append(dict(kind="store", resource=ordinal, address=address, value=value, guard=self.guard()))
            return True
        return super().execute_statement(node, state)

    def expression(self, node, symbols):
        if node.kind == "CXXOperatorCallExpr":
            ordinal, index = self.resource_access(node)
            address = self.snapshot(self.expression(index, symbols), "load.address")
            ref = len(self.events)
            self.events.append(dict(kind="load", resource=ordinal, address=address, guard=self.guard(), index=ref))
            return dict(kind="load", width="uint", index=ref)
        mask = self.dispatch_component(node)
        if mask is not None:
            return dict(kind="thread", width="uint") if mask == "x" else dict(kind="uint_literal", width="uint", value=0)
        return super().expression(node, symbols)

    def binary_operands(self, node, symbols):
        op = quoted(node.text)[-1]
        if op not in ("&&", "||"):
            return super().binary_operands(node, symbols)
        left = self.snapshot(self.expression(node.children[0], symbols), "short.left")
        saved = self.current_guard
        self.current_guard = logical("and", saved, left if op == "&&" else logical("not", left))
        try:
            right = self.expression(node.children[1], symbols)
        finally:
            self.current_guard = saved
        return [left, right]

    def conditional_operands(self, node, symbols):
        condition = self.snapshot(self.expression(node.children[0], symbols), "select.condition")
        saved = self.current_guard
        try:
            self.current_guard = logical("and", saved, condition)
            yes = self.expression(node.children[1], symbols)
            self.current_guard = logical("and", saved, logical("not", condition))
            no = self.expression(node.children[2], symbols)
        finally:
            self.current_guard = saved
        return [condition, yes, no]

    def model(self):
        field = self.fields[0]
        uniform = dict(name=declaration_name(field), type="uint", buffer=self.buffer["name"])
        self.globals[identifier(field)] = make_symbol(uniform["name"], "uint", "Var", False, dict(kind="count", width="uint"))
        self.validate_helper_initialization()
        self.invoke(self.main, [dict(kind="dispatch_id", width="uint3")])
        return dict(schema="compute-uint-1", resources=self.resources.layout, uniform=uniform,
                    parameter=self.main["parameters"][0]["name"], numthreads=self.numthreads,
                    bindings=self.bindings, events=self.events)


def import_uint_compute(source, dump):
    return UintComputeProgram(source, dump).model()


def uint_contract(data, original, optimized):
    def fail(message):
        return ModelError(message, "INVALID_INPUT")

    if any(model.get("schema") != "compute-uint-1" for model in (original, optimized)):
        raise fail("Expected compute-uint-1 models")
    if not isinstance(data, dict) or set(data) != {"schema", "dispatch_groups", "count_range", "bindings"} or type(data["schema"]) is not int or data["schema"] != 3:
        raise fail("uint32-buffer requires strict schema 3")
    for key in ("resources", "uniform", "parameter", "numthreads"):
        if original[key] != optimized[key]:
            raise fail("Compute interfaces differ: " + key)
    groups, limits = data["dispatch_groups"], data["count_range"]
    if type(groups) is not int or not 1 <= groups <= 65535:
        raise fail("Invalid dispatch groups")
    if not isinstance(limits, list) or len(limits) != 2 or any(type(n) is not int for n in limits) or not 0 <= limits[0] <= limits[1] <= min(groups * original["numthreads"], 2**32-1):
        raise fail("Invalid covered uint count range")
    bindings = data["bindings"]
    if not isinstance(bindings, dict) or set(bindings) != {r["name"] for r in original["resources"]}:
        raise fail("Bind every resource exactly once")
    capacities = {}
    for item in bindings.values():
        if not isinstance(item, dict) or set(item) != {"identity", "capacity"}:
            raise fail("Invalid resource binding fields")
        identity, capacity = item["identity"], item["capacity"]
        if type(identity) is not int or not 0 <= identity <= 65535 or type(capacity) is not int or not 0 <= capacity <= 2**32:
            raise fail("Invalid resource identity/capacity")
        if identity in capacities and capacities[identity] != capacity:
            raise fail("Aliased bindings require the same physical capacity")
        capacities[identity] = capacity
    return data

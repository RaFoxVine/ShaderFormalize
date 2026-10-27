"""Restricted two-lane HLSL to VerCors PVL access-safety translation."""
import re

from shader_ast import ModelError, parse_tree, quoted, source_header, validate_source
from shader_compute import variable_reference
from shader_packing import PackingTypes, uint_literal
from shader_types import component_mask, declaration_name, identifier, semantic


UINT_MODULUS = 2**32


class SyncTypes(PackingTypes):
    def node_type(self, node):
        names = quoted(node.text)
        if names and names[0].removeprefix("const ") in ("uint3", "vector<unsigned int, 3>"):
            return "uint3"
        return super().node_type(node)


class SyncProgram:
    def __init__(self, source, dump):
        validate_source(source)
        self.source = source
        self.types = SyncTypes([], allow_bool=False)
        self.resources = []
        self.resource_ids = {}
        self.shared = None
        self.parameter = None
        self.entry = None
        self.symbols = {}
        self.events = []
        root = parse_tree(dump)
        for node in root.children:
            if node.kind == "VarDecl":
                self.global_declaration(node)
            elif node.kind == "FunctionDecl":
                if self.entry is not None or declaration_name(node) != "main":
                    raise ModelError("Synchronization subset accepts only one main function")
                self.entry_declaration(node)
            elif node.kind != "EmptyDecl" or node.children:
                raise ModelError(f"Unsupported synchronization declaration: {node.kind}")
        inputs = sum(not resource["writable"] for resource in self.resources)
        outputs = sum(resource["writable"] for resource in self.resources)
        if self.shared is None or self.entry is None or inputs != 1 or outputs != 1:
            raise ModelError("Synchronization requires shared[2], one input buffer, one output buffer and main")
        self.execute(self.entry)

    def global_declaration(self, node):
        names = quoted(node.text)
        if not names:
            raise ModelError("Missing synchronization global type")
        if names[0] == "float4 __attribute__((address_space(3)))[2]":
            if self.shared is not None or len(node.children) != 1 or node.children[0].kind != "HLSLGroupSharedAttr":
                raise ModelError("Synchronization requires one groupshared float4[2]")
            self.shared = declaration_name(node)
            self.resource_ids[identifier(node)] = "shared"
            return
        if names[0] not in ("StructuredBuffer<float4>", "RWStructuredBuffer<float4>"):
            raise ModelError("Only groupshared float4[2] and float4 StructuredBuffers are supported")
        if len(node.children) != 1 or node.children[0].kind != "RegisterAssignment":
            raise ModelError("Synchronization buffers require explicit registers")
        register = source_header(node.children[0].text).group("tail").strip()
        writable = names[0].startswith("RW")
        expected = "u" if writable else "t"
        if not re.fullmatch(r"register\(" + expected + r"[0-9]+\)", register):
            raise ModelError("Synchronization buffer register/type mismatch")
        name = declaration_name(node)
        if name in [item["name"] for item in self.resources] or register in [item["register"] for item in self.resources]:
            raise ModelError("Duplicate synchronization resource", "INVALID_INPUT")
        self.resource_ids[identifier(node)] = len(self.resources)
        self.resources.append({"name": name, "type": names[0], "register": register, "writable": writable})

    def entry_declaration(self, node):
        if declaration_name(node) != "main" or quoted(node.text)[:1] != ["void (uint3)"]:
            raise ModelError("Synchronization requires void main(uint3)")
        parameter = None
        dimensions = None
        stage = False
        for child in node.children:
            if child.kind == "ParmVarDecl" and parameter is None:
                if (self.types.node_type(child) != "uint3" or len(child.children) != 1
                        or semantic(child.children[0]) != "SV_GROUPTHREADID"):
                    raise ModelError("Synchronization main requires uint3 SV_GroupThreadID")
                parameter = child
            elif child.kind == "CompoundStmt" and self.entry is None:
                self.entry = child
            elif child.kind == "HLSLNumThreadsAttr" and dimensions is None:
                dimensions = source_header(child.text).group("tail").strip()
            elif child.kind == "HLSLShaderAttr" and child.text.endswith('Implicit "compute"') and not stage:
                stage = True
            else:
                raise ModelError(f"Unsupported synchronization entry child: {child.kind}")
        if parameter is None or self.entry is None or dimensions != "2 1 1" or not stage:
            raise ModelError("Synchronization requires numthreads(2,1,1) and one group-thread parameter")
        name = declaration_name(parameter)
        self.parameter = {"name": name, "semantic": "SV_GroupThreadID", "type": "uint3"}
        self.symbols[identifier(parameter)] = {"name": name, "kind": "thread_vector"}

    def unwrap(self, node):
        if (node.kind == "ImplicitCastExpr" and len(node.children) == 1
                and (node.text.endswith("<LValueToRValue>") or node.text.endswith("<NoOp>"))):
            return self.unwrap(node.children[0])
        if node.kind in ("ParenExpr", "CStyleCastExpr", "CXXFunctionalCastExpr") and len(node.children) == 1:
            return self.unwrap(node.children[0])
        return node

    def expression(self, node):
        node = self.unwrap(node)
        kind = self.types.node_type(node)
        if node.kind == "IntegerLiteral" and kind in ("uint", "literal_int"):
            return uint_literal(node, self.source)
        if node.kind == "HLSLVectorElementExpr" and component_mask(node) == "x":
            tag, key, name = variable_reference(node.children[0])
            if tag == "ParmVar" and key in self.symbols and self.symbols[key]["kind"] == "thread_vector":
                return {"kind": "thread", "width": "uint"}
            raise ModelError("Only SV_GroupThreadID.x can drive synchronization addresses")
        if node.kind == "DeclRefExpr" and kind == "uint":
            tag, key, name = variable_reference(node)
            if tag != "Var" or key not in self.symbols or self.symbols[key]["kind"] != "uint":
                raise ModelError("Unknown synchronization uint local")
            return {"kind": "local", "width": "uint", "name": self.symbols[key]["name"]}
        if node.kind == "BinaryOperator" and kind == "uint" and quoted(node.text)[-1] in ("+", "-"):
            operator = quoted(node.text)[-1]
            return {"kind": "uint_add" if operator == "+" else "uint_sub", "width": "uint",
                    "arguments": [self.expression(child) for child in node.children]}
        raise ModelError(f"Unsupported synchronization address expression: {node.kind}")

    def access(self, node, writing):
        if node.kind == "ArraySubscriptExpr" and len(node.children) == 2:
            owner, index_node = node.children
            owner = self.unwrap(owner)
            tag, key, name = variable_reference(owner)
            if tag != "Var" or self.resource_ids.get(key) != "shared" or name != self.shared:
                raise ModelError("Unknown groupshared access")
            resource = "shared"
        elif node.kind == "CXXOperatorCallExpr" and len(node.children) == 3:
            callee, owner, index_node = node.children
            if (callee.kind != "ImplicitCastExpr" or len(callee.children) != 1
                    or "'operator[]'" not in callee.children[0].text):
                raise ModelError("Unknown synchronization buffer subscript")
            owner = self.unwrap(owner)
            tag, key, name = variable_reference(owner)
            resource = self.resource_ids.get(key)
            if tag != "Var" or not isinstance(resource, int):
                raise ModelError("Synchronization buffer access must be global")
            metadata = self.resources[resource]
            if name != metadata["name"] or writing != metadata["writable"]:
                raise ModelError("Synchronization buffer access permission/type mismatch")
            resource = metadata["name"]
        else:
            raise ModelError("Expected shared or StructuredBuffer subscript")
        if self.types.node_type(index_node) not in ("uint", "literal_int"):
            raise ModelError("Synchronization addresses must be uint32 or integer constants")
        return resource, self.expression(index_node)

    def append_event(self, kind, resource, address, node, value=None):
        event = {"kind": kind, "resource": resource, "address": address, "source_line": node.line}
        if value is not None:
            event["value_event"] = value
        self.events.append(event)
        return len(self.events) - 1

    def assignment(self, node):
        target, rhs = node.children
        resource, address = self.access(target, writing=True)
        value_resource, value_address = self.access(self.unwrap(rhs), writing=False)
        load = self.append_event("load", value_resource, value_address, rhs)
        self.append_event("store", resource, address, node, load)

    def barrier(self, node):
        if len(node.children) != 1:
            raise ModelError("Unsupported synchronization intrinsic")
        callee = node.children[0]
        if callee.kind != "ImplicitCastExpr" or len(callee.children) != 1:
            raise ModelError("Unsupported synchronization barrier callee")
        target = callee.children[0]
        match = re.search(r"\bFunction (0x[0-9a-fA-F]+) '([A-Za-z_][A-Za-z0-9_]*)' 'void \(\)'$",
                          source_header(target.text).group("tail"))
        if target.kind != "DeclRefExpr" or match is None or match.group(2) != "GroupMemoryBarrierWithGroupSync":
            raise ModelError("Only GroupMemoryBarrierWithGroupSync is supported")
        self.events.append({"kind": "barrier", "source_line": node.line})

    def execute(self, body):
        barriers = 0
        for node in body.children:
            if node.kind == "DeclStmt":
                for declaration in node.children:
                    if (declaration.kind != "VarDecl" or len(declaration.children) != 1
                            or self.types.node_type(declaration) != "uint"):
                        raise ModelError("Only initialized uint locals are supported")
                    name = declaration_name(declaration)
                    self.symbols[identifier(declaration)] = {"name": name, "kind": "uint", "value": self.expression(declaration.children[0])}
            elif node.kind == "BinaryOperator" and quoted(node.text)[-1] == "=":
                self.assignment(node)
            elif node.kind == "CallExpr":
                self.barrier(node)
                barriers += 1
                if barriers > 1:
                    raise ModelError("Synchronization subset permits at most one barrier")
            elif node.kind != "NullStmt" or node.children:
                raise ModelError(f"Unsupported synchronization statement: {node.kind}")

    def model(self):
        locals_by_name = {symbol["name"]: symbol["value"] for symbol in self.symbols.values() if symbol["kind"] == "uint"}
        return {"schema": "sync-hlsl-1", "shared": self.shared, "resources": self.resources,
                "parameter": self.parameter, "numthreads": [2, 1, 1], "locals": locals_by_name,
                "events": self.events}


def import_sync(source, dump):
    return SyncProgram(source, dump).model()


def sync_contract(data, model):
    if not isinstance(data, dict) or set(data) != {"schema", "bindings"} or type(data["schema"]) is not int or data["schema"] != 1:
        raise ModelError("Invalid synchronization contract", "INVALID_INPUT")
    names = {resource["name"] for resource in model["resources"]}
    bindings = data["bindings"]
    if not isinstance(bindings, dict) or set(bindings) != names:
        raise ModelError("Synchronization contract must bind both buffers", "INVALID_INPUT")
    identities = []
    for resource in model["resources"]:
        item = bindings[resource["name"]]
        if (not isinstance(item, dict) or set(item) != {"identity", "capacity"}
                or type(item["identity"]) is not int or not 0 <= item["identity"] <= 65535
                or type(item["capacity"]) is not int or item["capacity"] != 2):
            raise ModelError("Synchronization identities must be uint16 and capacities exactly two", "INVALID_INPUT")
        identities.append(item["identity"])
    if len(set(identities)) != len(identities):
        raise ModelError("Aliased input/output physical identities are outside this synchronization subset")
    return data


def pvl_expression(expression, locals_by_name):
    kind = expression["kind"]
    if kind == "uint_literal":
        return str(expression["value"])
    if kind == "thread":
        return "tid"
    if kind == "local":
        return pvl_expression(locals_by_name[expression["name"]], locals_by_name)
    arguments = [pvl_expression(item, locals_by_name) for item in expression["arguments"]]
    modulus = str(UINT_MODULUS)
    if kind == "uint_add":
        return f"(({arguments[0]} % {modulus}) + ({arguments[1]} % {modulus})) % {modulus}"
    if kind == "uint_sub":
        return f"(((0 + {modulus}) + ({arguments[0]} % {modulus}) - ({arguments[1]} % {modulus})) % {modulus})"
    raise ModelError(f"Unknown PVL address expression: {kind}")


def generate_pvl(model):
    local_values = model["locals"]
    input_name = next(resource["name"] for resource in model["resources"] if not resource["writable"])
    output_name = next(resource["name"] for resource in model["resources"] if resource["writable"])
    resource_names = {"shared": "shared", input_name: "input", output_name: "output"}
    pvl_input = resource_names[input_name]
    pvl_output = resource_names[output_name]
    final_shared = "1-tid" if any(event["kind"] == "barrier" for event in model["events"]) else "tid"
    lines = [
        "class HLSLSynchronization {",
        f"  context_everywhere {pvl_input} != null && {pvl_output} != null && shared != null;",
        f"  context_everywhere {pvl_input}.length == 2 && {pvl_output}.length == 2 && shared.length == 2;",
        f"  context (\\forall* int i; 0 <= i && i < 2; Perm({pvl_input}[i], read));",
        f"  context (\\forall* int i; 0 <= i && i < 2; Perm({pvl_output}[i], write));",
        "  context (\\forall* int i; 0 <= i && i < 2; Perm(shared[i], write));",
        f"  void execute(int[] {pvl_input}, int[] {pvl_output}, int[] shared) {{",
        "    par lanes (int tid = 0..2)",
        "      requires Perm(shared[tid], write);",
        f"      ensures Perm(shared[{final_shared}], write);",
        f"      context Perm({pvl_input}[tid], read);",
        f"      context Perm({pvl_output}[tid], write);",
        "    {",
    ]
    for event in model["events"]:
        if event["kind"] == "load":
            continue
        if event["kind"] == "barrier":
            lines.extend([
                "      barrier(lanes)",
                "        context 0 <= tid && tid < 2;",
                "        requires Perm(shared[tid], write);",
                "        ensures Perm(shared[1-tid], write);",
                "      {",
                "      }",
            ])
            continue
        load = model["events"][event["value_event"]]
        target = resource_names[event["resource"]]
        value = resource_names[load["resource"]]
        target_address = pvl_expression(event["address"], local_values)
        value_address = pvl_expression(load["address"], local_values)
        lines.append(f"      {target}[{target_address}] = {value}[{value_address}];")
    lines.extend(["    }", "  }", "}", ""])
    return "\n".join(lines)

"""Declaration identities and value types from the pinned, typed DXC AST."""
import re

from shader_ast import ModelError, quoted, source_header, width


def identifier(node):
    match = re.match(r" (0x[0-9a-fA-F]+) ", node.text)
    if match is None:
        raise ModelError("Missing declaration identity")
    return match.group(1)


def declaration_name(node):
    head = source_header(node.text).group("tail").split("'")[0].strip()
    match = re.fullmatch(r"(?:(?:used|referenced) )*([A-Za-z_][A-Za-z0-9_]*)", head)
    if match is None:
        raise ModelError("Unsupported declaration flags")
    return match.group(1)


def semantic(node):
    match = re.search(r'"([A-Za-z_][A-Za-z0-9_]*)"$', node.text)
    if node.kind != "SemanticDecl" or node.children or match is None:
        raise ModelError("Unsupported semantic")
    return match.group(1).upper()


def reference(kind, size, index):
    return {"kind": kind, "width": size, "index": index}


def operation(kind, size, arguments):
    return {"kind": kind, "width": size, "arguments": arguments}


def numeric_type(size):
    if size == "uint":
        return "uint"
    return "float" if size == 1 else f"float{size}"


def component_mask(node):
    # DXC prints lvalue selectors as "vectorcomponent xy", rvalues as "'type' xy".
    match = re.search(r"(?:\bvectorcomponent |' )([xyzwrgba]+)$", node.text)
    if node.kind != "HLSLVectorElementExpr" or match is None:
        raise ModelError("Unsupported vector component expression")
    return match.group(1)


def value_type(value):
    return value["type"] if value["kind"] == "record" else value["width"]


def initialized(value):
    if value is None:
        raise ModelError("Read before initialization")
    if value["kind"] == "record":
        for field in value["fields"].values():
            initialized(field)
    if value["kind"] == "partial_vector":
        raise ModelError("Read before all selected vector components are initialized")
    return value


def read_path(value, path):
    for name in path:
        value = value["fields"][name]
    return value


def replace_path(value, path, replacement):
    if not path:
        return replacement
    # Values are persistent: copying a struct or a by-value argument never aliases writes.
    fields = dict(value["fields"])
    fields[path[0]] = replace_path(fields[path[0]], path[1:], replacement)
    return dict(value, fields=fields)


class TypeRegistry:
    extra_leaves = ()

    def is_value_type(self, kind):
        return (isinstance(kind, int) or kind in self.records or kind in self.extra_leaves
                or (self.allow_bool and kind == "bool"))

    def parameter_metadata(self, node):
        if len(node.children) > 1:
            raise ModelError("Only default by-value parameters; no out/inout/default arguments")
        return {"id": identifier(node), "name": declaration_name(node), "type": self.node_type(node),
                "semantic": semantic(node.children[0]) if node.children else None}

    def __init__(self, declarations, allow_bool=False):
        self.allow_bool = allow_bool
        self.records = {}
        for node in declarations:
            match = re.fullmatch(r"(?:referenced )?struct ([A-Za-z_][A-Za-z0-9_]*) definition", source_header(node.text).group("tail").strip())
            if node.kind != "CXXRecordDecl" or match is None:
                raise ModelError("Only named plain struct definitions are supported")
            name = match.group(1)
            if name in self.records or len(self.records) >= 64:
                raise ModelError("Repeated or excessive struct declarations")
            self.records[name] = {"node": node, "fields": []}
        for name, record in list(self.records.items()):
            for child in record["node"].children:
                tail = source_header(child.text).group("tail").strip()
                if child.kind == "CXXRecordDecl" and not child.children and tail == f"implicit struct {name}":
                    continue
                if child.kind == "CXXDestructorDecl" and not child.children and re.fullmatch(
                    r"implicit(?: referenced)? ~" + re.escape(name) + r" 'void \(\) noexcept' inline", tail
                ):
                    continue
                if child.kind != "FieldDecl" or len(child.children) > 1:
                    raise ModelError("Struct methods, initializers and unknown members are unsupported")
                field_name = declaration_name(child)
                if self.node_type(child) in ("void", "Texture2D", "SamplerState") or (self.node_type(child) == "bool" and not allow_bool):
                    raise ModelError("Struct fields must be numeric or plain records")
                if any(field["name"] == field_name for field in record["fields"]):
                    raise ModelError("Repeated struct field")
                record["fields"].append({"name": field_name, "id": identifier(child), "type": self.node_type(child),
                                          "semantic": semantic(child.children[0]) if child.children else None})
            if not record["fields"] or len(record["fields"]) > 64:
                raise ModelError("Empty or excessive struct fields")
        self.shapes = {}
        for name in self.records:
            self.check_shape(name, [])

    def node_type(self, node):
        types = quoted(node.text)
        if not types:
            raise ModelError("Missing value type")
        name = types[0].removeprefix("const ")
        if name in ("void", "bool", "SamplerState"):
            return name
        if name in ("Texture2D", "Texture2D<float4>"):
            return "Texture2D"
        if name in self.records:
            return name
        return width(node)

    def named_type(self, name):
        if name == "bool" and self.allow_bool:
            return "bool"
        if name == "void":
            return "void"
        if name in self.records:
            return name
        match = re.fullmatch(r"float([234])?", name)
        if match is None:
            raise ModelError(f"Unsupported function result: {name}")
        return int(match.group(1) or 1)

    def check_shape(self, kind, ancestors):
        if isinstance(kind, int) or kind == "bool" or kind in self.extra_leaves:
            return 0, 1
        if kind in self.shapes:
            return self.shapes[kind]
        if kind in ancestors or len(ancestors) >= 16:
            raise ModelError("Recursive or excessively nested structs")
        depth, leaves = 1, 0
        for field in self.records[kind]["fields"]:
            child_depth, child_leaves = self.check_shape(field["type"], ancestors + [kind])
            depth = max(depth, 1 + child_depth)
            leaves += child_leaves
            if leaves > 4096:
                raise ModelError("Struct value exceeds 4096 numeric leaves")
        if depth > 16:
            raise ModelError("Excessively nested structs")
        # Named struct graphs may share children: compute each shape once, before expanding values.
        self.shapes[kind] = depth, leaves
        return depth, leaves

    def empty(self, kind):
        if isinstance(kind, int) or kind == "bool" or kind in self.extra_leaves:
            return None
        fields = {}
        for field in self.records[kind]["fields"]:
            fields[field["name"]] = self.empty(field["type"])
        return {"kind": "record", "type": kind, "fields": fields}

    def member(self, node, owner_type):
        match = re.search(r" lvalue \.([A-Za-z_][A-Za-z0-9_]*) (0x[0-9a-fA-F]+)$", node.text)
        if owner_type not in self.records or match is None:
            raise ModelError("Unsupported struct member access")
        for field in self.records[owner_type]["fields"]:
            if field["id"] == match.group(2) and field["name"] == match.group(1) and field["type"] == self.node_type(node):
                return field
        raise ModelError("Struct field owner/type/identity mismatch")

    def layout(self, kind):
        if kind in self.extra_leaves:
            raise ModelError("Integer stage inputs are not supported yet")
        if kind == "bool":
            raise ModelError("Boolean stage inputs are unsupported; use numeric inputs and scalar conditions")
        if isinstance(kind, int):
            return {"type": numeric_type(kind)}
        fields = []
        for field in self.records[kind]["fields"]:
            fields.append(dict(self.layout(field["type"]), name=field["name"], semantic=field["semantic"]))
        return {"type": kind, "fields": fields}

    def input_value(self, kind, path, field_semantic, interface):
        if isinstance(kind, int):
            if field_semantic is None or len(interface) >= 64:
                raise ModelError("Each entry leaf needs a semantic; at most 64 input leaves")
            index = len(interface)
            interface.append({"index": index, "name": path, "width": kind, "semantic": field_semantic, "storage": "parameter"})
            return reference("parameter", kind, index)
        if field_semantic is not None:
            raise ModelError("Semantics belong on struct leaf fields")
        fields = {}
        for field in self.records[kind]["fields"]:
            fields[field["name"]] = self.input_value(field["type"], path + "." + field["name"], field["semantic"], interface)
        return {"kind": "record", "type": kind, "fields": fields}

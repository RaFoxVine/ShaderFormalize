"""Structural DXC dump analysis. This module never generates a proof model."""
from collections import Counter, deque
from dataclasses import dataclass, field
import re


class AnalysisError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass
class Node:
    kind: str
    address: str
    text: str
    line: int
    parent: int
    children: list = field(default_factory=list)


def tail(node):
    """Skip a balanced source range, including nested <invalid sloc>."""
    start = node.text.find("<")
    if start < 0:
        raise AnalysisError("INVALID_AST", f"Missing source range at dump line {node.line}")
    depth = 0
    for position in range(start, len(node.text)):
        character = node.text[position]
        depth += int(character == "<") - int(character == ">")
        if depth == 0:
            return node.text[position+1:]
    raise AnalysisError("INVALID_AST", f"Unclosed source range at dump line {node.line}")


def quotes(node):
    return re.findall(r"'([^']*)'", tail(node))


def declaration(node):
    remainder = tail(node)
    types = re.findall(r"'([^']*)'", remainder)
    before = remainder.split("'", 1)[0].split()
    if not before or not types:
        raise AnalysisError("INVALID_DECLARATION", f"Missing declaration identity at dump line {node.line}")
    return {"id": node.address, "name": before[-1], "signature": types[0],
            "dump_line": node.line, "header": node.text}


class DumpIndex:
    def __init__(self, text, max_nodes=500000, max_depth=128, max_definitions=8192):
        self.nodes, stack = [], []
        pattern = re.compile(r"^([ |`-]*)([A-Za-z_][A-Za-z_0-9]*) (0x[0-9a-fA-F]+)(.*)$")
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            null = re.fullmatch(r"([ |`-]*)<<<NULL>>>", line)
            match = pattern.fullmatch(line)
            if null:
                prefix, kind, address, raw = null.group(1), "Null", "", ""
            elif match:
                prefix, kind, address, raw = match.groups()
            else:
                raise AnalysisError("INVALID_AST", f"Unrecognized dump line {line_number}")
            depth = len(prefix) // 2
            if len(prefix) % 2 or depth > len(stack) or depth > max_depth:
                raise AnalysisError("INVALID_AST", f"Invalid or excessive tree depth at dump line {line_number}")
            if len(self.nodes) >= max_nodes:
                raise AnalysisError("BUDGET_EXCEEDED", "AST node budget exceeded")
            if not depth and (self.nodes or kind != "TranslationUnitDecl"):
                raise AnalysisError("INVALID_AST", "Expected one TranslationUnitDecl root")
            index = len(self.nodes)
            parent = stack[depth-1] if depth else None
            if parent is not None:
                self.nodes[parent].children.append(index)
            self.nodes.append(Node(kind, address, raw, line_number, parent))
            stack = stack[:depth] + [index]
        if not self.nodes:
            raise AnalysisError("INVALID_AST", "Empty AST")
        self.functions, self.groups, self.globals = {}, {}, {}
        for index, node in enumerate(self.nodes):
            if node.kind in ("FunctionDecl", "CXXMethodDecl"):
                declaration(node)  # Validate before grouping or indexing its signature.
                if node.address in self.functions:
                    raise AnalysisError("INVALID_DECLARATION", "Duplicate function declaration ID")
                self.functions[node.address] = index
            elif node.kind == "VarDecl" and node.parent is not None:
                if self.nodes[node.parent].kind in ("TranslationUnitDecl", "NamespaceDecl", "HLSLBufferDecl"):
                    if node.address in self.globals:
                        raise AnalysisError("INVALID_DECLARATION", "Duplicate global declaration ID")
                    self.globals[node.address] = index
        self.canonical = {}
        self.missing_previous = set()
        for address in self.functions:
            chain, current = [], address
            while current not in self.canonical:
                if current in chain:
                    raise AnalysisError("INVALID_DECLARATION", "Cyclic previous-declaration chain")
                chain.append(current)
                if current not in self.functions:
                    self.missing_previous.add(current)
                    break
                prefix = self.nodes[self.functions[current]].text.split("<", 1)[0]
                previous = re.search(r"\bprev (0x[0-9a-fA-F]+)", prefix)
                if previous is None:
                    break
                current = previous.group(1)
            canonical = self.canonical.get(current, current)
            for item in chain:
                self.canonical[item] = canonical
        for address, index in self.functions.items():
            canonical = self.canonical[address]
            self.groups.setdefault(canonical, []).append(index)
        self.bodies = {}
        self.conflicting_signatures = set()
        for canonical, declarations in self.groups.items():
            if len({quotes(self.nodes[index])[-1] for index in declarations}) > 1:
                self.conflicting_signatures.add(canonical)
            bodies = []
            for index in declarations:
                bodies.extend(child for child in self.nodes[index].children if self.nodes[child].kind == "CompoundStmt")
            self.bodies[canonical] = bodies
        self.definition_count = sum(len(bodies) for bodies in self.bodies.values())
        if self.definition_count > max_definitions:
            raise AnalysisError("BUDGET_EXCEEDED", "Function definition budget exceeded")

    def unwrap(self, index):
        while self.nodes[index].kind in ("ImplicitCastExpr", "ParenExpr"):
            children = self.nodes[index].children
            if len(children) != 1:
                return None
            index = children[0]
        return index

    def callee(self, node):
        if not node.children:
            return None
        index = self.unwrap(node.children[0])
        if index is None:
            return None
        child = self.nodes[index]
        remainder = tail(child)
        match = re.search(r"\b(Function|CXXMethod) (0x[0-9a-fA-F]+) '([^']*)'", remainder)
        if child.kind == "DeclRefExpr" and match:
            kind, address, name = match.groups()
        elif child.kind == "MemberExpr":
            match = re.search(r"[.]([A-Za-z_][A-Za-z_0-9]*) (0x[0-9a-fA-F]+)", remainder)
            if match is None:
                return None
            name, address = match.groups()
            kind = "CXXMethod"
        else:
            return None
        return {"raw_id": address, "canonical_id": self.canonical.get(address, address),
                "name": name, "kind": kind, "signature": quotes(child)[0] if quotes(child) else None}

    def default(self, canonical, parameter):
        if canonical in self.conflicting_signatures:
            return None
        candidates = {}
        for index in self.groups.get(canonical, []):
            parameters = [child for child in self.nodes[index].children if self.nodes[child].kind == "ParmVarDecl"]
            if parameter >= len(parameters):
                continue
            node = self.nodes[parameters[parameter]]
            if re.search(r"\bcinit\b", tail(node)):
                initializers = [child for child in node.children if not self.nodes[child].kind.endswith("Attr")
                                and self.nodes[child].kind != "SemanticDecl"]
                for child in initializers:
                    candidates[self.nodes[child].address] = child
        return next(iter(candidates.values())) if len(candidates) == 1 else None


CALLS = {"CallExpr", "CXXMemberCallExpr", "CXXOperatorCallExpr"}
PLAIN = {"CompoundStmt", "NullStmt", "Null", "DeclStmt", "VarDecl", "ParmVarDecl", "ReturnStmt",
         "IfStmt", "ForStmt", "WhileStmt", "DoStmt", "SwitchStmt", "CaseStmt", "DefaultStmt",
         "BreakStmt", "ContinueStmt", "DiscardStmt", "AttributedStmt", "IntegerLiteral", "FloatingLiteral",
         "CXXBoolLiteralExpr", "StringLiteral", "CharacterLiteral", "DeclRefExpr", "MemberExpr",
         "ImplicitCastExpr", "CStyleCastExpr", "CXXFunctionalCastExpr", "ParenExpr", "InitListExpr",
         "HLSLVectorElementExpr", "ExtVectorElementExpr", "ExtMatrixElementExpr", "ArraySubscriptExpr",
         "BinaryOperator", "CompoundAssignOperator", "UnaryOperator", "ConditionalOperator", "ConstantExpr"}
OPERATORS = {"+", "-", "*", "/", "%", "<", ">", "<=", ">=", "==", "!=", "&&", "||", "&", "|", "^",
             "<<", ">>", "~", "!", "=", "+=", "-=", "*=", "/=", "%=", "|=", "&=", "^=", "<<=", ">>=", "++", "--"}
FEATURES = {"WhileStmt", "ForStmt", "DoStmt", "SwitchStmt", "ArraySubscriptExpr", "ExtMatrixElementExpr",
            "CXXDefaultArgExpr", "CStyleCastExpr"}


class Analyzer:
    def __init__(self, index, entry, max_edges=100000):
        self.index, self.max_edges = index, max_edges
        self.queue = deque()
        self.paths, self.reached, self.scanned = {}, {}, set()
        self.edges, self.defaults, self.issues = [], [], []
        self.default_nodes, self.global_references, self.initializers = set(), set(), []
        self.counts = {"body": Counter(), "default": Counter(), "global_initializer": Counter()}
        self.types, self.operators, self.examples = Counter(), Counter(), {}
        entries = []
        for canonical, declarations in index.groups.items():
            if any(declaration(index.nodes[node])["name"] == entry for node in declarations):
                entries.append(canonical)
        if len(entries) != 1:
            raise AnalysisError("ENTRY_NOT_FOUND" if not entries else "AMBIGUOUS_ENTRY", "Entry must identify one declaration group")
        self.entry = entries[0]
        self.entry_info = declaration(index.nodes[index.groups[self.entry][0]])
        if not index.bodies[self.entry]:
            raise AnalysisError("ENTRY_NOT_DEFINED", "Entry has no body")
        self.enqueue_function(self.entry, [entry])
        # Initializers can have effects even when nobody reads the global value.
        for address, node_index in index.globals.items():
            node = index.nodes[node_index]
            roots = [child for child in node.children if not index.nodes[child].kind.endswith("Attr")
                     and index.nodes[child].kind not in ("RegisterAssignment", "SemanticDecl")]
            if roots:
                item = declaration(node)
                self.initializers.append(item)
                for root in roots:
                    self.queue.append((root, f"global:{address}", [f"global initializer {item['name']}"], "global_initializer"))

    def issue(self, code, node, owner):
        self.issues.append({"code": code, "dump_line": node.line, "kind": node.kind, "owner": owner, "header": node.text})

    def enqueue_function(self, canonical, path):
        if canonical in self.paths:
            return
        self.paths[canonical] = path
        declarations = self.index.groups.get(canonical, [])
        bodies = self.index.bodies.get(canonical, [])
        if len({declaration(self.index.nodes[index])["name"] for index in declarations}) > 1:
            self.issue("DECLARATION_NAME_MISMATCH", self.index.nodes[declarations[0]], canonical)
        if canonical in self.index.conflicting_signatures:
            self.issue("DECLARATION_SIGNATURE_MISMATCH", self.index.nodes[declarations[0]], canonical)
        if canonical in self.index.missing_previous:
            self.issue("MISSING_PREVIOUS_DECLARATION", self.index.nodes[declarations[0]], canonical)
        if len(bodies) > 1:
            self.issue("AMBIGUOUS_DEFINITION", self.index.nodes[bodies[0]], canonical)
        elif bodies:
            self.reached[canonical] = bodies[0]
            self.queue.append((bodies[0], canonical, path, "body"))

    def call(self, node, owner, path):
        target = self.index.callee(node)
        if target is None:
            self.issue("UNRESOLVED_CALLEE", node, owner)
            return
        if len(self.edges) >= self.max_edges:
            raise AnalysisError("BUDGET_EXCEEDED", "Call edge budget exceeded")
        canonical = target["canonical_id"]
        target = dict(target, owner=owner, dump_line=node.line, external=not bool(self.index.bodies.get(canonical)))
        self.edges.append(target)
        if canonical in self.index.groups:
            self.enqueue_function(canonical, path + [target["name"]])
        offset = 2 if node.kind == "CXXOperatorCallExpr" and target["kind"] == "CXXMethod" else 1
        for position, argument in enumerate(node.children[offset:]):
            unwrapped = self.index.unwrap(argument)
            if unwrapped is None or self.index.nodes[unwrapped].kind != "CXXDefaultArgExpr":
                continue
            self.default_nodes.add(unwrapped)
            value = self.index.default(canonical, position)
            binding = {"call_line": node.line, "default_arg_line": self.index.nodes[unwrapped].line,
                       "callee_id": canonical, "parameter": position,
                       "initializer_line": self.index.nodes[value].line if value is not None else None}
            self.defaults.append(binding)
            if value is None:
                self.issue("UNRESOLVED_DEFAULT_ARGUMENT", self.index.nodes[unwrapped], owner)
            else:
                label = f"default {target['name']} parameter {position}"
                self.queue.append((value, f"default:{canonical}:{position}", path + [label], "default"))

    def scan(self, root, owner, path, origin):
        pending = [root]
        while pending:
            index = pending.pop()
            if index in self.scanned:
                continue
            self.scanned.add(index)
            node = self.index.nodes[index]
            self.counts[origin][node.kind] += 1
            if node.kind in CALLS:
                self.call(node, owner, path)
            elif node.kind == "CXXDefaultArgExpr":
                if index not in self.default_nodes:
                    self.issue("UNBOUND_DEFAULT_ARGUMENT", node, owner)
            elif node.kind not in PLAIN and not node.kind.endswith("Attr"):
                self.issue("UNKNOWN_POTENTIAL_CALL", node, owner)
            if node.kind == "DeclRefExpr":
                reference = re.search(r"\bVar (0x[0-9a-fA-F]+) '", tail(node))
                if reference and reference.group(1) in self.index.globals:
                    self.global_references.add(reference.group(1))
            types = quotes(node) if node.kind != "Null" else []
            if types:
                self.types[types[0]] += 1
            if node.kind in ("BinaryOperator", "CompoundAssignOperator", "UnaryOperator"):
                operators = [item for item in types[1:] if item in OPERATORS]
                if operators:
                    self.operators[operators[0]] += 1
            if node.kind in FEATURES:
                examples = self.examples.setdefault(node.kind, [])
                if len(examples) < 8:
                    examples.append({"dump_line": node.line, "owner": owner, "path": path, "header": node.text})
            pending.extend(reversed(node.children))

    def run(self):
        while self.queue:
            self.scan(*self.queue.popleft())
        functions = []
        for canonical, body in self.reached.items():
            parent = self.index.nodes[body].parent
            functions.append(dict(declaration(self.index.nodes[parent]), canonical_id=canonical, path=self.paths[canonical]))
        externals = {}
        for edge in self.edges:
            if edge["external"]:
                identity = edge["canonical_id"]
                externals.setdefault(identity, {key: edge[key] for key in ("raw_id", "canonical_id", "name", "kind", "signature")})
        return {"status": "INCOMPLETE" if self.issues else "ANALYZED", "schema": 1,
                "guarantee": "Syntactic may-call upper bound including global initialization and used default arguments; not a source importer or equivalence result",
                "entry_id": self.entry, "entry": self.entry_info, "definition_count": self.index.definition_count,
                "ast_nodes": len(self.index.nodes), "reachable_definitions": len(functions),
                "functions": functions, "calls": self.edges, "external_calls": list(externals.values()),
                "default_arguments": self.defaults, "global_initializers": self.initializers,
                "referenced_globals": [declaration(self.index.nodes[self.index.globals[key]]) for key in sorted(self.global_references)],
                "node_counts_by_origin": self.counts, "types": self.types, "operators": self.operators,
                "feature_examples": self.examples, "issues": self.issues,
                "precision": "No constant propagation, branch feasibility, execution counts, or resource dataflow analysis; globals include conservative initialization roots"}

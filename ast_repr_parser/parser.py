"""
Parse the Cangjie compiler AST text representation into a generic tree.
Structure is bracket-driven ({ ... } and [ ... ]).
"""

import re
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class ASTNode:
    """A node in the parsed AST. type and name identify the node; props hold key-value metadata; children are nested nodes."""
    type: str
    name: str = ""
    value: Optional[str] = None
    props: dict = field(default_factory=dict)
    children: List["ASTNode"] = field(default_factory=list)
    list_props: dict = field(default_factory=dict)  # key -> list of ASTNode (or raw values for simple lists)

    def get(self, key: str, default: Any = None) -> Any:
        if key in self.list_props:
            return self.list_props[key]
        return self.props.get(key, default)

    def get_position(self) -> Optional[str]:
        p = self.props.get("position")
        if p is not None:
            return str(p).strip()
        return None


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _strip_comment(line: str) -> str:
    i = 0
    while i < len(line):
        if line[i:i+2] == "//":
            return line[:i].rstrip()
        if line[i] == '"':
            i += 1
            while i < len(line) and line[i] != '"':
                if line[i] == "\\":
                    i += 1
                i += 1
            i += 1
            continue
        i += 1
    return line


def _parse_line(line: str) -> tuple:
    stripped = line.strip()
    if not stripped or stripped.startswith("//"):
        return ("comment",)
    if stripped == "}":
        return ("close",)
    if stripped == "]":
        return ("list_end",)
    m = re.match(r"^([A-Za-z][A-Za-z0-9_]*)\s*:\s*\[\s*$", stripped)
    if m:
        return ("list_start", m.group(1))
    m = re.match(r"^([A-Za-z][A-Za-z0-9_]*)\s+\[\s*$", stripped)
    if m:
        return ("list_start", m.group(1))
    if stripped.endswith(" {"):
        rest = stripped[:-2].rstrip()
        if ": " in rest:
            idx = rest.index(": ")
            ntype = rest[:idx].strip().rstrip(":")
            name = rest[idx+2:].strip()
            return ("node", ntype, name)
        # "Block {" or "ClassBody {" or "RefType: {" (colon but no space after)
        if ":" in rest:
            idx = rest.rfind(":")
            ntype = rest[:idx].strip()
            name = rest[idx+1:].strip()
            return ("node", ntype, name)
        parts = rest.rsplit(None, 1)
        if len(parts) == 2:
            return ("node", parts[0], parts[1])
        if len(parts) == 1:
            return ("node", parts[0], "")
        return ("node", rest, "")
    if ": " in stripped:
        idx = stripped.index(": ")
        key = stripped[:idx].strip()
        value = stripped[idx+2:].strip()
        return ("kv", key, value)
    return ("comment",)


class LineReader:
    def __init__(self, path: str):
        self.lines: List[tuple] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                content = line.rstrip("\n")
                indent = _indent(content)
                stripped = _strip_comment(content).strip()
                self.lines.append((indent, content, stripped))
        self.i = 0

    def peek(self) -> Optional[tuple]:
        if self.i >= len(self.lines):
            return None
        return self.lines[self.i]

    def consume(self) -> Optional[tuple]:
        if self.i >= len(self.lines):
            return None
        t = self.lines[self.i]
        self.i += 1
        return t

    def at_end(self) -> bool:
        return self.i >= len(self.lines)


def _parse_lit_const_name(name: str) -> tuple[str, Optional[str]]:
    text = name.strip()
    if not text:
        return ("", None)
    parts = text.split(None, 1)
    kind = parts[0]
    raw_value = parts[1].strip() if len(parts) > 1 else ""
    if raw_value.startswith('"') and raw_value.endswith('"') and len(raw_value) >= 2:
        return (kind, raw_value[1:-1])
    return (kind, raw_value or None)


def _make_node(ntype: str, name: str) -> ASTNode:
    if ntype == "LitConstExpr":
        lit_kind, lit_value = _parse_lit_const_name(name)
        return ASTNode(type=ntype, name=lit_kind, value=lit_value)
    return ASTNode(type=ntype, name=name)


def _parse_node_content(reader: LineReader, node: ASTNode) -> None:
    """Parse node body until its closing `}` (or end-of-file)."""
    while True:
        cur = reader.peek()
        if cur is None:
            return
        _indent_val, _raw, stripped = cur
        kind = _parse_line(stripped)

        # End of the current node body.
        if kind[0] == "close":
            reader.consume()
            return

        reader.consume()
        if kind[0] == "comment":
            continue
        if kind[0] == "list_end":
            continue
        if kind[0] == "list_start":
            key = kind[1]
            node.list_props[key] = []
            while True:
                elem = reader.peek()
                if elem is None:
                    break
                _ei, _eraw, estripped = elem
                ek = _parse_line(estripped)
                if ek[0] == "list_end":
                    reader.consume()
                    break
                if ek[0] == "comment":
                    reader.consume()
                    continue
                if ek[0] == "node":
                    reader.consume()
                    child = _make_node(ek[1], ek[2])
                    node.list_props[key].append(child)
                    _parse_node_content(reader, child)
                    continue
                # Any other token in list is consumed to ensure forward progress.
                reader.consume()
            continue
        if kind[0] == "kv":
            node.props[kind[1]] = kind[2]
            continue
        if kind[0] == "node":
            child = _make_node(kind[1], kind[2])
            node.children.append(child)
            _parse_node_content(reader, child)
            continue


def parse_ast_repr(path: str) -> ASTNode:
    reader = LineReader(path)
    first = reader.consume()
    if first is None:
        raise ValueError("Empty file")
    indent0, raw0, stripped0 = first
    kind = _parse_line(stripped0)
    if kind[0] != "node":
        raise ValueError(f"Expected root node at start, got {raw0!r}")

    root_type, root_name = kind[1], kind[2]
    if root_name.endswith(" {"):
        root_name = root_name[:-2].rstrip()

    root = _make_node(root_type, root_name)
    _parse_node_content(reader, root)

    if root.type == "File":
        return root

    if root.type == "Package":
        for child in root.children:
            if child.type == "File":
                return child
        raise ValueError("Package root found, but no File child was present")

    raise ValueError(f"Expected root 'File' or 'Package', got {raw0!r}")

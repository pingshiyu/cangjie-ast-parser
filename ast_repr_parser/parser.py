"""
Parse the Cangjie compiler AST text representation into a generic tree.
Indentation-based: 4 spaces per nesting level. Root has no leading spaces.
"""

import re
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class ASTNode:
    """A node in the parsed AST. type and name identify the node; props hold key-value metadata; children are nested nodes."""
    type: str
    name: str = ""
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


def _parse_node_content(reader: LineReader, parent_indent: int, node: ASTNode) -> None:
    """Parse lines that belong to node (indent > parent_indent) until } at parent_indent or end."""
    while True:
        cur = reader.peek()
        if cur is None:
            return
        indent, raw, stripped = cur
        if indent <= parent_indent:
            return
        kind = _parse_line(stripped)
        reader.consume()
        if kind[0] == "close":
            # Consumed the closing }; continue to next sibling
            continue
        if kind[0] == "comment":
            continue
        if kind[0] == "list_end":
            continue
        if kind[0] == "list_start":
            key = kind[1]
            node.list_props[key] = []
            list_indent = indent
            while True:
                elem = reader.peek()
                if elem is None:
                    break
                ei, eraw, estripped = elem
                if ei <= list_indent and estripped == "]":
                    reader.consume()
                    break
                if ei > list_indent:
                    ek = _parse_line(estripped)
                    if ek[0] == "node":
                        reader.consume()
                        child = ASTNode(type=ek[1], name=ek[2])
                        node.list_props[key].append(child)
                        _parse_node_content(reader, ei, child)
                    else:
                        reader.consume()
            continue
        if kind[0] == "kv":
            node.props[kind[1]] = kind[2]
            continue
        if kind[0] == "node":
            child = ASTNode(type=kind[1], name=kind[2])
            node.children.append(child)
            _parse_node_content(reader, indent, child)
            continue


def parse_ast_repr(path: str) -> ASTNode:
    reader = LineReader(path)
    first = reader.consume()
    if first is None:
        raise ValueError("Empty file")
    indent0, raw0, stripped0 = first
    kind = _parse_line(stripped0)
    if kind[0] != "node" or kind[1] != "File":
        raise ValueError(f"Expected 'File: ... {{' at start, got {raw0!r}")
    name = kind[2]
    if name.endswith(" {"):
        name = name[:-2].rstrip()
    root = ASTNode(type="File", name=name)
    _parse_node_content(reader, indent0, root)
    return root

"""
Emit desugared Cangjie source from parsed AST. Faithful to AST; no reverse-desugaring.
Positions emitted as comments; unknown nodes as placeholders with info preserved.
"""

from typing import List, Any, Optional
from .parser import ASTNode

# Known node types we can emit; others get a placeholder
KNOWN_NODE_TYPES = {
    "File", "PackageSpec", "ImportSpec", "ClassDecl", "ClassBody", "MainDecl",
    "FuncDecl", "FuncBody", "FuncParamList", "FuncParam", "Block", "VarDecl",
    "CallExpr", "BaseFunc", "RefExpr", "MemberAccess", "LitConstExpr",
    "RefType", "PrimitiveType", "AssignExpr", "BinaryExpr", "IfExpr", "MatchExpr",
    "MatchCase", "LambdaExpr", "TryExpr", "TryBlock", "Catch", "CatchPattern",
    "CatchBlock", "ExceptTypePattern", "VarPattern", "WildcardPattern",
    "ReturnExpr", "ThrowExpr", "FuncArg", "FinallyBlock", "TypePattern",
}


# Set by ast_to_cangjie(..., include_comments=...) so all emitters can skip position comments
_INCLUDE_COMMENTS = True
_SANITIZE_IDENTIFIERS = True


def _reindent(s: str, base_indent: str) -> str:
    """Reindent a multi-line string: strip minimum leading whitespace from each line, then prepend base_indent."""
    if not s or "\n" not in s:
        return s
    lines = s.split("\n")
    min_spaces = min(
        (len(line) - len(line.lstrip()) for line in lines if line.strip()),
        default=0,
    )
    return "\n".join(base_indent + line[min_spaces:] for line in lines)


def _position_comment(node: ASTNode) -> str:
    if not _INCLUDE_COMMENTS:
        return ""
    pos = node.get_position()
    if pos:
        return f"// position: {pos}\n"
    return ""


def _sanitize_identifier(name: str) -> str:
    if not _SANITIZE_IDENTIFIERS:
        return name
    return name.replace("-", "__").replace("$", "dollar_")


def _emit_type(node: ASTNode) -> str:
    """Emit type from RefType or PrimitiveType node."""
    if node.type == "PrimitiveType":
        return _sanitize_identifier(node.name or node.props.get("ty", "Unknown"))
    if node.type == "RefType":
        name = node.name.strip() if node.name else node.props.get("ty", "").split("-")[-1].split("<")[0]
        name = _sanitize_identifier(name)
        args = node.list_props.get("typeArguments", [])
        if args:
            arg_strs = []
            for a in args:
                if isinstance(a, ASTNode):
                    arg_strs.append(_emit_type(a))
                else:
                    arg_strs.append(str(a))
            return f"{name}<{', '.join(arg_strs)}>"
        return name or "Unit"
    return "Unknown"


def _emit_expr(node: ASTNode, indent: str) -> str:
    """Emit expression node to Cangjie."""
    pos = _position_comment(node)
    if node.type == "RefExpr":
        name = _sanitize_identifier(node.name.strip()) if node.name else "?"
        return pos + indent + name
    if node.type == "LitConstExpr":
        # LitConstExpr: String "..." or Integer "0" or Unit "()"
        kind = (node.name or node.props.get("ty", "")).strip()
        value = (node.value or "").strip()
        if "String" in kind or "string" in kind:
            return pos + indent + (f'"{value}"' if value else '""')
        if "Integer" in kind or "Int" in kind:
            return pos + indent + (value if value else "0")
        if "Bool" in kind:
            return pos + indent + (value if value else "false")
        if "Unit" in kind:
            return pos + indent + (value if value else "()")
        return pos + indent + (value if value else "()")
    if node.type == "CallExpr":
        base = ""
        args_list = node.list_props.get("arguments", [])
        for c in node.children:
            if c.type == "BaseFunc":
                base = _emit_base_func(c, indent)
                break
        if not base:
            for c in node.children:
                if c.type == "MemberAccess":
                    base = _emit_member_access(c, indent)
                    break
        if base.endswith(".init"):
            base = base[:-5]
        arg_strs = []
        for fa in args_list:
            if isinstance(fa, ASTNode):
                for fc in fa.children:
                    arg_strs.append(_emit_expr(fc, ""))
                if not fa.children and hasattr(fa, "props"):
                    # FuncArg might have expr in children or as single child
                    for fc in fa.children:
                        arg_strs.append(_emit_expr(fc, ""))
        if not arg_strs and args_list:
            for fa in args_list:
                if isinstance(fa, ASTNode):
                    # emit first expression child of FuncArg
                    for fc in fa.children:
                        arg_strs.append(_emit_expr(fc, ""))
                        break
        return pos + indent + base + "(" + ", ".join(arg_strs) + ")"
    if node.type == "MemberAccess":
        return pos + indent + _emit_member_access(node, indent)
    if node.type == "Block":
        # Block can contain a single expression or multiple statements
        parts = []
        for c in node.children:
            parts.append(_emit_stmt(c, indent + "    "))
        body = "\n".join(parts) if parts else ""
        return pos + indent + "{\n" + body + "\n" + indent + "}"
    if node.type == "AssignExpr":
        left = ""
        right = ""
        for c in node.children:
            if "leftValue" in str(c.type) or c.type == "MemberAccess" or c.type == "RefExpr":
                if not left:
                    left = _emit_expr(c, "")
            else:
                right = _emit_expr(c, "")
        # Sometimes left/right are in section comments; scan children
        for i, c in enumerate(node.children):
            if c.type == "MemberAccess" or c.type == "RefExpr":
                left = _emit_expr(c, "").strip()
            elif c.type in ("CallExpr", "RefExpr", "LitConstExpr", "Block", "MemberAccess"):
                if not right:
                    right = _emit_expr(c, "").strip()
        # Try to get from first two expr-like children
        expr_children = [c for c in node.children if c.type in ("MemberAccess", "RefExpr", "CallExpr", "LitConstExpr", "Block")]
        if len(expr_children) >= 2:
            left = _emit_expr(expr_children[0], "").strip()
            right = _emit_expr(expr_children[1], "").strip()
        if len(expr_children) == 1:
            right = _emit_expr(expr_children[0], "").strip()
        return pos + indent + f"{left} = {right}"
    if node.type == "BinaryExpr":
        op = node.name.strip() if node.name else node.props.get("ty", "?")
        parts = []
        for c in node.children:
            parts.append(_emit_expr(c, "").strip())
        if len(parts) >= 2:
            return pos + indent + f"({parts[0]} {op} {parts[1]})"
        return pos + indent + op.join(parts)
    if node.type == "IfExpr":
        cond = ""
        then_b = ""
        else_b = ""
        for c in node.children:
            if "condExpr" in str(c.props) or (c.type == "Block" and not then_b and cond):
                if not cond and c.type != "Block":
                    cond = _emit_expr(c, "").strip()
            if c.type == "Block":
                if not then_b:
                    then_b = _emit_brace_body(c, indent + "    ")
                else:
                    else_b = _emit_brace_body(c, indent + "    ")
        # Heuristic: first non-Block is cond, then Block then Block
        non_block = [c for c in node.children if c.type != "Block"]
        blocks = [c for c in node.children if c.type == "Block"]
        if non_block:
            cond = _emit_expr(non_block[0], "").strip()
        if len(blocks) >= 1:
            then_b = _emit_brace_body(blocks[0], indent + "    ")
        if len(blocks) >= 2:
            else_b = _emit_brace_body(blocks[1], indent + "    ")
        if not cond:
            cond = "true"
        out = pos + indent + f"if ({cond}) {{\n{then_b}\n{indent}}}"
        if else_b:
            out += f" else {{\n{else_b}\n{indent}}}"
        return out
    if node.type == "MatchExpr":
        sel = ""
        for c in node.children:
            if c.type == "selector":
                if c.children:
                    sel = _emit_expr(c.children[0], "").strip()
                    break
                continue
            if c.type not in ("MatchCase", "patterns"):
                sel = _emit_expr(c, "").strip()
                break
        sel_node = node.props.get("selector")
        cases = node.list_props.get("matchCases", [])
        case_strs = []
        for mc in cases:
            if isinstance(mc, ASTNode) and mc.type == "MatchCase":
                case_strs.append(_emit_match_case(mc, indent + "    "))
        return pos + indent + f"match ({sel}) {{\n" + "\n".join(case_strs) + "\n" + indent + "}"
    if node.type == "ReturnExpr":
        for c in node.children:
            if c.type != "ReturnExpr":
                e = _emit_expr(c, indent).strip()
                if "\n" in e:
                    first, rest = e.split("\n", 1)
                    return pos + indent + "return " + first + "\n" + rest
                return pos + indent + "return " + e
        return pos + indent + "return ()"
    if node.type == "ThrowExpr":
        for c in node.children:
            e = _emit_expr(c, indent).strip()
            if "\n" in e:
                first, rest = e.split("\n", 1)
                return pos + indent + "throw " + first + "\n" + rest
            return pos + indent + "throw " + e
        return pos + indent + "throw"
    if node.type == "LambdaExpr":
        body_node = None
        for c in node.children:
            if c.type == "FuncBody":
                body_node = c
                break
        if not body_node:
            return pos + indent + "{ }"
        params = body_node.list_props.get("FuncParamList", [])
        if not params:
            # get from FuncParamList child
            for c in body_node.children:
                if c.type == "FuncParamList":
                    params = c.children
                    break
        param_strs = []
        for p in (params if isinstance(params, list) else []):
            if isinstance(p, ASTNode) and p.type == "FuncParam":
                param_strs.append(p.name.strip() if p.name else "_")
        body = ""
        for c in body_node.children:
            if c.type == "Block":
                body = _emit_brace_body(c, indent + "    ")
                break
        return pos + indent + f"{{ {', '.join(param_strs)} =>\n{body}\n{indent}}}"
    if node.type == "TryExpr":
        try_block = ""
        catches = []
        for c in node.children:
            if c.type == "TryBlock":
                for b in c.children:
                    if b.type == "Block":
                        try_block = _emit_block_body(b, indent + "    ")
            if c.type == "Catch":
                catches.append(_emit_catch(c, indent))
        return pos + indent + "try {\n" + try_block + "\n" + indent + "}" + "".join(catches)
    if node.type == "UnknowNode":
        info = f"UnknowNode: {node.name or '?'}"
        for k, v in list(node.props.items())[:3]:
            info += f" {k}={v}"
        return pos + indent + f"/* {info} */"
    if node.type not in KNOWN_NODE_TYPES:
        info = f"{node.type}: {node.name or ''}".strip()
        return pos + indent + f"/* unknown: {info} */"
    return pos + indent + "/* " + node.type + " */"


def _emit_base_func(node: ASTNode, indent: str) -> str:
    for c in node.children:
        if c.type == "RefExpr":
            return _sanitize_identifier((c.name or "?").strip())
        if c.type == "MemberAccess":
            return _emit_member_access(c, "")
    return "?"


def _emit_member_access(node: ASTNode, indent: str) -> str:
    base = ""
    field = _sanitize_identifier(node.props.get("field", ""))
    for c in node.children:
        if c.type in ("RefExpr", "CallExpr", "MemberAccess"):
            base = _emit_expr(c, "").strip()
            break
    return f"{base}.{field}" if base else field


def _emit_block_body(block_node: ASTNode, indent: str) -> str:
    parts = []
    for c in block_node.children:
        parts.append(_emit_stmt(c, indent))
    return "\n".join(parts)


def _emit_brace_body(block_node: ASTNode, indent: str) -> str:
    if len(block_node.children) == 1 and block_node.children[0].type == "Block":
        return _emit_block_body(block_node.children[0], indent)
    return _emit_block_body(block_node, indent)


def _emit_stmt(node: ASTNode, indent: str) -> str:
    """Emit a statement (VarDecl, CallExpr, etc.)."""
    pos = _position_comment(node)
    if node.type == "VarDecl":
        raw_name = (node.name or "").strip()
        has_let = raw_name.startswith("let ")
        ident = raw_name[4:].strip() if has_let else raw_name
        ident = _sanitize_identifier(ident) if ident else "_"
        name = f"let {ident}"
        type_str = ""
        init_node = None
        for c in node.children:
            if c.type == "RefType" or c.type == "PrimitiveType":
                type_str = _emit_type(c)
            elif init_node is None:
                init_node = c
        if not type_str:
            for c in node.children:
                if c.type == "RefType" or c.type == "PrimitiveType":
                    type_str = _emit_type(c)
                    break
        if not init_node:
            return pos + indent + name
        # Emit initializer at same indent level so Block/Lambda content gets indent+4 from block
        init_str = _emit_expr(init_node, indent).strip()
        eq_part = f"{name} : {type_str} = " if type_str else f"{name} = "
        if "\n" not in init_str:
            return pos + indent + eq_part + init_str
        # Multi-line: first line after "=", rest unchanged (already correctly indented)
        first_line = init_str.split("\n")[0].strip()
        rest = "\n".join(init_str.split("\n")[1:])
        return pos + indent + eq_part + first_line + "\n" + rest
    if node.type in ("CallExpr", "AssignExpr", "ReturnExpr", "ThrowExpr"):
        return _emit_expr(node, indent)
    if node.type == "Block":
        return _emit_expr(node, indent)
    if node.type == "IfExpr":
        return _emit_expr(node, indent)
    if node.type == "MatchExpr":
        return _emit_expr(node, indent)
    if node.type == "VarDecl":
        return _emit_stmt(node, indent)
    return pos + indent + _emit_expr(node, indent)


def _get_match_pattern(match_case_node: ASTNode) -> str:
    """Extract pattern string from MatchCase: TypePattern (var: Type) or WildcardPattern (_). MatchCase has child 'patterns' (from 'patterns {') whose children are TypePattern or WildcardPattern, or props like WildcardPattern: _."""
    pattern_nodes = []
    patterns_node = None
    for c in match_case_node.children:
        if c.type == "patterns":
            patterns_node = c
            pattern_nodes = c.children
            break
        if c.type == "WildcardPattern":
            return _sanitize_identifier((c.name or "_").strip())
        if c.type == "TypePattern":
            type_str = _sanitize_identifier((c.props.get("ty") or "Unknown").split("-")[-1].split("<")[0])
            var_name = "_"
            for child in c.children:
                if child.type == "VarPattern":
                    var_name = _sanitize_identifier((child.name or "_").strip())
                    break
            return f"{var_name}: {type_str}"
    if patterns_node and patterns_node.props.get("WildcardPattern") is not None:
        return (patterns_node.props.get("WildcardPattern") or "_").strip()
    for c in pattern_nodes:
        if c.type == "WildcardPattern":
            return _sanitize_identifier((c.name or "_").strip())
        if c.type == "TypePattern":
            type_str = _sanitize_identifier((c.props.get("ty") or "Unknown").split("-")[-1].split("<")[0])
            var_name = "_"
            for child in c.children:
                if child.type == "VarPattern":
                    var_name = _sanitize_identifier((child.name or "_").strip())
                    break
            return f"{var_name}: {type_str}"
    return "?"


def _emit_match_case(node: ASTNode, indent: str) -> str:
    pat = _get_match_pattern(node)
    body = ""
    expr_or_decls = node.list_props.get("exprOrDecls", [])
    if expr_or_decls:
        parts = []
        for item in expr_or_decls:
            if isinstance(item, ASTNode):
                parts.append(_emit_stmt(item, indent + "    "))
        body = "\n".join(parts)
    else:
        for c in node.children:
            if c.type == "Block":
                body = _emit_brace_body(c, indent + "    ")
                break
    return indent + f"case {pat} =>\n{body}"


def _get_catch_pattern(catch_node: ASTNode) -> tuple:
    """Extract (var_name, exception_type) from Catch -> CatchPattern -> ExceptTypePattern (VarPattern + RefType). Returns (None, None) if not found."""
    for c in catch_node.children:
        if c.type != "CatchPattern":
            continue
        for ep in c.children:
            if ep.type != "ExceptTypePattern":
                continue
            var_name = None
            except_type = None
            for child in ep.children:
                if child.type == "VarPattern":
                    var_name = _sanitize_identifier((child.name or "").strip()) or "_"
                if child.type == "RefType":
                    except_type = _sanitize_identifier((child.name or "").strip())
                    if not except_type:
                        except_type = _sanitize_identifier((child.props.get("ty") or "Unknown").split("-")[-1].split("<")[0])
            return (var_name or "_", except_type or "Unknown")
    return (None, None)


def _emit_catch(node: ASTNode, indent: str) -> str:
    var_name, except_type = _get_catch_pattern(node)
    block = ""
    for c in node.children:
        if c.type == "CatchBlock":
            for b in c.children:
                if b.type == "Block":
                    block = _emit_block_body(b, indent + "    ")
    if var_name is not None and except_type is not None:
        return f" catch ({var_name}: {except_type}) {{\n{block}\n{indent}}}"
    return f" catch {{\n{block}\n{indent}}}"


def ast_to_cangjie(
    root: ASTNode,
    include_comments: bool = True,
    sanitize_identifiers: bool = False,
) -> str:
    """Convert parsed AST to desugared Cangjie source.

    Set include_comments=False to omit position comments.
    Set sanitize_identifiers=True to allow identifiers to be parsed by cjc.
    """
    global _INCLUDE_COMMENTS, _SANITIZE_IDENTIFIERS
    prev = _INCLUDE_COMMENTS
    prev_sanitize = _SANITIZE_IDENTIFIERS
    _INCLUDE_COMMENTS = include_comments
    _SANITIZE_IDENTIFIERS = sanitize_identifiers
    try:
        return _ast_to_cangjie_impl(root)
    finally:
        _INCLUDE_COMMENTS = prev
        _SANITIZE_IDENTIFIERS = prev_sanitize


def _ast_to_cangjie_impl(root: ASTNode) -> str:
    """Implementation of ast_to_cangjie (uses _INCLUDE_COMMENTS)."""
    out: List[str] = []
    if root.type != "File":
        return "/* not a File node */"
    out.append(_position_comment(root))
    for c in root.children:
        if c.type == "PackageSpec":
            name = c.name.strip() if c.name else "?"
            out.append(f"package {name}\n")
        elif c.type == "ImportSpec":
            path = c.props.get("prefixPaths", "")
            name = c.name.strip() if c.name else "*"
            if name == "*":
                out.append(f"import {path}.*\n")
            else:
                out.append(f"import {path}.{{{name}}}\n")
        elif c.type == "ClassDecl":
            out.append(_emit_class(c))
        elif c.type == "MainDecl":
            out.append(_emit_main(c))
        else:
            out.append(_emit_unknown_or_placeholder(c))
    return "\n".join(out)


def _emit_class(node: ASTNode) -> str:
    pos = _position_comment(node)
    name = _sanitize_identifier((node.name or "").strip())
    inherited = node.list_props.get("inheritedTypes", [])
    base_str = ""
    if inherited:
        bases = []
        for b in inherited:
            if isinstance(b, ASTNode):
                bases.append(_emit_type(b))
        if bases:
            base_str = " <: " + ", ".join(bases)
    body_parts = []
    for c in node.children:
        if c.type == "ClassBody":
            for fn in c.children:
                if fn.type == "FuncDecl":
                    body_parts.append(_emit_func_decl(fn, "    "))
    body = "\n".join(body_parts) if body_parts else ""
    return pos + f"class {name}{base_str} {{\n{body}\n}}\n"


def _emit_func_decl(node: ASTNode, indent: str) -> str:
    pos = _position_comment(node)
    name = _sanitize_identifier((node.name or "").strip())
    if " " in name and "(" in name:
        name = name.split("(")[0].strip()
    is_init = name == "init"
    params = []
    ret_type = "Unit"
    for c in node.children:
        if c.type == "FuncBody":
            for fb in c.children:
                if fb.type == "FuncParamList":
                    for p in fb.children:
                        if p.type == "FuncParam":
                            pname = _sanitize_identifier((p.name or "_").strip())
                            pt = "Unknown"
                            for tc in p.children:
                                if tc.type in ("RefType", "PrimitiveType"):
                                    pt = _emit_type(tc)
                                    break
                            params.append(f"{pname}: {pt}")
                if fb.type in ("RefType", "PrimitiveType"):
                    ret_type = _emit_type(fb)
            for fb in c.children:
                if fb.type == "RefType" and not fb.name:
                    ret_type = _sanitize_identifier(fb.props.get("ty", ret_type).split("-")[-1])
                if fb.type == "Block":
                    body = _emit_block_body(fb, indent + "    ")
                    param_str = ", ".join(params)
                    if is_init:
                        return pos + indent + f"init({param_str}) {{\n{body}\n{indent}}}\n"
                    return pos + indent + f"func {name}({param_str}): {ret_type} {{\n{body}\n{indent}}}\n"
    param_str = ", ".join(params)
    if is_init:
        return pos + indent + f"init({param_str}) {{\n{indent}}}\n"
    return pos + indent + f"func {name}({param_str}): {ret_type} {{\n{indent}}}\n"


def _emit_main(node: ASTNode) -> str:
    pos = _position_comment(node)
    for c in node.children:
        if c.type == "FuncDecl" and (c.name or "").strip().startswith("main"):
            # Emit main() { ... } (no func/return type)
            body = ""
            for fb in c.children:
                if fb.type == "FuncBody":
                    for bl in fb.children:
                        if bl.type == "Block":
                            body = _emit_block_body(bl, "    ")
                            break
            return pos + f"main() {{\n{body}\n}}\n"
    return pos + "main() {\n}\n"


def _emit_unknown_or_placeholder(node: ASTNode) -> str:
    pos = _position_comment(node)
    info = f"{node.type}: {node.name or ''}"
    for k in list(node.props.keys())[:2]:
        info += f" {k}={node.props[k]}"
    return pos + f"/* {info} */\n"

# cangjie-ast-parser

Parse the **Cangjie compiler’s AST dump** and convert it back to desugared Cangjie source.

## What file does it parse?

It parses the **text-based AST representation** produced by the Cangjie compiler (`cjc`) when you pass **`--dump-ast`**.

To generate an AST file from a Cangjie source file, compile with the `--dump-ast` flag in addition to the usual arguments.
For example:

```bash
cjc --dump-ast your-file.cj
```

This writes the compiler’s internal AST in a text format (indentation-based, with `//` comments). That output is what this parser reads.

## Requirements

- **Python 3**
- No extra dependencies (stdlib only).

## Command-line usage

From the `cangjie-ast-parser` directory:

```bash
# Parse an AST dump file and print desugared Cangjie to stdout
python3 run_ast_to_cangjie.py path/to/ast-dump.txt

# Default input: desugared-ast-repr.txt in this directory
python3 run_ast_to_cangjie.py

# Write result to a file
python3 run_ast_to_cangjie.py path/to/ast-dump.txt -o output.cj

# Omit position comments (// position: ...) from the output
python3 run_ast_to_cangjie.py path/to/ast-dump.txt --no-comments

# Round-trip identifier spelling ('-' -> '__', '$' -> 'dollar_')
python3 run_ast_to_cangjie.py path/to/ast-dump.txt --round-trip
```

**Options:**

| Option | Description |
|--------|-------------|
| `input` | Path to the AST repr file (optional; default: `desugared-ast-repr.txt` in this directory). |
| `-o`, `--output FILE` | Write desugared Cangjie to `FILE` instead of stdout. |
| `--no-comments` | Do not emit position comments in the output. |
| `--round-trip` | Enable round-trip lowering: sanitize identifiers and emit block expressions as `{ => ... }()`. |

## Using as a library

```python
from ast_repr_parser import parse_ast_repr, ast_to_cangjie, ASTNode

# Parse an AST dump file
root: ASTNode = parse_ast_repr("path/to/ast-dump.txt")

# Convert to desugared Cangjie source (string)
source = ast_to_cangjie(root)
print(source)

# Without position comments
source = ast_to_cangjie(root, include_comments=False)

# Enable round-trip lowering (identifier sanitization + block-expression wrapping)
source = ast_to_cangjie(root, sanitize_identifiers=True, round_trip=True)
```

- **`parse_ast_repr(path)`** — Reads the file at `path` and returns the root `ASTNode` of the parsed tree.
- **`ast_to_cangjie(root, include_comments=True, sanitize_identifiers=False, round_trip=False)`** — Converts the parsed AST back to desugared Cangjie source.

## Behaviour

- **Faithful to the desugared AST**: All nodes are emitted as in the AST (including `$frameLambda`, `HandlerFrame`, `DeferredFrame`, etc.). No reverse-desugaring.
- **Position**: Emitted as comments, e.g. `// position: (1, 26, 5) (1, 26, 66)` (unless `include_comments=False` or `--no-comments`).
- **Unknown nodes**: Emitted as placeholders with type/name info, e.g. `/* unknown: UnknowNode: *type */`.
- **String interpolation**: StringBuilder and `append`/`toString` are kept as in the AST (not converted back to interpolated strings).

## Project layout

- **`run_ast_to_cangjie.py`** — CLI entrypoint: reads an AST repr file and prints or writes desugared Cangjie.
- **`ast_repr_parser/`** — Python package:
  - **`parser.py`** — Parses the indentation-based AST text into an `ASTNode` tree.
  - **`codegen.py`** — Converts a parsed AST back to desugared Cangjie source.
  - **`__init__.py`** — Exposes `parse_ast_repr`, `ASTNode`, and `ast_to_cangjie`.

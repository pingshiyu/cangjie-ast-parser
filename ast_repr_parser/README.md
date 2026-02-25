# AST repr parser

Parse the Cangjie compiler's text-based AST representation and emit desugared Cangjie source.

## Usage

```python
from ast_repr_parser import parse_ast_repr, ast_to_cangjie

root = parse_ast_repr("path/to/desugared-ast-repr.txt")
cangjie_source = ast_to_cangjie(root)
print(cangjie_source)

# Preserve original identifier spelling
cangjie_source = ast_to_cangjie(root, sanitize_identifiers=False)
```

## Command line

From the repo root:

```bash
PYTHONPATH=. python3 -c "
from ast_repr_parser import parse_ast_repr, ast_to_cangjie
import sys
path = sys.argv[1] if len(sys.argv) > 1 else 'cangjie-resumptions-testing/desugared-ast-repr.txt'
root = parse_ast_repr(path)
print(ast_to_cangjie(root))
"
```

Or run the tests:

```bash
PYTHONPATH=. python3 tests/test_ast_repr_parser.py -v
```

## Behaviour

- **Faithful to desugared AST**: All nodes are emitted (including `$frameLambda`, `HandlerFrame`, `DeferredFrame`, etc.). No reverse-desugaring.
- **Position**: Emitted as comments, e.g. `// position: (1, 26, 5) (1, 26, 66)`.
- **Unknown nodes**: Emitted as placeholders with type/name info, e.g. `/* unknown: UnknowNode: *type */`.
- **String interpolation**: StringBuilder and `append`/`toString` are kept as in the AST (not recovered to interpolated strings).

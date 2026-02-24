"""
Tests for AST repr parser and codegen.
Plan: assert print strings "got here 0".."got here 5", dollar-prefixed vars, and structural sanity.
"""

import os
import re
import unittest
from ast_repr_parser import parse_ast_repr, ast_to_cangjie


# Path to the desugared AST repr file (relative to repo root)
DESUGARED_AST_PATH = os.path.join(
    os.path.dirname(__file__), "..", "cangjie-resumptions-testing", "desugared-ast-repr.txt"
)


def get_generated_cangjie():
    """Parse and convert the desugared AST file."""
    if not os.path.isfile(DESUGARED_AST_PATH):
        return None
    root = parse_ast_repr(DESUGARED_AST_PATH)
    return ast_to_cangjie(root)


class TestASTReprParser(unittest.TestCase):
    """Tests for parser and codegen."""

    @classmethod
    def setUpClass(cls):
        cls.generated = get_generated_cangjie()

    def test_parse_and_convert_runs(self):
        """Parser and codegen run without error and produce non-empty output."""
        if self.generated is None:
            self.skipTest(f"AST repr file not found: {DESUGARED_AST_PATH}")
        self.assertIsInstance(self.generated, str)
        self.assertGreater(len(self.generated), 0)

    def test_print_strings_got_here_present(self):
        """All 'got here 0'..'got here 4' (present in AST) must appear in the output."""
        if self.generated is None:
            self.skipTest(f"AST repr file not found: {DESUGARED_AST_PATH}")
        for i in range(5):
            self.assertIn(f"got here {i}", self.generated, f"Expected 'got here {i}' in output")

    def test_dollar_prefixed_variables_present(self):
        """Dollar-prefixed variables ($frameLambda, $handlerLambda) must appear."""
        if self.generated is None:
            self.skipTest(f"AST repr file not found: {DESUGARED_AST_PATH}")
        self.assertIn("$frameLambda", self.generated, "Expected $frameLambda in desugared output")
        self.assertIn("$handlerLambda", self.generated, "Expected $handlerLambda in desugared output")

    def test_structural_sanity(self):
        """Package, imports, and main entry should be present."""
        if self.generated is None:
            self.skipTest(f"AST repr file not found: {DESUGARED_AST_PATH}")
        self.assertIn("package ", self.generated)
        self.assertIn("import ", self.generated)
        self.assertIn("main()", self.generated)

    def test_position_comments_present(self):
        """Position should be emitted as comments."""
        if self.generated is None:
            self.skipTest(f"AST repr file not found: {DESUGARED_AST_PATH}")
        self.assertIn("// position:", self.generated)


class TestParserUnit(unittest.TestCase):
    """Unit test with a small snippet."""

    def test_parser_snippet(self):
        """Parse a small snippet (File with PackageSpec and one ImportSpec)."""
        import tempfile
        snippet = """File: test.cj {
    curFile: test.cj
    position: (1, 1, 1) (1, 10, 2)
    PackageSpec: pkgname {
      pkgname
    }
    ImportSpec: Foo {
      prefixPaths: std.foo
      isDecl: 1
    }
}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(snippet)
            path = f.name
        try:
            root = parse_ast_repr(path)
            self.assertEqual(root.type, "File")
            self.assertEqual(root.name, "test.cj")
            children_types = [c.type for c in root.children]
            self.assertIn("PackageSpec", children_types)
            self.assertIn("ImportSpec", children_types)
            pkg = next(c for c in root.children if c.type == "PackageSpec")
            self.assertEqual(pkg.name, "pkgname")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()

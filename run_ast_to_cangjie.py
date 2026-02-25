#!/usr/bin/env python3
"""Convert a Cangjie compiler AST repr file to desugared Cangjie source."""

import argparse
import os
import sys

# Allow importing ast_repr_parser from this directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ast_repr_parser import parse_ast_repr, ast_to_cangjie


def main():
    default_path = os.path.join(
        os.path.dirname(__file__), "desugared-ast-repr.txt"
    )
    parser = argparse.ArgumentParser(
        description="Convert a Cangjie compiler AST repr file to desugared Cangjie source."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=default_path,
        help=f"Path to the AST repr text file (default: {default_path})",
    )
    parser.add_argument(
        "--no-comments",
        action="store_true",
        help="Omit position comments (// position: ...) from the output",
    )
    parser.add_argument(
        "--sanitize-identifiers",
        action="store_true",
        help="Sanitize identifiers by replacing '-' with '__' and '$' with 'dollar_'",
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="Write output to FILE instead of stdout",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        parser.error(f"File not found: {args.input}")
    root = parse_ast_repr(args.input)
    out = ast_to_cangjie(
        root,
        include_comments=not args.no_comments,
        sanitize_identifiers=args.sanitize_identifiers,
    )
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        print(out)


if __name__ == "__main__":
    main()

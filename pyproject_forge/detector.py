"""Static (AST-based) detection of entry-point functions.

We never import user code to inspect it (that would execute arbitrary
side effects during a scan). Everything here is done with `ast.parse`.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

# Priority order for candidate function names. Lower index = preferred.
PREFERRED_NAMES = ("main", "cli", "run", "app", "usage")

# A function with this exact comment on the line above it (or as its
# first statement, a string containing the marker) is always preferred,
# regardless of name, resolving ambiguity explicitly instead of by guess.
ENTRY_MARKER = "pyproject-forge: entry"


@dataclass(frozen=True)
class EntryCandidate:
    module_file: Path        # the .py file the function lives in
    func_name: str           # function name
    is_marked: bool          # explicitly marked via ENTRY_MARKER comment
    takes_no_required_args: bool  # callable with no positional args (safe as entry)


def _func_takes_no_required_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    args = node.args
    n_defaults = len(args.defaults)
    n_positional = len(args.posonlyargs) + len(args.args)
    n_required_positional = n_positional - n_defaults
    has_required_kwonly = any(
        kw for kw, default in zip(args.kwonlyargs, args.kw_defaults) if default is None
    )
    return n_required_positional == 0 and not has_required_kwonly


def _has_entry_marker(source_lines: list[str], node: ast.AST) -> bool:
    lineno = getattr(node, "lineno", None)
    if lineno is None:
        return False
    # Check decorator lines and the line(s) immediately above the def.
    for offset in range(1, 4):
        idx = lineno - 1 - offset
        if idx < 0:
            break
        line = source_lines[idx]
        if ENTRY_MARKER in line:
            return True
        if line.strip() and not line.strip().startswith("#"):
            break
    return False


def find_entry_candidates(py_file: Path) -> list[EntryCandidate]:
    """Parse a single .py file and return all top-level function defs that
    look like they could be a console entry point.
    """
    try:
        source = py_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    try:
        tree = ast.parse(source, filename=str(py_file))
    except SyntaxError:
        return []

    source_lines = source.splitlines()
    candidates: list[EntryCandidate] = []

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        marked = _has_entry_marker(source_lines, node)
        if marked or node.name in PREFERRED_NAMES:
            candidates.append(
                EntryCandidate(
                    module_file=py_file,
                    func_name=node.name,
                    is_marked=marked,
                    takes_no_required_args=_func_takes_no_required_args(node),
                )
            )
    return candidates


def rank_candidates(candidates: list[EntryCandidate]) -> list[EntryCandidate]:
    """Sort candidates best-first: marked > preferred-name order > callable
    with no required args > others.
    """

    def key(c: EntryCandidate):
        try:
            name_rank = PREFERRED_NAMES.index(c.func_name)
        except ValueError:
            name_rank = len(PREFERRED_NAMES)
        return (
            0 if c.is_marked else 1,
            name_rank,
            0 if c.takes_no_required_args else 1,
        )

    return sorted(candidates, key=key)

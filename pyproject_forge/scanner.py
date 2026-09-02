#!/usr/bin/env python3

# File: pyproject-forge/pyproject_forge/scanner.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-02 11:34:12
# Description: 
# License: MIT

"""Walks a working directory and finds candidate "script packages":
folders containing .py files that should become an importable package
with a console_scripts entry point.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .utils import to_module_name

DEFAULT_EXCLUDES = frozenset(
    {
        ".git", ".hg", ".svn", ".venv", "venv", "env", ".env",
        "__pycache__", "node_modules", "build", "dist",
        ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
        ".idea", ".vscode", "site-packages",
    }
)
EGG_INFO_SUFFIX = ".egg-info"


@dataclass
class PackageCandidate:
    path: Path                      # absolute path to the folder
    rel_path: Path                  # path relative to scan root
    name: str                       # raw folder name
    py_files: list[Path] = field(default_factory=list)   # direct .py files
    has_init: bool = False
    has_main: bool = False
    parent_module_parts: tuple = field(default_factory=tuple)
    # sanitized module names of ancestor candidates that were themselves
    # selected as packages (only non-empty with --allow-nested). Lets the
    # generator build the correct dotted import path, e.g. "toolA.sub"
    # instead of just "sub".


def _is_excluded(dirname: str, excludes: frozenset[str]) -> bool:
    if dirname in excludes:
        return True
    if dirname.endswith(EGG_INFO_SUFFIX):
        return True
    if dirname.startswith("."):
        return True
    return False


def scan_packages(
    root: Path,
    max_depth: int = 3,
    extra_excludes: frozenset[str] = frozenset(),
    allow_nested: bool = False,
    include_root: bool = False,
) -> list[PackageCandidate]:
    """Return the list of directories under `root` that qualify as
    independent script packages.

    A directory qualifies if it directly contains at least one .py file.
    By default, once a directory qualifies it is NOT descended into for
    further top-level candidates (avoids double-registering a package's
    internal submodules as separate console scripts). Pass
    allow_nested=True to change that.
    """
    root = root.resolve()
    excludes = DEFAULT_EXCLUDES | extra_excludes
    results: list[PackageCandidate] = []

    def walk(current: Path, depth: int, stop_recursion: bool, parent_parts: tuple) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except PermissionError:
            return

        direct_py = [
            p for p in entries
            if p.is_file() and p.suffix == ".py"
        ]
        is_root_level = current == root

        qualifies = bool(direct_py) and (not is_root_level or include_root)

        next_parent_parts = parent_parts
        if qualifies:
            candidate = PackageCandidate(
                path=current,
                rel_path=current.relative_to(root),
                name=current.name if not is_root_level else root.name,
                py_files=direct_py,
                has_init=(current / "__init__.py").exists(),
                has_main=(current / "__main__.py").exists(),
                parent_module_parts=parent_parts,
            )
            results.append(candidate)
            next_parent_parts = parent_parts + (to_module_name(candidate.name),)
            if not allow_nested:
                stop_recursion = True

        if stop_recursion and qualifies:
            return

        for entry in entries:
            if not entry.is_dir():
                continue
            if _is_excluded(entry.name, excludes):
                continue
            walk(entry, depth + 1, stop_recursion, next_parent_parts)

    walk(root, depth=1, stop_recursion=False, parent_parts=())
    return results

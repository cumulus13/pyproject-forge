"""Small stateless helpers: name sanitizing, path/module conversion."""

from __future__ import annotations

import keyword
import re
from pathlib import Path

_KEBAB_SUB_RE = re.compile(r"[^a-z0-9]+")
_LEADING_TRAILING_DASH_RE = re.compile(r"^-+|-+$")


def to_console_name(identifier: str) -> str:
    """Convert an arbitrary folder/package name into a kebab-case console
    script name, e.g. 'My_Cool Tool' -> 'my-cool-tool'.
    """
    lowered = identifier.lower()
    kebab = _KEBAB_SUB_RE.sub("-", lowered)
    kebab = _LEADING_TRAILING_DASH_RE.sub("", kebab)
    return kebab or "unnamed-script"


def to_module_name(identifier: str) -> str:
    """Convert a folder name into a valid, importable Python module name.
    Falls back to prefixing with '_' if it starts with a digit or is a
    reserved keyword.
    """
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", identifier).strip("_")
    if not cleaned:
        cleaned = "pkg"
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned = f"{cleaned}_"
    return cleaned


def dotted_path(root_package: str, rel_parts: tuple[str, ...]) -> str:
    """Build a dotted module path from a root package name and the
    relative path parts under it, e.g. ('root', ('a', 'b')) -> 'root.a.b'.
    """
    parts = [root_package, *rel_parts] if root_package else list(rel_parts)
    return ".".join(parts)


def relative_parts(path: Path, root: Path) -> tuple[str, ...]:
    return tuple(path.relative_to(root).parts)


def is_hidden(path: Path) -> bool:
    return path.name.startswith(".")

#!/usr/bin/env python3

# File: pyproject-forge/pyproject_forge/header_parser.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-02 11:34:12
# Description: 
# License: MIT

Used two ways:
  - as a project-metadata source, sitting below explicit CLI/config
    (those were set on purpose) and above the interactive prompt
    (asking again for something already declared in the code is
    pointless) — see metadata.py.
  - to keep generated __main__.py files consistent with whatever
    shebang convention (if any) the rest of the project already uses,
    rather than inventing one from nothing.

Purely textual (first ~25 lines, comment characters only) — never
imports or executes the file being inspected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_FIELD_RE = re.compile(r"^#\s*([A-Za-z][A-Za-z0-9 _-]*)\s*:\s*(.*?)\s*$")
_EMAIL_RE = re.compile(r"<([^<>@\s]+@[^<>\s]+)>")
_MAX_HEADER_LINES = 25

# Maps the various header labels people actually use to a canonical field.
_FIELD_ALIASES = {
    "author": "author",
    "authors": "author",
    "maintainer": "maintainer",
    "date": "date",
    "created": "date",
    "description": "description",
    "desc": "description",
    "license": "license",
    "licence": "license",
    "version": "version",
    "file": "file",
    "filename": "file",
}


@dataclass
class FileHeader:
    shebang: str | None = None
    author_name: str | None = None
    author_email: str | None = None
    license: str | None = None
    description: str | None = None
    date: str | None = None
    version: str | None = None
    file_field: str | None = None


def parse_header(py_file: Path) -> FileHeader:
    """Read the leading comment block of a .py file: an optional shebang
    on line 1, then up to _MAX_HEADER_LINES of '# Key: value' comments.
    Stops at the first non-comment, non-blank line.
    """
    header = FileHeader()
    try:
        with py_file.open("r", encoding="utf-8", errors="replace") as f:
            lines = []
            for _ in range(_MAX_HEADER_LINES + 1):
                line = f.readline()
                if not line:
                    break
                lines.append(line.rstrip("\n"))
    except OSError:
        return header

    idx = 0
    if lines and lines[0].startswith("#!"):
        header.shebang = lines[0].strip()
        idx = 1

    for line in lines[idx:]:
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("#"):
            break
        m = _FIELD_RE.match(stripped)
        if not m:
            continue
        raw_key, value = m.group(1).strip().lower(), m.group(2).strip()
        canonical = _FIELD_ALIASES.get(raw_key)
        if not canonical or not value:
            continue

        if canonical == "author":
            email_match = _EMAIL_RE.search(value)
            if email_match:
                header.author_email = email_match.group(1)
                name_part = value[: email_match.start()].strip(" <")
                header.author_name = name_part or header.author_name
            else:
                header.author_name = value
        elif canonical == "license":
            header.license = value
        elif canonical == "description":
            header.description = value
        elif canonical == "date":
            header.date = value
        elif canonical == "version":
            header.version = value
        elif canonical == "file":
            header.file_field = value

    return header


def scan_headers(py_files: list[Path]) -> FileHeader:
    """Aggregate headers across many files: the first non-empty value
    found (in the given file order) wins per field. Used as a project-
    wide metadata fallback.
    """
    aggregate = FileHeader()
    for py_file in py_files:
        header = parse_header(py_file)
        for field_name in (
            "author_name", "author_email", "license",
            "description", "date", "version",
        ):
            if getattr(aggregate, field_name) is None and getattr(header, field_name):
                setattr(aggregate, field_name, getattr(header, field_name))
    return aggregate


def detect_shebang(py_files: list[Path], default: str | None = None) -> str | None:
    """Return the first shebang line found among py_files, or `default`
    if none of them declare one. Never invents a shebang out of thin
    air — a project with no shebangs anywhere stays that way unless the
    caller passes an explicit default.
    """
    for py_file in py_files:
        header = parse_header(py_file)
        if header.shebang:
            return header.shebang
    return default

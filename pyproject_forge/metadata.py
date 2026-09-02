#!/usr/bin/env python3

# File: pyproject-forge/pyproject_forge/metadata.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-02 11:35:32
# Description: 
# License: MIT

                              comment blocks found in the scanned .py
                              files — see header_parser.py)
    5. interactive prompt   (only for the core fields, only on a TTY,
                              only when creating a NEW pyproject.toml,
                              only if not --non-interactive)

Anything still unset after all five steps is simply omitted from the
generated [project] table — never filled with a placeholder guess.

Metadata is only ever applied when *creating* a new pyproject.toml.
An existing file's metadata is never touched, for the same reason
[project.scripts] entries are merged rather than overwritten: this tool
does not clobber content it didn't create.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, fields
from pathlib import Path

import tomlkit
from tomlkit.exceptions import ParseError

from .exceptions import ConfigParseError
from .header_parser import FileHeader

# Fields prompted for interactively when missing. Order matters (asked
# in this order). Everything else (keywords, urls, maintainer) is
# config/CLI-only — deliberately, so a first run isn't a 10-question quiz.
INTERACTIVE_FIELDS = ("author_name", "author_email", "license", "description")


@dataclass
class ProjectMetadata:
    author_name: str | None = None
    author_email: str | None = None
    maintainer_name: str | None = None
    maintainer_email: str | None = None
    license: str | None = None
    description: str | None = None
    keywords: list[str] | None = None
    homepage: str | None = None
    repository: str | None = None

    def merged_with(self, other: "ProjectMetadata") -> "ProjectMetadata":
        """Return a copy with `other`'s values filling in whatever is
        None on self. `self` wins on conflicts (self = higher precedence).
        """
        merged = {}
        for f in fields(self):
            mine = getattr(self, f.name)
            merged[f.name] = mine if mine not in (None, "", []) else getattr(other, f.name)
        return ProjectMetadata(**merged)

    def is_field_missing(self, name: str) -> bool:
        val = getattr(self, name)
        return val in (None, "", [])


def global_config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "pyproject-forge" / "defaults.toml"


def local_config_path(root: Path) -> Path:
    return root / ".pyprojectforge.toml"


def _load_toml_dict(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        return tomlkit.parse(text).unwrap()
    except (ParseError, OSError) as exc:
        raise ConfigParseError(str(path), exc) from exc


def _metadata_from_dict(data: dict) -> ProjectMetadata:
    defaults = data.get("defaults", data)  # allow either [defaults] table or flat file
    keywords = defaults.get("keywords")
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    return ProjectMetadata(
        author_name=defaults.get("author_name") or defaults.get("author"),
        author_email=defaults.get("author_email"),
        maintainer_name=defaults.get("maintainer_name"),
        maintainer_email=defaults.get("maintainer_email"),
        license=defaults.get("license"),
        description=defaults.get("description"),
        keywords=keywords,
        homepage=defaults.get("homepage"),
        repository=defaults.get("repository"),
    )


def load_config_metadata(root: Path) -> ProjectMetadata:
    """Load and merge global + project-local config files.
    Project-local wins over global on conflicts.
    """
    global_data = _load_toml_dict(global_config_path())
    local_data = _load_toml_dict(local_config_path(root))
    global_meta = _metadata_from_dict(global_data)
    local_meta = _metadata_from_dict(local_data)
    return local_meta.merged_with(global_meta)


def metadata_from_cli(args) -> ProjectMetadata:
    keywords = None
    if getattr(args, "keywords", None):
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    return ProjectMetadata(
        author_name=args.author,
        author_email=args.author_email,
        maintainer_name=args.maintainer,
        maintainer_email=args.maintainer_email,
        license=args.license,
        description=args.description,
        keywords=keywords,
        homepage=args.url_homepage,
        repository=args.url_repository,
    )


_PROMPTS = {
    "author_name": "Author name",
    "author_email": "Author email",
    "license": "License (e.g. MIT, Apache-2.0)",
    "description": "One-line project description",
}


def prompt_missing(meta: ProjectMetadata, allow_interactive: bool) -> ProjectMetadata:
    """Fill any still-missing INTERACTIVE_FIELDS by prompting on stdin.
    A blank answer (just Enter) leaves the field unset — never guessed.
    No-op entirely when not interactive (no TTY, or --non-interactive).
    """
    if not allow_interactive or not sys.stdin.isatty():
        return meta

    values = {f.name: getattr(meta, f.name) for f in fields(meta)}
    any_missing = any(meta.is_field_missing(name) for name in INTERACTIVE_FIELDS)
    if not any_missing:
        return meta

    print("\nSome project metadata isn't set yet (Enter to skip a field):")
    for name in INTERACTIVE_FIELDS:
        if not meta.is_field_missing(name):
            continue
        label = _PROMPTS[name]
        answer = input(f"  {label}: ").strip()
        if answer:
            values[name] = answer
    return ProjectMetadata(**values)


def metadata_from_header(header: FileHeader) -> ProjectMetadata:
    """Convert a detected source-header block into the project-metadata
    shape. Only the fields headers can actually express are populated;
    `date`/`version`/`file_field` aren't [project]-level concerns and
    stay in the FileHeader for callers who want them (e.g. --verbose
    reporting), not here.
    """
    return ProjectMetadata(
        author_name=header.author_name,
        author_email=header.author_email,
        license=header.license,
        description=header.description,
    )


def resolve_metadata(args, root: Path, header: FileHeader | None = None) -> ProjectMetadata:
    """Full precedence chain: CLI > project-local config > global config
    > detected source headers > interactive prompt.
    """
    cli_meta = metadata_from_cli(args)
    config_meta = load_config_metadata(root)
    header_meta = metadata_from_header(header) if header else ProjectMetadata()
    combined = cli_meta.merged_with(config_meta).merged_with(header_meta)
    if not getattr(args, "non_interactive", False):
        combined = prompt_missing(combined, allow_interactive=True)
    return combined


def save_as_global_defaults(meta: ProjectMetadata) -> Path:
    """Persist the resolved core fields to the global config file so
    future projects pick them up automatically. Only ever called when
    the user explicitly passes --save-defaults.
    """
    path = global_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = tomlkit.document()
    defaults = tomlkit.table()
    for name in ("author_name", "author_email", "license"):
        value = getattr(meta, name)
        if value:
            defaults[name] = value
    doc["defaults"] = defaults
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    return path

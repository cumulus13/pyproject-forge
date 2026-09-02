#!/usr/bin/env python3

# File: pyproject-forge/pyproject_forge/toml_writer.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-02 11:35:32
# Description: 
# License: MIT

"""Creates or merges pyproject.toml. Existing files are parsed with
tomlkit and only the sections pyproject-forge owns
([project.scripts], [tool.setuptools.packages], and — only on first
creation — the surrounding skeleton) are touched. Everything else the
user already has in the file is preserved byte-for-byte where possible.
"""

from __future__ import annotations

from pathlib import Path

import tomlkit
from tomlkit import comment, document, nl, table
from tomlkit.exceptions import ParseError

from .exceptions import ConflictingScriptNameError, PyprojectParseError


def _default_project_table(
    project_name: str,
    python_requires: str,
    metadata=None,
) -> tomlkit.TOMLDocument:
    doc = document()

    build_system = table()
    build_system.add("requires", ["setuptools>=68"])
    build_system.add("build-backend", "setuptools.build_meta")
    doc.add("build-system", build_system)
    doc.add(nl())

    project = table()
    project.add("name", project_name)
    project.add("version", "0.1.0")

    description = getattr(metadata, "description", None) if metadata else None
    if description:
        project.add("description", description)
    else:
        project.add(comment("TODO: fill in a real description"))
        project.add("description", "")

    project.add("requires-python", python_requires)

    if metadata is not None:
        if metadata.author_name or metadata.author_email:
            entry = {}
            if metadata.author_name:
                entry["name"] = metadata.author_name
            if metadata.author_email:
                entry["email"] = metadata.author_email
            project.add("authors", [entry])
        if metadata.maintainer_name or metadata.maintainer_email:
            entry = {}
            if metadata.maintainer_name:
                entry["name"] = metadata.maintainer_name
            if metadata.maintainer_email:
                entry["email"] = metadata.maintainer_email
            project.add("maintainers", [entry])
        if metadata.license:
            project.add("license", {"text": metadata.license})
        if metadata.keywords:
            project.add("keywords", metadata.keywords)

    doc.add("project", project)
    doc.add(nl())

    if metadata is not None and (metadata.homepage or metadata.repository):
        urls = table()
        if metadata.homepage:
            urls.add("Homepage", metadata.homepage)
        if metadata.repository:
            urls.add("Repository", metadata.repository)
        doc["project"]["urls"] = urls

    return doc


def load_or_create(
    pyproject_path: Path,
    project_name: str,
    python_requires: str,
    metadata=None,
):
    if pyproject_path.exists():
        try:
            text = pyproject_path.read_text(encoding="utf-8")
            return tomlkit.parse(text), True
        except (ParseError, OSError) as exc:
            raise PyprojectParseError(str(pyproject_path), exc) from exc
    return _default_project_table(project_name, python_requires, metadata), False


def apply_scripts(
    doc,
    entries: dict[str, str],
    packages: list[str],
    package_dirs: dict[str, str] | None = None,
) -> list[str]:
    """Write [project.scripts] and [tool.setuptools] packages/package-dir
    into the TOML document in place. Returns a list of human-readable
    warnings (e.g. about script names that were already present and are
    being overwritten by a *different* target).
    """
    warnings: list[str] = []
    package_dirs = package_dirs or {}

    if "project" not in doc:
        doc["project"] = table()
    project = doc["project"]

    if "scripts" not in project:
        project["scripts"] = table()
    scripts = project["scripts"]

    seen_targets: dict[str, str] = {}
    for name, target in sorted(entries.items()):
        if name in seen_targets and seen_targets[name] != target:
            raise ConflictingScriptNameError(name, seen_targets[name], target)
        seen_targets[name] = target

        if name in scripts and str(scripts[name]) != target:
            warnings.append(
                f"[project.scripts] '{name}' changed: "
                f"{scripts[name]!r} -> {target!r}"
            )
        scripts[name] = target

    if "tool" not in doc:
        doc["tool"] = table(is_super_table=True)
    tool = doc["tool"]
    if "setuptools" not in tool:
        tool["setuptools"] = table()
    setuptools_tbl = tool["setuptools"]

    existing_packages = set(setuptools_tbl.get("packages", []))
    merged_packages = sorted(existing_packages | set(packages))
    setuptools_tbl["packages"] = merged_packages

    if package_dirs:
        # setuptools uses dashed keys under [tool.setuptools]
        # (package-dir, not package_dir) — verified against the
        # setuptools pyproject.toml docs.
        existing_dir_map = dict(setuptools_tbl.get("package-dir", {}))
        for dotted_name, rel_path in package_dirs.items():
            if dotted_name in existing_dir_map and existing_dir_map[dotted_name] != rel_path:
                warnings.append(
                    f"[tool.setuptools.package-dir] '{dotted_name}' changed: "
                    f"{existing_dir_map[dotted_name]!r} -> {rel_path!r}"
                )
            existing_dir_map[dotted_name] = rel_path
        setuptools_tbl["package-dir"] = dict(sorted(existing_dir_map.items()))

    return warnings


def write(doc, pyproject_path: Path) -> None:
    pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

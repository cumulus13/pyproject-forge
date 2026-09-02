#!/usr/bin/env python3

# File: pyproject-forge/tests/test_metadata.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-02 11:34:12
# Description: 
# License: MIT

import os

import tomlkit

from pyproject_forge.cli import run
from pyproject_forge.metadata import (
    ProjectMetadata,
    load_config_metadata,
    metadata_from_cli,
    resolve_metadata,
)


def _touch(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class _Args:
    """Minimal stand-in for argparse.Namespace with just the metadata
    fields resolve_metadata/metadata_from_cli need."""
    def __init__(self, **kwargs):
        defaults = dict(
            author=None, author_email=None, maintainer=None, maintainer_email=None,
            license=None, description=None, keywords=None,
            url_homepage=None, url_repository=None, non_interactive=True,
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


def test_cli_beats_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _touch(
        tmp_path / "xdg" / "pyproject-forge" / "defaults.toml",
        '[defaults]\nauthor_name = "Config Author"\nlicense = "Apache-2.0"\n',
    )
    args = _Args(author="CLI Author")
    meta = resolve_metadata(args, tmp_path)
    assert meta.author_name == "CLI Author"     # CLI wins
    assert meta.license == "Apache-2.0"          # falls back to config


def test_local_config_beats_global_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _touch(
        tmp_path / "xdg" / "pyproject-forge" / "defaults.toml",
        '[defaults]\nauthor_name = "Global Author"\nlicense = "MIT"\n',
    )
    _touch(tmp_path / ".pyprojectforge.toml", '[defaults]\nauthor_name = "Local Author"\n')

    meta = load_config_metadata(tmp_path)
    assert meta.author_name == "Local Author"   # local wins
    assert meta.license == "MIT"                 # only global has this, still used


def test_keywords_comma_split():
    args = _Args(keywords="cli, tools, windows")
    meta = metadata_from_cli(args)
    assert meta.keywords == ["cli", "tools", "windows"]


def test_missing_field_never_guessed():
    meta = ProjectMetadata(author_name="Hadi")
    assert meta.is_field_missing("license") is True
    assert meta.is_field_missing("author_name") is False


def test_metadata_applied_only_on_creation(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _touch(tmp_path / "toolA" / "app.py", "def main():\n    return 0\n")

    run([
        str(tmp_path), "--author", "Hadi Cahyadi",
        "--author-email", "cumulus13@gmail.com", "--license", "MIT",
        "--non-interactive",
    ])
    doc = tomlkit.parse((tmp_path / "pyproject.toml").read_text())
    assert doc["project"]["authors"][0]["name"] == "Hadi Cahyadi"
    assert doc["project"]["license"]["text"] == "MIT"

    # Re-run with DIFFERENT metadata flags — must NOT overwrite, since the
    # file already exists.
    run([
        str(tmp_path), "--author", "Someone Else", "--license", "GPL-3.0",
        "--non-interactive",
    ])
    doc2 = tomlkit.parse((tmp_path / "pyproject.toml").read_text())
    assert doc2["project"]["authors"][0]["name"] == "Hadi Cahyadi"
    assert doc2["project"]["license"]["text"] == "MIT"


def test_non_interactive_never_prompts(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    def _fail_if_called(*a, **kw):
        raise AssertionError("input() should never be called with --non-interactive")

    monkeypatch.setattr("builtins.input", _fail_if_called)
    _touch(tmp_path / "toolA" / "app.py", "def main():\n    return 0\n")
    exit_code = run([str(tmp_path), "--non-interactive"])
    assert exit_code == 0

#!/usr/bin/env python3

# File: pyproject-forge/tests/test_nested_packages.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-02 11:35:32
# Description: 
# License: MIT

import tomlkit

from pyproject_forge.cli import run


def _touch(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_nested_package_gets_dotted_entry_and_package_dir(tmp_path, capsys):
    _touch(tmp_path / "toolA" / "app.py", "def main():\n    return 0\n")
    _touch(tmp_path / "toolA" / "sub" / "inner.py", "def main():\n    return 0\n")

    exit_code = run([
        str(tmp_path), "--allow-nested", "--max-depth", "4", "--non-interactive",
    ])
    assert exit_code == 0

    doc = tomlkit.parse((tmp_path / "pyproject.toml").read_text())
    scripts = doc["project"]["scripts"]

    # Leaf-only name would have been wrong ("sub.__main__:main") — must be
    # fully dotted so the import actually resolves.
    assert scripts["sub"] == "toolA.sub.__main__:main"
    assert scripts["toola"] == "toolA.__main__:main"

    packages = doc["tool"]["setuptools"]["packages"]
    assert "toolA.sub" in packages
    assert "toolA" in packages

    package_dir = doc["tool"]["setuptools"]["package-dir"]
    assert package_dir["toolA.sub"] == "toolA/sub"
    assert package_dir["toolA"] == "toolA"

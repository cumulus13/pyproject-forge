#!/usr/bin/env python3

# File: pyproject-forge/tests/test_integration.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-02 11:34:12
# Description: 
# License: MIT

import tomlkit

from pyproject_forge.cli import run


def _touch(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_end_to_end_generates_scripts_and_stubs(tmp_path, capsys):
    # toolA already has a proper main() in its own file, no __main__.py yet.
    _touch(
        tmp_path / "toolA" / "app.py",
        "def main():\n    print('toolA running')\n    return 0\n",
    )
    # toolB has nothing at all -> should get a stub.
    _touch(tmp_path / "toolB" / "core.py", "def helper():\n    pass\n")
    # toolC already has a complete __main__.py -> must be left untouched.
    _touch(
        tmp_path / "toolC" / "__main__.py",
        "def main():\n    return 0\n\nif __name__ == '__main__':\n    raise SystemExit(main())\n",
    )

    exit_code = run([str(tmp_path), "--python-requires", ">=3.10"])
    assert exit_code == 0

    pyproject = tmp_path / "pyproject.toml"
    assert pyproject.exists()
    doc = tomlkit.parse(pyproject.read_text())

    scripts = doc["project"]["scripts"]
    assert scripts["toola"] == "toolA.__main__:main"
    assert scripts["toolb"] == "toolB.__main__:main"
    assert scripts["toolc"] == "toolC.__main__:main"

    assert (tmp_path / "toolA" / "__main__.py").exists()
    assert (tmp_path / "toolA" / "__init__.py").exists()
    assert "helper" in (tmp_path / "toolB" / "core.py").read_text()
    assert "main" in (tmp_path / "toolB" / "__main__.py").read_text()

    # toolC's original content must be preserved verbatim.
    toolc_main = (tmp_path / "toolC" / "__main__.py").read_text()
    assert toolc_main.count("def main") == 1


def test_dry_run_writes_nothing(tmp_path):
    _touch(tmp_path / "toolA" / "app.py", "def main():\n    return 0\n")
    run([str(tmp_path), "--dry-run"])
    assert not (tmp_path / "pyproject.toml").exists()
    assert not (tmp_path / "toolA" / "__main__.py").exists()


def test_rerun_is_idempotent(tmp_path):
    _touch(tmp_path / "toolA" / "app.py", "def main():\n    return 0\n")
    run([str(tmp_path)])
    first = (tmp_path / "pyproject.toml").read_text()
    run([str(tmp_path)])
    second = (tmp_path / "pyproject.toml").read_text()
    assert first == second


def test_merges_into_existing_pyproject_without_clobbering(tmp_path):
    _touch(
        tmp_path / "pyproject.toml",
        '[project]\nname = "existing-project"\nversion = "2.3.4"\n'
        'dependencies = ["requests"]\n',
    )
    _touch(tmp_path / "toolA" / "app.py", "def main():\n    return 0\n")

    run([str(tmp_path)])

    doc = tomlkit.parse((tmp_path / "pyproject.toml").read_text())
    assert doc["project"]["name"] == "existing-project"
    assert doc["project"]["version"] == "2.3.4"
    assert doc["project"]["dependencies"] == ["requests"]
    assert doc["project"]["scripts"]["toola"] == "toolA.__main__:main"

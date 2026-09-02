from pyproject_forge.scanner import scan_packages


def _touch(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_finds_top_level_script_folders(tmp_path):
    _touch(tmp_path / "toolA" / "app.py", "def main(): pass")
    _touch(tmp_path / "toolB" / "run.py", "def main(): pass")
    _touch(tmp_path / "notes.md", "hi")  # not a .py file, root, ignored

    candidates = scan_packages(tmp_path)
    names = sorted(c.name for c in candidates)
    assert names == ["toolA", "toolB"]


def test_excludes_venv_and_git(tmp_path):
    _touch(tmp_path / ".venv" / "lib" / "x.py", "def main(): pass")
    _touch(tmp_path / ".git" / "hooks" / "y.py", "def main(): pass")
    _touch(tmp_path / "real" / "app.py", "def main(): pass")

    candidates = scan_packages(tmp_path)
    names = [c.name for c in candidates]
    assert names == ["real"]


def test_does_not_descend_into_selected_package_by_default(tmp_path):
    _touch(tmp_path / "toolA" / "app.py", "def main(): pass")
    _touch(tmp_path / "toolA" / "sub" / "inner.py", "def main(): pass")

    candidates = scan_packages(tmp_path)
    assert len(candidates) == 1
    assert candidates[0].name == "toolA"


def test_allow_nested_registers_subfolders_too(tmp_path):
    _touch(tmp_path / "toolA" / "app.py", "def main(): pass")
    _touch(tmp_path / "toolA" / "sub" / "inner.py", "def main(): pass")

    candidates = scan_packages(tmp_path, allow_nested=True, max_depth=4)
    names = sorted(c.rel_path.as_posix() for c in candidates)
    assert names == ["toolA", "toolA/sub"]


def test_respects_max_depth(tmp_path):
    _touch(tmp_path / "a" / "b" / "c" / "deep.py", "def main(): pass")
    candidates = scan_packages(tmp_path, max_depth=2)
    assert candidates == []

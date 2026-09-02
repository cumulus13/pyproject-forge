import os
import stat
import sys

import tomlkit

from pyproject_forge.cli import run


def _touch(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_detected_shebang_propagates_to_generated_main(tmp_path):
    _touch(
        tmp_path / "toolA" / "core.py",
        "#!/usr/bin/env python3\ndef main():\n    return 0\n",
    )
    exit_code = run([str(tmp_path), "--non-interactive"])
    assert exit_code == 0

    generated = (tmp_path / "toolA" / "__main__.py").read_text()
    assert generated.startswith("#!/usr/bin/env python3\n")

    # The exec bit is a POSIX concept — Windows filesystems don't carry
    # it, so chmod() there is a harmless no-op (see the try/except in
    # generator._make_executable_if_shebanged). Only assert it where it
    # actually means something.
    if sys.platform != "win32":
        mode = (tmp_path / "toolA" / "__main__.py").stat().st_mode
        assert mode & stat.S_IXUSR


def test_no_shebang_flag_suppresses_detection(tmp_path):
    _touch(
        tmp_path / "toolA" / "core.py",
        "#!/usr/bin/env python3\ndef main():\n    return 0\n",
    )
    run([str(tmp_path), "--non-interactive", "--no-shebang"])
    generated = (tmp_path / "toolA" / "__main__.py").read_text()
    assert not generated.startswith("#!")


def test_forced_shebang_overrides_detected(tmp_path):
    _touch(
        tmp_path / "toolA" / "core.py",
        "#!/usr/bin/env python3\ndef main():\n    return 0\n",
    )
    run([str(tmp_path), "--non-interactive", "--shebang", "#!/usr/bin/env python3.12"])
    generated = (tmp_path / "toolA" / "__main__.py").read_text()
    assert generated.startswith("#!/usr/bin/env python3.12\n")


def test_no_shebang_anywhere_stays_shebang_free(tmp_path):
    _touch(tmp_path / "toolA" / "core.py", "def main():\n    return 0\n")
    run([str(tmp_path), "--non-interactive"])
    generated = (tmp_path / "toolA" / "__main__.py").read_text()
    assert not generated.startswith("#!")


def test_header_metadata_fills_project_when_no_cli_or_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _touch(
        tmp_path / "toolA" / "core.py",
        "#!/usr/bin/env python3\n"
        "# Author: Hadi Cahyadi <cumulus13@gmail.com>\n"
        "# License: MIT\n"
        "# Description: Sample tool\n"
        "def main():\n    return 0\n",
    )
    run([str(tmp_path), "--non-interactive"])
    doc = tomlkit.parse((tmp_path / "pyproject.toml").read_text())
    assert doc["project"]["authors"][0]["name"] == "Hadi Cahyadi"
    assert doc["project"]["authors"][0]["email"] == "cumulus13@gmail.com"
    assert doc["project"]["license"]["text"] == "MIT"
    assert doc["project"]["description"] == "Sample tool"


def test_cli_flag_still_beats_header(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _touch(
        tmp_path / "toolA" / "core.py",
        "# Author: Header Author\n# License: MIT\ndef main():\n    return 0\n",
    )
    run([str(tmp_path), "--non-interactive", "--author", "CLI Author"])
    doc = tomlkit.parse((tmp_path / "pyproject.toml").read_text())
    assert doc["project"]["authors"][0]["name"] == "CLI Author"
    assert doc["project"]["license"]["text"] == "MIT"   # still filled from header


def test_file_field_mismatch_is_flagged(tmp_path, capsys):
    _touch(
        tmp_path / "toolA" / "core.py",
        "# File: wrong/path.py\ndef main():\n    return 0\n",
    )
    run([str(tmp_path), "--non-interactive", "--verbose"])
    captured = capsys.readouterr()
    assert "wrong/path.py" in captured.out
    assert "toolA/core.py" in captured.out

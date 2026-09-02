from pyproject_forge.detector import find_entry_candidates, rank_candidates


def test_finds_main_function(tmp_path):
    f = tmp_path / "app.py"
    f.write_text("def helper():\n    pass\n\ndef main():\n    return 0\n")
    candidates = find_entry_candidates(f)
    names = [c.func_name for c in candidates]
    assert "main" in names
    assert "helper" not in names


def test_ignores_private_functions(tmp_path):
    f = tmp_path / "app.py"
    f.write_text("def _main():\n    pass\n")
    assert find_entry_candidates(f) == []


def test_marker_comment_wins_ranking(tmp_path):
    f = tmp_path / "app.py"
    f.write_text(
        "def run():\n    pass\n\n"
        "# pyproject-forge: entry\n"
        "def start():\n    pass\n"
    )
    ranked = rank_candidates(find_entry_candidates(f))
    assert ranked[0].func_name == "start"
    assert ranked[0].is_marked is True


def test_preferred_name_ranking(tmp_path):
    f = tmp_path / "app.py"
    f.write_text("def run():\n    pass\n\ndef main():\n    pass\n")
    ranked = rank_candidates(find_entry_candidates(f))
    assert ranked[0].func_name == "main"


def test_syntax_error_file_returns_empty(tmp_path):
    f = tmp_path / "broken.py"
    f.write_text("def main(:\n    pass\n")
    assert find_entry_candidates(f) == []

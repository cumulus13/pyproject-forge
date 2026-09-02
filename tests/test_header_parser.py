#!/usr/bin/env python3

# File: pyproject-forge/tests/test_header_parser.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-02 11:35:32
# Description: 
# License: MIT

        "\n"
        "def main():\n"
        "    return 0\n"
    )
    header = parse_header(f)
    assert header.shebang == "#!/usr/bin/env python3"
    assert header.author_name == "Hadi Cahyadi"
    assert header.author_email == "cumulus13@gmail.com"
    assert header.license == "MIT"
    assert header.description == "Fetches BMKG weather data"
    assert header.date == "2026-09-01"
    assert header.file_field == "bmkg/bmkg.py"


def test_author_without_email(tmp_path):
    f = tmp_path / "app.py"
    f.write_text("# Author: Jane Doe\n\ndef main():\n    pass\n")
    header = parse_header(f)
    assert header.author_name == "Jane Doe"
    assert header.author_email is None


def test_no_shebang_no_header(tmp_path):
    f = tmp_path / "plain.py"
    f.write_text("def main():\n    pass\n")
    header = parse_header(f)
    assert header.shebang is None
    assert header.author_name is None


def test_stops_at_first_code_line(tmp_path):
    f = tmp_path / "app.py"
    f.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "# License: MIT\n"  # after code — must NOT be picked up
        "\n"
    )
    header = parse_header(f)
    assert header.shebang == "#!/usr/bin/env python3"
    assert header.license is None


def test_scan_headers_first_found_wins(tmp_path):
    f1 = tmp_path / "a.py"
    f1.write_text("# Author: First Author\n")
    f2 = tmp_path / "b.py"
    f2.write_text("# Author: Second Author\n# License: Apache-2.0\n")
    agg = scan_headers([f1, f2])
    assert agg.author_name == "First Author"    # f1 found first, wins
    assert agg.license == "Apache-2.0"           # only f2 has it


def test_detect_shebang_falls_back_to_default(tmp_path):
    f = tmp_path / "plain.py"
    f.write_text("def main():\n    pass\n")
    assert detect_shebang([f], default=None) is None
    assert detect_shebang([f], default="#!/usr/bin/env python3") == "#!/usr/bin/env python3"


def test_detect_shebang_finds_first_declared(tmp_path):
    f1 = tmp_path / "a.py"
    f1.write_text("def main():\n    pass\n")
    f2 = tmp_path / "b.py"
    f2.write_text("#!/usr/bin/env python3\ndef main():\n    pass\n")
    assert detect_shebang([f1, f2], default=None) == "#!/usr/bin/env python3"

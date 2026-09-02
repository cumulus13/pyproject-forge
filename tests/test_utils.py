#!/usr/bin/env python3

# File: pyproject-forge/tests/test_utils.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-02 11:35:32
# Description: 
# License: MIT

from pyproject_forge.utils import to_console_name, to_module_name


def test_to_console_name_basic():
    assert to_console_name("My_Cool Tool") == "my-cool-tool"
    assert to_console_name("jfcli") == "jfcli"
    assert to_console_name("  weird--name__") == "weird-name"


def test_to_module_name_handles_digits_and_keywords():
    assert to_module_name("2fast") == "_2fast"
    assert to_module_name("class") == "class_"
    assert to_module_name("My-Tool") == "My_Tool"
    assert to_module_name("") == "pkg"

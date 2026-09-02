#!/usr/bin/env python3

# File: pyproject-forge/pyproject_forge/exceptions.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-02 11:35:32
# Description: 
# License: MIT

"""Exceptions used to make failures explicit rather than silently guessed."""


class ForgeError(Exception):
    """Base class for all pyproject-forge errors."""


class AmbiguousEntryPointError(ForgeError):
    """Raised when a package has more than one plausible entry function
    and the tool refuses to guess which one is the console entry point.
    """

    def __init__(self, package_path: str, candidates: list[str]):
        self.package_path = package_path
        self.candidates = candidates
        super().__init__(
            f"Ambiguous entry point in {package_path!r}: found candidates "
            f"{candidates!r}. Refusing to guess — pass --entry-func or "
            f"annotate one function with '# pyproject-forge: entry'."
        )


class NoEntryPointError(ForgeError):
    """Raised (in strict mode) when a package has no callable that looks
    like a main/usage entry point and --no-stub was requested, so the tool
    cannot proceed without guessing.
    """

    def __init__(self, package_path: str):
        self.package_path = package_path
        super().__init__(
            f"No entry point found in {package_path!r} and stub generation "
            f"is disabled (--no-stub). Nothing was written."
        )


class ConflictingScriptNameError(ForgeError):
    """Raised when two different packages would produce the same console
    script name, which would silently overwrite one entry in pyproject.toml.
    """

    def __init__(self, name: str, existing: str, new: str):
        self.name = name
        self.existing = existing
        self.new = new
        super().__init__(
            f"Console script name {name!r} is claimed by both "
            f"{existing!r} and {new!r}. Rename one package or pass "
            f"--name-template to disambiguate."
        )


class ConfigParseError(ForgeError):
    """Raised when a defaults config file (global or project-local)
    cannot be parsed. The tool never silently ignores a broken config —
    it stops and tells you exactly which file and why.
    """

    def __init__(self, path: str, original: Exception):
        self.path = path
        self.original = original
        super().__init__(
            f"Could not parse config file {path!r}: {original!r}. "
            f"Fix the TOML or remove the file."
        )


class PyprojectParseError(ForgeError):
    """Raised when an existing pyproject.toml cannot be parsed. The tool
    never overwrites a file it could not understand.
    """

    def __init__(self, path: str, original: Exception):
        self.path = path
        self.original = original
        super().__init__(
            f"Could not parse existing {path!r}: {original!r}. "
            f"Refusing to touch it — fix the TOML or move it aside."
        )

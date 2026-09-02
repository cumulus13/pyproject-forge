#!/usr/bin/env python3

# File: pyproject-forge/pyproject_forge/cli.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-02 11:34:12
# Description: 
# License: MIT

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .exceptions import ForgeError
from .generator import Action, PackageResult, process_candidate
from .header_parser import detect_shebang, scan_headers
from .metadata import resolve_metadata, save_as_global_defaults
from .scanner import scan_packages
from .toml_writer import apply_scripts, load_or_create, write
from .utils import to_console_name

ACTIONS_THAT_MODIFY_DISK = {
    Action.CREATED_INIT,
    Action.CREATED_MAIN_DELEGATE,
    Action.CREATED_MAIN_STUB,
    Action.ADDED_GUARD,
    Action.RENAMED_DIR,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pyproject-forge",
        description=(
            "Scan a working directory, ensure every script folder has a "
            "console-usable __main__.py, and generate/merge pyproject.toml "
            "with [project.scripts] entries."
        ),
    )
    p.add_argument(
        "root", nargs="?", default=".",
        help="working directory to scan (default: current directory)",
    )
    p.add_argument(
        "--max-depth", type=int, default=3,
        help="how many directory levels deep to scan (default: 3)",
    )
    p.add_argument(
        "--allow-nested", action="store_true",
        help="also register subfolders of an already-selected package as "
             "separate console scripts (default: off)",
    )
    p.add_argument(
        "--include-root", action="store_true",
        help="treat loose .py files directly in the root directory as a "
             "package too (default: off)",
    )
    p.add_argument(
        "--exclude", action="append", default=[],
        metavar="DIRNAME",
        help="additional directory name to exclude (repeatable)",
    )
    p.add_argument(
        "--no-stub", action="store_true",
        help="never auto-generate a stub __main__.py; fail loudly instead "
             "when no entry point is found",
    )
    p.add_argument(
        "--auto-rename", action="store_true",
        help="rename folders that are not valid Python module names "
             "instead of skipping them (destructive: renames on disk)",
    )
    p.add_argument(
        "--name-template", default="{name}",
        help="template for console script names, e.g. 'mytool-{name}' "
             "(default: '{name}')",
    )
    p.add_argument(
        "--python-requires", default=">=3.9",
        help="requires-python value used only when creating a new "
             "pyproject.toml (default: >=3.9)",
    )
    p.add_argument(
        "--project-name", default=None,
        help="[project].name used only when creating a new pyproject.toml "
             "(default: the root directory's name)",
    )
    meta_group = p.add_argument_group(
        "metadata (only applied when creating a NEW pyproject.toml; "
        "an existing file's metadata is never touched)"
    )
    meta_group.add_argument("--author", default=None, help="author name")
    meta_group.add_argument("--author-email", default=None, help="author email")
    meta_group.add_argument("--maintainer", default=None, help="maintainer name")
    meta_group.add_argument("--maintainer-email", default=None, help="maintainer email")
    meta_group.add_argument("--license", default=None, help="license, e.g. MIT")
    meta_group.add_argument("--description", default=None, help="project description")
    meta_group.add_argument(
        "--keywords", default=None, help="comma-separated keywords"
    )
    meta_group.add_argument("--url-homepage", default=None, help="project homepage URL")
    meta_group.add_argument("--url-repository", default=None, help="repository URL")
    meta_group.add_argument(
        "--non-interactive", action="store_true",
        help="never prompt for missing metadata; leave unresolved fields "
             "out of pyproject.toml (recommended for CI)",
    )
    meta_group.add_argument(
        "--save-defaults", action="store_true",
        help="after resolving, save author/email/license to the global "
             "config (~/.config/pyproject-forge/defaults.toml) for reuse "
             "in future projects",
    )
    shebang_group = p.add_argument_group("shebang handling for generated __main__.py")
    shebang_group.add_argument(
        "--shebang", default=None, metavar="LINE",
        help="force this exact shebang line on every generated __main__.py "
             "(e.g. --shebang '#!/usr/bin/env python3')",
    )
    shebang_group.add_argument(
        "--no-shebang", action="store_true",
        help="never add a shebang to generated files, even if detected "
             "elsewhere in the project",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="show what would happen; write nothing to disk",
    )
    p.add_argument(
        "-v", "--verbose", action="store_true",
        help="print per-package detail, not just the summary",
    )
    return p


def _print_tree(root: Path, results: list[PackageResult]) -> None:
    print("\nFile tree (script packages only):")
    print(f"{root.name}/")
    for r in sorted(results, key=lambda r: r.candidate.rel_path):
        indent = "    " * len(r.candidate.rel_path.parts[:-1])
        print(f"{indent}├── {r.candidate.rel_path}/")
        sub_indent = indent + "    "
        print(f"{sub_indent}├── __init__.py")
        main_marker = "" if r.entry_target else "  (missing/skipped)"
        print(f"{sub_indent}└── __main__.py{main_marker}")


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()

    if not root.is_dir():
        print(f"ERROR: not a directory: {root}", file=sys.stderr)
        return 2

    candidates = scan_packages(
        root,
        max_depth=args.max_depth,
        extra_excludes=frozenset(args.exclude),
        allow_nested=args.allow_nested,
        include_root=args.include_root,
    )

    if not candidates:
        print(f"No script packages found under {root} "
              f"(no folder with a direct .py file within --max-depth={args.max_depth}).")
        return 0

    used_names: dict[str, str] = {}
    results: list[PackageResult] = []
    errors: list[str] = []

    # Project-wide shebang convention (if any): only used as a fallback
    # for folders that have no shebang of their own — a folder's own
    # files always take priority over the project-wide default.
    all_py_files = [f for c in candidates for f in c.py_files]
    project_shebang = None if args.no_shebang else detect_shebang(all_py_files, default=None)
    detected_header = scan_headers(all_py_files)

    for candidate in candidates:
        console_name = args.name_template.format(name=to_console_name(candidate.name))
        try:
            result = process_candidate(
                candidate,
                console_name,
                root,
                allow_stub=not args.no_stub,
                auto_rename=args.auto_rename,
                dry_run=args.dry_run,
                forced_shebang=args.shebang,
                disable_shebang=args.no_shebang,
                project_shebang=project_shebang,
            )
        except ForgeError as exc:
            errors.append(f"{candidate.path}: {exc}")
            continue

        if result.entry_target and console_name in used_names:
            errors.append(
                f"Console script name collision: '{console_name}' wanted by "
                f"both {used_names[console_name]} and {candidate.path}. "
                f"Use --name-template to disambiguate."
            )
            continue
        if result.entry_target:
            used_names[console_name] = str(candidate.path)
        results.append(result)

    entries = {r.console_name: r.entry_target for r in results if r.entry_target}
    packages = [r.dotted_module_name for r in results if r.entry_target]
    package_dirs = {
        r.dotted_module_name: r.rel_path_posix for r in results if r.entry_target
    }

    pyproject_path = root / "pyproject.toml"
    project_name = args.project_name or to_console_name(root.name)

    metadata = None
    if not pyproject_path.exists():
        # Metadata (author/license/description/...) is only ever resolved
        # and applied when we're about to CREATE a new pyproject.toml.
        # An existing file's [project] table is never touched — same
        # "don't clobber what you didn't create" rule as [project.scripts].
        try:
            metadata = resolve_metadata(args, root, header=detected_header)
        except ForgeError as exc:
            print(f"FATAL: {exc}", file=sys.stderr)
            return 1
        if args.save_defaults and not args.dry_run:
            saved_path = save_as_global_defaults(metadata)
            print(f"Saved author/email/license to {saved_path}")

    if not args.dry_run:
        try:
            doc, existed = load_or_create(
                pyproject_path, project_name, args.python_requires, metadata
            )
            warnings = apply_scripts(doc, entries, packages, package_dirs)
            write(doc, pyproject_path)
        except ForgeError as exc:
            print(f"FATAL: {exc}", file=sys.stderr)
            return 1
    else:
        warnings = []
        existed = pyproject_path.exists()

    # ---- Report -----------------------------------------------------
    print(f"Scanned {root}")
    print(f"  script packages found : {len(candidates)}")
    print(f"  console scripts ready : {len(entries)}")
    print(f"  pyproject.toml        : {'merged' if existed else 'created'}"
          f"{' (dry-run, not written)' if args.dry_run else ''}")

    if args.verbose:
        print("\nPer-package detail:")
        for r in results:
            action_str = ", ".join(a.value for a in r.actions) or "unchanged"
            target = r.entry_target or "SKIPPED"
            print(f"  {r.candidate.rel_path}: [{action_str}] -> {target}")
            if r.detail:
                print(f"      {r.detail}")
            for w in r.warnings:
                print(f"      WARNING: {w}")

    all_package_warnings = [w for r in results for w in r.warnings]
    if warnings or all_package_warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  - {w}")
        for w in all_package_warnings:
            print(f"  - {w}")

    skipped = [r for r in results if not r.entry_target]
    if skipped:
        print(f"\n{len(skipped)} package(s) skipped (no console script generated):")
        for r in skipped:
            print(f"  - {r.candidate.rel_path}: {r.detail}")

    if errors:
        print(f"\n{len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)

    if entries:
        print("\n[project.scripts] entries:")
        for name, target in sorted(entries.items()):
            print(f"  {name} = \"{target}\"")

    _print_tree(root, results)

    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(argv)
    except ForgeError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

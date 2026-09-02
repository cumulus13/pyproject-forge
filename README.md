# pyproject-forge

Scan a working directory, make sure every "script folder" has a
console-usable `__main__.py`, and generate/merge a `pyproject.toml`
with `[project.scripts]` entries — one console command per folder.

## Install

```bash
pip install -e .
```

This registers the `pyproject-forge` command (and `python -m pyproject_forge`).

## Usage

```bash
pyproject-forge /path/to/workdir --verbose
```

Run with no args to scan the current directory. Nothing is written until
you run it for real — use `--dry-run` first to preview.

## What it does, per folder

For every folder under the root that directly contains a `.py` file:

1. Ensures `__init__.py` exists (creates an empty one if missing).
2. Looks for an entry point, in this order:
   - An existing `__main__.py` that already defines `main`, `cli`, `run`,
     `app`, or `usage` — left alone, just gets a `if __name__ ==
     "__main__":` guard appended if it's missing.
   - No `__main__.py`, but another file in the folder defines one of
     those functions — a `__main__.py` is generated that imports and
     re-exports it.
   - Nothing found — a documented **stub** `__main__.py` is generated
     (argparse skeleton, clearly marked `TODO`), unless `--no-stub`.
3. Adds `folder-name = "module.__main__:func"` to `[project.scripts]`
   in `pyproject.toml`, and the module to `[tool.setuptools].packages`.

An existing `pyproject.toml` is parsed and **merged**, not overwritten —
your `dependencies`, `version`, custom tables, etc. are preserved.

## Key flags

| Flag | Purpose |
|---|---|
| `--dry-run` | Preview everything; write nothing to disk. |
| `-v, --verbose` | Print per-package action detail, not just the summary. |
| `--max-depth N` | How many directory levels deep to scan (default 3). |
| `--allow-nested` | Also register subfolders of an already-selected package as separate scripts (off by default, to avoid double-registering internals). |
| `--include-root` | Treat loose `.py` files directly in the root dir as a package too. |
| `--exclude DIRNAME` | Extra directory name to skip (repeatable). Common junk (`.git`, `.venv`, `__pycache__`, `build`, `dist`, ...) is already excluded. |
| `--no-stub` | Fail loudly instead of generating a stub when no entry point is found — use this once you want the tool to stop guessing for you. |
| `--auto-rename` | Rename folders that aren't valid Python identifiers instead of skipping them (destructive — off by default). |
| `--name-template '{name}'` | Template for console script names, e.g. `--name-template 'acme-{name}'`. |
| `--python-requires` / `--project-name` | Only used the first time a `pyproject.toml` is created. |

## Resolving ambiguity without guessing

If a folder has more than one function that looks like an entry point
(e.g. both `run()` and `main()` in different files, no clear winner),
the tool **refuses to guess** and reports the folder as an error instead
of silently picking one. Two ways to resolve it explicitly:

- Rename so it matches the preferred order: `main` > `cli` > `run` >
  `app` > `usage`.
- Or mark the one you want with a comment directly above it:

  ```python
  # pyproject-forge: entry
  def start():
      ...
  ```

Folder names that aren't valid Python identifiers (spaces, leading
digits, dashes) are also **flagged and skipped**, never silently
mangled — pass `--auto-rename` if you want the tool to fix them for you.

## Metadata (author, license, description, etc.)

`[project]` metadata is resolved from three sources, in this precedence
(highest wins), and is **only ever written when creating a brand-new
`pyproject.toml`** — an existing file's metadata is never touched, same
rule as `[project.scripts]`:

1. **CLI flags** — `--author`, `--author-email`, `--maintainer`,
   `--maintainer-email`, `--license`, `--description`, `--keywords
   "a,b,c"`, `--url-homepage`, `--url-repository`.
2. **Project-local config** — `<root>/.pyprojectforge.toml`:
   ```toml
   [defaults]
   author_name = "Hadi Cahyadi"
   author_email = "cumulus13@gmail.com"
   license = "MIT"
   ```
3. **Global config** — `~/.config/pyproject-forge/defaults.toml` (or
   `$XDG_CONFIG_HOME/pyproject-forge/defaults.toml`), same format. Set
   this once and every new project you scan picks it up automatically.
   Pass `--save-defaults` to write the resolved author/email/license
   here after a run, so you only ever type them once.
4. **Interactive prompt** — if `author_name`, `author_email`,
   `license`, or `description` are still missing after the above, and
   you're at a real terminal, the tool asks (Enter to skip any field).
   Pass `--non-interactive` to disable this entirely (recommended in
   CI) — unresolved fields are then simply left out of the file, never
   guessed.

Any field still unset after all four steps is omitted from
`[project]` — no placeholders, no invented values.

## Shebang and header-comment detection

Generated `__main__.py` files pick up a shebang the same way metadata
does — detected from your existing code, never invented from nothing:

- If any `.py` file **in the same folder** already has a shebang
  (`#!/usr/bin/env python3`), it's reused for the generated file.
- Otherwise, if any file **anywhere in the scanned project** has one,
  that becomes the fallback.
- If nothing in the project uses a shebang, generated files get none
  either — the tool never adds a convention that isn't already yours.
- `--shebang '#!/usr/bin/env python3.12'` forces an exact line on every
  generated file; `--no-shebang` disables detection entirely.
- Generated files with a shebang are also marked executable (`chmod
  +x`) on POSIX, best-effort (never fails the run if it can't).

Structured header comments are also detected and feed into the
metadata precedence chain (below explicit CLI/config, above the
interactive prompt) — `# Author:`, `# License:`, `# Description:`,
`# Date:`:

```python
#!/usr/bin/env python3
# File: bmkg/bmkg.py
# Author: Hadi Cahyadi <cumulus13@gmail.com>
# Date: 2026-09-01
# Description: Fetch BMKG weather/earthquake data
# License: MIT
```

If a source file declares `# File: <path>` and that path doesn't match
where the file actually is, it's flagged as a warning (`--verbose`
shows it) rather than silently ignored — usually means the file got
moved or renamed after the comment was written.

**One real limitation, not glossed over:** a generated file that
*delegates* to your existing code (`from .core import main as main`)
uses a relative import, so while the pip-installed console command and
`python -m yourpackage` both work correctly, running the file directly
as `./yourpackage/__main__.py` does **not** — Python's relative-import
rules forbid that regardless of the shebang or exec bit. This is
inherent to any package using relative imports, not specific to this
tool. Only the plain **stub** case (no existing code to delegate to)
supports true direct execution. If you need direct-execution to always
work, keep your entry logic in `__main__.py` itself rather than a
sibling file.



When a package is nested inside another selected package (e.g.
`toolA/sub/`), the generated entry point and `[tool.setuptools]` config
use the full dotted path (`toolA.sub`, not just `sub`), and an explicit
`[tool.setuptools.package-dir]` mapping is written for every package so
the physical folder always resolves correctly regardless of how deep it
sits in the tree.



```
pyproject_forge/
├── __init__.py
├── __main__.py       # python -m pyproject_forge
├── cli.py            # argparse + orchestration + reporting
├── scanner.py         # walks the tree, finds candidate folders
├── detector.py         # AST-based main()/cli()/run() detection (no imports/exec)
├── generator.py         # writes __init__.py / __main__.py, resolves entry targets
├── toml_writer.py         # tomlkit-based create/merge of pyproject.toml
├── exceptions.py         # explicit, non-silent failure modes
└── utils.py              # name sanitizing (kebab-case console name, valid module name)
tests/
├── test_utils.py
├── test_detector.py
├── test_scanner.py
└── test_integration.py   # full run() pipeline, incl. idempotency + merge-safety
```

## Tests

```bash
pytest tests/ -v
```

16/16 passing, including an idempotency check (running twice produces a
byte-identical `pyproject.toml`) and a merge-safety check (an existing
`pyproject.toml`'s `name`, `version`, and `dependencies` survive a scan
untouched).

## 👤 Author
        
[Hadi Cahyadi](mailto:cumulus13@gmail.com)
    

[![Buy Me a Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/cumulus13)

[![Donate via Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/cumulus13)
 
[Support me on Patreon](https://www.patreon.com/cumulus13)
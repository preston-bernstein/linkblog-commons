# Tasks: Core LinkPost Record, Hugo Renderer, and Feed Generator

Generated from: docs/core-record-render-feed/ on 2026-08-15

## Status legend
- [ ] pending
- [>] in progress
- [x] done
- [!] blocked

## Tasks

### Task 1: Install test and development dependencies
**Status**: [x] done
**Files**: none (installs to environment)
**Test**: `pip install -e ".[test,dev]"` succeeds; `pytest --version` returns a valid version.
**Depends on**: none
**Parallelizable**: No
**Notes**: System Python is Homebrew-managed (PEP 668) — created `.venv/` (matches feed-commons's own `.gitignore` convention) and installed there. All subsequent test/lint commands use `.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/python`, not bare `pytest`/`python`. feedgen 1.0.0 confirmed installed (matches the version the spec-challenge review verified against).

### Task 2: Create error types module
**Status**: [x] done
**Files**: `src/linkblog_commons/errors.py`
**Test**: Import module, instantiate `LinkBlogError("missing_fields", fields=["url"])`, verify `.code`/`.fields`.
**Depends on**: none
**Parallelizable**: No
**Notes**:

### Task 3: Create LinkPost record module
**Status**: [x] done
**Files**: `src/linkblog_commons/record.py`
**Test**: Construct valid/invalid records; verify presence, timestamp/tzinfo, and tags-coercion validation in `__post_init__`.
**Depends on**: Task 2
**Parallelizable**: No
**Notes**:

### Task 4: Create and verify LinkPost record tests
**Status**: [x] done
**Files**: `tests/test_record.py`
**Test**: `pytest tests/test_record.py -v` — all pass, including `comment=""`, invalid timestamp, tz-naive timestamp, and list-to-tuple tags coercion cases.
**Depends on**: Task 1, Task 3
**Parallelizable**: Yes (with Task 5, Task 6)
**Notes**: 10/11 tests pass; found 2 real bugs in record.py's from_dict (out of this task's file scope) — (1) dict-merge happens outside the try/except so a non-dict input leaks a raw TypeError instead of invalid_json, (2) url/published entirely absent from input dict (vs present-but-empty) causes cls(**merged) to raise a missing-arg TypeError before __post_init__ runs, getting remapped to invalid_json instead of the correct missing_fields. Escalated to a scoped fix task against record.py.

### Task 5: Create Hugo renderer module
**Status**: [x] done
**Files**: `src/linkblog_commons/render.py`
**Test**: `hugo_render()` writes one deterministic `.md` file (hash of `(url, published)`), front matter has `title`(=url)/`url`/`published`/`tags` correctly quoted/escaped, missing `content_dir` raises `io_error`.
**Depends on**: Task 3
**Parallelizable**: Yes (with Task 4, Task 6)
**Notes**:

### Task 6: Create feed generator module
**Status**: [x] done
**Files**: `src/linkblog_commons/feed.py`
**Test**: `generate_feed()` builds Atom-only feed, one entry per record (title=url, includes comment), deterministic `updated`, empty-list input succeeds.
**Depends on**: Task 3
**Parallelizable**: Yes (with Task 4, Task 5)
**Notes**: Fixed an undocumented determinism bug beyond the original spec text — feedgen's per-Entry `updated` field defaults to `datetime.now()` unless set explicitly; now set to each entry's `published` value.

### Task 7: Create and verify renderer tests
**Status**: [x] done
**Files**: `tests/test_render.py`
**Test**: `pytest tests/test_render.py -v` — all pass, including same-record-twice and same-(url,published)-different-record overwrite cases.
**Depends on**: Task 5
**Parallelizable**: Yes (with Task 8)
**Notes**:

### Task 8: Create and verify feed generator tests
**Status**: [x] done
**Files**: `tests/test_feed.py`
**Test**: `pytest tests/test_feed.py -v` — all pass, including `comment=""`, comment-in-entry assertion, and empty-records-list cases.
**Depends on**: Task 6
**Parallelizable**: Yes (with Task 7)
**Notes**:

### Task 8a: Create CLI module — Part A (argparse + render subcommand)
**Status**: [x] done
**Files**: `src/linkblog_commons/cli.py` (partial)
**Test**: `main(["render", ...])` in-process succeeds and invokes `hugo_render()` correctly.
**Depends on**: Task 3, Task 5
**Parallelizable**: No
**Notes**:

### Task 8b: Create CLI module — Part B (feed subcommand, JSON envelope, error mapping, entry point)
**Status**: [x] done
**Files**: `src/linkblog_commons/cli.py` (completed), `src/linkblog_commons/__main__.py`
**Test**: `main()` in-process for both subcommands returns correct JSON envelope (with `schema_version`); `python -m linkblog_commons --help` exits 0.
**Depends on**: Task 3, Task 6, Task 8a
**Parallelizable**: No
**Notes**:

### Task 9: Update public API exports
**Status**: [x] done
**Files**: `src/linkblog_commons/__init__.py`
**Test**: `python -c "from linkblog_commons import LinkPost, hugo_render, generate_feed"` succeeds.
**Depends on**: Task 3, Task 5, Task 6
**Parallelizable**: Yes
**Notes**:

### Task 10: Create and verify CLI tests
**Status**: [x] done
**Files**: `tests/test_cli.py`
**Test**: `pytest tests/test_cli.py -v` — all pass, including subprocess byte-for-byte parity and `feed --input -` stdin case.
**Depends on**: Task 8a, Task 8b
**Parallelizable**: No
**Notes**:

### Task 11: Run full test suite with linting and no network
**Status**: [x] done
**Files**: `pyproject.toml` (added `pytest-socket` to test extras, `addopts = "--disable-socket"`), `tests/test_render.py` (ruff C408 fix), `src/linkblog_commons/cli.py` (documented `# noqa: BLE001` on the intentional catch-all)
**Test**: `ruff check .` clean (9 auto-fixed, 2 fixed directly, 1 documented suppression); `pytest tests/ -v --tb=short` — 32/32 pass with `--disable-socket` actually enforcing no real network access, not just prose.
**Depends on**: Task 4, Task 7, Task 8, Task 10
**Parallelizable**: No
**Notes**: Also created `.venv/` (Task 1) since system Python is Homebrew-managed and blocks global pip installs — matches feed-commons's own `.gitignore` convention.

## Blocked / open
(populated during implementation)

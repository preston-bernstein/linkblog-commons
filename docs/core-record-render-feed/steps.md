# Steps: Core LinkPost Record, Hugo Renderer, and Feed Generator

## Prerequisites
The repo skeleton and `pyproject.toml` (including `feedgen>=1.0.0,<2`) are already in place. No external access or prior features required. Test dependencies will be installed in Step 1.

## Implementation steps

### Step 1: Install test and development dependencies
**What**: Run `pip install -e ".[test,dev]"` to install the package in editable mode with test and development dependencies, enabling `pytest` and other tools for all subsequent test steps.
**Files**: none (installs to environment)
**Test**: Verify `pip install` succeeds and `pytest --version` returns a valid version.
**Depends on**: none
**Parallelizable**: No

### Step 2: Create error types module
**What**: Define `LinkBlogError` exception class and `LinkBlogErrorCode` type literal for consistent error handling across all submodules.
**Files**: `src/linkblog_commons/errors.py`
**Test**: Import the module and instantiate a `LinkBlogError("missing_fields", fields=["url"])` — verify `.code` and `.fields` attributes are set correctly.
**Depends on**: none
**Parallelizable**: No

### Step 3: Create LinkPost record module
**What**: Implement the frozen `LinkPost` dataclass with `__post_init__` validation, `from_dict()` classmethod for JSON coercion, and immutable tuple storage for `tags`.
**Files**: `src/linkblog_commons/record.py`
**Test**: Construct valid records with all combinations of required/optional fields; verify missing `url` or `published` raises `LinkBlogError("missing_fields", fields=[...])` with correct field names; verify whitespace-only values are treated as missing.
**Depends on**: Step 2
**Parallelizable**: No

### Step 4: Create and verify LinkPost record tests
**What**: Write comprehensive unit tests for record construction, validation, and `from_dict()` coercion, including edge cases (empty tags, empty comment, whitespace fields). Include explicit test cases for: (1) a LinkPost with `comment=""` (a legal record) to verify the implementation derives feed/front-matter title from `url`, not `comment`; (2) an unparseable `published` string raises `LinkBlogError("invalid_timestamp")` at construction; (3) a parseable but timezone-naive `published` string (e.g. `"2026-08-15T10:00:00"`, no offset) also raises `LinkBlogError("invalid_timestamp")` at construction — this is the case that would otherwise crash later, deep inside `feedgen`, if not caught here; (4) `tags` passed as a `list` via direct keyword construction (not `from_dict`) is coerced to a `tuple` in `__post_init__`, same as the `from_dict` path.
**Files**: `tests/test_record.py`
**Test**: Run `pytest tests/test_record.py -v` — all tests pass.
**Depends on**: Steps 1, 3
**Parallelizable**: Yes (with Steps 5 and 6)

### Step 5: Create Hugo renderer module
**What**: Implement `hugo_render(record: LinkPost, content_dir: str | Path) -> Path`, with deterministic filename derivation from `sha256((url, published))` (the pair, not `url` alone — see plan.md Risk Area 4), date-prefixed for chronological sorting; `content_dir` must already exist (raise `LinkBlogError("io_error")` if not — no auto-mkdir); hand-rolled YAML front matter with `title` (= `record.url`, per plan.md's title-source decision), `url`, `published`, `tags`, using the explicit double-quote + backslash-escape rule from plan.md's Technology choices (raise `LinkBlogError("io_error")` on an unescapable raw newline).
**Files**: `src/linkblog_commons/render.py`
**Test**: Call `hugo_render()` with a test record and a temp directory; verify exactly one `.md` file is written, filename is deterministic (same record → same filename both times) and derived from `(url, published)` together (two records with the same `url` but different `published` get different filenames), front matter contains `title`/`url`/`published`/`tags` in YAML format with correct quoting/escaping, and body contains the comment unchanged. Verify calling with a non-existent `content_dir` raises `LinkBlogError("io_error")` rather than creating it.
**Depends on**: Step 3
**Parallelizable**: Yes (with Steps 4 and 6)

### Step 6: Create feed generator module
**What**: Implement `generate_feed(records: list[LinkPost], output_path: str | Path, *, feed_title, feed_link, feed_id=None) -> Path`, using `feedgen.feed.FeedGenerator` to build Atom-only feeds with one entry per record; each entry's `fe.title()` = `record.url` (per plan.md's title-source decision — `feedgen` requires a non-empty title and `LinkPost` has none). `published` is already a validated, tz-aware `datetime` string by construction time (see record.py) — parse with `datetime.fromisoformat()` and set feed-level `updated` to the maximum `published` timestamp across records for determinism, with an explicit fallback (not `max()` on an empty sequence) when `records` is empty — `generate_feed([])` must succeed and produce a valid zero-entry feed. Each feed entry must include the record's `comment` content in addition to `url`, `published`, and `tags`.
**Files**: `src/linkblog_commons/feed.py`
**Test**: Call `generate_feed()` with a list of test records and a temp file path; verify the feed file is created, contains exactly N entries (one per record), all entries have url/published/tags/comment from the records, feed-level id/title/link are correct, and feed XML is well-formed (parseable by `xml.etree.ElementTree`). Include an explicit test case for a LinkPost with `comment=""` (a legal record) surviving feed generation without error.
**Depends on**: Step 3
**Parallelizable**: Yes (with Steps 4 and 5)

### Step 7: Create and verify renderer tests
**What**: Write unit tests for Hugo file output, directory creation, filename determinism, front-matter formatting, and error cases (non-writable directory, file overwrite behavior). Include two concrete test cases for overwrite: (a) the SAME record rendered twice to the same directory produces the same filename and same content, silent success (not an error); (b) two DIFFERENT records sharing the same (url, published) pair — the documented, in-spec collision case — the second render silently supersedes the first's file (also not an error, this is intentional per the plan).
**Files**: `tests/test_render.py`
**Test**: Run `pytest tests/test_render.py -v` — all tests pass.
**Depends on**: Step 5
**Parallelizable**: Yes (with Step 8)

### Step 8: Create and verify feed generator tests
**What**: Write unit tests for feed file generation, entry count, XML structure, determinism (identical records → identical feed file on repeated calls), and error cases (non-writable output path). Include explicit test cases for: (1) a LinkPost with `comment=""` surviving generation without error (title comes from `url`, not `comment`); (2) assertions that feed entries include the record's `comment` content, not just `url`/`published`/`tags`; (3) `generate_feed([])` (empty records list) succeeds and produces a valid, well-formed zero-entry feed, not a crash. (Invalid/timezone-naive-timestamp rejection is now tested in `test_record.py`/Step 4, since `LinkPost.__post_init__` is the single validation gate — no need to duplicate it here.)
**Files**: `tests/test_feed.py`
**Test**: Run `pytest tests/test_feed.py -v` — all tests pass.
**Depends on**: Step 6
**Parallelizable**: Yes (with Step 7)

### Step 8a: Create CLI module — Part A: argparse scaffolding and render subcommand
**What**: Implement `main()` entry point with `argparse` subparsers for the `render` subcommand; parse render flags (`--url`, `--published`, `--comment`, `--tag`...) and hook into the existing `hugo_render()` function.
**Files**: `src/linkblog_commons/cli.py` (partial)
**Test**: Call `main(["render", "--url", "http://example.com", "--published", "2024-01-01T00:00:00Z"])` in-process; verify successful parsing and correct invocation of `hugo_render()`.
**Depends on**: Steps 3, 5
**Parallelizable**: No

### Step 8b: Create CLI module — Part B: feed subcommand, JSON envelope, error mapping, and entry point
**What**: Complete the CLI by implementing the `feed` subcommand parsing (`--input`, `--output`, `--title`, `--link`); wrap both `render` and `feed` subcommands in a JSON envelope (`{status, result, error}`); map `LinkBlogError` fields to the JSON envelope error payload; exit with 0/1 on success/failure. Implement `src/linkblog_commons/__main__.py` with a single line `sys.exit(main())` to make `python -m linkblog_commons` invoke the CLI.
**Files**: `src/linkblog_commons/cli.py` (completed), `src/linkblog_commons/__main__.py`
**Test**: Call `main()` in-process with valid arguments for both render and feed subcommands; verify JSON envelope structure is correct, success cases return `"status": "ok"` with appropriate result keys, failure cases return `"status": "fail"` with error code and fields mapped from `LinkBlogError`. Run `python -m linkblog_commons --help` to verify help text appears and exit code is 0.
**Depends on**: Steps 3, 6, 8a
**Parallelizable**: No

### Step 9: Update public API exports
**What**: Modify `src/linkblog_commons/__init__.py` to define `__all__` and re-export `LinkPost`, `LinkBlogError`, `LinkBlogErrorCode`, `hugo_render`, and `generate_feed` for direct Python imports.
**Files**: `src/linkblog_commons/__init__.py`
**Test**: Run `python -c "from linkblog_commons import LinkPost, hugo_render, generate_feed; print('OK')"` — verify no import errors.
**Depends on**: Steps 3, 5, 6
**Parallelizable**: Yes

### Step 10: Create and verify CLI tests
**What**: Write unit tests covering CLI success/failure paths (valid/invalid records, missing required fields), JSON envelope correctness, and a subprocess smoke test (`subprocess.run([sys.executable, "-m", "linkblog_commons", ...])`) comparing CLI output to direct Python calls for byte-for-byte equivalence on rendering and feed generation. Include an explicit test case for the CLI's `feed --input -` (reading the JSON array from stdin instead of a file).
**Files**: `tests/test_cli.py`
**Test**: Run `pytest tests/test_cli.py -v` — all tests pass, including subprocess parity checks and stdin test.
**Depends on**: Steps 8a, 8b
**Parallelizable**: No

### Step 11: Run full test suite with linting and no network
**What**: Execute the complete test suite with linting and network access disabled to verify all requirements are met, no ambient state is used, and all code paths work in an isolated environment. Run `ruff check .` to verify code quality. Add `pytest-socket` to the environment or a `conftest.py` fixture to explicitly block `socket.socket` calls during testing (not just prose).
**Files**: none (all created); optionally `conftest.py` if adding fixture
**Test**: Run `ruff check .` and verify no violations. Run `pytest tests/ -v --tb=short` and verify all tests pass; re-run with `pytest --co` to confirm all 5 test modules are discovered; inspect a sample of test output to confirm record validation, render file I/O, feed XML generation, CLI envelope/parity tests, and stdin test all run.
**Depends on**: Steps 4, 7, 8, 10
**Parallelizable**: No

## Rollback plan
All steps are reversible via git. If a step fails during testing:
- Delete its created file(s) or revert `__init__.py` edits with `git checkout`.
- Preceding steps' outputs are not affected; you can re-run any earlier step without re-doing previous ones.
- No database, config files, or external state are modified.

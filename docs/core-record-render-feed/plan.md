# Plan: Core LinkPost Record, Hugo Renderer, and Feed Generator

## Approach

Implement three pure, stateless pieces on top of one shared record type: a
frozen `LinkPost` dataclass that validates itself on construction, a
`hugo_render()` function that turns one record into a Hugo-shaped Markdown
file, and a `generate_feed()` function that turns a list of records into a
`feedgen`-built Atom file — both taking every output path as an
argument, never a repo-local constant. A `cli.py` wraps both with
`argparse` subparsers and an always-JSON envelope, copying feed-commons's
`poll` CLI pattern exactly (subparsers, `python -m` entry, non-zero exit +
structured error code on failure, no raw traceback on stdout). This fits
the constraints because every design rule in `CONTRACT.md` — record-only
interface, no network calls, no hardcoded paths, no credentials — maps to
a single small module each, with no shared mutable state between them.

## Architecture

```
                      ┌─────────────────────┐
                      │   record.py          │
                      │   LinkPost (frozen    │
                      │   dataclass, self-    │
                      │   validating)         │
                      └──────────┬────────────┘
                                 │ (the only input shape)
              ┌──────────────────┼──────────────────┐
              ▼                                     ▼
   ┌────────────────────┐                ┌────────────────────────┐
   │ render.py            │                │ feed.py                  │
   │ hugo_render(record,   │                │ generate_feed(records,   │
   │   content_dir) → Path │                │   output_path, feed_*)   │
   │ (1 record → 1 .md)    │                │   → Path (feedgen, Atom) │
   └──────────┬────────────┘                └───────────┬──────────────┘
              │                                          │
              └─────────────────┬────────────────────────┘
                                 ▼
                          ┌─────────────┐
                          │   cli.py      │
                          │  argparse:    │
                          │  render|feed  │
                          │  → JSON       │
                          │    envelope   │
                          └──────┬────────┘
                                 ▼
                          __main__.py
                          `python -m linkblog_commons ...`
                                 ▲
                                 │ shell-out (no Python import)
                     pres-ber-blog's Hugo pre-build script
                          (not built in this pass)
```

Data flow, both paths:

1. Caller (Python import, or the CLI parsing flags/JSON) constructs one or
   more `LinkPost` records. Construction is the only validation gate —
   `render.py` and `feed.py` never re-validate or reshape the record.
2. `hugo_render` takes exactly one record + a caller-given content
   directory that must already exist, computes a deterministic filename
   from `(url, published)`, writes front matter (`title` = `record.url`)
   + body, returns the `Path` written.
3. `generate_feed` takes a list of records + a caller-given output path
   (+ feed-level identity — see Data model), builds one `feedgen` Atom
   entry per record (each entry's `title` = its `record.url`), writes the
   feed file, returns the `Path` written.
4. The CLI is a thin adapter: parse argv → build `LinkPost`(s) → call the
   same function a Python caller would call → print a JSON envelope →
   exit 0/1. No logic lives in `cli.py` that isn't already in `render.py`
   / `feed.py`, which is what makes requirement 18 (CLI output
   byte-for-byte equal to the direct Python call) true by construction
   rather than by a separate equivalence check.

## Data model

Not a database — this is the `LinkPost` record's shape (per the prompt's
redefinition of "data model" for this repo).

**Design decision — title source.** Atom (via `feedgen`) requires every
entry to have a non-empty title: `feedgen/entry.py`'s `atom_entry()` does
`if not (self.__atom_id and self.__atom_title and self.__atom_updated):
raise ValueError('Required fields not set')`, and `LinkPost` has no
`title` field. `comment` can't be the implicit title source, because
requirement 4 makes `comment=""` explicitly legal — feeding a record with
an empty comment through would hit that same `ValueError` on the first
try. Both `hugo_render`'s front-matter `title` and `generate_feed`'s
per-entry `fe.title()` are therefore derived from the record's `url`
field — the only field guaranteed non-empty by `__post_init__`. This is a
named design decision, not left for the implementer to guess:
`title = record.url`, verbatim, no truncation or slugifying.

```python
# record.py
@dataclass(frozen=True)
class LinkPost:
    url: str
    published: str            # ISO-8601 timestamp string; presence,
                               # parseability, AND timezone-awareness are
                               # all checked in __post_init__ (see below)
                               # — construction is the single validation
                               # gate for this field, not a presence check
                               # here plus a format/tzinfo check later,
                               # deep inside feed.py
    comment: str = ""          # plain text or markdown, no length limit
    tags: tuple[str, ...] = () # zero or more strings; tuple, not list, to
                               # keep the record genuinely immutable/hashable

    def __post_init__(self) -> None:
        missing = [f for f in ("url", "published")
                   if not getattr(self, f) or not str(getattr(self, f)).strip()]
        if missing:
            raise LinkBlogError("missing_fields", fields=missing)

        try:
            dt = datetime.fromisoformat(self.published)
        except ValueError:
            raise LinkBlogError("invalid_timestamp", fields=["published"])
        if dt.tzinfo is None:
            raise LinkBlogError("invalid_timestamp", fields=["published"])

        # Normalize tags here too (not just in from_dict) so direct
        # construction — LinkPost(url=..., published=..., tags=["a","b"]) —
        # gets the same immutable/hashable guarantee as from_dict-built
        # records, instead of silently keeping a mutable list around until
        # something tries to hash it.
        object.__setattr__(self, "tags", tuple(self.tags))
```

- Exactly four public fields, matching requirement 1.
- `url` / `published` required (falsy or whitespace-only counts as
  missing); `comment` and `tags` default to empty — satisfies requirement
  4 (empty `tags`, arbitrary-length `comment` accepted without error).
- `published` is fully validated at construction time, in order: presence,
  then `datetime.fromisoformat` parseability, then timezone-awareness
  (`dt.tzinfo is not None`). This closes a second, separate crash site:
  `feedgen/feed.py` raises its own `ValueError('Datetime object has no
  timezone info')` from both `fg.updated()` and `fe.published()` when
  handed a naive datetime — a check that fires deep inside feed
  generation, far removed from where the bad input was constructed.
  Catching it in `__post_init__` means a timezone-naive-but-otherwise-
  parseable `published` string fails fast, at the `LinkPost(...)` call
  itself, mapped to `LinkBlogError("invalid_timestamp")` right there —
  construction is the genuine single validation gate for this field, not
  just presence-checked here and format/tzinfo-checked later.
- `tags` stored as a `tuple` so the whole record stays hashable/immutable;
  the coercion happens in `__post_init__` itself (via
  `object.__setattr__(self, "tags", tuple(self.tags))`), so both direct
  `LinkPost(...)` construction and `LinkPost.from_dict(...)` get identical
  guarantees — there is no second, better-behaved construction path.
- `LinkPost.from_dict(d: dict) -> LinkPost` — classmethod used by both the
  `feed` CLI subcommand (parsing a JSON array) and any future Python
  caller loading records from JSON. Implementation strategy is fixed here,
  not left ambiguous: build `merged = {**_DEFAULTS, **d}` then
  `cls(**merged)`, wrapped in a single `try/except (TypeError, KeyError)`
  that maps either exception to `LinkBlogError("invalid_json")`. Pinning
  both the merge strategy and the exact exception types caught means the
  resulting error code doesn't depend on which internal dict-access style
  got used — `from_dict` is pure dict-unpacking sugar on top of the same
  constructor, not a second constructor with its own error behavior.

```python
# errors.py
LinkBlogErrorCode = Literal[
    "missing_fields",     # LinkPost missing url and/or published
    "invalid_json",       # feed subcommand's input isn't a JSON array of objects
    "invalid_timestamp",  # published isn't parseable ISO-8601 or lacks tzinfo
                           # (raised by LinkPost.__post_init__, at construction
                           # time — not deferred to feed.py)
    "io_error",           # output path/dir not writable, content_dir missing,
                           # or a front-matter value the serializer can't
                           # safely quote
    "internal_error",     # catch-all for anything unanticipated (CLI only)
]

class LinkBlogError(Exception):
    def __init__(self, code: LinkBlogErrorCode, fields: Sequence[str] = ()) -> None:
        self.code = code
        self.fields = tuple(fields)
        super().__init__(f"{code}: {', '.join(fields)}" if fields else code)
```

One error type for the whole repo (record validation, render, feed, CLI),
mirroring feed-commons's single `PollError` — this repo doesn't need
per-submodule error types since there's exactly one input shape.

## API / interface contract

### Python API (`import linkblog_commons`)

```python
LinkPost(url: str, published: str, comment: str = "", tags: Sequence[str] = ()) -> LinkPost
LinkPost.from_dict(d: dict) -> LinkPost

hugo_render(record: LinkPost, content_dir: str | Path) -> Path
# writes exactly one .md file into content_dir; returns the file's Path.
# content_dir must already exist — hugo_render does NOT create it (see
# Risk areas: an auto-created directory Hugo never scans would "succeed"
# silently while the post never appears on the site). Raises
# LinkBlogError("io_error") if content_dir doesn't exist, isn't a
# directory, or isn't writable. Front-matter `title` is `record.url` (see
# Data model's title-source design decision) — there's no separate title
# field to pull it from.

generate_feed(
    records: list[LinkPost],
    output_path: str | Path,
    *,
    feed_title: str,
    feed_link: str,
    feed_id: str | None = None,   # defaults to feed_link if omitted
) -> Path
# writes exactly one Atom feed file with one entry per record; returns its
# Path. feed_title/feed_link are REQUIRED caller-supplied feed-level
# identity — feedgen refuses to serialize a feed missing id/title/link,
# and neither value is derivable from a LinkPost record (they describe the
# *feed*, e.g. "pres-ber-blog: Linkblog", not any single entry). Not in
# requirements.md's field list for the function signature explicitly, but
# necessary for req 10 ("build an Atom feed") to produce valid XML at all
# — flagged again under Risk areas.
# Always produces Atom — there is no `fmt`/RSS parameter in this pass
# (see Deferred, below).
# Each entry's fe.title() is record.url (see Data model's title-source
# decision) — feedgen's atom_entry() raises ValueError if any entry lacks
# a title, and LinkPost has no title field.
# records may be empty — a legitimate, valid, zero-entry Atom feed (e.g.
# before the first post is ever made). fg.updated() falls back to a
# fixed, deterministic constant in that case, rather than calling max() on
# an empty sequence (see Risk areas).
```

### CLI (`python -m linkblog_commons ...`)

Concrete decision for requirement 16/17 (this was left TBD in
requirements.md and is resolved here): `render` takes one record as flags
(a single record is small and flag-shaped); `feed` takes many records as a
JSON array via `--input` (file path or `-` for stdin), since a feed
inherently needs a list and flags don't scale to N records. Both follow
feed-commons's envelope shape, adapted from `{status, items, error}` to
`{status, result, error}` since these ops produce one artifact, not a list
of polled items — plus a `schema_version` field feed-commons's envelope
doesn't have (see below).

```
python -m linkblog_commons render \
    --url URL --published TIMESTAMP [--comment TEXT] [--tag TAG ...] \
    --output-dir DIR

python -m linkblog_commons feed \
    --input PATH_OR_-  --output PATH \
    --title TITLE --link URL [--id ID]
```

- `render` flags map 1:1 to `LinkPost` fields; `--tag` is repeatable
  (`action="append"`), omitted entirely → `tags=()`.
- `feed --input` reads a JSON array of objects (`{"url":...,
  "published":..., "comment":..., "tags":[...]}`); each object goes
  through `LinkPost.from_dict`. `--input -` reads the array from stdin so
  a caller doesn't need a temp file. `--title`/`--link` are required (no
  default — see feed-level identity note above). Output is always Atom —
  there is no `--format` flag in this pass (RSS is a deferred, cheap
  future extension; see Deferred, below).
- Every JSON envelope — success or failure, `render` or `feed` — carries
  `"schema_version": 1` as a top-level field. Cheap to add now, expensive
  to retrofit once pres-ber-blog's build script is parsing this output
  unconditionally as its first real cross-repo consumer.
- Success envelope: `{"schema_version": 1, "status": "ok", "result": {...},
  "error": null}`. `result` for `render` is `{"path": str, "filename":
  str}`; for `feed` it's `{"path": str, "entry_count": int}`.
- Failure envelope: `{"schema_version": 1, "status": "fail", "result":
  null, "error": {"code": str, "fields": [str, ...]}}`, printed to stdout
  (matching feed-commons's convention of always emitting the envelope to
  stdout, even on failure) with exit code 1. No `"degraded"` status —
  unlike feed-commons's `poll`, render/feed have no partial-success case: a
  `LinkPost` is either fully valid or the whole call fails.
- `LinkBlogError` is caught and mapped straight to its `.code`/`.fields`;
  any other exception is caught and mapped to `{"code": "internal_error",
  "fields": []}` — this is the "structured error codes, not raw exception
  text" rule, so a bug here never leaks a Python traceback onto stdout for
  a shell caller to choke on. This `fields` array plus the catch-all
  `internal_error` mapping is a deliberate extension beyond feed-commons's
  own `cli.py`, which only has `{status, items, error}` with no `fields`
  array and doesn't catch generic exceptions — noted here explicitly so
  this design isn't assumed to be a literal structural mirror of the
  sibling repo.
- `__main__.py`: `sys.exit(main())`, identical to feed-commons's.

## Integration points

- `src/linkblog_commons/errors.py` — new. `LinkBlogError` + `LinkBlogErrorCode`, shared by record/render/feed/cli.
- `src/linkblog_commons/record.py` — new. `LinkPost` frozen dataclass, `__post_init__` validation (presence, timestamp parse + tzinfo, tags coercion), `from_dict`.
- `src/linkblog_commons/render.py` — new. `hugo_render()`, deterministic filename derivation from `(url, published)`, hand-rolled front-matter serialization with an explicit quoting rule.
- `src/linkblog_commons/feed.py` — new. `generate_feed()` built on `feedgen.feed.FeedGenerator`, Atom only.
- `src/linkblog_commons/cli.py` — new. `_build_render_parser`/`_build_feed_parser`/`_build_parser`, `main()`, JSON envelope construction (including `schema_version`), error mapping.
- `src/linkblog_commons/__main__.py` — new. `sys.exit(main())`, copied from feed-commons's file verbatim (just the import path changes).
- `src/linkblog_commons/__init__.py` — currently empty; add `LinkPost`, `LinkBlogError`, `LinkBlogErrorCode`, `hugo_render`, `generate_feed` to `__all__`, matching feed-commons's `__init__.py` re-export pattern.
- `tests/__init__.py`, `tests/test_record.py`, `tests/test_render.py`, `tests/test_feed.py`, `tests/test_cli.py` — new. Mirrors feed-commons's `tests/` layout (one file per module + one for the CLI, including an in-process `main()` test and a `subprocess.run([sys.executable, "-m", "linkblog_commons", ...])` smoke test for `--help` and one real invocation, matching `tests/test_cli.py`'s two-tier approach there).
- `pyproject.toml` — no dependency changes; `feedgen` is already pinned and no other new runtime dependency is needed (front matter is hand-serialized, not via a new YAML library — see Technology choices). Existing `network` pytest marker stays unused by this feature's tests (this repo makes no network calls by design), inherited from the shared repo template.

## Technology choices

- **`feedgen.feed.FeedGenerator`** (already pinned) for the feed generator — required by the constraints, not a new choice; used via `fg.add_entry()` per record and `fg.atom_file(path)`. Atom only in this pass — no `fg.rss_file(...)` call (see Deferred, below).
- **Hand-rolled YAML front matter, no new dependency, explicit quoting rule.** The front-matter field set is small and fully known (three plain strings + a string list), so a minimal internal serializer is enough; adding `PyYAML` for three scalar fields would be new dependency weight for no real safety gain, and this repo's whole point is staying a thin, dependency-light shared library. The quoting rule is fixed here, not left as "basic quoting": every string scalar (`url`, `title`, each tag) is always double-quoted, with internal `\` and `"` backslash-escaped (`\` → `\\`, `"` → `\"`). This makes a `comment` line that happens to read exactly `---` (Hugo's frontmatter delimiter), or one containing `:` or `"`, always safe — it's always inside a quoted scalar, never emitted bare. If a value contains a raw newline, which this simple escaping strategy can't safely represent as a single-line double-quoted scalar, the serializer raises `LinkBlogError("io_error")` instead of silently emitting corrupt or invalid YAML.
- **`datetime.fromisoformat`** (stdlib, no new dependency) to parse and timezone-check `published`. This now happens exactly once, inside `LinkPost.__post_init__` at construction time (see Data model) — not deferred to `feed.py`. Python 3.11 (this repo's floor) parses the common ISO-8601 variants including a trailing `Z`, so no `dateutil` is needed.
- **`hashlib.sha256`** (stdlib) over the `(url, published)` pair — not `url` alone — to build the deterministic filename slug in `render.py`. Hashing the pair matches Risk Area 4's accepted collision boundary: two distinct posts that share a URL but have different `published` timestamps (an ordinary linkblog case — resurfacing a link on a different day) get different filenames; only a genuine duplicate `(url, published)` pair collides, which requirement 8 treats as in-spec, not a bug. The filename is prefixed with the `published` date (`YYYY-MM-DD-<hash[:16]>.md`) as a bonus: output sorts chronologically in the content directory, which a hash-only scheme wouldn't.

## Risk areas

1. **Feed-level identity isn't in the LinkPost record.** `generate_feed()` needs `feed_title`/`feed_link` that requirements.md never names as a parameter — they're needed only because `feedgen` refuses to serialize an Atom feed without them. This is a real interpretation call, not something the requirements resolved; if pres-ber-blog's integration later wants these to come from a config file instead of CLI flags, that's a compatible extension, not a breaking one, but it's worth flagging now rather than discovering it during the CLI acceptance tests.
2. **Naive (no-tzinfo) `published` timestamps — resolved at construction, not left as a gray area.** `feedgen/feed.py` raises `ValueError('Datetime object has no timezone info')` from both `fg.updated()` and `fe.published()` when handed a naive datetime — a second, separate crash site from `datetime.fromisoformat`'s own parsing failure. `LinkPost.__post_init__` now checks both parseability and `dt.tzinfo is not None` at construction time, raising `LinkBlogError("invalid_timestamp")` right there. This still needs a concrete test case (a timezone-naive-but-parseable string, e.g. `"2026-08-15T10:00:00"`, must be rejected at `LinkPost(...)` construction, never reach `feed.py`) to call this solid — verify against the installed `feedgen` version's actual behavior, not just this plan's description of it.
3. **Feed-level `updated` and `generator` fields must not touch the system clock, and must not crash on an empty feed.** Left to `feedgen` defaults, `fg.updated()` typically falls back to "now," which would make `generate_feed()` output non-deterministic between two calls with identical input — violating both requirement 18 (byte-for-byte CLI/direct-call equivalence) and the "pure function, no ambient state" non-functional requirement. Plan is to explicitly set `fg.updated()` to the max `published` across the input records (deterministic, derived only from input) — this must be verified against the installed `feedgen` version's actual default behavior, not assumed. Separately: `generate_feed([])` is a legitimate call (an empty feed, e.g. before the first post) and must not crash — computing "max published across records" via bare `max()` on an empty list raises `ValueError`, so the empty-records case needs an explicit guard that falls back to a fixed, deterministic constant (e.g. an epoch constant, or something derived from `feed_link`) instead of calling `max()` on nothing.
4. **Deterministic filenames now hash `(url, published)`, matching this plan's own accepted collision boundary.** Requirement 8 only asks that the *same* record render to the *same* filename twice — it doesn't require global uniqueness across a corpus of different records — so a collision on a genuine duplicate `(url, published)` pair is in-spec, not a bug. Hashing `url` alone (an earlier draft of this plan) would have silently collided on a different, out-of-spec case too: two distinct posts linking the same URL on different days (an ordinary linkblog case — resurfacing a link) would overwrite each other, which this Risk Area never claimed as accepted. Hashing the pair together closes that gap.
5. **`--comment` as a plain CLI flag has practical shell limits.** Fine for the short commentary this format is designed for, but a caller with an unusually long or multi-line comment will hit shell argument-length/quoting friction well before hitting this repo's own "no length limit enforced" rule. No stdin/file-input escape hatch is planned for `render` in this pass (would be scope creep beyond requirements.md); Python callers with long comments should use the direct `hugo_render()` import instead of the CLI.
6. **Caller-trust boundary for `content_dir`/`output_path`.** Both are trusted local-operator input — this is a CLI/library invoked by the repo owner's own build script, not a network-facing service — so no path-traversal hardening (e.g. rejecting `..` segments, symlink checks) is built in this pass. That's a real, deliberately deferred, low-severity item, noted here so it isn't silently unaddressed rather than considered and dropped.

## Deferred (explicitly out of scope for this pass)

- **RSS output.** `feedgen/feed.py`'s `_create_rss` requires a channel-level `description` (`if not (self.__rss_title and self.__rss_link and self.__rss_description): raise ValueError(...)`), which `generate_feed()`'s signature doesn't collect. RSS is also unrequested scope creep as of this pass — Atom alone already satisfies every requirement and acceptance criterion. Dropped entirely from this pass, including the `fmt`/`--format` parameter/flag. Real, cheap future extension once a `feed_description` parameter is added — not blocked, just not built now.
- **A `render-batch` CLI verb.** Mirroring `feed`'s `--input` JSON-array shape for `render`, avoiding N separate process spawns when pres-ber-blog's build script eventually renders many posts per build. Real, cheap future extension — not built in this pass, since there's exactly one caller today and nothing requires it yet.

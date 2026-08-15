# Requirements: Core LinkPost Record, Hugo Renderer, and Feed Generator

## Problem statement
linkblog-commons is a scaffold with no working code: `src/linkblog_commons/__init__.py` is empty and CONTRACT.md describes an intended shape that has never been implemented. pres-ber-blog (a Hugo static site) needs a linkblog section — short link-plus-commentary posts, kept separate from its main long-form posts and main feed — but there is no prior implementation to extract from, unlike this repo's siblings (e.g. feed-commons's `poll` submodule, pulled from internal-monitor-app's existing poller). This feature builds that first real implementation: a shared LinkPost record and the two pure-function submodules (Hugo file renderer, Atom feed generator) that turn it into site output, plus a CLI so non-Python callers (Hugo's build pipeline) can invoke them. It matters now because pres-ber-blog's linkblog section is blocked on this library existing; this pass delivers the library only, not the site integration.

## Users / stakeholders
- pres-ber-blog's Hugo build pipeline — the first real consumer, invoking this repo via CLI shell-out from a pre-build script (not modified in this pass, but the CLI contract must be usable by it).
- Future Python callers that `import linkblog_commons` directly instead of shelling out.
- The repo maintainer, who needs the CONTRACT.md design rules (record-only interface, no network calls, distinct output paths, no credentials) enforced by tests, not just documented.

## Functional requirements
1. The system shall define a LinkPost record with exactly four fields: `url` (string), `comment` (string, plain text or markdown, no length limit enforced), `published` (ISO-8601 timestamp), and `tags` (zero or more strings).
2. The system shall treat the LinkPost record as the only input type accepted by the renderer submodule, the feed generator submodule, and the CLI — no submodule shall accept a different shape for the same data.
3. The system shall reject construction/validation of a LinkPost record missing `url` or `published`, raising an error identifying the missing field(s).
4. The system shall accept a LinkPost record with an empty `tags` list and with `comment` of arbitrary length, without error.
5. The system shall validate that a LinkPost record's `published` field is a timezone-aware, parseable ISO-8601 timestamp at construction time, raising a clear, structured error if it is unparseable or timezone-naive — this validation is not deferred to the Hugo renderer or the feed generator, so construction is the single validation gate the rest of this spec assumes it is.
6. The system shall coerce `LinkPost.tags` to a tuple in `__post_init__` regardless of construction path — whether the record is constructed directly via keyword arguments or via `from_dict` — so both entry points provide identical immutability guarantees.
7. The Hugo renderer submodule and the feed generator submodule shall each derive a title for their output — the rendered file's front matter title and the feed entry's title, respectively — from the record's `url` field, since LinkPost has no dedicated title field and `url` is the only field guaranteed non-empty.
8. The Hugo renderer submodule shall convert a single LinkPost record into a Markdown file containing YAML front matter with a `url` field, a `published` field, a `tags` field, and a `title` field derived from `url` (per requirement 7), and a body containing the record's `comment`.
9. The Hugo renderer submodule shall write its output file into a content directory supplied by the caller at call time (a parameter or config value), never a path hardcoded in this repo.
10. The Hugo renderer submodule shall never write into, or otherwise touch, the site's main-post content directory.
11. The Hugo renderer submodule shall derive the output filename deterministically from a hash of the LinkPost record's `url` and `published` fields taken together (not `url` alone), such that rendering the same record twice produces the same filename.
12. The Hugo renderer submodule shall perform no network calls, no filesystem reads/writes outside the caller-specified output directory, and no fetching of the `url` field's contents.
13. The feed generator submodule shall build a single Atom feed, using the `feedgen` library, containing one feed entry per input LinkPost record, populated from that record's `url`, `comment`, `published`, `tags`, and the title derived per requirement 7.
14. The system shall require the caller to supply feed-level identity — a feed title and a feed link — as required parameters to `generate_feed()`, since the `feedgen` library cannot serialize a feed without them and no LinkPost field can supply feed-level (as opposed to per-entry) title or link values.
15. The feed generator submodule shall write the feed to an output path supplied by the caller at call time, never a path hardcoded in this repo.
16. The feed generator submodule shall never write into, merge with, or append to the site's main-post feed file.
17. The feed generator submodule shall produce a single Atom feed containing only link-post entries — no mixing with any other content type in a single feed file.
18. The feed generator submodule shall perform no network calls, including no fetching of the `url` field's contents to verify it resolves or to enrich the entry.
19. The system shall expose a CLI entry point runnable as `python -m linkblog_commons`, with a subcommand (or equivalent invocation) for the Hugo renderer and a separate subcommand for the feed generator.
20. The CLI shall expose a `render` subcommand that accepts a single LinkPost record's data via command-line flags, and a `feed` subcommand that accepts multiple records via a `--input` JSON array argument or stdin, both writing to a caller-specified output path/directory supplied as CLI-level input and both producing a JSON envelope on stdout — matching feed-commons's existing `argparse`-based, always-JSON-envelope `python -m` CLI convention.
21. The CLI shall exit with a non-zero status code and print an error message when given invalid or incomplete LinkPost input (e.g., missing `url` or `published`).
22. The Markdown file written by the CLI's `render` subcommand shall be byte-for-byte identical to the file written by calling the Hugo renderer submodule directly in Python with the same LinkPost data and output directory; the feed file written by the CLI's `feed` subcommand shall be byte-for-byte identical to the file written by calling the feed generator submodule directly in Python with the same records and output path. This equivalence applies to the file written to disk — not to the CLI's own stdout JSON envelope, which wraps a result summary (e.g., path and filename), not the raw file contents.
23. The system shall include automated tests covering: LinkPost record construction and validation (valid and invalid cases), the Hugo renderer's file output and content, the feed generator's file output and content, and the CLI's success and failure paths.

## Non-functional requirements
- No network calls anywhere in this repo's render or feed-generation code path — tests must pass with network access disabled.
- Renderer and feed generator are pure functions over the LinkPost record: identical input (record + output path) produces identical output on repeated calls, with no reliance on ambient state (system clock, environment, network).
- No credentials, API keys, or auth tokens are required or accepted by this repo in this pass (per CONTRACT.md rule 5).

## Constraints
- Feed generation must use the `feedgen` library (already pinned in `pyproject.toml`: `feedgen>=1.0.0,<2`) — no alternative feed-generation library.
- All output paths (Hugo content directory, feed output path) must be caller-supplied config values; this repo must not assume or hardcode any specific site's directory layout.
- The CLI's invocation pattern must match feed-commons's existing `python -m` cross-language CLI convention, so non-Python callers (e.g. Hugo's pre-build pipeline) can shell out to both repos the same way.
- The LinkPost record is the single interface every submodule takes — no submodule may parse the `url` to infer link type, fetch it, or generate/alter the `comment` text.
- pres-ber-blog itself is not modified in this pass; this feature delivers the library only, with no live integration to verify against beyond tests.

## Out of scope
- Modifying pres-ber-blog or wiring its build pipeline to call this CLI.
- Fetching, resolving, or validating that `url` points to a live resource.
- Generating, summarizing, or editing the `comment` text.
- Parsing `url` to classify or enrich the link (e.g., detecting domain, fetching OpenGraph metadata).
- Rendering or generating the site's main-post content or main-post feed.
- Persistence or storage of LinkPost records (e.g., a database or file-based record store) — records are passed in per call, not stored by this repo.
- Authentication, credentials, or any credentialed API calls (explicitly excluded from v1 per CONTRACT.md).
- Any non-Hugo static-site renderer.
- RSS feed output (Atom only for this pass) — RSS requires an additional channel-level `description` field with no natural source in the LinkPost record; a real, low-cost future extension once that's designed, not built now.

## Acceptance criteria
1. Constructing a LinkPost record with valid `url`, `comment`, `published`, and `tags` succeeds and exposes all four fields unchanged.
2. Constructing a LinkPost record missing `url` or missing `published` raises an error identifying the missing field.
3. Constructing a LinkPost record with an unparseable or timezone-naive `published` value raises a clear, structured error at construction time.
4. Given a valid LinkPost record and a target content directory, the Hugo renderer writes exactly one Markdown file into that directory, with front matter containing the record's `url`, `published`, `tags`, and a `title` derived from `url`, and a body containing the record's `comment`.
5. The Hugo renderer never writes to any directory other than the one passed by the caller in that call.
6. A LinkPost record with `comment=""` (a legal record per requirement 4) renders successfully via the Hugo renderer and feeds successfully via the feed generator without error, since title no longer depends on `comment`.
7. Rendering the same LinkPost record to the same directory twice produces the same output filename both times, because the filename is derived from a hash of the `(url, published)` pair; two different records that happen to share the same `url` and `published` values intentionally collide to the same filename — this is documented behavior, not a bug.
8. Given a list of LinkPost records, a feed title, a feed link, and a caller-specified output path, the feed generator writes a single feed file to that path containing exactly one entry per input record and no other entries.
9. Calling the feed generator without a `feed_title` or `feed_link` fails with a clear error, since the `feedgen` library cannot serialize a feed without feed-level identity and no LinkPost field can supply it.
10. Calling the feed generator with an empty list of records does not crash and produces a valid, well-formed feed containing zero entries.
11. The feed file produced in test 8 validates as well-formed Atom XML.
12. Running the renderer and the feed generator with network access disabled produces output identical to running them with network access enabled.
13. The Markdown file written to disk by `python -m linkblog_commons`'s `render` subcommand is byte-for-byte identical to the file written by calling the Hugo renderer submodule directly in Python with the same record and output directory — not the CLI's stdout JSON envelope, which wraps a result summary (path/filename), not the raw file.
14. The feed file written to disk by `python -m linkblog_commons`'s `feed` subcommand is byte-for-byte identical to the file written by calling the feed generator submodule directly in Python with the same records, feed title, feed link, and output path — not the CLI's stdout JSON envelope, which wraps a result summary (path/filename), not the raw file.
15. Invoking the CLI with a LinkPost input missing a required field exits with a non-zero status code and prints an error message.
16. The test suite includes at least one passing test for each of: the LinkPost record, the Hugo renderer, the feed generator, and the CLI, and the full suite passes with network access disabled.

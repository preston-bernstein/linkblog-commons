# Spec Challenge Notes

## Agents run
- Requirements Auditor (haiku): 10 issues found, 6 accepted
- Scope & Dependency Auditor (sonnet): 8 issues found, 6 accepted
- Design Devil's Advocate (sonnet): 8 issues found, 8 accepted
- Implementation Realist (sonnet): 7 issues found, 7 accepted — verified directly against the real `feedgen==1.0.0` source (not speculation), the highest-confidence lane
- Steps & Sequencing Critic (sonnet): 10 issues found, 10 accepted
- Data Model Critic (sonnet): 13 issues found, 5 accepted (the rest were duplicate framings of issues already captured by other lanes)
- Security/Threat Auditor (haiku): 5 issues found, 2 accepted (path traversal, YAML injection — both folded into plan.md as a caller-trust-boundary note and an explicit quoting rule, respectively; auth/exposure/dependency findings didn't apply to a local CLI/library)

## Changes made
- **Fixed a guaranteed crash**: `LinkPost` had no title field, but `feedgen` requires a non-empty title on every Atom entry — verified against the actual library source (`entry.py`'s `atom_entry()` raises `ValueError` without one). A record with the explicitly-legal `comment=""` would have crashed the first time it hit `generate_feed()`. Both the renderer and feed generator now derive title from `record.url`, the only field guaranteed non-empty — a named design decision, not left for an implementer to guess.
- **Fixed a second guaranteed crash**: RSS output was in scope but `feedgen`'s RSS path requires a channel-level `description` field the design never collected — every `fmt="rss"` call would have raised `ValueError`. Also independently flagged as unrequested scope creep. Dropped RSS entirely for this pass (Atom only); noted as a cheap, real future extension once `feed_description` is designed.
- **Fixed a third crash site**: timezone-naive timestamps parse fine via `datetime.fromisoformat()` but raise a *separate* `ValueError` later, deep inside `feedgen`'s `fg.updated()`/`fe.published()`. Moved full `published` validation (parseable + timezone-aware) into `LinkPost.__post_init__`, so construction is genuinely the single validation gate the rest of the spec assumed it already was.
- **Fixed the filename collision boundary**: the plan hashed `sha256(url)` alone but its own Risk Area claimed the accepted collision was on `(url, published)` — the two didn't match, so two posts resurfacing the same URL on different days would have silently overwritten each other. Now hashes the pair, date-prefixed for chronological sorting as a bonus.
- **Fixed a `tags` immutability gap**: tuple-coercion happened only in `from_dict`, not `__post_init__` — three independent review lanes converged on this. Direct keyword construction now gets the same guarantee.
- **Fixed `generate_feed([])`**: would have crashed calling `max()` on an empty sequence. An empty feed is a legitimate state (e.g. before the first post); now has an explicit deterministic fallback.
- **Fixed undefined front-matter escaping**: a `comment` containing a bare `---` line or a colon/quote could have corrupted Hugo's frontmatter delimiter. Now has a named, testable quoting rule (always double-quote, backslash-escape `\`/`"`; raise a structured error rather than silently emit invalid YAML on an unescapable raw newline).
- **Fixed a design tension with CONTRACT.md rule 2**: `hugo_render` auto-created `content_dir` if missing, so a typo'd path would silently create a directory Hugo never scans instead of failing loudly. Now requires the directory to pre-exist.
- **Fixed steps.md ordering**: Step 8 (CLI) was realistically >2 hours, split into 8a/8b; a false dependency on Step 8 for the `__init__.py` exports step was removed; the record-tests step was wrongly sequenced strictly before the render/feed steps despite having no real dependency on either — now parallelizable with both.
- **Added missing steps**: installing test dependencies (nothing did this before Step 1's first `pytest` run), running `ruff check .` (no step ran the CI lint job at all), and actually disabling network access for the "network disabled" acceptance criterion (was prose-only, now wires in `pytest-socket` or a `conftest.py` fixture).
- **Post-rewrite pass caught residual staleness**: the automated steps.md rewriter fixed the 12 items it was given but left Step 5's description referencing the old `sha256(url)`-only filename scheme and omitting the `title` field — both already fixed in plan.md. Corrected directly (not re-delegated) to keep the specs internally consistent; also added the timezone-naive and empty-feed test cases explicitly to Steps 4 and 8.

## Critiques rejected
- CLI JSON envelope naming (`result` vs. feed-commons's `items`) — Scope Auditor flagged this as a possible violation of "match feed-commons's convention," but the constraint is about invocation *pattern* (argparse subparsers, `python -m`, always-JSON), not literal field-name identity; a single-artifact result naturally isn't shaped like a list of polled items. Plan.md now states this explicitly as a deliberate, noted extension rather than a violation.
- FR7/FR12 ("never write to main-post directory") flagged as untestable by the Requirements Auditor — rejected as a real gap since acceptance criterion 4/5 already tests the positive form (writes only to the caller-specified directory), which is the practical, testable proxy for the same constraint.
- A `render-batch` CLI verb (Design Devil's Advocate) — real and reversible, but genuine scope creep for a pass with exactly one caller and no step requiring it. Noted in plan.md's Deferred section instead of built now.
- Several Data Model Critic findings (naming asymmetry between `--tag`/`tags`, `LinkBlogErrorCode`'s two-tier specificity) — real observations but cosmetic, not defects; not worth a spec change.

## Open questions requiring human input
None. Every review-driven ambiguity had a resolvable answer within this pass's own constraints (CONTRACT.md, the sibling repos' conventions, or the real `feedgen` library's actual behavior) — nothing required a business decision only Preston could make.

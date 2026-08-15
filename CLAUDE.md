# linkblog-commons

This is a scaffold, not a finished library. linkblog-commons is meant to be
**imported** (Python) or **shelled out to via its CLI** (non-Python
consumers, e.g. Hugo's build pipeline via a pre-build script) by home-lab
blog projects — not run as a standalone service. See `CONTRACT.md` for the
intended shape.

This is a fourth, sibling application of the same shared-library split
`scraper-commons`, `api-clients-commons`, and `feed-commons` already
establish: `internal-infra/docs/adr/0015-shared-scraper-library.md` (the general
imported-library-gets-a-dedicated-repo decision) and
`internal-infra/docs/adr/0023-dedicated-lib-repos-for-fleet-logging-and-ollama-client.md`
(a second concrete application of that same split). No new ADR was written
for this repo, matching `api-clients-commons`' and `feed-commons`' own
precedent — it cites 0015/0023 rather than getting a unique entry, since
this isn't a new architectural decision, just another instance of the
established one.

**Unlike its siblings, this repo is not extracted from an already-working
caller.** `feed-commons`'s `poll` submodule was pulled out of
internal-monitor-app's existing feed poller. pres-ber-blog has no linkblog
feature yet — there is nothing to extract. `CONTRACT.md` defines the
intended shape up front instead, and the first submodule gets built as part
of standing up pres-ber-blog's linkblog section, not lifted from prior code.
Treat the schema in `CONTRACT.md` as a real design decision, not a
placeholder — get it right the first time, since pres-ber-blog is the only
consumer until a second project needs this.

Distinct from siblings: `scraper-commons` holds stealth/anti-detection
scraping logic; `api-clients-commons` holds credentialed API clients;
`feed-commons` polls and normalizes an *incoming* feed. This repo produces
outgoing content — a normalized link-post record, a static-site-file
renderer, and an outgoing Atom/RSS feed containing only link posts. It never
fetches anything itself; if a future submodule needs to check whether a URL
is reachable before publishing, that's a `requests` call here, not a
dependency on `feed-commons` or `scraper-commons` (the two repos in this
family never import each other).

Cross-cutting home-lab conventions (service users, secrets, the shared
library vs. shared service split) live in `internal-infra/CONVENTIONS.md`.

## Remotes

A single `git push` to `origin` writes to two remotes: the NAS (primary,
`ssh://nas.example.internal/.../linkblog-commons.git`) first, then GitHub (offsite
mirror, `preston-bernstein/linkblog-commons`, private) second. `git fetch`
only reads from the NAS.

## Secret-scan gate — run once per clone

Git hooks that scan for secrets live in `.githooks/` and are checked into
the repo, but git does not turn them on automatically. On any fresh clone,
run **`scripts/install-hooks.sh`** once. It points git at that hooks folder
(`core.hooksPath`) and checks that `gitleaks` is installed.

Once enabled, the pre-commit hook blocks any commit that stages a secret or
a real `.env` file, and the pre-push hook scans outgoing commits before they
can reach the GitHub mirror. This fails closed: if the `gitleaks` binary
isn't installed, commits and pushes are refused rather than let through
unscanned. Install it with `brew install gitleaks`. The scan rules and
allowlist live in `.gitleaks.toml`.

# linkblog-commons

linkblog-commons is a Python library and CLI that turns a link plus a short comment into a Hugo post file and an Atom feed. It exists so link posts stay on their own feed, apart from long-form posts.

## Link posts need their own feed

Short link posts and dense long-form posts serve different readers. RSS readers and curated directories reward link posts. AI search engines reward long, single-topic posts and rate link streams as weak sources. A separate feed and a separate content folder keep each type from diluting the other. The research is in the Obsidian vault at `Development/Research/linkblogging-blog-traffic.md`.

## What it does

1. `LinkPost` is the one record. It holds a URL, an ISO-8601 timestamp with a timezone, a comment (plain text or markdown) and tags.
2. `hugo_render` writes one Markdown file with front matter. The name is `<date>-<hash>.md`. The title and URL both come from the link URL.
3. `generate_feed` writes an Atom feed that holds only link posts.

The render and feed code makes no network calls. It never fetches the linked page.

The first consumer is `pres-ber-blog` (Hugo). Sibling repos `scraper-commons`, `api-clients-commons` and `feed-commons` fetch data. This repo only writes output.

## Install

```bash
pip install -e ".[test,dev]"
```

Python 3.11 or newer. The one runtime dependency is `feedgen`.

## Use the CLI

The CLI prints one JSON line. `status` is `ok` or `fail`. On failure, `error.code` is one of `missing_fields`, `invalid_json`, `invalid_timestamp`, `io_error` or `internal_error`. The exit code is 0 on success and 1 on failure.

Render one post. The output directory must exist and be writable:

```bash
python -m linkblog_commons render --url https://example.com \
  --published 2026-11-01T10:00:00+00:00 --comment "Worth a read." \
  --tag python --output-dir content/links
```

Build a feed from a JSON array of posts. Use `--input -` to read stdin:

```bash
python -m linkblog_commons feed --input posts.json --output links.xml \
  --title "Links" --link https://example.com/links
```

Each array item has `url` and `published`. `comment` and `tags` are optional. `--id` sets the feed ID. It defaults to `--link`.

## Use the Python API

```python
from linkblog_commons.record import LinkPost
from linkblog_commons.render import hugo_render
from linkblog_commons.feed import generate_feed
```

## Test

```bash
pytest -m "not network"
ruff check .
```

Tests block network access. Run `scripts/install-hooks.sh` once per clone to enable the git hooks. The hooks need `gitleaks`.

## Where things live

- `src/linkblog_commons/`: `record.py`, `render.py`, `feed.py`, `cli.py`, `errors.py`.
- `CONTRACT.md`: the design rules.
- `docs/core-record-render-feed/`: the spec for the first build.

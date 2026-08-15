# Contract: linkblog-commons

## Intended shape

A **link post** is one normalized record: a URL, a short comment (plain
text or markdown, no length limit enforced here — that's an editorial
choice for the caller), an ISO-8601 timestamp, and zero or more tags. This
repo turns that record into two outputs:

1. **A static-site source file.** For a Hugo consumer, that's a markdown
   file with frontmatter in the shape Hugo expects (see
   `hugo_render()` once implemented) — filename, frontmatter fields, and
   body derived from the record. Non-Hugo consumers get the same data as
   JSON via the CLI, matching `feed-commons`'s cross-language pattern.
2. **A feed entry.** An Atom/RSS feed built from `feedgen`, containing only
   link posts — never mixed with a site's main-post feed. This is the
   mechanism that keeps link posts and long-form posts on separate feeds so
   neither dilutes the other (see the README's "Why link posts need to stay
   separate" section).

## Design rules

1. **The record is the only interface.** Every submodule (Hugo renderer,
   feed generator, a future non-Hugo renderer) takes the same link-post
   record as input. Nothing here parses a URL to decide what it links to,
   fetches the URL, or generates the comment text — those are editorial or
   caller-side concerns.
2. **Never touches the main post feed or main post directory.** This repo's
   output paths and feed file are always distinct from a site's existing
   content — never write into a shared directory where a script could
   silently mix link posts into the main content stream by accident. Which
   exact paths a given site uses is a per-consumer config value, not a
   hardcoded assumption.
3. **No network calls in the render/feed path.** Turning a record into a
   file or a feed entry is pure — no fetching the linked URL to check it
   resolves, no fetching metadata (title, favicon) from it. If that's
   wanted later, it's a new, explicit, opt-in submodule, not a default.
4. **A CLI entry point exists for every submodule**, so a non-Python
   consumer (Hugo's build step, a shell script) can call this without a
   Python import boundary.
5. **No credentials in v1.** Nothing here talks to an authenticated
   service. If a future submodule needs one (e.g. cross-posting to
   Bluesky), that's a new, explicit extension to design then.

## Status today

Scaffold only. No submodule implemented. First real consumer:
`pres-ber-blog`, standing up its linkblog section.

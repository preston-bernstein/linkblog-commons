# linkblog-commons

linkblog-commons is a shared Python library for the home lab's blog
projects that want a linkblog: a stream of short posts, each a link plus a
few sentences of commentary, kept separate from long-form posts. It defines
one normalized "link post" record, a renderer that turns that record into
files a static site generator can build, and a feed generator that produces
an Atom/RSS feed containing only link posts.

## Why link posts need to stay separate

Research into whether linkblogging would grow blog traffic
(`Development/Research/linkblogging-blog-traffic.md` in the Obsidian vault)
found a real split: RSS readers, Bluesky's chronological feed, and
curated-directory sites like Kagi Small Web are reviving in 2026 and reward
exactly this format. AI search engines (ChatGPT, Perplexity, Google AI
Overviews) reward the opposite — dense, comprehensive, single-topic posts —
and treat a stream of short link posts as citation-weak. A blog that wants
both needs to keep the two content types structurally distinct: separate
feed, separate section, so a link post never dilutes the data-dense posts
tuned for AI citation, and the AI-citation tuning never talks the blog out
of publishing something short.

## How this differs from its siblings

`scraper-commons` holds stealth/anti-detection scraping logic.
`api-clients-commons` holds real, credentialed API clients.
`feed-commons` polls and normalizes an *incoming* public feed. This repo is
none of those — it produces content, not fetches it: given a link and a
comment, it emits a post file and an outgoing feed entry.

## Built when a real consumer needs it, not speculatively

`CONTRACT.md` defines the intended shape, but each submodule is only built
once a real project needs it — same discipline `scraper-commons`,
`api-clients-commons`, and `feed-commons` use for their own modules. Status
today: scaffold only, no submodule implemented yet. `pres-ber-blog` (Hugo)
is the first intended consumer.

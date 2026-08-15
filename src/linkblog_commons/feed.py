from datetime import datetime
from pathlib import Path

from feedgen.feed import FeedGenerator

from linkblog_commons.record import LinkPost

_EPOCH_FALLBACK = datetime.fromisoformat("1970-01-01T00:00:00+00:00")


def generate_feed(
    records: list[LinkPost],
    output_path: str | Path,
    *,
    feed_title: str,
    feed_link: str,
    feed_id: str | None = None,
) -> Path:
    fg = FeedGenerator()
    fg.id(feed_id or feed_link)
    fg.title(feed_title)
    fg.link(href=feed_link)

    published_dts = []
    for record in records:
        published_dt = datetime.fromisoformat(record.published)
        published_dts.append(published_dt)
        fe = fg.add_entry()
        # feedgen's own docs: "Two entries in a feed can have the same
        # value for id if they represent the same entry at different
        # points in time" — i.e. id is meant to identify one logical
        # entry across edits, not one URL. Two distinct LinkPost records
        # sharing a `url` but not a `published` (an ordinary linkblog
        # case — resurfacing a link on a different day, see plan.md Risk
        # Area 4) are NOT the same logical entry, so `id` must include
        # `published` too — an id of `record.url` alone would make feed
        # readers that dedupe on id collapse the resurfaced post into
        # the original instead of showing it as a new entry.
        fe.id(f"{record.url}#{record.published}")
        fe.title(record.url)
        fe.link(href=record.url)
        fe.published(published_dt)
        # feedgen defaults an entry's `updated` to datetime.now() at
        # construction time if never set explicitly, which would make
        # generate_feed() non-deterministic across calls. There is no
        # separate "updated" concept on LinkPost, so reuse `published`
        # as the deterministic entry-level updated timestamp.
        fe.updated(published_dt)
        fe.content(record.comment)
        if record.tags:
            fe.category([{"term": t} for t in record.tags])

    fg.updated(max(published_dts) if published_dts else _EPOCH_FALLBACK)

    output_path = Path(output_path)
    fg.atom_file(str(output_path))
    return output_path

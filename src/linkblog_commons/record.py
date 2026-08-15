from dataclasses import dataclass
from datetime import datetime

from linkblog_commons.errors import LinkBlogError

_DEFAULTS = {"comment": "", "tags": ()}


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

    @classmethod
    def from_dict(cls, d: dict) -> "LinkPost":
        try:
            merged = {**_DEFAULTS, **d}
            url = merged.get("url", "")
            published = merged.get("published", "")
            comment = merged.get("comment", "")
            tags = merged.get("tags", ())
            return cls(url=url, published=published, comment=comment, tags=tags)
        except (TypeError, KeyError, AttributeError):
            raise LinkBlogError("invalid_json")

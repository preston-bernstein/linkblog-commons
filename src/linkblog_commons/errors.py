from collections.abc import Sequence
from typing import Literal

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

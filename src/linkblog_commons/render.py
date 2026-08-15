import hashlib
import os
from pathlib import Path

from linkblog_commons.errors import LinkBlogError
from linkblog_commons.record import LinkPost


def _quote(value: str) -> str:
    """Double-quote a YAML scalar, escaping backslashes and quotes.

    Raises LinkBlogError("io_error") if the value contains a raw newline,
    which this single-line-scalar quoting strategy can't safely represent.
    """
    if "\n" in value:
        raise LinkBlogError("io_error")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def hugo_render(record: LinkPost, content_dir: str | Path) -> Path:
    content_dir = Path(content_dir)

    if not content_dir.is_dir() or not os.access(content_dir, os.W_OK):
        raise LinkBlogError("io_error")

    digest = hashlib.sha256(
        f"{record.url}|{record.published}".encode()
    ).hexdigest()
    filename = f"{record.published[:10]}-{digest[:16]}.md"
    out_path = content_dir / filename

    # title and url are both derived from record.url (LinkPost has no
    # separate title field — see plan.md's title-source design decision).
    quoted_url = _quote(record.url)
    tags = ", ".join(_quote(tag) for tag in record.tags)

    front_matter = (
        "---\n"
        f"title: {quoted_url}\n"
        f"url: {quoted_url}\n"
        f"published: \"{record.published}\"\n"
        f"tags: [{tags}]\n"
        "---\n"
    )

    content = front_matter + record.comment

    out_path.write_text(content, encoding="utf-8")

    return out_path

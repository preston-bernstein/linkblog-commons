import hashlib
from pathlib import Path

import pytest

from linkblog_commons.errors import LinkBlogError
from linkblog_commons.record import LinkPost
from linkblog_commons.render import _quote, hugo_render

VALID_URL = "https://example.com/post"
VALID_PUBLISHED = "2026-08-15T10:00:00+00:00"


def make_record(**overrides) -> LinkPost:
    kwargs = {
        "url": VALID_URL,
        "published": VALID_PUBLISHED,
        "comment": "Some commentary.",
        "tags": ("tag-a", "tag-b"),
    }
    kwargs.update(overrides)
    return LinkPost(**kwargs)


def split_front_matter(text: str) -> tuple[list[str], str]:
    """Delimit front matter the way Hugo would: the document must open with
    a '---' line, front matter runs up to the next line that is *exactly*
    '---', and everything after that closing line is body -- regardless of
    what the body itself contains.
    """
    lines = text.split("\n")
    assert lines[0] == "---", "document must open with a '---' delimiter"
    for i in range(1, len(lines)):
        if lines[i] == "---":
            front_matter_lines = lines[1:i]
            body = "\n".join(lines[i + 1:])
            return front_matter_lines, body
    raise AssertionError("no closing '---' delimiter found")


def expected_filename(record: LinkPost) -> str:
    digest = hashlib.sha256(f"{record.url}|{record.published}".encode()).hexdigest()
    return f"{record.published[:10]}-{digest[:16]}.md"


# 1. Valid record + existing temp dir -> exactly one .md file; front matter
#    has title (= url), url, published, tags; body has the comment.
def test_valid_record_writes_single_md_file_with_expected_front_matter(tmp_path):
    record = make_record()
    out_path = hugo_render(record, tmp_path)

    md_files = list(tmp_path.glob("*.md"))
    assert md_files == [out_path]
    assert out_path.name == expected_filename(record)

    text = out_path.read_text(encoding="utf-8")
    front_matter_lines, body = split_front_matter(text)

    assert f'title: "{record.url}"' in front_matter_lines
    assert f'url: "{record.url}"' in front_matter_lines
    assert f'published: "{record.published}"' in front_matter_lines

    tags_line = next(line for line in front_matter_lines if line.startswith("tags:"))
    for tag in record.tags:
        assert f'"{tag}"' in tags_line

    assert body == record.comment


# 2. The SAME record rendered twice to the same directory produces the SAME
#    filename both times, succeeds silently both times, and the content is
#    the same too.
def test_rendering_same_record_twice_is_idempotent(tmp_path):
    record = make_record()

    out_path_1 = hugo_render(record, tmp_path)
    content_1 = out_path_1.read_text(encoding="utf-8")

    out_path_2 = hugo_render(record, tmp_path)
    content_2 = out_path_2.read_text(encoding="utf-8")

    assert out_path_1 == out_path_2
    assert content_1 == content_2
    assert list(tmp_path.glob("*.md")) == [out_path_1]


# 3. TWO DIFFERENT records sharing the same (url, published) pair produce
#    the SAME filename -- documented, intentional collision behavior. The
#    second render silently supersedes the first's file, not an error.
def test_records_sharing_url_and_published_collide_on_filename(tmp_path):
    record_a = make_record(comment="first version", tags=("a",))
    record_b = make_record(comment="second version, supersedes first", tags=("b",))
    assert record_a.url == record_b.url
    assert record_a.published == record_b.published
    assert record_a.comment != record_b.comment

    out_path_a = hugo_render(record_a, tmp_path)
    out_path_b = hugo_render(record_b, tmp_path)

    assert out_path_a == out_path_b
    assert list(tmp_path.glob("*.md")) == [out_path_b]

    final_content = out_path_b.read_text(encoding="utf-8")
    assert record_b.comment in final_content
    assert record_a.comment not in final_content


# 4. Two records with the SAME url but DIFFERENT published values produce
#    DIFFERENT filenames.
def test_same_url_different_published_yields_different_filenames(tmp_path):
    record_a = make_record(published="2026-08-15T10:00:00+00:00")
    record_b = make_record(published="2026-08-16T10:00:00+00:00")
    assert record_a.url == record_b.url
    assert record_a.published != record_b.published

    out_path_a = hugo_render(record_a, tmp_path)
    out_path_b = hugo_render(record_b, tmp_path)

    assert out_path_a != out_path_b
    assert {p.name for p in tmp_path.glob("*.md")} == {out_path_a.name, out_path_b.name}


# 5. Calling hugo_render() with a content_dir that does not exist raises
#    LinkBlogError("io_error") and does NOT create the directory.
def test_missing_content_dir_raises_io_error_and_does_not_create_it(tmp_path):
    missing_dir = tmp_path / "does" / "not" / "exist"
    assert not missing_dir.exists()

    with pytest.raises(LinkBlogError) as exc_info:
        hugo_render(make_record(), missing_dir)

    assert exc_info.value.code == "io_error"
    assert not missing_dir.exists()
    assert not (tmp_path / "does").exists()


# 6. A comment containing a bare '---' line and a colon does not corrupt the
#    front matter -- the front matter still parses/delimits correctly.
def test_comment_with_bare_delimiter_and_colon_does_not_corrupt_front_matter(tmp_path):
    tricky_comment = (
        "Intro line.\n"
        "---\n"
        "key: value inside the comment, not YAML\n"
        "Trailing line."
    )
    record = make_record(comment=tricky_comment)

    out_path = hugo_render(record, tmp_path)
    text = out_path.read_text(encoding="utf-8")

    front_matter_lines, body = split_front_matter(text)

    # The closing delimiter must be render.py's own fixed closing line (the
    # first '---' after the opening one) -- the comment's bare '---' must
    # land in the body, not be mistaken for part of the front matter.
    assert f'title: "{record.url}"' in front_matter_lines
    assert f'url: "{record.url}"' in front_matter_lines
    assert f'published: "{record.published}"' in front_matter_lines
    assert not any("key: value" in line for line in front_matter_lines)

    assert body == tricky_comment
    assert "key: value inside the comment" in body


# 8. _quote() raises io_error on a raw newline, and escapes backslashes and
#    double quotes so the resulting scalar round-trips as a single line.
def test_quote_raises_io_error_on_raw_newline():
    with pytest.raises(LinkBlogError) as exc_info:
        _quote("line one\nline two")
    assert exc_info.value.code == "io_error"


def test_quote_escapes_backslashes_and_double_quotes():
    assert _quote(r"a\b") == r'"a\\b"'
    assert _quote('say "hi"') == r'"say \"hi\""'
    assert _quote(r'\"') == r'"\\\""'


# 9. A URL containing a raw newline propagates through hugo_render() as an
#    io_error (title/url front-matter fields are both quoted via _quote()).
def test_render_url_with_newline_raises_io_error(tmp_path):
    record = make_record(url="https://example.com/post\nmalicious")
    with pytest.raises(LinkBlogError) as exc_info:
        hugo_render(record, tmp_path)
    assert exc_info.value.code == "io_error"
    assert list(tmp_path.glob("*.md")) == []


# 10. hugo_render() raises io_error when content_dir exists but is not
#     writable -- the guard is "not is_dir() OR not writable", not AND, so a
#     read-only existing directory must still fail rather than silently
#     attempting (and failing) the write.
def test_existing_but_unwritable_content_dir_raises_io_error(tmp_path):
    content_dir = tmp_path / "readonly"
    content_dir.mkdir()
    content_dir.chmod(0o500)
    try:
        with pytest.raises(LinkBlogError) as exc_info:
            hugo_render(make_record(), content_dir)
        assert exc_info.value.code == "io_error"
    finally:
        content_dir.chmod(0o700)


# 11. hugo_render() never writes anywhere except the given content_dir.
def test_render_writes_only_inside_content_dir(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    sibling_dir = tmp_path / "sibling"
    sibling_dir.mkdir()

    cwd_before = set(Path.cwd().iterdir())
    sibling_before = set(sibling_dir.iterdir())
    tmp_path_top_before = {p.name for p in tmp_path.iterdir()}

    out_path = hugo_render(make_record(), content_dir)

    assert out_path.parent == content_dir
    assert set(sibling_dir.iterdir()) == sibling_before
    assert set(Path.cwd().iterdir()) == cwd_before
    assert {p.name for p in tmp_path.iterdir()} == tmp_path_top_before
    assert list(content_dir.glob("*.md")) == [out_path]

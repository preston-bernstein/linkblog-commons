import pytest

from linkblog_commons.errors import LinkBlogError
from linkblog_commons.record import LinkPost

VALID_URL = "https://example.com/post"
VALID_PUBLISHED = "2026-08-15T10:00:00+00:00"


def test_empty_comment_is_legal():
    post = LinkPost(url=VALID_URL, published=VALID_PUBLISHED, comment="")
    assert post.comment == ""


def test_missing_url_raises_missing_fields():
    with pytest.raises(LinkBlogError) as exc_info:
        LinkPost(url="", published=VALID_PUBLISHED)
    err = exc_info.value
    assert err.code == "missing_fields"
    assert "url" in err.fields


def test_missing_published_raises_missing_fields():
    with pytest.raises(LinkBlogError) as exc_info:
        LinkPost(url=VALID_URL, published="")
    err = exc_info.value
    assert err.code == "missing_fields"
    assert "published" in err.fields


def test_whitespace_only_url_is_treated_as_missing():
    with pytest.raises(LinkBlogError) as exc_info:
        LinkPost(url="   ", published=VALID_PUBLISHED)
    err = exc_info.value
    assert err.code == "missing_fields"
    assert "url" in err.fields


def test_whitespace_only_published_is_treated_as_missing():
    with pytest.raises(LinkBlogError) as exc_info:
        LinkPost(url=VALID_URL, published="   ")
    err = exc_info.value
    assert err.code == "missing_fields"
    assert "published" in err.fields


def test_unparseable_published_raises_invalid_timestamp():
    with pytest.raises(LinkBlogError) as exc_info:
        LinkPost(url=VALID_URL, published="not-a-date")
    err = exc_info.value
    assert err.code == "invalid_timestamp"
    assert "published" in err.fields


def test_timezone_naive_published_raises_invalid_timestamp():
    # Parseable ISO-8601, but no UTC offset — feedgen crashes deep inside
    # on a naive datetime if this isn't caught here at construction time.
    with pytest.raises(LinkBlogError) as exc_info:
        LinkPost(url=VALID_URL, published="2026-08-15T10:00:00")
    err = exc_info.value
    assert err.code == "invalid_timestamp"
    assert "published" in err.fields


def test_tags_list_coerced_to_tuple_and_hashable():
    post = LinkPost(url=VALID_URL, published=VALID_PUBLISHED, tags=["a", "b"])
    assert isinstance(post.tags, tuple)
    assert post.tags == ("a", "b")
    # Must be hashable now that tags is a tuple.
    hash(post)


def test_from_dict_full_valid_dict_matches_direct_construction():
    d = {
        "url": VALID_URL,
        "published": VALID_PUBLISHED,
        "comment": "hello",
        "tags": ["x", "y"],
    }
    from_dict_post = LinkPost.from_dict(d)
    direct_post = LinkPost(
        url=VALID_URL, published=VALID_PUBLISHED, comment="hello", tags=["x", "y"]
    )
    assert from_dict_post == direct_post


def test_from_dict_defaults_missing_comment_and_tags():
    d = {"url": VALID_URL, "published": VALID_PUBLISHED}
    post = LinkPost.from_dict(d)
    assert post.comment == ""
    assert post.tags == ()


def test_from_dict_missing_required_key_propagates_missing_fields():
    d = {"published": VALID_PUBLISHED}
    with pytest.raises(LinkBlogError) as exc_info:
        LinkPost.from_dict(d)
    err = exc_info.value
    assert err.code == "missing_fields"
    assert "url" in err.fields


def test_from_dict_missing_published_propagates_missing_fields():
    d = {"url": VALID_URL}
    with pytest.raises(LinkBlogError) as exc_info:
        LinkPost.from_dict(d)
    err = exc_info.value
    assert err.code == "missing_fields"
    assert "published" in err.fields


@pytest.mark.parametrize("malformed", [["not", "a", "dict"], "just a string"])
def test_from_dict_malformed_top_level_shape_raises_invalid_json(malformed):
    with pytest.raises(LinkBlogError) as exc_info:
        LinkPost.from_dict(malformed)
    assert exc_info.value.code == "invalid_json"

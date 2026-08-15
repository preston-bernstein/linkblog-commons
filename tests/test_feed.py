import xml.etree.ElementTree as ET

from linkblog_commons.feed import generate_feed
from linkblog_commons.record import LinkPost

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _entries(tree_root):
    return tree_root.findall(f"{ATOM_NS}entry")


def _make_records(n: int) -> list[LinkPost]:
    records = []
    for i in range(n):
        records.append(
            LinkPost(
                url=f"https://example.com/post-{i}",
                published=f"2024-01-0{i + 1}T00:00:00+00:00",
                comment=f"comment number {i}",
                tags=("tag-a", "tag-b") if i % 2 == 0 else (),
            )
        )
    return records


def test_generate_feed_produces_well_formed_xml_with_exact_entry_count(tmp_path):
    records = _make_records(3)
    output_path = tmp_path / "feed.xml"

    result_path = generate_feed(
        records,
        output_path,
        feed_title="My Link Blog",
        feed_link="https://example.com/",
    )

    assert result_path == output_path
    tree = ET.parse(output_path)
    root = tree.getroot()
    entries = _entries(root)
    assert len(entries) == 3


def test_feed_entries_contain_comment_content(tmp_path):
    records = [
        LinkPost(
            url="https://example.com/a",
            published="2024-01-01T00:00:00+00:00",
            comment="this is the actual comment body",
            tags=("news",),
        ),
    ]
    output_path = tmp_path / "feed.xml"

    generate_feed(
        records,
        output_path,
        feed_title="My Link Blog",
        feed_link="https://example.com/",
    )

    tree = ET.parse(output_path)
    root = tree.getroot()
    entries = _entries(root)
    assert len(entries) == 1
    content_el = entries[0].find(f"{ATOM_NS}content")
    assert content_el is not None
    assert content_el.text == "this is the actual comment body"


def test_record_with_empty_comment_feeds_through_without_error(tmp_path):
    records = [
        LinkPost(
            url="https://example.com/empty-comment",
            published="2024-01-01T00:00:00+00:00",
            comment="",
        ),
    ]
    output_path = tmp_path / "feed.xml"

    generate_feed(
        records,
        output_path,
        feed_title="My Link Blog",
        feed_link="https://example.com/",
    )

    tree = ET.parse(output_path)
    root = tree.getroot()
    entries = _entries(root)
    assert len(entries) == 1


def test_generate_feed_with_empty_records_list_succeeds(tmp_path):
    output_path = tmp_path / "feed.xml"

    generate_feed(
        [],
        output_path,
        feed_title="My Link Blog",
        feed_link="https://example.com/",
    )

    tree = ET.parse(output_path)
    root = tree.getroot()
    entries = _entries(root)
    assert len(entries) == 0


def test_feed_entry_published_matches_record(tmp_path):
    records = [
        LinkPost(
            url="https://example.com/a",
            published="2024-03-05T12:30:00+00:00",
            comment="hello",
        ),
    ]
    output_path = tmp_path / "feed.xml"

    generate_feed(
        records,
        output_path,
        feed_title="My Link Blog",
        feed_link="https://example.com/",
    )

    tree = ET.parse(output_path)
    root = tree.getroot()
    entries = _entries(root)
    published_el = entries[0].find(f"{ATOM_NS}published")
    assert published_el is not None
    assert published_el.text.startswith("2024-03-05T12:30:00")


def test_feed_entry_includes_category_terms_for_tagged_record(tmp_path):
    records = [
        LinkPost(
            url="https://example.com/a",
            published="2024-01-01T00:00:00+00:00",
            comment="hello",
            tags=("news", "tech"),
        ),
    ]
    output_path = tmp_path / "feed.xml"

    generate_feed(
        records,
        output_path,
        feed_title="My Link Blog",
        feed_link="https://example.com/",
    )

    tree = ET.parse(output_path)
    root = tree.getroot()
    entries = _entries(root)
    category_terms = {
        el.get("term") for el in entries[0].findall(f"{ATOM_NS}category")
    }
    assert category_terms == {"news", "tech"}


def test_entry_id_includes_published_so_resurfaced_urls_stay_distinct(tmp_path):
    # Two distinct records sharing a url but not a published date (resurfacing
    # a link on a different day, see plan.md Risk Area 4) must get distinct
    # atom:id values -- an id of url alone would make feed readers that
    # dedupe on id collapse the second post into the first.
    records = [
        LinkPost(
            url="https://example.com/a",
            published="2024-01-01T00:00:00+00:00",
            comment="first time",
        ),
        LinkPost(
            url="https://example.com/a",
            published="2024-02-01T00:00:00+00:00",
            comment="resurfaced",
        ),
    ]
    output_path = tmp_path / "feed.xml"

    generate_feed(
        records,
        output_path,
        feed_title="My Link Blog",
        feed_link="https://example.com/",
    )

    tree = ET.parse(output_path)
    root = tree.getroot()
    entries = _entries(root)
    assert len(entries) == 2
    ids = {el.find(f"{ATOM_NS}id").text for el in entries}
    assert len(ids) == 2


def test_empty_records_list_feed_updated_is_epoch_fallback(tmp_path):
    output_path = tmp_path / "feed.xml"

    generate_feed(
        [],
        output_path,
        feed_title="My Link Blog",
        feed_link="https://example.com/",
    )

    tree = ET.parse(output_path)
    root = tree.getroot()
    updated_el = root.find(f"{ATOM_NS}updated")
    assert updated_el is not None
    assert updated_el.text.startswith("1970-01-01T00:00:00")


def test_generate_feed_is_deterministic_across_calls(tmp_path):
    records = _make_records(2)
    output_path_1 = tmp_path / "feed1.xml"
    output_path_2 = tmp_path / "feed2.xml"

    generate_feed(
        records,
        output_path_1,
        feed_title="My Link Blog",
        feed_link="https://example.com/",
        feed_id="https://example.com/feed-id",
    )
    generate_feed(
        records,
        output_path_2,
        feed_title="My Link Blog",
        feed_link="https://example.com/",
        feed_id="https://example.com/feed-id",
    )

    assert output_path_1.read_bytes() == output_path_2.read_bytes()

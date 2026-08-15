from linkblog_commons.errors import LinkBlogError


def test_str_with_no_fields_is_just_the_code():
    err = LinkBlogError("io_error")
    assert str(err) == "io_error"


def test_str_with_fields_lists_them_comma_separated():
    err = LinkBlogError("missing_fields", fields=["url", "published"])
    assert str(err) == "missing_fields: url, published"

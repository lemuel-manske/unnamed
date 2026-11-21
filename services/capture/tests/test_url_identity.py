import pytest

from domain import InvalidURLIdentity, identify_url


def test_identity_normalizes_scheme_host_default_port_and_dot_segments() -> None:
    identity = identify_url("HTTPS://EXAMPLE.COM:443/a/../Course/%7euser?q=2&q=1#section")

    assert identity.fetch_url == "https://example.com/Course/~user?q=2&q=1"
    assert identity.navigation_url == identity.fetch_url
    assert identity.discovery_url.endswith("#section")


def test_identity_preserves_path_case_trailing_slash_and_query_order() -> None:
    course = identify_url("https://example.com/Course?a=1&b=2")
    lowercase = identify_url("https://example.com/course?a=1&b=2")
    trailing_slash = identify_url("https://example.com/Course/?a=1&b=2")
    reordered_query = identify_url("https://example.com/Course?b=2&a=1")

    assert len({course.url_key, lowercase.url_key, trailing_slash.url_key}) == 3
    assert course.url_key != reordered_query.url_key


def test_identity_ignores_ordinary_fragments() -> None:
    first = identify_url("https://example.com/article#introduction")
    second = identify_url("https://example.com/article#conclusion")

    assert first.fetch_url == second.fetch_url
    assert first.navigation_url == second.navigation_url
    assert first.url_key == second.url_key


def test_identity_preserves_hash_routes_as_distinct_navigation_targets() -> None:
    settings = identify_url("https://example.com/#/settings")
    dashboard = identify_url("https://example.com/#/dashboard")
    nested = identify_url("https://example.com/app#!/dashboard")

    assert settings.fetch_url == dashboard.fetch_url
    assert settings.navigation_url.endswith("#/settings")
    assert dashboard.navigation_url.endswith("#/dashboard")
    assert settings.url_key != dashboard.url_key
    assert nested.navigation_url.endswith("#!/dashboard")


def test_identity_normalizes_unreserved_but_not_reserved_percent_escapes() -> None:
    escaped = identify_url("https://example.com/a%7eb%2fc")
    literal = identify_url("https://example.com/a~b%2Fc")

    assert escaped.fetch_url == "https://example.com/a~b%2Fc"
    assert escaped.url_key == literal.url_key


def test_identity_preserves_repeated_path_slashes() -> None:
    identity = identify_url("https://example.com/a//b")

    assert identity.fetch_url == "https://example.com/a//b"


@pytest.mark.parametrize(
    "url",
    (
        "",
        "ftp://example.com/file",
        "https://user:password@example.com/",
        "https://example.com:70000/",
        "https://example.com:0/",
        "/relative/path",
    ),
)
def test_identity_rejects_invalid_navigation_urls(url: str) -> None:
    with pytest.raises(InvalidURLIdentity):
        identify_url(url)

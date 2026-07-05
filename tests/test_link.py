import app.ingest.link as link_mod
from app.ingest.link import inspect_link, is_public_url


def test_is_public_url_accepts_normal_hosts():
    assert is_public_url("https://example.com/a")
    assert is_public_url("http://news.ycombinator.com/item?id=1")
    assert is_public_url("https://youtu.be/abc")


def test_is_public_url_rejects_internal_and_private():
    assert not is_public_url("http://localhost:8000/x")
    assert not is_public_url("http://127.0.0.1/x")
    assert not is_public_url("http://192.168.1.10/x")
    assert not is_public_url("http://10.0.0.5/x")
    assert not is_public_url("http://wiki.corp/page")       # internal suffix
    assert not is_public_url("http://service.internal/api")  # internal suffix
    assert not is_public_url("http://intranet/page")         # bare dotless host
    assert not is_public_url("")


def test_inspect_non_public_link_is_not_fetched(monkeypatch):
    def _boom(url):
        raise AssertionError("should not fetch a non-public link")

    monkeypatch.setattr(link_mod, "fetch_metadata", _boom)
    info = inspect_link("http://localhost/x")
    assert info.public is False
    assert info.reachable is False
    assert info.verified is False
    assert info.title is None


def test_inspect_public_link_extracts_content(monkeypatch):
    monkeypatch.setattr(link_mod, "fetch_metadata", lambda url: {
        "title": "Cool", "image_url": "https://i/x.png",
        "summary": "blurb", "text": "body text",
    })
    info = inspect_link("https://example.com/a")
    assert info.public and info.reachable and info.verified
    assert info.title == "Cool"
    assert info.image_url == "https://i/x.png"
    assert info.text == "body text"


def test_inspect_public_link_that_fails_is_unreachable(monkeypatch):
    monkeypatch.setattr(link_mod, "fetch_metadata", lambda url: {
        "title": None, "image_url": None, "summary": None, "text": None,
    })
    info = inspect_link("https://example.com/dead")
    assert info.public is True
    assert info.reachable is False
    assert info.verified is False


def test_inspect_image_only_page_is_not_verified(monkeypatch):
    # An og:image with no title/summary/text isn't describable content.
    monkeypatch.setattr(link_mod, "fetch_metadata", lambda url: {
        "title": None, "image_url": "https://i/x.png", "summary": None, "text": None,
    })
    info = inspect_link("https://example.com/img")
    assert info.reachable is False

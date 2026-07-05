from unittest.mock import patch

import app.ingest.rss_scanner as scanner
from app.ingest.rss_scanner import entry_image
from app.models import Source, FeedItem
import app.db as db


def test_entry_image_prefers_media_thumbnail():
    entry = {"media_thumbnail": [{"url": "https://img/x.jpg"}], "summary": ""}
    assert entry_image(entry) == "https://img/x.jpg"


def test_entry_image_reads_inline_img_from_summary():
    entry = {"summary": 'text <img src="https://img/inline.png"/> more'}
    assert entry_image(entry) == "https://img/inline.png"


def test_entry_image_none_when_absent():
    assert entry_image({"summary": "no images here"}) is None


class FakeProvider:
    def explain(self, title, text):
        return {"short": f"short {title}", "long": f"long {title}"}


def test_scan_inserts_and_dedupes(session_factory, monkeypatch):
    monkeypatch.setattr(scanner, "fetch_metadata", lambda url: {"image_url": None})
    fake_feed = type("F", (), {"entries": [
        {"link": "https://e.com/1", "title": "One", "summary": "raw"},
        {"link": "https://e.com/1", "title": "One", "summary": "raw"},
    ]})()
    with patch.object(scanner, "feedparser") as fp:
        fp.parse.return_value = fake_feed
        with db.SessionLocal() as s:
            src = Source(kind="rss", name="X", url="https://feed")
            s.add(src); s.commit()
            n = scanner.scan_source(s, src, FakeProvider())
            assert n == 1
            items = s.query(FeedItem).all()
            assert len(items) == 1
            assert items[0].short_summary == "short One"
            assert items[0].long_summary == "long One"
            # article_summary mirrors the short blurb for back-compat.
            assert items[0].article_summary == "short One"
            assert items[0].source_type == "auto"
            assert items[0].shared_by_name == "System Auto-Pull"


def test_scan_falls_back_on_provider_error(session_factory, monkeypatch):
    monkeypatch.setattr(scanner, "fetch_metadata", lambda url: {"image_url": None})
    fake_feed = type("F", (), {"entries": [
        {"link": "https://e.com/2", "title": "Two", "summary": "raw text"},
    ]})()

    class Boom:
        def explain(self, title, text):
            raise RuntimeError("model down")

    with patch.object(scanner, "feedparser") as fp:
        fp.parse.return_value = fake_feed
        with db.SessionLocal() as s:
            src = Source(kind="rss", name="Y", url="https://feed2")
            s.add(src); s.commit()
            scanner.scan_source(s, src, Boom())
            item = s.query(FeedItem).first()
            assert item.short_summary == "raw text"
            assert item.article_summary == "raw text"
            assert item.long_summary is None

from app.models import FeedItem


def test_feeditem_defaults(session_factory):
    with session_factory() as s:
        item = FeedItem(
            content_type="article",
            source_url="https://example.com/a",
            dedup_hash="h1",
            source_type="manual",
            shared_by_name="Alice",
            shared_by_email="alice@x.com",
        )
        s.add(item)
        s.commit()
        s.refresh(item)
        assert item.id is not None
        assert item.views == 0
        assert item.likes == 0
        assert item.status == "published"

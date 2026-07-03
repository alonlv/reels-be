import logging

import feedparser

from app.db import SessionLocal
from app.ingest.dedupe import dedup_hash
from app.ingest.scraper import fetch_metadata
from app.llm.factory import get_provider
from app.models import FeedItem, Source

log = logging.getLogger("rss_scanner")


def scan_source(session, source: Source, provider) -> int:
    feed = feedparser.parse(source.url)
    inserted = 0
    for entry in feed.entries[:10]:
        url = entry.get("link")
        title = entry.get("title") or url
        if not url:
            continue
        h = dedup_hash(url, title)
        if session.query(FeedItem).filter_by(dedup_hash=h).first():
            continue
        raw = entry.get("summary", "")
        try:
            summary = provider.summarize(title, raw)
        except Exception as exc:  # noqa: BLE001 — never crash a scan
            log.warning("summarize failed for %s: %s", url, exc)
            summary = raw[:500] or None
        image = fetch_metadata(url)["image_url"]
        session.add(FeedItem(
            content_type="article", source_url=url, dedup_hash=h,
            title=title, article_summary=summary, image_url=image,
            source_type="auto", status="published",
            shared_by_name="System Auto-Pull",
            shared_by_email="system@company.internal",
        ))
        inserted += 1
    session.commit()
    return inserted


def run_scan() -> int:
    provider = get_provider()
    total = 0
    with SessionLocal() as s:
        for source in s.query(Source).filter_by(is_active=True, kind="rss").all():
            try:
                total += scan_source(s, source, provider)
            except Exception as exc:  # noqa: BLE001
                log.warning("scan failed for %s: %s", source.url, exc)
    return total

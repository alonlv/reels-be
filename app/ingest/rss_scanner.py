import calendar
import logging
import re
from datetime import datetime, timezone

import feedparser

from app.db import SessionLocal
from app.ingest.dedupe import dedup_hash
from app.ingest.enrich import enrich
from app.ingest.scraper import fetch_metadata
from app.llm.factory import get_provider
from app.models import FeedItem, Source

log = logging.getLogger("rss_scanner")

_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def entry_image(entry) -> str | None:
    """Pull a thumbnail straight from the feed entry when the feed provides one.

    Feeds commonly carry a related image via media:thumbnail, media:content, an
    image enclosure, or an <img> embedded in the summary/content HTML.
    """
    for key in ("media_thumbnail", "media_content"):
        media = entry.get(key)
        if media and isinstance(media, list) and media[0].get("url"):
            return media[0]["url"]
    for enc in entry.get("enclosures", []) or []:
        if str(enc.get("type", "")).startswith("image") and enc.get("href"):
            return enc["href"]
    html = entry.get("summary", "") or ""
    match = _IMG_SRC_RE.search(html)
    if match:
        return match.group(1)
    return None


def entry_published(entry) -> datetime | None:
    """The source publish date, when the feed provides a parseable one."""
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                return datetime.fromtimestamp(
                    calendar.timegm(parsed), tz=timezone.utc
                ).replace(tzinfo=None)
            except (ValueError, OverflowError, TypeError):
                continue
    return None


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
        short, long, technical, category = enrich(provider, title, raw)
        # Prefer a thumbnail the feed already supplies; else scrape the page.
        image = entry_image(entry) or fetch_metadata(url)["image_url"]
        session.add(FeedItem(
            content_type="article", source_url=url, dedup_hash=h,
            title=title,
            # article_summary keeps mirroring the short blurb for back-compat.
            article_summary=short, short_summary=short, long_summary=long,
            technical_summary=technical,
            category=category, feed="ai_news", image_url=image,
            published_at=entry_published(entry),
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

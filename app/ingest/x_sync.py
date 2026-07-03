import logging

import httpx

from app.config import get_settings
from app.db import SessionLocal
from app.ingest.dedupe import dedup_hash
from app.models import FeedItem, MonitoredXAccount

log = logging.getLogger("x_sync")


def fetch_tweets(x_user_id: str, since_id: str | None, bearer: str) -> list[dict]:
    params = {"max_results": 10}
    if since_id:
        params["since_id"] = since_id
    try:
        resp = httpx.get(
            f"https://api.twitter.com/2/users/{x_user_id}/tweets",
            params=params,
            headers={"authorization": f"Bearer {bearer}"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as exc:  # noqa: BLE001
        log.warning("x fetch failed for %s: %s", x_user_id, exc)
        return []


def sync_account(session, account: MonitoredXAccount, bearer: str) -> int:
    tweets = fetch_tweets(account.x_user_id, account.last_tweet_id, bearer)
    inserted = 0
    newest = account.last_tweet_id
    for tw in tweets:
        tid = tw["id"]
        url = f"https://x.com/i/web/status/{tid}"
        h = dedup_hash(url, tid)
        if session.query(FeedItem).filter_by(dedup_hash=h).first():
            continue
        session.add(FeedItem(
            content_type="x", source_url=url, dedup_hash=h,
            title=tw.get("text", "")[:280], article_summary=tw.get("text"),
            source_type="auto", status="published",
            shared_by_name="System Auto-Pull",
            shared_by_email="system@company.internal",
        ))
        inserted += 1
        if newest is None or int(tid) > int(newest):
            newest = tid
    account.last_tweet_id = newest
    session.commit()
    return inserted


def run_x_sync() -> int:
    bearer = get_settings().x_bearer_token
    if not bearer:
        return 0
    total = 0
    with SessionLocal() as s:
        for acct in s.query(MonitoredXAccount).filter_by(is_active=True).all():
            total += sync_account(s, acct, bearer)
    return total

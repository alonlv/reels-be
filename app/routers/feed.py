import threading

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import FeedItem
from app.schemas import FeedItemOut, FeedItemCreate
from app.ingest.classify import classify_url
from app.ingest.dedupe import dedup_hash
from app.ingest.rss_scanner import run_scan
from app.ingest.scraper import fetch_metadata
from app.ratelimit import rate_limit

router = APIRouter(prefix="/api")

_SORT = {
    "date": FeedItem.created_at.desc(),
    "views": FeedItem.views.desc(),
    "likes": FeedItem.likes.desc(),
}


@router.get("/feed", response_model=list[FeedItemOut])
def get_feed(
    sort_by: str = "date",
    content_type: str | None = None,
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
):
    order = _SORT.get(sort_by, _SORT["date"])
    stmt = select(FeedItem).where(FeedItem.status == "published")
    if content_type:
        stmt = stmt.where(FeedItem.content_type == content_type)
    stmt = stmt.order_by(order).limit(limit)
    return session.execute(stmt).scalars().all()


def _bump(session: Session, feed_id: int, column):
    item = session.get(FeedItem, feed_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not found")
    setattr(item, column, getattr(item, column) + 1)
    session.commit()
    return getattr(item, column)


@router.post("/feed/{feed_id}/view")
def add_view(feed_id: int, session: Session = Depends(get_session)):
    return {"views": _bump(session, feed_id, "views")}


@router.post("/feed/{feed_id}/like")
def add_like(feed_id: int, session: Session = Depends(get_session)):
    return {"likes": _bump(session, feed_id, "likes")}


@router.post("/feed", response_model=FeedItemOut, status_code=status.HTTP_201_CREATED)
def submit_feed(
    payload: FeedItemCreate,
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(rate_limit),
):
    url = payload.url.strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must be http(s)")
    meta = fetch_metadata(url)
    title = payload.title or meta["title"] or url
    summary = payload.description or meta["summary"]
    h = dedup_hash(url, title)
    if session.query(FeedItem).filter_by(dedup_hash=h).first():
        raise HTTPException(status_code=409, detail="duplicate")
    item = FeedItem(
        content_type=classify_url(url),
        source_url=url,
        dedup_hash=h,
        title=title,
        article_summary=summary,
        image_url=meta["image_url"],
        source_type="manual",
        status="published",
        shared_by_name=payload.shared_by_name,
        shared_by_email=payload.shared_by_email,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.post("/scan", status_code=202)
def trigger_scan():
    threading.Thread(target=run_scan, daemon=True).start()
    return {"ok": True}

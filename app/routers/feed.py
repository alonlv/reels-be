import base64
import threading
from uuid import uuid4

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import FeedItem
from app.schemas import FeedItemOut, FeedItemCreate
from app.ingest.categorize import categorize
from app.ingest.classify import classify_url
from app.ingest.dedupe import dedup_hash
from app.ingest.enrich import enrich
from app.ingest.rss_scanner import run_scan
from app.ingest.scraper import fetch_metadata
from app.llm.factory import get_provider
from app.ratelimit import rate_limit

router = APIRouter(prefix="/api")

# ~4 MB decoded; base64 inflates ~33%, so cap the raw upload accordingly.
MAX_PHOTO_BYTES = 4 * 1024 * 1024

_SORT = {
    "date": FeedItem.created_at.desc(),
    "views": FeedItem.views.desc(),
    "likes": FeedItem.likes.desc(),
}


@router.get("/feed", response_model=list[FeedItemOut])
def get_feed(
    sort_by: str = "date",
    content_type: str | None = None,
    category: str | None = None,
    feed: str | None = None,
    limit: int = Query(default=50, le=200, ge=1),
    session: Session = Depends(get_session),
):
    order = _SORT.get(sort_by, _SORT["date"])
    stmt = select(FeedItem).where(FeedItem.status == "published")
    if content_type:
        stmt = stmt.where(FeedItem.content_type == content_type)
    if category:
        stmt = stmt.where(FeedItem.category == category)
    if feed:
        stmt = stmt.where(FeedItem.feed == feed)
    stmt = stmt.order_by(order).limit(limit)
    return session.execute(stmt).scalars().all()


def _bump(session: Session, feed_id: int, column, delta: int = 1, floor: int | None = None):
    item = session.get(FeedItem, feed_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not found")
    value = getattr(item, column) + delta
    if floor is not None:
        value = max(floor, value)
    setattr(item, column, value)
    session.commit()
    return value


@router.post("/feed/{feed_id}/view")
def add_view(feed_id: int, session: Session = Depends(get_session)):
    return {"views": _bump(session, feed_id, "views")}


@router.post("/feed/{feed_id}/like")
def add_like(feed_id: int, session: Session = Depends(get_session)):
    return {"likes": _bump(session, feed_id, "likes")}


@router.post("/feed/{feed_id}/unlike")
def remove_like(feed_id: int, session: Session = Depends(get_session)):
    # Pressing like again removes it; never drops below zero.
    return {"likes": _bump(session, feed_id, "likes", delta=-1, floor=0)}


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
    long = None
    category = categorize(title, summary or "")
    # When asked, let the model write the short/long blurbs + category from the
    # page's own text (fetched description) so manual links read like auto ones.
    if payload.summarize:
        source_text = payload.description or meta["summary"] or title
        llm_short, long, category = enrich(get_provider(), title, source_text)
        summary = llm_short or summary
    h = dedup_hash(url, title)
    if session.query(FeedItem).filter_by(dedup_hash=h).first():
        raise HTTPException(status_code=409, detail="duplicate")
    item = FeedItem(
        content_type=classify_url(url),
        source_url=url,
        dedup_hash=h,
        title=title,
        article_summary=summary,
        short_summary=summary,
        long_summary=long,
        category=category,
        feed="ai_news",
        image_url=meta["image_url"],
        source_type="manual",
        status="published",
        shared_by_name=payload.shared_by_name,
        shared_by_email=payload.shared_by_email,
    )
    session.add(item)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="duplicate")
    session.refresh(item)
    return item


@router.post("/csi", response_model=FeedItemOut, status_code=status.HTTP_201_CREATED)
async def create_csi(
    title: str = Form(...),
    summary: str = Form(""),
    link: str = Form(""),
    use_llm: bool = Form(False),
    shared_by_name: str = Form("CSI"),
    photo: UploadFile | None = File(None),
    session: Session = Depends(get_session),
    _: None = Depends(rate_limit),
):
    """Create a CSI-feed item from user-provided title/summary/photo/link.

    The photo is stored inline as a data URI. When ``use_llm`` is set the model
    rewrites the summary into short/long blurbs and picks a category.
    """
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    link = (link or "").strip()
    if link and not link.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="link must be http(s)")

    image_data = None
    if photo is not None:
        content = await photo.read()
        if len(content) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=413, detail="photo too large (max 4MB)")
        if content:
            mime = photo.content_type or "image/jpeg"
            image_data = f"data:{mime};base64," + base64.b64encode(content).decode()

    short = summary.strip() or None
    long = None
    category = categorize(title, summary)
    if use_llm:
        llm_short, long, category = enrich(get_provider(), title, summary or title)
        short = llm_short or short

    # Dedupe by link when given; otherwise every manual entry is distinct.
    h = dedup_hash(link or f"csi:{uuid4()}", title)
    item = FeedItem(
        content_type="article",
        source_url=link,
        dedup_hash=h,
        title=title,
        article_summary=short,
        short_summary=short,
        long_summary=long,
        category=category,
        feed="csi",
        image_data=image_data,
        source_type="manual",
        status="published",
        shared_by_name=shared_by_name.strip() or "CSI",
        shared_by_email="csi@company.internal",
    )
    session.add(item)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="duplicate")
    session.refresh(item)
    return item


@router.post("/scan", status_code=202)
def trigger_scan():
    threading.Thread(target=run_scan, daemon=True).start()
    return {"ok": True}

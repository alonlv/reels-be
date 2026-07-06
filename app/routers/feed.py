import base64
import threading
from uuid import uuid4

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Query, Request,
    UploadFile, status,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.db as db
from app.config import get_settings
from app.db import get_session
from app.deps import require_admin
from app.models import FeedItem
from app.schemas import (
    FeedItemCreate, FeedItemOut, FeedItemPatch, LoginRequest, LoginResponse,
)
from app.ingest.categorize import categorize
from app.ingest.classify import classify_url
from app.ingest.dedupe import dedup_hash
from app.ingest.enrich import enrich
from app.ingest.link import inspect_link
from app.ingest.rss_scanner import run_scan
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


def _requires_verification(content_type: str, info) -> bool:
    """Whether a link must be rejected because it couldn't be verified.

    Only plain public articles have to actually load: YouTube/X/Reddit render
    from their platform embed (which carries the content), and those hosts often
    block scrapers, so a failed metadata fetch there isn't fatal. Non-public
    (internal) links are never verifiable and are kept as given.
    """
    return content_type == "article" and info.public and not info.reachable


def _enrich_and_update(item_id: int, title: str, text: str) -> None:
    """Run the model and patch an item's summaries/category in the background.

    LLM generation is too slow to run inside the request (it would blow past
    gateway timeouts), so items are created immediately and enriched here.
    """
    short, long, technical, category = enrich(get_provider(), title, text)
    with db.SessionLocal() as session:
        item = session.get(FeedItem, item_id)
        if item is None:
            return
        if short:
            item.short_summary = short
            item.article_summary = short
        item.long_summary = long
        item.technical_summary = technical
        if category:
            item.category = category
        session.commit()


def _enrich_in_background(item_id: int, title: str, text: str) -> None:
    threading.Thread(
        target=_enrich_and_update, args=(item_id, title, text), daemon=True
    ).start()


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
    # Verify and read the link rather than storing the bare URL. A public article
    # that won't load is rejected here so a dead/blocked page never lands in the
    # feed; a non-public (internal) link can't be verified and is kept as given.
    content_type = classify_url(url)
    info = inspect_link(url)
    if _requires_verification(content_type, info):
        raise HTTPException(
            status_code=400,
            detail="could not verify the link — it appears to be dead or blocked",
        )
    title = payload.title or info.title or url
    summary = payload.description or info.summary
    category = categorize(title, summary or "")
    h = dedup_hash(url, title)
    if session.query(FeedItem).filter_by(dedup_hash=h).first():
        raise HTTPException(status_code=409, detail="duplicate")
    item = FeedItem(
        content_type=content_type,
        source_url=url,
        dedup_hash=h,
        title=title,
        article_summary=summary,
        short_summary=summary,
        category=category,
        feed="ai_news",
        image_url=info.image_url,
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
    # Return immediately; the model rewrites the blurbs/category out of band so
    # a slow LLM never times out the request. Feed it the extracted page text so
    # it summarises what's actually on the page, not just the URL/blurb.
    if payload.summarize:
        _enrich_in_background(
            item.id, title, info.text or payload.description or info.summary or title
        )
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

    # Same rule as the submit-a-link flow: a public link is verified and read;
    # an internal/private link can't be reached, so it's kept as given. CSI just
    # happens to lean on the second case more (internal reports, wiki links).
    info = inspect_link(link)
    if link and _requires_verification(classify_url(link), info):
        raise HTTPException(
            status_code=400,
            detail="could not verify the link — it appears to be dead or blocked",
        )

    image_data = None
    if photo is not None:
        content = await photo.read()
        if len(content) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=413, detail="photo too large (max 4MB)")
        if content:
            mime = photo.content_type or "image/jpeg"
            image_data = f"data:{mime};base64," + base64.b64encode(content).decode()

    # Prefer the user's own summary; fall back to what we extracted from a
    # verified link so the card still says something.
    short = summary.strip() or info.summary or None
    category = categorize(title, summary or info.summary or "")
    # A verified link's social image backfills the card when no photo was given.
    image_url = info.image_url if image_data is None else None

    # Dedupe by link when given; otherwise every manual entry is distinct.
    h = dedup_hash(link or f"csi:{uuid4()}", title)
    item = FeedItem(
        content_type="article",
        source_url=link,
        dedup_hash=h,
        title=title,
        article_summary=short,
        short_summary=short,
        category=category,
        feed="csi",
        image_url=image_url,
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
    # Enrich out of band so a slow model never times out the upload request.
    # Feed the model the extracted page text when we verified a link.
    if use_llm:
        _enrich_in_background(item.id, title, info.text or summary or title)
    return item


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    """Legacy username + admin-password auth, kept as the SSO fallback.

    Gated behind the PASSWORD_AUTH_ENABLED feature flag: the admin password
    grants the admin token; everyone else is a named guest. Not production-grade
    — a single shared admin."""
    settings = get_settings()
    if not settings.password_auth_enabled:
        raise HTTPException(status_code=403, detail="password login is disabled; use SSO")
    name = (payload.username or "guest").strip() or "guest"
    admin_pw = settings.admin_password
    if payload.password and payload.password == admin_pw:
        return LoginResponse(name=name or "admin", role="admin", token=admin_pw)
    if payload.password:
        raise HTTPException(status_code=401, detail="wrong admin password")
    return LoginResponse(name=name, role="guest", token=None)


@router.patch("/feed/{feed_id}", response_model=FeedItemOut)
def edit_feed(
    feed_id: int,
    patch: FeedItemPatch,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
):
    item = session.get(FeedItem, feed_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not found")
    fields = patch.model_dump(exclude_unset=True)
    if "short_summary" in fields:
        item.article_summary = fields["short_summary"]
    for key, value in fields.items():
        setattr(item, key, value)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/feed/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feed(
    feed_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
):
    item = session.get(FeedItem, feed_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not found")
    session.delete(item)
    session.commit()


@router.post("/scan", status_code=202)
def trigger_scan(_: None = Depends(require_admin)):
    threading.Thread(target=run_scan, daemon=True).start()
    return {"ok": True}

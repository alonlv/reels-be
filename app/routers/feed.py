from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import FeedItem
from app.schemas import FeedItemOut

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

import threading

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.ingest.rss_scanner import run_scan
from app.models import Source
from app.ratelimit import rate_limit
from app.schemas import SourceCreate, SourceOut

router = APIRouter(prefix="/api/sources")


@router.get("", response_model=list[SourceOut])
def list_sources(session: Session = Depends(get_session)):
    stmt = select(Source).order_by(Source.id)
    return session.execute(stmt).scalars().all()


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def add_source(
    payload: SourceCreate,
    session: Session = Depends(get_session),
    _: None = Depends(rate_limit),
):
    url = payload.url.strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must be http(s)")
    name = payload.name.strip() or url
    existing = session.query(Source).filter_by(url=url).first()
    if existing:
        existing.name = name
        existing.kind = payload.kind
        existing.is_active = True
        item = existing
    else:
        item = Source(kind=payload.kind, name=name, url=url, is_active=True)
        session.add(item)
    session.commit()
    session.refresh(item)
    # Pull from the new source right away so it populates without waiting for cron.
    threading.Thread(target=run_scan, daemon=True).start()
    return item


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: int, session: Session = Depends(get_session)):
    item = session.get(Source, source_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not found")
    session.delete(item)
    session.commit()

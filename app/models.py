from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FeedItem(Base):
    __tablename__ = "feed_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_type: Mapped[str] = mapped_column(String(16))
    source_url: Mapped[str] = mapped_column(String(2048))
    dedup_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    author: Mapped[str | None] = mapped_column(String(256), nullable=True)
    article_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # LLM-generated two-layer explanation: a one-line blurb (short) shown on the
    # card, and a deep-dive (long) revealed by "see more" in the feed.
    short_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Technical deep-dive ("read technical info"), separate from the general
    # "read more" (long_summary).
    technical_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Topic bucket (research/product/business/policy/open-source/tutorial/other).
    category: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    # When the underlying item was published at the source (vs created_at, when
    # we ingested it into the feed).
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Which feed this item belongs to: "ai_news" (auto/curated) or "csi" (manual).
    feed: Mapped[str] = mapped_column(String(16), default="ai_news", index=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # Inline image (data: URI) for user-uploaded photos, e.g. CSI entries.
    image_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="published")
    shared_by_name: Mapped[str] = mapped_column(String(256))
    shared_by_email: Mapped[str] = mapped_column(String(256))
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class MonitoredXAccount(Base):
    __tablename__ = "monitored_x_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    x_handle: Mapped[str] = mapped_column(String(64), unique=True)
    x_user_id: Mapped[str] = mapped_column(String(64))
    last_tweet_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(256))
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

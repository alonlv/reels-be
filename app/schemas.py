from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FeedItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content_type: str
    source_url: str
    title: str | None
    author: str | None
    article_summary: str | None
    short_summary: str | None
    long_summary: str | None
    technical_summary: str | None
    category: str | None
    feed: str
    image_url: str | None
    image_data: str | None
    source_type: str
    status: str
    shared_by_name: str
    shared_by_email: str
    views: int
    likes: int
    created_at: datetime
    published_at: datetime | None


class FeedItemCreate(BaseModel):
    url: str
    title: str | None = None
    description: str | None = None
    summarize: bool = False
    shared_by_name: str = "Anonymous"
    shared_by_email: str = "anonymous@company.internal"


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    name: str
    url: str
    is_active: bool


class SourceCreate(BaseModel):
    name: str
    url: str
    kind: str = "rss"


class LoginRequest(BaseModel):
    username: str = "guest"
    password: str | None = None


class LoginResponse(BaseModel):
    name: str
    role: str  # "admin" | "guest"
    token: str | None = None


class FeedItemPatch(BaseModel):
    title: str | None = None
    short_summary: str | None = None
    long_summary: str | None = None
    technical_summary: str | None = None
    category: str | None = None

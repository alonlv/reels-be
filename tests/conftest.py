import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db as db
from app.db import Base


@pytest.fixture
def session_factory(tmp_path):
    url = f"sqlite:///{tmp_path/'test.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)
    import app.models  # noqa: F401
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    # Point the app's SessionLocal at this test engine.
    db.SessionLocal = factory
    return factory


@pytest.fixture
def client(session_factory):
    from app.main import create_app
    return TestClient(create_app())

import os
import io
import pytest
from PIL import Image as PILImage
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.database import Base, get_db
from backend.app.models.user import User
from backend.app.models.api_key import ApiKey
from backend.app.auth.security import hash_password, generate_api_key, hash_api_key, mask_api_key
from backend.app.storage.factory import get_storage
from backend.app.services.rate_limiter import rate_limiter

# In-memory SQLite engine for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    import backend.app.database
    import backend.app.api.v1.images
    backend.app.database.SessionLocal = TestingSessionLocal
    backend.app.api.v1.images.SessionLocal = TestingSessionLocal
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    try:
        if transaction.is_active:
            transaction.rollback()
    except Exception:
        pass
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    rate_limiter.reset()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    user = db_session.query(User).filter((User.username == "tester") | (User.email == "tester@example.com")).first()
    if not user:
        user = User(
            email="tester@example.com",
            username="tester",
            hashed_password=hash_password("testpass123"),
            is_active=True,
            is_admin=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture
def test_api_key(db_session, test_user):
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    masked = mask_api_key(raw_key)

    api_key_obj = ApiKey(
        user_id=test_user.id,
        name="Automated Test Key",
        key_hash=key_hash,
        masked_key=masked,
        scopes="images:upload,images:read,images:delete",
        is_active=True
    )
    db_session.add(api_key_obj)
    db_session.commit()
    db_session.refresh(api_key_obj)
    return raw_key, api_key_obj


@pytest.fixture
def sample_png_bytes():
    """Generates valid 100x100 PNG image bytes."""
    buf = io.BytesIO()
    img = PILImage.new("RGB", (100, 100), color=(73, 109, 137))
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_jpeg_bytes():
    """Generates valid 100x100 JPEG image bytes."""
    buf = io.BytesIO()
    img = PILImage.new("RGB", (100, 100), color=(255, 100, 50))
    img.save(buf, format="JPEG")
    return buf.getvalue()

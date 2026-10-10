from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.app.config import settings

# Engine setup
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI database dependency providing a transactional DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initializes tables in database."""
    # Import all models to ensure they are registered with Base metadata
    from backend.app.models import user, api_key, image, api_request  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Ensure status column exists in images table (for existing databases)
    try:
        with engine.begin() as conn:
            from sqlalchemy import text
            res = conn.execute(text("PRAGMA table_info(images)"))
            cols = [row[1] for row in res.fetchall()]
            if "status" not in cols and len(cols) > 0:
                conn.execute(text("ALTER TABLE images ADD COLUMN status VARCHAR(20) DEFAULT 'active'"))
    except Exception:
        pass

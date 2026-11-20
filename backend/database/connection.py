import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()


def sqlalchemy_url(url: str | None) -> str | None:
    """Hosts such as Neon hand out postgresql://... (or postgres://...). Without a driver name
    SQLAlchemy would look for psycopg2, which is not installed, so name psycopg (version 3) here."""
    if url:
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = sqlalchemy_url(os.getenv("DATABASE_URL"))

# pool_pre_ping: a hosted database (Neon's free plan) suspends after a few idle minutes and drops its
# connections; checking a connection before use replaces a dead one instead of failing the request.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

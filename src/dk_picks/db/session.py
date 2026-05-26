from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from dk_picks.config import settings
from dk_picks.db.models import Base


def get_engine(db_path: Path | None = None):
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", echo=False)


def get_session(db_path: Path | None = None) -> Session:
    engine = get_engine(db_path)
    return sessionmaker(bind=engine)()


def init_db(db_path: Path | None = None) -> None:
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)

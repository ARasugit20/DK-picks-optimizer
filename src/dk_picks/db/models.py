from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sport: Mapped[str] = mapped_column(String(32), index=True)
    event_id: Mapped[str] = mapped_column(String(128), index=True)
    home_team: Mapped[str] = mapped_column(String(64))
    away_team: Mapped[str] = mapped_column(String(64))
    commence_time: Mapped[datetime] = mapped_column(DateTime)
    market: Mapped[str] = mapped_column(String(32))  # h2h, spreads, totals
    outcome: Mapped[str] = mapped_column(String(128))
    bookmaker: Mapped[str] = mapped_column(String(32), default="draftkings")
    price_american: Mapped[int] = mapped_column(Integer)
    point: Mapped[float | None] = mapped_column(Float, nullable=True)
    implied_prob: Mapped[float] = mapped_column(Float)
    fair_prob: Mapped[float] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TeamStat(Base):
    __tablename__ = "team_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sport: Mapped[str] = mapped_column(String(32), index=True)
    team: Mapped[str] = mapped_column(String(64), index=True)
    as_of_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    off_rating: Mapped[float] = mapped_column(Float, default=0.0)
    def_rating: Mapped[float] = mapped_column(Float, default=0.0)
    pace: Mapped[float] = mapped_column(Float, default=0.0)
    win_pct: Mapped[float] = mapped_column(Float, default=0.0)
    rest_days: Mapped[int] = mapped_column(Integer, default=1)
    is_home: Mapped[bool] = mapped_column(Boolean, default=False)


class PickLog(Base):
    __tablename__ = "pick_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sport: Mapped[str] = mapped_column(String(32))
    event_id: Mapped[str] = mapped_column(String(128))
    market: Mapped[str] = mapped_column(String(32))
    selection: Mapped[str] = mapped_column(String(256))
    model_prob: Mapped[float] = mapped_column(Float)
    fair_prob: Mapped[float] = mapped_column(Float)
    edge: Mapped[float] = mapped_column(Float)
    stake: Mapped[float] = mapped_column(Float)
    odds_american: Mapped[int] = mapped_column(Integer)
    is_parlay: Mapped[bool] = mapped_column(Boolean, default=False)
    parlay_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str | None] = mapped_column(String(16), nullable=True)  # win, loss, push
    clv: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

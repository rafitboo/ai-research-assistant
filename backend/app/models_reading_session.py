"""
NEW FILE — place at: app/models_reading_session.py

Defines the ReadingSession table used for time-tracking. Kept separate from
app/models.py on purpose so nothing in the existing file is touched.

Uses the same Base as app/models.py, so it's picked up automatically by
Base.metadata.create_all(bind=engine) in main.py — no migration needed,
same as how your existing tables are created.
"""

from sqlalchemy import Column, Integer, ForeignKey, DateTime
from datetime import datetime, timezone
from app.database import Base


class ReadingSession(Base):
    __tablename__ = "reading_sessions"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    seconds_logged = Column(Integer, default=0)

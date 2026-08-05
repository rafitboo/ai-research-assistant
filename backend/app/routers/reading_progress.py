"""
NEW FILE — place at: app/routers/reading_progress.py

Adds progress-tracking endpoints under the same /api/papers prefix your
papers.py router already uses. Paths are distinct (no collisions):

  PATCH /api/papers/{paper_id}/progress
  POST  /api/papers/{paper_id}/reading-sessions
  POST  /api/papers/{paper_id}/reading-sessions/{session_id}/heartbeat
  POST  /api/papers/{paper_id}/reading-sessions/{session_id}/end

Doesn't touch app/models.py — Paper already has reading_status,
read_percentage, and time_spent_seconds columns.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Paper
from app.models_reading_session import ReadingSession
from app.auth_utils import get_current_user

router = APIRouter(prefix="/api/papers", tags=["Reading Progress"])

VALID_STATUSES = {"Unread", "Reading", "Completed"}


class ProgressUpdateSchema(BaseModel):
    reading_status: Optional[str] = None
    read_percentage: Optional[int] = Field(None, ge=0, le=100)


class HeartbeatSchema(BaseModel):
    seconds_elapsed: int = Field(..., ge=1, le=120)
    read_percentage: Optional[int] = Field(None, ge=0, le=100)


def _get_owned_paper(paper_id: int, user_id: int, db: Session) -> Paper:
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.user_id == user_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@router.patch("/{paper_id}/progress")
def update_progress(
    paper_id: int,
    data: ProgressUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manual override — status dropdown or % slider on the reading page."""
    paper = _get_owned_paper(paper_id, current_user["user_id"], db)

    if data.reading_status is not None:
        if data.reading_status not in VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"reading_status must be one of {sorted(VALID_STATUSES)}",
            )
        paper.reading_status = data.reading_status

    if data.read_percentage is not None:
        paper.read_percentage = data.read_percentage
        if data.read_percentage == 100:
            paper.reading_status = "Completed"
        elif data.read_percentage > 0 and paper.reading_status == "Unread":
            paper.reading_status = "Reading"

    db.commit()
    db.refresh(paper)
    return {
        "id": paper.id,
        "reading_status": paper.reading_status,
        "read_percentage": paper.read_percentage,
        "time_spent_seconds": paper.time_spent_seconds,
    }


@router.post("/{paper_id}/reading-sessions")
def start_reading_session(
    paper_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Called when the reading page loads."""
    paper = _get_owned_paper(paper_id, current_user["user_id"], db)

    if paper.reading_status == "Unread":
        paper.reading_status = "Reading"
        db.commit()

    session = ReadingSession(paper_id=paper.id, user_id=current_user["user_id"])
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": session.id}


@router.post("/{paper_id}/reading-sessions/{session_id}/heartbeat")
def heartbeat(
    paper_id: int,
    session_id: int,
    data: HeartbeatSchema,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Client pings this every ~30s while the tab is visible and open."""
    paper = _get_owned_paper(paper_id, current_user["user_id"], db)

    session = (
        db.query(ReadingSession)
        .filter(
            ReadingSession.id == session_id,
            ReadingSession.paper_id == paper_id,
            ReadingSession.user_id == current_user["user_id"],
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Reading session not found")

    session.seconds_logged += data.seconds_elapsed
    paper.time_spent_seconds += data.seconds_elapsed

    if data.read_percentage is not None:
        paper.read_percentage = max(paper.read_percentage, data.read_percentage)

    if paper.read_percentage >= 100:
        paper.reading_status = "Completed"
    elif paper.reading_status == "Unread":
        paper.reading_status = "Reading"

    db.commit()
    db.refresh(paper)
    return {
        "time_spent_seconds": paper.time_spent_seconds,
        "reading_status": paper.reading_status,
        "read_percentage": paper.read_percentage,
    }


@router.post("/{paper_id}/reading-sessions/{session_id}/end")
def end_reading_session(
    paper_id: int,
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Called via sendBeacon on page unload/tab close."""
    session = (
        db.query(ReadingSession)
        .filter(
            ReadingSession.id == session_id,
            ReadingSession.paper_id == paper_id,
            ReadingSession.user_id == current_user["user_id"],
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Reading session not found")

    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}

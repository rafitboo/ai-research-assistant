from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models import JournalEntry, Paper
from app.auth_utils import get_current_user

router = APIRouter(
    prefix="/api/journal",
    tags=["Journal"]
)

# Pydantic schemas
class JournalCreate(BaseModel):
    title: Optional[str] = None
    content: str
    paper_id: Optional[int] = None
    category: str = "General"
    tags: Optional[str] = None

class JournalUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    paper_id: Optional[int] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    pinned: Optional[bool] = None

class JournalResponse(BaseModel):
    id: int
    title: Optional[str]
    content: str
    paper_id: Optional[int]
    paper_title: Optional[str] = None
    category: str
    tags: Optional[str] = None
    pinned: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AutocompletePaperResponse(BaseModel):
    id: int
    title: str


def get_user_id_from_token(current_user: dict) -> int:
    user_id = current_user.get("user_id") or current_user.get("sub") or current_user.get("id")
    if user_id is None:
        raise HTTPException(status_code=401, detail=f"User ID not found in token payload: {current_user}")
    return int(user_id)


def _serialize(entry: JournalEntry, paper_title: Optional[str] = None) -> dict:
    return {
        "id": entry.id,
        "title": entry.title,
        "content": entry.content,
        "paper_id": entry.paper_id,
        "paper_title": paper_title,
        "category": entry.category,
        "tags": entry.tags,
        "pinned": bool(entry.pinned),
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


def _get_owned_entry(entry_id: int, user_id: int, db: Session) -> JournalEntry:
    entry = db.query(JournalEntry).filter(
        JournalEntry.id == entry_id,
        JournalEntry.user_id == user_id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry


@router.post("/", response_model=JournalResponse)
def create_journal_entry(
    entry: JournalCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    actual_user_id = get_user_id_from_token(current_user)

    new_entry = JournalEntry(
        user_id=actual_user_id,
        title=entry.title,
        content=entry.content,
        paper_id=entry.paper_id,
        category=entry.category,
        tags=entry.tags,
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    paper_title = None
    if new_entry.paper_id:
        paper = db.query(Paper).filter(Paper.id == new_entry.paper_id).first()
        if paper:
            paper_title = paper.title

    return _serialize(new_entry, paper_title)


@router.get("/", response_model=List[JournalResponse])
def get_journal_entries(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    q: Optional[str] = Query(None, description="Search title and content"),
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    actual_user_id = get_user_id_from_token(current_user)

    query = db.query(JournalEntry).filter(JournalEntry.user_id == actual_user_id)

    if q:
        like = f"%{q}%"
        query = query.filter(or_(JournalEntry.title.ilike(like), JournalEntry.content.ilike(like)))

    if category and category != "All":
        query = query.filter(JournalEntry.category == category)

    if tag:
        query = query.filter(JournalEntry.tags.ilike(f"%{tag}%"))

    # Pinned entries first, newest first within each group
    entries = query.order_by(
        JournalEntry.pinned.desc(),
        JournalEntry.created_at.desc()
    ).offset(skip).limit(limit).all()

    paper_ids = {e.paper_id for e in entries if e.paper_id}
    paper_map = {}
    if paper_ids:
        papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all()
        paper_map = {p.id: p.title for p in papers}

    return [_serialize(e, paper_map.get(e.paper_id)) for e in entries]


@router.put("/{entry_id}", response_model=JournalResponse)
def update_journal_entry(
    entry_id: int,
    update: JournalUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    actual_user_id = get_user_id_from_token(current_user)
    entry = _get_owned_entry(entry_id, actual_user_id, db)

    data = update.model_dump(exclude_unset=True)
    if "pinned" in data:
        data["pinned"] = int(data["pinned"])
    for field, value in data.items():
        setattr(entry, field, value)

    db.commit()
    db.refresh(entry)

    paper_title = None
    if entry.paper_id:
        paper = db.query(Paper).filter(Paper.id == entry.paper_id).first()
        if paper:
            paper_title = paper.title

    return _serialize(entry, paper_title)


@router.patch("/{entry_id}/pin", response_model=JournalResponse)
def toggle_pin(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    actual_user_id = get_user_id_from_token(current_user)
    entry = _get_owned_entry(entry_id, actual_user_id, db)
    entry.pinned = 0 if entry.pinned else 1
    db.commit()
    db.refresh(entry)
    return _serialize(entry)


@router.delete("/{entry_id}")
def delete_journal_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    actual_user_id = get_user_id_from_token(current_user)
    entry = _get_owned_entry(entry_id, actual_user_id, db)
    db.delete(entry)
    db.commit()
    return {"success": True, "deleted_id": entry_id}


@router.get("/autocomplete-papers", response_model=List[AutocompletePaperResponse])
def autocomplete_papers(
    q: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if not q or len(q) < 2:
        return []
    actual_user_id = get_user_id_from_token(current_user)
    papers = db.query(Paper).filter(
        Paper.user_id == actual_user_id,
        Paper.title.ilike(f"%{q}%")
    ).limit(5).all()
    return papers
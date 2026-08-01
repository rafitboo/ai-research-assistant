import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Paper, User
from app.auth_utils import get_current_user

router = APIRouter(prefix="/api/papers", tags=["Papers"])

# Upload directory path inside backend folder
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
def upload_paper(
    title: str = Form(...),
    author: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    topic: Optional[str] = Form(None),
    research_area: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["user_id"]
    
    saved_file_path = None
    if file and file.filename:
        # Generate unique filename to prevent overwriting
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        saved_file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(saved_file_path, "wb") as buffer:
            buffer.write(file.file.read())

    new_paper = Paper(
        title=title,
        author=author,
        year=year,
        topic=topic,
        research_area=research_area,
        tags=tags,
        file_path=saved_file_path,
        reading_status="Unread",
        read_percentage=0,
        time_spent_seconds=0,
        user_id=user_id
    )
    db.add(new_paper)
    db.commit()
    db.refresh(new_paper)

    return {"message": "Paper uploaded successfully", "paper_id": new_paper.id}


@router.get("/")
def list_papers(
    topic: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    author: Optional[str] = Query(None),
    research_area: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["user_id"]
    query = db.query(Paper).filter(Paper.user_id == user_id)

    # Filtering logic
    if topic and topic.strip():
        query = query.filter(Paper.topic.ilike(f"%{topic.strip()}%"))
    if year:
        query = query.filter(Paper.year == year)
    if author and author.strip():
        query = query.filter(Paper.author.ilike(f"%{author.strip()}%"))
    if research_area and research_area.strip():
        query = query.filter(Paper.research_area.ilike(f"%{research_area.strip()}%"))
    if search and search.strip():
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            (Paper.title.ilike(search_filter)) |
            (Paper.tags.ilike(search_filter)) |
            (Paper.author.ilike(search_filter))
        )

    papers = query.order_by(Paper.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "author": p.author,
            "year": p.year,
            "topic": p.topic,
            "research_area": p.research_area,
            "tags": p.tags,
            "file_path": p.file_path,
            "reading_status": p.reading_status,
            "read_percentage": p.read_percentage,
            "time_spent_seconds": p.time_spent_seconds,
            "created_at": p.created_at.isoformat() if p.created_at else None
        }
        for p in papers
    ]


@router.get("/{paper_id}/file")
def download_paper_file(
    paper_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["user_id"]
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.user_id == user_id).first()
    if not paper or not paper.file_path:
        raise HTTPException(status_code=404, detail="Paper or file not found")

    if not os.path.exists(paper.file_path):
        raise HTTPException(status_code=404, detail="File missing on disk")

    return FileResponse(paper.file_path, media_type="application/pdf", filename=f"{paper.title}.pdf")
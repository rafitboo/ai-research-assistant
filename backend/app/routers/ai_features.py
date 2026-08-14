import os
import json
import google.generativeai as genai
from PyPDF2 import PdfReader
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models import Paper, PaperSummary, PaperInsight, SavedTitle, Project
from app.auth_utils import get_current_user

router = APIRouter(prefix="/api/ai", tags=["AI Features"])

class InsightUpdate(BaseModel):
    content: str

class TitleGenerateRequest(BaseModel):
    topic: str

class SaveTitleRequest(BaseModel):
    title_text: str
    project_id: Optional[int] = None

def get_user_id(user_dict: dict) -> int:
    return int(user_dict.get("user_id") or user_dict.get("sub") or user_dict.get("id"))

# --- Summarization & Insights Endpoints ---
@router.get("/summary/{paper_id}")
def get_paper_summary(paper_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.user_id == user_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    summary = db.query(PaperSummary).filter(PaperSummary.paper_id == paper_id).first()
    if not summary:
        return {"status": "none"}

    insights = db.query(PaperInsight).filter(PaperInsight.paper_id == paper_id).all()
    categorized = {"contribution": [], "advantage": [], "limitation": [], "future_work": []}
    for ins in insights:
        if ins.category in categorized:
            categorized[ins.category].append({"id": ins.id, "content": ins.content})

    return {
        "status": "exists",
        "data": {
            "abstract": summary.abstract_summary,
            "methodology": summary.methodology_summary,
            "findings": summary.findings_summary,
            "insights": categorized
        }
    }

@router.post("/summary/{paper_id}/generate")
def generate_summary(paper_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.user_id == user_id).first()
    if not paper or not paper.file_path or not os.path.exists(paper.file_path):
        raise HTTPException(status_code=404, detail="PDF file not found")

    try:
        reader = PdfReader(paper.file_path)
        text = "".join([page.extract_text() for page in reader.pages[:15]])
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read PDF")

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-3.6-flash')
    
    prompt = """
    Analyze the following academic paper and return a strict JSON object with this exact structure:
    {
      "abstract": "1-paragraph summary of abstract.",
      "methodology": "1-paragraph summary of methodology and datasets.",
      "findings": "1-paragraph summary of main findings.",
      "contribution": ["bullet 1", "bullet 2"],
      "advantage": ["bullet 1", "bullet 2"],
      "limitation": ["bullet 1", "bullet 2"],
      "future_work": ["bullet 1", "bullet 2"]
    }
    Text:
    """ + text[:30000]

    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API Error: {str(e)}")

    try:
        data = json.loads(response.text)
    except Exception:
        raise HTTPException(status_code=500, detail="AI parsing format error")

    db.query(PaperSummary).filter(PaperSummary.paper_id == paper_id).delete()
    db.query(PaperInsight).filter(PaperInsight.paper_id == paper_id).delete()

    new_summary = PaperSummary(
        paper_id=paper_id,
        abstract_summary=data.get("abstract", ""),
        methodology_summary=data.get("methodology", ""),
        findings_summary=data.get("findings", "")
    )
    db.add(new_summary)

    for cat in ["contribution", "advantage", "limitation", "future_work"]:
        for bullet in data.get(cat, []):
            db.add(PaperInsight(paper_id=paper_id, category=cat, content=bullet))
            
    db.commit()
    return {"message": "Success"}

@router.put("/insights/{insight_id}")
def update_insight(insight_id: int, payload: InsightUpdate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    insight = db.query(PaperInsight).filter(PaperInsight.id == insight_id).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    insight.content = payload.content
    db.commit()
    return {"message": "Updated"}

# AI Title Generator Endpoints
@router.post("/titles/generate")
def generate_titles(payload: TitleGenerateRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-3.6-flash')
    
    prompt = f"""
    Given the following research topic or short description, generate exactly 5 candidate academic paper or thesis titles.
    Return a strict JSON object with this exact structure:
    {{
      "titles": ["Title option 1", "Title option 2", "Title option 3", "Title option 4", "Title option 5"]
    }}
    Topic / Description: {payload.topic}
    """
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API Error: {str(e)}")

    try:
        data = json.loads(response.text)
        return data.get("titles", [])
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse generated titles")

    
@router.post("/titles/save")
def save_title(payload: SaveTitleRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    saved = SavedTitle(user_id=user_id, project_id=payload.project_id, title_text=payload.title_text)
    db.add(saved)
    db.commit()
    return {"message": "Title saved successfully"}

@router.get("/titles/saved")
def get_saved_titles(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    saved = db.query(SavedTitle).filter(SavedTitle.user_id == user_id).order_by(SavedTitle.created_at.desc()).all()
    return [{"id": s.id, "title_text": s.title_text, "project_id": s.project_id} for s in saved]
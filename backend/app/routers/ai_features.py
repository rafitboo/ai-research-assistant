import os
import json
import google.generativeai as genai
from PyPDF2 import PdfReader
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models import Paper, PaperSummary, PaperInsight, SavedTitle, Project, User
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


# Maps the JSON keys Gemini returns to the PaperInsight.category values stored in the DB.
INSIGHT_CATEGORY_MAP = {
    "contribution": "contribution",
    "advantage": "advantage",
    "limitation": "limitation",
    "future_work": "future_work",
}

HYPOTHESIS_CATEGORY_MAP = {
    "core_variable": "hyp_core_variable",
    "structural_context": "hyp_structural_context",
    "methodological_alignment": "hyp_methodological_alignment",
    "logical_justification": "hyp_logical_justification",
}

GAP_CATEGORY_MAP = {
    "context": "gap_context",
    "location": "gap_location",
    "response": "gap_response",
    "significance": "gap_significance",
}

# Used by the single-point regenerate endpoint to know what to ask Gemini for.
CATEGORY_INSTRUCTIONS = {
    "contribution": "a single concise bullet describing one contribution of this paper",
    "advantage": "a single concise bullet describing one advantage of this paper's approach",
    "limitation": "a single concise bullet describing one limitation of this paper",
    "future_work": "a single concise bullet describing one future work direction suggested by this paper",
    "hyp_core_variable": "one core variable (independent, dependent, or mediating) relevant to forming a hypothesis for this paper",
    "hyp_structural_context": "one structural or contextual element (setting, population, or scope) relevant to forming a hypothesis for this paper",
    "hyp_methodological_alignment": "one point on how a hypothesis should align with this paper's methodology and measurable evidence",
    "hyp_logical_justification": "one logical justification connecting this paper's findings to a plausible hypothesis",
    "gap_context": "one point on what was missing or overlooked in this paper's field of study",
    "gap_location": "one point on where in the paper's scope or domain the research gap exists",
    "gap_response": "one point on how this paper addresses or responds to part of that gap",
    "gap_significance": "one point on why this research gap is academically significant",
}


def _read_pdf_text(paper: Paper, max_pages: int = 15) -> str:
    if not paper.file_path or not os.path.exists(paper.file_path):
        raise HTTPException(status_code=404, detail="PDF file not found")
    try:
        reader = PdfReader(paper.file_path)
        return "".join([page.extract_text() or "" for page in reader.pages[:max_pages]])
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read PDF")


def _fetch_categorized_insights(db: Session, paper_id: int, category_map: dict) -> dict:
    db_categories = list(category_map.values())
    rows = db.query(PaperInsight).filter(
        PaperInsight.paper_id == paper_id,
        PaperInsight.category.in_(db_categories)
    ).all()
    reverse_map = {v: k for k, v in category_map.items()}
    result = {json_key: [] for json_key in category_map}
    for row in rows:
        json_key = reverse_map.get(row.category)
        if json_key:
            result[json_key].append({"id": row.id, "content": row.content, "starred": bool(row.starred)})
    return result


def _replace_unstarred_categories(db: Session, paper_id: int, category_map: dict, generated: dict):
    """Deletes only the NON-starred rows for these categories, then inserts fresh ones.
    Starred rows are left untouched so they survive regeneration."""
    db_categories = list(category_map.values())
    db.query(PaperInsight).filter(
        PaperInsight.paper_id == paper_id,
        PaperInsight.category.in_(db_categories),
        PaperInsight.starred == 0
    ).delete(synchronize_session=False)
    for json_key, db_category in category_map.items():
        for bullet in generated.get(json_key, []):
            bullet = str(bullet).strip()
            if bullet:
                db.add(PaperInsight(paper_id=paper_id, category=db_category, content=bullet))




def enforce_premium_access(user_dict: dict, db: Session):
    """Blocks Free users from accessing AI endpoints."""
    user_id = get_user_id(user_dict)
    user_record = db.query(User).filter(User.id == user_id).first()
    if not user_record or user_record.subscription_tier != "Premium":
        raise HTTPException(
            status_code=403, 
            detail="Premium required. Please upgrade your account to unlock AI features."
        )

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
            categorized[ins.category].append({"id": ins.id, "content": ins.content, "starred": bool(ins.starred)})

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
    enforce_premium_access(user, db)
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

    new_summary = PaperSummary(
        paper_id=paper_id,
        abstract_summary=data.get("abstract", ""),
        methodology_summary=data.get("methodology", ""),
        findings_summary=data.get("findings", "")
    )
    db.add(new_summary)

    _replace_unstarred_categories(db, paper_id, INSIGHT_CATEGORY_MAP, data)

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
    enforce_premium_access(user, db)
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



# --- Hypothesis Generator ---
@router.get("/hypothesis/{paper_id}")
def get_hypothesis(paper_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.user_id == user_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    data = _fetch_categorized_insights(db, paper_id, HYPOTHESIS_CATEGORY_MAP)
    if not any(data.values()):
        return {"status": "none"}
    return {"status": "exists", "data": data}


@router.post("/hypothesis/{paper_id}/generate")
def generate_hypothesis(paper_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    enforce_premium_access(user, db)
    user_id = get_user_id(user)
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.user_id == user_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    text = _read_pdf_text(paper)

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-3.6-flash')

    prompt = """
    Analyze the following academic paper and help formulate a research hypothesis for it.
    Return a strict JSON object with this exact structure:
    {
      "core_variable": ["bullet 1", "bullet 2"],
      "structural_context": ["bullet 1", "bullet 2"],
      "methodological_alignment": ["bullet 1", "bullet 2"],
      "logical_justification": ["bullet 1", "bullet 2"]
    }
    Where:
    - core_variable: the paper's key independent, dependent, and mediating variables relevant to a hypothesis.
    - structural_context: structural and contextual elements (setting, population, scope) relevant to forming a hypothesis.
    - methodological_alignment: how a hypothesis should align with the paper's methodology and measurable evidence.
    - logical_justification: the logical reasoning connecting the paper's findings to a plausible hypothesis.
    Keep every bullet concise (1-2 sentences) and specific to this paper. Return 2-4 bullets per category.
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

    _replace_unstarred_categories(db, paper_id, HYPOTHESIS_CATEGORY_MAP, data)
    db.commit()
    return {"message": "Success"}


# --- Research Gap Finder  ---
@router.get("/gaps/{paper_id}")
def get_research_gap(paper_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.user_id == user_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    data = _fetch_categorized_insights(db, paper_id, GAP_CATEGORY_MAP)
    if not any(data.values()):
        return {"status": "none"}
    return {"status": "exists", "data": data}


@router.post("/gaps/{paper_id}/generate")
def generate_research_gap(paper_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    enforce_premium_access(user, db)
    user_id = get_user_id(user)
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.user_id == user_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    text = _read_pdf_text(paper)

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-3.6-flash')

    prompt = """
    Analyze the following academic paper and identify its main research gap.
    Return a strict JSON object with this exact structure:
    {
      "context": ["bullet 1", "bullet 2"],
      "location": ["bullet 1", "bullet 2"],
      "response": ["bullet 1", "bullet 2"],
      "significance": ["bullet 1", "bullet 2"]
    }
    Where:
    - context: what was missing or overlooked in this area of research before/around this paper.
    - location: where specifically the gap exists (which part of the problem, dataset, method, or scope).
    - response: how this paper addresses or partially responds to that gap.
    - significance: why this research gap matters academically.
    Keep every bullet concise and academically relevant, based only on this paper's content. Return 2-4 bullets per category.
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

    _replace_unstarred_categories(db, paper_id, GAP_CATEGORY_MAP, data)
    db.commit()
    return {"message": "Success"}


# --- Generic per-point actions, shared by Extract Insights, Hypothesis Generator, Research Gap Finder ---
@router.post("/insights/{insight_id}/star")
def toggle_star_insight(insight_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    insight = db.query(PaperInsight).filter(PaperInsight.id == insight_id).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    insight.starred = 0 if insight.starred else 1
    db.commit()
    return {"id": insight.id, "starred": bool(insight.starred)}


@router.post("/insights/{insight_id}/regenerate")
def regenerate_insight(insight_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    print(f"[regenerate] hit for insight_id={insight_id}")  # TEMP: confirms the request reached the backend
    enforce_premium_access(user, db)
    user_id = get_user_id(user)
    insight = db.query(PaperInsight).filter(PaperInsight.id == insight_id).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    paper = db.query(Paper).filter(Paper.id == insight.paper_id, Paper.user_id == user_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    instruction = CATEGORY_INSTRUCTIONS.get(insight.category)
    if not instruction:
        raise HTTPException(status_code=400, detail="Unsupported category for regeneration")

    text = _read_pdf_text(paper)
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-3.6-flash')

    prompt = f"""
    Analyze the following academic paper text and generate {instruction}.
    Return a strict JSON object with this exact structure:
    {{ "point": "the single generated point as one concise sentence" }}
    Text:
    {text[:30000]}
    """

    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API Error: {str(e)}")

    try:
        data = json.loads(response.text)
        new_content = str(data.get("point", "")).strip()
        if not new_content:
            raise ValueError("empty point")
    except Exception:
        raise HTTPException(status_code=500, detail="AI parsing format error")

    insight.content = new_content
    db.commit()
    db.refresh(insight)
    return {"id": insight.id, "content": insight.content, "starred": bool(insight.starred)}

## starred items
@router.delete("/titles/saved/{title_id}")
def delete_saved_title(title_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    saved = db.query(SavedTitle).filter(SavedTitle.id == title_id, SavedTitle.user_id == user_id).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved title not found")
    db.delete(saved)
    db.commit()
    return {"message": "Removed"}


@router.get("/starred")
def get_starred_items(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)

    rows = (
        db.query(PaperInsight, Paper.title)
        .join(Paper, Paper.id == PaperInsight.paper_id)
        .filter(Paper.user_id == user_id, PaperInsight.starred == 1)
        .all()
    )

    insights, gaps, hypothesis = [], [], []
    for insight, paper_title in rows:
        item = {
            "id": insight.id,
            "content": insight.content,
            "category": insight.category,
            "paper_id": insight.paper_id,
            "paper_title": paper_title,
        }
        if insight.category.startswith("gap_"):
            gaps.append(item)
        elif insight.category.startswith("hyp_"):
            hypothesis.append(item)
        elif insight.category in INSIGHT_CATEGORY_MAP:
            insights.append(item)

    titles = db.query(SavedTitle).filter(SavedTitle.user_id == user_id).order_by(SavedTitle.created_at.desc()).all()
    titles_list = [{"id": t.id, "title_text": t.title_text, "project_id": t.project_id} for t in titles]

    return {
        "insights": insights,
        "gaps": gaps,
        "hypothesis": hypothesis,
        "titles": titles_list,
    }
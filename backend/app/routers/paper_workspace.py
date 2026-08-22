import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import Paper, PageNote, User
from app.auth_utils import get_current_user
import google.generativeai as genai
from io import BytesIO
from fastapi.responses import StreamingResponse
from gtts import gTTS
from typing import Optional
from deep_translator import GoogleTranslator



router = APIRouter(prefix="/api/papers", tags=["Paper Workspace"])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def enforce_premium_access(user_dict: dict, db: Session):
    """Blocks Free users from accessing AI endpoints."""
    user_id = int(user_dict.get("user_id") or user_dict.get("sub") or user_dict.get("id"))
    user_record = db.query(User).filter(User.id == user_id).first()
    if not user_record or user_record.subscription_tier != "Premium":
        raise HTTPException(
            status_code=403, 
            detail="Premium required. Please upgrade your account to unlock AI features."
        )


def extract_pdf_text(file_path: str, max_pages: int = 15) -> str:
    """Extract text from the PDF, scanning up to 15 pages to ensure the abstract is caught."""
    if not file_path or not os.path.exists(file_path):
        return ""
    text_content = ""
    try:
        import pypdf
        reader = pypdf.PdfReader(file_path)
        for i, page in enumerate(reader.pages[:max_pages]):
            txt = page.extract_text()
            if txt:
                text_content += f"\n[Page {i+1}]\n" + txt
    except Exception as e:
        print(f"PDF extraction error: {e}")
    return text_content

class NoteCreateSchema(BaseModel):
    page_number: int
    note_content: str

class ChatQuerySchema(BaseModel):
    question: str
class TTSRequest(BaseModel):
    text: str
    lang: Optional[str] = "en"       # "en" or "bn"
    accent: Optional[str] = "com"
    
    
@router.get("/{paper_id}/overview")
def get_paper_overview(paper_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    file_path = getattr(paper, "file_path", None)
    pdf_text = extract_pdf_text(file_path, max_pages=15) if file_path else ""
    
    abstract_text = ""
    if pdf_text and GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel("gemini-3.6-flash")
            prompt = f"""
            Thoroughly scan the following research paper text across all provided pages to locate the 'Abstract' section. 
            Extract its core objective, methodology, and key findings. Rewrite it briefly using very simple, clear words so anyone can easily understand it.
            CRITICAL: Do NOT use markdown symbols like hashtags (###) or bold asterisks (**). Output clean plain text paragraphs only.

            Paper Text:
            {pdf_text}
            """
            response = model.generate_content(prompt)
            abstract_text = response.text
        except Exception as e:
            abstract_text = f"Could not generate abstract: {str(e)}"
    else:
        abstract_text = "PDF file text could not be read."

    return {
        "id": paper.id,
        "title": paper.title,
        "abstract": abstract_text,
        "file_url": getattr(paper, "file_url", "#")
    }

@router.get("/{paper_id}/notes")
def get_page_notes(paper_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    notes = db.query(PageNote).filter(PageNote.paper_id == paper_id, PageNote.user_id == current_user["user_id"]).all()
    return [{"id": n.id, "page_number": n.page_number, "note_content": n.note_content} for n in notes]

@router.post("/{paper_id}/notes")
def create_page_note(paper_id: int, data: NoteCreateSchema, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    note = PageNote(
        user_id=current_user["user_id"],
        paper_id=paper_id,
        page_number=data.page_number,
        note_content=data.note_content
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"message": "Note saved successfully", "note_id": note.id}

@router.post("/{paper_id}/chat")
def chat_with_paper(paper_id: int, data: ChatQuerySchema, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    enforce_premium_access(current_user, db)
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    file_path = getattr(paper, "file_path", None)
    pdf_text = extract_pdf_text(file_path, max_pages=30) if file_path else ""
    
    prompt = f"""
    You are an advanced, expert AI research assistant modeled after Gemini. Answer the user's question comprehensively and fluently based on the full research paper text provided below. 
    At the end of your response, provide a brief verified source reference tag (e.g., "from Section 5, page 4").

    Research Paper Text:
    {pdf_text}

    User Question: {data.question}
    """
    
    try:
        model = genai.GenerativeModel("gemini-3.6-flash")
        response = model.generate_content(prompt)
        answer = response.text
        source_reference = "from Document Context"
    except Exception as e:
        answer = f"Gemini API Error: {str(e)}"
        source_reference = "Unknown source"

    return {
        "answer": answer,
        # "source": source_reference
    }
    
@router.post("/tts")
def generate_audio_summary(data: TTSRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    enforce_premium_access(current_user, db)
    
    if not data.text or len(data.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="No text provided for audio generation.")

    try:
        spoken_text = data.text

        if data.lang == "bn":
            # Translates English to Bengali
            spoken_text = GoogleTranslator(source='en', target='bn').translate(data.text)
            tts = gTTS(text=spoken_text, lang='bn', slow=False)
        else:
            # English with regional voice
            tld_accent = data.accent if data.accent in ["com", "co.uk", "co.in", "com.au"] else "com"
            tts = gTTS(text=spoken_text, lang='en', tld=tld_accent, slow=False)

        # In-memory buffer streaming
        audio_buffer = BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        
        return StreamingResponse(audio_buffer, media_type="audio/mpeg")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio generation failed: {str(e)}")
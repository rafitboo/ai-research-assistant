import os
import json
from typing import List

import google.generativeai as genai
from PyPDF2 import PdfReader
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Paper, PaperInsight
from app.auth_utils import get_current_user


router = APIRouter(
    prefix="/api/research-gaps",
    tags=["Cross-Paper Research Gaps"],
)


class ResearchGapRequest(BaseModel):
    paper_ids: List[int]


def get_user_id(user_dict: dict) -> int:
    user_id = user_dict.get("user_id") or user_dict.get("sub") or user_dict.get("id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="User ID not found")
    return int(user_id)


def extract_pdf_text(file_path: str, max_pages: int = 20) -> str:
    """Fallback used when a selected paper has no saved AI insight rows yet."""
    if not file_path or not os.path.exists(file_path):
        return ""

    try:
        reader = PdfReader(file_path)
        parts = []

        for page_number, page in enumerate(reader.pages[:max_pages], start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                parts.append(f"[Page {page_number}]\n{page_text}")

        return "\n".join(parts)
    except Exception as exc:
        print(f"Research-gap PDF extraction error: {exc}")
        return ""


def build_paper_context(paper: Paper, db: Session) -> str:
    """
    Prefer the existing Module 2 Feature 4 limitation/future-work rows.
    Fall back to PDF text if those rows do not exist yet.
    """
    insights = (
        db.query(PaperInsight)
        .filter(
            PaperInsight.paper_id == paper.id,
            PaperInsight.category.in_(["limitation", "future_work"]),
        )
        .all()
    )

    limitation_items = [
        insight.content.strip()
        for insight in insights
        if insight.category == "limitation" and insight.content
    ]
    future_work_items = [
        insight.content.strip()
        for insight in insights
        if insight.category == "future_work" and insight.content
    ]

    context = [
        f"PAPER ID: {paper.id}",
        f"TITLE: {paper.title}",
        f"AUTHOR: {paper.author or 'Unknown'}",
        f"YEAR: {paper.year or 'Unknown'}",
    ]

    if limitation_items or future_work_items:
        context.append("\nEXISTING AI-EXTRACTED LIMITATIONS:")
        context.extend(f"- {item}" for item in limitation_items)

        context.append("\nEXISTING AI-EXTRACTED FUTURE WORK:")
        context.extend(f"- {item}" for item in future_work_items)
        return "\n".join(context)

    pdf_text = extract_pdf_text(paper.file_path)
    if pdf_text:
        context.append(
            "\nNO SAVED LIMITATION/FUTURE-WORK INSIGHTS WERE FOUND. "
            "Use the following PDF text only to identify those sections "
            "and extract relevant evidence:"
        )
        context.append(pdf_text[:24000])
    else:
        context.append(
            "\nNO READABLE LIMITATION/FUTURE-WORK MATERIAL WAS AVAILABLE."
        )

    return "\n".join(context)


@router.post("/generate")
def generate_research_gaps(
    payload: ResearchGapRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)

    paper_ids = list(dict.fromkeys(payload.paper_ids))

    if len(paper_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="Please select at least two papers.",
        )

    if len(paper_ids) > 10:
        raise HTTPException(
            status_code=400,
            detail="Please select no more than 10 papers at a time.",
        )

    papers = (
        db.query(Paper)
        .filter(
            Paper.id.in_(paper_ids),
            Paper.user_id == user_id,
        )
        .all()
    )

    if len(papers) != len(paper_ids):
        raise HTTPException(
            status_code=403,
            detail="One or more selected papers are unavailable.",
        )

    papers_by_id = {paper.id: paper for paper in papers}
    ordered_papers = [papers_by_id[paper_id] for paper_id in paper_ids]

    paper_contexts = [
        build_paper_context(paper, db)
        for paper in ordered_papers
    ]

    combined_context = "\n\n".join(
        f"==============================\n{context}\n"
        f"=============================="
        for context in paper_contexts
    )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not configured.",
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-3.6-flash")

    prompt = f"""
You are an academic research-gap synthesis assistant.

Analyze the selected research papers together and identify
candidate research gaps that could support future research.

IMPORTANT RULES:
1. Use only the supplied paper information.
2. Prioritize the supplied limitations and future-work material.
3. Identify gaps that are genuinely useful for proposing new research.
4. Do not invent findings, datasets, methods, limitations, or future work.
5. Do not simply repeat one paper's limitation. Explain the cross-paper
   relationship or unresolved issue that makes it a research gap.
6. A gap may be supported by one paper, but prefer gaps supported by
   multiple papers when the evidence allows it.
7. Every gap must cite at least one supplied PAPER ID.
8. Keep the titles concise and academically meaningful.
9. Return 3 to 8 candidate gaps.
10. Return ONLY valid JSON matching the schema below.

Use exactly these categories:
- Methodological Gaps
- Dataset / Evaluation Gaps
- Application Gaps
- Generalization Gaps
- Theoretical Gaps
- Future Research Opportunities

JSON schema:
{{
  "gaps": [
    {{
      "category": "Methodological Gaps",
      "title": "Short candidate gap title",
      "description": "Explain the unresolved issue and why it represents a research opportunity.",
      "sources": [
        {{
          "paper_id": 1,
          "evidence": "Brief evidence from this source paper that supports the gap."
        }}
      ]
    }}
  ]
}}

SELECTED PAPERS:
{combined_context}
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini API Error: {str(exc)}",
        )

    try:
        data = json.loads(response.text)
        gaps = data.get("gaps", [])
        if not isinstance(gaps, list):
            raise ValueError("gaps is not a list")
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="AI parsing format error.",
        )

    paper_lookup = {
        paper.id: {
            "id": paper.id,
            "title": paper.title,
        }
        for paper in ordered_papers
    }

    cleaned_gaps = []

    for gap in gaps:
        sources = []

        for source in gap.get("sources", []):
            try:
                source_id = int(source.get("paper_id"))
            except (TypeError, ValueError):
                continue

            if source_id not in paper_lookup:
                continue

            source_meta = paper_lookup[source_id]

            sources.append(
                {
                    "paper_id": source_meta["id"],
                    "paper_title": source_meta["title"],
                    "evidence": source.get("evidence", "").strip(),
                    "url": f"/papers/{source_meta['id']}/file",
                }
            )

        if not sources:
            continue

        cleaned_gaps.append(
            {
                "category": gap.get("category", "Future Research Opportunities"),
                "title": gap.get("title", "Candidate Research Gap"),
                "description": gap.get("description", "").strip(),
                "sources": sources,
            }
        )

    return {
        "selected_papers": [
            {
                "id": paper.id,
                "title": paper.title,
                "author": paper.author,
                "year": paper.year,
            }
            for paper in ordered_papers
        ],
        "gaps": cleaned_gaps,
    }

import os
import csv
import io
import json

import google.generativeai as genai

from PyPDF2 import PdfReader

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from fastapi.responses import StreamingResponse

from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.database import get_db
from app.auth_utils import get_current_user

from app.models import (
    User,
    Paper,
    LiteratureMatrix,
    LiteratureMatrixPaper,
    LiteratureMatrixColumn,
    LiteratureMatrixCell
)


router = APIRouter(
    prefix="/api/literature-matrix",
    tags=["Literature Comparison Matrix"]
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def get_user_id(user_dict: dict) -> int:
    return int(
        user_dict.get("user_id")
        or user_dict.get("sub")
        or user_dict.get("id")
    )


def require_premium(
    user: dict,
    db: Session
):
    user_id = get_user_id(user)

    account = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not account:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    if account.subscription_tier != "Premium":
        raise HTTPException(
            status_code=403,
            detail=(
                "Premium subscription required "
                "for Literature Comparison Matrix AI."
            )
        )


def get_matrix_or_404(
    matrix_id: int,
    user_id: int,
    db: Session
):
    matrix = (
        db.query(LiteratureMatrix)
        .filter(
            LiteratureMatrix.id == matrix_id,
            LiteratureMatrix.user_id == user_id
        )
        .first()
    )

    if not matrix:
        raise HTTPException(
            status_code=404,
            detail="Literature matrix not found"
        )

    return matrix


def read_paper_text(
    paper: Paper,
    max_pages: int = 20
) -> str:

    if not paper.file_path:
        return ""

    if not os.path.exists(paper.file_path):
        return ""

    try:
        reader = PdfReader(paper.file_path)

        pages = reader.pages[:max_pages]

        text = ""

        for page in pages:
            text += page.extract_text() or ""
            text += "\n"

        return text

    except Exception:
        return ""


def generate_ai_analysis(
    papers_data,
    custom_columns=None
):

    genai.configure(
        api_key=os.getenv("GEMINI_API_KEY")
    )

    model = genai.GenerativeModel(
        "gemini-3.6-flash"
    )

    custom_columns = custom_columns or []

    columns = [
        {
            "key": "dataset",
            "name": "Dataset"
        },
        {
            "key": "method",
            "name": "Method"
        },
        {
            "key": "results",
            "name": "Results"
        },
        {
            "key": "limitations",
            "name": "Limitations"
        }
    ]

    for column in custom_columns:
        columns.append(
            {
                "key": column["key"],
                "name": column["name"]
            }
        )

    paper_blocks = []

    for paper in papers_data:

        paper_blocks.append(
            f"""
PAPER ID: {paper["id"]}
TITLE: {paper["title"]}

CONTENT:
{paper["text"][:25000]}
"""
        )

    schema = {
        "papers": [
            {
                "paper_id": "integer",
                "cells": {
                    "dataset": "string",
                    "method": "string",
                    "results": "string",
                    "limitations": "string"
                }
            }
        ]
    }

    for column in custom_columns:

        for item in schema["papers"]:

            item["cells"][column["key"]] = "string"

    prompt = f"""
You are an academic literature-analysis assistant.

Analyze the following research papers.

For each paper, extract information for these comparison columns:

{json.dumps(columns, indent=2)}

IMPORTANT RULES:

1. Only use information actually supported by the paper.
2. Do not invent datasets, methods, results, or claims.
3. Keep each cell concise but informative.
4. If information is unavailable, write "Not reported".
5. For results, include important quantitative results when available.
6. For limitations, use limitations explicitly stated by the authors
   or clearly supported limitations.
7. For custom columns, answer specifically according to the column name.
8. Return ONLY valid JSON.

Expected JSON structure:

{json.dumps(schema, indent=2)}

PAPERS:

{"".join(paper_blocks)}
"""

    try:

        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json"
            }
        )

        return json.loads(response.text)

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Gemini analysis failed: {str(exc)}"
        )


# ---------------------------------------------------------
# Schemas
# ---------------------------------------------------------

class MatrixCreate(BaseModel):
    title: str
    description: str | None = None
    project_id: int | None = None


class AddPapersRequest(BaseModel):
    paper_ids: list[int]


class AddColumnRequest(BaseModel):
    name: str


class SaveCellRequest(BaseModel):  
    paper_id: int
    column_id: int
    value: str


# ---------------------------------------------------------
# Create matrix
# ---------------------------------------------------------

@router.post("")
def create_matrix(
    payload: MatrixCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):

    user_id = get_user_id(user)

    matrix = LiteratureMatrix(
        user_id=user_id,
        project_id=payload.project_id,
        title=payload.title,
        description=payload.description
    )

    db.add(matrix)
    db.flush()

    default_columns = [
        ("Dataset", "dataset"),
        ("Method", "method"),
        ("Results", "results"),
        ("Limitations", "limitations")
    ]

    for position, (name, key) in enumerate(default_columns):

        column = LiteratureMatrixColumn(
            matrix_id=matrix.id,
            name=name,
            key=key,
            is_custom=0,
            position=position
        )

        db.add(column)

    db.commit()
    db.refresh(matrix)

    return {
        "id": matrix.id,
        "title": matrix.title,
        "description": matrix.description
    }


# ---------------------------------------------------------
# List matrices
# ---------------------------------------------------------

@router.get("")
def list_matrices(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):

    user_id = get_user_id(user)

    matrices = (
        db.query(LiteratureMatrix)
        .filter(
            LiteratureMatrix.user_id == user_id
        )
        .order_by(
            LiteratureMatrix.created_at.desc()
        )
        .all()
    )

    return [
        {
            "id": matrix.id,
            "title": matrix.title,
            "description": matrix.description,
            "created_at": (
                matrix.created_at.isoformat()
                if matrix.created_at
                else None
            )
        }
        for matrix in matrices
    ]


# ---------------------------------------------------------
# Get matrix
# ---------------------------------------------------------

@router.get("/{matrix_id}")
def get_matrix(
    matrix_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):

    user_id = get_user_id(user)

    matrix = get_matrix_or_404(
        matrix_id,
        user_id,
        db
    )

    columns = (
        db.query(LiteratureMatrixColumn)
        .filter(
            LiteratureMatrixColumn.matrix_id == matrix.id
        )
        .order_by(
            LiteratureMatrixColumn.position
        )
        .all()
    )

    matrix_papers = (
        db.query(LiteratureMatrixPaper)
        .filter(
            LiteratureMatrixPaper.matrix_id == matrix.id
        )
        .order_by(
            LiteratureMatrixPaper.position
        )
        .all()
    )

    cells = (
        db.query(LiteratureMatrixCell)
        .filter(
            LiteratureMatrixCell.matrix_id == matrix.id
        )
        .all()
    )

    cell_map = {}

    for cell in cells:

        cell_map[
            f"{cell.paper_id}:{cell.column_id}"
        ] = {
            "id": cell.id,
            "value": cell.value or "",
            "source": cell.source
        }

    rows = []

    for matrix_paper in matrix_papers:

        row = {
            "paper_id": matrix_paper.paper_id,
            "title": matrix_paper.paper.title,
            "cells": {}
        }

        for column in columns:

            row["cells"][column.id] = cell_map.get(
                f"{matrix_paper.paper_id}:{column.id}",
                {
                    "id": None,
                    "value": "",
                    "source": None
                }
            )

        rows.append(row)

    return {
        "id": matrix.id,
        "title": matrix.title,
        "description": matrix.description,
        "columns": [
            {
                "id": c.id,
                "name": c.name,
                "key": c.key,
                "is_custom": bool(c.is_custom),
                "position": c.position
            }
            for c in columns
        ],
        "papers": rows
    }


# ---------------------------------------------------------
# Add papers
# ---------------------------------------------------------

@router.post("/{matrix_id}/papers")
def add_papers(
    matrix_id: int,
    payload: AddPapersRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):

    user_id = get_user_id(user)

    matrix = get_matrix_or_404(
        matrix_id,
        user_id,
        db
    )

    existing = {
        row.paper_id
        for row in db.query(LiteratureMatrixPaper)
        .filter(
            LiteratureMatrixPaper.matrix_id == matrix.id
        )
        .all()
    }

    position = (
        db.query(LiteratureMatrixPaper)
        .filter(
            LiteratureMatrixPaper.matrix_id == matrix.id
        )
        .count()
    )

    for paper_id in payload.paper_ids:

        if paper_id in existing:
            continue

        paper = (
            db.query(Paper)
            .filter(
                Paper.id == paper_id,
                Paper.user_id == user_id
            )
            .first()
        )

        if not paper:
            raise HTTPException(
                status_code=404,
                detail=f"Paper {paper_id} not found"
            )

        db.add(
            LiteratureMatrixPaper(
                matrix_id=matrix.id,
                paper_id=paper.id,
                position=position
            )
        )

        position += 1

    db.commit()

    return {
        "message": "Papers added successfully"
    }


# ---------------------------------------------------------
# Remove paper
# ---------------------------------------------------------

@router.delete("/{matrix_id}/papers/{paper_id}")
def remove_paper(
    matrix_id: int,
    paper_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):

    user_id = get_user_id(user)

    matrix = get_matrix_or_404(
        matrix_id,
        user_id,
        db
    )

    row = (
        db.query(LiteratureMatrixPaper)
        .filter(
            LiteratureMatrixPaper.matrix_id == matrix.id,
            LiteratureMatrixPaper.paper_id == paper_id
        )
        .first()
    )

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Paper is not in this matrix"
        )

    db.query(LiteratureMatrixCell).filter(
        LiteratureMatrixCell.matrix_id == matrix.id,
        LiteratureMatrixCell.paper_id == paper_id
    ).delete(
        synchronize_session=False
    )

    db.delete(row)
    db.commit()

    return {
        "message": "Paper removed"
    }


# ---------------------------------------------------------
# AI Analyze
# ---------------------------------------------------------

@router.post("/{matrix_id}/analyze")
def analyze_matrix(
    matrix_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):

    require_premium(user, db)

    user_id = get_user_id(user)

    matrix = get_matrix_or_404(
        matrix_id,
        user_id,
        db
    )

    matrix_papers = (
        db.query(LiteratureMatrixPaper)
        .filter(
            LiteratureMatrixPaper.matrix_id == matrix.id
        )
        .order_by(
            LiteratureMatrixPaper.position
        )
        .all()
    )

    if len(matrix_papers) < 2:

        raise HTTPException(
            status_code=400,
            detail="Select at least 2 papers before running AI analysis."
        )

    custom_columns = (
        db.query(LiteratureMatrixColumn)
        .filter(
            LiteratureMatrixColumn.matrix_id == matrix.id,
            LiteratureMatrixColumn.is_custom == 1
        )
        .all()
    )

    papers_data = []

    for item in matrix_papers:

        papers_data.append(
            {
                "id": item.paper.id,
                "title": item.paper.title,
                "text": read_paper_text(item.paper)
            }
        )

    result = generate_ai_analysis(
        papers_data,
        [
            {
                "key": column.key,
                "name": column.name
            }
            for column in custom_columns
        ]
    )

    columns = (
        db.query(LiteratureMatrixColumn)
        .filter(
            LiteratureMatrixColumn.matrix_id == matrix.id
        )
        .all()
    )

    column_by_key = {
        column.key: column
        for column in columns
    }

    for paper_result in result.get("papers", []):

        try:
            raw_id = str(paper_result.get("paper_id", ""))
            paper_id = int(''.join(filter(str.isdigit, raw_id)))
        except ValueError:
            continue

        cells = paper_result.get(
            "cells",
            {}
        )

        for key, value in cells.items():

            column = column_by_key.get(key)

            if not column:
                continue

            existing = (
                db.query(LiteratureMatrixCell)
                .filter(
                    LiteratureMatrixCell.matrix_id == matrix.id,
                    LiteratureMatrixCell.paper_id == paper_id,
                    LiteratureMatrixCell.column_id == column.id
                )
                .first()
            )

            if existing:

                existing.value = str(value)
                existing.source = "AI"

            else:

                db.add(
                    LiteratureMatrixCell(
                        matrix_id=matrix.id,
                        paper_id=paper_id,
                        column_id=column.id,
                        value=str(value),
                        source="AI"
                    )
                )

    db.commit()

    return {
        "message": "AI analysis completed successfully"
    }

# ---------------------------------------------------------
# Delete Column
# ---------------------------------------------------------

@router.delete("/{matrix_id}/columns/{column_id}")
def delete_column(
    matrix_id: int,
    column_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    user_id = get_user_id(user)
    matrix = get_matrix_or_404(matrix_id, user_id, db)

    column = (
        db.query(LiteratureMatrixColumn)
        .filter(
            LiteratureMatrixColumn.id == column_id,
            LiteratureMatrixColumn.matrix_id == matrix.id
        )
        .first()
    )

    if not column:
        raise HTTPException(status_code=404, detail="Column not found")

    # Delete all cell data under this column
    db.query(LiteratureMatrixCell).filter(
        LiteratureMatrixCell.column_id == column_id
    ).delete(synchronize_session=False)

    db.delete(column)
    db.commit()

    return {"message": "Column deleted successfully"}


# ---------------------------------------------------------
# Add custom column
# ---------------------------------------------------------

@router.post("/{matrix_id}/columns")
def add_column(
    matrix_id: int,
    payload: AddColumnRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):

    require_premium(user, db)

    user_id = get_user_id(user)

    matrix = get_matrix_or_404(
        matrix_id,
        user_id,
        db
    )

    name = payload.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Column name is required"
        )

    existing = (
        db.query(LiteratureMatrixColumn)
        .filter(
            LiteratureMatrixColumn.matrix_id == matrix.id
        )
        .all()
    )

    key = (
        name.lower()
        .replace(" ", "_")
        .replace("-", "_")
    )

    base_key = key
    counter = 2

    existing_keys = {
        column.key
        for column in existing
    }

    while key in existing_keys:

        key = f"{base_key}_{counter}"
        counter += 1

    position = len(existing)

    column = LiteratureMatrixColumn(
        matrix_id=matrix.id,
        name=name,
        key=key,
        is_custom=1,
        position=position
    )

    db.add(column)
    db.commit()
    db.refresh(column)

    return {
        "id": column.id,
        "name": column.name,
        "key": column.key,
        "is_custom": True
    }


# ---------------------------------------------------------
# Update cell
# ---------------------------------------------------------

# ---------------------------------------------------------  
# Save or Update Cell  
# ---------------------------------------------------------  

@router.post("/{matrix_id}/cells")
def save_cell(
    matrix_id: int,
    payload: SaveCellRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    user_id = get_user_id(user)
    matrix = get_matrix_or_404(matrix_id, user_id, db)

    # Check if a cell already exists for this matrix, paper, and column
    cell = (
        db.query(LiteratureMatrixCell)
        .filter(
            LiteratureMatrixCell.matrix_id == matrix.id,
            LiteratureMatrixCell.paper_id == payload.paper_id,
            LiteratureMatrixCell.column_id == payload.column_id
        )
        .first()
    )

    if cell:
        cell.value = payload.value
        cell.source = "Manual"
    else:
        cell = LiteratureMatrixCell(
            matrix_id=matrix.id,
            paper_id=payload.paper_id,
            column_id=payload.column_id,
            value=payload.value,
            source="Manual"
        )
        db.add(cell)

    db.commit()
    return {"message": "Cell saved successfully"}

# ---------------------------------------------------------
# CSV Export
# ---------------------------------------------------------

@router.get("/{matrix_id}/export")
def export_matrix(
    matrix_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):

    user_id = get_user_id(user)

    matrix = get_matrix_or_404(
        matrix_id,
        user_id,
        db
    )

    columns = (
        db.query(LiteratureMatrixColumn)
        .filter(
            LiteratureMatrixColumn.matrix_id == matrix.id
        )
        .order_by(
            LiteratureMatrixColumn.position
        )
        .all()
    )

    papers = (
        db.query(LiteratureMatrixPaper)
        .filter(
            LiteratureMatrixPaper.matrix_id == matrix.id
        )
        .order_by(
            LiteratureMatrixPaper.position
        )
        .all()
    )

    cells = (
        db.query(LiteratureMatrixCell)
        .filter(
            LiteratureMatrixCell.matrix_id == matrix.id
        )
        .all()
    )

    cell_map = {
        (
            cell.paper_id,
            cell.column_id
        ): cell.value or ""
        for cell in cells
    }

    output = io.StringIO()

    writer = csv.writer(output)

    header = ["Paper"]

    header.extend(
        column.name
        for column in columns
    )

    writer.writerow(header)

    for matrix_paper in papers:

        row = [
            matrix_paper.paper.title
        ]

        for column in columns:

            row.append(
                cell_map.get(
                    (
                        matrix_paper.paper_id,
                        column.id
                    ),
                    ""
                )
            )

        writer.writerow(row)

    output.seek(0)

    filename = (
        matrix.title
        .replace(" ", "_")
        .replace("/", "_")
        + ".csv"
    )

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="{filename}"'
        }
    )
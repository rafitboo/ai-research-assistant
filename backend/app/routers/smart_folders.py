import numpy as np
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from typing import List

from app.database import get_db
from app.models import SmartFolder, Paper, SmartFolderPaper, DismissedRecommendation, User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/smart-folders", tags=["Smart Folders"])

def get_valid_user_id(current_user, db: Session) -> int:
    if hasattr(current_user, 'id') and current_user.id is not None:
        return current_user.id
    if isinstance(current_user, dict) and current_user.get("id") is not None:
        return current_user.get("id")
    email = getattr(current_user, 'email', None) or (isinstance(current_user, dict) and current_user.get("email"))
    if email:
        db_user = db.query(User).filter(User.email == email).first()
        if db_user:
            return db_user.id
    raise HTTPException(status_code=401, detail="Could not resolve valid user ID from token payload.")


@router.post("/create")
def create_smart_folder(name: str, color: str = "indigo", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = get_valid_user_id(current_user, db)
    
    new_folder = SmartFolder(name=name, color=color, user_id=user_id)
    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)
    return new_folder

@router.get("/{folder_id}/insights")
def get_folder_insights(folder_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = get_valid_user_id(current_user, db)
    folder = db.query(SmartFolder).filter(SmartFolder.id == folder_id, SmartFolder.user_id == user_id).first()
    
    if not folder or not folder.papers:
        return {"total_papers": 0, "completed": 0, "timeline": "N/A", "top_tags": []}

    papers = folder.papers
    completed = sum(1 for p in papers if p.reading_status == "Completed")
    
    years = [p.year for p in papers if getattr(p, 'year', None)]
    timeline = f"{min(years)} - {max(years)}" if years else "Unknown"
    if years and min(years) == max(years):
        timeline = str(min(years))

    all_tags = []
    for p in papers:
        if getattr(p, 'tags', None):
            all_tags.extend([t.strip().upper() for t in p.tags.split(",")])
            
    top_tags = [tag for tag, count in Counter(all_tags).most_common(4)]

    return {
        "total_papers": len(papers),
        "completed": completed,
        "progress_pct": int((completed / len(papers)) * 100) if papers else 0,
        "timeline": timeline,
        "top_tags": top_tags
    }

@router.post("/{folder_id}/add-paper/{paper_id}")
def add_paper_to_folder(folder_id: int, paper_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = get_valid_user_id(current_user, db)
    
    folder = db.query(SmartFolder).filter(SmartFolder.id == folder_id, SmartFolder.user_id == user_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
        
    association = SmartFolderPaper(folder_id=folder_id, paper_id=paper_id)
    db.add(association)
    db.commit()
    return {"message": "Paper added to smart folder successfully"}

@router.get("/{folder_id}/recommendations")
def get_folder_recommendations(folder_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = get_valid_user_id(current_user, db)
    
    folder = db.query(SmartFolder).filter(SmartFolder.id == folder_id, SmartFolder.user_id == user_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    current_papers = folder.papers
    if not current_papers:
        return []

    embeddings = [paper.embedding for paper in current_papers if getattr(paper, 'embedding', None) is not None]
    
    if not embeddings:
        return []
        
    centroid_vector = np.mean(embeddings, axis=0).tolist()
    
    current_paper_ids = [p.id for p in current_papers]
    dismissed_ids = [
        d.paper_id for d in db.query(DismissedRecommendation)\
        .filter(DismissedRecommendation.user_id == user_id).all()
    ]
    exclusions = current_paper_ids + dismissed_ids

    recommendations = db.query(Paper).filter(
        and_(
            Paper.id.notin_(exclusions),
            Paper.embedding.is_not(None)
        )
    ).order_by(
        Paper.embedding.cosine_distance(centroid_vector)
    ).limit(10).all()

    return recommendations

@router.post("/recommendations/{paper_id}/dismiss")
def dismiss_recommendation(paper_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = get_valid_user_id(current_user, db)
    
    dismissal = DismissedRecommendation(user_id=user_id, paper_id=paper_id)
    db.add(dismissal)
    db.commit()
    return {"message": "Recommendation permanently dismissed"}

@router.get("/")
def list_folders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = get_valid_user_id(current_user, db)
    
    folders = db.query(SmartFolder).filter(SmartFolder.user_id == user_id).all()
    return [{"id": f.id, "name": f.name, "color": getattr(f, 'color', 'indigo'), "paper_count": len(f.papers)} for f in folders]

@router.get("/{folder_id}/papers")
def list_folder_papers(folder_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = get_valid_user_id(current_user, db)
    
    folder = db.query(SmartFolder).filter(SmartFolder.id == folder_id, SmartFolder.user_id == user_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder.papers

@router.delete("/{folder_id}/remove-paper/{paper_id}")
def remove_paper_from_folder(folder_id: int, paper_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = get_valid_user_id(current_user, db)
    
    folder = db.query(SmartFolder).filter(SmartFolder.id == folder_id, SmartFolder.user_id == user_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
        
    association = db.query(SmartFolderPaper).filter_by(folder_id=folder_id, paper_id=paper_id).first()
    if not association:
        raise HTTPException(status_code=404, detail="Paper is not in this folder")
        
    db.delete(association)
    db.commit()
    return {"message": "Paper successfully removed from the folder"}

# --- NEW: Delete Entire Folder Route ---
@router.delete("/{folder_id}")
def delete_smart_folder(folder_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = get_valid_user_id(current_user, db)
    
    folder = db.query(SmartFolder).filter(SmartFolder.id == folder_id, SmartFolder.user_id == user_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
        
    db.delete(folder)
    db.commit()
    return {"message": "Folder successfully deleted"}
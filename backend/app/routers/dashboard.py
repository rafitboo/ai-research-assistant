from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Paper, Project, ProjectMember, User
from app.auth_utils import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/overview")
def get_dashboard_overview(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user["user_id"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Summary Metrics
    total_papers = db.query(Paper).filter(Paper.user_id == user_id).count()
    completed_papers = db.query(Paper).filter(
        Paper.user_id == user_id, 
        Paper.reading_status == "Completed"
    ).count()
    
    joined_project_ids = db.query(ProjectMember.project_id).filter(ProjectMember.user_id == user_id)
    total_projects = db.query(Project).filter(
        (Project.owner_id == user_id) | (Project.id.in_(joined_project_ids))
    ).count()

    # Recent Papers List
    recent_papers_query = db.query(Paper).filter(Paper.user_id == user_id).order_by(Paper.created_at.desc()).limit(8).all()
    recent_papers = [
        {
            "id": p.id,
            "title": p.title,
            "tag": p.topic or p.tags or "General",
            "status": p.reading_status or "Unread"
        } for p in recent_papers_query
    ]

    # Recent Projects List with Member Counts
    projects_query = db.query(Project).filter(
        (Project.owner_id == user_id) | (Project.id.in_(joined_project_ids))
    ).order_by(Project.created_at.desc()).limit(5).all()

    recent_projects = []
    for proj in projects_query:
        member_count = db.query(ProjectMember).filter(ProjectMember.project_id == proj.id).count() + 1 # include owner
        recent_projects.append({
            "id": proj.id,
            "title": proj.title,
            "members_count": member_count
        })

    return {
        "total_papers": total_papers,
        "completed_papers": completed_papers,
        "total_projects": total_projects,
        "subscription_plan": user.subscription_tier or "Free",
        "recent_papers": recent_papers,
        "recent_projects": recent_projects
    }
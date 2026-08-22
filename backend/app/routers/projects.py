from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import Project, ProjectMember, User
from app.auth_utils import get_current_user
from app.audit import log_audit

router = APIRouter(prefix="/api/projects", tags=["Projects"])


class ProjectCreateSchema(BaseModel):
    title: str
    description: Optional[str] = None


@router.post("/create")
def create_project(
    data: ProjectCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["user_id"]
    
    if not data.title or not data.title.strip():
        raise HTTPException(status_code=400, detail="Project title is required")
    
    # 1. Create the project setting current user as owner
    new_project = Project(
        title=data.title.strip(),
        description=data.description.strip() if data.description else None,
        owner_id=user_id
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    # 2. Add creator as a project member with 'Owner' role
    owner_member = ProjectMember(
        project_id=new_project.id,
        user_id=user_id,
        role="Owner"
    )
    db.add(owner_member)

    log_audit(
        db, new_project.id, user_id,
        action="project.created",
        description=f"Project '{new_project.title}' was created.",
        entity_type="project",
        entity_id=new_project.id,
    )

    db.commit()

    return {"message": "Project created successfully", "project_id": new_project.id}


@router.get("/")
def list_projects(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["user_id"]
    
    # Fetch projects where user is owner OR a member
    joined_project_ids = db.query(ProjectMember.project_id).filter(ProjectMember.user_id == user_id)
    projects = db.query(Project).filter(
        (Project.owner_id == user_id) | (Project.id.in_(joined_project_ids))
    ).order_by(Project.created_at.desc()).all()

    result = []
    for p in projects:
        owner = db.query(User).filter(User.id == p.owner_id).first()
        member_count = db.query(ProjectMember).filter(ProjectMember.project_id == p.id).count()
        
        result.append({
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "created_at": p.created_at.strftime("%B %d, %Y") if p.created_at else None,
            "owner_id": p.owner_id,
            "owner_name": owner.name if owner else "Unknown",
            "is_owner": (p.owner_id == user_id),
            "member_count": member_count if member_count > 0 else 1
        })

    return result
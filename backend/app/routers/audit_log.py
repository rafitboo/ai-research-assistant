from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, ProjectMember, AuditLog, User
from app.auth_utils import get_current_user

router = APIRouter(prefix="/api/projects", tags=["Audit Log"])


def get_user_id(user_dict: dict) -> int:
    user_id = user_dict.get("user_id") or user_dict.get("sub") or user_dict.get("id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="User ID not found")
    return int(user_id)


def _require_project_access(project_id: int, user_id: int, db: Session) -> Project:
    """Same owner-or-member pattern used in collaboration.py / supervisor_portal.py."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    is_owner = project.owner_id == user_id
    is_member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
        is not None
    )
    if not (is_owner or is_member):
        raise HTTPException(status_code=403, detail="You don't have access to this project")
    return project


@router.get("/{project_id}/audit-log")
def get_project_audit_log(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    _require_project_access(project_id, user_id, db)

    entries = (
        db.query(AuditLog)
        .filter(AuditLog.project_id == project_id)
        .order_by(AuditLog.created_at.desc())
        .limit(200)
        .all()
    )

    result = []
    for entry in entries:
        actor = db.query(User).filter(User.id == entry.user_id).first() if entry.user_id else None
        result.append({
            "id": entry.id,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "description": entry.description,
            "actor_name": actor.name if actor else "System",
            "created_at": entry.created_at,
        })
    return result
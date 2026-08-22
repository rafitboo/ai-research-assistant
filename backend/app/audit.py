from sqlalchemy.orm import Session
from app.models import AuditLog


def log_audit(
    db: Session,
    project_id: int,
    user_id: int,
    action: str,
    description: str,
    entity_type: str = None,
    entity_id: int = None,
) -> AuditLog:
    entry = AuditLog(
        project_id=project_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
    )
    db.add(entry)
    return entry
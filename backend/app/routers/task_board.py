from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth_utils import get_current_user
from app.database import get_db
from app.models import Project, ProjectMember, User, Task, ResearchMilestone
from app.notifications import create_notification
from app.audit import log_audit

router = APIRouter(prefix="/api/task-board", tags=["Task Board & Milestone Timeline"])

VALID_STATUSES = {"Todo", "In Progress", "Done"}


class TaskCreatePayload(BaseModel):
    project_id: int
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    milestone_id: Optional[int] = None
    milestone_title: Optional[str] = None
    depends_on_id: Optional[int] = None
    assignee_id: Optional[int] = None

class TaskUpdatePayload(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[date] = None
    milestone_id: Optional[int] = None
    depends_on_id: Optional[int] = None
    assignee_id: Optional[int] = None


class TaskStatusPayload(BaseModel):
    status: str


def get_user_id(user_dict: dict) -> int:
    user_id = user_dict.get("user_id") or user_dict.get("sub") or user_dict.get("id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="User ID not found")
    return int(user_id)


def require_project_access(project_id: int, user_id: int, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )
    if project.owner_id != user_id and not member:
        raise HTTPException(status_code=403, detail="You don't have access to this project")

    return project


def refresh_overdue_flags(db: Session, project_id: int) -> None:
    """Flags Todo/In Progress tasks whose due_date has passed. Called on every read
    so the board and the timeline always reflect current overdue state."""
    today = date.today()
    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    changed = False
    for t in tasks:
        should_be_overdue = bool(
            t.due_date and t.due_date < today and t.status != "Done"
        )
        new_flag = 1 if should_be_overdue else 0
        if t.is_overdue != new_flag:
            t.is_overdue = new_flag
            changed = True
    if changed:
        db.commit()


def serialize_task(t: Task, db: Session) -> dict:
    assignee = db.query(User).filter(User.id == t.assignee_id).first() if t.assignee_id else None
    creator = db.query(User).filter(User.id == t.created_by).first()
    blocker = db.query(Task).filter(Task.id == t.depends_on_id).first() if t.depends_on_id else None
    return {
        "id": t.id,
        "project_id": t.project_id,
        "milestone_id": t.milestone_id,
        "depends_on_id": t.depends_on_id,
        "depends_on_title": blocker.title if blocker else None,
        "depends_on_done": (blocker.status == "Done") if blocker else True,
        "title": t.title,
        "description": t.description,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "assignee_id": t.assignee_id,
        "assignee_name": assignee.name if assignee else None,
        "created_by": t.created_by,
        "created_by_name": creator.name if creator else "Unknown",
        "status": t.status,
        "is_overdue": bool(t.is_overdue),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("/projects/{project_id}/tasks")
def list_tasks(project_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    require_project_access(project_id, user_id, db)
    refresh_overdue_flags(db, project_id)

    tasks = (
        db.query(Task)
        .filter(Task.project_id == project_id)
        .order_by(Task.due_date.asc().nullslast(), Task.id.asc())
        .all()
    )
    return [serialize_task(t, db) for t in tasks]


@router.post("/tasks")
def create_task(payload: TaskCreatePayload, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    require_project_access(payload.project_id, user_id, db)

    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Task title is required")

    target_milestone_id = payload.milestone_id

    # Handle custom milestone input or fetch existing
    if payload.milestone_title and payload.milestone_title.strip():
        clean_title = payload.milestone_title.strip()
        existing_milestone = (
            db.query(ResearchMilestone)
            .filter(
                ResearchMilestone.project_id == payload.project_id,
                ResearchMilestone.title.ilike(clean_title)
            )
            .first()
        )
        if existing_milestone:
            target_milestone_id = existing_milestone.id
        else:
            # Create a dedicated milestone with created_by set
            new_milestone = ResearchMilestone(
                project_id=payload.project_id,
                created_by=user_id,  # Added to satisfy NOT NULL constraint
                title=clean_title,
                due_date=payload.due_date,
                status="Pending"
            )
            db.add(new_milestone)
            db.flush()  # Populates new_milestone.id before task insertion
            target_milestone_id = new_milestone.id

    elif target_milestone_id is not None:
        milestone = (
            db.query(ResearchMilestone)
            .filter(ResearchMilestone.id == target_milestone_id, ResearchMilestone.project_id == payload.project_id)
            .first()
        )
        if not milestone:
            raise HTTPException(status_code=400, detail="Milestone not found in this project")

    if payload.depends_on_id is not None:
        blocker = (
            db.query(Task)
            .filter(Task.id == payload.depends_on_id, Task.project_id == payload.project_id)
            .first()
        )
        if not blocker:
            raise HTTPException(status_code=400, detail="Dependency task not found in this project")

    task = Task(
        project_id=payload.project_id,
        milestone_id=target_milestone_id,
        depends_on_id=payload.depends_on_id,
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        due_date=payload.due_date,
        assignee_id=payload.assignee_id,
        created_by=user_id,
        status="Todo",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    log_audit(
        db, payload.project_id, user_id,
        action="task.created",
        description=f"Task '{task.title}' was created.",
        entity_type="task", entity_id=task.id,
    )
    if task.assignee_id and task.assignee_id != user_id:
        create_notification(
            db, task.assignee_id, f"You were assigned to task '{task.title}'.",
            type="task_assigned", title="New task assigned",
            project_id=payload.project_id, reference_id=task.id,
        )
    db.commit()

    return {"message": "Task created", "task_id": task.id}


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdatePayload, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    require_project_access(task.project_id, user_id, db)

    if payload.depends_on_id is not None and payload.depends_on_id == task.id:
        raise HTTPException(status_code=400, detail="A task cannot depend on itself")

    for field in ("title", "description", "due_date", "milestone_id", "depends_on_id", "assignee_id"):
        value = getattr(payload, field)
        if value is not None:
            if field == "title":
                value = value.strip()
            setattr(task, field, value)

    db.commit()

    log_audit(
        db, task.project_id, user_id,
        action="task.updated",
        description=f"Task '{task.title}' was updated.",
        entity_type="task", entity_id=task.id,
    )
    db.commit()

    return {"message": "Task updated"}


@router.post("/tasks/{task_id}/status")
def update_task_status(task_id: int, payload: TaskStatusPayload, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Moves a task between Kanban columns. Blocks moving to 'Done' while its
    dependency isn't done yet, since the board manages *dependent* tasks."""
    user_id = get_user_id(user)
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    require_project_access(task.project_id, user_id, db)

    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Status must be Todo, In Progress, or Done")

    if task.assignee_id and task.assignee_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the assigned person can change this task's status",
        )

    if task.status == "Done" and payload.status != "Done":
        raise HTTPException(
            status_code=400,
            detail="This task is already Done. Reopen it explicitly instead of dragging it.",
        )

    if payload.status == "Done" and task.depends_on_id:
        blocker = db.query(Task).filter(Task.id == task.depends_on_id).first()
        if blocker and blocker.status != "Done":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot complete this task before its dependency '{blocker.title}' is done",
            )

    task.status = payload.status
    if payload.status == "Done":
        task.is_overdue = 0

    log_audit(
        db, task.project_id, user_id,
        action="task.status_changed",
        description=f"Task '{task.title}' moved to {payload.status}.",
        entity_type="task", entity_id=task.id,
    )
    db.commit()

    return {"message": f"Task moved to {payload.status}"}


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    project = require_project_access(task.project_id, user_id, db)

    if project.owner_id != user_id and task.created_by != user_id:
        raise HTTPException(
            status_code=403,
            detail="Only the project owner or the task's creator can delete this task",
        )

    title = task.title
    db.delete(task)

    log_audit(
        db, task.project_id, user_id,
        action="task.deleted",
        description=f"Task '{title}' was deleted.",
        entity_type="task", entity_id=task_id,
    )
    db.commit()

    return {"message": "Task deleted"}


@router.get("/projects/{project_id}/timeline")
def get_task_timeline(project_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Visual milestone timeline populated automatically from tasks.
    Groups tasks under their milestone (or 'Unassigned') and flags overdue
    items across both the board and this timeline."""
    user_id = get_user_id(user)
    require_project_access(project_id, user_id, db)
    refresh_overdue_flags(db, project_id)

    milestones = (
        db.query(ResearchMilestone)
        .filter(ResearchMilestone.project_id == project_id)
        .order_by(ResearchMilestone.due_date.asc().nullslast(), ResearchMilestone.id.asc())
        .all()
    )

    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    tasks_by_milestone: dict = {}
    unassigned = []
    for t in tasks:
        entry = serialize_task(t, db)
        if t.milestone_id:
            tasks_by_milestone.setdefault(t.milestone_id, []).append(entry)
        else:
            unassigned.append(entry)

    timeline = []
    for m in milestones:
        m_tasks = tasks_by_milestone.get(m.id, [])
        timeline.append(
            {
                "milestone_id": m.id,
                "milestone_title": m.title,
                "due_date": m.due_date.isoformat() if m.due_date else None,
                "milestone_status": m.status,
                "tasks": m_tasks,
                "has_overdue": any(t["is_overdue"] for t in m_tasks),
            }
        )

    if unassigned:
        timeline.append(
            {
                "milestone_id": None,
                "milestone_title": "Unassigned",
                "due_date": None,
                "milestone_status": None,
                "tasks": unassigned,
                "has_overdue": any(t["is_overdue"] for t in unassigned),
            }
        )

    return timeline
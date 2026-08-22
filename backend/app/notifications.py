from datetime import date
from sqlalchemy.orm import Session
from app.models import Notification, ResearchMilestone


def create_notification(
    db: Session,
    user_id: int,
    message: str,
    type: str = None,
    title: str = None,
    project_id: int = None,
    reference_id: int = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        message=message,
        type=type,
        title=title,
        project_id=project_id,
        reference_id=reference_id,
        is_read=0,
    )
    db.add(notif)
    return notif


def ensure_overdue_milestone_notifications(db: Session, user_id: int) -> None:

    today = date.today()
    overdue = (
        db.query(ResearchMilestone)
        .filter(
            ResearchMilestone.created_by == user_id,
            ResearchMilestone.due_date.isnot(None),
            ResearchMilestone.due_date < today,
            ResearchMilestone.status != "Approved",
        )
        .all()
    )
    if not overdue:
        return

    for milestone in overdue:
        existing = (
            db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.type == "milestone_overdue",
                Notification.reference_id == milestone.id,
            )
            .first()
        )
        if not existing:
            create_notification(
                db,
                user_id,
                f"Milestone '{milestone.title}' is overdue.",
                type="milestone_overdue",
                title="Overdue milestone",
                project_id=milestone.project_id,
                reference_id=milestone.id,
            )
    db.commit()
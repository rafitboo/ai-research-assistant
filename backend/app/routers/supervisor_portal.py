from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.auth_utils import get_current_user
from app.database import get_db
from app.models import (
    Project,
    ProjectMember,
    User,
    Notification,
    ConsultationRequest,
    ResearchMilestone,
    MilestoneReview
)


router = APIRouter(
    prefix="/api/supervisor-portal",
    tags=["Supervisor Consultation & Review"],
)

ACTIVE_MEETING_STATUSES = {"Pending", "Approved"}
VALID_MEETING_DECISIONS = {"Approved", "Declined"}
VALID_MILESTONE_DECISIONS = {"Approved", "Revision Requested"}


class MeetingRequestPayload(BaseModel):
    project_id: int
    supervisor_id: int
    start_at: str
    end_at: str
    topic: str
    notes: Optional[str] = None


class MeetingDecisionPayload(BaseModel):
    decision: str
    response: Optional[str] = None


class MilestoneCreatePayload(BaseModel):
    project_id: int
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None


class MilestoneReviewPayload(BaseModel):
    decision: str
    comments: Optional[str] = None


def get_user_id(user_dict: dict) -> int:
    user_id = user_dict.get("user_id") or user_dict.get("sub") or user_dict.get("id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="User ID not found")
    return int(user_id)


def parse_client_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid meeting date/time") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


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


def project_member(project_id: int, user_id: int, db: Session) -> Optional[ProjectMember]:
    return (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )


def require_supervisor(project_id: int, user_id: int, db: Session) -> None:
    member = project_member(project_id, user_id, db)
    if not member or member.role != "Supervisor":
        raise HTTPException(status_code=403, detail="Supervisor access is required for this action")


def is_project_participant(project_id: int, user_id: int, db: Session) -> bool:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return False
    if project.owner_id == user_id:
        return True
    return project_member(project_id, user_id, db) is not None


def has_meeting_collision(
    db: Session,
    *,
    supervisor_id: int,
    requester_id: int,
    start_at: datetime,
    end_at: datetime,
    exclude_id: Optional[int] = None,
) -> Optional[str]:
    conditions = [
        ConsultationRequest.status.in_(ACTIVE_MEETING_STATUSES),
        ConsultationRequest.start_at < end_at,
        ConsultationRequest.end_at > start_at,
        or_(
            ConsultationRequest.supervisor_id == supervisor_id,
            ConsultationRequest.requester_id == requester_id,
        ),
    ]

    if exclude_id is not None:
        conditions.append(ConsultationRequest.id != exclude_id)

    collision = db.query(ConsultationRequest).filter(and_(*conditions)).first()
    if not collision:
        return None

    if collision.supervisor_id == supervisor_id:
        return "The selected supervisor already has another meeting in this time range."
    return "You already have another meeting in this time range."


def notify(db: Session, user_id: int, message: str) -> None:
    db.add(Notification(user_id=user_id, message=message, is_read=0))


@router.get("/projects")
def list_supervision_projects(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)

    member_project_ids = db.query(ProjectMember.project_id).filter(ProjectMember.user_id == user_id)
    projects = (
        db.query(Project)
        .filter(or_(Project.owner_id == user_id, Project.id.in_(member_project_ids)))
        .order_by(Project.created_at.desc())
        .all()
    )

    result = []
    for project in projects:
        member = project_member(project.id, user_id, db)
        role = "Owner" if project.owner_id == user_id else (member.role if member else "Member")
        result.append(
            {
                "id": project.id,
                "title": project.title,
                "description": project.description,
                "role": role,
            }
        )

    return result


@router.get("/projects/{project_id}/supervisors")
def list_project_supervisors(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    project = require_project_access(project_id, user_id, db)

    members = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.id, ProjectMember.role == "Supervisor")
        .all()
    )

    result = []
    for member in members:
        if member.user:
            result.append({"id": member.user.id, "name": member.user.name, "email": member.user.email})

    return result


@router.get("/projects/{project_id}/meetings")
def list_project_meetings(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    require_project_access(project_id, user_id, db)

    meetings = (
        db.query(ConsultationRequest)
        .filter(ConsultationRequest.project_id == project_id)
        .order_by(ConsultationRequest.start_at.asc())
        .all()
    )

    result = []
    for meeting in meetings:
        requester = db.query(User).filter(User.id == meeting.requester_id).first()
        supervisor = db.query(User).filter(User.id == meeting.supervisor_id).first()
        result.append(
            {
                "id": meeting.id,
                "requester_id": meeting.requester_id,
                "requester_name": requester.name if requester else "Unknown",
                "supervisor_id": meeting.supervisor_id,
                "supervisor_name": supervisor.name if supervisor else "Unknown",
                "start_at": meeting.start_at.isoformat() if meeting.start_at else None,
                "end_at": meeting.end_at.isoformat() if meeting.end_at else None,
                "topic": meeting.topic,
                "notes": meeting.notes,
                "status": meeting.status,
                "supervisor_response": meeting.supervisor_response,
                "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
            }
        )

    return result


@router.post("/meetings/request")
def request_meeting(
    payload: MeetingRequestPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    require_project_access(payload.project_id, user_id, db)

    supervisor_member = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == payload.project_id,
            ProjectMember.user_id == payload.supervisor_id,
            ProjectMember.role == "Supervisor",
        )
        .first()
    )
    if not supervisor_member:
        raise HTTPException(status_code=400, detail="Selected user is not a supervisor for this project")

    if payload.supervisor_id == user_id:
        raise HTTPException(status_code=400, detail="You cannot request a meeting with yourself")

    start_at = parse_client_datetime(payload.start_at)
    end_at = parse_client_datetime(payload.end_at)

    if end_at <= start_at:
        raise HTTPException(status_code=400, detail="Meeting end time must be after start time")

    duration_seconds = (end_at - start_at).total_seconds()
    if duration_seconds < 15 * 60:
        raise HTTPException(status_code=400, detail="Meeting must be at least 15 minutes long")
    if duration_seconds > 4 * 60 * 60:
        raise HTTPException(status_code=400, detail="Meeting cannot be longer than 4 hours")

    collision_message = has_meeting_collision(
        db,
        supervisor_id=payload.supervisor_id,
        requester_id=user_id,
        start_at=start_at,
        end_at=end_at,
    )
    if collision_message:
        raise HTTPException(status_code=409, detail=collision_message)

    if not payload.topic.strip():
        raise HTTPException(status_code=400, detail="Meeting topic is required")

    meeting = ConsultationRequest(
        project_id=payload.project_id,
        requester_id=user_id,
        supervisor_id=payload.supervisor_id,
        start_at=start_at,
        end_at=end_at,
        topic=payload.topic.strip(),
        notes=payload.notes.strip() if payload.notes else None,
        status="Pending",
    )
    db.add(meeting)
    notify(db, payload.supervisor_id, f"New consultation request: {payload.topic.strip()}")
    db.commit()
    db.refresh(meeting)

    return {"message": "Meeting request submitted", "meeting_id": meeting.id}


@router.post("/meetings/{meeting_id}/decision")
def decide_meeting(
    meeting_id: int,
    payload: MeetingDecisionPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    meeting = db.query(ConsultationRequest).filter(ConsultationRequest.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting request not found")

    require_supervisor(meeting.project_id, user_id, db)

    if meeting.supervisor_id != user_id:
        raise HTTPException(status_code=403, detail="You are not the supervisor assigned to this request")

    if meeting.status != "Pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be decided")

    if payload.decision not in VALID_MEETING_DECISIONS:
        raise HTTPException(status_code=400, detail="Decision must be Approved or Declined")

    if payload.decision == "Approved":
        collision_message = has_meeting_collision(
            db,
            supervisor_id=meeting.supervisor_id,
            requester_id=meeting.requester_id,
            start_at=meeting.start_at,
            end_at=meeting.end_at,
            exclude_id=meeting.id,
        )
        if collision_message:
            raise HTTPException(status_code=409, detail=collision_message)

    meeting.status = payload.decision
    meeting.supervisor_response = payload.response.strip() if payload.response else None

    if payload.decision == "Approved":
        notify(db, meeting.requester_id, f"Your consultation request for '{meeting.topic}' was approved.")
    else:
        notify(db, meeting.requester_id, f"Your consultation request for '{meeting.topic}' was declined.")

    db.commit()
    return {"message": f"Meeting request {payload.decision.lower()}"}


@router.post("/meetings/{meeting_id}/cancel")
def cancel_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    meeting = db.query(ConsultationRequest).filter(ConsultationRequest.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting request not found")

    if meeting.requester_id != user_id and meeting.supervisor_id != user_id:
        raise HTTPException(status_code=403, detail="You cannot cancel this meeting")

    if meeting.status not in ACTIVE_MEETING_STATUSES:
        raise HTTPException(status_code=400, detail="Only pending or approved meetings can be cancelled")

    meeting.status = "Cancelled"
    db.commit()
    return {"message": "Meeting cancelled"}


@router.get("/projects/{project_id}/milestones")
def list_milestones(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    require_project_access(project_id, user_id, db)

    milestones = (
        db.query(ResearchMilestone)
        .filter(ResearchMilestone.project_id == project_id)
        .order_by(ResearchMilestone.due_date.asc().nullslast(), ResearchMilestone.created_at.asc())
        .all()
    )

    result = []
    for milestone in milestones:
        creator = db.query(User).filter(User.id == milestone.created_by).first()
        reviewer = db.query(User).filter(User.id == milestone.reviewed_by).first() if milestone.reviewed_by else None
        result.append(
            {
                "id": milestone.id,
                "title": milestone.title,
                "description": milestone.description,
                "due_date": milestone.due_date.isoformat() if milestone.due_date else None,
                "status": milestone.status,
                "created_by": milestone.created_by,
                "created_by_name": creator.name if creator else "Unknown",
                "submitted_at": milestone.submitted_at.isoformat() if milestone.submitted_at else None,
                "reviewed_at": milestone.reviewed_at.isoformat() if milestone.reviewed_at else None,
                "reviewed_by": milestone.reviewed_by,
                "reviewed_by_name": reviewer.name if reviewer else None,
                "latest_review_comment": milestone.latest_review_comment,
            }
        )

    return result


@router.post("/milestones")
def create_milestone(
    payload: MilestoneCreatePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    require_project_access(payload.project_id, user_id, db)

    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Milestone title is required")

    milestone = ResearchMilestone(
        project_id=payload.project_id,
        created_by=user_id,
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        due_date=payload.due_date,
        status="Draft",
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)

    return {"message": "Milestone created", "milestone_id": milestone.id}


@router.post("/milestones/{milestone_id}/submit")
def submit_milestone(
    milestone_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    milestone = db.query(ResearchMilestone).filter(ResearchMilestone.id == milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")

    require_project_access(milestone.project_id, user_id, db)

    if milestone.created_by != user_id:
        raise HTTPException(status_code=403, detail="Only the milestone creator can submit it for review")

    if milestone.status not in {"Draft", "Revision Requested"}:
        raise HTTPException(status_code=400, detail="This milestone is not ready for submission")

    milestone.status = "Pending Review"
    milestone.submitted_at = datetime.now(timezone.utc)
    db.commit()

    supervisors = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == milestone.project_id, ProjectMember.role == "Supervisor")
        .all()
    )
    for supervisor in supervisors:
        notify(db, supervisor.user_id, f"Milestone submitted for review: {milestone.title}")
    db.commit()

    return {"message": "Milestone submitted for review"}


@router.post("/milestones/{milestone_id}/review")
def review_milestone(
    milestone_id: int,
    payload: MilestoneReviewPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    milestone = db.query(ResearchMilestone).filter(ResearchMilestone.id == milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")

    require_supervisor(milestone.project_id, user_id, db)

    if payload.decision not in VALID_MILESTONE_DECISIONS:
        raise HTTPException(status_code=400, detail="Decision must be Approved or Revision Requested")

    if milestone.status != "Pending Review":
        raise HTTPException(status_code=400, detail="Only submitted milestones can be reviewed")

    milestone.status = payload.decision
    milestone.reviewed_by = user_id
    milestone.reviewed_at = datetime.now(timezone.utc)
    milestone.latest_review_comment = payload.comments.strip() if payload.comments else None

    review = MilestoneReview(
        milestone_id=milestone.id,
        supervisor_id=user_id,
        decision=payload.decision,
        comments=payload.comments.strip() if payload.comments else None,
    )
    db.add(review)
    notify(db, milestone.created_by, f"Milestone '{milestone.title}' was marked {payload.decision}.")
    db.commit()

    return {"message": f"Milestone {payload.decision.lower()}"}


@router.get("/projects/{project_id}/timeline")
def get_project_timeline_status(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Stable timeline data source for this feature.
    A future Module 3 timeline can consume this endpoint without
    changing the existing Module 3 Feature 3 implementation.
    """
    user_id = get_user_id(user)
    require_project_access(project_id, user_id, db)

    milestones = (
        db.query(ResearchMilestone)
        .filter(ResearchMilestone.project_id == project_id)
        .order_by(ResearchMilestone.due_date.asc().nullslast(), ResearchMilestone.id.asc())
        .all()
    )

    return [
        {
            "id": m.id,
            "title": m.title,
            "due_date": m.due_date.isoformat() if m.due_date else None,
            "status": m.status,
        }
        for m in milestones
    ]

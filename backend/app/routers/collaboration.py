"""
NEW FILE — place at: app/routers/collaboration.py

Covers Module 2, Member 3's combined feature:
  "Discussion Board + Project Membership & Invitations"

  - Invite by email, assign role (Collaborator / Supervisor)
  - Pending invitations auto-expire after 7 days, one-click resend
  - Once a member joins, they get access to a per-project discussion
    board with threaded, timestamped, attributed posts
  - @mentions trigger a notification for the mentioned user

Fixes applied vs. the original draft:
  - Ownership/membership checks added on resend, posts, and members
    endpoints (previously anyone authenticated could hit any project_id)
  - Added GET /projects/{id}/members — the actual "project detail page
    shows all current members and their roles" requirement, which the
    original draft never implemented (it only showed invitations)
  - Added GET /my-invitations — lets an invited user see invites sent
    to their email so they can actually accept them (the original draft
    defined the accept endpoint but nothing ever called it)
  - Duplicate-pending-invite prevention
  - Role values aligned with the spec wording: "Collaborator" / "Supervisor"
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, ProjectMember, ProjectInvitation, DiscussionPost, Notification, User
from app.auth_utils import get_current_user
from app.notifications import create_notification, ensure_overdue_milestone_notifications
from app.audit import log_audit

router = APIRouter(prefix="/api/collaboration", tags=["Collaboration"])

VALID_ROLES = {"Collaborator", "Supervisor"}
INVITE_EXPIRY_DAYS = 7


class InviteRequest(BaseModel):
    email: str
    role: str = "Collaborator"


class PostRequest(BaseModel):
    content: str
    parent_id: Optional[int] = None


def get_user_id(user_dict: dict) -> int:
    """Same pattern as journal.py's get_user_id_from_token, for consistency."""
    user_id = user_dict.get("user_id") or user_dict.get("sub") or user_dict.get("id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="User ID not found in token payload")
    return int(user_id)


def _require_project_access(project_id: int, user_id: int, db: Session) -> Project:
    """Owner OR existing member only — blocks guessing project_ids."""
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


def _expire_stale_invitations(invitations: list[ProjectInvitation], db: Session) -> None:
    now = datetime.now(timezone.utc)
    changed = False
    for inv in invitations:
        if inv.status == "Pending" and inv.created_at:
            created_at = inv.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if (now - created_at) > timedelta(days=INVITE_EXPIRY_DAYS):
                inv.status = "Expired"
                changed = True
    if changed:
        db.commit()


# --- Invitations & Membership ---

@router.post("/projects/{project_id}/invite")
def invite_member(
    project_id: int,
    payload: InviteRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == user_id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Only project owners can send invitations.")

    role = payload.role if payload.role in VALID_ROLES else "Collaborator"

    existing = (
        db.query(ProjectInvitation)
        .filter(
            ProjectInvitation.project_id == project_id,
            ProjectInvitation.email == payload.email,
            ProjectInvitation.status == "Pending",
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="An invitation is already pending for this email.")

    invitation = ProjectInvitation(project_id=project_id, email=payload.email, role=role, status="Pending")
    db.add(invitation)

    log_audit(
        db, project_id, user_id,
        action="invitation.sent",
        description=f"Invited {payload.email} as {role}.",
        entity_type="invitation",
    )

    # Notify the invited person only if they already have an account (Notification.user_id is a real FK).
    invited_user = db.query(User).filter(User.email == payload.email).first()
    if invited_user:
        create_notification(
            db, invited_user.id,
            f"You were invited to join '{project.title}' as {role}.",
            type="project_invitation", title="Project invitation",
            project_id=project_id,
        )

    db.commit()
    return {"message": "Invitation sent successfully"}


@router.get("/projects/{project_id}/invitations")
def get_invitations(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    _require_project_access(project_id, user_id, db)

    invitations = db.query(ProjectInvitation).filter(ProjectInvitation.project_id == project_id).all()
    _expire_stale_invitations(invitations, db)

    return [
        {"id": i.id, "email": i.email, "role": i.role, "status": i.status, "created_at": i.created_at}
        for i in invitations
    ]


@router.post("/invitations/{invitation_id}/resend")
def resend_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    inv = db.query(ProjectInvitation).filter(ProjectInvitation.id == invitation_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")

    project = db.query(Project).filter(Project.id == inv.project_id).first()
    if not project or project.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only the project owner can resend invitations.")

    inv.status = "Pending"
    inv.created_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Invitation re-sent successfully"}


@router.get("/my-invitations")
def get_my_invitations(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Invitations addressed to the logged-in user's email, still pending."""
    user_id = get_user_id(user)
    current = db.query(User).filter(User.id == user_id).first()
    if not current:
        raise HTTPException(status_code=404, detail="User not found")

    invites = (
        db.query(ProjectInvitation)
        .filter(ProjectInvitation.email == current.email, ProjectInvitation.status == "Pending")
        .all()
    )
    _expire_stale_invitations(invites, db)

    result = []
    for inv in invites:
        if inv.status != "Pending":
            continue
        result.append(
            {
                "id": inv.id,
                "project_id": inv.project_id,
                "project_title": inv.project.title if inv.project else "Unknown Project",
                "role": inv.role,
                "created_at": inv.created_at,
            }
        )
    return result


@router.post("/invitations/{invitation_id}/accept")
def accept_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    current_user_obj = db.query(User).filter(User.id == user_id).first()

    inv = db.query(ProjectInvitation).filter(ProjectInvitation.id == invitation_id).first()
    if not inv or inv.status != "Pending":
        raise HTTPException(status_code=400, detail="Invalid or expired invitation")

    if current_user_obj.email != inv.email:
        raise HTTPException(status_code=403, detail="This invitation was sent to a different email address.")

    inv.status = "Accepted"

    existing_member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == inv.project_id, ProjectMember.user_id == user_id)
        .first()
    )
    if not existing_member:
        new_member = ProjectMember(project_id=inv.project_id, user_id=user_id, role=inv.role)
        db.add(new_member)

    project = db.query(Project).filter(Project.id == inv.project_id).first()

    log_audit(
        db, inv.project_id, user_id,
        action="member.joined",
        description=f"{current_user_obj.name} joined as {inv.role}.",
        entity_type="member",
        entity_id=user_id,
    )

    if project:
        create_notification(
            db, project.owner_id,
            f"{current_user_obj.name} accepted your invitation to '{project.title}'.",
            type="invitation_accepted", title="Invitation accepted",
            project_id=inv.project_id, reference_id=user_id,
        )

    db.commit()
    return {"message": "Successfully joined the project", "project_id": inv.project_id}


@router.get("/projects/{project_id}/members")
def get_project_members(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """The actual 'project detail page shows all current members and
    their roles' requirement from the spec."""
    user_id = get_user_id(user)
    project = _require_project_access(project_id, user_id, db)

    members = db.query(ProjectMember).filter(ProjectMember.project_id == project_id).all()

    result = []
    if project.owner:
        result.append(
            {"user_id": project.owner.id, "name": project.owner.name, "email": project.owner.email, "role": "Owner"}
        )
    for m in members:
        if m.user:
            result.append({"user_id": m.user.id, "name": m.user.name, "email": m.user.email, "role": m.role})

    return result


# --- Discussion Board & @Mentions ---

@router.get("/projects/{project_id}/posts")
def get_project_posts(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    _require_project_access(project_id, user_id, db)

    posts = (
        db.query(DiscussionPost)
        .filter(DiscussionPost.project_id == project_id, DiscussionPost.parent_id.is_(None))
        .order_by(DiscussionPost.created_at.desc())
        .all()
    )

    def serialize_post(p: DiscussionPost) -> dict:
        return {
            "id": p.id,
            "content": p.content,
            "author": p.user.name if p.user else "Unknown",
            "created_at": p.created_at,
            "replies": [
                {
                    "id": r.id,
                    "content": r.content,
                    "author": r.user.name if r.user else "Unknown",
                    "created_at": r.created_at,
                }
                for r in p.replies
            ],
        }

    return [serialize_post(p) for p in posts]


@router.post("/projects/{project_id}/posts")
def create_project_post(
    project_id: int,
    payload: PostRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    _require_project_access(project_id, user_id, db)

    post = DiscussionPost(
        project_id=project_id,
        user_id=user_id,
        parent_id=payload.parent_id,
        content=payload.content,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    author = db.query(User).filter(User.id == user_id).first()
    log_audit(
        db, project_id, user_id,
        action="discussion.posted" if payload.parent_id is None else "discussion.replied",
        description=f"{author.name if author else 'A member'} posted in the discussion board.",
        entity_type="post",
        entity_id=post.id,
    )

    # Parse @mentions (e.g., @RafiulIslam or @Name)
    for word in payload.content.split():
        if word.startswith("@") and len(word) > 1:
            mentioned_name = word[1:].replace("_", " ")
            mentioned_user = (
                db.query(User)
                .filter(User.name.ilike(f"%{mentioned_name}%"))
                .first()
            )
            if mentioned_user and mentioned_user.id != user_id:
                create_notification(
                    db, mentioned_user.id,
                    "You were mentioned in a project discussion.",
                    type="mention", title="You were mentioned",
                    project_id=project_id, reference_id=post.id,
                )

    db.commit()
    return {"message": "Post created successfully"}


# --- Notifications / Global Notification Center ---

def _notification_link(n: Notification) -> str:
    """Best-effort target URL for clicking a notification."""
    if n.type == "mention" or n.type in ("discussion.posted",):
        return f"/projects/{n.project_id}/workspace" if n.project_id else "/projects"
    if n.type in ("milestone_overdue", "milestone_approved", "milestone_revision"):
        return "/supervision"
    if n.type in ("project_invitation", "invitation_accepted"):
        return f"/projects/{n.project_id}/workspace" if n.project_id else "/projects"
    return "/projects" if n.project_id else "/"


@router.get("/notifications")
def get_notifications(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    ensure_overdue_milestone_notifications(db, user_id)

    notifs = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "message": n.message,
            "is_read": bool(n.is_read),
            "project_id": n.project_id,
            "reference_id": n.reference_id,
            "link": _notification_link(n),
            "created_at": n.created_at,
        }
        for n in notifs
    ]


@router.get("/notifications/unread-count")
def get_unread_notification_count(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    ensure_overdue_milestone_notifications(db, user_id)
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == 0)
        .count()
    )
    return {"unread_count": count}


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if notif:
        notif.is_read = 1
        db.commit()
    return {"message": "Marked as read"}


@router.post("/notifications/mark-all-read")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = get_user_id(user)
    db.query(Notification).filter(
        Notification.user_id == user_id, Notification.is_read == 0
    ).update({"is_read": 1})
    db.commit()
    return {"message": "All notifications marked as read"}
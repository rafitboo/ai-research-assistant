from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.models import Project, ProjectMember, ProjectInvitation, DiscussionPost, Notification, User
from app.auth_utils import get_current_user

router = APIRouter(prefix="/api/collaboration", tags=["Collaboration"])

class InviteRequest(BaseModel):
    email: str
    role: str = "Member"

class PostRequest(BaseModel):
    content: str
    parent_id: Optional[int] = None

def get_user_id(user_dict: dict) -> int:
    return int(user_dict.get("user_id") or user_dict.get("sub") or user_dict.get("id"))

# --- Invitations & Membership ---
@router.post("/projects/{project_id}/invite")
def invite_member(project_id: int, payload: InviteRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == user_id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Only project owners can send invitations.")

    invitation = ProjectInvitation(
        project_id=project_id,
        email=payload.email,
        role=payload.role,
        status="Pending"
    )
    db.add(invitation)
    db.commit()
    return {"message": "Invitation sent successfully"}

@router.get("/projects/{project_id}/invitations")
def get_invitations(project_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    invitations = db.query(ProjectInvitation).filter(ProjectInvitation.project_id == project_id).all()
    
    now = datetime.now(timezone.utc)
    for inv in invitations:
        if inv.status == "Pending":
            # Check if older than 7 days
            created_at_utc = inv.created_at
            if created_at_utc and (now - created_at_utc) > timedelta(days=7):
                inv.status = "Expired"
    db.commit()

    return [{
        "id": i.id,
        "email": i.email,
        "role": i.role,
        "status": i.status,
        "created_at": i.created_at
    } for i in invitations]

@router.post("/invitations/{invitation_id}/resend")
def resend_invitation(invitation_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    inv = db.query(ProjectInvitation).filter(ProjectInvitation.id == invitation_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    inv.status = "Pending"
    inv.created_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Invitation re-sent successfully"}

@router.post("/invitations/{invitation_id}/accept")
def accept_invitation(invitation_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    current_user_obj = db.query(User).filter(User.id == user_id).first()
    
    inv = db.query(ProjectInvitation).filter(ProjectInvitation.id == invitation_id).first()
    if not inv or inv.status != "Pending":
        raise HTTPException(status_code=400, detail="Invalid or expired invitation")
    
    if current_user_obj.email != inv.email:
        raise HTTPException(status_code=403, detail="This invitation was sent to a different email address.")

    inv.status = "Accepted"
    
    # Add to project members if not already added
    existing_member = db.query(ProjectMember).filter(ProjectMember.project_id == inv.project_id, ProjectMember.user_id == user_id).first()
    if not existing_member:
        new_member = ProjectMember(project_id=inv.project_id, user_id=user_id, role=inv.role)
        db.add(new_member)
        
    db.commit()
    return {"message": "Successfully joined the project"}

# --- Discussion Board & @Mentions ---
@router.get("/projects/{project_id}/posts")
def get_project_posts(project_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    posts = db.query(DiscussionPost).filter(DiscussionPost.project_id == project_id, DiscussionPost.parent_id == None).order_by(DiscussionPost.created_at.desc()).all()
    
    def serialize_post(p):
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
                    "created_at": r.created_at
                } for r in p.replies
            ]
        }
    return [serialize_post(p) for p in posts]

@router.post("/projects/{project_id}/posts")
def create_project_post(project_id: int, payload: PostRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    
    post = DiscussionPost(
        project_id=project_id,
        user_id=user_id,
        parent_id=payload.parent_id,
        content=payload.content
    )
    db.add(post)
    db.commit()

    # Parse @mentions (e.g., @RafiulIslam or @Name)
    words = payload.content.split()
    for word in words:
        if word.startswith("@"):
            mentioned_name = word[1:].replace("_", " ")
            mentioned_user = db.query(User).filter(User.name.ilike(f"%{mentioned_name}%")).first()
            if mentioned_user and mentioned_user.id != user_id:
                notif = Notification(
                    user_id=mentioned_user.id,
                    message=f"You were mentioned in a project discussion."
                )
                db.add(notif)
                db.commit()

    return {"message": "Post created successfully"}

# --- Notifications / Dashboard Badge ---
@router.get("/notifications")
def get_notifications(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    user_id = get_user_id(user)
    notifs = db.query(Notification).filter(Notification.user_id == user_id).order_by(Notification.created_at.desc()).all()
    return [{"id": n.id, "message": n.message, "is_read": n.is_read, "created_at": n.created_at} for n in notifs]

@router.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if notif:
        notif.is_read = 1
        db.commit()
    return {"message": "Marked as read"}
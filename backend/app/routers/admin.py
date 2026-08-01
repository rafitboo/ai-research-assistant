from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import User, Paper, Project
from app.auth_utils import get_current_user

# ⚠️ Make sure this variable is named exactly 'router'
router = APIRouter(prefix="/api/admin", tags=["Admin"])

class SubscriptionUpdateSchema(BaseModel):
    subscription_tier: str  # "Free" or "Premium"

@router.get("/stats")
def get_admin_stats(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    total_users = db.query(User).count()
    total_papers = db.query(Paper).count()
    total_projects = db.query(Project).count()
    users = db.query(User).all()
    
    user_list = [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "subscription_tier": u.subscription_tier
        } for u in users
    ]
    
    return {
        "stats": {
            "total_users": total_users,
            "total_papers": total_papers,
            "total_projects": total_projects,
            "ai_request_volume": 128
        },
        "users": user_list
    }

@router.put("/users/{user_id}/subscription")
def update_subscription(user_id: int, data: SubscriptionUpdateSchema, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.subscription_tier = data.subscription_tier
    db.commit()
    return {"message": f"Updated {user.name}'s plan to {user.subscription_tier}"}
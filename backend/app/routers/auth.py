from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models import User
from app.auth_utils import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])

class RegisterSchema(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "Researcher" # Researcher or Team Member

class LoginSchema(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
def register(data: RegisterSchema, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email is already registered")
    
    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
        subscription_tier="Free"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = create_access_token({"user_id": user.id, "email": user.email, "role": user.role, "name": user.name})
    return {"token": token, "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "subscription_tier": user.subscription_tier}}

@router.post("/login")
def login(data: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(user.password_hash, data.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token({"user_id": user.id, "email": user.email, "role": user.role, "name": user.name})
    return {"token": token, "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "subscription_tier": user.subscription_tier}}

@router.get("/me")
def me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "subscription_tier": user.subscription_tier}
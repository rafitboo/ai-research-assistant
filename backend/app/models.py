from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="Researcher")  # Researcher, Team Member, Admin, Supervisor
    subscription_tier = Column(String, default="Free")  # Free, Premium

    papers = relationship("Paper", back_populates="owner")
    owned_projects = relationship("Project", back_populates="owner")
    project_memberships = relationship("ProjectMember", back_populates="user")


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    author = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    topic = Column(String, nullable=True)
    research_area = Column(String, nullable=True)
    tags = Column(String, nullable=True)  # Comma-separated tags
    file_path = Column(String, nullable=True)
    
    # Progress Tracking fields (for Module 1, Feature 3)
    reading_status = Column(String, default="Unread")  # Unread, Reading, Completed
    read_percentage = Column(Integer, default=0)       # 0 - 100
    time_spent_seconds = Column(Integer, default=0)   # Total seconds spent

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="papers")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="owned_projects")
    members = relationship("ProjectMember", back_populates="project")


class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String, default="Member")  # Member, Supervisor

    project = relationship("Project", back_populates="members")
    user = relationship("User", back_populates="project_memberships")
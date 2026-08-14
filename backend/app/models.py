from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from sqlalchemy.sql import func
from app.database import Base
from sqlalchemy.orm import backref

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
    author = Column("authors", String, nullable=True)
    year = Column("publication_year", Integer, nullable=True)
    topic = Column(String, nullable=True)
    research_area = Column(String, nullable=True)
    tags = Column(String, nullable=True)  # Comma-separated tags
    file_path = Column(String, nullable=True)
    
    # Progress Tracking fields (for Module 1, Feature 3)
    reading_status = Column(String, default="Unread")  # Unread, Reading, Completed
    read_percentage = Column(Integer, default=0)       # 0 - 100
    time_spent_seconds = Column(Integer, default=0)   # Total seconds spent

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    user_id = Column("owner_id", Integer, ForeignKey("users.id"))
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
    
    
    
class PaperChunk(Base):
    __tablename__ = "paper_chunks"
    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"))
    page_number = Column(Integer, nullable=False)
    section_title = Column(String(255), nullable=True)
    chunk_text = Column(Text, nullable=False)
    # Note: If pgvector extension is installed in PostgreSQL, 
    # you can define an embedding column here: embedding = Column(Vector(768))

class PageNote(Base):
    __tablename__ = "page_notes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"))
    page_number = Column(Integer, nullable=False)
    note_content = Column(Text, nullable=False)
    
    paper = relationship("Paper", backref="notes")
    
    
    
class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=True)

    title = Column(String, index=True, nullable=True)
    content = Column(Text, nullable=False)
    category = Column(String, default="General")
    tags = Column(String, nullable=True)          # comma-separated, same pattern as Paper.tags
    pinned = Column(Integer, default=0)            # 0/1, avoids Boolean/SQLite quirks
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())



class ProjectInvitation(Base):
    __tablename__ = "project_invitations"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    email = Column(String, nullable=False)
    role = Column(String, default="Member")  # Member, Supervisor
    status = Column(String, default="Pending")  # Pending, Accepted, Expired
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    project = relationship("Project", backref="invitations")

class DiscussionPost(Base):
    __tablename__ = "discussion_posts"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    parent_id = Column(Integer, ForeignKey("discussion_posts.id", ondelete="CASCADE"), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    project = relationship("Project", backref="posts")
    user = relationship("User", backref="posts")
    replies = relationship("DiscussionPost", backref=backref("parent", remote_side=[id]), cascade="all, delete-orphan")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    message = Column(Text, nullable=False)
    is_read = Column(Integer, default=0)  # 0 = unread (triggers badge), 1 = read
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="notifications")


class PaperSummary(Base):
    __tablename__ = "paper_summaries"
    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), unique=True)
    abstract_summary = Column(Text, nullable=False)
    methodology_summary = Column(Text, nullable=False)
    findings_summary = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PaperInsight(Base):
    __tablename__ = "paper_insights"
    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"))
    category = Column(String, nullable=False) # contribution, advantage, limitation, future_work
    content = Column(Text, nullable=False)

class SavedTitle(Base):
    __tablename__ = "saved_titles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    title_text = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())    
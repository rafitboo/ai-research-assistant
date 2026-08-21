from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Text, Float
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
    ai_quota_used = Column(Integer, default=0)

    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Integer, default=0)  
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

    # Added for the Global Notification Center. All nullable so existing
    # Notification(user_id=..., message=...) call sites keep working unchanged.
    type = Column(String, nullable=True)         
    title = Column(String, nullable=True)        
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    reference_id = Column(Integer, nullable=True)  

    user = relationship("User", backref="notifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String, nullable=False)        
    entity_type = Column(String, nullable=True)      
    entity_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", backref="audit_logs")
    user = relationship("User")


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
    category = Column(String, nullable=False) # contribution, advantage, limitation, future_work, hyp_*, gap_*
    content = Column(Text, nullable=False)
    starred = Column(Integer, default=0)  # 0/1, same pattern as JournalEntry.pinned

class SavedTitle(Base):
    __tablename__ = "saved_titles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    title_text = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())    
    


class SmartFolder(Base):
    __tablename__ = "smart_folders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    color = Column(String, default="indigo") # <--- ADD THIS LINE
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner = relationship("User", backref="smart_folders")
    papers = relationship("Paper", secondary="smart_folder_papers", backref="folders")

class SmartFolderPaper(Base):
    __tablename__ = "smart_folder_papers"
    folder_id = Column(Integer, ForeignKey("smart_folders.id", ondelete="CASCADE"), primary_key=True)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True)

class DismissedRecommendation(Base):
    __tablename__ = "dismissed_recommendations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    status = Column(String, default="Pending") # Pending, Completed, Failed
    transaction_ref = Column(String, unique=True, index=True, nullable=False) # Unique simulated payment ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="transactions")

# ============================================================
# Module 4 - Feature 3
# Supervisor Consultation Portal & Review System
# ============================================================

class ConsultationRequest(Base):
    __tablename__ = "consultation_requests"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    requester_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    supervisor_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    start_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    end_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    topic = Column(String(255), nullable=False)
    notes = Column(Text, nullable=True)

    # Pending -> Approved / Declined / Cancelled
    status = Column(
        String(30),
        nullable=False,
        default="Pending",
        index=True
    )

    supervisor_response = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )


class ResearchMilestone(Base):
    __tablename__ = "research_milestones"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)

    # Draft -> Pending Review -> Approved / Revision Requested
    status = Column(
        String(40),
        nullable=False,
        default="Draft",
        index=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    submitted_at = Column(DateTime(timezone=True), nullable=True)

    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    reviewed_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    latest_review_comment = Column(Text, nullable=True)

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # Optional link so a task can automatically populate the milestone timeline.
    milestone_id = Column(Integer, ForeignKey("research_milestones.id", ondelete="SET NULL"), nullable=True, index=True)

    # A task can depend on another task in the same project (nullable = no dependency).
    depends_on_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)

    assignee_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Kanban column: Todo -> In Progress -> Done
    status = Column(String(30), nullable=False, default="Todo", index=True)

    # Server-computed/refreshed flag: true once due_date has passed and status != Done
    is_overdue = Column(Integer, default=0)  # 0/1, same pattern used elsewhere in this codebase

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", backref="tasks")
    milestone = relationship("ResearchMilestone", backref="tasks")
    depends_on = relationship("Task", remote_side=[id], backref="blocking_tasks")

class MilestoneReview(Base):
    __tablename__ = "milestone_reviews"

    id = Column(Integer, primary_key=True, index=True)

    milestone_id = Column(
        Integer,
        ForeignKey(
            "research_milestones.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    supervisor_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    # Approved / Revision Requested
    decision = Column(
        String(40),
        nullable=False
    )

    comments = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

class LiteratureMatrix(Base):
    __tablename__ = "literature_matrices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True
    )

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    user = relationship("User", backref="literature_matrices")
    project = relationship("Project", backref="literature_matrices")

    papers = relationship(
        "LiteratureMatrixPaper",
        back_populates="matrix",
        cascade="all, delete-orphan"
    )

    columns = relationship(
        "LiteratureMatrixColumn",
        back_populates="matrix",
        cascade="all, delete-orphan",
        order_by="LiteratureMatrixColumn.position"
    )


class LiteratureMatrixPaper(Base):
    __tablename__ = "literature_matrix_papers"

    id = Column(Integer, primary_key=True, index=True)

    matrix_id = Column(
        Integer,
        ForeignKey("literature_matrices.id", ondelete="CASCADE"),
        nullable=False
    )

    paper_id = Column(
        Integer,
        ForeignKey("papers.id", ondelete="CASCADE"),
        nullable=False
    )

    position = Column(
        Integer,
        nullable=False,
        default=0
    )

    matrix = relationship(
        "LiteratureMatrix",
        back_populates="papers"
    )

    paper = relationship("Paper")


class LiteratureMatrixColumn(Base):
    __tablename__ = "literature_matrix_columns"

    id = Column(Integer, primary_key=True, index=True)

    matrix_id = Column(
        Integer,
        ForeignKey("literature_matrices.id", ondelete="CASCADE"),
        nullable=False
    )

    name = Column(
        String(255),
        nullable=False
    )

    key = Column(
        String(100),
        nullable=False
    )

    is_custom = Column(
        Integer,
        nullable=False,
        default=0
    )

    position = Column(
        Integer,
        nullable=False,
        default=0
    )

    matrix = relationship(
        "LiteratureMatrix",
        back_populates="columns"
    )

    cells = relationship(
        "LiteratureMatrixCell",
        back_populates="column",
        cascade="all, delete-orphan"
    )


class LiteratureMatrixCell(Base):
    __tablename__ = "literature_matrix_cells"

    id = Column(Integer, primary_key=True, index=True)

    matrix_id = Column(
        Integer,
        ForeignKey("literature_matrices.id", ondelete="CASCADE"),
        nullable=False
    )

    paper_id = Column(
        Integer,
        ForeignKey("papers.id", ondelete="CASCADE"),
        nullable=False
    )

    column_id = Column(
        Integer,
        ForeignKey(
            "literature_matrix_columns.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    value = Column(
        Text,
        nullable=True
    )

    source = Column(
        String(30),
        nullable=False,
        default="AI"
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    column = relationship(
        "LiteratureMatrixColumn",
        back_populates="cells"
    )

    paper = relationship("Paper")
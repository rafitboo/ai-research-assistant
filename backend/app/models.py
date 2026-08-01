from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float, DateTime
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="Researcher")
    subscription_tier = Column(String, default="Free") # Free or Premium

class Paper(Base):
    __tablename__ = "papers"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String, index=True)
    authors = Column(String)
    publication_year = Column(Integer)
    abstract = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    reading_status = Column(String, default="Unread") # Unread, Reading, Completed
    read_percentage = Column(Float, default=0.0)
    time_spent_seconds = Column(Integer, default=0)

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
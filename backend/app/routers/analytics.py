from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime, timedelta, timezone, date
from collections import Counter

from app.database import get_db
from app.models import Paper, User, JournalEntry, Project, ProjectMember
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["Library Analytics"])

def get_valid_user_id(current_user, db: Session) -> int:
    if hasattr(current_user, 'id') and current_user.id is not None:
        return current_user.id
    if isinstance(current_user, dict) and current_user.get("id") is not None:
        return current_user.get("id")
    email = getattr(current_user, 'email', None) or (isinstance(current_user, dict) and current_user.get("email"))
    if email:
        db_user = db.query(User).filter(User.email == email).first()
        if db_user:
            return db_user.id
    raise HTTPException(status_code=401, detail="Could not resolve valid user ID.")


def calculate_current_streak(active_dates: list) -> int:
    """
    Calculates the current CONSECUTIVE-day streak ending today (or yesterday,
    so a user isn't penalized for not having logged anything yet today).
    active_dates: list of date objects (distinct days with a journal entry).
    """
    if not active_dates:
        return 0

    date_set = set(active_dates)
    today = datetime.now(timezone.utc).date()

    # Anchor the streak at today if active today, otherwise at yesterday.
    if today in date_set:
        cursor = today
    elif (today - timedelta(days=1)) in date_set:
        cursor = today - timedelta(days=1)
    else:
        return 0

    streak = 0
    while cursor in date_set:
        streak += 1
        cursor -= timedelta(days=1)

    return streak


@router.get("/dashboard")
def get_library_analytics(
    days: Optional[int] = Query(None, description="Filter window in days (7, 30, or None for all time)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_id = get_valid_user_id(current_user, db)

    # Base query for user papers
    paper_query = db.query(Paper).filter(Paper.user_id == user_id)

    cutoff_date = None
    if days:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        paper_query = paper_query.filter(Paper.created_at >= cutoff_date)

    papers = paper_query.all()
    total_papers = len(papers)

    if total_papers == 0:
        return {
            "total": 0,
            "avg_completion": 0,
            "status_breakdown": {},
            "top_areas": [],
            "streak": 0,
            "activity_timeline": [],
            "project_snapshots": []
        }

    # 1. Average Completion Percentage
    avg_completion = sum((p.read_percentage or 0) for p in papers) / total_papers

    # 2. Status Breakdown
    statuses = [p.reading_status for p in papers if p.reading_status]
    status_breakdown = dict(Counter(statuses))

    # 3. Top Research Areas
    areas = [p.research_area for p in papers if p.research_area]
    top_areas = [{"area": area, "count": count} for area, count in Counter(areas).most_common(5)]

    # 4. Reading Activity Timeline (grouped by date)
    activity_map = Counter()
    for p in papers:
        if p.created_at:
            date_str = p.created_at.strftime("%Y-%m-%d")
            activity_map[date_str] += 1

    sorted_dates = sorted(activity_map.keys())
    activity_timeline = [{"date": d, "count": activity_map[d]} for d in sorted_dates]

    # 5. Reading Streak — real consecutive-day streak based on journal activity
    journal_query = db.query(func.date(JournalEntry.created_at)).filter(JournalEntry.user_id == user_id)
    if cutoff_date:
        journal_query = journal_query.filter(JournalEntry.created_at >= cutoff_date)
    raw_dates = journal_query.distinct().all()

    active_dates = []
    for (d,) in raw_dates:
        if d is None:
            continue
        # func.date() can return a date, datetime, or string depending on DB driver
        if isinstance(d, datetime):
            active_dates.append(d.date())
        elif isinstance(d, date):
            active_dates.append(d)
        else:
            active_dates.append(datetime.strptime(str(d), "%Y-%m-%d").date())

    streak = calculate_current_streak(active_dates)

    # 6. Project Contribution Snapshot
    # NOTE: Paper and JournalEntry are not currently linked to a specific Project
    # in the schema (no project_id FK on either model), so per-project paper/journal
    # counts can't be computed accurately yet. Rather than show duplicated/fake
    # numbers for every project, we surface real, currently-available project data.
    # TODO: once Paper/JournalEntry gain a project_id FK, swap member_count-only
    # snapshot below for real per-project papers_contributed / journals_logged counts.
    owned_projects = db.query(Project).filter(Project.owner_id == user_id).all()
    member_projects = db.query(Project).join(ProjectMember).filter(ProjectMember.user_id == user_id).all()
    all_user_projects = {p.id: p for p in (owned_projects + member_projects)}.values()

    project_snapshots = []
    for proj in all_user_projects:
        member_count = db.query(ProjectMember).filter(ProjectMember.project_id == proj.id).count()
        project_snapshots.append({
            "title": proj.title,
            "role": "Owner" if proj.owner_id == user_id else "Member",
            "member_count": member_count,
            "created_at": proj.created_at.strftime("%Y-%m-%d") if proj.created_at else None
        })

    return {
        "total": total_papers,
        "avg_completion": round(avg_completion, 1),
        "status_breakdown": status_breakdown,
        "top_areas": top_areas,
        "streak": streak,
        "activity_timeline": activity_timeline,
        "project_snapshots": project_snapshots
    }
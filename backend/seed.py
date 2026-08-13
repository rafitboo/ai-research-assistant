from app.database import SessionLocal, engine, Base
from app.models import User, Paper, Project, ProjectMember
from app.auth_utils import hash_password
from sqlalchemy import text

# Ensure all tables exist in the local database
Base.metadata.create_all(bind=engine)


def ensure_papers_schema():
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE papers ADD COLUMN IF NOT EXISTS topic VARCHAR"))
        conn.execute(text("ALTER TABLE papers ADD COLUMN IF NOT EXISTS research_area VARCHAR"))
        conn.execute(text("ALTER TABLE papers ADD COLUMN IF NOT EXISTS tags VARCHAR"))
        conn.execute(text("ALTER TABLE papers ADD COLUMN IF NOT EXISTS file_path VARCHAR"))
        conn.execute(text("ALTER TABLE papers ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"))

db = SessionLocal()

def seed_database():
    print("🌱 Starting database seed...")
    ensure_papers_schema()

    # 1. Create Default Admin & Sample Researchers
    admin = db.query(User).filter(User.email == "admin@platform.com").first()
    if not admin:
        admin = User(
            name="Md. Rafiul Islam",
            email="admin@platform.com",
            password_hash=hash_password("admin123"),
            role="Admin",
            subscription_tier="Premium"
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print("  ✅ Admin user created (admin@platform.com / admin123)")

    # 2. Add Sample Research Papers
    sample_papers = [
        {
            "title": "A heterogeneous Federated Learning Approach for Decentralized Pest Detection under Non-IID Distributions",
            "author": "Md. Rafiul Islam",
            "year": 2025,
            "topic": "FL",
            "tags": "Federated Learning, Agriculture",
            "reading_status": "Unread",
            "read_percentage": 0,
            "time_spent_seconds": 0
        },
        {
            "title": "Attention Is All You Need",
            "author": "Vaswani et al.",
            "year": 2017,
            "topic": "Transformer",
            "tags": "Deep Learning, NLP",
            "reading_status": "Completed",
            "read_percentage": 100,
            "time_spent_seconds": 3600
        },
        {
            "title": "ImageNet Classification with Deep Convolutional Neural Networks",
            "author": "Krizhevsky et al.",
            "year": 2012,
            "topic": "Vision",
            "tags": "CNN, Computer Vision",
            "reading_status": "Completed",
            "read_percentage": 100,
            "time_spent_seconds": 2400
        }
    ]

    for p in sample_papers:
        existing = db.query(Paper).filter(Paper.title == p["title"], Paper.user_id == admin.id).first()
        if not existing:
            paper = Paper(**p, user_id=admin.id)
            db.add(paper)
    
    db.commit()
    print("  ✅ Sample papers created")

    # 3. Add Sample Research Projects
    sample_projects = [
        {"title": "Heterogeneous Federated Learning", "description": "Research project on non-IID partitioning and model aggregation."},
        {"title": "Sentiment Analysis", "description": "NLP model development for text classification."},
        {"title": "Traffic Congestion Management using Deep Learning", "description": "Real-time object detection for urban traffic flow."}
    ]

    for proj_data in sample_projects:
        existing_proj = db.query(Project).filter(Project.title == proj_data["title"], Project.owner_id == admin.id).first()
        if not existing_proj:
            project = Project(**proj_data, owner_id=admin.id)
            db.add(project)
    
    db.commit()
    print("  ✅ Sample projects created")
    
    print("\n🎉 Seeding complete! Database is populated and ready.")
    db.close()

if __name__ == "__main__":
    seed_database()
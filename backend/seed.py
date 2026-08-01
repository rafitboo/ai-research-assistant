from app.database import SessionLocal, engine, Base
from app.models import User
from app.auth_utils import hash_password

# Ensure tables exist
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Check if sample admin exists
admin = db.query(User).filter(User.email == "admin@platform.com").first()
if not admin:
    admin_user = User(
        name="System Admin",
        email="admin@platform.com",
        password_hash=hash_password("admin123"),
        role="Admin",
        subscription_tier="Premium"
    )
    db.add(admin_user)
    db.commit()
    print("✅ Seed successful: Default Admin account created (admin@platform.com / admin123)")
else:
    print("ℹ️ Database already seeded.")

db.close()
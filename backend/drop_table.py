from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("DROP TABLE papers"))
    conn.commit()

print("Table dropped successfully.")
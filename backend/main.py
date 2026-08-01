from fastapi import FastAPI
from app.database import engine, Base

# Create tables (In production, use Alembic, but for this course project this is fine)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Research Assistant API")

@app.get("/")
def read_root():
    return {"status": "FastAPI Backend is running"}
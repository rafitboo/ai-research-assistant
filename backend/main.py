from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import auth, admin, dashboard , papers, projects, paper_workspace, reading_progress, journal, collaboration, ai_features, research_gaps

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Research Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(dashboard.router)
app.include_router(papers.router)
app.include_router(projects.router)
app.include_router(reading_progress.router) 
app.include_router(paper_workspace.router)
app.include_router(journal.router)
app.include_router(collaboration.router)
app.include_router(ai_features.router)
app.include_router(research_gaps.router)

@app.get("/")
def read_root():
    return {"status": "FastAPI Backend is running"}

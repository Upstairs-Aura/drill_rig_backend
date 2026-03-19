from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from app.database import engine, Base
from app.routes import dashboard, ingest

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Drill Rig Predictive Maintenance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", os.getenv("FRONTEND_URL", "")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(ingest.router)

@app.get("/")
def root():
    return {"status": "ok", "message": "Drill Rig API is running"}
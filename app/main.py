from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from app.database import engine, Base
from app.routes import dashboard, ingest, config, label

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Drill Rig Predictive Maintenance API")

# Middleware for cors (connections)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)
app.include_router(dashboard.router)
app.include_router(ingest.router)
app.include_router(label.router)

@app.get("/")
def root():
    return {"status": "ok", "message": "Drill Rig API is running"}
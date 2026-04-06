from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from app.database import get_db
from app.models import FeatureRecord, MaintenanceEvent
from fastapi import APIRouter, Depends, BackgroundTasks

router = APIRouter(prefix="/api/v1/label", tags=["Labelling"])

class FailureConfirmRequest(BaseModel):
    asset_id:     str
    failure_time: datetime
    window_hours: int = 72
    event_type:   str = "confirmed_failure"
    notes:        str = ""

def retrain_models():
    from app.ml.train_forest import train as train_rf
    from app.ml.train_lstm import train as train_lstm
    from app.ml.predict import _load
    print("Retraining triggered by failure event...")
    train_rf()
    train_lstm()
    _load()
    print("Retraining complete. Models reloaded.")

@router.post("/confirm-failure")
def confirm_failure(req: FailureConfirmRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    cutoff = req.failure_time - timedelta(hours=req.window_hours)

    pre_failure_count = db.query(FeatureRecord).filter(
        FeatureRecord.asset_id  == req.asset_id,
        FeatureRecord.source    == "live",
        FeatureRecord.timestamp >= cutoff,
        FeatureRecord.timestamp <= req.failure_time,
        ).update({"label": 1})

    normal_count = db.query(FeatureRecord).filter(
        FeatureRecord.asset_id  == req.asset_id,
        FeatureRecord.source    == "live",
        FeatureRecord.label     == None,
        FeatureRecord.timestamp <  cutoff,
        ).update({"label": 0})

    db.add(MaintenanceEvent(
        asset_id=req.asset_id, timestamp=req.failure_time,
        event_type=req.event_type, notes=req.notes,
    ))
    db.commit()
    background_tasks.add_task(retrain_models)
    return {"pre_failure_labelled": pre_failure_count, "normal_labelled": normal_count}

@router.get("/summary/{asset_id}")
def label_summary(asset_id: str, db: Session = Depends(get_db)):
    total    = db.query(FeatureRecord).filter(FeatureRecord.asset_id == asset_id, FeatureRecord.source == "live").count()
    labelled = db.query(FeatureRecord).filter(FeatureRecord.asset_id == asset_id, FeatureRecord.source == "live", FeatureRecord.label != None).count()
    pre_fail = db.query(FeatureRecord).filter(FeatureRecord.asset_id == asset_id, FeatureRecord.source == "live", FeatureRecord.label == 1).count()
    return {"total_live": total, "labelled": labelled, "unlabelled": total - labelled, "pre_failure": pre_fail}
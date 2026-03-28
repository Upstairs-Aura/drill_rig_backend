from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import FeatureRecord, Asset, PredictionRecord
from datetime import datetime
from app.ml.predict import predict as run_predict


router = APIRouter(prefix="/api/v1/assets", tags=["Dashboard"])

@router.get("/")
def get_all_assets(db: Session = Depends(get_db)):
    return db.query(Asset).all()

@router.get("/{asset_id}/metrics/latest")
def get_latest_metrics(asset_id: str, db: Session = Depends(get_db)):
    record = db.query(FeatureRecord).filter(
        FeatureRecord.asset_id == asset_id
    ).order_by(FeatureRecord.timestamp.desc()).first()
    if not record:
        return {"temperature": "--", "vibration": "--", "current": "--"}
    return {
        "temperature": f"{record.temperature}°C",
        "vibration": f"{record.rms}mm/s",
        "current": f"{record.current}A"
    }

@router.get("/{asset_id}/alerts")
def get_alerts(asset_id: str, db: Session = Depends(get_db)):
    record = db.query(FeatureRecord).filter(
        FeatureRecord.asset_id == asset_id
    ).order_by(FeatureRecord.timestamp.desc()).first()
    if not record:
        return [
            {"text": "Vibration", "severity": "normal"},
            {"text": "Temperature", "severity": "normal"},
            {"text": "Current", "severity": "normal"},
        ]
    def severity(value, warn, critical):
        if value >= critical: return "critical"
        if value >= warn: return "warning"
        return "normal"
    return [
        {"text": "Vibration", "severity": severity(record.rms, 6.0, 9.0)},
        {"text": "Temperature", "severity": severity(record.temperature, 70.0, 78.0)},
        {"text": "Current", "severity": severity(record.current, 400.0, 500.0)},
    ]

@router.get("/{asset_id}/health-history")
def get_health_history(asset_id: str, days: int = 30, db: Session = Depends(get_db)):
    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(days=days)
    records = db.query(FeatureRecord).filter(
        FeatureRecord.asset_id == asset_id,
        FeatureRecord.timestamp >= since
    ).order_by(FeatureRecord.timestamp).all()
    return [{"day": r.timestamp.strftime("%b %d"), "health": round((1 - min(r.rms / 15.0, 1)) * 100, 1)} for r in records]

@router.get("/{asset_id}/system-status")
def get_system_status(asset_id: str, db: Session = Depends(get_db)):
    record = db.query(FeatureRecord).filter(
        FeatureRecord.asset_id == asset_id
    ).order_by(FeatureRecord.timestamp.desc()).first()
    if not record:
        return {"lastReading": "No data", "lastTransmission": "No data"}
    return {
        "lastReading": record.timestamp.strftime("%H:%M"),
        "lastTransmission": record.timestamp.strftime("%H:%M")
    }

@router.get("/{asset_id}/predict")
def get_prediction(asset_id: str, db: Session = Depends(get_db)):
    recent = db.query(FeatureRecord).filter(
        FeatureRecord.asset_id == asset_id
    ).order_by(FeatureRecord.timestamp.desc()).limit(7).all()
    recent = list(reversed(recent))  # oldest first

    if not recent:
        return {"anomaly": False, "risk_score": 0.0, "source": "no_data"}

    latest = recent[-1]
    result = run_predict(latest, recent_records=recent)

    if result is None:
        return {"anomaly": False, "risk_score": 0.0, "source": "no_model"}

    db.add(PredictionRecord(
        asset_id     = asset_id,
        timestamp    = datetime.utcnow(),
        model_source = result["source"],
        anomaly      = int(result["anomaly"]),
        risk_score   = result["risk_score"],
    ))
    db.commit()
    return result

@router.get("/{asset_id}/prediction-history")
def get_prediction_history(asset_id: str, db: Session = Depends(get_db)):
    records = (
        db.query(PredictionRecord)
        .filter(PredictionRecord.asset_id == asset_id)
        .order_by(PredictionRecord.timestamp.desc())
        .limit(30)
        .all()
    )
    return [
        {"timestamp": r.timestamp.strftime("%b %d %H:%M"), "risk_score": round(r.risk_score * 100, 1)}
        for r in reversed(records)
    ]
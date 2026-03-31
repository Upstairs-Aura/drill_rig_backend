from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import FeatureRecord, AssetConfig
from app.schemas import IngestRequest

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingest"])

@router.post("/")
def ingest_records(payload: IngestRequest, db: Session = Depends(get_db)):
    #fecth and check sensore id's and types match.
    for record in payload.records:
        cfg_row = db.query(AssetConfig).filter(
            AssetConfig.asset_id == record.asset_id,
            AssetConfig.is_active == True
        ).first()

        if cfg_row:
            allowed_ids = {s["sensor_id"] for s in cfg_row.config["sensors"]}
            if record.sensor_id not in allowed_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"sensor_id '{record.sensor_id}' not in active config for {record.asset_id}"
                )

    for record in payload.records:
        db_record = FeatureRecord(
            asset_id=record.asset_id,
            sensor_id=record.sensor_id,
            timestamp=record.timestamp,
            rms=record.rms,
            peak=record.peak,
            crest_factor=record.crest_factor,
            kurtosis=record.kurtosis,
            skewness=record.skewness,
            dominant_frequency=record.dominant_frequency,
            temperature=record.temperature,
            current=record.current,
        )
        db.add(db_record)
    db.commit()
    return {"inserted": len(payload.records)}
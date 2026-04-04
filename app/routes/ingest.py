from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import FeatureRecord, AssetConfig
from app.schemas import IngestRequest

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingest"])

@router.post("/")
def ingest_records(payload: IngestRequest, db: Session = Depends(get_db)):
    errors = []
    for i, record in enumerate(payload.records):
        cfg_row = db.query(AssetConfig).filter(
            AssetConfig.asset_id == record.asset_id,
            AssetConfig.is_active == True
        ).first()

        if cfg_row:
            cfg = cfg_row.config
            allowed_ids = {s["sensor_id"] for s in cfg["sensors"]}
            if record.sensor_id not in allowed_ids:
                errors.append({"index": i, "asset_id": record.asset_id,
                               "error": f"sensor_id '{record.sensor_id}' not in active config"})

            if record.config_version > 0 and record.config_version != cfg_row.version:
                errors.append({"index": i, "asset_id": record.asset_id,
                               "error": f"Config version mismatch: payload v{record.config_version}, active v{cfg_row.version}"})

            configured_rate = cfg["sampling"]["sampling_rate_hz"]
            if record.sampling_rate_hz > 0 and abs(record.sampling_rate_hz - configured_rate) > 1.0:
                errors.append({"index": i, "asset_id": record.asset_id,
                               "error": f"Sampling rate mismatch: {record.sampling_rate_hz}Hz vs configured {configured_rate}Hz"})

            configured_window = cfg["filter"]["window_length"]
            if record.window_length > 0 and record.window_length != configured_window:
                errors.append({"index": i, "asset_id": record.asset_id,
                               "error": f"Window length mismatch: {record.window_length} vs configured {configured_window}"})

    if errors:
        raise HTTPException(status_code=422, detail=errors)

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
            bpfo_ratio=record.bpfo_ratio,
            bpfi_ratio=record.bpfi_ratio,
            temperature=record.temperature,
            current=record.current,
            source="live",   # <-- add this line
            label=None,      # <-- add this line
        )
        db.add(db_record)
    db.commit()
    return {"inserted": len(payload.records)}
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import FeatureRecord, AssetConfig
from app.schemas import IngestRequest

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingest"])

@router.post("/")
def ingest_records(payload: IngestRequest, db: Session = Depends(get_db)):
    for record in payload.records:
        cfg_row = db.query(AssetConfig).filter(
            AssetConfig.asset_id == record.asset_id,
            AssetConfig.is_active == True
        ).first()

        if cfg_row:
            cfg = cfg_row.config

            # 1. Sensor ID must be in active config
            allowed_ids = {s["sensor_id"] for s in cfg["sensors"]}
            if record.sensor_id not in allowed_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"sensor_id '{record.sensor_id}' not in active config for {record.asset_id}"
                )

            # 2. Config version must match (if provided by edge device)
            if record.config_version > 0 and record.config_version != cfg_row.version:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Config version mismatch for {record.asset_id}: "
                        f"payload used v{record.config_version}, "
                        f"active config is v{cfg_row.version}. "
                        f"Re-fetch config before sending data."
                    )
                )

            # 3. Sampling rate must match config (if provided)
            configured_rate = cfg["sampling"]["sampling_rate_hz"]
            if record.sampling_rate_hz > 0:
                if abs(record.sampling_rate_hz - configured_rate) > 1.0:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Sampling rate mismatch for {record.asset_id}: "
                            f"payload used {record.sampling_rate_hz}Hz, "
                            f"config requires {configured_rate}Hz."
                        )
                    )

            # 4. Window length must match config (if provided)
            configured_window = cfg["filter"]["window_length"]
            if record.window_length > 0:
                if record.window_length != configured_window:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Window length mismatch for {record.asset_id}: "
                            f"payload used {record.window_length} samples, "
                            f"config requires {configured_window} samples."
                        )
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
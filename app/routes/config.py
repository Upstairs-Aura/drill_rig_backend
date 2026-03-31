from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AssetConfig
from app.schemas import ConfigSubmitRequest
from app.config.validator import validate_config

router = APIRouter(prefix="/api/v1/config", tags=["Config"])

@router.post("/{asset_id}")
def submit_config(asset_id: str, body: ConfigSubmitRequest, db: Session = Depends(get_db)):
    errors = validate_config(body.config)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    # Deactivate current active config
    db.query(AssetConfig).filter(
        AssetConfig.asset_id == asset_id,
        AssetConfig.is_active == True
    ).update({"is_active": False})

    # Get next version number
    latest = db.query(AssetConfig).filter(
        AssetConfig.asset_id == asset_id
    ).order_by(AssetConfig.version.desc()).first()
    next_version = (latest.version + 1) if latest else 1

    new_config = AssetConfig(
        asset_id  = asset_id,
        version   = next_version,
        is_active = True,
        config    = body.config.model_dump(),
    )
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    return {"version": new_config.version, "message": "Config saved and activated"}

@router.get("/{asset_id}/active")
def get_active_config(asset_id: str, db: Session = Depends(get_db)):
    cfg = db.query(AssetConfig).filter(
        AssetConfig.asset_id == asset_id,
        AssetConfig.is_active == True
    ).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="No active config for this asset")
    return {"version": cfg.version, "created_at": cfg.created_at, "config": cfg.config}

@router.get("/{asset_id}/history")
def get_config_history(asset_id: str, db: Session = Depends(get_db)):
    rows = db.query(AssetConfig).filter(
        AssetConfig.asset_id == asset_id
    ).order_by(AssetConfig.version.desc()).all()
    return [
        {"version": r.version, "is_active": r.is_active, "created_at": r.created_at}
        for r in rows
    ]
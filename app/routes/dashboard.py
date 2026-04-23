from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import FeatureRecord, Asset, PredictionRecord, AssetConfig
from datetime import datetime
from app.ml.predict import predict as run_predict, LSTM_SEQ_LEN

router = APIRouter(prefix="/api/v1/assets", tags=["Dashboard"])


# ── Threshold helper ──────────────────────────────────────────────────────────
def get_thresholds(asset_id: str, db: Session) -> dict:
    cfg = db.query(AssetConfig).filter(
        AssetConfig.asset_id == asset_id,
        AssetConfig.is_active == True
    ).first()
    if cfg:
        return cfg.config["thresholds"]
    return {
        "vibration_warn_mms":    6.0,  "vibration_critical_mms": 9.0,
        "temperature_warn_c":   70.0,  "temperature_critical_c": 78.0,
        "current_warn_a":      400.0,  "current_critical_a":    500.0,
    }


# ── Helper: RMS-based health score (fallback when no ML prediction exists) ───
def _rms_health(rms: float, critical_rms: float) -> float:
    """Linear approximation used only when no ML prediction is available."""
    return round((1 - min(rms / critical_rms, 1.0)) * 100, 1)


# ── Helper: ML-based health score ────────────────────────────────────────────
def _ml_health(risk_score: float) -> float:
    """
    Converts the ML model's pre-failure risk score (0–1) to a health
    percentage (0–100).  A risk of 0.0 → 100% healthy; 1.0 → 0% healthy.
    """
    return round((1.0 - risk_score) * 100, 1)


# ─────────────────────────────────────────────────────────────────────────────

@router.get("/")
def get_all_assets(db: Session = Depends(get_db)):
    return db.query(Asset).all()


@router.get("/{asset_id}/metrics/latest")
def get_latest_metrics(asset_id: str, db: Session = Depends(get_db)):
    record = db.query(FeatureRecord).filter(
        FeatureRecord.asset_id == asset_id
    ).order_by(FeatureRecord.timestamp.desc()).first()

    cfg = db.query(AssetConfig).filter(
        AssetConfig.asset_id == asset_id,
        AssetConfig.is_active == True
    ).first()
    sensor_types = (
        [s["sensor_type"] for s in cfg.config["sensors"]]
        if cfg else ["vibration"]
    )

    if not record:
        return {
            "sensor_types": sensor_types,
            "vibration": None, "temperature": None, "current": None,
            "dominant_frequency": None, "bpfo_ratio": None, "bpfi_ratio": None,
            "rms": None, "peak": None, "crest_factor": None,
            "kurtosis": None, "skewness": None,
            "timestamp": None,
        }

    return {
        "sensor_types":       sensor_types,
        "vibration":          round(record.rms, 3),
        "temperature":        round(record.temperature, 1),
        "current":            round(record.current, 1),
        "dominant_frequency": round(record.dominant_frequency, 1),
        "bpfo_ratio":         round(getattr(record, "bpfo_ratio", 0.0) or 0.0, 4),
        "bpfi_ratio":         round(getattr(record, "bpfi_ratio", 0.0) or 0.0, 4),
        "rms":                round(record.rms, 3),
        "peak":               round(record.peak, 3),
        "crest_factor":       round(record.crest_factor, 3),
        "kurtosis":           round(record.kurtosis, 3),
        "skewness":           round(record.skewness, 3),
        "timestamp":          record.timestamp.isoformat(),
    }


@router.get("/{asset_id}/alerts")
def get_alerts(asset_id: str, db: Session = Depends(get_db)):
    record = db.query(FeatureRecord).filter(
        FeatureRecord.asset_id == asset_id
    ).order_by(FeatureRecord.timestamp.desc()).first()
    if not record:
        return [
            {"text": "Vibration",   "severity": "normal"},
            {"text": "Temperature", "severity": "normal"},
            {"text": "Current",     "severity": "normal"},
        ]
    t_hold = get_thresholds(asset_id, db)

    def classify(value, warn, critical):
        if value >= critical:
            return "critical"
        if value >= warn:
            return "warning"
        return "normal"

    return [
        {
            "text": "Vibration",
            "severity": classify(record.rms,
                                 t_hold["vibration_warn_mms"],
                                 t_hold["vibration_critical_mms"])
        },
        {
            "text": "Temperature",
            "severity": classify(record.temperature,
                                 t_hold["temperature_warn_c"],
                                 t_hold["temperature_critical_c"])
        },
        {
            "text": "Current",
            "severity": classify(record.current,
                                 t_hold["current_warn_a"],
                                 t_hold["current_critical_a"])
        },
    ]


@router.get("/{asset_id}/health-history")
def get_health_history(asset_id: str, days: int = 30, db: Session = Depends(get_db)):
    """
    Returns a time-series of health scores for the chart.

    Strategy (per time point):
      1. If a PredictionRecord exists within ±5 minutes of a FeatureRecord,
         use ML-derived health: (1 - risk_score) * 100.
         This reflects all 10 features the model was trained on.
      2. Otherwise fall back to RMS-based health so the chart is never empty
         for historical IMS data that was seeded before predictions were run.

    The 'source' field in each point tells the frontend which method was used,
    allowing it to render a legend or tooltip if desired.
    """
    feature_records = (
        db.query(FeatureRecord)
        .filter(FeatureRecord.asset_id == asset_id)
        .order_by(FeatureRecord.timestamp.desc())
        .limit(days * 144)          # 144 bursts/day at 10-min intervals
        .all()
    )
    feature_records = list(reversed(feature_records))   # oldest → newest

    if not feature_records:
        return []

    # Load all PredictionRecords for this asset in one query and index by
    # timestamp so we can do O(1) lookups instead of N queries.
    prediction_records = (
        db.query(PredictionRecord)
        .filter(PredictionRecord.asset_id == asset_id)
        .order_by(PredictionRecord.timestamp)
        .all()
    )
    # Build a sorted list of (timestamp, risk_score) for bisect lookups
    pred_times      = [p.timestamp for p in prediction_records]
    pred_scores     = {p.timestamp: p.risk_score for p in prediction_records}

    t_hold       = get_thresholds(asset_id, db)
    critical_rms = t_hold["vibration_critical_mms"]

    import bisect
    from datetime import timedelta
    MATCH_WINDOW = timedelta(minutes=5)

    result = []
    for fr in feature_records:
        # Find the nearest PredictionRecord within ±5 minutes
        matched_risk = None
        if pred_times:
            idx = bisect.bisect_left(pred_times, fr.timestamp)
            # Check the neighbours on both sides of the insertion point
            for candidate_idx in [idx - 1, idx]:
                if 0 <= candidate_idx < len(pred_times):
                    pt = pred_times[candidate_idx]
                    if abs(pt - fr.timestamp) <= MATCH_WINDOW:
                        matched_risk = pred_scores[pt]
                        break

        if matched_risk is not None:
            result.append({
                "ts":     fr.timestamp.isoformat(),
                "health": _ml_health(matched_risk),
                "source": "ml",
            })
        else:
            result.append({
                "ts":     fr.timestamp.isoformat(),
                "health": _rms_health(fr.rms, critical_rms),
                "source": "rms_fallback",
            })

    return result


@router.get("/{asset_id}/system-status")
def get_system_status(asset_id: str, db: Session = Depends(get_db)):
    record = db.query(FeatureRecord).filter(
        FeatureRecord.asset_id == asset_id
    ).order_by(FeatureRecord.timestamp.desc()).first()
    if not record:
        return {"lastReading": "No data", "lastTransmission": "No data"}
    return {
        "lastReading":     record.timestamp.strftime("%H:%M"),
        "lastTransmission": record.timestamp.strftime("%H:%M"),
    }


@router.get("/{asset_id}/predict")
def get_prediction(asset_id: str, db: Session = Depends(get_db)):
    recent = db.query(FeatureRecord).filter(
        FeatureRecord.asset_id == asset_id,
        ).order_by(FeatureRecord.timestamp.desc()).limit(LSTM_SEQ_LEN).all()
    recent = list(reversed(recent))     # oldest first

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


@router.get("/{asset_id}/recommendations")
def get_recommendations(asset_id: str, db: Session = Depends(get_db)):
    record = db.query(FeatureRecord).filter(
        FeatureRecord.asset_id == asset_id
    ).order_by(FeatureRecord.timestamp.desc()).first()

    if not record:
        return {"nextMaintenance": "--", "issues": [], "systemHealth": None}

    t_hold = get_thresholds(asset_id, db)
    issues = []

    # Vibration checks
    if record.rms >= t_hold["vibration_critical_mms"]:
        issues.append({
            "title": "Critical: Schedule immediate inspection",
            "description": f"Vibration at {round(record.rms, 1)} mm/s exceeds critical limit of {t_hold['vibration_critical_mms']} mm/s.",
            "buttonText": "Alert", "buttonClass": "alert"
        })
    elif record.rms >= t_hold["vibration_warn_mms"]:
        issues.append({
            "title": "Warning: Vibration elevated",
            "description": f"Vibration at {round(record.rms, 1)} mm/s exceeds warning limit of {t_hold['vibration_warn_mms']} mm/s.",
            "buttonText": "Monitor", "buttonClass": "alert"
        })

    # Temperature checks
    if record.temperature >= t_hold["temperature_critical_c"]:
        issues.append({
            "title": "Critical: Overheating detected",
            "description": f"Temperature at {round(record.temperature, 1)}°C exceeds critical limit of {t_hold['temperature_critical_c']}°C.",
            "buttonText": "Alert", "buttonClass": "alert"
        })
    elif record.temperature >= t_hold["temperature_warn_c"]:
        issues.append({
            "title": "Warning: Temperature elevated",
            "description": f"Temperature at {round(record.temperature, 1)}°C exceeds warning limit of {t_hold['temperature_warn_c']}°C.",
            "buttonText": "Monitor", "buttonClass": "alert"
        })

    # Current checks
    if record.current >= t_hold["current_critical_a"]:
        issues.append({
            "title": "Critical: Current overload",
            "description": f"Current at {round(record.current, 1)} A exceeds critical limit of {t_hold['current_critical_a']} A.",
            "buttonText": "Alert", "buttonClass": "alert"
        })
    elif record.current >= t_hold["current_warn_a"]:
        issues.append({
            "title": "Warning: Current elevated",
            "description": f"Current at {round(record.current, 1)} A exceeds warning limit of {t_hold['current_warn_a']} A.",
            "buttonText": "Monitor", "buttonClass": "alert"
        })

    if not issues:
        issues.append({
            "title": "All systems nominal",
            "description": "No threshold violations detected. Next routine inspection as scheduled.",
            "buttonText": "Review", "buttonClass": "review"
        })

    # ── Risk score and derived metrics ───────────────────────────────────────
    latest_prediction = db.query(PredictionRecord).filter(
        PredictionRecord.asset_id == asset_id
    ).order_by(PredictionRecord.timestamp.desc()).first()

    if latest_prediction is not None:
        risk          = latest_prediction.risk_score
        system_health = _ml_health(risk)
        health_source = "ml"
    else:
        # No prediction has been run yet — fall back to RMS-based health
        # so the panel always shows a meaningful number.
        critical_rms  = t_hold["vibration_critical_mms"]
        system_health = _rms_health(record.rms, critical_rms)
        risk          = 1.0 - (system_health / 100.0)
        health_source = "rms_fallback"

    if risk >= 0.80:
        next_maintenance = "Immediate"
    elif risk >= 0.60:
        next_maintenance = "3–7 days"
    elif risk >= 0.40:
        next_maintenance = "14 days"
    else:
        next_maintenance = "30+ days"

    return {
        "nextMaintenance": next_maintenance,
        "systemHealth":    system_health,
        "healthSource":    health_source,   # "ml" or "rms_fallback"
        "issues":          issues,
    }


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
        {"ts": r.timestamp.isoformat(), "risk_score": round(r.risk_score * 100, 1)}
        for r in reversed(records)
    ]
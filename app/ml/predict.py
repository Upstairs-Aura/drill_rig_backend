import os, joblib
import numpy as np
from app.ml.features import record_to_features, FEATURE_COLUMNS

_iso_model   = None
_rf_model    = None
_lstm_model  = None
_lstm_scaler = None

def _load():
    global _iso_model, _rf_model, _lstm_model, _lstm_scaler

    if os.path.exists("app/models/isolation_forest.pkl"):
        _iso_model = joblib.load("app/models/isolation_forest.pkl")
        print("Loaded: isolation_forest.pkl")

    if os.path.exists("app/models/random_forest.pkl"):
        _rf_model = joblib.load("app/models/random_forest.pkl")
        print("Loaded: random_forest.pkl")

    if (os.path.exists("app/models/lstm_model.keras") and
            os.path.exists("app/models/lstm_scaler.pkl")):
        from tensorflow.keras.models import load_model
        _lstm_model  = load_model("app/models/lstm_model.keras")
        _lstm_scaler = joblib.load("app/models/lstm_scaler.pkl")
        print("Loaded: lstm_model.keras + lstm_scaler.pkl")

_load()

def predict(record, recent_records=None):
    """
    Run inference on a FeatureRecord ORM object.
    recent_records: list of the last 7 FeatureRecord objects (needed for LSTM).
    Returns: { anomaly: bool, risk_score: float, source: str }
    Returns None if no model is available.
    """
    # Random Forest — highest priority
    if _rf_model is not None:
        features = record_to_features(record)
        prob = _rf_model.predict_proba(features)[0][1]
        return {
            "anomaly":    bool(prob >= 0.5),
            "risk_score": round(float(prob), 4),
            "source":     "random_forest",
        }

    # LSTM — second priority
    if _lstm_model is not None and recent_records is not None:
        if len(recent_records) >= 7:
            import pandas as pd
            seq_df = pd.DataFrame(
                [{col: getattr(r, col) for col in FEATURE_COLUMNS}
                 for r in recent_records[-7:]]
            )
            seq_scaled = _lstm_scaler.transform(seq_df)
            seq_input  = seq_scaled.reshape(1, 7, len(FEATURE_COLUMNS))
            prob = float(_lstm_model.predict(seq_input, verbose=0)[0][0])
            return {
                "anomaly":    bool(prob >= 0.5),
                "risk_score": round(prob, 4),
                "source":     "lstm",
            }

    # Isolation Forest — fallback
    if _iso_model is not None:
        features = record_to_features(record)
        raw  = _iso_model.decision_function(features)[0]
        risk = round(float(1 / (1 + np.exp(raw * 3))), 4)
        return {
            "anomaly":    bool(_iso_model.predict(features)[0] == -1),
            "risk_score": risk,
            "source":     "isolation_forest",
        }

    return None
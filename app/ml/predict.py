import os, joblib
import numpy as np
from ml.features import record_to_features

_iso_model = None
_rf_model  = None

def _load():
    global _iso_model, _rf_model
    if os.path.exists("models/isolation_forest.pkl"):
        _iso_model = joblib.load("models/isolation_forest.pkl")
        print("Loaded: isolation_forest.pkl")
    if os.path.exists("models/random_forest.pkl"):
        _rf_model = joblib.load("models/random_forest.pkl")
        print("Loaded: random_forest.pkl")

_load()

def predict(record):
    """
    Run inference on a single FeatureRecord ORM object.
    Returns: { anomaly: bool, risk_score: float, source: str }
    Returns None if no model is available.
    """
    features = record_to_features(record)

    if _rf_model is not None:
        prob = _rf_model.predict_proba(features)[0][1]
        return {
            "anomaly":    bool(prob >= 0.5),
            "risk_score": round(float(prob), 4),
            "source":     "random_forest"
        }

    if _iso_model is not None:
        raw  = _iso_model.decision_function(features)[0]
        # Normalise: more negative = more anomalous → higher risk score
        risk = round(float(1 / (1 + np.exp(raw * 3))), 4)
        return {
            "anomaly":    bool(_iso_model.predict(features)[0] == -1),
            "risk_score": risk,
            "source":     "isolation_forest"
        }

    return None
import os, joblib
import numpy as np
from app.ml.features import record_to_features, FEATURE_COLUMNS

_iso_model      = None
_rf_model       = None
_lstm_model     = None
_lstm_scaler    = None
_lstm_threshold = 0.5

LSTM_SEQ_LEN = 24   # must match SEQUENCE_LENGTH in train_lstm.py

def _load():
    global _iso_model, _rf_model, _lstm_model, _lstm_scaler, _lstm_threshold

    if os.path.exists("app/models/isolation_forest.pkl"):
        _iso_model = joblib.load("app/models/isolation_forest.pkl")

    if os.path.exists("app/models/random_forest.pkl"):
        _rf_model = joblib.load("app/models/random_forest.pkl")

    if (os.path.exists("app/models/lstm_model.keras") and
            os.path.exists("app/models/lstm_scaler.pkl")):
        from tensorflow.keras.models import load_model
        _lstm_model  = load_model("app/models/lstm_model.keras")
        _lstm_scaler = joblib.load("app/models/lstm_scaler.pkl")
        if os.path.exists("app/models/lstm_threshold.pkl"):
            _lstm_threshold = joblib.load("app/models/lstm_threshold.pkl")
        print(f"Loaded LSTM (threshold={_lstm_threshold:.2f})")

_load()

def predict(record, recent_records=None):
    # 1. LSTM first — preferred when we have a full sequence
    if _lstm_model is not None and recent_records is not None:
        if len(recent_records) >= LSTM_SEQ_LEN:
            import pandas as pd
            seq_df = pd.DataFrame(
                [{col: getattr(r, col) for col in FEATURE_COLUMNS}
                 for r in recent_records[-LSTM_SEQ_LEN:]]
            )
            seq_scaled = _lstm_scaler.transform(seq_df)
            seq_input  = seq_scaled.reshape(1, LSTM_SEQ_LEN, len(FEATURE_COLUMNS))
            prob = float(_lstm_model.predict(seq_input, verbose=0)[0][0])
            return {"anomaly": bool(prob >= _lstm_threshold), "risk_score": round(prob, 4), "source": "lstm"}

    # 2. Random Forest — fallback when sequence is too short
    if _rf_model is not None:
        features = record_to_features(record)
        prob = _rf_model.predict_proba(features)[0][1]
        return {"anomaly": bool(prob >= 0.5), "risk_score": round(float(prob), 4), "source": "random_forest"}

    # 3. Isolation Forest — last resort, no labels needed
    if _iso_model is not None:
        features = record_to_features(record)
        raw  = _iso_model.decision_function(features)[0]
        risk = round(float(1 / (1 + np.exp(raw * 3))), 4)
        return {"anomaly": bool(_iso_model.predict(features)[0] == -1), "risk_score": risk, "source": "isolation_forest"}

    return None
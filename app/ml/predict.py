import os, joblib
import numpy as np
from app.ml.features import record_to_features, FEATURE_COLUMNS
from sklearn.pipeline import Pipeline

_iso_model      = None
_rf_model:   Pipeline | None = None
_lstm_model     = None
_lstm_scaler    = None
_lstm_threshold = 0.5
_rf_threshold   = 0.05

_rf_f1   = 0.0
_lstm_f1 = 0.0

LSTM_SEQ_LEN = 24

def _load():
    global _iso_model, _rf_model, _lstm_model, _lstm_scaler
    global _lstm_threshold, _rf_threshold, _rf_f1, _lstm_f1
    global _active_model

    if os.path.exists("app/models/isolation_forest.pkl"):
        _iso_model = joblib.load("app/models/isolation_forest.pkl")

    if os.path.exists("app/models/random_forest.pkl"):
        _rf_model = joblib.load("app/models/random_forest.pkl")
        if os.path.exists("app/models/rf_threshold.pkl"):
            _rf_threshold = joblib.load("app/models/rf_threshold.pkl")
        if os.path.exists("app/models/rf_metrics.pkl"):
            _rf_f1 = joblib.load("app/models/rf_metrics.pkl")["pre_failure_f1"]

    if (os.path.exists("app/models/lstm_model.keras") and
            os.path.exists("app/models/lstm_scaler.pkl")):
        from tensorflow.keras.models import load_model
        _lstm_model  = load_model("app/models/lstm_model.keras")
        _lstm_scaler = joblib.load("app/models/lstm_scaler.pkl")
        if os.path.exists("app/models/lstm_threshold.pkl"):
            _lstm_threshold = joblib.load("app/models/lstm_threshold.pkl")
        if os.path.exists("app/models/lstm_metrics.pkl"):
            _lstm_f1 = joblib.load("app/models/lstm_metrics.pkl")["pre_failure_f1"]

    print(f"Model f1 score — RF: {_rf_f1:.2f} | LSTM: {_lstm_f1:.2f} || Isolation Forest (fallback)")
    _active_model = _select_model()
    print(f"Active model selected: {_active_model}")

_load()

# ─── Add this function after _load() ───────────────────────────────────────

def _select_model() -> str:
    rf_ready   = _rf_model is not None
    lstm_ready = _lstm_model is not None and _lstm_scaler is not None

    if rf_ready and lstm_ready:
        if _rf_f1 > 0.0 or _lstm_f1 > 0.0:
            return "random_forest" if _rf_f1 >= _lstm_f1 else "lstm"
        else:
            return "lstm"   # both untrained — prefer LSTM (.keras ships in repo)

    if rf_ready:
        return "random_forest"
    if lstm_ready:
        return "lstm"
    if _iso_model is not None:
        return "isolation_forest"

    return "none"

_active_model: str = "none"   # set after _load()


def _predict_rf(record, recent_records):
    import pandas as pd
    from app.ml.train_forest import add_rolling_features, ROLL_WINDOW
    feature_cols = joblib.load("app/models/rf_feature_cols.pkl")
    src = recent_records if (recent_records and len(recent_records) >= 2) else [record]
    rows = [{col: getattr(r, col) for col in FEATURE_COLUMNS} for r in src]
    df_rolled = add_rolling_features(pd.DataFrame(rows), ROLL_WINDOW)
    prob = float(_rf_model.predict_proba(df_rolled[feature_cols].iloc[[-1]])[0][1])
    return {"anomaly": bool(prob >= _rf_threshold), "risk_score": round(prob, 4), "source": "random_forest"}


def _predict_lstm(recent_records):
    import pandas as pd
    seq_df = pd.DataFrame(
        [{col: getattr(r, col) for col in FEATURE_COLUMNS}
         for r in recent_records[-LSTM_SEQ_LEN:]]
    )
    seq_input = _lstm_scaler.transform(seq_df).reshape(1, LSTM_SEQ_LEN, len(FEATURE_COLUMNS))
    prob = float(_lstm_model.predict(seq_input, verbose=0)[0][0])
    return {"anomaly": bool(prob >= _lstm_threshold), "risk_score": round(prob, 4), "source": "lstm"}


def predict(record, recent_records=None):
    lstm_ready = (_lstm_model is not None and
                  recent_records is not None and
                  len(recent_records) >= LSTM_SEQ_LEN)

    if _active_model == "random_forest" and _rf_model is not None:
        return _predict_rf(record, recent_records)

    if _active_model == "lstm" and lstm_ready:
        return _predict_lstm(recent_records)

    # LSTM was chosen but not enough records yet — fall back to RF
    if _active_model == "lstm" and _rf_model is not None:
        return _predict_rf(record, recent_records)

    if _active_model == "isolation_forest" and _iso_model is not None:
        features = record_to_features(record)
        raw  = _iso_model.decision_function(features)[0]
        risk = round(float(1 / (1 + np.exp(raw * 3))), 4)
        return {"anomaly": bool(_iso_model.predict(features)[0] == -1), "risk_score": risk, "source": "isolation_forest"}

    return None
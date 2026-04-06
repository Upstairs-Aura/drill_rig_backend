import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, f1_score, recall_score
from app.database import SessionLocal
from app.models import FeatureRecord, MaintenanceEvent
from app.ml.features import FEATURE_COLUMNS
from datetime import timedelta

ROLL_WINDOW = 24
LABEL_WINDOW_DAYS = 7

# Set 2 (set2-bearing1) is excluded: its full run duration (~7 days)
# falls entirely within the pre-failure label window, leaving zero
# normal examples. Including it collapses the class distribution and
# causes the decision threshold to degenerate. Sets 1 and 3 provide
# sufficient run-to-failure trajectories covering both health states.
ALL_ASSETS = [
    "set1-bearing3-x",
    "set1-bearing3-y",
    "set3-bearing3",
]


def add_rolling_features(df: pd.DataFrame, window: int) -> pd.DataFrame:
    augmented = df.copy()
    for col in FEATURE_COLUMNS:
        rolling  = df[col].rolling(window, min_periods=1)
        mean_col = rolling.mean()
        augmented[f"{col}_mean"]  = mean_col
        augmented[f"{col}_std"]   = rolling.std().fillna(0)
        augmented[f"{col}_slope"] = mean_col.diff(window).fillna(0)
    return augmented


def load_asset(db, asset_id: str, event_times_by_asset: dict):
    records = (
        db.query(FeatureRecord)
        .filter(FeatureRecord.asset_id == asset_id)
        .order_by(FeatureRecord.timestamp)
        .all()
    )
    if not records:
        return pd.DataFrame()

    rows, timestamps = [], []
    for r in records:
        rows.append({col: getattr(r, col) for col in FEATURE_COLUMNS})
        timestamps.append(r.timestamp)

    df = pd.DataFrame(rows)
    event_times = event_times_by_asset.get(asset_id, [])

    labels = [
        1 if any(timedelta(0) <= (e - ts) <= timedelta(days=LABEL_WINDOW_DAYS)
                 for e in event_times) else 0
        for ts in timestamps
    ]
    df["label"] = labels
    pos = sum(labels)
    pct = pos / len(records) * 100
    print(f"  {asset_id}: {len(records)} records, {pos} pre-failure ({pct:.1f}%)")

    if pct == 100.0:
        print(f"  WARNING: {asset_id} is 100% pre-failure — "
              f"run duration shorter than label window. Excluding.")
        return pd.DataFrame()

    return add_rolling_features(df, ROLL_WINDOW)


def train():
    db = SessionLocal()
    all_events = db.query(MaintenanceEvent).all()
    event_times_by_asset: dict = {}
    for e in all_events:
        event_times_by_asset.setdefault(e.asset_id, []).append(e.timestamp)

    print("\n--- Loading assets ---")
    asset_dfs = []
    for asset_id in ALL_ASSETS:
        df = load_asset(db, asset_id, event_times_by_asset)
        if not df.empty:
            asset_dfs.append(df)
    db.close()

    if not asset_dfs:
        print("No usable assets loaded.")
        return

    feature_cols = [c for c in asset_dfs[0].columns if c != "label"]

    train_parts, val_parts, test_parts = [], [], []
    for df in asset_dfs:
        n = len(df)
        t = int(n * 0.70)
        v = int(n * 0.85)
        train_parts.append(df.iloc[:t])
        val_parts.append(df.iloc[t:v])
        test_parts.append(df.iloc[v:])

    train_df = pd.concat(train_parts, ignore_index=True)
    val_df   = pd.concat(val_parts,   ignore_index=True)
    test_df  = pd.concat(test_parts,  ignore_index=True)

    X_train, y_train = train_df[feature_cols], train_df["label"]
    X_val,   y_val   = val_df[feature_cols],   val_df["label"]
    X_test,  y_test  = test_df[feature_cols],  test_df["label"]

    print(f"\nTrain: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
    print(f"Pre-failure in train / val / test: "
          f"{y_train.sum()} / {y_val.sum()} / {y_test.sum()}")

    if y_train.sum() < 5:
        print("Too few pre-failure examples in training window.")
        return

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model",  RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42,
        ))
    ])
    pipeline.fit(X_train, y_train)

    val_probs = pipeline.predict_proba(X_val)[:, 1]
    best_thresh, best_f1 = 0.5, 0.0
    for thresh in np.arange(0.05, 0.95, 0.05):
        preds = (val_probs >= thresh).astype(int)
        f1    = f1_score(y_val, preds, pos_label=1, zero_division=0)
        if f1 > best_f1:
            best_f1, best_thresh = f1, float(thresh)
    print(f"\nOptimal threshold: {best_thresh:.2f}  "
          f"(val pre-failure F1={best_f1:.3f})")

    print("\n--- Validation Set Results ---")
    print(classification_report(
        y_val, (val_probs >= best_thresh).astype(int),
        target_names=["Normal", "Pre-failure"], zero_division=0))

    test_probs = pipeline.predict_proba(X_test)[:, 1]
    print("--- Test Set Results ---")
    print(classification_report(
        y_test, (test_probs >= best_thresh).astype(int),
        target_names=["Normal", "Pre-failure"], zero_division=0))
    joblib.dump({"pre_failure_f1": float(f1_score(y_test, (test_probs >= best_thresh).astype(int), pos_label=1, zero_division=0))},
                "app/models/rf_metrics.pkl")

    os.makedirs("app/models", exist_ok=True)
    joblib.dump(pipeline,     "app/models/random_forest.pkl")
    joblib.dump(best_thresh,  "app/models/rf_threshold.pkl")
    joblib.dump(feature_cols, "app/models/rf_feature_cols.pkl")
    print(f"\nSaved model, threshold ({best_thresh:.2f}), "
          f"{len(feature_cols)} features → app/models/")


if __name__ == "__main__":
    train()
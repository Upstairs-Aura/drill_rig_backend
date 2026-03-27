import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from app.database import SessionLocal
from app.models import FeatureRecord, MaintenanceEvent
from app.ml.features import records_to_dataframe, FEATURE_COLUMNS
from datetime import timedelta

def train():
    db = SessionLocal()
    records = db.query(FeatureRecord).all()
    events  = db.query(MaintenanceEvent).all()
    db.close()

    if not events:
        print("No maintenance events found. Run seed.py first.")
        return

    event_times = [e.timestamp for e in events]
    df = records_to_dataframe(records)
    timestamps = [r.timestamp for r in records]

    # Label: 1 if a failure occurred within 7 days of this reading
    labels = []
    for ts in timestamps:
        upcoming = [e for e in event_times
                    if timedelta(0) <= (e - ts) <= timedelta(days=7)]
        labels.append(1 if upcoming else 0)

    df["label"] = labels
    positives = sum(labels)
    print(f"Training on {len(df)} records — {positives} pre-failure, {len(df)-positives} normal")

    if positives < 5:
        print("Too few failure examples (need at least 5). Add more maintenance events.")
        return

    X = df[FEATURE_COLUMNS]
    y = df["label"]

    # 70/15/15 chronological split (matches thesis Section 3.6.2)
    X_temp,  X_test,  y_temp,  y_test  = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y)
    X_train, X_val,   y_train, y_val   = train_test_split(
        X_temp, y_temp, test_size=0.176, random_state=42, stratify=y_temp)
    # 0.176 of 0.85 ≈ 0.15 of total → gives ~70/15/15

    print(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42,
        ))
    ])
    pipeline.fit(X_train, y_train)

    print("\n--- Validation Set Results ---")
    print(classification_report(y_val, pipeline.predict(X_val),
                                target_names=["Normal", "Pre-failure"], zero_division=0))

    print("--- Test Set Results ---")
    print(classification_report(y_test, pipeline.predict(X_test),
                                target_names=["Normal", "Pre-failure"], zero_division=0))

    os.makedirs("app/models", exist_ok=True)
    joblib.dump(pipeline, "app/models/random_forest.pkl")
    print("Saved → app/models/random_forest.pkl")

if __name__ == "__main__":
    train()
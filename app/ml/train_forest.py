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
from ml.features import records_to_dataframe, FEATURE_COLUMNS
from datetime import timedelta

def train():
    db = SessionLocal()
    records = db.query(FeatureRecord).all()
    events  = db.query(MaintenanceEvent).all()
    db.close()

    if not events:
        print("No maintenance events found. Cannot train Random Forest yet.")
        print("Log failures in the maintenance_events table first, then re-run.")
        return

    event_times = [e.timestamp for e in events]
    df = records_to_dataframe(records)
    timestamps = [r.timestamp for r in records]

    # Label: 1 if a failure occurred within 7 days of this reading
    labels = []
    for ts in timestamps:
        upcoming = [
            e for e in event_times
            if timedelta(0) <= (e - ts) <= timedelta(days=7)
        ]
        labels.append(1 if upcoming else 0)

    df["label"] = labels
    positives = sum(labels)
    print(f"Training on {len(df)} records — {positives} pre-failure, {len(df)-positives} normal")

    if positives < 5:
        print("Too few failure examples (need at least 5). Collect more data first.")
        return

    X = df[FEATURE_COLUMNS]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42
        ))
    ])
    pipeline.fit(X_train, y_train)
    print(classification_report(y_test, pipeline.predict(X_test)))

    os.makedirs("models", exist_ok=True)
    joblib.dump(pipeline, "models/random_forest.pkl")
    print("Saved → models/random_forest.pkl")
    print("Deploy to Pi:")
    print("  scp models/random_forest.pkl pi@<pi-ip>:~/drill_rig_backend-Third/models/")

if __name__ == "__main__":
    train()
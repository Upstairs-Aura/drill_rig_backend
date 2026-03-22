import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from app.database import SessionLocal
from app.models import FeatureRecord
from ml.features import records_to_dataframe

def train():
    db = SessionLocal()
    records = db.query(FeatureRecord).all()
    db.close()

    if len(records) < 10:
        print(f"Only {len(records)} records — need at least 10. Run seed.py first.")
        return

    df = records_to_dataframe(records)
    print(f"Training Isolation Forest on {len(df)} records...")

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42
        ))
    ])
    pipeline.fit(df)

    os.makedirs("models", exist_ok=True)
    joblib.dump(pipeline, "models/isolation_forest.pkl")
    print("Saved → models/isolation_forest.pkl")

if __name__ == "__main__":
    train()
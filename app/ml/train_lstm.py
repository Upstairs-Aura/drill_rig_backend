import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
from app.database import SessionLocal
from app.models import FeatureRecord, MaintenanceEvent
from app.ml.features import FEATURE_COLUMNS
from datetime import timedelta

SEQUENCE_LENGTH = 7  # 7 consecutive daily readings = one week of history

def build_sequences(df, labels, seq_len):
    X, y = [], []
    for i in range(len(df) - seq_len):
        X.append(df.iloc[i:i + seq_len].values)
        y.append(labels[i + seq_len])
    return np.array(X), np.array(y)

def train():
    db = SessionLocal()
    records = db.query(FeatureRecord).order_by(FeatureRecord.timestamp).all()
    events  = db.query(MaintenanceEvent).all()
    db.close()

    if len(records) < SEQUENCE_LENGTH + 5:
        print(f"Need at least {SEQUENCE_LENGTH + 5} records. Run seed.py first.")
        return

    event_times = [e.timestamp for e in events]

    # Build a labelled dataframe from all records
    rows, timestamps, labels = [], [], []
    for r in records:
        rows.append({col: getattr(r, col) for col in FEATURE_COLUMNS})
        timestamps.append(r.timestamp)

    df = pd.DataFrame(rows)

    # Label: 1 if a failure occurred within 7 days after this reading
    for ts in timestamps:
        upcoming = [e for e in event_times
                    if timedelta(0) <= (e - ts) <= timedelta(days=7)]
        labels.append(1 if upcoming else 0)

    positives = sum(labels)
    print(f"Building sequences from {len(df)} records — "
          f"{positives} pre-failure labels, {len(df) - positives} normal")

    # Scale features before sequencing
    scaler = StandardScaler()
    df_scaled = pd.DataFrame(scaler.fit_transform(df), columns=FEATURE_COLUMNS)

    X, y = build_sequences(df_scaled, labels, SEQUENCE_LENGTH)
    print(f"Sequence shape: {X.shape}, Labels shape: {y.shape}")

    if sum(y) < 3:
        print("Too few positive sequences after windowing. Add more maintenance events.")
        return

    # Chronological 70/15/15 split — no shuffle, order matters for time-series
    n = len(X)
    train_end = int(n * 0.70)
    val_end   = int(n * 0.85)

    X_train, y_train = X[:train_end],       y[:train_end]
    X_val,   y_val   = X[train_end:val_end], y[train_end:val_end]
    X_test,  y_test  = X[val_end:],          y[val_end:]

    print(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    # LSTM architecture: 2 stacked layers with dropout for regularisation
    model = Sequential([
        LSTM(64, input_shape=(SEQUENCE_LENGTH, len(FEATURE_COLUMNS)),
             return_sequences=True),
        Dropout(0.2),
        LSTM(32, return_sequences=False),
        Dropout(0.2),
        Dense(1, activation="sigmoid"),
    ])
    model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
    model.summary()

    early_stop = EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)

    model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=50,
        batch_size=16,
        callbacks=[early_stop],
        verbose=1,
    )

    # Evaluate on held-out test set
    y_pred = (model.predict(X_test) >= 0.5).astype(int).flatten()
    print("\n--- LSTM Test Set Results ---")
    print(classification_report(y_test, y_pred, target_names=["Normal", "Pre-failure"],
                                zero_division=0))

    # Save model and scaler
    os.makedirs("app/models", exist_ok=True)
    model.save("app/models/lstm_model.keras")
    joblib.dump(scaler, "app/models/lstm_scaler.pkl")
    print("Saved → app/models/lstm_model.keras")
    print("Saved → app/models/lstm_scaler.pkl")

if __name__ == "__main__":
    train()
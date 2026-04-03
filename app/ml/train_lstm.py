import sys, os
from keras.src.regularizers import L2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
from app.database import SessionLocal
from app.models import FeatureRecord, MaintenanceEvent
from app.ml.features import FEATURE_COLUMNS
from datetime import timedelta

SEQUENCE_LENGTH = 24
LABEL_WINDOW_H  = 72

ALL_ASSETS = ["set1-bearing3-x", "set1-bearing3-y", "set2-bearing1", "set3-bearing3"]

def build_sequences(df, labels, seq_len):
    X, y = [], []
    for i in range(len(df) - seq_len):
        X.append(df.iloc[i:i + seq_len].values)
        y.append(labels[i + seq_len-1])
    return np.array(X), np.array(y)





def load_asset_data(db, asset_id, event_times_by_asset):
    records = (
        db.query(FeatureRecord)
        .filter(
            FeatureRecord.asset_id == asset_id,
            FeatureRecord.source   == "ims",
            )
        .order_by(FeatureRecord.timestamp)
        .all()
    )
    if not records:
        return pd.DataFrame(), np.array([])

    rows, timestamps = [], []
    for r in records:
        rows.append({col: getattr(r, col) for col in FEATURE_COLUMNS})
        timestamps.append(r.timestamp)

    df = pd.DataFrame(rows)
    event_times = event_times_by_asset.get(asset_id, [])
    labels = []
    for ts in timestamps:
        upcoming = [e for e in event_times
                    if timedelta(0) <= (e - ts) <= timedelta(hours=LABEL_WINDOW_H)]
        labels.append(1 if upcoming else 0)

    pos = sum(labels)
    print(f"  {asset_id}: {len(records)} records, {pos} pre-failure ({pos/len(records)*100:.1f}%)")
    return df, np.array(labels)


def train():
    db = SessionLocal()

    all_events = db.query(MaintenanceEvent).all()
    event_times_by_asset = {}
    for e in all_events:
        event_times_by_asset.setdefault(e.asset_id, []).append(e.timestamp)

    print("\n--- Loading all assets ---")
    train_dfs, train_labels = [], []
    for asset_id in ALL_ASSETS:
        df, labels = load_asset_data(db, asset_id, event_times_by_asset)
        if df.empty:
            print(f"  WARNING: no records for {asset_id}")
            continue
        train_dfs.append(df)
        train_labels.append(labels)

    # Include any operator-confirmed live records
    live_records = (
        db.query(FeatureRecord)
        .filter(FeatureRecord.source == "live", FeatureRecord.label != None)
        .order_by(FeatureRecord.timestamp)
        .all()
    )
    db.close()

    if live_records:
        live_rows = [{col: getattr(r, col) for col in FEATURE_COLUMNS} for r in live_records]
        live_lbls = np.array([r.label for r in live_records])
        live_df   = pd.DataFrame(live_rows)
        print(f"\nLabelled live records: {len(live_records)} ({live_lbls.sum()} pre-failure)")
        train_dfs.append(live_df)
        train_labels.append(live_lbls)
    else:
        print("\nNo labelled live records found — training on IMS data only")


    if not train_dfs:
        print("ERROR: Missing training data. Check source column and seed.")
        return
    all_df = pd.concat(train_dfs, ignore_index=True)
    scaler = StandardScaler()
    scaler.fit(all_df)

    X_train_parts, y_train_parts = [], []
    X_val_parts,   y_val_parts   = [], []
    X_test_parts,  y_test_parts  = [], []

    for df, labels in zip(train_dfs, train_labels):
        df_scaled = pd.DataFrame(scaler.transform(df), columns=FEATURE_COLUMNS)
        if len(df_scaled) <= SEQUENCE_LENGTH:
            continue
        X, y = build_sequences(df_scaled, labels, SEQUENCE_LENGTH)
        n = len(X)
        t = int(n * 0.70)
        v = int(n * 0.85)
        X_train_parts.append(X[:t]);  y_train_parts.append(y[:t])
        X_val_parts.append(X[t:v]);   y_val_parts.append(y[t:v])
        X_test_parts.append(X[v:]);   y_test_parts.append(y[v:])

    X_train = np.concatenate(X_train_parts)
    y_train = np.concatenate(y_train_parts)
    X_val   = np.concatenate(X_val_parts)
    y_val   = np.concatenate(y_val_parts)
    X_test  = np.concatenate(X_test_parts)
    y_test  = np.concatenate(y_test_parts)

    print(f"\nTrain: {len(X_train)} ({y_train.sum()} pos) | "
          f"Val: {len(X_val)} ({y_val.sum()} pos) | "
          f"Test: {len(X_test)} ({y_test.sum()} pos)")

    if y_train.sum() < 3:
        print("ERROR: Too few positives in training. Check source column backfill.")
        return

    pos = y_train.sum()
    neg = len(y_train) - pos
    class_weight = {0: 1.0, 1: float(neg / pos)}
    print(f"Class weights → Normal: 1.00, Pre-failure: {neg/pos:.2f}")

    model = Sequential([
        LSTM(64, input_shape=(SEQUENCE_LENGTH, len(FEATURE_COLUMNS)),
             return_sequences=True, kernel_regularizer=L2(0.001)),
        Dropout(0.3),
        LSTM(32, return_sequences=False, kernel_regularizer=L2(0.001)),
        Dropout(0.3),
        Dense(1, activation="sigmoid"),
    ])

    model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
    model.summary()

    model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        class_weight=class_weight,
        epochs=30,
        shuffle=False,
        batch_size=16,
        callbacks=[EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)],
        verbose=1,
    )

    from sklearn.metrics import f1_score

    val_probs = model.predict(X_val, verbose=0).flatten()

    # Sweep thresholds on validation set, optimise for pre-failure F1
    best_threshold, best_f1 = 0.5, 0.0
    for t in np.arange(0.1, 0.9, 0.05):
        preds = (val_probs >= t).astype(int)
        f1 = f1_score(y_val, preds, pos_label=1, zero_division=0)
        if f1 > best_f1:
            best_f1, best_threshold = f1, float(t)

    threshold = best_threshold
    print(f"\nOptimal threshold: {threshold:.2f}  (val pre-failure F1={best_f1:.3f})")

    print("\n--- Validation Set Results ---")
    print(classification_report(y_val,
                                (val_probs >= threshold).astype(int),
                                target_names=["Normal", "Pre-failure"], labels=[0, 1], zero_division=0))

    print("--- Test Set Results ---")
    print(classification_report(y_test,
                                (model.predict(X_test, verbose=0).flatten() >= threshold).astype(int),
                                target_names=["Normal", "Pre-failure"], labels=[0, 1], zero_division=0))

    os.makedirs("app/models", exist_ok=True)
    model.save("app/models/lstm_model.keras")
    joblib.dump(scaler,    "app/models/lstm_scaler.pkl")
    joblib.dump(threshold, "app/models/lstm_threshold.pkl")
    print(f"Saved model, scaler, threshold ({threshold:.2f})")


if __name__ == "__main__":
    train()
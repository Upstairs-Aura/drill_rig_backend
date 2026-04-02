# seed_nasa.py
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from nasa_loader import load_test_set
from app.database import SessionLocal, engine, Base
from app.models import Asset, Sensor, FeatureRecord, MaintenanceEvent, AssetConfig, PredictionRecord
from app.config.constants import (
    FILTER_ORDER, LOWCUT_HZ, HIGHCUT_HZ, WINDOW_LENGTH,
    VIBRATION_WARN_MMS, VIBRATION_CRITICAL_MMS,
    TEMPERATURE_WARN_C, TEMPERATURE_CRITICAL_C,
    CURRENT_WARN_A, CURRENT_CRITICAL_A,
)

Base.metadata.create_all(bind=engine)

FAILURE_EVENTS = [
    ("bearing-1-ch3", datetime(2003, 11, 25, 23, 39, 56), "inner_race_failure",
     "Test Set 1, Bearing 3 inner race defect"),
    ("bearing-1-ch4", datetime(2003, 11, 25, 23, 39, 56), "rolling_element_failure",
     "Test Set 1, Bearing 4 rolling element defect"),
    ("bearing-2-ch1", datetime(2004, 2, 19, 6, 22, 39), "outer_race_failure",
     "Test Set 2, Bearing 1 outer race defect"),
    ("bearing-3-ch3", datetime(2004, 4, 8, 9, 27, 13), "outer_race_failure",
     "Test Set 3, Bearing 3 outer race defect"),
]

ASSETS = [
    {"asset_id": "bearing-1-ch3", "name": "Test1 Bearing 3", "sensor_id": "s-1-3",
     "folder": r"C:\Users\User\Downloads\1st_test\1st_test", "channel": 2},
    {"asset_id": "bearing-1-ch4", "name": "Test1 Bearing 4", "sensor_id": "s-1-4",
     "folder": r"C:\Users\User\Downloads\1st_test\1st_test", "channel": 3},
    {"asset_id": "bearing-2-ch1", "name": "Test2 Bearing 1", "sensor_id": "s-2-1",
     "folder": r"C:\Users\User\Downloads\2nd_test\2nd_test", "channel": 0},
    {"asset_id": "bearing-3-ch3", "name": "Test3 Bearing 3", "sensor_id": "s-3-3",
     "folder": r"C:\Users\User\Downloads\3rd_test\4th_test", "channel": 2},
]


def seed_nasa():
    db = SessionLocal()

    # Delete in correct order — children before parents
    db.query(PredictionRecord).delete()
    db.query(FeatureRecord).delete()
    db.query(MaintenanceEvent).delete()
    db.query(AssetConfig).delete()
    db.query(Sensor).delete()
    db.query(Asset).delete()
    db.commit()

    # Create assets and sensors
    for a in ASSETS:
        db.add(Asset(id=a["asset_id"], name=a["name"],
                     asset_type="bearing", drill=a["name"]))
        db.add(Sensor(id=a["sensor_id"], asset_id=a["asset_id"],
                      sensor_type="vibration"))
    db.commit()

    # Create AssetConfig for each bearing
    for a in ASSETS:
        config = {
            "sensors": [{"sensor_id": a["sensor_id"], "sensor_type": "vibration"}],
            "sampling": {
                "sampling_rate_hz":  20000.0,
                "burst_duration_s":  1.0,
                "samples_per_burst": 20480,
            },
            "filter": {
                "filter_order":  FILTER_ORDER,
                "lowcut_hz":     LOWCUT_HZ,
                "highcut_hz":    HIGHCUT_HZ,
                "window_length": WINDOW_LENGTH,
            },
            "thresholds": {
                "vibration_warn_mms":     VIBRATION_WARN_MMS,
                "vibration_critical_mms": VIBRATION_CRITICAL_MMS,
                "temperature_warn_c":     TEMPERATURE_WARN_C,
                "temperature_critical_c": TEMPERATURE_CRITICAL_C,
                "current_warn_a":         CURRENT_WARN_A,
                "current_critical_a":     CURRENT_CRITICAL_A,
            },
        }
        db.add(AssetConfig(asset_id=a["asset_id"], version=1,
                           is_active=True, config=config))
    db.commit()

    # Load NASA data and insert feature records
    total = 0
    for a in ASSETS:
        df = load_test_set(a["folder"], channel=a["channel"])
        if df.empty:
            print(f"  [WARNING] No data loaded for {a['asset_id']} — skipping")
            continue
        for _, row in df.iterrows():
            db.add(FeatureRecord(
                asset_id=a["asset_id"],
                sensor_id=a["sensor_id"],
                timestamp=row["timestamp"],
                rms=row["rms"],
                peak=row["peak"],
                crest_factor=row["crest_factor"],
                kurtosis=row["kurtosis"],
                skewness=row["skewness"],
                dominant_frequency=row["dominant_frequency"],
                bpfo_ratio=row["bpfo_ratio"],
                bpfi_ratio=row["bpfi_ratio"],
                temperature=row["temperature"],
                current=row["current"],
                source="ims",
            ))
        total += len(df)
        print(f"  Inserted {len(df)} records for {a['asset_id']}")

    db.commit()

    # Insert known failure events
    for asset_id, ts, etype, notes in FAILURE_EVENTS:
        db.add(MaintenanceEvent(asset_id=asset_id, timestamp=ts,
                                event_type=etype, notes=notes))
    db.commit()
    db.close()

    print(f"\nDone. Seeded {total} NASA bearing records + {len(FAILURE_EVENTS)} failure events.")


if __name__ == "__main__":
    seed_nasa()
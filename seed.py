import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
import random
from app.database import SessionLocal, engine, Base
from app.models import Asset, Sensor, FeatureRecord, MaintenanceEvent, PredictionRecord, AssetConfig
from app.config.constants import (
    ASSETS as ASSET_CONFIGS, SEED_PROFILES,
    SAMPLING_RATE_HZ, BURST_DURATION_S, SAMPLES_PER_BURST,
    FILTER_ORDER, LOWCUT_HZ, HIGHCUT_HZ, WINDOW_LENGTH,
    VIBRATION_WARN_MMS, VIBRATION_CRITICAL_MMS,
    TEMPERATURE_WARN_C, TEMPERATURE_CRITICAL_C,
    CURRENT_WARN_A, CURRENT_CRITICAL_A,
)

Base.metadata.create_all(bind=engine)

def seed_configs(db, assets):
    db.query(AssetConfig).delete()
    for asset in assets:
        asset_cfg = next(a for a in ASSET_CONFIGS if a["asset_id"] == asset.id)
        default_config = {
            "sensors": [{"sensor_id": asset_cfg["sensor_id"], "sensor_type": asset_cfg["sensor_type"]}],
            "sampling": {
                "sampling_rate_hz":  SAMPLING_RATE_HZ,
                "burst_duration_s":  BURST_DURATION_S,
                "samples_per_burst": SAMPLES_PER_BURST,
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
        db.add(AssetConfig(asset_id=asset.id, version=1, is_active=True, config=default_config))
    db.commit()

def seed():
    db = SessionLocal()

    # Clear existing data
    db.query(FeatureRecord).delete()
    db.query(MaintenanceEvent).delete()
    db.query(PredictionRecord).delete()
    db.query(AssetConfig).delete()
    db.query(Sensor).delete()
    db.query(Asset).delete()
    db.commit()

    # 4 drill assets
    assets = [
    Asset(id=a["asset_id"], name=a["name"], asset_type="gearbox", drill=a["drill"])
    for a in ASSET_CONFIGS
    ]
    db.add_all(assets)
    db.commit()

    # 1 vibration sensor per gearbox
    sensors = [
    Sensor(id=a["sensor_id"], asset_id=a["asset_id"], sensor_type=a["sensor_type"])
    for a in ASSET_CONFIGS
    ]
    db.add_all(sensors)
    db.commit()

    # Sensor profiles matching your mock data health levels
    profiles = SEED_PROFILES

    # 30 days of records, one per day per gearbox
    records = []
    for asset in assets:
        p = profiles[asset.id]
        for day in range(30):
            timestamp = datetime.utcnow() - timedelta(days=(30 - day))
            rms = random.uniform(*p["rms"])
            records.append(FeatureRecord(
                asset_id=asset.id,
                sensor_id=f"sensor-{asset.id}",
                timestamp=timestamp,
                rms=rms,
                peak=rms * random.uniform(2.5, 3.5),
                crest_factor=random.uniform(2.5, 4.0),
                kurtosis=random.uniform(3.0, 5.0),
                skewness=random.uniform(-0.5, 0.5),
                dominant_frequency=random.uniform(50.0, 120.0),
                temperature=random.uniform(*p["temp"]),
                current=random.uniform(*p["current"]),
            ))

    events = [
        MaintenanceEvent(
            asset_id="drill-a",
            timestamp=datetime.utcnow() - timedelta(days=20),
            event_type="bearing_failure",
            notes="Seeded: elevated vibration led to bearing replacement"
        ),
        MaintenanceEvent(
            asset_id="drill-a",
            timestamp=datetime.utcnow() - timedelta(days=7),
            event_type="gear_wear",
            notes="Seeded: gear tooth wear detected on inspection"
        ),
        MaintenanceEvent(
            asset_id="drill-c",
            timestamp=datetime.utcnow() - timedelta(days=25),
            event_type="bearing_failure",
            notes="Seeded: outer race bearing failure"
        ),
        MaintenanceEvent(
            asset_id="drill-c",
            timestamp=datetime.utcnow() - timedelta(days=14),
            event_type="overload",
            notes="Seeded: current overload tripped protection relay"
        ),
        MaintenanceEvent(
            asset_id="drill-c",
            timestamp=datetime.utcnow() - timedelta(days=3),
            event_type="gear_wear",
            notes="Seeded: gear mesh frequency amplitude exceeded threshold"
        ),
    ]
    db.add_all(records)
    db.commit()

    db.add_all(events)
    db.commit()


    seed_configs(db, assets)
    db.close()
    print(f"Seeded {len(assets)} assets, {len(sensors)} sensors, {len(records)} feature records, {len(events)} maintenance events.")

if __name__ == "__main__":
    seed()





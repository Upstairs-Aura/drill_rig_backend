import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
import random
from app.database import SessionLocal, engine, Base
from app.models import Asset, Sensor, FeatureRecord, MaintenanceEvent, PredictionRecord

Base.metadata.create_all(bind=engine)

def seed():
    db = SessionLocal()

    # Clear existing data
    db.query(FeatureRecord).delete()
    db.query(MaintenanceEvent).delete()
    db.query(PredictionRecord).delete()
    db.query(Sensor).delete()
    db.query(Asset).delete()
    db.commit()

    # 4 drill assets
    assets = [
        Asset(id="drill-a", name="Gearbox A", asset_type="gearbox", drill="Drill A"),
        Asset(id="drill-b", name="Gearbox B", asset_type="gearbox", drill="Drill B"),
        Asset(id="drill-c", name="Gearbox C", asset_type="gearbox", drill="Drill C"),
        Asset(id="drill-d", name="Gearbox D", asset_type="gearbox", drill="Drill D"),
    ]
    db.add_all(assets)
    db.commit()

    # 1 vibration sensor per gearbox
    sensors = [
        Sensor(id=f"sensor-{a.id}", asset_id=a.id, sensor_type="vibration")
        for a in assets
    ]
    db.add_all(sensors)
    db.commit()

    # Sensor profiles matching your mock data health levels
    profiles = {
        "drill-a": {"rms": (7.0, 9.0),   "temp": (70.0, 74.0), "current": (390.0, 430.0)},
        "drill-b": {"rms": (3.0, 5.5),   "temp": (60.0, 67.0), "current": (300.0, 360.0)},
        "drill-c": {"rms": (9.0, 12.0),  "temp": (76.0, 82.0), "current": (490.0, 560.0)},
        "drill-d": {"rms": (5.5, 7.5),   "temp": (64.0, 70.0), "current": (340.0, 400.0)},
    }

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

    db.close()
    print(f"Seeded {len(assets)} assets, {len(sensors)} sensors, {len(records)} feature records, {len(events)} maintenance events.")

if __name__ == "__main__":
    seed()



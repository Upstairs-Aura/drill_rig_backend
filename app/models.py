from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from app.database import Base
from datetime import datetime

class Asset(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True)
    name = Column(String)
    asset_type = Column(String)
    drill = Column(String)

class Sensor(Base):
    __tablename__ = "sensors"
    id = Column(String, primary_key=True)
    asset_id = Column(String, ForeignKey("assets.id"))
    sensor_type = Column(String)

class FeatureRecord(Base):
    __tablename__ = "feature_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(String, ForeignKey("assets.id"))
    sensor_id = Column(String, ForeignKey("sensors.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    rms = Column(Float)
    peak = Column(Float)
    crest_factor = Column(Float)
    kurtosis = Column(Float)
    skewness = Column(Float)
    dominant_frequency = Column(Float)
    temperature = Column(Float)
    current = Column(Float)

class MaintenanceEvent(Base):
    __tablename__ = "maintenance_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(String, ForeignKey("assets.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String)
    notes = Column(String)

class PredictionRecord(Base):
    __tablename__ = "prediction_records"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    asset_id    = Column(String, ForeignKey("assets.id"))
    timestamp   = Column(DateTime, default=datetime.utcnow)
    model_source = Column(String)    # "isolation_forest" or "random_forest"
    anomaly     = Column(Integer)    # 1 = anomaly, 0 = normal
    risk_score  = Column(Float)      # 0.0 – 1.0
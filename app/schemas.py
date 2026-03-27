from pydantic import BaseModel
from datetime import datetime
from typing import List

class FeaturePayload(BaseModel):
    asset_id: str
    sensor_id: str
    timestamp: datetime
    rms: float
    peak: float
    crest_factor: float
    kurtosis: float
    skewness: float
    dominant_frequency: float
    temperature: float
    current: float

class IngestRequest(BaseModel):
    records: List[FeaturePayload]
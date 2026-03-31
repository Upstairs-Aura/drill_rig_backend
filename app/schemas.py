from pydantic import BaseModel
from datetime import datetime
from typing import List, Literal

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

class SensorEntry(BaseModel):
    sensor_id:   str
    sensor_type: Literal["vibration", "temperature", "current"]

class SamplingConfig(BaseModel):
    sampling_rate_hz:   float   # e.g. 1600.0
    burst_duration_s:   float   # e.g. 1.0
    samples_per_burst:  int     # derived but validated: must equal rate × duration

class FilterConfig(BaseModel):
    filter_order:      int    # Butterworth order, e.g. 4
    lowcut_hz:         float
    highcut_hz:        float
    window_length:     int    # FFT window in samples, e.g. 256 or 512

class AlertThresholds(BaseModel):
    vibration_warn_mms:     float
    vibration_critical_mms: float
    temperature_warn_c:     float
    temperature_critical_c: float
    current_warn_a:         float
    current_critical_a:     float

class ConfigPayload(BaseModel):
    sensors:    List[SensorEntry]
    sampling:   SamplingConfig
    filter:     FilterConfig
    thresholds: AlertThresholds

class ConfigSubmitRequest(BaseModel):
    asset_id: str
    config:   ConfigPayload
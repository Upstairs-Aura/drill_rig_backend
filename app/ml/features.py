import numpy as np

FEATURE_COLUMNS = [
    "rms", "peak", "crest_factor",
    "kurtosis", "skewness",
    "dominant_frequency", "temperature", "current"
]

def record_to_features(record):
    """Single FeatureRecord ORM object → numpy array for inference."""
    return np.array([[
        record.rms,
        record.peak,
        record.crest_factor,
        record.kurtosis,
        record.skewness,
        record.dominant_frequency,
        record.temperature,
        record.current,
    ]])

def records_to_dataframe(records):
    """List of FeatureRecord objects → pandas DataFrame for training."""
    import pandas as pd
    return pd.DataFrame([
        {col: getattr(r, col) for col in FEATURE_COLUMNS}
        for r in records
    ])
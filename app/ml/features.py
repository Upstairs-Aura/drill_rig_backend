import numpy as np

FEATURE_COLUMNS = [
    "rms", "peak", "crest_factor",
    "kurtosis", "skewness",
    "dominant_frequency", "bpfo_ratio", "bpfi_ratio",
    "temperature", "current"
]

def record_to_features(record):
    """Single FeatureRecord ORM object is to numpy array for inference."""
    return np.array([[
        record.rms,
        record.peak,
        record.crest_factor,
        record.kurtosis,
        record.skewness,
        record.dominant_frequency,
        getattr(record, 'bpfo_ratio', 0.0) or 0.0,
        getattr(record, 'bpfi_ratio', 0.0) or 0.0,
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
# nasa_loader.py
import os
import numpy as np
import pandas as pd
from scipy.stats import kurtosis, skew
from scipy.signal import welch, butter, filtfilt
from datetime import datetime

SAMPLING_RATE = 20000   # 20 kHz
# Rexnord ZA-2115 at 2000 RPM — actual bearing fault frequencies
BPFO_HZ = 236.4         # outer race fault frequency
BPFI_HZ = 296.9         # inner race fault frequency

def bandpass_filter(signal, lowcut=100, highcut=500, fs=SAMPLING_RATE, order=4):
    nyq = fs / 2
    b, a = butter(order, [lowcut / nyq, highcut / nyq], btype='band')
    return filtfilt(b, a, signal)

def extract_features(signal: np.ndarray) -> dict:
    sig = bandpass_filter(signal)
    rms = float(np.sqrt(np.mean(sig**2)))
    peak = float(np.max(np.abs(sig)))

    freqs, psd = welch(sig, fs=SAMPLING_RATE, nperseg=1024)
    dom_idx = np.argmax(psd)

    # BPFO/BPFI amplitude ratio vs RMS — matches your existing schema
    def amp_at(target_hz, bandwidth=5):
        mask = (freqs >= target_hz - bandwidth) & (freqs <= target_hz + bandwidth)
        return float(np.sqrt(np.max(psd[mask]))) if mask.any() else 0.0

    bpfo_amp = amp_at(BPFO_HZ)
    bpfi_amp = amp_at(BPFI_HZ)

    return {
        "rms":                rms,
        "peak":               peak,
        "crest_factor":       peak / rms if rms > 0 else 0.0,
        "kurtosis":           float(kurtosis(sig)),
        "skewness":           float(skew(sig)),
        "dominant_frequency": float(freqs[dom_idx]),
        "bpfo_ratio":         bpfo_amp / rms if rms > 0 else 0.0,
        "bpfi_ratio":         bpfi_amp / rms if rms > 0 else 0.0,
        # NASA dataset has no temperature/current — use 0.0 as sentinel
        "temperature":        0.0,
        "current":            0.0,
    }

def parse_filename_to_dt(filename: str) -> datetime:
    """e.g. '2003.10.22.12.06.24' → datetime"""
    parts = filename.replace(".", "-").split("-")
    try:
        return datetime(*[int(p) for p in parts[:6]])
    except Exception:
        return datetime.utcnow()

def load_test_set(folder: str, channel: int = 0) -> pd.DataFrame:
    rows = []
    for fname in sorted(os.listdir(folder)):
        fpath = os.path.join(folder, fname)
        try:
            data = np.loadtxt(fpath)
        except Exception:
            continue

        if data.ndim == 1:
            signal = data
        else:
            signal = data[:, channel]

        features = extract_features(signal)
        features["timestamp"] = parse_filename_to_dt(fname)  # ← must be inside the dict before append
        rows.append(features)

    if not rows:
        print(f"  [WARNING] No files loaded from {folder}")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.sort_values("timestamp").reset_index(drop=True)  # now timestamp column exists
    print(f"Loaded {len(df)} snapshots from {folder} (channel {channel})")
    return df
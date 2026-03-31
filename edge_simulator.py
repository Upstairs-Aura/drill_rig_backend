import numpy as np
from scipy.signal import butter, filtfilt
from scipy.stats import kurtosis, skew
import requests
from datetime import datetime, timezone

API_URL = "http://localhost:8000"
SAMPLING_RATE_HZ = 1600
BURST_DURATION_S = 1.0
WINDOW_LENGTH    = 512
FILTER_ORDER     = 4
LOWCUT_HZ        = 10.0
HIGHCUT_HZ       = 500.0

ASSETS = [
    {"asset_id": "drill-a", "sensor_id": "sensor-drill-a", "fault_level": 0.4},
    {"asset_id": "drill-b", "sensor_id": "sensor-drill-b", "fault_level": 0.1},
    {"asset_id": "drill-c", "sensor_id": "sensor-drill-c", "fault_level": 0.9},
    {"asset_id": "drill-d", "sensor_id": "sensor-drill-d", "fault_level": 0.3},
]


def generate_raw_signal(fault_level: float) -> np.ndarray:
    """Synthetic vibration signal: base rotation + harmonics + fault impulses + noise."""
    n_samples = int(SAMPLING_RATE_HZ * BURST_DURATION_S)
    t = np.linspace(0, BURST_DURATION_S, n_samples, endpoint=False)

    # Shaft rotation at 30 Hz + harmonics
    signal = (
            np.sin(2 * np.pi * 30 * t) +
            0.4 * np.sin(2 * np.pi * 60 * t) +
            0.2 * np.sin(2 * np.pi * 90 * t)
    )

    # Fault impulses at bearing pass frequency outer race (BPFO ≈ 105 Hz)
    bpfo = 105.0
    fault_impulses = fault_level * np.sin(2 * np.pi * bpfo * t) * (
            1 + 0.5 * np.sin(2 * np.pi * 30 * t)
    )
    signal += fault_impulses

    # Gaussian noise
    signal += np.random.normal(0, 0.05 + fault_level * 0.1, n_samples)
    return signal


def apply_butterworth_filter(signal: np.ndarray) -> np.ndarray:
    """4th-order Butterworth bandpass filter, 10–500 Hz."""
    nyquist = SAMPLING_RATE_HZ / 2.0
    low  = LOWCUT_HZ  / nyquist
    high = HIGHCUT_HZ / nyquist
    b, a = butter(FILTER_ORDER, [low, high], btype="band")
    return filtfilt(b, a, signal)


def extract_features(filtered: np.ndarray) -> dict:
    """Compute time-domain and frequency-domain features from filtered signal."""
    # Time-domain
    rms          = float(np.sqrt(np.mean(filtered ** 2)))
    peak         = float(np.max(np.abs(filtered)))
    crest_factor = float(peak / rms) if rms > 0 else 0.0
    kurt         = float(kurtosis(filtered, fisher=False))   # Pearson kurtosis
    skewness     = float(skew(filtered))

    # Frequency-domain: FFT on first window
    window   = filtered[:WINDOW_LENGTH] * np.hanning(WINDOW_LENGTH)
    spectrum = np.abs(np.fft.rfft(window))
    freqs    = np.fft.rfftfreq(WINDOW_LENGTH, d=1.0 / SAMPLING_RATE_HZ)
    dominant_frequency = float(freqs[np.argmax(spectrum)])

    return {
        "rms":                rms,
        "peak":               peak,
        "crest_factor":       crest_factor,
        "kurtosis":           kurt,
        "skewness":           skewness,
        "dominant_frequency": dominant_frequency,
    }


def simulate_asset(asset: dict) -> dict:
    """Full pipeline for one asset: generate → filter → extract → package."""
    raw      = generate_raw_signal(asset["fault_level"])
    filtered = apply_butterworth_filter(raw)
    features = extract_features(filtered)

    # Temperature and current scale with fault level
    temperature = round(60.0 + asset["fault_level"] * 25.0 + np.random.uniform(-1, 1), 2)
    current     = round(300.0 + asset["fault_level"] * 250.0 + np.random.uniform(-5, 5), 2)

    return {
        "asset_id":  asset["asset_id"],
        "sensor_id": asset["sensor_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **features,
        "temperature": temperature,
        "current":     current,
    }


def run():
    records = [simulate_asset(a) for a in ASSETS]

    print("--- Simulated feature vectors ---")
    for r in records:
        print(
            f"  {r['asset_id']:10s}  rms={r['rms']:.3f}  "
            f"kurtosis={r['kurtosis']:.2f}  dom_freq={r['dominant_frequency']:.1f} Hz  "
            f"temp={r['temperature']}°C  current={r['current']}A"
        )

    payload = {"records": records}
    try:
        resp = requests.post(f"{API_URL}/api/v1/ingest/", json=payload, timeout=5)
        resp.raise_for_status()
        print(f"\nIngest response: {resp.json()}")
    except requests.exceptions.ConnectionError:
        print(f"\nCould not reach API at {API_URL} — is the server running?")
    except requests.exceptions.HTTPError as e:
        print(f"\nAPI error {resp.status_code}: {resp.text}")


if __name__ == "__main__":
    run()

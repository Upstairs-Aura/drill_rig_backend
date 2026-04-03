# ─── Edge / sampling parameters ───────────────────────────────────────────────
SAMPLING_RATE_HZ   = 20000.0 # was 1600
BURST_DURATION_S   = 1.0
SAMPLES_PER_BURST  = 20480 # was 20kHz x 1s

# ─── Signal processing ────────────────────────────────────────────────────────
FILTER_ORDER   = 4
LOWCUT_HZ      = 10.0
HIGHCUT_HZ     = 500.0
WINDOW_LENGTH  = 512   # must be power of 2

# ─── Bearing fault frequencies ────────────────────────────────────────────────
BPFO_HZ = 236.4   # bearing pass frequency outer race
BPFI_HZ = 296.9   # bearing pass frequency inner race

# ─── Alert thresholds ─────────────────────────────────────────────────────────
VIBRATION_WARN_MMS      = 6.0
VIBRATION_CRITICAL_MMS  = 9.0
TEMPERATURE_WARN_C      = 70.0
TEMPERATURE_CRITICAL_C  = 78.0
CURRENT_WARN_A          = 400.0
CURRENT_CRITICAL_A      = 500.0

# ─── Assets and sensors ───────────────────────────────────────────────────────
ASSETS = [
    {
        # Set 1, Ch 5 (0-indexed col 4) — Bearing 3 x-axis, inner race failure
        "asset_id":    "set1-bearing3-x",
        "name":        "Set1 Bearing 3 (x-axis)",
        "drill":       "Test Set 1",
        "sensor_id":   "s-1-b3-x",
        "sensor_type": "vibration",
        "fault_level": 0.6,
    },
    {
        # Set 1, Ch 6 (0-indexed col 5) — Bearing 3 y-axis, inner race failure
        "asset_id":    "set1-bearing3-y",
        "name":        "Set1 Bearing 3 (y-axis)",
        "drill":       "Test Set 1",
        "sensor_id":   "s-1-b3-y",
        "sensor_type": "vibration",
        "fault_level": 0.7,
    },
    {
        # Set 2, Ch 1 (0-indexed col 0) — Bearing 1, outer race failure
        "asset_id":    "set2-bearing1",
        "name":        "Set2 Bearing 1",
        "drill":       "Test Set 2",
        "sensor_id":   "s-2-b1",
        "sensor_type": "vibration",
        "fault_level": 0.9,
    },
    {
        # Set 3, Ch 3 (0-indexed col 2) — Bearing 3, outer race failure
        "asset_id":    "set3-bearing3",
        "name":        "Set3 Bearing 3",
        "drill":       "Test Set 3",
        "sensor_id":   "s-3-b3",
        "sensor_type": "vibration",
        "fault_level": 0.5,
    },
]

# ─── Seed profiles (simulated health levels per asset) ────────────────────────
SEED_PROFILES = {
    "set1-bearing3-x": {"rms": (5.0, 8.0),  "temp": (60.0, 70.0), "current": (300.0, 380.0)},
    "set1-bearing3-y": {"rms": (6.0, 9.0),  "temp": (62.0, 72.0), "current": (320.0, 400.0)},
    "set2-bearing1":   {"rms": (9.0, 13.0), "temp": (74.0, 82.0), "current": (460.0, 540.0)},
    "set3-bearing3":   {"rms": (4.0, 7.0),  "temp": (58.0, 68.0), "current": (280.0, 360.0)},
}
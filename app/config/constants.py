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
        "asset_id":    "bearing-1-ch3",
        "name":        "Test1 Bearing 3",
        "drill":       "Test 1",
        "sensor_id":   "s-1-3",
        "sensor_type": "vibration",
        "fault_level": 0.6,
    },
    {
        "asset_id":    "bearing-1-ch4",
        "name":        "Test1 Bearing 4",
        "drill":       "Test 1",
        "sensor_id":   "s-1-4",
        "sensor_type": "vibration",
        "fault_level": 0.7,
    },
    {
        "asset_id":    "bearing-2-ch1",
        "name":        "Test2 Bearing 1",
        "drill":       "Test 2",
        "sensor_id":   "s-2-1",
        "sensor_type": "vibration",
        "fault_level": 0.9,
    },
    {
        "asset_id":    "bearing-3-ch3",
        "name":        "Test3 Bearing 3",
        "drill":       "Test 3",
        "sensor_id":   "s-3-3",
        "sensor_type": "vibration",
        "fault_level": 0.5,
    },
]

# ─── Seed profiles (simulated health levels per asset) ────────────────────────
SEED_PROFILES = {
    "bearing-1-ch3": {"rms": (5.0, 8.0),  "temp": (60.0, 70.0), "current": (300.0, 380.0)},
    "bearing-1-ch4": {"rms": (6.0, 9.0),  "temp": (62.0, 72.0), "current": (320.0, 400.0)},
    "bearing-2-ch1": {"rms": (9.0, 13.0), "temp": (74.0, 82.0), "current": (460.0, 540.0)},
    "bearing-3-ch3": {"rms": (4.0, 7.0),  "temp": (58.0, 68.0), "current": (280.0, 360.0)},
}
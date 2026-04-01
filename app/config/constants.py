# ─── Edge / sampling parameters ───────────────────────────────────────────────
SAMPLING_RATE_HZ   = 1600.0
BURST_DURATION_S   = 1.0
SAMPLES_PER_BURST  = int(SAMPLING_RATE_HZ * BURST_DURATION_S)  # 1600

# ─── Signal processing ────────────────────────────────────────────────────────
FILTER_ORDER   = 4
LOWCUT_HZ      = 10.0
HIGHCUT_HZ     = 500.0
WINDOW_LENGTH  = 512   # must be power of 2

# ─── Bearing fault frequencies ────────────────────────────────────────────────
BPFO_HZ = 105.0   # bearing pass frequency outer race
BPFI_HZ = 155.0   # bearing pass frequency inner race

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
        "asset_id":  "drill-a",
        "name":      "Gearbox A",
        "drill":     "Drill A",
        "sensor_id": "sensor-drill-a",
        "sensor_type": "vibration",
        "fault_level": 0.4,
    },
    {
        "asset_id":  "drill-b",
        "name":      "Gearbox B",
        "drill":     "Drill B",
        "sensor_id": "sensor-drill-b",
        "sensor_type": "vibration",
        "fault_level": 0.1,
    },
    {
        "asset_id":  "drill-c",
        "name":      "Gearbox C",
        "drill":     "Drill C",
        "sensor_id": "sensor-drill-c",
        "sensor_type": "vibration",
        "fault_level": 0.9,
    },
    {
        "asset_id":  "drill-d",
        "name":      "Gearbox D",
        "drill":     "Drill D",
        "sensor_id": "sensor-drill-d",
        "sensor_type": "vibration",
        "fault_level": 0.3,
    },
]

# ─── Seed profiles (simulated health levels per asset) ────────────────────────
SEED_PROFILES = {
    "drill-a": {"rms": (7.0, 9.0),  "temp": (70.0, 74.0), "current": (390.0, 430.0)},
    "drill-b": {"rms": (3.0, 5.5),  "temp": (60.0, 67.0), "current": (300.0, 360.0)},
    "drill-c": {"rms": (9.0, 12.0), "temp": (76.0, 82.0), "current": (490.0, 560.0)},
    "drill-d": {"rms": (5.5, 7.5),  "temp": (64.0, 70.0), "current": (340.0, 400.0)},
}
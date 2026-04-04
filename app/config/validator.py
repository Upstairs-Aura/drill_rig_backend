from app.schemas import ConfigPayload

MAX_DATA_RATE_HZ = 100000   # hardware output limit

def validate_config(payload: ConfigPayload) -> list[str]:
    errors = []
    s = payload.sampling
    f = payload.filter

    # Nyquist: sampling rate must be at least 2× the highcut frequency
    if s.sampling_rate_hz < 2 * f.highcut_hz:
        errors.append(
            f"Nyquist violation: sampling rate {s.sampling_rate_hz}Hz "
            f"is less than 2× highcut {f.highcut_hz}Hz"
        )

    # Hardware output data rate limit
    total_rate = s.sampling_rate_hz * len(payload.sensors)
    if total_rate > MAX_DATA_RATE_HZ:
        errors.append(
            f"Total data rate {total_rate}Hz exceeds hardware limit {MAX_DATA_RATE_HZ}Hz"
        )

    # Burst duration: samples_per_burst must equal rate × duration
    expected = int(s.sampling_rate_hz * s.burst_duration_s)
    if s.samples_per_burst != expected:
        errors.append(
            f"samples_per_burst {s.samples_per_burst} does not match "
            f"sampling_rate × burst_duration = {expected}"
        )

    # Sensor-type rules: BPFO/BPFI features only valid for vibration sensors
    sensor_types = {se.sensor_type for se in payload.sensors}
    if "vibration" not in sensor_types and f.lowcut_hz > 0:
        errors.append(
            "Bandpass filter is configured but no vibration sensor is present. "
            "BPFO/BPFI features require a vibration sensor."
        )

    # Window length must be a power of 2 for FFT efficiency
    wl = f.window_length
    if wl < 2 or (wl & (wl - 1)) != 0:
        errors.append(
            f"window_length {wl} must be a power of 2 (e.g. 256, 512, 1024)"
        )

    return errors
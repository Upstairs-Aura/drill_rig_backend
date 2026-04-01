"""
End-to-end pipeline runner.
Runs: simulate then filter, then extract, then POST ingest, then trigger predict, then verify dashboard.
"""
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
from edge_simulator import ASSETS, simulate_asset

API_URL = "http://localhost:8000"
PASS = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"

def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    print(f"  [{status} ] {label}" + (f" — {detail}" if detail else ""))
    return condition

def run_pipeline():
    print("\n========================================")
    print("  Drill Rig — End-to-End Pipeline Runner")
    print("========================================\n")

    all_passed = True

    # ── Step 1: Health check ──────────────────────────────────────────────────
    print("Step 1 — API health check")
    try:
        r = requests.get(f"{API_URL}/", timeout=5)
        ok = check("API is reachable", r.status_code == 200, r.json().get("message", ""))
    except Exception as e:
        check("API is reachable", False, str(e))
        print("\n  Cannot reach API. Is `uvicorn app.main:app` running?\n")
        sys.exit(1)

    # ── Step 2: Simulate + ingest ─────────────────────────────────────────────
    print("\nStep 2 — Edge simulation → feature extraction → ingest")
    records = []
    for asset in ASSETS:
        rec = simulate_asset(asset)
        records.append(rec)
        print(f"  Simulated {rec['asset_id']:10s}  "
              f"rms={rec['rms']:.3f}  bpfo={rec['bpfo_ratio']:.4f}  "
              f"dom_freq={rec['dominant_frequency']:.1f}Hz")

    payload = {"records": records}
    try:
        r = requests.post(f"{API_URL}/api/v1/ingest/", json=payload, timeout=10)
        inserted = r.json().get("inserted", 0) if r.ok else 0
        ok = check("Ingest accepted all records", r.ok and inserted == len(ASSETS),
                   f"{inserted}/{len(ASSETS)} inserted" if r.ok else r.text)
        all_passed = all_passed and ok
    except Exception as e:
        check("Ingest endpoint reachable", False, str(e))
        all_passed = False

    # ── Step 3: Predict for each asset ────────────────────────────────────────
    print("\nStep 3 — Trigger prediction for each asset")
    predict_results = {}
    for asset in ASSETS:
        asset_id = asset["asset_id"]
        try:
            r = requests.get(f"{API_URL}/api/v1/assets/{asset_id}/predict", timeout=10)
            if r.ok:
                result = r.json()
                predict_results[asset_id] = result
                source = result.get("source", "unknown")
                risk   = result.get("risk_score", 0)
                anomaly = result.get("anomaly", False)
                ok = check(
                    f"Prediction for {asset_id}",
                    source != "no_model",
                    f"source={source}  risk={risk:.3f}  anomaly={anomaly}"
                )
                all_passed = all_passed and ok
            else:
                check(f"Prediction for {asset_id}", False, f"HTTP {r.status_code}")
                all_passed = False
        except Exception as e:
            check(f"Prediction for {asset_id}", False, str(e))
            all_passed = False

    # ── Step 4: Verify dashboard endpoints respond ────────────────────────────
    print("\nStep 4 — Verify dashboard endpoints for each asset")
    endpoints = ["metrics/latest", "alerts", "health-history", "recommendations"]
    for asset in ASSETS:
        asset_id = asset["asset_id"]
        for ep in endpoints:
            try:
                r = requests.get(f"{API_URL}/api/v1/assets/{asset_id}/{ep}", timeout=5)
                ok = check(f"{asset_id}/{ep}", r.ok, f"HTTP {r.status_code}")
                all_passed = all_passed and ok
            except Exception as e:
                check(f"{asset_id}/{ep}", False, str(e))
                all_passed = False

    # ── Step 5: Summary ───────────────────────────────────────────────────────
    print("\n========================================")
    if all_passed:
        print("  \033[92mAll checks passed — pipeline is healthy.\033[0m")
        print("  Dashboard at: http://localhost:3000")
    else:
        print("  \033[91mSome checks failed — see above.\033[0m")
    print("========================================\n")

    # Print risk score summary table
    if predict_results:
        print("  Risk score summary:")
        print(f"  {'Asset':<12} {'Source':<20} {'Risk':>6} {'Anomaly':>8}")
        print("  " + "-" * 50)
        for asset_id, res in predict_results.items():
            print(f"  {asset_id:<12} {res.get('source','?'):<20} "
                  f"{res.get('risk_score',0):>6.3f} {str(res.get('anomaly','?')):>8}")
        print()

if __name__ == "__main__":
    run_pipeline()
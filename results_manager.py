import os
import json
from datetime import datetime
import pandas as pd


RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def save_results(results: list[dict], fmt: str = "csv") -> str:
    """Save scan results with timestamp. Returns filepath."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"scan_{timestamp}.{fmt}"
    filepath = os.path.join(RESULTS_DIR, filename)

    # Flatten fundamentals dict for export
    flat = []
    for r in results:
        row = {k: v for k, v in r.items() if k not in ("fundamentals", "explanation")}
        fund = r.get("fundamentals", {})
        for fk, fv in fund.items():
            row[f"fund_{fk}"] = fv
        row["explanation"] = r.get("explanation", "")
        flat.append(row)

    if fmt == "csv":
        pd.DataFrame(flat).to_csv(filepath, index=False)
    else:
        with open(filepath, "w") as f:
            json.dump(flat, f, indent=2, default=str)

    return filepath


def load_scan_history() -> list[dict]:
    """List saved scans with metadata."""
    if not os.path.exists(RESULTS_DIR):
        return []

    scans = []
    for fname in sorted(os.listdir(RESULTS_DIR), reverse=True):
        if not (fname.endswith(".csv") or fname.endswith(".json")):
            continue
        fpath = os.path.join(RESULTS_DIR, fname)
        size = os.path.getsize(fpath)
        # Extract timestamp from filename
        parts = fname.replace("scan_", "").rsplit(".", 1)[0]
        scans.append({
            "filename": fname,
            "filepath": fpath,
            "timestamp": parts.replace("_", " "),
            "size_kb": round(size / 1024, 1),
        })

    return scans


def get_previous_symbols() -> set:
    """Get symbols from the most recent saved scan for comparison."""
    history = load_scan_history()
    if not history:
        return set()

    latest = history[0]
    try:
        if latest["filename"].endswith(".csv"):
            df = pd.read_csv(latest["filepath"])
            return set(df["symbol"].tolist())
        else:
            with open(latest["filepath"]) as f:
                data = json.load(f)
            return {r["symbol"] for r in data}
    except Exception:
        return set()

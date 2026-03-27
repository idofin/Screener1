"""
ReversalIQ Daily Auto-Scanner.
Runs standalone (no Streamlit needed). Works locally and in GitHub Actions.

Usage:
    python daily_scan.py                          # scan only, no alerts
    python daily_scan.py --telegram               # scan + Telegram alerts (uses env vars)
    python daily_scan.py --count 1000             # scan top 1000 stocks

Environment variables for Telegram:
    TELEGRAM_BOT_TOKEN=your_bot_token
    TELEGRAM_CHAT_ID=your_chat_id
"""
import sys
import os
import time
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
os.environ["STREAMLIT_RUNTIME"] = "0"

from config import (
    DEFAULT_RSI_THRESHOLD, DEFAULT_SMA_PROXIMITY_PCT, DEFAULT_PULLBACK_PCT,
    DEFAULT_CONFIRMATION_CANDLES, DEFAULT_LOOKBACK_DAYS,
    BATCH_SIZE, BATCH_DELAY,
    SP500_FALLBACK, NASDAQ100_FALLBACK,
)
from data_fetcher import fetch_universe, fetch_price_data


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def fetch_all_largecap(target_count=3000):
    log(f"Fetching up to {target_count} large-cap US stocks...")
    symbols = fetch_universe("All US Large-Cap ($1B+)", target_count)
    log(f"  Found {len(symbols)} US stocks")
    return symbols


def download_prices(symbols, period="1y"):
    log(f"Downloading price data for {len(symbols)} stocks...")
    price_data = fetch_price_data(tuple(symbols), period=period)
    log(f"  Total: {len(price_data)} stocks with sufficient data")
    return price_data


def screen_stocks(price_data):
    from screener_engine import technical_screen, fundamental_filter

    log("Running technical screen...")
    candidates = technical_screen(
        price_data,
        rsi_threshold=DEFAULT_RSI_THRESHOLD,
        sma_proximity_pct=DEFAULT_SMA_PROXIMITY_PCT,
        pullback_pct=DEFAULT_PULLBACK_PCT,
        confirmation_candles=DEFAULT_CONFIRMATION_CANDLES,
        lookback_days=DEFAULT_LOOKBACK_DAYS,
    )
    log(f"  {len(candidates)} technical candidates")

    log("Running fundamental filter...")
    results = fundamental_filter(candidates)
    log(f"  {len(results)} passed fundamental filter")

    return results


def get_previous_symbols() -> set:
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    if not os.path.exists(results_dir):
        return set()

    daily_files = sorted(
        [f for f in os.listdir(results_dir)
         if f.startswith("daily_scan_") and f.endswith(".json")],
        reverse=True,
    )
    if not daily_files:
        return set()

    try:
        with open(os.path.join(results_dir, daily_files[0])) as f:
            data = json.load(f)
        return {r["symbol"] for r in data}
    except Exception:
        return set()


def save_results(results):
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filepath = os.path.join(results_dir, f"daily_scan_{timestamp}.json")

    flat = []
    for r in results:
        row = {k: v for k, v in r.items() if k not in ("fundamentals", "explanation")}
        fund = r.get("fundamentals", {})
        for fk, fv in fund.items():
            row[f"fund_{fk}"] = fv
        row["explanation"] = r.get("explanation", "")
        flat.append(row)

    with open(filepath, "w") as f:
        json.dump(flat, f, indent=2, default=str)

    log(f"Results saved to {filepath}")
    return filepath


def send_telegram_alert(results):
    """Send alerts via Telegram Bot API."""
    from telegram_alerts import send_alerts
    log("Sending Telegram alert...")
    ok = send_alerts(results)
    if ok:
        log("  Telegram alert sent!")
    else:
        log("  Telegram send failed — check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")


def main():
    parser = argparse.ArgumentParser(description="ReversalIQ Daily Scanner")
    parser.add_argument("--telegram", action="store_true", help="Send alerts via Telegram")
    parser.add_argument("--count", type=int, default=3000, help="Number of stocks to scan")
    args = parser.parse_args()

    log("=" * 50)
    log("ReversalIQ Daily Scan")
    log("=" * 50)

    # 1. Fetch universe
    symbols = fetch_all_largecap(args.count)

    # 2. Download prices
    price_data = download_prices(symbols)

    # 3. Screen
    results = screen_stocks(price_data)

    # 4. Compare with previous scan
    prev_symbols = get_previous_symbols()
    new_signals = [r for r in results if r["symbol"] not in prev_symbols]
    returning = [r for r in results if r["symbol"] in prev_symbols]

    # 5. Print summary
    log("")
    log(f"{'=' * 50}")
    log(f"SCAN COMPLETE — {len(results)} total signals")
    log(f"  NEW: {len(new_signals)}  |  Returning: {len(returning)}")
    log(f"{'=' * 50}")

    if new_signals:
        log("NEW signals:")
        for r in new_signals:
            fund = r.get("fundamentals", {})
            name = fund.get("longName", r["symbol"])
            log(f"  + {r['symbol']:6s}  {name:30s}  RSI:{r['rsi_at_signal']:5.1f}  "
                f"Pullback:{r['pullback_pct']:5.1f}%  SMA-{r['sma_period']}")

    if returning:
        log("Still active from previous scan:")
        for r in returning:
            log(f"  = {r['symbol']:6s}")

    # 6. Save ALL results
    if results:
        save_results(results)

    # 7. Telegram — only send NEW signals
    if args.telegram and new_signals:
        send_telegram_alert(new_signals)
    elif args.telegram and not new_signals and results:
        log("No new signals since last scan, skipping Telegram")
    elif args.telegram and not results:
        log("No signals found, skipping Telegram")

    log("Done!")


if __name__ == "__main__":
    main()

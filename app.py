import sys
import os
import textwrap
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from config import (
    DEFAULT_RSI_THRESHOLD, DEFAULT_SMA_PROXIMITY_PCT, DEFAULT_PULLBACK_PCT,
    DEFAULT_CONFIRMATION_CANDLES, DEFAULT_LOOKBACK_DAYS, UNIVERSE_OPTIONS,
)
from data_fetcher import fetch_universe, fetch_price_data
from screener_engine import technical_screen, fundamental_filter
from results_manager import save_results, load_scan_history, get_previous_symbols
from notifications import notify_new_signals
from telegram_alerts import send_alerts as send_telegram
from indicators import compute_sma


def _fmt(val, fmt=".1f", multiply=1, prefix="", suffix=""):
    """Safely format a numeric value that might be a string or None."""
    if val is None:
        return "N/A"
    try:
        return f"{prefix}{float(val) * multiply:{fmt}}{suffix}"
    except (ValueError, TypeError):
        return str(val)


# ── Daily scan scheduler (runs inside the Streamlit process) ──
import json as _json
import threading

PYTHON_PATH = sys.executable
_SCHEDULE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "daily_schedule.json")
_SCAN_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "daily_scan_log.txt")


def _load_schedule() -> dict:
    """Load saved schedule config."""
    try:
        with open(_SCHEDULE_FILE) as f:
            return _json.load(f)
    except Exception:
        return {}


def _save_schedule(config: dict):
    """Persist schedule config to disk."""
    os.makedirs(os.path.dirname(_SCHEDULE_FILE), exist_ok=True)
    with open(_SCHEDULE_FILE, "w") as f:
        _json.dump(config, f, indent=2)


def _is_daily_scan_active() -> bool:
    config = _load_schedule()
    return config.get("enabled", False)


def _get_schedule_status() -> str:
    config = _load_schedule()
    if not config.get("enabled"):
        return ""
    time_str = config.get("time", "18:30")
    size = config.get("scan_size", 3000)
    phone = config.get("phone", "")
    last = config.get("last_run", "Never")
    status = f"Daily at {time_str} | {size} stocks"
    if phone:
        status += " | WhatsApp on"
    status += f"\nLast run: {last}"
    return status


def _run_daily_scan_background(scan_size: int, phone: str = ""):
    """
    Run the full scan pipeline in a background thread.
    This is the same logic as daily_scan.py but runs inside the app process.
    """
    import json as json_mod
    from data_fetcher import fetch_universe, fetch_price_data
    from screener_engine import technical_screen, fundamental_filter
    from telegram_alerts import send_alerts as _send_tg
    from results_manager import get_previous_symbols

    log_lines = []
    def log(msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        log_lines.append(line)
        print(line)

    try:
        log(f"Daily scan started — {scan_size} stocks")

        # 1. Fetch universe
        symbols = fetch_universe("All US Large-Cap ($1B+)", scan_size)
        log(f"Fetched {len(symbols)} US stocks")

        # 2. Download prices
        price_data = fetch_price_data(tuple(symbols), period="1y")
        log(f"Downloaded data for {len(price_data)} stocks")

        # 3. Technical screen
        candidates = technical_screen(
            price_data,
            rsi_threshold=DEFAULT_RSI_THRESHOLD,
            sma_proximity_pct=DEFAULT_SMA_PROXIMITY_PCT,
            pullback_pct=DEFAULT_PULLBACK_PCT,
            confirmation_candles=DEFAULT_CONFIRMATION_CANDLES,
            lookback_days=DEFAULT_LOOKBACK_DAYS,
        )
        log(f"{len(candidates)} technical candidates")

        # 4. Fundamental filter
        results = fundamental_filter(candidates)
        log(f"{len(results)} passed fundamental filter")

        # 5. Compare with previous scan — only send NEW signals
        prev_symbols = get_previous_symbols()
        new_signals = [r for r in results if r["symbol"] not in prev_symbols]
        log(f"{len(new_signals)} NEW signals, {len(results) - len(new_signals)} returning")

        # 6. Save results
        if results:
            from results_manager import save_results as save_res
            save_res(results, fmt="json")
            log("Results saved")

        # 7. Telegram — only new signals
        sched_config = _load_schedule()
        tg_tok = sched_config.get("tg_token", "")
        tg_cid = sched_config.get("tg_chat_id", "")
        if tg_tok and tg_cid and new_signals:
            log(f"Sending {len(new_signals)} new signal(s) to Telegram...")
            _send_tg(new_signals, tg_tok, tg_cid)
            log("Telegram sent")
        elif tg_tok and tg_cid and not new_signals:
            log("No new signals — Telegram skipped")

        # Update last run time
        config = _load_schedule()
        config["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        config["last_results"] = len(results)
        config["last_new"] = len(new_signals)
        _save_schedule(config)

        log("Daily scan complete!")

    except Exception as e:
        log(f"Daily scan ERROR: {e}")

    # Write log
    try:
        os.makedirs(os.path.dirname(_SCAN_LOG_FILE), exist_ok=True)
        with open(_SCAN_LOG_FILE, "w") as f:
            f.write("\n".join(log_lines))
    except Exception:
        pass


def _start_scheduler():
    """Start a background thread that checks every 30s if it's time to scan."""
    import time as _time

    def scheduler_loop():
        last_triggered_date = None
        while True:
            try:
                config = _load_schedule()
                if config.get("enabled"):
                    target_time = config.get("time", "18:30")
                    now = datetime.now()
                    current_time = now.strftime("%H:%M")
                    current_date = now.strftime("%Y-%m-%d")

                    # Trigger once per day at the scheduled time
                    if current_time == target_time and current_date != last_triggered_date:
                        last_triggered_date = current_date
                        phone = config.get("phone", "")
                        # Open daily_scan.py in a visible console window
                        import subprocess as _sp
                        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daily_scan.py")
                        cmd = f'"{PYTHON_PATH}" "{script}"'
                        if phone:
                            cmd += f" {phone}"
                        _sp.Popen(f'start "ReversalIQ Daily Scan" cmd /k {cmd}', shell=True)
            except Exception:
                pass
            _time.sleep(30)

    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()


# Start the scheduler when the app loads (only once)
if "scheduler_started" not in st.session_state:
    st.session_state.scheduler_started = True
    _start_scheduler()


# ── Page config ──
st.set_page_config(
    page_title="ReversalIQ — Stock Screener",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Full theme override ──
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

<style>
    /* ───── ROOT VARIABLES ───── */
    :root {
        --bg-0: #05060a;
        --bg-50: #0a0d14;
        --bg-100: #0f1219;
        --bg-200: #151a24;
        --bg-300: #1c2231;
        --bg-400: #252d3f;
        --bg-500: #334155;
        --brand-400: #59b2ff;
        --brand-500: #3b91ff;
        --brand-600: #1a6ff5;
        --brand-700: #1459e1;
        --green: #22c55e;
        --red: #ef4444;
        --orange: #fb923c;
        --text-primary: #e2e8f0;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --border: rgba(255,255,255,0.06);
        --glass-bg: linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%);
        --glass-border: rgba(255,255,255,0.06);
    }

    /* ───── GLOBAL ───── */
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        background-color: var(--bg-0) !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    }

    .stApp > header { background: transparent !important; }

    /* ───── SIDEBAR ───── */
    [data-testid="stSidebar"] {
        background: var(--bg-50) !important;
        border-right: 1px solid var(--border) !important;
    }
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        background: var(--bg-50) !important;
    }
    [data-testid="stSidebar"] * {
        color: var(--text-primary) !important;
    }
    [data-testid="stSidebar"] .stSelectbox > div > div,
    [data-testid="stSidebar"] .stTextInput > div > div > input,
    [data-testid="stSidebar"] .stTextArea textarea {
        background-color: var(--bg-200) !important;
        border-color: var(--bg-400) !important;
        color: var(--text-primary) !important;
        border-radius: 10px !important;
    }
    [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] [role="slider"] {
        background-color: var(--brand-600) !important;
    }
    [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] > div > div {
        background: var(--bg-400) !important;
    }
    [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] > div > div > div {
        background: var(--brand-600) !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: var(--border) !important;
    }

    /* Sidebar logo block */
    .sidebar-brand {
        display: flex; align-items: center; gap: 12px;
        padding: 4px 0 12px 0;
    }
    .sidebar-brand .logo-icon {
        width: 36px; height: 36px; border-radius: 10px;
        background: linear-gradient(135deg, var(--brand-500), var(--brand-700));
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 4px 16px rgba(59,145,255,0.2);
    }
    .sidebar-brand .logo-icon svg { width: 20px; height: 20px; }
    .sidebar-brand .logo-text {
        font-size: 18px; font-weight: 800; letter-spacing: -0.02em;
        color: #fff !important;
    }
    .sidebar-brand .logo-text span { color: var(--brand-400); }

    /* Sidebar section labels */
    .sidebar-section {
        font-size: 11px; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.08em; color: var(--text-muted) !important;
        margin: 16px 0 8px 0; padding: 0;
    }

    /* ───── MAIN CONTENT AREA ───── */
    .block-container {
        padding-top: 2rem !important;
        max-width: 1400px !important;
    }

    /* ───── HEADER ───── */
    .main-header {
        display: flex; align-items: center; gap: 16px;
        margin-bottom: 4px;
    }
    .main-header h1 {
        font-size: 28px; font-weight: 800; letter-spacing: -0.02em;
        color: #fff; margin: 0; line-height: 1.2;
    }
    .main-header h1 span { color: var(--brand-400); }
    .main-subtitle {
        font-size: 14px; color: var(--text-muted); margin-bottom: 24px;
    }
    .live-dot {
        display: inline-flex; align-items: center; gap: 6px;
        font-size: 11px; font-weight: 600; color: var(--green);
        background: rgba(34,197,94,0.08); border: 1px solid rgba(34,197,94,0.15);
        padding: 4px 12px; border-radius: 999px;
    }
    .live-dot::before {
        content: ''; width: 6px; height: 6px; border-radius: 50%;
        background: var(--green); animation: pulse-dot 2s ease-in-out infinite;
    }
    @keyframes pulse-dot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.4; transform: scale(0.8); }
    }

    /* ───── METRICS (top row) ───── */
    div[data-testid="stMetric"] {
        background: var(--glass-bg) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 14px !important;
        padding: 20px 24px !important;
        backdrop-filter: blur(20px);
        transition: border-color 0.2s;
    }
    div[data-testid="stMetric"]:hover {
        border-color: rgba(59,145,255,0.15) !important;
    }
    div[data-testid="stMetric"] label {
        color: var(--text-muted) !important;
        font-size: 12px !important; font-weight: 500 !important;
        text-transform: uppercase !important; letter-spacing: 0.06em !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #fff !important;
        font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
        font-size: 22px !important; font-weight: 700 !important;
    }

    /* ───── EXPANDER (signal cards) ───── */
    [data-testid="stExpander"] {
        background: var(--glass-bg) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 16px !important;
        overflow: hidden;
        margin-bottom: 12px !important;
        backdrop-filter: blur(20px);
        transition: border-color 0.25s, box-shadow 0.25s;
    }
    [data-testid="stExpander"]:hover {
        border-color: rgba(59,145,255,0.15) !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.3);
    }
    [data-testid="stExpander"] summary {
        background: transparent !important;
        color: var(--text-primary) !important;
        padding: 18px 24px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
    }
    [data-testid="stExpander"] summary:hover {
        color: #fff !important;
    }
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        padding: 0 24px 24px 24px !important;
        border-top: 1px solid var(--border) !important;
    }

    /* ───── BUTTONS ───── */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, var(--brand-600), var(--brand-700)) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        padding: 12px 24px !important;
        transition: all 0.2s !important;
        box-shadow: 0 4px 16px rgba(26,111,245,0.2) !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(135deg, var(--brand-500), var(--brand-600)) !important;
        box-shadow: 0 6px 24px rgba(26,111,245,0.35) !important;
        transform: translateY(-1px);
    }
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="stBaseButton-secondary"] {
        background: var(--bg-200) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--bg-400) !important;
        border-radius: 12px !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        padding: 12px 24px !important;
        transition: all 0.2s !important;
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="stBaseButton-secondary"]:hover {
        border-color: var(--bg-500) !important;
        background: var(--bg-300) !important;
    }
    .stButton > button:disabled {
        opacity: 0.35 !important;
    }

    /* ───── PROGRESS BAR ───── */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, var(--brand-600), var(--brand-400)) !important;
        border-radius: 8px !important;
    }
    .stProgress > div > div {
        background: var(--bg-300) !important;
        border-radius: 8px !important;
    }

    /* ───── DIVIDERS ───── */
    hr {
        border-color: var(--border) !important;
    }

    /* ───── INFO / WARNING / SUCCESS / ERROR ───── */
    [data-testid="stAlert"] {
        background: var(--bg-200) !important;
        border-radius: 12px !important;
        border-left: 4px solid var(--brand-600) !important;
        color: var(--text-primary) !important;
    }
    .stSuccess [data-testid="stAlert"] { border-left-color: var(--green) !important; }
    .stWarning [data-testid="stAlert"] { border-left-color: var(--orange) !important; }
    .stError [data-testid="stAlert"] { border-left-color: var(--red) !important; }

    /* ───── DATAFRAME ───── */
    [data-testid="stDataFrame"] {
        border-radius: 12px !important;
        overflow: hidden;
    }
    .stDataFrame [data-testid="glideDataEditor"] {
        border-radius: 12px !important;
    }

    /* ───── RADIO BUTTONS ───── */
    .stRadio > div { gap: 8px !important; }
    .stRadio label {
        background: var(--bg-200) !important;
        border: 1px solid var(--bg-400) !important;
        border-radius: 10px !important;
        padding: 6px 16px !important;
        color: var(--text-secondary) !important;
        transition: all 0.2s !important;
    }
    .stRadio label[data-checked="true"],
    .stRadio label:has(input:checked) {
        background: var(--brand-600) !important;
        border-color: var(--brand-500) !important;
        color: #fff !important;
    }

    /* ───── TOGGLE ───── */
    [data-testid="stToggle"] label span {
        color: var(--text-primary) !important;
    }

    /* ───── SELECT SLIDER ───── */
    [data-testid="stSliderTickBarMin"],
    [data-testid="stSliderTickBarMax"] {
        color: var(--text-muted) !important;
    }

    /* ───── MARKDOWN ───── */
    .stMarkdown p, .stMarkdown li {
        color: var(--text-secondary) !important;
    }
    .stMarkdown strong {
        color: #fff !important;
    }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #fff !important;
    }

    /* ───── CAPTION ───── */
    .stCaption, [data-testid="stCaptionContainer"] {
        color: var(--text-muted) !important;
    }

    /* ───── TOAST ───── */
    [data-testid="stToast"] {
        background: var(--bg-200) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 12px !important;
        color: var(--text-primary) !important;
    }

    /* ───── SCROLLBAR ───── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg-50); }
    ::-webkit-scrollbar-thumb { background: var(--bg-400); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--bg-500); }

    /* ───── LANDING LINK ───── */
    .back-to-landing {
        display: inline-flex; align-items: center; gap: 6px;
        font-size: 13px; color: var(--text-muted);
        text-decoration: none; margin-bottom: 12px;
        transition: color 0.2s;
    }
    .back-to-landing:hover { color: var(--brand-400); }

    /* ───── EMPTY STATE ───── */
    .empty-state {
        text-align: center; padding: 80px 20px;
    }
    .empty-state .icon-ring {
        width: 80px; height: 80px; border-radius: 50%;
        background: rgba(59,145,255,0.06); border: 1px solid rgba(59,145,255,0.1);
        display: flex; align-items: center; justify-content: center;
        margin: 0 auto 20px auto;
    }
    .empty-state h3 {
        font-size: 20px; font-weight: 700; color: #fff; margin-bottom: 8px;
    }
    .empty-state p {
        font-size: 14px; color: var(--text-muted); max-width: 400px; margin: 0 auto;
    }

    /* ───── GRID BACKGROUND PATTERN ───── */
    .grid-bg {
        position: fixed; inset: 0; z-index: -1; pointer-events: none;
        background-image:
            linear-gradient(rgba(59,145,255,0.015) 1px, transparent 1px),
            linear-gradient(90deg, rgba(59,145,255,0.015) 1px, transparent 1px);
        background-size: 64px 64px;
        mask-image: radial-gradient(ellipse 70% 50% at 50% 30%, black, transparent);
    }

    /* ───── HIDE STREAMLIT DEFAULTS ───── */
    #MainMenu { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent !important; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }

    /* ───── SUBHEADER STYLE ───── */
    [data-testid="stSubheader"] h2,
    .stSubheader {
        font-size: 18px !important; font-weight: 700 !important;
        color: #fff !important; letter-spacing: -0.01em;
    }

    /* ───── SIGNAL CARD (matching landing page) ───── */
    .signal-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 16px;
        backdrop-filter: blur(20px);
        transition: border-color 0.25s, box-shadow 0.25s;
    }
    .signal-card:hover {
        border-color: rgba(59,145,255,0.15);
        box-shadow: 0 4px 24px rgba(0,0,0,0.3);
    }

    /* Card header */
    .card-header {
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 20px;
    }
    .card-header-left {
        display: flex; align-items: center; gap: 12px;
    }
    .stock-icon {
        width: 44px; height: 44px; border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700; font-size: 16px; color: #fff;
    }
    .stock-name {
        font-size: 16px; font-weight: 700; color: #fff;
    }
    .stock-name span {
        font-size: 12px; font-weight: 400; color: var(--text-muted); margin-left: 6px;
    }
    .stock-sector {
        font-size: 11px; color: var(--text-muted);
    }
    .card-header-right { text-align: right; }
    .card-price {
        font-size: 16px; font-weight: 700; color: #fff;
        font-family: 'JetBrains Mono', monospace;
    }
    .card-pullback {
        font-size: 12px; font-weight: 600; color: var(--red);
        font-family: 'JetBrains Mono', monospace;
    }

    /* Signal badge */
    .signal-badge {
        display: inline-flex; align-items: center; gap: 6px;
        font-size: 11px; font-weight: 600; color: var(--green);
        background: rgba(34,197,94,0.08); border: 1px solid rgba(34,197,94,0.15);
        padding: 4px 10px; border-radius: 999px; margin-left: 12px;
    }
    .signal-badge::before {
        content: ''; width: 6px; height: 6px; border-radius: 50%;
        background: var(--green); display: inline-block;
    }

    /* Metrics grid */
    .metrics-grid {
        display: grid; gap: 8px; margin-bottom: 16px;
    }
    .metrics-grid-5 { grid-template-columns: repeat(5, 1fr); }
    .metrics-grid-3 { grid-template-columns: repeat(3, 1fr); }
    .metrics-grid-6 { grid-template-columns: repeat(6, 1fr); }
    .metrics-grid-4 { grid-template-columns: repeat(4, 1fr); }
    .metric-box {
        background: var(--bg-100);
        border-radius: 10px;
        padding: 12px 8px;
        text-align: center;
    }
    .metric-label {
        font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em;
        color: var(--text-muted); margin-bottom: 4px;
    }
    .metric-value {
        font-size: 15px; font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        color: #fff;
    }
    .metric-value.brand { color: var(--brand-400); }
    .metric-value.green { color: var(--green); }
    .metric-value.red { color: var(--red); }
    .metric-value.orange { color: var(--orange); }

    /* Confirmation row */
    .confirm-row {
        display: flex; align-items: center; gap: 8px;
        font-size: 12px; margin-top: 12px;
    }
    .confirm-row .label { color: var(--text-muted); }
    .confirm-row .value { color: var(--green); font-weight: 600; }
    .confirm-checks {
        display: flex; gap: 4px; margin-left: auto;
    }
    .confirm-check {
        width: 22px; height: 22px; border-radius: 6px;
        background: rgba(34,197,94,0.12);
        display: flex; align-items: center; justify-content: center;
    }
    .confirm-check svg { width: 12px; height: 12px; }

    /* Explanation text */
    .card-explanation {
        font-size: 13px; color: var(--text-secondary); line-height: 1.6;
        padding: 16px 0 0 0; border-top: 1px solid var(--border); margin-top: 16px;
    }
    .card-explanation strong { color: var(--brand-300); font-weight: 600; }

    /* Responsive */
    @media (max-width: 640px) {
        .metrics-grid-5, .metrics-grid-6 { grid-template-columns: repeat(3, 1fr); }
        .card-header { flex-direction: column; align-items: flex-start; gap: 12px; }
        .card-header-right { text-align: left; }
    }
</style>

<div class="grid-bg"></div>
""", unsafe_allow_html=True)


# ── Session state ──
if "scan_results" not in st.session_state:
    st.session_state.scan_results = None
if "price_cache" not in st.session_state:
    st.session_state.price_cache = {}
if "scan_time" not in st.session_state:
    st.session_state.scan_time = None
if "stop_scan" not in st.session_state:
    st.session_state.stop_scan = False


def _check_stop():
    """Returns True if the user has requested to stop the scan."""
    return st.session_state.get("stop_scan", False)


# ── Sidebar ──
with st.sidebar:
    # Brand logo
    st.markdown("""
    <div class="sidebar-brand">
        <div class="logo-icon">
            <svg fill="none" stroke="white" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 17l6-6 4 4 8-8M14 7h7v7"/>
            </svg>
        </div>
        <div class="logo-text">Reversal<span>IQ</span></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<a class="back-to-landing" href="http://localhost:8000" target="_self">&larr; Back to Home</a>', unsafe_allow_html=True)

    st.divider()
    st.markdown('<div class="sidebar-section">Stock Universe</div>', unsafe_allow_html=True)

    universe = st.selectbox(
        "Stock Universe",
        list(UNIVERSE_OPTIONS.keys()),
        help="Which group of stocks to scan",
        label_visibility="collapsed",
    )

    if universe == "Custom":
        custom_tickers = st.text_area(
            "Tickers (comma-separated)",
            placeholder="AAPL, MSFT, GOOGL, NVDA",
            help="Enter stock tickers separated by commas",
        )
    else:
        custom_tickers = ""

    max_stocks = st.select_slider(
        "Stocks to Scan",
        options=[50, 100, 250, 500, 1000, 2000, 3000],
        value=500,
        help="Number of stocks to screen (more = slower)",
    )

    st.divider()
    st.markdown('<div class="sidebar-section">Technical Parameters</div>', unsafe_allow_html=True)

    rsi_threshold = st.slider(
        "RSI Threshold",
        min_value=15.0, max_value=45.0,
        value=DEFAULT_RSI_THRESHOLD, step=1.0,
        help="RSI must drop below this level to trigger a signal",
    )

    sma_proximity = st.slider(
        "SMA Proximity (%)",
        min_value=0.5, max_value=5.0,
        value=DEFAULT_SMA_PROXIMITY_PCT, step=0.5,
        help="Max distance from SMA to count as 'touching'",
    )

    pullback_pct = st.slider(
        "Min Pullback from High (%)",
        min_value=5.0, max_value=35.0,
        value=DEFAULT_PULLBACK_PCT, step=1.0,
        help="Minimum decline from 52-week high",
    )

    confirm_candles = st.slider(
        "Confirmation Candles",
        min_value=1, max_value=5,
        value=DEFAULT_CONFIRMATION_CANDLES,
        help="Consecutive candles closing above SMA to confirm reversal",
    )

    st.divider()

    scan_col1, scan_col2 = st.columns([3, 1])
    with scan_col1:
        run_scan = st.button("Run Scan", type="primary", use_container_width=True)
    with scan_col2:
        if st.button("Stop", use_container_width=True, type="secondary"):
            st.session_state.stop_scan = True

    st.divider()
    st.markdown('<div class="sidebar-section">Export</div>', unsafe_allow_html=True)
    export_fmt = st.radio("Export Format", ["CSV", "JSON"], horizontal=True, label_visibility="collapsed")

    export_btn = st.button(
        "Export Results",
        use_container_width=True,
        disabled=st.session_state.scan_results is None,
    )

    st.divider()
    st.markdown('<div class="sidebar-section">Telegram Alerts</div>', unsafe_allow_html=True)
    tg_enabled = st.toggle("Enable Telegram", value=True)

    # Load saved credentials
    _tg_creds_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "tg_creds.json")
    _saved_tg = {}
    try:
        with open(_tg_creds_file) as _f:
            _saved_tg = _json.load(_f)
    except Exception:
        pass

    tg_token = st.text_input(
        "Bot Token",
        value=_saved_tg.get("token", ""),
        type="password",
        help="Get from @BotFather on Telegram",
    )
    tg_chat_id = st.text_input(
        "Chat ID",
        value=_saved_tg.get("chat_id", ""),
        help="Your Telegram chat ID",
    )

    # Auto-save credentials when changed
    if tg_token and tg_chat_id:
        _new_tg = {"token": tg_token, "chat_id": tg_chat_id}
        if _new_tg != _saved_tg:
            os.makedirs(os.path.dirname(_tg_creds_file), exist_ok=True)
            with open(_tg_creds_file, "w") as _f:
                _json.dump(_new_tg, _f)

    if tg_enabled and (not tg_token or not tg_chat_id):
        st.caption("Set up: message @BotFather on Telegram, send /newbot, get token. Then message your bot and visit api.telegram.org/bot<TOKEN>/getUpdates for chat\\_id")

    tg_send_btn = st.button(
        "Send Results to Telegram",
        use_container_width=True,
        disabled=(st.session_state.scan_results is None or not tg_enabled
                  or not tg_token or not tg_chat_id),
    )

    st.divider()
    st.markdown('<div class="sidebar-section">Daily Auto-Scan</div>', unsafe_allow_html=True)

    saved_config = _load_schedule()
    daily_enabled = st.toggle("Enable Daily Scan", value=saved_config.get("enabled", False))
    daily_time = st.time_input(
        "Scan Time",
        value=datetime.strptime(saved_config.get("time", "18:30"), "%H:%M").time(),
        help="When to run the daily scan (after market close)",
    )

    daily_universe_size = 3000
    daily_wa = False
    if daily_enabled:
        daily_universe_size = st.select_slider(
            "Daily Scan Size",
            options=[500, 1000, 2000, 3000],
            value=saved_config.get("scan_size", 3000),
            help="How many stocks to scan daily",
        )
        daily_tg = st.checkbox(
            "Send Telegram alert",
            value=saved_config.get("telegram", False) and tg_enabled,
        )
        if daily_tg and (not tg_token or not tg_chat_id):
            st.caption("Enter bot token and chat ID above first")

    col_sched1, col_sched2 = st.columns(2)
    with col_sched1:
        if st.button("Save Schedule", use_container_width=True):
            config = {
                "enabled": daily_enabled,
                "time": daily_time.strftime("%H:%M"),
                "scan_size": daily_universe_size,
                "telegram": daily_tg if daily_enabled else False,
                "tg_token": tg_token if (daily_enabled and daily_tg) else "",
                "tg_chat_id": tg_chat_id if (daily_enabled and daily_tg) else "",
                "last_run": saved_config.get("last_run", "Never"),
                "last_results": saved_config.get("last_results", 0),
                "last_new": saved_config.get("last_new", 0),
            }
            _save_schedule(config)
            if daily_enabled:
                st.success(f"Scheduled daily at {config['time']}")
            else:
                st.success("Daily scan disabled")
    with col_sched2:
        run_daily_now = st.button("Run Now", use_container_width=True)

    # Status
    status = _get_schedule_status()
    if status:
        st.caption(status)

    # Show last scan log if available
    if os.path.exists(_SCAN_LOG_FILE):
        with st.expander("Last Daily Scan Log"):
            with open(_SCAN_LOG_FILE) as f:
                st.code(f.read(), language=None)


# ── Main Header ──
st.markdown("""
<div class="main-header">
    <h1>Stock Reversal <span>Screener</span></h1>
    <div class="live-dot">LIVE</div>
</div>
<div class="main-subtitle">
    Large-cap stocks bouncing off 150 &amp; 200-day SMA with RSI confirmation and fundamental validation
</div>
""", unsafe_allow_html=True)


# ── Plotly theme matching the landing page ──
CHART_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(15,18,25,1)",
    plot_bgcolor="rgba(15,18,25,1)",
    font=dict(family="Inter, system-ui, sans-serif", color="#94a3b8"),
    xaxis=dict(
        gridcolor="rgba(255,255,255,0.03)",
        linecolor="rgba(255,255,255,0.06)",
        zerolinecolor="rgba(255,255,255,0.03)",
    ),
    yaxis=dict(
        gridcolor="rgba(255,255,255,0.03)",
        linecolor="rgba(255,255,255,0.06)",
        zerolinecolor="rgba(255,255,255,0.03)",
        side="right",
    ),
    xaxis_rangeslider_visible=False,
    margin=dict(l=0, r=0, t=36, b=0),
    height=380,
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(size=11, color="#94a3b8"),
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="left", x=0,
    ),
)

CANDLE_COLORS = dict(
    increasing_line_color="#22c55e",
    increasing_fillcolor="#22c55e",
    decreasing_line_color="#ef4444",
    decreasing_fillcolor="#ef4444",
)


# ── Run daily scan (in-page) ──
if run_daily_now:
    st.session_state.stop_scan = False
    config = _load_schedule()
    daily_scan_size = config.get("scan_size", 3000)
    daily_tg_token = config.get("tg_token", tg_token or "")
    daily_tg_chat_id = config.get("tg_chat_id", tg_chat_id or "")

    st.info(f"Running daily scan — **{daily_scan_size}** stocks from **All US Large-Cap**...")
    progress_bar = st.progress(0, text="Fetching stock universe...")

    daily_tickers = fetch_universe("All US Large-Cap ($1B+)", daily_scan_size)
    progress_bar.progress(10, text=f"Found {len(daily_tickers)} stocks. Downloading prices...")

    daily_price_data = fetch_price_data(tuple(daily_tickers), period="1y")
    progress_bar.progress(40, text=f"Downloaded {len(daily_price_data)} stocks. Screening...")

    def daily_tech_progress(current, total, msg):
        pct = 40 + int((current / max(total, 1)) * 30)
        progress_bar.progress(min(pct, 70), text=msg)

    daily_candidates = technical_screen(
        daily_price_data,
        rsi_threshold=DEFAULT_RSI_THRESHOLD,
        sma_proximity_pct=DEFAULT_SMA_PROXIMITY_PCT,
        pullback_pct=DEFAULT_PULLBACK_PCT,
        confirmation_candles=DEFAULT_CONFIRMATION_CANDLES,
        lookback_days=DEFAULT_LOOKBACK_DAYS,
        progress_callback=daily_tech_progress,
        stop_flag=_check_stop,
    )

    if _check_stop():
        st.warning("Daily scan stopped by user.")
        st.session_state.stop_scan = False
        st.stop()

    progress_bar.progress(70, text=f"{len(daily_candidates)} candidates. Checking fundamentals...")

    def daily_fund_progress(current, total, msg):
        pct = 70 + int((current / max(total, 1)) * 25)
        progress_bar.progress(min(pct, 95), text=msg)

    daily_results = fundamental_filter(daily_candidates, progress_callback=daily_fund_progress, stop_flag=_check_stop)

    if _check_stop():
        st.warning("Daily scan stopped by user.")
        st.session_state.stop_scan = False
        st.stop()

    # Compare with previous
    prev = get_previous_symbols()
    new_only = [r for r in daily_results if r["symbol"] not in prev]

    progress_bar.progress(100, text=f"Done! {len(daily_results)} total, {len(new_only)} new signals")

    # Save to session so they show in the results area
    st.session_state.scan_results = daily_results
    st.session_state.price_cache = daily_price_data
    st.session_state.scan_time = datetime.now()

    # Save results for next comparison
    if daily_results:
        save_results(daily_results, fmt="json")

    # Update schedule last run
    sched = _load_schedule()
    sched["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    sched["last_results"] = len(daily_results)
    sched["last_new"] = len(new_only)
    _save_schedule(sched)

    # Telegram — only new
    if tg_enabled and tg_token and tg_chat_id and new_only:
        with st.spinner(f"Sending {len(new_only)} new signal(s) to Telegram..."):
            if send_telegram(new_only, tg_token, tg_chat_id):
                st.success(f"Telegram sent! ({len(new_only)} new signals)")
            else:
                st.warning("Telegram send failed")
    elif tg_enabled and tg_token and tg_chat_id and not new_only and daily_results:
        st.info("No new signals since last scan — Telegram skipped")


# ── Run scan ──
if run_scan:
    st.session_state.stop_scan = False

    if universe == "Custom":
        tickers = [t.strip().upper() for t in custom_tickers.split(",") if t.strip()]
        if not tickers:
            st.error("Enter at least one ticker.")
            st.stop()
    else:
        with st.spinner("Loading stock universe..."):
            tickers = fetch_universe(universe, max_stocks)

    st.info(f"Scanning **{len(tickers)}** stocks from **{universe}**...")

    progress_bar = st.progress(0, text="Downloading price data...")
    price_data = fetch_price_data(tuple(tickers), period="1y")
    progress_bar.progress(40, text=f"Downloaded data for {len(price_data)} stocks")

    def tech_progress(current, total, msg):
        pct = 40 + int((current / max(total, 1)) * 30)
        progress_bar.progress(min(pct, 70), text=msg)

    candidates = technical_screen(
        price_data,
        rsi_threshold=rsi_threshold,
        sma_proximity_pct=sma_proximity,
        pullback_pct=pullback_pct,
        confirmation_candles=confirm_candles,
        lookback_days=DEFAULT_LOOKBACK_DAYS,
        progress_callback=tech_progress,
        stop_flag=_check_stop,
    )

    if _check_stop():
        st.warning("Scan stopped by user.")
        st.session_state.stop_scan = False
        st.stop()

    progress_bar.progress(70, text=f"Found {len(candidates)} technical candidates. Checking fundamentals...")

    def fund_progress(current, total, msg):
        pct = 70 + int((current / max(total, 1)) * 28)
        progress_bar.progress(min(pct, 98), text=msg)

    results = fundamental_filter(candidates, progress_callback=fund_progress, stop_flag=_check_stop)

    if _check_stop():
        st.warning("Scan stopped by user.")
        st.session_state.stop_scan = False
        st.stop()

    progress_bar.progress(100, text="Scan complete!")

    st.session_state.scan_results = results
    st.session_state.price_cache = price_data
    st.session_state.scan_time = datetime.now()

    prev = get_previous_symbols()
    current_syms = [r["symbol"] for r in results]
    new_only = [r for r in results if r["symbol"] not in prev]
    notify_new_signals(current_syms, prev)

    if tg_enabled and tg_token and tg_chat_id and new_only:
        with st.spinner(f"Sending {len(new_only)} new signal(s) to Telegram..."):
            if send_telegram(new_only, tg_token, tg_chat_id):
                st.success(f"Telegram alert sent! ({len(new_only)} new signals)")
            else:
                st.warning("Telegram send failed.")
    elif tg_enabled and tg_token and tg_chat_id and results and not new_only:
        st.info("No new signals since last scan — Telegram skipped")


# ── Display results ──
results = st.session_state.scan_results

if results is not None:
    scan_time = st.session_state.scan_time

    col1, col2, col3 = st.columns(3)
    col1.metric("Candidates Found", len(results))
    col2.metric("Last Scan", scan_time.strftime("%H:%M:%S") if scan_time else "N/A")
    col3.metric(
        "Avg Pullback",
        f"{sum(r['pullback_pct'] for r in results) / max(len(results), 1):.1f}%"
        if results else "N/A"
    )

    if not results:
        st.markdown("""
        <div class="empty-state">
            <div class="icon-ring">
                <svg width="32" height="32" fill="none" stroke="#3b91ff" stroke-width="1.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/>
                </svg>
            </div>
            <h3>No Signals Found</h3>
            <p>No stocks matched all criteria with the current parameters. Try relaxing the RSI threshold or pullback percentage.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.divider()
        st.subheader(f"Results ({len(results)} stocks)")

        for r in sorted(results, key=lambda x: x["pullback_pct"], reverse=True):
            sym = r["symbol"]
            fund = r.get("fundamentals", {})
            name = fund.get("longName", sym)
            sector = fund.get("sector", "N/A")
            industry = fund.get("industry", "")

            # Color for stock icon based on first letter hash
            icon_colors = [
                "linear-gradient(135deg,#1a6ff5,#1448b6)",
                "linear-gradient(135deg,#16a34a,#15803d)",
                "linear-gradient(135deg,#9333ea,#7e22ce)",
                "linear-gradient(135deg,#ea580c,#c2410c)",
                "linear-gradient(135deg,#0891b2,#0e7490)",
                "linear-gradient(135deg,#e11d48,#be123c)",
            ]
            icon_bg = icon_colors[ord(sym[0]) % len(icon_colors)]

            # Format signal date nicely
            try:
                from datetime import datetime as _dt
                sig_date = _dt.strptime(r["signal_date"], "%Y-%m-%d").strftime("%b %d")
            except Exception:
                sig_date = r["signal_date"]

            # Build confirmation checks HTML
            checks_html = ""
            for i in range(r.get("confirmed_candles", 3)):
                checks_html += '<div class="confirm-check"><svg fill="#22c55e" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg></div>'

            # Revenue growth color
            rev_g = fund.get("revenueGrowth")
            rev_str = _fmt(rev_g, ".1f", multiply=100, prefix="+", suffix="%") if rev_g and float(rev_g) > 0 else _fmt(rev_g, ".1f", multiply=100, suffix="%")
            rev_class = "green" if rev_g and float(rev_g) > 0 else "red" if rev_g and float(rev_g) < 0 else ""

            # Build the card HTML
            card_html = textwrap.dedent(f'''\
<div class="signal-card">
<div class="card-header">
<div class="card-header-left">
<div class="stock-icon" style="background:{icon_bg};">{sym[0]}</div>
<div>
<div class="stock-name">{sym}<span>{name}</span>
<span class="signal-badge">Reversal Signal</span>
</div>
<div class="stock-sector">{sector} | {industry}</div>
</div>
</div>
<div class="card-header-right">
<div class="card-price">${r["current_price"]}</div>
<div class="card-pullback">-{r["pullback_pct"]}% from high</div>
</div>
</div>
<div class="metrics-grid metrics-grid-5">
<div class="metric-box">
<div class="metric-label">Signal</div>
<div class="metric-value">{sig_date}</div>
</div>
<div class="metric-box">
<div class="metric-label">RSI</div>
<div class="metric-value brand">{r["rsi_at_signal"]}</div>
</div>
<div class="metric-box">
<div class="metric-label">SMA</div>
<div class="metric-value orange">{r["sma_period"]}d</div>
</div>
<div class="metric-box">
<div class="metric-label">SMA Dist</div>
<div class="metric-value green">{r["sma_distance_pct"]}%</div>
</div>
<div class="metric-box">
<div class="metric-label">52W High</div>
<div class="metric-value">${r["high_52w"]}</div>
</div>
</div>
</div>''')
            st.markdown(card_html, unsafe_allow_html=True)

            # Chart in a dropdown
            price_data = st.session_state.price_cache.get(sym)
            if price_data is not None:
                with st.expander(f"Chart — {sym} Last 90 Days", expanded=False):
                    chart_df = price_data.tail(90).copy()
                    close_col = chart_df["Close"].squeeze() if isinstance(chart_df["Close"], pd.DataFrame) else chart_df["Close"]
                    full_close = (
                        st.session_state.price_cache[sym]["Close"].squeeze()
                        if isinstance(st.session_state.price_cache[sym]["Close"], pd.DataFrame)
                        else st.session_state.price_cache[sym]["Close"]
                    )
                    sma_line = compute_sma(full_close, r["sma_period"]).tail(90)

                    fig = go.Figure()
                    fig.add_trace(go.Candlestick(
                        x=chart_df.index,
                        open=(chart_df["Open"].squeeze() if isinstance(chart_df["Open"], pd.DataFrame) else chart_df["Open"]),
                        high=(chart_df["High"].squeeze() if isinstance(chart_df["High"], pd.DataFrame) else chart_df["High"]),
                        low=(chart_df["Low"].squeeze() if isinstance(chart_df["Low"], pd.DataFrame) else chart_df["Low"]),
                        close=close_col,
                        name="Price",
                        **CANDLE_COLORS,
                    ))
                    fig.add_trace(go.Scatter(
                        x=sma_line.index, y=sma_line.values,
                        mode="lines", name=f"SMA-{r['sma_period']}",
                        line=dict(color="#fb923c", width=2),
                    ))
                    fig.update_layout(
                        title=dict(
                            text=f"{sym} — Last 90 Days",
                            font=dict(size=14, color="#e2e8f0"),
                        ),
                        **CHART_LAYOUT,
                    )
                    st.plotly_chart(fig, use_container_width=True)

            # Fundamentals row + confirmation + explanation
            explanation_html = r.get("explanation", "").replace(chr(10), "<br>")
            fund_html = textwrap.dedent(f'''\
<div class="signal-card" style="margin-top:-12px; border-top-left-radius:0; border-top-right-radius:0;">
<div class="metrics-grid metrics-grid-6">
<div class="metric-box">
<div class="metric-label">Rev Growth</div>
<div class="metric-value {rev_class}">{rev_str}</div>
</div>
<div class="metric-box">
<div class="metric-label">Margin</div>
<div class="metric-value">{_fmt(fund.get("profitMargins"), ".1f", multiply=100, suffix="%")}</div>
</div>
<div class="metric-box">
<div class="metric-label">P/E</div>
<div class="metric-value">{_fmt(fund.get("trailingPE"))}</div>
</div>
<div class="metric-box">
<div class="metric-label">Fwd P/E</div>
<div class="metric-value">{_fmt(fund.get("forwardPE"))}</div>
</div>
<div class="metric-box">
<div class="metric-label">D/E</div>
<div class="metric-value">{_fmt(fund.get("debtToEquity"))}</div>
</div>
<div class="metric-box">
<div class="metric-label">ROE</div>
<div class="metric-value">{_fmt(fund.get("returnOnEquity"), ".1f", multiply=100, suffix="%")}</div>
</div>
</div>
<div class="confirm-row">
<span class="label">Confirmation:</span>
<span class="value">{r.get("confirmed_candles", 3)}/{r.get("confirmed_candles", 3)} candles above SMA</span>
<div class="confirm-checks">{checks_html}</div>
</div>
<div class="card-explanation">{explanation_html}</div>
</div>''')
            st.markdown(fund_html, unsafe_allow_html=True)
            st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

elif results is None:
    st.markdown("""
    <div class="empty-state">
        <div class="icon-ring">
            <svg width="32" height="32" fill="none" stroke="#3b91ff" stroke-width="1.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 17l6-6 4 4 8-8M14 7h7v7"/>
            </svg>
        </div>
        <h3>Ready to Scan</h3>
        <p>Configure parameters in the sidebar and click <strong>Run Scan</strong> to find reversal setups across large-cap stocks.</p>
    </div>
    """, unsafe_allow_html=True)


# ── Export ──
if export_btn and results:
    fmt = export_fmt.lower()
    filepath = save_results(results, fmt=fmt)
    st.sidebar.success(f"Saved to `{os.path.basename(filepath)}`")

    with open(filepath, "rb") as f:
        st.sidebar.download_button(
            label="Download File",
            data=f.read(),
            file_name=os.path.basename(filepath),
            mime="text/csv" if fmt == "csv" else "application/json",
        )


# ── Manual Telegram send ──
if tg_send_btn and st.session_state.scan_results:
    with st.spinner("Sending Telegram alert..."):
        if send_telegram(st.session_state.scan_results, tg_token, tg_chat_id):
            st.success("Telegram alert sent!")
        else:
            st.error("Failed to send. Check your bot token and chat ID.")


# ── GitHub Actions Status ──
st.divider()
with st.expander("GitHub Actions — Cloud Scans"):
    try:
        import requests as _req
        _gh_api = "https://api.github.com/repos/idofin/Screener1/actions/runs?per_page=5"
        _gh_resp = _req.get(_gh_api, timeout=5)
        if _gh_resp.status_code == 200:
            _runs = _gh_resp.json().get("workflow_runs", [])
            if _runs:
                for _run in _runs:
                    _status_icon = {"completed": "circle-check", "in_progress": "clock", "queued": "clock"}.get(_run["status"], "circle")
                    _conclusion = _run.get("conclusion", "running")
                    if _conclusion == "success":
                        _color = "green"
                        _label = "Passed"
                    elif _conclusion == "failure":
                        _color = "red"
                        _label = "Failed"
                    elif _run["status"] == "in_progress":
                        _color = "orange"
                        _label = "Running..."
                    else:
                        _color = "gray"
                        _label = _run["status"]

                    _created = _run.get("created_at", "")[:16].replace("T", " ")
                    _run_html = f'''<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);">
<span style="width:8px;height:8px;border-radius:50%;background:{_color};display:inline-block;"></span>
<span style="color:#e2e8f0;font-size:13px;font-weight:600;">{_run["name"]}</span>
<span style="color:#64748b;font-size:12px;margin-left:auto;">{_created}</span>
<span style="color:{_color};font-size:12px;font-weight:500;">{_label}</span>
</div>'''
                    st.markdown(_run_html, unsafe_allow_html=True)
            else:
                st.caption("No runs yet. The daily scan runs Mon-Fri at 6:30 PM ET.")
        else:
            st.caption("Could not fetch GitHub Actions status")
    except Exception:
        st.caption("Could not connect to GitHub API")

# ── Scan history ──
st.divider()
with st.expander("Scan History"):
    history = load_scan_history()
    if history:
        hist_df = pd.DataFrame(history)[["timestamp", "filename", "size_kb"]]
        hist_df.columns = ["Timestamp", "File", "Size (KB)"]
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No saved scans yet. Run a scan and export to see history here.")

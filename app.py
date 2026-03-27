import sys
import os
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
from notifications import notify_new_signals, send_whatsapp
from indicators import compute_sma


def _fmt(val, fmt=".1f", multiply=1, prefix="", suffix=""):
    """Safely format a numeric value that might be a string or None."""
    if val is None:
        return "N/A"
    try:
        return f"{prefix}{float(val) * multiply:{fmt}}{suffix}"
    except (ValueError, TypeError):
        return str(val)


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
        options=[50, 100, 250, 500],
        value=100,
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

    run_scan = st.button("Run Scan", type="primary", use_container_width=True)

    st.divider()
    st.markdown('<div class="sidebar-section">Export</div>', unsafe_allow_html=True)
    export_fmt = st.radio("Export Format", ["CSV", "JSON"], horizontal=True, label_visibility="collapsed")

    export_btn = st.button(
        "Export Results",
        use_container_width=True,
        disabled=st.session_state.scan_results is None,
    )

    st.divider()
    st.markdown('<div class="sidebar-section">WhatsApp Alerts</div>', unsafe_allow_html=True)
    wa_enabled = st.toggle("Enable WhatsApp", value=False)
    wa_phone = st.text_input(
        "Phone Number",
        placeholder="+972501234567",
        help="International format with country code",
    )
    if wa_enabled and not wa_phone:
        st.caption("Enter your phone number to enable alerts")
    if wa_enabled and wa_phone:
        st.caption("Make sure you're logged into WhatsApp Web in your browser")

    wa_send_btn = st.button(
        "Send Results to WhatsApp",
        use_container_width=True,
        disabled=(st.session_state.scan_results is None or not wa_enabled
                  or not wa_phone),
    )


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


# ── Run scan ──
if run_scan:
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
    )

    progress_bar.progress(70, text=f"Found {len(candidates)} technical candidates. Checking fundamentals...")

    def fund_progress(current, total, msg):
        pct = 70 + int((current / max(total, 1)) * 28)
        progress_bar.progress(min(pct, 98), text=msg)

    results = fundamental_filter(candidates, progress_callback=fund_progress)
    progress_bar.progress(100, text="Scan complete!")

    st.session_state.scan_results = results
    st.session_state.price_cache = price_data
    st.session_state.scan_time = datetime.now()

    prev = get_previous_symbols()
    current_syms = [r["symbol"] for r in results]
    notify_new_signals(current_syms, prev)

    if wa_enabled and wa_phone and results:
        with st.spinner("Sending WhatsApp alert..."):
            if send_whatsapp(wa_phone, results):
                st.success("WhatsApp alert sent!")
            else:
                st.warning("WhatsApp send failed. Check your phone number and API key.")


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
            sector = fund.get("sector", "")

            # Expander label
            label = f"**{sym}** — {name}  |  RSI: {r['rsi_at_signal']}  |  Pullback: {r['pullback_pct']}%  |  SMA-{r['sma_period']}"

            with st.expander(label, expanded=False):

                # Signal metrics
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Signal Date", r["signal_date"])
                m2.metric("Price @ Signal", _fmt(r['price_at_signal'], ",.2f", prefix="$"))
                m3.metric("Current Price", _fmt(r['current_price'], ",.2f", prefix="$"))
                m4.metric("52W High", _fmt(r['high_52w'], ",.2f", prefix="$"))
                m5.metric("RSI", f"{r['rsi_at_signal']}")

                # Chart
                price_data = st.session_state.price_cache.get(sym)
                if price_data is not None:
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

                # Fundamental details
                st.divider()
                f1, f2, f3, f4, f5, f6 = st.columns(6)
                f1.metric("Rev Growth", _fmt(fund.get("revenueGrowth"), ".1f", multiply=100, suffix="%"))
                f2.metric("Profit Margin", _fmt(fund.get("profitMargins"), ".1f", multiply=100, suffix="%"))
                f3.metric("P/E (TTM)", _fmt(fund.get("trailingPE")))
                f4.metric("P/E (Fwd)", _fmt(fund.get("forwardPE")))
                f5.metric("Debt/Equity", _fmt(fund.get("debtToEquity")))
                f6.metric("ROE", _fmt(fund.get("returnOnEquity"), ".1f", multiply=100, suffix="%"))

                # Explanation
                st.divider()
                st.markdown(r.get("explanation", ""))

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


# ── Manual WhatsApp send ──
if wa_send_btn and st.session_state.scan_results:
    with st.spinner("Sending WhatsApp alert..."):
        if send_whatsapp(wa_phone, st.session_state.scan_results):
            st.success("WhatsApp alert sent successfully!")
        else:
            st.error("Failed to send WhatsApp message. Check your phone number and API key.")


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

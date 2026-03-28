import streamlit as st

st.set_page_config(
    page_title="ReversalIQ — Smart Stock Reversal Screener",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide sidebar nav labels and streamlit defaults
st.markdown("""
<style>
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
    header[data-testid="stHeader"] { background: transparent !important; }
    [data-testid="stSidebar"] { background: #0a0d14 !important; }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
</style>
""", unsafe_allow_html=True)

LANDING_HTML = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body, .stApp, [data-testid="stAppViewContainer"] {
    background: #05060a !important; color: #e2e8f0;
    font-family: 'Inter', system-ui, sans-serif;
}
.landing { max-width: 1100px; margin: 0 auto; padding: 20px; }

.hero { text-align: center; padding: 60px 20px 40px; position: relative; }
.hero::before {
    content: ''; position: absolute; inset: 0;
    background: radial-gradient(ellipse 600px 400px at 50% 30%, rgba(59,145,255,0.08), transparent);
    pointer-events: none;
}
.hero h1 {
    font-size: clamp(36px, 6vw, 64px); font-weight: 900; line-height: 1.1;
    letter-spacing: -0.03em; color: #fff; margin-bottom: 12px; position: relative;
}
.hero h1 span {
    background: linear-gradient(135deg, #59b2ff, #3b91ff, #06b6d4);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero p {
    font-size: 17px; color: #94a3b8; max-width: 600px; margin: 0 auto 32px;
    line-height: 1.7; position: relative;
}
.live-badge {
    display: inline-flex; align-items: center; gap: 8px; padding: 6px 16px;
    border-radius: 999px; font-size: 12px; font-weight: 600; color: #22c55e;
    background: rgba(34,197,94,0.08); border: 1px solid rgba(34,197,94,0.15);
    margin-bottom: 24px;
}
.live-badge::before {
    content: ''; width: 6px; height: 6px; border-radius: 50%;
    background: #22c55e; animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

.features { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin: 40px 0; }
.feature {
    background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; padding: 28px;
    transition: border-color 0.2s;
}
.feature:hover { border-color: rgba(59,145,255,0.15); }
.feature-icon {
    width: 44px; height: 44px; border-radius: 12px; display: flex;
    align-items: center; justify-content: center; margin-bottom: 16px; font-size: 20px;
}
.feature h3 { font-size: 16px; font-weight: 700; color: #fff; margin-bottom: 8px; }
.feature p { font-size: 13px; color: #94a3b8; line-height: 1.6; }

.how-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 40px 0; }
@media (max-width: 768px) { .how-grid { grid-template-columns: repeat(2, 1fr); } }
.how-step { text-align: center; }
.how-num {
    width: 48px; height: 48px; border-radius: 14px; display: flex;
    align-items: center; justify-content: center; margin: 0 auto 12px;
    font-size: 22px; font-weight: 800; font-family: 'JetBrains Mono', monospace;
}
.how-step h4 { font-size: 14px; font-weight: 700; color: #fff; margin-bottom: 6px; }
.how-step p { font-size: 12px; color: #94a3b8; }

.section-label {
    display: inline-flex; align-items: center; gap: 8px; padding: 5px 14px;
    border-radius: 999px; font-size: 12px; font-weight: 600; color: #59b2ff;
    background: rgba(59,145,255,0.06); border: 1px solid rgba(59,145,255,0.1);
    margin-bottom: 12px;
}
.section-title {
    font-size: clamp(28px, 4vw, 40px); font-weight: 800; color: #fff;
    letter-spacing: -0.02em; margin-bottom: 8px;
}
.section-sub { font-size: 15px; color: #94a3b8; margin-bottom: 32px; }
.section { text-align: center; padding: 50px 0; }

.demo-card {
    background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; padding: 24px;
    max-width: 500px; margin: 0 auto; text-align: left;
}
.demo-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.demo-left { display: flex; align-items: center; gap: 12px; }
.demo-icon {
    width: 40px; height: 40px; border-radius: 10px;
    background: linear-gradient(135deg,#1a6ff5,#1448b6);
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; color: #fff; font-size: 16px;
}
.demo-ticker { font-size: 18px; font-weight: 700; color: #fff; }
.demo-name { font-size: 12px; color: #64748b; }
.demo-price { font-size: 16px; font-weight: 700; color: #fff; font-family: 'JetBrains Mono', monospace; }
.demo-pull { font-size: 11px; color: #ef4444; font-family: 'JetBrains Mono', monospace; }
.demo-metrics { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-top: 16px; }
.demo-met {
    background: #151a24; border-radius: 8px; padding: 8px 4px; text-align: center;
}
.demo-met-label { font-size: 9px; color: #64748b; text-transform: uppercase; letter-spacing: 0.06em; }
.demo-met-val { font-size: 14px; font-weight: 700; font-family: 'JetBrains Mono', monospace; margin-top: 2px; }

.footer {
    text-align: center; padding: 40px 0 20px;
    border-top: 1px solid rgba(255,255,255,0.04);
    font-size: 12px; color: #475569;
}
</style>

<div class="landing">

<!-- HERO -->
<div class="hero">
    <div class="live-badge">Live screening 3,000+ large-cap stocks</div>
    <h1>Catch the <span>Reversal.</span><br>Before the Crowd.</h1>
    <p>AI-powered screener that finds large-cap stocks bouncing off the 150 & 200-day SMA with RSI confirmation and full fundamental analysis.</p>
</div>
</div>

<!-- FEATURES -->
<div class="landing">
<div class="section">
    <div class="section-label">Core Engine</div>
    <div class="section-title">Technical Precision Meets<br>Fundamental Depth</div>
    <div class="section-sub">Every signal is validated by a multi-layer screening engine.</div>
</div>

<div class="features">
    <div class="feature">
        <div class="feature-icon" style="background:rgba(59,145,255,0.1);">📈</div>
        <h3>150 & 200 SMA Bounce</h3>
        <p>Detects when price is above and within 2% of the 150 or 200-day moving average — institutional support levels where smart money accumulates.</p>
    </div>
    <div class="feature">
        <div class="feature-icon" style="background:rgba(147,51,234,0.1);">📊</div>
        <h3>RSI Oversold Confirmation</h3>
        <p>Requires RSI(14) to drop below 30 before confirming the bounce. Filters out weak pullbacks and catches genuine oversold reversals.</p>
    </div>
    <div class="feature">
        <div class="feature-icon" style="background:rgba(34,197,94,0.1);">✅</div>
        <h3>Candle Confirmation</h3>
        <p>Waits for 2-3 consecutive candles to close above the SMA. Reduces false positives and confirms directional momentum.</p>
    </div>
    <div class="feature">
        <div class="feature-icon" style="background:rgba(251,146,60,0.1);">💰</div>
        <h3>Deep Fundamentals</h3>
        <p>Revenue growth, profit margins, P/E ratios, debt-to-equity, ROE. Automatically excludes companies with negative revenue growth.</p>
    </div>
    <div class="feature">
        <div class="feature-icon" style="background:rgba(6,182,212,0.1);">📱</div>
        <h3>Telegram Alerts</h3>
        <p>Get instant Telegram notifications with styled card images when high-probability setups trigger. Never miss a reversal.</p>
    </div>
    <div class="feature">
        <div class="feature-icon" style="background:rgba(225,29,72,0.1);">🌐</div>
        <h3>Cloud Auto-Scan</h3>
        <p>GitHub Actions runs the scan daily after market close — even when your computer is off. Fully automated, completely free.</p>
    </div>
</div>

<!-- HOW IT WORKS -->
<div class="section">
    <div class="section-label">The Algorithm</div>
    <div class="section-title">4-Layer Signal Validation</div>
    <div class="section-sub">Every stock passes through four independent filters.</div>
</div>

<div class="how-grid">
    <div class="how-step">
        <div class="how-num" style="background:rgba(59,145,255,0.15);color:#59b2ff;">1</div>
        <h4>Pullback Filter</h4>
        <p>Stock must be 12%+ below its 52-week high</p>
    </div>
    <div class="how-step">
        <div class="how-num" style="background:rgba(147,51,234,0.15);color:#a855f7;">2</div>
        <h4>SMA Support</h4>
        <p>Price is above and within 2% of the 150 or 200-day SMA</p>
    </div>
    <div class="how-step">
        <div class="how-num" style="background:rgba(34,197,94,0.15);color:#22c55e;">3</div>
        <h4>RSI + Confirmation</h4>
        <p>RSI below 30 confirmed by 3 candles closing above SMA</p>
    </div>
    <div class="how-step">
        <div class="how-num" style="background:rgba(251,146,60,0.15);color:#fb923c;">4</div>
        <h4>Fundamental Check</h4>
        <p>Positive revenue growth, margins and debt validated</p>
    </div>
</div>

<!-- DEMO CARD -->
<div class="section">
    <div class="section-label">Sample Output</div>
    <div class="section-title">What You'll See</div>
    <div class="section-sub">Each signal comes with a full breakdown.</div>
</div>

<div class="demo-card">
    <div class="demo-header">
        <div class="demo-left">
            <div class="demo-icon">A</div>
            <div>
                <div class="demo-ticker">AAPL <span style="font-size:12px;font-weight:400;color:#64748b;margin-left:4px;">Apple Inc.</span></div>
                <div class="demo-name">Technology | Consumer Electronics</div>
            </div>
        </div>
        <div style="text-align:right;">
            <div class="demo-price">$185.40</div>
            <div class="demo-pull">-14.2% from high</div>
        </div>
    </div>
    <div class="demo-metrics">
        <div class="demo-met"><div class="demo-met-label">Signal</div><div class="demo-met-val" style="color:#fff;">Mar 20</div></div>
        <div class="demo-met"><div class="demo-met-label">RSI</div><div class="demo-met-val" style="color:#59b2ff;">28.3</div></div>
        <div class="demo-met"><div class="demo-met-label">SMA</div><div class="demo-met-val" style="color:#fb923c;">200d</div></div>
        <div class="demo-met"><div class="demo-met-label">Rev</div><div class="demo-met-val" style="color:#22c55e;">+15.7%</div></div>
        <div class="demo-met"><div class="demo-met-label">P/E</div><div class="demo-met-val" style="color:#fff;">32.1</div></div>
    </div>
</div>

<!-- FOOTER -->
<div class="footer">
    Not financial advice. For educational purposes only.<br>
    Built with ReversalIQ
</div>

</div>
"""

st.markdown(LANDING_HTML, unsafe_allow_html=True)

# CTA button using Streamlit (navigates to Screener page)
st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("🔍  Launch Screener", type="primary", use_container_width=True):
        st.switch_page("pages/1_Screener.py")

import os


def _safe_fmt(val, fmt=".1f", multiply=1):
    """Safely format a numeric value that might be a string."""
    if val is None:
        return None
    try:
        return f"{float(val) * multiply:{fmt}}"
    except (ValueError, TypeError):
        return str(val)


def notify_new_signals(current_symbols: list, previous_symbols: set):
    """Show toast notifications for newly detected signals."""
    try:
        import streamlit as st
    except Exception:
        return

    if not previous_symbols:
        return
    new = [s for s in current_symbols if s not in previous_symbols]
    if new:
        st.toast(f"New signals detected: {', '.join(new[:10])}", icon="🚨")
    removed = [s for s in previous_symbols if s not in current_symbols]
    if removed:
        st.toast(f"Signals no longer active: {', '.join(removed[:10])}", icon="📉")


def _build_message(results: list[dict]) -> str:
    """Build a formatted WhatsApp message."""
    lines = [
        "📊 *ReversalIQ — Reversal Signals*",
        f"_{len(results)} stock{'s' if len(results) != 1 else ''} detected_",
        "",
    ]

    for idx, r in enumerate(results[:10]):
        fund = r.get("fundamentals", {})
        name = fund.get("longName", r["symbol"])
        sector = fund.get("sector", "")
        industry = fund.get("industry", "")

        try:
            from datetime import datetime as _dt
            sig_date = _dt.strptime(r["signal_date"], "%Y-%m-%d").strftime("%b %d")
        except Exception:
            sig_date = r["signal_date"]

        lines.append(f"*{r['symbol']}*  {name}")
        lines.append(f"{sector} | {industry}")
        lines.append(f"💰 *${r['current_price']}*  ·  📉 -{r['pullback_pct']}% from high")
        lines.append("")
        lines.append(f"Signal: *{sig_date}*  ·  RSI: *{r['rsi_at_signal']}*  ·  SMA: *{r['sma_period']}d*")

        rev_g = fund.get("revenueGrowth")
        pe = fund.get("trailingPE")
        pm = fund.get("profitMargins")

        fund_parts = []
        rev_str = _safe_fmt(rev_g, multiply=100)
        if rev_str is not None:
            fund_parts.append(f"Rev: +{rev_str}%")
        pm_str = _safe_fmt(pm, multiply=100)
        if pm_str is not None:
            fund_parts.append(f"Margin: {pm_str}%")
        pe_str = _safe_fmt(pe)
        if pe_str is not None:
            fund_parts.append(f"P/E: {pe_str}")
        if fund_parts:
            lines.append("  ·  ".join(fund_parts))

        lines.append("")
        lines.append(
            f"{r['symbol']} triggered a reversal when RSI dropped to "
            f"*{r['rsi_at_signal']}* while price was within "
            f"{r['sma_distance_pct']}% of its {r['sma_period']}-day SMA."
        )

        if idx < min(len(results), 10) - 1:
            lines.append("")
            lines.append("─" * 30)
            lines.append("")

    if len(results) > 10:
        lines.append("")
        lines.append(f"_+{len(results) - 10} more signals in the app_")

    lines.append("")
    lines.append("─" * 30)
    lines.append("_Sent by ReversalIQ_")

    return "\n".join(lines)


def send_whatsapp(phone: str, results: list[dict], wait_time: int = 15) -> bool:
    """
    Send scan results via WhatsApp using pywhatkit text message.
    Opens WhatsApp Web and sends automatically.
    """
    if not phone or not results:
        return False

    try:
        import pywhatkit as kit

        message = _build_message(results)
        kit.sendwhatmsg_instantly(
            phone_no=phone,
            message=message,
            wait_time=wait_time,
            tab_close=True,
        )
        return True
    except Exception as e:
        print(f"WhatsApp send error: {e}")
        return False

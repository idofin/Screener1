import streamlit as st


def _safe_fmt(val, fmt=".1f", multiply=1):
    """Safely format a numeric value that might be a string."""
    if val is None:
        return None
    try:
        return f"{float(val) * multiply:{fmt}}"
    except (ValueError, TypeError):
        return str(val)


def notify_new_signals(current_symbols: list[str], previous_symbols: set):
    """Show toast notifications for newly detected signals."""
    if not previous_symbols:
        return

    new = [s for s in current_symbols if s not in previous_symbols]
    if new:
        st.toast(f"New signals detected: {', '.join(new[:10])}", icon="🚨")

    removed = [s for s in previous_symbols if s not in current_symbols]
    if removed:
        st.toast(f"Signals no longer active: {', '.join(removed[:10])}", icon="📉")


def _build_message(results: list[dict]) -> str:
    """Build a formatted message from scan results."""
    lines = ["Stock Reversal Screener Alert", ""]
    for r in results[:10]:
        fund = r.get("fundamentals", {})
        name = fund.get("longName", r["symbol"])
        rev_g = fund.get("revenueGrowth")
        pe = fund.get("trailingPE")
        pm = fund.get("profitMargins")

        lines.append(f"{r['symbol']} - {name}")
        lines.append(f"  Signal: {r['signal_date']} | RSI: {r['rsi_at_signal']}")
        lines.append(f"  Price: ${r['price_at_signal']} > Now: ${r['current_price']}")
        lines.append(f"  Pullback: {r['pullback_pct']}% from ${r['high_52w']}")
        lines.append(f"  SMA-{r['sma_period']}: ${r['sma_value']} ({r['sma_distance_pct']}% away)")

        detail_parts = []
        rev_str = _safe_fmt(rev_g, multiply=100)
        if rev_str is not None:
            detail_parts.append(f"Rev Growth: {rev_str}%")
        pm_str = _safe_fmt(pm, multiply=100)
        if pm_str is not None:
            detail_parts.append(f"Margin: {pm_str}%")
        pe_str = _safe_fmt(pe)
        if pe_str is not None:
            detail_parts.append(f"P/E: {pe_str}")
        if detail_parts:
            lines.append(f"  {' | '.join(detail_parts)}")
        lines.append("")

    if len(results) > 10:
        lines.append(f"...and {len(results) - 10} more. Check the app for full results.")

    lines.append("Sent by ReversalIQ Stock Screener")
    return "\n".join(lines)


def send_whatsapp(phone: str, results: list[dict], wait_time: int = 15) -> bool:
    """
    Send scan results via WhatsApp using pywhatkit.
    Opens WhatsApp Web in your browser and sends the message.

    Args:
        phone: Phone number with country code, e.g. "+972501234567"
        results: List of scan result dicts
        wait_time: Seconds to wait for WhatsApp Web to load (default 15)
    """
    if not phone or not results:
        return False

    try:
        import pywhatkit as kit

        message = _build_message(results)

        # sendwhatmsg_instantly opens WhatsApp Web and sends right away
        kit.sendwhatmsg_instantly(
            phone_no=phone,
            message=message,
            wait_time=wait_time,
            tab_close=True,
        )
        return True
    except Exception as e:
        st.error(f"WhatsApp send error: {e}")
        return False

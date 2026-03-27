"""
Telegram alert system for ReversalIQ.
Sends styled text messages and card images to your Telegram.

Setup (one-time, 2 minutes):
1. Open Telegram, search for @BotFather
2. Send /newbot, pick a name (e.g. "ReversalIQ Bot")
3. Copy the token it gives you
4. Send any message to your new bot
5. Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
6. Find your chat_id in the response
7. Set these as environment variables or pass them directly:
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_CHAT_ID=your_chat_id
"""
import os
import requests


def _safe_fmt(val, fmt=".1f", multiply=1):
    if val is None:
        return None
    try:
        return f"{float(val) * multiply:{fmt}}"
    except (ValueError, TypeError):
        return str(val)


def send_telegram_message(text: str, token: str = None, chat_id: str = None) -> bool:
    """Send a text message via Telegram Bot API."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("Telegram credentials not set")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }, timeout=15)

    if resp.status_code == 200:
        return True
    else:
        print(f"Telegram API error: {resp.status_code} {resp.text}")
        return False


def send_telegram_image(image_path: str, caption: str = "",
                        token: str = None, chat_id: str = None) -> bool:
    """Send an image via Telegram Bot API."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("Telegram credentials not set")
        return False

    # Send as document to avoid Telegram's photo compression
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with open(image_path, "rb") as img:
        resp = requests.post(url, data={
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "Markdown",
        }, files={"document": (os.path.basename(image_path), img, "image/png")}, timeout=30)

    if resp.status_code == 200:
        return True
    else:
        print(f"Telegram image error: {resp.status_code} {resp.text}")
        return False


def build_signal_message(results: list[dict]) -> str:
    """Build a Telegram-formatted message from scan results."""
    lines = [
        "📊 *ReversalIQ — Reversal Signals*",
        f"_{len(results)} stock{'s' if len(results) != 1 else ''} detected_",
        "",
    ]

    for idx, r in enumerate(results[:15]):
        fund = r.get("fundamentals", {})
        name = fund.get("longName", r["symbol"])
        sector = fund.get("sector", "")

        try:
            from datetime import datetime
            sig_date = datetime.strptime(r["signal_date"], "%Y-%m-%d").strftime("%b %d")
        except Exception:
            sig_date = r["signal_date"]

        lines.append(f"🔹 *{r['symbol']}* — {name}")
        lines.append(f"💰 *${r['current_price']}*  ·  📉 -{r['pullback_pct']}% from high")
        lines.append(f"Signal: *{sig_date}*  ·  RSI: *{r['rsi_at_signal']}*  ·  SMA: *{r['sma_period']}d*")

        fund_parts = []
        rev_str = _safe_fmt(fund.get("revenueGrowth"), multiply=100)
        if rev_str is not None:
            fund_parts.append(f"Rev: +{rev_str}%")
        pm_str = _safe_fmt(fund.get("profitMargins"), multiply=100)
        if pm_str is not None:
            fund_parts.append(f"Margin: {pm_str}%")
        pe_str = _safe_fmt(fund.get("trailingPE"))
        if pe_str is not None:
            fund_parts.append(f"P/E: {pe_str}")
        if fund_parts:
            lines.append(" · ".join(fund_parts))

        if idx < min(len(results), 15) - 1:
            lines.append("")

    if len(results) > 15:
        lines.append(f"\n_+{len(results) - 15} more signals_")

    lines.append("")
    lines.append("_Sent by ReversalIQ_")

    return "\n".join(lines)


def send_alerts(results: list[dict], token: str = None, chat_id: str = None) -> bool:
    """
    Send scan results via Telegram — text message + card images.
    This is the main function to call from the screener.
    """
    if not results:
        return False

    # Send text summary
    message = build_signal_message(results)
    text_ok = send_telegram_message(message, token, chat_id)

    # Send card images
    try:
        from card_renderer import render_signal_card
        cache_dir = os.path.join(os.path.dirname(__file__), "cache")
        os.makedirs(cache_dir, exist_ok=True)

        for r in results[:5]:  # Send top 5 as individual card images
            img_path = os.path.join(cache_dir, f"tg_{r['symbol']}.png")
            render_signal_card(r, img_path)
            fund = r.get("fundamentals", {})
            caption = f"*{r['symbol']}* — {fund.get('longName', r['symbol'])}"
            send_telegram_image(img_path, caption, token, chat_id)
    except Exception as e:
        print(f"Card image send failed: {e}")

    return text_ok

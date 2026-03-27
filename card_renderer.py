"""Renders signal cards as high-resolution PNG images matching the app's dark glassmorphism design."""
import os
import platform
from PIL import Image, ImageDraw, ImageFont


# ── Colors ──
BG = (5, 6, 10)
CARD_BG = (15, 18, 25)
CARD_BORDER = (40, 48, 65)
METRIC_BG = (21, 26, 36)
WHITE = (226, 232, 240)
MUTED = (148, 163, 184)
BRAND = (89, 178, 255)
GREEN = (34, 197, 94)
RED = (239, 68, 68)
ORANGE = (251, 146, 60)

ICON_COLORS = [
    ((26, 111, 245), (20, 72, 182)),
    ((22, 163, 74), (21, 128, 61)),
    ((147, 51, 234), (126, 34, 206)),
    ((234, 88, 12), (194, 65, 12)),
    ((8, 145, 178), (14, 116, 144)),
    ((225, 29, 72), (190, 18, 60)),
]

# Render at 2x for sharp Telegram images, then scale if needed
SCALE = 2


def _safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _get_font(size, bold=False):
    """Load a font, works on both Windows and Linux (GitHub Actions)."""
    size = size * SCALE

    # Windows fonts
    win_fonts = (
        ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"]
        if bold else
        ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    )
    # Linux fonts (GitHub Actions / Ubuntu)
    linux_fonts = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
    )

    for path in win_fonts + linux_fonts:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def s(val):
    """Scale a value by the SCALE factor."""
    return int(val * SCALE)


def render_signal_card(result: dict, output_path: str) -> str:
    """Render a single signal card as a high-resolution PNG."""
    fund = result.get("fundamentals", {})
    sym = result["symbol"]
    name = fund.get("longName", sym)
    sector = fund.get("sector", "N/A")
    industry = fund.get("industry", "")

    try:
        from datetime import datetime
        sig_date = datetime.strptime(result["signal_date"], "%Y-%m-%d").strftime("%b %d")
    except Exception:
        sig_date = result["signal_date"]

    rev_g = _safe_float(fund.get("revenueGrowth"))
    pe = _safe_float(fund.get("trailingPE"))
    pm = _safe_float(fund.get("profitMargins"))
    dte = _safe_float(fund.get("debtToEquity"))

    # ── Canvas (2x resolution) ──
    W, H = s(720), s(340)
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    # ── Fonts ──
    f_ticker = _get_font(24, bold=True)
    f_name = _get_font(14)
    f_sector = _get_font(12)
    f_price = _get_font(22, bold=True)
    f_pullback = _get_font(12, bold=True)
    f_label = _get_font(10)
    f_value = _get_font(17, bold=True)
    f_body = _get_font(13)
    f_badge = _get_font(10, bold=True)

    # ── Card background with subtle gradient effect ──
    card_x, card_y = s(16), s(16)
    card_w, card_h = W - s(32), H - s(32)
    # Outer glow
    draw.rounded_rectangle(
        [card_x - s(1), card_y - s(1), card_x + card_w + s(1), card_y + card_h + s(1)],
        radius=s(18), fill=None, outline=(59, 145, 255, 20), width=s(1)
    )
    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h],
        radius=s(16), fill=CARD_BG, outline=CARD_BORDER, width=s(1)
    )

    # ── Stock Icon ──
    icon_x, icon_y = card_x + s(24), card_y + s(24)
    icon_sz = s(48)
    color_pair = ICON_COLORS[ord(sym[0]) % len(ICON_COLORS)]
    draw.rounded_rectangle(
        [icon_x, icon_y, icon_x + icon_sz, icon_y + icon_sz],
        radius=s(14), fill=color_pair[0]
    )
    # Icon shadow
    draw.rounded_rectangle(
        [icon_x + s(1), icon_y + s(1), icon_x + icon_sz + s(1), icon_y + icon_sz + s(1)],
        radius=s(14), fill=(0, 0, 0, 40)
    )
    draw.rounded_rectangle(
        [icon_x, icon_y, icon_x + icon_sz, icon_y + icon_sz],
        radius=s(14), fill=color_pair[0]
    )
    letter = sym[0]
    lbox = draw.textbbox((0, 0), letter, font=f_ticker)
    lw, lh = lbox[2] - lbox[0], lbox[3] - lbox[1]
    draw.text(
        (icon_x + (icon_sz - lw) // 2, icon_y + (icon_sz - lh) // 2 - s(2)),
        letter, fill=WHITE, font=f_ticker
    )

    # ── Ticker + Name + Badge ──
    text_x = icon_x + icon_sz + s(16)
    draw.text((text_x, icon_y + s(2)), sym, fill=WHITE, font=f_ticker)
    ticker_w = draw.textbbox((0, 0), sym, font=f_ticker)[2]
    draw.text((text_x + ticker_w + s(10), icon_y + s(8)), name, fill=MUTED, font=f_name)

    # Reversal Signal badge
    badge_text = "Reversal Signal"
    badge_w = draw.textbbox((0, 0), badge_text, font=f_badge)[2] + s(16)
    badge_x = text_x + ticker_w + s(10) + draw.textbbox((0, 0), name, font=f_name)[2] + s(12)
    if badge_x + badge_w > card_x + card_w - s(20):
        badge_x = text_x  # Move to next line area if too long
        badge_y_offset = s(0)
    else:
        badge_y_offset = s(4)
    draw.rounded_rectangle(
        [badge_x, icon_y + badge_y_offset, badge_x + badge_w, icon_y + badge_y_offset + s(20)],
        radius=s(10), fill=(34, 197, 94, 20), outline=(34, 197, 94, 60)
    )
    # Green dot
    dot_x = badge_x + s(8)
    dot_y = icon_y + badge_y_offset + s(7)
    draw.ellipse([dot_x, dot_y, dot_x + s(6), dot_y + s(6)], fill=GREEN)
    draw.text((dot_x + s(10), icon_y + badge_y_offset + s(3)), badge_text, fill=GREEN, font=f_badge)

    # Sector line
    sector_text = f"{sector} | {industry}" if industry else sector
    draw.text((text_x, icon_y + s(32)), sector_text, fill=MUTED, font=f_sector)

    # ── Price + Pullback (right aligned) ──
    price_str = f"${result['current_price']}"
    pbox = draw.textbbox((0, 0), price_str, font=f_price)
    pw = pbox[2] - pbox[0]
    draw.text((card_x + card_w - s(24) - pw, icon_y + s(2)), price_str, fill=WHITE, font=f_price)

    pullback_str = f"-{result['pullback_pct']}% from high"
    pbox2 = draw.textbbox((0, 0), pullback_str, font=f_pullback)
    pw2 = pbox2[2] - pbox2[0]
    draw.text((card_x + card_w - s(24) - pw2, icon_y + s(32)), pullback_str, fill=RED, font=f_pullback)

    # ── Metrics row ──
    metrics_y = icon_y + icon_sz + s(28)
    metrics = [
        ("Signal", sig_date, WHITE),
        ("RSI", str(result["rsi_at_signal"]), BRAND),
        ("SMA", f"{result['sma_period']}d", ORANGE),
    ]
    if rev_g is not None:
        metrics.append(("Rev", f"+{rev_g * 100:.1f}%", GREEN))
    if pe is not None:
        metrics.append(("P/E", f"{pe:.1f}", WHITE))
    if pm is not None and len(metrics) < 6:
        metrics.append(("Margin", f"{pm * 100:.1f}%", WHITE))
    if dte is not None and len(metrics) < 6:
        metrics.append(("D/E", f"{dte:.1f}", WHITE))

    num_metrics = len(metrics)
    metric_gap = s(8)
    metric_w = (card_w - s(48) - (num_metrics - 1) * metric_gap) // num_metrics
    metric_h = s(56)

    for i, (label, value, color) in enumerate(metrics):
        mx = card_x + s(24) + i * (metric_w + metric_gap)
        draw.rounded_rectangle(
            [mx, metrics_y, mx + metric_w, metrics_y + metric_h],
            radius=s(10), fill=METRIC_BG
        )
        # Label
        lbox = draw.textbbox((0, 0), label, font=f_label)
        lw = lbox[2] - lbox[0]
        draw.text((mx + (metric_w - lw) // 2, metrics_y + s(8)), label, fill=MUTED, font=f_label)
        # Value
        vbox = draw.textbbox((0, 0), value, font=f_value)
        vw = vbox[2] - vbox[0]
        draw.text((mx + (metric_w - vw) // 2, metrics_y + s(28)), value, fill=color, font=f_value)

    # ── Explanation text ──
    text_y = metrics_y + metric_h + s(20)
    max_text_w = card_w - s(48)

    explanation = (
        f"{sym} triggered a reversal signal when RSI(14) dropped to "
        f"{result['rsi_at_signal']} while the price was within {result['sma_distance_pct']}% of "
        f"its {result['sma_period']}-day SMA."
    )
    if rev_g is not None and rev_g > 0:
        pm_str = f" with {pm * 100:.0f}% profit margins" if pm else ""
        explanation += f" Revenue growing at {rev_g * 100:.1f}%{pm_str}."

    wrapped = _wrap_text(draw, explanation, f_body, max_text_w)
    for line_text in wrapped[:3]:
        draw.text((card_x + s(24), text_y), line_text, fill=MUTED, font=f_body)
        text_y += s(20)

    img.save(output_path, "PNG")
    return output_path


def render_summary_image(results: list[dict], output_path: str) -> str:
    """Render all signals into a single tall image."""
    if not results:
        return ""

    card_h = s(340)
    gap = s(8)
    count = min(len(results), 10)
    total_h = count * card_h + (count - 1) * gap + s(32)
    W = s(720)

    summary = Image.new("RGB", (W, total_h), BG)

    for i, r in enumerate(results[:10]):
        card_path = output_path + f"_tmp_{i}.png"
        render_signal_card(r, card_path)
        card_img = Image.open(card_path)
        summary.paste(card_img, (0, s(16) + i * (card_h + gap)))
        card_img.close()
        os.remove(card_path)

    summary.save(output_path, "PNG")
    return output_path


def _wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

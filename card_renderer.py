"""Renders signal cards as PNG images matching the app's dark glassmorphism design."""
import os
from PIL import Image, ImageDraw, ImageFont


# ── Colors ──
BG = (5, 6, 10)
CARD_BG = (15, 18, 25)
CARD_BORDER = (40, 48, 65)
METRIC_BG = (21, 26, 36)
WHITE = (226, 232, 240)
MUTED = (100, 116, 139)
BRAND = (89, 178, 255)
GREEN = (34, 197, 94)
RED = (239, 68, 68)
ORANGE = (251, 146, 60)

# Icon background colors
ICON_COLORS = [
    ((26, 111, 245), (20, 72, 182)),
    ((22, 163, 74), (21, 128, 61)),
    ((147, 51, 234), (126, 34, 206)),
    ((234, 88, 12), (194, 65, 12)),
    ((8, 145, 178), (14, 116, 144)),
    ((225, 29, 72), (190, 18, 60)),
]


def _safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _get_font(size, bold=False):
    """Try to load a good font, fall back to default."""
    font_names = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    if bold:
        font_names = [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ]
    for path in font_names:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def render_signal_card(result: dict, output_path: str) -> str:
    """
    Render a single signal card as a PNG image.
    Returns the output file path.
    """
    fund = result.get("fundamentals", {})
    sym = result["symbol"]
    name = fund.get("longName", sym)
    sector = fund.get("sector", "N/A")
    industry = fund.get("industry", "")

    # Format signal date
    try:
        from datetime import datetime
        sig_date = datetime.strptime(result["signal_date"], "%Y-%m-%d").strftime("%b %d")
    except Exception:
        sig_date = result["signal_date"]

    rev_g = _safe_float(fund.get("revenueGrowth"))
    pe = _safe_float(fund.get("trailingPE"))

    # ── Canvas ──
    W, H = 700, 320
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ── Fonts ──
    f_ticker = _get_font(22, bold=True)
    f_name = _get_font(14)
    f_sector = _get_font(12)
    f_price = _get_font(20, bold=True)
    f_pullback = _get_font(12, bold=True)
    f_label = _get_font(10)
    f_value = _get_font(16, bold=True)
    f_body = _get_font(13)
    f_body_bold = _get_font(13, bold=True)

    # ── Card background ──
    card_x, card_y = 16, 16
    card_w, card_h = W - 32, H - 32
    _draw_rounded_rect(draw, card_x, card_y, card_w, card_h, 16, CARD_BG, CARD_BORDER)

    # ── Icon ──
    icon_x, icon_y = card_x + 20, card_y + 20
    icon_size = 44
    color_pair = ICON_COLORS[ord(sym[0]) % len(ICON_COLORS)]
    _draw_rounded_rect(draw, icon_x, icon_y, icon_size, icon_size, 12, color_pair[0])
    # Letter centered in icon
    letter = sym[0]
    lbox = draw.textbbox((0, 0), letter, font=f_ticker)
    lw, lh = lbox[2] - lbox[0], lbox[3] - lbox[1]
    draw.text(
        (icon_x + (icon_size - lw) // 2, icon_y + (icon_size - lh) // 2 - 2),
        letter, fill=WHITE, font=f_ticker
    )

    # ── Ticker + Name ──
    text_x = icon_x + icon_size + 14
    draw.text((text_x, icon_y + 2), sym, fill=WHITE, font=f_ticker)
    # Name next to ticker
    ticker_w = draw.textbbox((0, 0), sym, font=f_ticker)[2]
    draw.text((text_x + ticker_w + 10, icon_y + 6), name, fill=MUTED, font=f_name)
    # Sector
    sector_text = f"{sector} | {industry}" if industry else sector
    draw.text((text_x, icon_y + 28), sector_text, fill=MUTED, font=f_sector)

    # ── Price + Pullback (right side) ──
    price_str = f"${result['current_price']}"
    pbox = draw.textbbox((0, 0), price_str, font=f_price)
    pw = pbox[2] - pbox[0]
    price_x = card_x + card_w - 20 - pw
    draw.text((price_x, icon_y), price_str, fill=WHITE, font=f_price)

    pullback_str = f"-{result['pullback_pct']}% from high"
    pbox2 = draw.textbbox((0, 0), pullback_str, font=f_pullback)
    pw2 = pbox2[2] - pbox2[0]
    draw.text((card_x + card_w - 20 - pw2, icon_y + 28), pullback_str, fill=RED, font=f_pullback)

    # ── Metrics row ──
    metrics_y = icon_y + icon_size + 24
    metrics = [
        ("Signal", sig_date, WHITE),
        ("RSI", str(result["rsi_at_signal"]), BRAND),
        ("SMA", f"{result['sma_period']}d", ORANGE),
    ]
    # Add Rev if available
    if rev_g is not None:
        rev_str = f"+{rev_g*100:.1f}%"
        metrics.append(("Rev", rev_str, GREEN))
    # Add P/E if available
    if pe is not None:
        metrics.append(("P/E", f"{pe:.1f}", WHITE))

    num_metrics = len(metrics)
    metric_gap = 8
    metric_w = (card_w - 40 - (num_metrics - 1) * metric_gap) // num_metrics
    metric_h = 52

    for i, (label, value, color) in enumerate(metrics):
        mx = card_x + 20 + i * (metric_w + metric_gap)
        _draw_rounded_rect(draw, mx, metrics_y, metric_w, metric_h, 8, METRIC_BG)

        # Label centered
        lbox = draw.textbbox((0, 0), label, font=f_label)
        lw = lbox[2] - lbox[0]
        draw.text((mx + (metric_w - lw) // 2, metrics_y + 8), label, fill=MUTED, font=f_label)

        # Value centered
        vbox = draw.textbbox((0, 0), value, font=f_value)
        vw = vbox[2] - vbox[0]
        draw.text((mx + (metric_w - vw) // 2, metrics_y + 24), value, fill=color, font=f_value)

    # ── Explanation text ──
    text_y = metrics_y + metric_h + 20
    max_text_w = card_w - 40

    # Build explanation
    explanation = (
        f"{sym} triggered a reversal signal when RSI(14) dropped to "
        f"{result['rsi_at_signal']} while the price was within {result['sma_distance_pct']}% of "
        f"its {result['sma_period']}-day SMA."
    )
    if rev_g is not None and rev_g > 0:
        pm = _safe_float(fund.get("profitMargins"))
        pm_str = f" with {pm*100:.0f}% profit margins" if pm else ""
        explanation += f" Revenue growing at {rev_g*100:.1f}%{pm_str}."

    # Word wrap
    wrapped = _wrap_text(draw, explanation, f_body, max_text_w)
    for line_text in wrapped[:3]:  # Max 3 lines
        # Bold the numbers
        draw.text((card_x + 20, text_y), line_text, fill=MUTED, font=f_body)
        text_y += 18

    img.save(output_path, "PNG", quality=95)
    return output_path


def render_all_cards(results: list[dict], output_dir: str) -> list[str]:
    """Render all result cards as individual PNGs. Returns list of file paths."""
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    for i, r in enumerate(results[:10]):
        path = os.path.join(output_dir, f"signal_{r['symbol']}.png")
        render_signal_card(r, path)
        paths.append(path)
    return paths


def render_summary_image(results: list[dict], output_path: str) -> str:
    """Render all signals into a single tall image."""
    if not results:
        return ""

    card_h = 320
    gap = 12
    count = min(len(results), 10)
    total_h = count * card_h + (count - 1) * gap + 32
    W = 700

    summary = Image.new("RGB", (W, total_h), BG)

    for i, r in enumerate(results[:10]):
        # Render individual card
        card_path = output_path + f"_tmp_{i}.png"
        render_signal_card(r, card_path)
        card_img = Image.open(card_path)
        summary.paste(card_img, (0, 16 + i * (card_h + gap)))
        card_img.close()
        os.remove(card_path)

    summary.save(output_path, "PNG", quality=95)
    return output_path


def _draw_rounded_rect(draw, x, y, w, h, r, fill, outline=None):
    """Draw a rounded rectangle."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=fill, outline=outline)


def _wrap_text(draw, text, font, max_width):
    """Simple word-wrap for text."""
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

import pandas as pd
from indicators import compute_rsi, compute_sma
from data_fetcher import fetch_fundamentals


def _to_float(val, default=None):
    """Safely convert a value to float. Returns default if not possible."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def technical_screen(
    price_data: dict,
    rsi_threshold: float = 30.0,
    sma_periods: list = None,
    sma_proximity_pct: float = 2.0,
    pullback_pct: float = 12.0,
    confirmation_candles: int = 3,
    lookback_days: int = 30,
    progress_callback=None,
    stop_flag=None,
) -> list[dict]:
    """
    Screen stocks for reversal setup:
    1. RSI drops below threshold
    2. Price is near 150 or 200 SMA
    3. Pullback from 52-week high >= pullback_pct
    4. Next N candles close above the SMA (confirmation)
    """
    if sma_periods is None:
        sma_periods = [150, 200]

    candidates = []
    symbols = list(price_data.keys())

    for idx, symbol in enumerate(symbols):
        if stop_flag and stop_flag():
            break
        if progress_callback:
            progress_callback(idx, len(symbols), f"Screening {symbol}...")

        try:
            df = price_data[symbol].copy()
            if len(df) < max(sma_periods) + lookback_days:
                continue

            close = df["Close"].squeeze() if isinstance(df["Close"], pd.DataFrame) else df["Close"]

            # Compute indicators
            rsi = compute_rsi(close)
            smas = {p: compute_sma(close, p) for p in sma_periods}
            high_52w = close.rolling(window=252, min_periods=50).max()

            # Scan last N trading days for signal
            scan_start = max(0, len(df) - lookback_days - confirmation_candles)
            scan_end = len(df) - confirmation_candles

            for i in range(scan_end - 1, scan_start - 1, -1):
                if pd.isna(rsi.iloc[i]) or rsi.iloc[i] > rsi_threshold:
                    continue

                price_at_signal = close.iloc[i]
                h52 = high_52w.iloc[i]

                if pd.isna(h52) or h52 == 0:
                    continue

                pullback = (h52 - price_at_signal) / h52 * 100
                if pullback < pullback_pct:
                    continue

                # Check price is above SMA and within proximity %
                for period in sma_periods:
                    sma_val = smas[period].iloc[i]
                    if pd.isna(sma_val) or sma_val == 0:
                        continue

                    # Price must be AT or ABOVE the SMA (bouncing off it)
                    if price_at_signal < sma_val:
                        continue

                    distance = (price_at_signal - sma_val) / sma_val * 100
                    if distance > sma_proximity_pct:
                        continue

                    # Check confirmation candles
                    confirmed = 0
                    for j in range(1, confirmation_candles + 1):
                        if i + j < len(df):
                            if close.iloc[i + j] > sma_val:
                                confirmed += 1

                    if confirmed >= confirmation_candles:
                        # Current price must still be above the current SMA
                        current_price = close.iloc[-1]
                        current_sma = smas[period].iloc[-1]
                        if pd.isna(current_sma) or current_price < current_sma:
                            continue

                        candidates.append({
                            "symbol": symbol,
                            "signal_date": df.index[i].strftime("%Y-%m-%d") if hasattr(df.index[i], "strftime") else str(df.index[i]),
                            "rsi_at_signal": round(rsi.iloc[i], 1),
                            "price_at_signal": round(price_at_signal, 2),
                            "sma_period": period,
                            "sma_value": round(sma_val, 2),
                            "sma_distance_pct": round(distance, 2),
                            "high_52w": round(h52, 2),
                            "pullback_pct": round(pullback, 1),
                            "confirmed_candles": confirmed,
                            "current_price": round(close.iloc[-1], 2),
                        })
                        break  # Found signal for this stock, move on
                else:
                    continue
                break  # Found signal, stop scanning dates

        except Exception:
            continue

    if progress_callback:
        progress_callback(len(symbols), len(symbols), "Technical screen complete")

    return candidates


def fundamental_filter(candidates: list[dict], progress_callback=None, stop_flag=None) -> list[dict]:
    """
    Fetch fundamentals for each candidate, exclude negative revenue growth,
    and generate explanations.
    """
    enriched = []

    for idx, c in enumerate(candidates):
        if stop_flag and stop_flag():
            break
        if progress_callback:
            progress_callback(idx, len(candidates), f"Analyzing {c['symbol']}...")

        fundamentals = fetch_fundamentals(c["symbol"])

        # Coerce all numeric fields to float
        for key in ("revenueGrowth", "grossMargins", "profitMargins",
                     "operatingMargins", "trailingPE", "forwardPE",
                     "debtToEquity", "returnOnEquity", "marketCap",
                     "freeCashflow", "totalRevenue"):
            fundamentals[key] = _to_float(fundamentals.get(key))

        # Exclude negative revenue growth
        rev_growth = fundamentals.get("revenueGrowth")
        if rev_growth is not None and rev_growth < 0:
            continue

        c["fundamentals"] = fundamentals
        c["explanation"] = _generate_explanation(c, fundamentals)
        enriched.append(c)

    if progress_callback:
        progress_callback(len(candidates), len(candidates), "Fundamental analysis complete")

    return enriched


def _generate_explanation(candidate: dict, fundamentals: dict) -> str:
    """Generate a human-readable explanation for why this stock was selected."""
    sym = candidate["symbol"]
    name = fundamentals.get("longName", sym)
    sector = fundamentals.get("sector", "N/A")
    signal_date = candidate["signal_date"]
    rsi = candidate["rsi_at_signal"]
    price = candidate["price_at_signal"]
    sma_period = candidate["sma_period"]
    sma_val = candidate["sma_value"]
    sma_dist = candidate["sma_distance_pct"]
    pullback = candidate["pullback_pct"]
    high = candidate["high_52w"]
    confirmed = candidate["confirmed_candles"]

    # Use HTML tags since this renders inside an HTML div
    lines = [
        f"On {signal_date}, {sym} triggered a reversal signal when RSI(14) dropped to "
        f"<strong>{rsi}</strong> while the price (${price:,.2f}) was within "
        f"<strong>{sma_dist}%</strong> of its <strong>{sma_period}-day SMA</strong> "
        f"(${sma_val:,.2f}). The stock had pulled back <strong>{pullback}%</strong> "
        f"from its 52-week high of ${high:,.2f}.",
        "",
        f"The next <strong>{confirmed} candle(s)</strong> confirmed the reversal by "
        f"closing above the {sma_period}-day SMA, signaling potential upside momentum.",
    ]

    # Investment thesis
    
    rev_growth = fundamentals.get("revenueGrowth")
    profit_margin = fundamentals.get("profitMargins")
    pe = fundamentals.get("trailingPE")
    dte = fundamentals.get("debtToEquity")

    thesis_parts = []
    if rev_growth is not None and rev_growth > 0.1:
        thesis_parts.append("strong revenue growth")
    elif rev_growth is not None and rev_growth > 0:
        thesis_parts.append("positive revenue growth")
    if profit_margin is not None and profit_margin > 0.15:
        thesis_parts.append("healthy profit margins")
    if pe is not None and pe < 25:
        thesis_parts.append("reasonable valuation")
    elif pe is not None and pe < 40:
        thesis_parts.append("moderate valuation")
    if dte is not None and dte < 100:
        thesis_parts.append("manageable debt levels")

    if thesis_parts:
        lines.append("")
        lines.append(
            f"The fundamental picture supports the technical setup with "
            f"{', '.join(thesis_parts)}."
        )

    return "\n".join(lines)

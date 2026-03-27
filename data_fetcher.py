import time
import os
import pandas as pd
import yfinance as yf

# Allow running outside Streamlit (e.g. daily_scan.py)
try:
    import streamlit as st
    _has_st = True
except Exception:
    _has_st = False

from config import (
    BATCH_SIZE, BATCH_DELAY, CACHE_TTL, SCREENER_PAGE_SIZE,
    SP500_FALLBACK, NASDAQ100_FALLBACK, UNIVERSE_OPTIONS,
)


def _cache(func):
    """Apply st.cache_data only when running inside Streamlit."""
    if _has_st and not os.environ.get("STREAMLIT_RUNTIME") == "0":
        return st.cache_data(ttl=CACHE_TTL, show_spinner=False)(func)
    return func


@_cache
def fetch_universe(universe_name: str, count: int) -> list[str]:
    """
    Get a list of stock tickers for the chosen universe.
    Tries yfinance screener first, falls back to hardcoded lists.
    """
    if universe_name == "Custom":
        return []

    # "All US Large-Cap" and "Russell 1000" use live screener
    if universe_name in ("All US Large-Cap ($1B+)", "Russell 1000"):
        try:
            return _fetch_via_screener(count)
        except Exception:
            combined = list(dict.fromkeys(SP500_FALLBACK + NASDAQ100_FALLBACK))
            return combined[:count]

    # Try hardcoded lists first for known universes (most reliable)
    if universe_name == "S&P 500":
        return SP500_FALLBACK[:count]
    if universe_name == "NASDAQ 100":
        return NASDAQ100_FALLBACK[:count]

    # Fallback
    try:
        return _fetch_via_screener(count)
    except Exception:
        combined = list(dict.fromkeys(SP500_FALLBACK + NASDAQ100_FALLBACK))
        return combined[:count]


def _fetch_via_screener(count: int) -> list[str]:
    """Paginate through yfinance equity screener for US large-cap stocks."""
    from yfinance import EquityQuery

    query = EquityQuery("and", [
        EquityQuery("gt", ["intradaymarketcap", 1_000_000_000]),
        EquityQuery("eq", ["region", "us"]),
    ])
    symbols = []
    offset = 0

    while len(symbols) < count:
        try:
            result = yf.screen(
                query,
                sortField="intradaymarketcap",
                sortAsc=False,
                offset=offset,
                size=SCREENER_PAGE_SIZE,
            )
            quotes = result.get("quotes", [])
            if not quotes:
                break
            for q in quotes:
                sym = q.get("symbol", "")
                if sym and sym not in symbols:
                    symbols.append(sym)
            offset += SCREENER_PAGE_SIZE
            time.sleep(0.3)
        except Exception:
            break

    return symbols[:count]


@_cache
def fetch_price_data(symbols: tuple, period: str = "1y") -> dict:
    """
    Download OHLCV data in batches. Returns dict of symbol -> DataFrame.
    Accepts tuple (for Streamlit cache hashability).
    """
    all_data = {}
    symbol_list = list(symbols)

    for i in range(0, len(symbol_list), BATCH_SIZE):
        batch = symbol_list[i : i + BATCH_SIZE]
        try:
            df = yf.download(batch, period=period, group_by="ticker",
                             progress=False, threads=True)
            if len(batch) == 1:
                sym = batch[0]
                if not df.empty:
                    all_data[sym] = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            else:
                for sym in batch:
                    try:
                        sdf = df[sym][["Open", "High", "Low", "Close", "Volume"]].copy()
                        sdf = sdf.dropna(subset=["Close"])
                        if len(sdf) >= 200:
                            all_data[sym] = sdf
                    except (KeyError, TypeError):
                        continue
        except Exception:
            continue

        if i + BATCH_SIZE < len(symbol_list):
            time.sleep(BATCH_DELAY)

    return all_data


@_cache
def fetch_fundamentals(symbol: str) -> dict:
    """Fetch fundamental data for a single stock."""
    try:
        info = yf.Ticker(symbol).info
        return {
            "longName": info.get("longName", symbol),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "marketCap": info.get("marketCap"),
            "revenueGrowth": info.get("revenueGrowth"),
            "grossMargins": info.get("grossMargins"),
            "profitMargins": info.get("profitMargins"),
            "operatingMargins": info.get("operatingMargins"),
            "trailingPE": info.get("trailingPE"),
            "forwardPE": info.get("forwardPE"),
            "debtToEquity": info.get("debtToEquity"),
            "returnOnEquity": info.get("returnOnEquity"),
            "freeCashflow": info.get("freeCashflow"),
            "totalRevenue": info.get("totalRevenue"),
        }
    except Exception:
        return {"longName": symbol, "revenueGrowth": None}

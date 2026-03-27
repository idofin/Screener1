# Default screening parameters
DEFAULT_RSI_THRESHOLD = 30.0
DEFAULT_SMA_PERIODS = [150, 200]
DEFAULT_SMA_PROXIMITY_PCT = 2.0
DEFAULT_PULLBACK_PCT = 12.0
DEFAULT_CONFIRMATION_CANDLES = 3
DEFAULT_LOOKBACK_DAYS = 30

# Data fetching
BATCH_SIZE = 20
BATCH_DELAY = 1.0
CACHE_TTL = 14400  # 4 hours
SCREENER_PAGE_SIZE = 25

# Universe presets
UNIVERSE_OPTIONS = {
    "S&P 500": {"count": 500, "exchanges": ["NMS", "NYQ"]},
    "NASDAQ 100": {"count": 100, "exchanges": ["NMS"]},
    "Russell 1000": {"count": 1000, "exchanges": None},
    "Custom": {"count": None, "exchanges": None},
}

# Fallback ticker lists
SP500_FALLBACK = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "GOOG", "META", "BRK-B", "UNH", "LLY",
    "JPM", "XOM", "V", "AVGO", "JNJ", "PG", "MA", "HD", "COST", "MRK",
    "ABBV", "CVX", "CRM", "BAC", "AMD", "NFLX", "KO", "PEP", "TMO", "WMT",
    "LIN", "ACN", "CSCO", "MCD", "ABT", "DHR", "ADBE", "ORCL", "TXN", "PM",
    "CMCSA", "INTC", "WFC", "VZ", "IBM", "INTU", "COP", "AMGN", "NEE", "UNP",
    "NOW", "CAT", "RTX", "SPGI", "HON", "BA", "QCOM", "GE", "LOW", "ELV",
    "PFE", "UPS", "DE", "AMAT", "T", "BLK", "GS", "SYK", "BKNG", "ADP",
    "MDT", "ISRG", "MDLZ", "GILD", "LMT", "TJX", "MMC", "REGN", "VRTX", "CB",
    "AMT", "ADI", "ETN", "CI", "PLD", "LRCX", "PANW", "BSX", "TMUS", "MU",
    "ZTS", "SNPS", "SLB", "BDX", "SCHW", "SO", "CME", "FI", "DUK", "EOG",
    "AON", "MO", "PGR", "KLAC", "NOC", "ICE", "SHW", "CL", "WM", "CDNS",
    "APD", "MCK", "CMG", "PYPL", "GD", "ITW", "USB", "HUM", "MCO", "CTAS",
    "EMR", "PNC", "FDX", "TGT", "TDG", "PH", "NXPI", "AJG", "MSI", "ECL",
    "CSX", "PSA", "ROP", "GM", "AEP", "NSC", "MAR", "FCX", "ABNB", "ORLY",
    "AFL", "MPC", "CARR", "TFC", "PCAR", "WELL", "KMB", "D", "AZO", "HLT",
    "OKE", "MCHP", "GEV", "FTNT", "DXCM", "O", "AIG", "SRE", "SPG", "PSX",
    "NEM", "TRV", "CCI", "KDP", "DLR", "MNST", "ALL", "BK", "TEL", "ROST",
    "MSCI", "AMP", "PAYX", "KMI", "PCG", "A", "FAST", "YUM", "CTVA", "ON",
    "DVN", "IDXX", "OXY", "HCA", "DHI", "VRSK", "EXC", "PRU", "FANG", "NUE",
    "EW", "GWW", "EA", "CNC", "LHX", "GEHC", "OTIS", "KVUE", "ODFL", "CTSH",
    "CPAY", "MLM", "ACGL", "DOW", "VMC", "KR", "XEL", "KHC", "ED", "HAL",
    "EFX", "STZ", "RCL", "BKR", "MPWR", "BIIB", "DD", "WEC", "ANSS", "CBRE",
    "FITB", "PPG", "GPN", "CDW", "IRM", "EIX", "ROK", "HPQ", "HES", "MTB",
    "KEYS", "WAB", "AWK", "WBD", "TSCO", "GLW", "ULTA", "DG", "WTW", "IT",
    "TRGP", "IR", "WY", "CAH", "RMD", "BR", "CHD", "HPE", "VICI", "AVB",
    "XYL", "SW", "DOV", "HUBB", "ZBH", "IFF", "FSLR", "FTV", "SBAC", "EQR",
    "TTWO", "TYL", "PTC", "WST", "APTV", "DLTR", "STE", "CBOE", "HBAN", "PHM",
    "ILMN", "RF", "ES", "LVS", "MTD", "EQT", "MOH", "LUV", "BAX", "CFG",
    "PPL", "CINF", "FE", "LDOS", "STLD", "CSGP", "AEE", "VTR", "MKC", "LYB",
    "CLX", "IEX", "DTE", "WAT", "ARE", "NTRS", "TDY", "K", "CNP", "CMS",
    "J", "SNA", "OMC", "COO", "CF", "IP", "INVH", "BALL", "WRB", "NVR",
    "PNR", "EXPD", "LNT", "L", "MAA", "HOLX", "SYF", "TRMB", "GEN", "EG",
    "JBHT", "DGX", "NTAP", "ATO", "KIM", "SWK", "AMCR", "AVY", "POOL", "MAS",
    "AKAM", "CCL", "BG", "TECH", "EVRG", "TXT", "HST", "REG", "CPT", "ALB",
    "MGM", "UDR", "EMN", "BXP", "BBY", "NDSN", "EPAM", "PEAK", "NRG", "ZBRA",
    "IPG", "CRL", "AAL", "WBA", "FRT", "HRL", "AES", "TAP", "LKQ", "CE",
    "JKHY", "ALLE", "HSIC", "AOS", "FFIV", "GL", "DAY", "WYNN", "TPR", "ETSY",
    "BEN", "IVZ", "NWSA", "NWS", "PARA", "CZR", "MTCH", "MHK", "GNRC", "BWA",
    "HAS", "PNW", "AIZ", "SEE", "DVA", "RL", "WHR", "FMC", "BIO", "XRAY",
    "HII", "PAYC", "BBWI", "MKTX", "DPZ", "CHRW", "RHI", "SOLV", "CPB", "VTRS",
]

NASDAQ100_FALLBACK = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "GOOG", "META", "AVGO", "COST", "NFLX",
    "AMD", "PEP", "CSCO", "ADBE", "INTC", "CMCSA", "TXN", "QCOM", "INTU", "AMGN",
    "AMAT", "BKNG", "ISRG", "MDLZ", "ADI", "REGN", "VRTX", "LRCX", "PANW", "MU",
    "SNPS", "KLAC", "CDNS", "PYPL", "MCHP", "NXPI", "ORLY", "FTNT", "DXCM", "MNST",
    "KDP", "ROST", "PAYX", "ON", "IDXX", "EA", "ODFL", "CTSH", "CPAY", "BIIB",
    "ANSS", "CDW", "TTWO", "DLTR", "ILMN", "ZS", "MRNA", "LCID", "ENPH", "SIRI",
    "AZN", "TEAM", "WDAY", "CRWD", "DDOG", "ZM", "MRVL", "CTAS", "FAST", "ADP",
    "CEG", "PCAR", "HON", "EXC", "XEL", "KHC", "ABNB", "LULU", "DASH", "FANG",
    "GEHC", "TTD", "SMCI", "ARM", "COIN", "MELI", "PDD", "JD", "RIVN", "OKTA",
    "SPLK", "ALGN", "CHTR", "WBD", "VRSK", "EBAY", "GFS", "SWKS", "SBUX", "TMUS",
]

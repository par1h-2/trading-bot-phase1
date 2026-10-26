# Trading pair
DEFAULT_SYMBOL = "BTCUSDT"

# Volatility-based adaptive thresholds
VOLATILITY_MULTIPLIER = 1.5    # threshold = std_dev_pct * multiplier
MIN_TICKS_FOR_VOLATILITY = 20  # kam se kam itne price points chahiye
PRICE_HISTORY_SIZE = 50        # rolling window size

# Fallback thresholds (jab data kam ho)
FALLBACK_BUY_PCT = -2.0
FALLBACK_SELL_PCT = 2.0

# Virtual wallet
STARTING_BALANCE = 10000.0  # $10,000 virtual balance

# Polling
PRICE_POLL_INTERVAL = 20  # seconds between price checks

# Backtest defaults
BACKTEST_DEFAULT_BALANCE = 10000.0

# Sentiment keywords
POSITIVE_KEYWORDS = [
    "bullish", "surge", "rally", "gain", "profit", "growth", "adoption",
    "institutional", "etf", "approval", "record", "high", "breakout",
    "moon", "pump", "buy", "accumulate", "support", "recovery", "boom",
]

NEGATIVE_KEYWORDS = [
    "bearish", "crash", "dump", "loss", "decline", "sell", "ban",
    "regulation", "hack", "scam", "fraud", "fear", "panic", "drop",
    "plunge", "correction", "resistance", "collapse", "risk", "warning",
]

SENTIMENT_WEIGHT = 0.5
NEWS_CACHE_MINUTES = 30

# Multi-asset
COIN_UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT"]
TOP_GAINERS_COUNT = 5
TRADE_TOP_N = 2
SCAN_INTERVAL = 300  # seconds between market scans

# Stop-loss
STOP_LOSS_PCT = -5.0  # agar lot -5% se zyada gira ho to force sell

# Kronos (ML prediction - CPU optimized)
KRONOS_WEIGHT = 0.4
KRONOS_PRED_CACHE_MINUTES = 30
KRONOS_LOOKBACK_CANDLES = 200
KRONOS_PREDICT_CANDLES = 4  # kam candles = faster prediction
KRONOS_MODEL_NAME = "NeoQuasar/Kronos-small"
KRONOS_TOKENIZER_NAME = "NeoQuasar/Kronos-Tokenizer-base"

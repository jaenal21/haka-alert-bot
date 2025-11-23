# main.py – Crypto MACD Divergence Pro Bot (Final Version)

import os
import time
import threading
import logging
from datetime import datetime, timezone

import pandas as pd
import pandas_ta as ta
import ccxt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import telebot
from flask import Flask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
#  CONFIG
# =========================
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("Set TELEGRAM_TOKEN di env!")

bot = telebot.TeleBot(TOKEN)
USER_CHAT_ID = None

app = Flask(__name__)
@app.route("/")
def home():
    return "MACD Divergence Pro Bot - Running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

exchange = ccxt.binance({
    'enableRateLimit': True,
    'timeout': 30000,
})

PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "PAXG/USDT", "DOT/USDT"]
TIMEFRAMES = ["15m", "30m", "1h", "4h", "1d"]

LAST_SIGNAL = {}

# =========================
#  DIVERGENCE + MULTI-CONFIRMATION
# =========================
def detect_divergence_with_confirmation(symbol, tf):
    ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=200)
    if not ohlcv or len(ohlcv) < 100:
        return None

    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["ts"], unit="ms")

    # Indikator utama
    macd = ta.macd(df["close"])
    rsi = ta.rsi(df["close"], length=14)
    stoch_rsi = ta.stochrsi(df["close"])
    mfi = ta.mfi(df["high"], df["low"], df["close"], df["volume"])
    obv = ta.obv(df["close"], df["volume"])
    bb = ta.bbands(df["close"])
    pct_b = (df["close"] - bb["BBL_5_2.0"]) / (bb["BBU_5_2.0"] - bb["BBL_5_2.0"])

    df["MACD"] = macd["MACD_12_26_9"]
    df["Signal"] = macd["MACDs_12_26_9"]
    df["Hist"] = macd["MACDh_12_26_9"]
    df["RSI"] = rsi
    df["StochRSI"] = stoch_rsi["STOCHRSIk_14_14_3_3"]
    df["MFI"] = mfi
    df["OBV"] = obv
    df["%B"] = pct_b

    df = df.dropna().reset_index(drop=True)

    if len(df) < 50:
        return None

    # === DETEKSI DIVERGENCE ===
    def find_swing_lows_highs(series, window=5):
        lows = []
        highs = []
        for i in range(window, len(series)-window):
            if all(series[i] < series[i-j] for j in range(1, window+1)) and \
               all(series[i] < series[i+j] for j in range(1, window+1)):
                if series[i] == series.low()[i]:
                    lows.append((i, series[i]))
                if series[i] == series.high()[i]:
                    highs.append((i, series[i]))
        return lows, highs

    price_lows, price_highs = find_swing_lows_highs(df["low"])
    macd_lows, macd_highs = find_swing_lows_highs(df["Hist"])

    current = df.iloc[-1]
    signal = None
    strength = 0
    reasons = []

    key = (symbol, tf)

    # Bullish Divergence
    if len(price_lows) >= 2 and len(macd_lows) >= 2:
        p1_idx, p1_val = price_lows[-2]
        p2_idx, p2_val = price_lows[-1]
        m1_idx = min(range(len(macd_lows)), key=lambda i: abs(macd_lows[i][0] - p1_idx))
        m2_idx = min(range(len(macd_lows)), key=lambda i: abs(macd_lows[i][0] - p2_idx))

        if p2_val < p1_val and df["Hist"].iloc[macd_lows[m2_idx][0]] > df["Hist"].iloc[macd_lows[m1_idx][0]]:
            signal = "BULLISH DIVERGENCE"
            strength += 3
            reasons.append("MACD Bullish Divergence")

    # Bearish Divergence
    if len(price_highs) >= 2 and len(macd_highs) >= 2:
        p1_idx, p1_val = price_highs[-2]
        p2_idx, p2_val = price_highs[-1]
        m1_idx = min(range(len(macd_highs)), key=lambda i: abs(macd_highs[i][0] - p1_idx))
        m2_idx = min(range(len(macd_highs)), key=lambda i: abs(macd_highs[i][0] - p2_idx))

        if p2_val > p1_val and df["Hist"].iloc[macd_highs[m2_idx][0]] < df["Hist"].iloc[macd_highs[m1_idx][0]]:
            signal = "BEARISH DIVERGENCE"
            strength += 3
            reasons.append("MACD Bearish Divergence")

    if not signal:
        return None

    # === KONFRIMASI TAMBAHAN ===
    if current["RSI"] < 35:           strength += 1; reasons.append("RSI Oversold")
    if current["RSI"] > 65:           strength += 1; reasons.append("RSI Overbought")
    if current["StochRSI"] < 0.2:     strength += 1; reasons.append("StochRSI Oversold")
    if current["StochRSI"] > 0.8:     strength += 1; reasons.append("StochRSI Overbought")
    if current["MFI"] < 30:           strength += 1; reasons.append("MFI Oversold")
    if current["MFI"] > 70:           strength += 1; reasons.append("MFI Overbought")
    if current["%B"] < 0.2:           strength += 1; reasons.append("BB %B Oversold")
    if current["%B"] > 0.8:           strength += 1; reasons.append("BB %B Overbought")
    if df["OBV"].iloc[-1] > df["OBV"].iloc[-10]: reasons.append("OBV Rising")

    # Kirim hanya jika strength tinggi & belum pernah dikirim
    if strength >= 5 and LAST_SIGNAL.get(key) != signal:
        LAST_SIGNAL[key] = signal

        msg = (
            f"*MACD DIVERGENCE DETECTED*\n\n"
            f"*Pair:* `{symbol}` | *TF:* `{tf}`\n"
            f"*Signal:* *{signal}*\n"
            f"*Strength:* `{strength}/10` ⭐\n\n"
            f"Price: `{current['close']:.6f}`\n"
            f"RSI: `{current['RSI']:.2f}` | StochRSI: `{current['StochRSI']:.2f}`\n"
            f"MFI: `{current['MFI']:.2f}` | BB %B: `{current['%B']:.3f}`\n"
            f"Konfirmasi:\n" + "\n".join([f"• {r}" for r in reasons]) +
            f"\n\nWaktu: `{current['date'].strftime('%Y-%m-%d %H:%M')} UTC`"
        )
        return msg

    return None

# =========================
#  SCANNER LOOP
# =========================
def scanner_loop():
    logger.info("MACD Divergence Scanner STARTED")
    while True:
        try:
            for symbol in PAIRS:
                for tf in TIMEFRAMES:
                    msg = detect_divergence_with_confirmation(symbol, tf)
                    if msg:
                        if USER_CHAT_ID:
                            bot.send_message(USER_CHAT_ID, msg, parse_mode="Markdown")
                    time.sleep(1)
            time.sleep(60)
        except Exception as e:
            logger.error(f"Scanner error: {e}")
            time.sleep(60)

# =========================
#  TELEGRAM COMMANDS (tetap ada /tf chart)
# =========================
@bot.message_handler(commands=["start"])
def start(msg):
    global USER_CHAT_ID
    USER_CHAT_ID = msg.chat.id
    text = (
        "*MACD Divergence Pro Bot*\n\n"
        "Bot ini hanya mengirim sinyal saat ada:\n"
        "• MACD Bullish/Bearish Divergence\n"
        "• Dikonfirmasi minimal 2-3 indikator pendukung\n\n"
        "Indikator yang dipakai:\n"
        "- MACD + Histogram\n"
        "- RSI + Stochastic RSI\n"
        "- Money Flow Index (MFI)\n"
        "- Bollinger Bands %B\n"
        "- On-Balance Volume (OBV)\n\n"
        "Gunakan /tf untuk chart manual."
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# (Chart /tf tetap sama seperti versi sebelumnya – saya singkat di sini)

# =========================
#  MAIN
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=scanner_loop, daemon=True).start()
    bot.infinity_polling(none_stop=True)

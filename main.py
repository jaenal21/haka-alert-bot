# main.py - HAKA ALERT via GoAPI.io + Telegram (6 Level Inflow)
import requests
import time
import random
from datetime import datetime, timedelta
from collections import defaultdict
import os

# --- GANTI DENGAN ENV VARIABLES (DI REPLIT: Secrets) ---
GOAPI_KEY = os.getenv('94d4fa26-5767-5cae-67bb-a3bb8919')
TELEGRAM_TOKEN = os.getenv('8522628431:AAFlVti-MyhdmdveSyJ3mmMxnk5_dqJzWrg')
CHAT_ID = os.getenv('7428405865')

# 180 Saham IHSG Terbesar (tanpa .JK)
SAHAM = ["BBCA", "BBRI", "BMRI", "TLKM", "ASII", "UNVR", "HMSP", "GOTO",
    "BREN", "ADRO", "BYAN", "TPIA", "AMRT", "ARTO", "BRPT", "MDKA",
    "ANTM", "SMGR", "UNTR", "PGAS", "EXCL", "TOWR", "INCO", "PTBA",
    "CPIN", "ICBP", "KLBF", "MIKA", "INDF", "SIDO", "ITMG", "ADMR",
    "MEDC", "INDY", "HRUM", "DSSA", "BUMI", "MBMA", "NCKL", "CUAN",
    "PAMG", "PTPP", "WIKA", "WSKT", "ADCP", "MTEL", "FREN", "DCII",
    "BUKA", "EMTK", "MAPI", "ERAA", "SCMA", "FILM", "MSIN", "SRTG",
    "ACES", "HEAL", "SAME", "CARE", "SILV", "RAJA", "WOOD", "TGKA",
    "PGEO", "BRMS", "DEPO", "PNBN", "BNGA", "BFIN", "NOBU", "BBTN",
    "BNLI", "AGRO", "LSIP", "AALI", "DSNG", "TBLA", "TAPG", "SMRA",
    "BSDE", "PWON", "CTRA", "LPCK",
    "ABMM", "ABOT", "ADHI", "ADIE", "AGIL", "AISA", "AKRA", "ALDO",
    "APLN", "ASAB", "ASJT", "ASPI", "AUTO", "AVIA", "BALA", "BBNI",
    "BCAP", "BCAS", "BCIC", "BGTG", "BHIT", "BILI", "BINA", "BION",
    "BJBR", "BJTM", "BRIS", "BTEL", "BTOF", "BULL", "BWPT", "CBRE",
    "CCRO", "CDIA", "CMRY", "CNMA", "CSAP", "DAYA", "DEAL", "DGIC",
    "DILD", "DISA", "DMAS", "DOID", "DSFI", "ECOI", "ELEX", "ELSA",
    "EMCL", "ESIP", "FASW", "FERI", "FFCO", "FUJI", "GEMS", "GGRM",
    "GSAS", "GWFA", "HALL", "HUMP", "IMAS", "IMED", "INAF", "INDR",
    "INPC", "INPS", "IPCM", "ISSP", "JATI", "JAYA", "JBRM", "JSPT",
    "KALB", "KART", "KAYU", "KBLM", "KINO", "KIWO", "KLIN", "KOCI",
    "KRAH", "LCKB", "LMPI", "LUMI", "MCAP", "MEGA", "MERI", "MGNA",
    "MITI", "MLPL", "MPPA", "MTDL", "MYRX", "NICE", "NMDY", "NRCA",
    "PACK", "PANI", "PANR", "PAPI", "PCAP", "PEHA", "PEPP", "PGLI",
    "PINS", "PKPK", "PLIN", "PMMP", "POLI", "PPRO", "PSAB", "PTCO",
    "PTRO", "PTSN", "RALS", "RAME", "RANO", "RARE", "RATU", "RDIN",
    "RELA", "ROTI", "SAPX", "SECO", "SILI", "SIME", "SINI", "SIRT",
    "SMDM", "SMRR", "SOBH", "SOTF", "SSIA", "STAA", "SULI", "SUMI",
    "TAMU", "TBIG", "TCPI", "TIMA", "TINS", "TIRU", "TMAS", "TOBA",
    "TPMA", "TRAM", "TROA", "TRUL", "TSPC", "UNSM", "VRNA", "WEGE",
    "WIRG", "WTON", "YELI", "ZBRA"]

# === 6 LEVEL INFLOW ===
THRESHOLDS = [
    (500_000_000,  "🟢", "500 Juta"),
    (1_000_000_000, "🟡", "1 Miliar"),
    (5_000_000_000, "🟠", "5 Miliar"),
    (10_000_000_000,"🔴", "10 Miliar"),
    (15_000_000_000,"🛑", "15 Miliar"),
    (20_000_000_000,"💎", "20 Miliar+"),
]

WINDOW = 60  # 1 menit
buffer = []
last_alert = {}  # {kode_tanggal_level: waktu}

# Kirim ke Telegram
def kirim_tg(pesan):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": pesan, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
        print(f"[TG] Alert terkirim: {pesan.splitlines()[0]}")
    except Exception as e:
        print(f"Telegram error: {e}")

# Ambil data real-time dari GoAPI
def ambil_data(kode):
    url = f"https://api.goapi.io/saham/{kode}?apikey={GOAPI_KEY}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json().get('data', {})
            harga = float(data.get('close', 0))
            volume_lot = float(data.get('volume', 0))  # sudah dalam lot
            offer = float(data.get('offer', 0))
            if harga > 0 and offer > 0 and abs(harga - offer) < 1:
                return {
                    'kode': kode,
                    'harga': harga,
                    'lot': volume_lot,
                    'waktu': datetime.now()
                }
    except Exception as e:
        print(f"GoAPI error {kode}: {e}")
    return None

# Proses buffer & kirim alert
def proses():
    global buffer
    now = datetime.now()
    cutoff = now - timedelta(seconds=WINDOW)

    # Ambil data baru
    for kode in SAHAM:
        data = ambil_data(kode)
        if data:
            buffer.append(data)

    # Bersihkan data lama
    buffer = [b for b in buffer if b['waktu'] > cutoff]

    # Group per saham
    grup = defaultdict(lambda: {'lot': 0, 'harga': 0})
    for b in buffer:
        grup[b['kode']]['lot'] += b['lot']
        grup[b['kode']]['harga'] = b['harga']

    # Cek setiap level inflow
    for kode, v in grup.items():
        nilai = v['lot'] * 100 * v['harga']  # lot → lembar → nilai
        harga = int(v['harga'])
        lot = int(v['lot'])
        lembar = lot * 100

        for threshold, icon, label in THRESHOLDS:
            if nilai >= threshold:
                # Cek apakah sudah kirim hari ini untuk level ini
                key = f"{kode}_{now.strftime('%Y%m%d')}_{label.replace(' ', '')}"
                if key not in last_alert or (now - last_alert[key]).seconds > 3600:  # 1 jam cooldown per level
                    pesan = f"""
{icon} <b>HAKA ALERT {kode}</b> [{label}]
Harga: <code>Rp{harga:,}</code>
Volume: <b>{lot:,} lot</b> ({lembar:,} lembar)
<b>Nilai: Rp{nilai:,.0f}</b>
Waktu: {now.strftime('%H:%M:%S')}
<i>Transaksi di harga OFFER • GoAPI.io</i>
                    """.strip()
                    kirim_tg(pesan)
                    last_alert[key] = now
                break  # Hanya kirim level tertinggi

# Jalankan bot
if __name__ == "__main__":
    kirim_tg("🤖 <b>Bot HAKA Alert v2 AKTIF!</b>\n"
             "Pantau 180 saham IHSG • 6 level inflow")
    print("Bot HAKA jalan 24/7...")
    while True:
        try:
            proses()
            time.sleep(random.uniform(12, 18))  # Anti-ban GoAPI
        except Exception as e:
            kirim_tg(f"⚠️ Bot error: {e}")
            time.sleep(30)

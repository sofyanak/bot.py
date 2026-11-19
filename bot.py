import logging
import sqlite3
import re
import json
import urllib.request
from datetime import datetime, time, timezone, timedelta
from pathlib import Path

from telegram import (
    Update, InputFile, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

MARKUP = 1000

SUPPLIER_PROVIDER_MAP = {
    "BY.U": "BY.U",
    "Three": "Three",
    "Indosat / IM3": "Indosat",
    "Smartfren": "Smartfren",
    "XL": "XL",
    "AXIS": "Axis",
    "Telkomsel": "Telkomsel",
}

# =========================
# CONFIG
# =========================
BOT_TOKEN = "8959936233:AAHVAjCpupuKxG2dg7qh_aRarUSE0hmitxc"
ADMIN_IDS = {6553824892}
QRIS_FILE = Path(__file__).parent / "qris.jpg"
DB_FILE = Path(__file__).parent / "orders.db"
QRIS_ID_FILE = Path(__file__).parent / "qris_file_id.txt"

async def send_admin_message(bot, **kwargs):
    for admin_id in ADMIN_IDS:
        await bot.send_message(chat_id=admin_id, **kwargs)

async def send_admin_photo(bot, **kwargs):
    for admin_id in ADMIN_IDS:
        await bot.send_photo(chat_id=admin_id, **kwargs)

def send_rich_message(token, chat_id, rich_message):
    data = json.dumps({
        "chat_id": chat_id,
        "rich_message": rich_message
    }).encode()

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendRichMessage",
        data=data,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print("RICH API ERROR:", body)
        raise


async def rich_reply(chat_id, content, mode="markdown", media=None):
    rich_message = {mode: content}
    if media:
        rich_message["media"] = media
    return send_rich_message(BOT_TOKEN, chat_id, rich_message)


async def send_admin_rich_message(bot, content, mode="markdown"):
    for admin_id in ADMIN_IDS:
        await rich_reply(admin_id, content, mode)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =========================
# PRODUCT DATA
# =========================
PRODUCTS = {
    "BY.U": {
        "1 Hari": [("3 GB", 8500), ("10 GB", 9000)],
        "2 Hari": [("6 GB", 8500), ("8 GB", 9000), ("12 GB", 11500)],
        "3 Hari": [("3 GB", 12500), ("8 GB", 13500), ("9 GB", 14000)],
        "5 Hari": [("10 GB", 15500), ("11 GB", 19500), ("13 GB", 18500)],
        "7 Hari": [("3 GB", 13000), ("6 GB", 15500), ("7.5 GB", 18500), ("8 GB", 19000), ("10 GB", 20000), ("12 GB", 24000), ("14 GB", 25000)],
        "14 Hari": [("3.5 GB", 19000), ("7 GB", 25000), ("8 GB", 25500), ("9 GB", 26500), ("12 GB", 27500)],
        "28 Hari": [("7 GB", 36000), ("10 GB", 44000), ("11 GB", 48000), ("15 GB", 50000)],
    },

    "Three": {
        "1 Hari": [("1 GB", 7500), ("6 GB", 8500), ("10 GB", 9000)],
        "2 Hari": [("5 GB", 11500), ("6 GB", 12000), ("7 GB", 12200), ("10 GB", 12500), ("15 GB", 15000)],
        "3 Hari": [("1 GB — Bonus s/d. 500MB", 8000), ("3 GB — Bonus s/d. 2GB", 13500), ("5 GB — Bonus s/d. 2GB", 14000), ("6 GB — Bonus s/d. 2GB", 14500), ("11 GB", 15000), ("20 GB", 19000), ("30 GB", 28000)],
        "5 Hari": [("7 GB", 15500), ("10 GB", 18000), ("11 GB", 19500), ("12 GB", 20500), ("30 GB", 27000)],
        "7 Hari": [("6 GB", 21000), ("10 GB — Bonus s/d. 2GB", 23500), ("15 GB", 23500), ("25 GB", 29000), ("100 GB", 48000)],
        "14 Hari": [("7 GB", 24000), ("8 GB", 25000), ("10 GB", 27000), ("12 GB", 28000), ("25 GB", 54000)],
        "28 Hari": [("7 GB", 30500), ("9 GB", 35000), ("11 GB", 40000), ("12 GB", 45000), ("15 GB", 46500), ("18 GB", 47000), ("22 GB", 56000), ("25 GB", 58000), ("32 GB", 73000), ("36 GB", 76000), ("50 GB", 84000), ("55 GB", 88000), ("66 GB", 93000), ("100 GB", 107000)],
        "Promo": [("5 GB 1H + VC 5K", 9000), ("7 GB 3H + VC 5K", 15000), ("10 GB 7H + VC 10K", 24000)],
    },

    "Indosat / IM3": {
        "1 Hari": [("1 GB", 7000), ("3 GB", 8000), ("5 GB", 9000), ("7 GB", 10000), ("9 GB", 12000)],
        "2 Hari": [("5 GB", 11000), ("6 GB", 12000), ("9 GB", 13000), ("15 GB", 15000)],
        "3 Hari": [("3 GB", 13500), ("4 GB", 14000), ("5 GB", 14500), ("6 GB", 15000), ("10 GB", 17000), ("15 GB", 18500), ("20 GB", 19000), ("30 GB", 27000)],
        "5 Hari": [("4 GB", 14500), ("5 GB", 15000), ("6 GB", 16000), ("7 GB", 15500), ("10 GB", 17000), ("12 GB", 21000), ("30 GB", 27500)],
        "7 Hari": [("6 GB", 21000), ("10 GB", 23500), ("15 GB", 24000), ("25 GB", 29000), ("100 GB", 48000)],
        "14 Hari": [("8 GB", 24500), ("10 GB", 28000), ("12 GB", 29000)],
        "28 Hari": [("4.5 GB", 25000), ("5 GB", 26500), ("7 GB", 31000), ("11 GB", 34500), ("18 GB", 53500), ("22 GB", 56000)],
    },

    "Smartfren": {
        "1 Hari": [("1 GB", 7500), ("10 GB", 9000)],
        "2 Hari": [("6 GB", 10500)],
        "3 Hari": [("1 GB", 8500), ("4 GB", 11000), ("6 GB", 13000), ("10 GB", 15500), ("20 GB", 20000)],
        "5 Hari": [("4 GB", 15000), ("6.5 GB", 15500)],
        "7 Hari": [("6 GB", 17000), ("9 GB", 18000), ("10 GB", 19500), ("30 GB", 40000)],
        "14 Hari": [("5 GB", 21500), ("12 GB", 28500), ("20 GB", 29000), ("40 GB", 65000)],
        "28 Hari": [("7 GB", 35000), ("9 GB", 38500), ("10 GB", 41000), ("15 GB", 48000), ("24 GB", 61000), ("66 GB", 96000)],
    },

    "XL": {
        "1 Hari": [("3 GB", 8000), ("10 GB", 10500)],
        "2 Hari": [("6 GB", 12000), ("12 GB", 14500), ("15 GB", 15000)],
        "3 Hari": [("4 GB", 13000), ("6 GB", 15000), ("20 GB", 20000)],
        "5 Hari": [("4 GB", 15000), ("8 GB", 19500)],
        "7 Hari": [("4 GB", 17000), ("6 GB", 19500), ("10 GB", 24500), ("20 GB", 29000), ("40 GB", 39000), ("75 GB", 49000)],
        "10 Hari": [("7 GB", 21500), ("9 GB", 24000)],
        "14 Hari": [("3 GB", 19000), ("7 GB", 24000), ("8 GB", 28500), ("15 GB", 37500), ("30 GB", 47000), ("75 GB", 72000), ("150 GB", 96000)],
        "28 Hari": [("7 GB", 36000), ("10 GB", 42500), ("15 GB", 48000), ("22 GB", 58000), ("28 GB", 68000), ("36 GB", 76500), ("46 GB", 86000), ("65 GB", 97000)],
    },

    "AXIS": {
        "Kuota Per-Jam": [("1.5 GB — 2 Jam", 3000), ("3 GB — 3 Jam", 4000), ("3 GB — 6 Jam", 5000)],
        "1 Hari": [("5 GB", 7500), ("15 GB", 9000)],
        "2 Hari": [("5 GB", 10000), ("7 GB", 11000), ("8 GB", 13000), ("13 GB", 14000), ("17 GB", 18000), ("30 GB", 21000)],
        "3 Hari": [("3 GB", 12000), ("5 GB", 13000), ("7 GB", 14000), ("13 GB", 19000), ("17 GB", 20000)],
        "5 Hari": [("2 GB", 14000), ("4 GB", 15000), ("5 GB", 16000), ("8 GB", 18000), ("16 GB", 24000), ("24 GB", 27000), ("32 GB", 35000), ("50 GB", 37000)],
        "7 Hari": [("4 GB", 19000), ("6 GB", 20000), ("10 GB", 25000), ("17 GB", 27000), ("23 GB", 31000), ("45 GB", 45000)],
        "14 Hari": [("3 GB", 20000), ("5 GB", 24000), ("10 GB", 35000), ("15 GB", 37000), ("25 GB", 47000), ("36 GB", 58000)],
        "28 Hari — Voucher": [("5 GB", 35500), ("6 GB", 43500), ("15 GB", 48500), ("16 GB", 62500), ("26 GB", 73000)],
    },

    "Telkomsel": {
        "1 Hari": [("1 GB", 9000), ("4 GB", 10500), ("5 GB", 11500), ("6 GB", 12000), ("8 GB", 12500)],
        "3 Hari": [("1 GB", 10500), ("2 GB", 12500), ("3 GB", 14000), ("15 GB", 48500)],
        "5 Hari": [("2.5 GB", 13000)],
        "7 Hari": [("500 MB", 8000), ("2 GB", 17000), ("3 GB", 18000), ("5 GB", 25500), ("6 GB", 27000), ("7 GB", 27500), ("9 GB", 28000), ("13 GB", 31000)],
        "14 Hari": [("3 GB", 25000), ("5 GB", 33500), ("6 GB", 36500), ("7 GB", 38500)],
        "28 Hari": [("2 GB", 23000), ("3 GB", 28000), ("4 GB", 40000), ("5 GB", 41000), ("7 GB", 42000), ("8 GB", 45000), ("10 GB", 48500), ("11 GB", 54500), ("15 GB", 58000)],
        "Kuota Regional": [("Kirim nomor + kota untuk cek paket yang tersedia", 0)],
    },
}
# =========================
# DATA PRODUK TELEGRAM STARS & GAME
# Harga di sini = HARGA JUAL FINAL (tanpa MARKUP).
# !! HARGA DI BAWAH CUMA CONTOH — GANTI SESUAI MODAL LU !!
# =========================
GAME_PRODUCTS = {
    "stars": {
        "menu_text": "Telegram ⭐",
        "name": "Telegram ⭐",
        "target_label": "🎯 Username Telegram",
        "target_prompt": "Kirim *username Telegram* penerima ⭐.\nContoh: `@username`",
        "categories": [
            {
                "name": "🎁 Gift ⭐",
                "packages": [
                    ("Gift 15 ⭐", 5100),
                    ("Gift 25 ⭐", 8500),
                    ("Gift 50 ⭐", 17000),
                    ("Gift 75 ⭐", 25500),
                    ("Gift 100 ⭐", 34000),
                ],
            },
            {
                "name": "🛒 Top Up ⭐",
                "packages": [
                    ("Top Up 50 ⭐", 17000),
                    ("Top Up 75 ⭐", 25500),
                    ("Top Up 100 ⭐", 34000),
                    ("Top Up 150 ⭐", 51000),
                    ("Top Up 200 ⭐", 68000),
                    ("Top Up 250 ⭐", 76000),
                    ("Top Up 300 ⭐", 91500),
                    ("Top Up 350 ⭐", 107000),
                    ("Top Up 400 ⭐", 122000),
                    ("Top Up 450 ⭐", 133000),
                    ("Top Up 500 ⭐", 147500),
                    ("Top Up 550 ⭐", 162000),
                    ("Top Up 600 ⭐", 177000),
                    ("Top Up 650 ⭐", 188500),
                    ("Top Up 700 ⭐", 203000),
                    ("Top Up 750 ⭐", 217500),
                    ("Top Up 800 ⭐", 232000),
                    ("Top Up 850 ⭐", 246500),
                    ("Top Up 900 ⭐", 261000),
                    ("Top Up 950 ⭐", 275500),
                    ("Top Up 1000 ⭐", 290000),
                ],
            },
        ],
    },
    "mlbb": {
        "menu_text": "MLBB 💎",
        "name": "MLBB 💎",
        "target_label": "🎯 User ID (Zone ID)",
        "target_prompt": "Kirim *User ID* dan *Zone ID* MLBB.\nContoh: `12345678 1234`",
        "categories": [
            {
                "name": "💎 Reguler",
                "packages": [
                    ("3 💎", 1800),
                    ("5 💎", 1900),
                    ("11 💎", 4000),
                    ("12 💎", 4200),
                    ("15 💎", 4900),
                    ("18 💎", 6400),
                    ("19 💎", 6600),
                    ("20 💎", 6900),
                    ("23 💎", 8000),
                    ("28 💎", 9500),
                    ("30 💎", 10400),
                    ("33 💎", 11100),
                    ("36 💎", 12300),
                    ("40 💎", 13400),
                    ("42 💎", 14000),
                    ("45 💎", 14100),
                    ("46 💎", 15200),
                    ("54 💎", 16900),
                    ("59 💎", 18700),
                    ("64 💎", 20000),
                    ("66 💎", 20200),
                    ("70 💎", 21400),
                    ("74 💎", 23900),
                    ("75 💎", 24500),
                    ("78 💎", 24600),
                    ("84 💎", 26100),
                    ("85 💎", 26800),
                    ("88 💎", 27300),
                    ("92 💎", 29000),
                    ("102 💎", 33600),
                    ("110 💎", 34300),
                    ("114 💎", 35900),
                    ("129 💎", 38000),
                    ("140 💎", 41800),
                    ("141 💎", 42900),
                    ("148 💎", 44800),
                    ("153 💎", 45400),
                    ("168 💎", 50600),
                    ("172 💎", 50800),
                    ("183 💎", 56000),
                    ("185 💎", 58900),
                    ("210 💎", 61700),
                    ("222 💎", 71100),
                    ("241 💎", 72400),
                    ("258 💎", 76600),
                    ("277 💎", 82400),
                    ("284 💎", 83400),
                    ("285 💎", 87000),
                    ("300 💎", 88600),
                    ("366 💎", 106700),
                    ("387 💎", 115900),
                    ("370 💎", 116200),
                    ("406 💎", 119900),
                    ("408 💎", 128000),
                    ("415 💎", 130100),
                    ("429 💎", 134200),
                    ("500 💎", 145300),
                    ("530 💎", 173200),
                    ("568 💎", 174100),
                    ("600 💎", 180900),
                    ("642 💎", 186600),
                    ("716 💎", 208800),
                    ("720 💎", 210500),
                    ("750 💎", 219300),
                    ("758 💎", 226000),
                    ("792 💎", 226700),
                    ("790 💎", 230200),
                    ("845 💎", 249300),
                    ("875 💎", 266700),
                    ("878 💎", 268200),
                    ("938 💎", 270400),
                    ("940 💎", 272800),
                ],
            },
            {
                "name": "🎫 Weekly Pass",
                "packages": [
                    ("Weekly 💎 Pass", 32000),
                ],
            },
        ],
    },
    "ff": {
        "menu_text": "Free Fire 💎",
        "name": "Free Fire 💎",
        "target_label": "🎯 Player ID",
        "target_prompt": "Kirim *Player ID* Free Fire.\nContoh: `123456789`",
        "categories": [
            {
                "name": "💎 Reguler",
                "packages": [
                    ("5 💎", 900),
                    ("10 💎", 1600),
                    ("12 💎", 1900),
                    ("15 💎", 2900),
                    ("20 💎", 3500),
                    ("25 💎", 4000),
                    ("30 💎", 4900),
                    ("50 💎", 6700),
                    ("55 💎", 7200),
                    ("70 💎", 8900),
                    ("75 💎", 9300),
                    ("80 💎", 10200),
                    ("100 💎", 12900),
                    ("120 💎", 15400),
                    ("125 💎", 16100),
                    ("140 💎", 17600),
                    ("150 💎", 19000),
                    ("160 💎", 20900),
                    ("190 💎", 24300),
                    ("200 💎", 24900),
                    ("210 💎", 25700),
                    ("250 💎", 33400),
                    ("280 💎", 35700),
                    ("300 💎", 39900),
                    ("355 💎", 44000),
                    ("375 💎", 46000),
                    ("405 💎", 46700),
                    ("425 💎", 54800),
                    ("475 💎", 58300),
                    ("510 💎", 62200),
                    ("565 💎", 66000),
                    ("600 💎", 76600),
                    ("635 💎", 81000),
                    ("720 💎", 87900),
                    ("790 💎", 98800),
                    ("860 💎", 106800),
                    ("930 💎", 117700),
                    ("1000 💎", 131300),
                    ("1075 💎", 135300),
                    ("1450 💎", 185600),
                    ("2000 💎", 257500),
                    ("2140 💎", 277800),
                    ("2180 💎", 280700),
                    ("2355 💎", 285300),
                    ("2350 💎", 297000),
                    ("2720 💎", 336100),
                    ("2720 💎", 348800),
                    ("3640 💎", 457700),
                    ("4000 💎", 493200),
                    ("7290 💎", 888100),
                    ("9290 💎", 1065100),
                ],
            },
            {
                "name": "👑 Membership",
                "packages": [
                    ("Membership Mingguan", 26400),
                    ("Membership Bulanan", 77900),
                ],
            },
        ],
    },
}

GAME_BY_MENU = {g["menu_text"]: key for key, g in GAME_PRODUCTS.items()}

MAIN_KEYBOARD_ROWS = [
    [KeyboardButton("📊 Kuota Internet")],
    [KeyboardButton("💳 Pulsa"), KeyboardButton("📅 Masa Aktif")],
    [KeyboardButton("⚡ Token PLN"), KeyboardButton("Telegram ⭐")],
    [KeyboardButton("MLBB 💎"), KeyboardButton("Free Fire 💎")],
]

# =========================
# MARKUP GAME (terpisah dari MARKUP kuota)
# Harga di GAME_PRODUCTS = pricelist awal (patokan).
# Harga jual = harga awal + markup %, lalu digenapkan KE ATAS ke kelipatan
# GAME_ROUND. Kalau hasil markup sudah kelipatan GAME_ROUND, tidak dibulatkan lagi.
# Stars tidak kena markup. Set persen 0 untuk mematikan.
# =========================
GAME_MARKUP = {"mlbb": 1.5, "ff": 1.5}
GAME_ROUND = 100

from decimal import Decimal as _D, ROUND_CEILING as _CEIL


def _markup_price(price, pct):
    if not pct:
        return price
    x = _D(price) * (_D(100) + _D(str(pct))) / _D(100)
    step = _D(GAME_ROUND)
    return int((x / step).to_integral_value(rounding=_CEIL) * step)


for _key, _pct in GAME_MARKUP.items():
    for _cat in GAME_PRODUCTS[_key]["categories"]:
        _cat["packages"] = [
            (_label, _markup_price(_price, _pct))
            for _label, _price in _cat["packages"]
        ]

# =========================
# PULSA & MASA AKTIF (harga fix, tanpa MARKUP kuota)
# =========================
def _nominal(n):
    return f"{n:,}".replace(",", ".")


_PULSA = [
    (5000, 7500), (10000, 12500), (15000, 17000), (20000, 22000),
    (25000, 27500), (30000, 32000), (35000, 37000), (40000, 42000),
    (45000, 46500), (50000, 52000), (55000, 57000), (60000, 62000),
    (65000, 66500), (70000, 71500), (75000, 77000), (80000, 81500),
    (85000, 86500), (90000, 91500), (95000, 96500), (100000, 100000),
]

_MASA_AKTIF = {
    "Telkomsel": [
        (5, 4000), (10, 6000), (15, 7500), (30, 15500),
        (90, 34000), (180, 56500), (330, 102500), (360, 111000),
    ],
    "Indosat / IM3": [
        (15, 10000), (30, 14000), (90, 33000), (180, 56500), (360, 107500),
    ],
    "Three": [
        (30, 15500), (90, 33500), (180, 56500), (360, 105000),
    ],
}

FIXED_PRODUCTS = {
    "pulsa": {
        "menu_text": "💳 Pulsa",
        # semua operator yang ada di menu kuota
        "providers": {
            prov: [(f"Pulsa {_nominal(n)}", price) for n, price in _PULSA]
            for prov in PRODUCTS
        },
    },
    "masa": {
        "menu_text": "📅 Masa Aktif",
        "providers": {
            prov: [(f"Masa Aktif {d} Hari", price) for d, price in items]
            for prov, items in _MASA_AKTIF.items()
        },
    },
}

_PLN = [
    (5000, 7000), (10000, 12000), (15000, 17000), (20000, 22000),
    (25000, 27000), (50000, 52000), (100000, 102000), (200000, 202000),
    (500000, 502000), (1000000, 1002000),
]

FIXED_PRODUCTS["pln"] = {
    "menu_text": "⚡ Token PLN",
    "providers": {
        "Token PLN": [(f"Token PLN {_nominal(n)}", price) for n, price in _PLN],
    },
}

FIXED_BY_MENU = {f["menu_text"]: key for key, f in FIXED_PRODUCTS.items()}

# =========================
# DATABASE
# =========================
def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def supplier_info(provider, duration, package):
    conn = db()

    provider_map = {
        "BY.U": "BY.U",
        "Three": "Three",
        "Indosat / IM3": "Indosat",
        "Smartfren": "Smartfren",
        "XL": "XL",
        "AXIS": "Axis",
        "Telkomsel": "Telkomsel",
    }

    supplier_provider = provider_map.get(provider, provider)

    # Exact package dulu
    exact = conn.execute("""
        SELECT supplier_price, available, package
        FROM pricelist
        WHERE provider = ?
          AND duration = ?
          AND package = ?
        LIMIT 1
    """, (supplier_provider, duration, package)).fetchone()

    if exact:
        conn.close()
        return {
            "price": exact["supplier_price"],
            "available": exact["available"] == 1,
            "package": exact["package"],
        }

    # Fallback berdasarkan kapasitas
    gb_match = re.search(
        r"(\d+(?:\.\d+)?)\s*GB",
        package,
        re.I
    )

    if not gb_match:
        conn.close()
        return None

    gb = gb_match.group(1)

    rows = conn.execute("""
        SELECT supplier_price, available, package
        FROM pricelist
        WHERE provider = ?
          AND duration = ?
    """, (supplier_provider, duration)).fetchall()

    conn.close()

    # 2GB tidak boleh match 22GB
    pattern = rf"(?<!\d){re.escape(gb)}\s*GB(?!\d)"

    for row in rows:
        if re.search(pattern, row["package"], re.I):
            return {
                "price": row["supplier_price"],
                "available": row["available"] == 1,
                "package": row["package"],
            }

    return None




def get_supplier_packages(provider, duration):
    conn = db()

    provider_map = {
        "BY.U": "BY.U",
        "Three": "Three",
        "Indosat / IM3": "Indosat",
        "Smartfren": "Smartfren",
        "XL": "XL",
        "AXIS": "Axis",
        "Telkomsel": "Telkomsel",
    }

    supplier_provider = provider_map.get(provider, provider)

    rows = conn.execute("""
        SELECT package, supplier_price, available
        FROM pricelist
        WHERE provider = ?
          AND duration = ?
          AND available = 1
        ORDER BY supplier_price ASC
    """, (supplier_provider, duration)).fetchall()

    conn.close()

    return [
        (row["package"], row["supplier_price"])
        for row in rows
    ]



def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            provider TEXT NOT NULL,
            duration TEXT NOT NULL,
            package TEXT NOT NULL,
            price INTEGER NOT NULL,
            phone TEXT NOT NULL,
            proof_file_id TEXT,
            status TEXT NOT NULL DEFAULT 'WAITING_PROOF',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def create_order(data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = db()
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(orders)")}
    if "category" not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN category TEXT")
    cur = conn.execute("""
        INSERT INTO orders
        (user_id, username, provider, duration, package, price, phone,
         category, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'WAITING_PROOF', ?, ?)
    """, (
        data["user_id"], data["username"], data["provider"],
        data["duration"], data["package"], data["price"], data["phone"],
        data.get("category", "kuota"), now, now
    ))
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id

def update_proof(order_id, proof_file_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = db()
    conn.execute("""
        UPDATE orders
        SET proof_file_id=?, status='PROCESSING', updated_at=?
        WHERE id=?
    """, (proof_file_id, now, order_id))
    conn.commit()
    conn.close()

# =========================
# AUTO POST TRANSAKSI SELESAI KE CHANNEL (+ STRUK)
# =========================
import html as _html
import json as _json
import threading
import urllib.request as _urlreq

DONE_POST_ENABLED = True       # False = matikan
DONE_CHANNEL = "@verlfy"   # channel tujuan


def _tg_api(method, payload):
    req = _urlreq.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=_json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return _urlreq.urlopen(req, timeout=20).read()


def save_receipt(order_id, file_id):
    """Simpan file_id struk yang dikirim admin, dipakai saat posting ke channel."""
    conn = db()
    try:
        try:
            conn.execute(
                "UPDATE orders SET receipt_file_id=? WHERE id=?", (file_id, order_id)
            )
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE orders ADD COLUMN receipt_file_id TEXT")
            conn.execute(
                "UPDATE orders SET receipt_file_id=? WHERE id=?", (file_id, order_id)
            )
        conn.commit()
    finally:
        conn.close()


def post_done_to_channel(order_id):
    try:
        order = get_order(order_id)
        if not order:
            return

        esc = _html.escape
        category = order["category"] if "category" in order.keys() else None
        hashtags = {
            "kuota": "#Kuota",
            "stars": "#Stars",
            "diamond": "#Diamond",
            "pulsa": "#Pulsa",
            "masa": "#MasaAktif",
            "token": "#Token",
        }
        hashtag = hashtags.get(category, "#Kuota")
        paket = (
            order["package"] if order["duration"] == "-"
            else f"{order['package']} {order['duration']}"
        )
        waktu = datetime.now().strftime("%d-%m-%Y %H:%M")

        try:
            receipt = order["receipt_file_id"]
        except (IndexError, KeyError):
            receipt = None

        if receipt:
            # log + struk dalam satu postingan (foto dengan caption)
            caption = (
                f"<b>{hashtag}</b>\n"
                f"<b>Order #{order['id']:04d} Selesai</b>\n"
                f"Provider: {esc(order['provider'])}\n"
                f"Paket: {esc(paket)}\n"
                f"Harga: {rupiah(order['price'])}\n"
                f"Waktu: {waktu}"
            )
            _tg_api("sendPhoto", {
                "chat_id": DONE_CHANNEL,
                "photo": receipt,
                "caption": caption,
                "parse_mode": "HTML",
            })
        else:
            # belum ada struk tersimpan: kirim log teks saja
            rich_html = (
                f"<b>{hashtag}</b><br>"
                f"<b>Order #{order['id']:04d} Selesai</b><br>"
                f"Provider: {esc(order['provider'])}<br>"
                f"Paket: {esc(paket)}<br>"
                f"Harga: {rupiah(order['price'])}<br>"
                f"Waktu: {waktu}"
            )
            send_rich_message(BOT_TOKEN, DONE_CHANNEL, {"html": rich_html})
    except Exception as e:
        logger.warning("gagal post order #%s ke channel: %s", order_id, e)


def update_status(order_id, status):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = db()
    old = conn.execute(
        "SELECT status FROM orders WHERE id=?", (order_id,)
    ).fetchone()
    conn.execute(
        "UPDATE orders SET status=?, updated_at=? WHERE id=?",
        (status, now, order_id)
    )
    conn.commit()
    conn.close()

    # sekali saja per order: hanya saat berubah menjadi DONE
    if (
        status == "DONE"
        and DONE_POST_ENABLED
        and not (old and old["status"] == "DONE")
    ):
        threading.Thread(
            target=post_done_to_channel, args=(order_id,), daemon=True
        ).start()


def get_order(order_id):
    conn = db()
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    conn.close()
    return row

def get_waiting_confirmation_order(user_id):
    conn = db()
    row = conn.execute("""
        SELECT * FROM orders
        WHERE user_id = ?
          AND status = 'PROCESSING'
        ORDER BY id DESC
        LIMIT 1
    """, (user_id,)).fetchone()
    conn.close()
    return row

def get_seller_confirmation_order():
    conn = db()
    row = conn.execute("""
        SELECT * FROM orders
        WHERE status = 'WAITING_SELLER_CONFIRMATION'
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()
    conn.close()
    return row


def get_qris_photo():
    """Pakai file_id hasil upload sebelumnya kalau qris.jpg belum berubah."""
    try:
        mtime, file_id = QRIS_ID_FILE.read_text().strip().split("|", 1)
        if file_id and mtime == str(int(QRIS_FILE.stat().st_mtime)):
            return file_id
    except (OSError, ValueError):
        pass
    return QRIS_FILE


def save_qris_id(file_id):
    try:
        QRIS_ID_FILE.write_text(
            f"{int(QRIS_FILE.stat().st_mtime)}|{file_id}"
        )
    except OSError:
        pass


async def send_qris(message, caption, parse_mode=None):
    photo = get_qris_photo()

    # Utamakan file_id Telegram agar tidak upload ulang.
    if photo != QRIS_FILE:
        try:
            return await message.reply_photo(
                photo=photo,
                caption=caption,
                parse_mode=parse_mode
            )
        except Exception as e:
            logger.warning("QRIS file_id gagal, coba upload file: %s", e)

    # Upload lokal hanya jika file_id belum tersedia atau gagal.
    try:
        with open(QRIS_FILE, "rb") as photo_file:
            sent = await message.reply_photo(
                photo=photo_file,
                caption=caption,
                parse_mode=parse_mode
            )
        if sent.photo:
            save_qris_id(sent.photo[-1].file_id)
        return sent
    except Exception:
        logger.exception("QRIS gagal dikirim sebagai foto")
        raise


def rupiah(n):
    return f"Rp{n:,.0f}".replace(",", ".")


def target_label(provider):
    """Label data tujuan order (nomor HP untuk kuota, ID/username untuk game)."""
    for game in GAME_PRODUCTS.values():
        if game["name"] == provider:
            return game["target_label"]
    if provider == "Token PLN":
        return "🎯 ID Pelanggan"
    return "📱 Nomor"


def _game_sell_price(supplier_price):
    """Rumus markup diamond: harga supplier + 0.7% + 500, lalu dibulatkan ke atas per 100."""
    raw = _D(supplier_price) * _D("1.007") + _D(500)
    return int((raw / _D(100)).to_integral_value(rounding=_CEIL) * _D(100))


def _display_game_items(game, kind):
    """Sama seperti kuota: amount sama -> ambil termurah; amount lebih kecil
    yang harga jualnya >= amount lebih besar -> disembunyikan."""
    conn = db()
    try:
        try:
            rows = conn.execute(
                "SELECT amount, supplier_price FROM game_pricelist "
                "WHERE game=? AND kind=? AND available=1",
                (game, kind)
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
    finally:
        conn.close()

    cheapest = {}
    for amount, supplier_price in rows:
        if amount in cheapest and supplier_price >= cheapest[amount]:
            continue
        cheapest[amount] = supplier_price

    items = []
    min_sell = None
    for amount in sorted(cheapest, reverse=True):
        sell = _game_sell_price(cheapest[amount])
        if min_sell is not None and sell >= min_sell:
            continue
        items.append((amount, sell))
        min_sell = sell if min_sell is None else min(min_sell, sell)

    items.sort(key=lambda x: x[1])
    return items


def _game_label(kind, amount):
    if kind == "diamond":
        return f"{amount} 💎"
    if kind == "weekly_pass":
        return f"Weekly Pass {amount} 💎"
    if kind == "membership_mingguan":
        return "Membership Mingguan"
    if kind == "membership_bulanan":
        return "Membership Bulanan"
    return f"{amount} 💎"


GAME_DYNAMIC_CATEGORIES = {
    "mlbb": [
        ("💎 Reguler", ["diamond"]),
        ("🎫 Weekly Pass", ["weekly_pass"]),
    ],
    "ff": [
        ("💎 Reguler", ["diamond"]),
        ("👑 Membership", ["membership_mingguan", "membership_bulanan"]),
    ],
}


def game_categories_dynamic(game):
    categories = []
    for cat_name, kinds in GAME_DYNAMIC_CATEGORIES[game]:
        packages = []
        for kind in kinds:
            for amount, sell in _display_game_items(game, kind):
                packages.append((_game_label(kind, amount), sell))
        categories.append({"name": cat_name, "packages": packages})
    return categories


def game_category_menu(key):
    game = GAME_PRODUCTS[key]
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(c["name"]) for c in game["categories"]],
            [KeyboardButton("⬅️ Kembali")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def game_package_menu(key, cat_index):
    game = GAME_PRODUCTS[key]

    if key in ("mlbb", "ff"):
        category_name = game["categories"][cat_index]["name"]
        packages = game_categories_dynamic(key)[cat_index]["packages"]
    else:
        category = game["categories"][cat_index]
        category_name = category["name"]
        packages = category["packages"]

    blocks = [
        {
            "type": "heading",
            "text": f"{game['menu_text']} — {category_name}",
            "size": 3
        },
        {
            "type": "paragraph",
            "text": "Pilih paket:"
        }
    ]

    if not packages:
        blocks.append({
            "type": "paragraph",
            "text": "⚠️ Belum ada paket tersedia saat ini."
        })

    for index, (label, price) in enumerate(packages):
        blocks.append({
            "type": "buttons",
            "buttons": [{
                "text": f"{label} — {rupiah(price)}",
                "callback_data": f"gpkg|{key}|{cat_index}|{index}"
            }]
        })

    return blocks


def fixed_provider_menu(key):
    names = list(FIXED_PRODUCTS[key]["providers"].keys())
    rows = []
    for i in range(0, len(names), 2):
        row = [KeyboardButton(names[i])]
        if i + 1 < len(names):
            row.append(KeyboardButton(names[i + 1]))
        rows.append(row)
    rows.append([KeyboardButton("⬅️ Kembali")])
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def fixed_package_menu(key, provider):
    fixed = FIXED_PRODUCTS[key]
    provider_index = list(fixed["providers"].keys()).index(provider)

    blocks = [
        {
            "type": "heading",
            "text": f"{fixed['menu_text']} — {provider}",
            "size": 3
        },
        {
            "type": "paragraph",
            "text": "Pilih paket:"
        }
    ]

    for index, (label, price) in enumerate(fixed["providers"][provider]):
        blocks.append({
            "type": "buttons",
            "buttons": [{
                "text": f"{label} — {rupiah(price)}",
                "callback_data": f"fpkg|{key}|{provider_index}|{index}"
            }]
        })

    return blocks


def validate_target(key, raw):
    """Return (target_ternormalisasi, pesan_error)."""
    raw = (raw or "").strip()

    if key == "stars":
        m = re.fullmatch(r"@?([A-Za-z][A-Za-z0-9_]{4,31})", raw)
        if not m:
            return None, "❌ Username tidak valid.\nContoh: @username (5–32 karakter)."
        return f"@{m.group(1)}", None

    if key == "mlbb":
        parts = re.findall(r"\d+", raw)
        if (
            len(parts) != 2
            or not (5 <= len(parts[0]) <= 12)
            or not (3 <= len(parts[1]) <= 5)
        ):
            return None, (
                "❌ Format salah. Kirim User ID dan Zone ID.\n"
                "Contoh: `12345678 1234`"
            )
        return f"{parts[0]} ({parts[1]})", None

    if key == "ff":
        if not raw.isdigit() or not (6 <= len(raw) <= 15):
            return None, "❌ Player ID tidak valid. Kirim angka saja (6–15 digit)."
        return raw, None

    return None, "❌ Data tidak valid."

# =========================
# KEYBOARDS
# =========================
def main_menu():
    return (
        '<tg-button-row>'
        '<tg-button type="callback_data" data="menu_quota">📶 Kuota Internet</tg-button>'
        '</tg-button-row>'
    )


def provider_menu():
    names = list(PRODUCTS.keys())
    keyboard = []
    for i in range(0, len(names), 2):
        row = [KeyboardButton(names[i])]
        if i + 1 < len(names):
            row.append(KeyboardButton(names[i + 1]))
        keyboard.append(row)
    keyboard.append([KeyboardButton("⬅️ Kembali")])
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True,
        is_persistent=False
    )


def duration_menu(provider):
    supplier_provider = SUPPLIER_PROVIDER_MAP.get(provider, provider)

    with db() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT duration
            FROM pricelist
            WHERE provider = ?
              AND available = 1
            """,
            (supplier_provider,)
        ).fetchall()

    durations = [row["duration"] for row in rows]

    def sort_duration(duration):
        match = re.search(r"(\d+)", duration or "")
        return (
            int(match.group(1)) if match else 999999,
            duration
        )

    durations.sort(key=sort_duration)

    keyboard = []
    for i in range(0, len(durations), 2):
        row = [KeyboardButton(durations[i])]
        if i + 1 < len(durations):
            row.append(KeyboardButton(durations[i + 1]))
        keyboard.append(row)

    keyboard.append([KeyboardButton("⬅️ Kembali")])

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=False
    )

def normalize_range_display(package):
    if not package:
        return package

    match = re.search(
        r'(\\d+(?:[.,]\\d+)?)\\s*GB\\s*(?:-|–|—|s/d|sd|sampai)\\s*\\d+(?:[.,]\\d+)?\\s*GB',
        str(package),
        re.IGNORECASE
    )

    if match:
        return f"{match.group(1).replace(',', '.')} GB"

    return package


def _get_display_packages_base(provider, duration):
    packages = [
        (original_package, supplier_price)
        for original_package, supplier_price in get_supplier_packages(provider, duration)
        if "malam" not in original_package.lower()
    ]

    cheapest = {}

    for original_package, supplier_price in packages:
        package_main = re.sub(r"\([^)]*\)", " ", original_package)

        gb_matches = re.findall(
            r"(\d+(?:\.\d+)?)\s*GB",
            package_main,
            re.I
        )

        if not gb_matches:
            mb_matches = re.findall(
                r"(\d+(?:\.\d+)?)\s*MB",
                package_main,
                re.I
            )

            if not mb_matches:
                continue

            values = [float(x) / 1000 for x in mb_matches]
        else:
            values = [float(x) for x in gb_matches]

        if len(values) == 1:
            gb = values[0]
            display_package = (
                f"{int(gb)} GB"
                if gb.is_integer()
                else f"{gb} GB"
            )
            package_type = "exact"
        else:
            low = values[0]
            high = max(values)

            display_package = (
                f"{int(low) if low.is_integer() else low}"
                f"–"
                f"{int(high) if high.is_integer() else high} GB"
            )
            package_type = "range"

        key = (display_package, package_type)

        if (
            key not in cheapest
            or supplier_price < cheapest[key][1]
        ):
            cheapest[key] = (
                original_package,
                supplier_price,
                package_type,
                high if package_type == "range" else gb
            )

    items = []

    for (
        display_package,
        package_type
    ), (
        original_package,
        supplier_price,
        package_type,
        max_gb
    ) in cheapest.items():
        items.append((
            display_package,
            original_package,
            supplier_price,
            package_type,
            max_gb
        ))

    exact_items = [
        item
        for item in items
        if item[3] == "exact"
    ]

    filtered = []

    for item in items:
        (
            display_package,
            original_package,
            supplier_price,
            package_type,
            gb
        ) = item

        if package_type == "range":
            filtered.append(item)
            continue

        dominated = False

        for other in exact_items:
            (
                other_display,
                other_original,
                other_price,
                other_type,
                other_gb
            ) = other

            if other_display == display_package:
                continue

            if (
                other_gb > gb
                and other_price <= supplier_price
            ):
                dominated = True
                break

        if not dominated:
            filtered.append(item)

    filtered.sort(
        key=lambda x: (
            ((x[2] + MARKUP + x[2] * 7 // 1000 + 499) // 500) * 500,
            -x[4]
        )
    )

    for _i, _item in enumerate(filtered):

        if isinstance(_item, tuple) and len(_item) >= 1:

            filtered[_i] = (

                normalize_range_display(_item[0]),

                *_item[1:]

            )


    return filtered



def get_display_packages(provider, duration):
    items = _get_display_packages_base(provider, duration)

    # Jika beberapa paket punya harga jual yang sama,
    # tampilkan paket dengan kapasitas GB terbesar.
    best_by_price = {}

    def get_capacity(item):
        if not item:
            return 0.0

        display = str(item[0])

        # Prioritas GB
        match = re.search(r'(\\d+(?:[.,]\\d+)?)\\s*GB', display, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", "."))

        # Fallback MB
        match = re.search(r'(\\d+(?:[.,]\\d+)?)\\s*MB', display, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", ".")) / 1024

        # Fallback ke nilai gb dari tuple lama
        if len(item) >= 5 and isinstance(item[4], (int, float)):
            return float(item[4])

        return 0.0

    for item in items:
        if len(item) < 3:
            continue

        supplier_price = item[2]
        selling_price = ((supplier_price + MARKUP + supplier_price * 7 // 1000 + 499) // 500) * 500
        capacity = get_capacity(item)

        current = best_by_price.get(selling_price)

        if current is None or capacity > get_capacity(current):
            best_by_price[selling_price] = item

    return list(best_by_price.values())

def _sell_price(supplier_price):
    return ((supplier_price + MARKUP + supplier_price * 7 // 1000 + 499) // 500) * 500


def get_display_packages(provider, duration):
    """Paket yang tampil ke pembeli (menggantikan versi lama):
    - rentang (5–6 GB) ditampilkan sebagai batas bawahnya (5 GB)
    - ukuran sama -> ambil yang paling murah
    - paket lebih kecil tapi harga jualnya sama/lebih mahal dari paket
      yang lebih besar -> disembunyikan (per provider & durasi)
    """
    cheapest = {}
    for original, supplier_price in get_supplier_packages(provider, duration):
        if "malam" in original.lower():
            continue

        main = re.sub(r"\([^)]*\)", " ", original)
        values = [
            float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*GB", main, re.I)
        ]
        if not values:
            values = [
                float(x) / 1000
                for x in re.findall(r"(\d+(?:\.\d+)?)\s*MB", main, re.I)
            ]
        if not values:
            continue

        low, high = values[0], max(values)
        size = round(low, 3)
        current = cheapest.get(size)
        if current is None or supplier_price < current[2]:
            cheapest[size] = (
                f"{low:g} GB",
                original,
                supplier_price,
                "range" if len(values) > 1 else "exact",
                high,
            )

    items = []
    min_price = None
    for size in sorted(cheapest, reverse=True):      # dari yang terbesar
        item = cheapest[size]
        sell = _sell_price(item[2])
        if min_price is not None and sell >= min_price:
            continue                                  # kalah dari paket lebih besar
        items.append(item)
        min_price = sell if min_price is None else min(min_price, sell)

    items.sort(key=lambda x: (_sell_price(x[2]), -x[4]))
    return items


def package_menu(provider, duration):
    items = get_display_packages(provider, duration)

    blocks = [
        {
            "type": "heading",
            "text": f"📦 {provider} — {duration}",
            "size": 3
        },
        {
            "type": "paragraph",
            "text": "Pilih paket:"
        }
    ]

    for index, (
        display_package,
        original_package,
        supplier_price,
        package_type,
        gb
    ) in enumerate(items):
        price = ((supplier_price + MARKUP + supplier_price * 7 // 1000 + 499) // 500) * 500

        blocks.append({
            "type": "buttons",
            "buttons": [{
                "text": f"{display_package} — {rupiah(price)}",
                "callback_data": f"pkg|{provider}|{duration}|{index}"
            }]
        })

    return blocks


def confirm_menu():
    return [
        {
            "type": "buttons",
            "buttons": [{
                "text": "✅ Lanjut Bayar",
                "callback_data": "pay",
                "style": "success"
            }]
        },
        {
            "type": "buttons",
            "buttons": [{
                "text": "❌ Batal",
                "callback_data": "cancel",
                "style": "danger"
            }]
        }
    ]

def payment_menu():
    return (
        '<tg-button-row>'
        '<tg-button type="callback_data" data="cancel">❌ Batalkan Order</tg-button>'
        '</tg-button-row>'
    )


def admin_menu(order_id):
    return (
        '<tg-button-row>'
        f'<tg-button type="callback_data" data="admin_done|{order_id}">✅ SELESAI</tg-button>'
        f'<tg-button type="callback_data" data="admin_failed|{order_id}">❌ GAGAL</tg-button>'
        '</tg-button-row>'
    )


# =========================
# USER FLOW
# =========================


# =========================
# DAFTAR PENGGUNA (/cekuser, khusus admin)
# =========================
from telegram.ext import TypeHandler


def ensure_users_table():
    conn = db()
    try:
        ada = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                start_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        if not ada:
            # isi awal dari pembeli yang sudah pernah order
            conn.execute("""
                INSERT OR IGNORE INTO users
                (user_id, username, full_name, first_seen, last_seen, start_count)
                SELECT user_id, MAX(username), '', MIN(created_at), MAX(created_at), 0
                FROM orders GROUP BY user_id
            """)
        conn.commit()
    finally:
        conn.close()


async def track_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catat setiap pengguna yang berinteraksi (tidak mengubah alur bot)."""
    try:
        user = update.effective_user
        if not user or user.is_bot:
            return

        ensure_users_table()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        is_start = bool(
            update.message and update.message.text
            and update.message.text.startswith("/start")
        )
        name = " ".join(x for x in (user.first_name, user.last_name) if x)

        conn = db()
        try:
            conn.execute("""
                INSERT INTO users (user_id, username, full_name, first_seen, last_seen, start_count)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    last_seen = excluded.last_seen,
                    start_count = users.start_count + ?
            """, (user.id, user.username, name, now, now, 1 if is_start else 0,
                  1 if is_start else 0))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning("gagal catat pengguna: %s", e)


async def cekuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or user.id not in ADMIN_IDS:
        return

    ensure_users_table()
    per_page = 30
    page = 1
    if context.args and context.args[0].isdigit():
        page = max(1, int(context.args[0]))

    conn = db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        hari_ini = datetime.now().strftime("%Y-%m-%d")
        baru = conn.execute(
            "SELECT COUNT(*) FROM users WHERE first_seen >= ?", (hari_ini,)
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM users ORDER BY first_seen DESC LIMIT ? OFFSET ?",
            (per_page, (page - 1) * per_page)
        ).fetchall()
    finally:
        conn.close()

    pages = max(1, -(-total // per_page))
    lines = [
        f"👥 Total pengguna: {total}",
        f"🆕 Baru hari ini: {baru}",
        f"📄 Halaman {page}/{pages}",
        "",
    ]
    if not rows:
        lines.append("Belum ada data di halaman ini.")

    for i, r in enumerate(rows, start=(page - 1) * per_page + 1):
        nama = (r["full_name"] or "-")[:25]
        uname = f"@{r['username']}" if r["username"] else "tanpa username"
        gabung = datetime.strptime(r["first_seen"], "%Y-%m-%d %H:%M:%S").strftime("%d-%m %H:%M")
        lines.append(f"{i}. {nama} ({uname})\n   ID {r['user_id']} • gabung {gabung}")

    if page < pages:
        lines += ["", f"Lanjut: /cekuser {page + 1}"]

    await update.message.reply_text("\n".join(lines))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    # Maintenance harian WIB: 23.30 sampai 00.35.
    now_wib = datetime.now(timezone(timedelta(hours=7))).time()
    maintenance_start = time(23, 30)
    maintenance_end = time(0, 35)
    if now_wib >= maintenance_start or now_wib < maintenance_end:
        await update.effective_message.reply_text(
            "🛠️ *SERVER SEDANG MAINTENANCE*\n\n"
            "Kami sedang melakukan pemeliharaan sistem agar layanan tetap berjalan dengan baik.\n\n"
            "Layanan akan kembali tersedia setelah pukul *00.35 WIB*. "
            "Silakan coba lagi nanti. Terima kasih atas pengertiannya.\n\n"
            "— Akira",
            parse_mode="Markdown"
        )
        return

    # Deep link dari katalog @networwk
    param = context.args[0].lower().strip() if context.args else ""

    quota_links = {
        "quota_telkomsel": "Telkomsel",
        "quota_byu": "BY.U",
        "quota_three": "Three",
        "quota_indosat": "Indosat / IM3",
        "quota_smartfren": "Smartfren",
        "quota_xl": "XL",
        "quota_axis": "AXIS",
    }

    if param in quota_links:
        provider = quota_links[param]

        if provider not in PRODUCTS:
            await update.message.reply_text(
                f"Provider {provider} belum tersedia."
            )
            return

        context.user_data["provider"] = provider
        context.user_data["selecting_provider"] = False
        context.user_data["selecting_duration"] = True
        context.user_data["selecting_package"] = False

        await update.message.reply_text(
            f"📶 *{provider}*\n\nSilakan pilih durasi:",
            parse_mode="Markdown",
            reply_markup=duration_menu(provider)
        )
        return

    if param == "pulsa":
        if "pulsa" not in FIXED_PRODUCTS:
            await update.message.reply_text("Menu pulsa belum tersedia.")
            return

        context.user_data["fixed_key"] = "pulsa"
        context.user_data["selecting_fixed_provider"] = True

        await update.message.reply_text(
            f"{FIXED_PRODUCTS['pulsa']['menu_text']}\n\nPilih provider:",
            reply_markup=fixed_provider_menu("pulsa")
        )
        return

    if param == "pln":
        if "pln" not in FIXED_PRODUCTS:
            await update.message.reply_text("Menu token listrik belum tersedia.")
            return

        providers = list(FIXED_PRODUCTS["pln"]["providers"].keys())
        if not providers:
            await update.message.reply_text("Paket token listrik belum tersedia.")
            return

        context.user_data["fixed_key"] = "pln"
        context.user_data["selecting_fixed_provider"] = True

        send_rich_message(
            BOT_TOKEN,
            update.effective_chat.id,
            {"blocks": fixed_package_menu("pln", providers[0])}
        )
        return

    if param in ("mlbb", "ff"):
        if param not in GAME_PRODUCTS:
            await update.message.reply_text("Menu game belum tersedia.")
            return

        context.user_data["game_key"] = param
        context.user_data["selecting_game_category"] = True

        await update.message.reply_text(
            f"{GAME_PRODUCTS[param]['menu_text']}\n\nPilih kategori:",
            reply_markup=game_category_menu(param)
        )
        return

    keyboard = MAIN_KEYBOARD_ROWS

    rich_html = (
        "🛍️ Bot Order by Akira<br><br>"
        "📱 Kuota Internet<br>"
        "⭐ Telegram<br>"
        "💎 Top Up Game<br>"
        "⚡ Proses cepat & manual<br>"
        "💳 Pembayaran via QRIS<br>"
        '<tg-button-row><tg-button type="url" url="https://t.me/vNamwoon">👤 Admin</tg-button></tg-button-row>'
        '<tg-button-row><tg-button type="url" url="https://t.me/verlfy">⭐ Testimonial</tg-button></tg-button-row>'
    )

    await rich_reply(
        update.effective_chat.id,
        rich_html,
        mode="html"
    )

    await update.message.reply_text(
        "Pilih layanan:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )
    )


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    data = q.data

    if data == "info_order":
        await q.edit_message_text(
            """📋 *CARA ORDER*

1. Pilih 📶 Kuota Internet
2. Pilih provider
3. Pilih durasi & paket
4. Masukkan nomor tujuan
5. Lanjut pembayaran via QRIS
6. Kirim bukti pembayaran
7. Pesanan diproses secara manual oleh admin

👤 Admin: @vNamwoon""",
            parse_mode="Markdown",
            
        )
        return

    if data == "order":
        context.user_data.clear()
        context.user_data["selecting_provider"] = True
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(
            "📶 *Pilih Provider*",
            parse_mode="Markdown",
            
        )
        return
    if data == "home":
        context.user_data.clear()

        keyboard = [
            [KeyboardButton("📊 Kuota Internet")]
        ]

        await q.edit_message_text(
            """🛍️ SELAMAT DATANG DI BELI KUOTA — BY AKIRA

📱 Layanan Kuota Internet
⚡ Proses cepat & manual
💳 Pembayaran via QRIS

👤 ADMIN: @vNamwoon
⭐ TESTIMONIAL: @verlfy

🛒 MENU ORDER
Pilih layanan:""",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        )
        return
    if data == "menu_quota":
        context.user_data.clear()
        await q.edit_message_text(
            "📶 *Pilih Provider*",
            parse_mode="Markdown",
            
        )
        return

    if data.startswith("duration|"):
        _, provider, duration = data.split("|", 2)

        print("DEBUG DURATION:", repr(provider), repr(duration))

        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(
            f"📶 *{provider} — {duration}*\n\nPilih paket:",
            parse_mode="Markdown",
            
        )
        return

    if data.startswith("provider|"):
        _, provider = data.split("|", 1)

        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(
            f"📶 *{provider}*\n\nPilih durasi:",
            parse_mode="Markdown",
            
        )
        return

    if data.startswith("pkg|"):
        _, provider, duration, index = data.split("|", 3)

        try:
            index = int(index)
        except ValueError:
            await q.answer("❌ Paket tidak valid.", show_alert=True)
            return

        items = get_display_packages(provider, duration)

        if index < 0 or index >= len(items):
            await q.answer(
                "❌ Paket sudah berubah. Silakan pilih ulang.",
                show_alert=True
            )
            return

        display_package, original_package, supplier_price, package_type, gb = items[index]

        price = ((supplier_price + MARKUP + supplier_price * 7 // 1000 + 499) // 500) * 500

        context.user_data.update({
            "provider": provider,
            "duration": duration,
            "package": display_package,
            "price": price,
            "selecting_provider": False,
            "selecting_duration": False,
            "selecting_package": False,
        })

        context.user_data["awaiting_phone"] = True

        await q.edit_message_text(
            f"📦 *Pesanan*\n\n"
            f"Provider: {provider}\n"
            f"Durasi: {duration}\n"
            f"Paket: {display_package}\n"
            f"Harga: {rupiah(price)}\n\n"
            f"📱 Kirim nomor HP yang akan diisi.\n"
            f"Contoh: `081234567890`",
            parse_mode="Markdown"
        )
        return

    if data.startswith("gpkg|"):
        _, key, cat_index, index = data.split("|", 3)
        game = GAME_PRODUCTS.get(key)

        try:
            cat_index, index = int(cat_index), int(index)
            if key in ("mlbb", "ff"):
                packages = game_categories_dynamic(key)[cat_index]["packages"]
            else:
                packages = game["categories"][cat_index]["packages"]
            label, price = packages[index]
        except (TypeError, ValueError, IndexError, KeyError):
            await q.answer("❌ Paket tidak valid.", show_alert=True)
            return

        context.user_data.clear()
        context.user_data.update({
            "game_key": key,
            "selecting_game_category": True,
            "provider": game["name"],
            "duration": "-",
            "package": label,
            "price": price,
            "awaiting_target": True,
        })

        await q.edit_message_text(
            f"📦 *Pesanan*\n\n"
            f"Layanan: {game['name']}\n"
            f"Paket: {label}\n"
            f"Harga: {rupiah(price)}\n\n"
            f"{game['target_prompt']}",
            parse_mode="Markdown"
        )
        return

    if data.startswith("fpkg|"):
        _, key, provider_index, index = data.split("|", 3)
        fixed = FIXED_PRODUCTS.get(key)

        try:
            provider = list(fixed["providers"].keys())[int(provider_index)]
            label, price = fixed["providers"][provider][int(index)]
        except (TypeError, ValueError, IndexError):
            await q.answer("❌ Paket tidak valid.", show_alert=True)
            return

        context.user_data.clear()
        context.user_data.update({
            "fixed_key": key,
            "selecting_fixed_provider": True,
            "provider": provider,
            "duration": "-",
            "package": label,
            "price": price,
            "awaiting_phone": True,
        })

        if provider == "Token PLN":
            prompt = "🎯 Kirim ID Pelanggan / No. Meter PLN.\nContoh: `12345678901`"
        else:
            prompt = "📱 Kirim nomor HP yang akan diisi.\nContoh: `081234567890`"

        await q.edit_message_text(
            f"📦 *Pesanan*\n\n"
            f"Provider: {provider}\n"
            f"Paket: {label}\n"
            f"Harga: {rupiah(price)}\n\n"
            f"{prompt}",
            parse_mode="Markdown"
        )
        return

    if data == "cancel":
        context.user_data.clear()

        await q.edit_message_text(
            "❌ *Order dibatalkan.*",
            parse_mode="Markdown"
        )

        await q.message.reply_text(
            "Silakan pilih layanan:",
            reply_markup=ReplyKeyboardMarkup(
                MAIN_KEYBOARD_ROWS,
                resize_keyboard=True,
                one_time_keyboard=False
            )
        )
        return

    if data == "pay":
        data_order = {
            "user_id": q.from_user.id,
            "username": q.from_user.username or "",
            "provider": context.user_data.get("provider"),
            "duration": context.user_data.get("duration"),
            "package": context.user_data.get("package"),
            "price": context.user_data.get("price"),
            "phone": context.user_data.get("phone"),
            "category": (
                "stars" if context.user_data.get("game_key") == "stars"
                else "diamond" if context.user_data.get("game_key") in ("mlbb", "ff")
                else {
                    "pulsa": "pulsa",
                    "masa": "masa",
                    "pln": "token",
                }.get(context.user_data.get("fixed_key"), "kuota")
            ),
        }

        required = ["provider", "duration", "package", "price", "phone"]

        if any(data_order.get(key) is None for key in required):
            await q.answer(
                "❌ Data order tidak lengkap. Silakan ulangi order.",
                show_alert=True
            )
            return

        order_id = create_order(data_order)
        context.user_data["order_id"] = order_id
        context.user_data["awaiting_proof"] = True

        await q.answer("Pembayaran diproses.")

        await send_qris(
            q.message,
            caption=(
                f"💳 *PEMBAYARAN ORDER #{order_id:04d}*\n\n"
                f"📦 {data_order['provider']} — {data_order['package']}\n"
                f"{target_label(data_order['provider'])}: `{data_order['phone']}`\n"
                f"💰 Total: *{rupiah(data_order['price'])}*\n\n"
                "Silakan scan QRIS di atas dan lakukan pembayaran.\n"
                "Setelah pembayaran, kirim *foto bukti pembayaran* di chat ini."
            ),
            parse_mode="Markdown",
            
        )
        return

    if data.startswith("buyer_confirm|"):
        order_id = int(data.split("|", 1)[1])
        order = get_order(order_id)

        if not order:
            await q.answer("Order tidak ditemukan.", show_alert=True)
            return

        if q.from_user.id != order["user_id"]:
            await q.answer("⛔ Ini bukan order kamu.", show_alert=True)
            return

        await q.answer("Konfirmasi diterima.")
        await q.edit_message_reply_markup(reply_markup=None)

        keyboard = [
            [
                KeyboardButton(
                    "✅ KONFIRMASI SELESAI",
                    callback_data=f"admin_finish|{order_id}"
                )
            ]
        ]

        await send_admin_message(
            context.bot,
            text=(
                f"🔔 *KONFIRMASI BUYER*\n\n"
                f"Order: #{order_id:04d}\n"
                f"👤 @{order['username'] or '-'}\n"
                f"🆔 User ID: `{order['user_id']}`\n"
                f"📦 {order['provider']} — {order['package']}\n"
                f"{target_label(order['provider'])}: `{order['phone']}`\n\n"
                f"Buyer mengonfirmasi bahwa pesanan sudah masuk."
            ),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        )
        return

    if data.startswith("admin_finish|"):
        if q.from_user.id not in ADMIN_IDS:
            await q.answer("⛔ Akses ditolak.", show_alert=True)
            return

        order_id = int(data.split("|", 1)[1])
        order = get_order(order_id)

        if not order:
            await q.answer("Order tidak ditemukan.", show_alert=True)
            return

        update_status(order_id, "DONE")

        await q.answer("Order berhasil difinalisasi.")
        await q.edit_message_reply_markup(reply_markup=None)

        await context.bot.send_message(
            chat_id=order["user_id"],
            text=(
                "Orderan terkonfirmasi telah selesai, "
                "harap isi rnk di t.me/rephutasi/2. Terimakasih.\n"
                "— Akira"
            )
        )

        await q.message.reply_text(
            f"✅ Order #{order_id:04d} resmi ditandai SELESAI."
        )
        return

    if data.startswith("admin_done|") or data.startswith("admin_failed|"):
        if q.from_user.id not in ADMIN_IDS:
            await q.answer("⛔ Akses ditolak.", show_alert=True)
            return

        action, order_id_text = data.split("|", 1)
        order_id = int(order_id_text)
        order = get_order(order_id)

        if not order:
            await q.answer("Order tidak ditemukan.", show_alert=True)
            return

        if action == "admin_done":
            context.user_data["awaiting_receipt"] = order_id

            await q.answer()
            await q.message.reply_text(
                f"🧾 *ORDER #{order_id:04d}*\n\n"
                f"Silakan kirim *foto struk* untuk dikirim ke buyer.",
                parse_mode="Markdown"
            )
            return

        else:
            update_status(order_id, "FAILED")

            buyer_text = (
                f"❌ *ORDER GAGAL*\n\n"
                f"Order: #{order_id:04d}\n"
                f"{order['provider']} — {order['package']}\n\n"
                f"Pesanan tidak dapat diproses. Silakan hubungi admin untuk tindak lanjut."
            )

            await context.bot.send_message(
                order["user_id"],
                buyer_text,
                parse_mode="Markdown"
            )

            await q.edit_message_reply_markup(reply_markup=None)
            await q.message.reply_text(
                f"❌ Order #{order_id:04d} ditandai GAGAL."
            )
            return

# =========================
# PESAN BEBAS DARI BUYER -> DITERUSKAN KE ADMIN (+ admin bisa balas)
# =========================
def _buyer_header(user):
    nama = " ".join(x for x in (user.first_name, user.last_name) if x) or "-"
    uname = f"@{user.username}" if user.username else "tanpa username"
    return f"👤 {nama} ({uname})\nID: {user.id}  #U{user.id}"


def _relay_allowed(context, key, jeda):
    """Anti-spam sederhana per pembeli."""
    now = datetime.now().timestamp()
    if now - context.user_data.get(key, 0) < jeda:
        return False
    context.user_data[key] = now
    return True


_BTN_CACHE = {"t": 0, "set": set()}


def _norm_btn(t):
    """Samakan teks: buang emoji/simbol di depan, huruf kecil."""
    t = re.sub(r"^[^0-9A-Za-z]+", "", str(t or "").strip())
    return t.lower().strip()


def _known_button_texts():
    """Semua teks yang sudah punya fungsi di bot (tombol menu, provider, durasi, dll)."""
    now = datetime.now().timestamp()
    if _BTN_CACHE["set"] and now - _BTN_CACHE["t"] < 60:
        return _BTN_CACHE["set"]

    labels = {
        "⬅️ Kembali", "✅ KONFIRMASI SELESAI",
        "✅ Pesanan Sudah Masuk", "✅ Kuota Sudah Masuk",
    }
    # 1) teks tombol statis yang tertulis di kode bot
    try:
        src = Path(__file__).read_text(encoding="utf-8")
        labels.update(re.findall(r'KeyboardButton\(\s*"([^"]+)"', src))
    except Exception:
        pass
    # 2) menu yang disusun dari data
    labels.update(globals().get("PRODUCTS", {}).keys())
    for key in ("GAME_PRODUCTS", "FIXED_PRODUCTS"):
        for g in globals().get(key, {}).values():
            labels.add(g.get("menu_text", ""))
            labels.update(c.get("name", "") for c in g.get("categories", []))
            labels.update(g.get("providers", {}).keys())
    # 3) durasi dari pricelist
    try:
        conn = db()
        try:
            labels.update(r[0] for r in conn.execute("SELECT DISTINCT duration FROM pricelist"))
        finally:
            conn.close()
    except Exception:
        pass

    result = {_norm_btn(x) for x in labels if x}
    _BTN_CACHE["t"], _BTN_CACHE["set"] = now, result
    return result


def _is_button_text(text):
    return _norm_btn(text) in _known_button_texts()


async def relay_buyer_message(update: Update, context: ContextTypes.DEFAULT_TYPE, ack=True):
    user = update.effective_user
    if not user or user.id in ADMIN_IDS:
        return False
    if _is_button_text(update.message.text):
        return False          # teks tombol bukan pesan ketikan
    if not _relay_allowed(context, "relay_last", 1.5):
        return False

    body = (
        "💬 Pesan dari buyer\n"
        f"{_buyer_header(user)}\n\n"
        f"{update.message.text}\n\n"
        "↩️ Reply pesan ini untuk membalas buyer."
    )

    terkirim = 0
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=body[:4000])
            terkirim += 1
        except Exception as e:
            logger.warning("gagal teruskan pesan ke admin %s: %s", admin_id, e)

    if terkirim == 0:
        if ack:
            await update.message.reply_text(
                "⚠️ Pesan belum bisa diteruskan ke admin. Coba lagi sebentar lagi ya."
            )
    elif ack and _relay_allowed(context, "relay_ack", 60):
        await update.message.reply_text(
            "✅ Pesan kamu sudah diteruskan ke admin. Mohon tunggu balasannya ya.\n\n"
            "Untuk order, ketik /start."
        )

    return terkirim > 0


async def relay_buyer_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or user.id in ADMIN_IDS:
        return False
    if not _relay_allowed(context, "relay_last", 1.5):
        return True

    header = (
        "📷 Foto dari buyer\n"
        f"{_buyer_header(user)}\n\n"
        "↩️ Reply pesan ini untuk membalas buyer."
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=header)
            await context.bot.forward_message(
                chat_id=admin_id,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id,
            )
        except Exception as e:
            logger.warning("gagal teruskan foto ke admin %s: %s", admin_id, e)
    return True


async def relay_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin me-reply pesan relay dari bot -> dikirim ke buyer. True jika diproses."""
    replied = update.message.reply_to_message
    if not replied or not replied.from_user or replied.from_user.id != context.bot.id:
        return False

    m = re.search(r"#U(\d+)", replied.text or replied.caption or "")
    if not m:
        return False

    try:
        await context.bot.send_message(
            chat_id=int(m.group(1)),
            text=f"💬 Admin:\n{update.message.text}"
        )
        await update.message.reply_text("✅ Terkirim ke buyer.")
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal kirim ke buyer: {e}")
    return True


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # ADMIN membalas pesan buyer (reply ke pesan relay dari bot)
    if (
        update.effective_user.id in ADMIN_IDS
        and update.message.reply_to_message
        and await relay_admin_reply(update, context)
    ):
        return

    if text in ("✅ Kuota Sudah Masuk", "✅ Pesanan Sudah Masuk"):
        order = get_waiting_confirmation_order(update.effective_user.id)

        if not order:
            await update.message.reply_text(
                "❌ Tidak ada order yang menunggu konfirmasi."
            )
            return

        update_status(order["id"], "WAITING_SELLER_CONFIRMATION")

        keyboard = [
            [KeyboardButton("✅ KONFIRMASI SELESAI")]
        ]

        await send_admin_message(
            context.bot,
            text=(
                f"🔔 *KONFIRMASI BUYER*\n\n"
                f"Order: #{order['id']:04d}\n"
                f"👤 @{order['username'] or '-'}\n"
                f"🆔 User ID: `{order['user_id']}`\n"
                f"📦 {order['provider']} — {order['package']}\n"
                f"{target_label(order['provider'])}: `{order['phone']}`\n\n"
                f"Buyer mengonfirmasi bahwa pesanan sudah masuk."
            ),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True,
                one_time_keyboard=False
            )
        )

        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text(
                "✅ Konfirmasi diterima.\n\n"
                "Admin akan menyelesaikan order.",
                reply_markup=ReplyKeyboardRemove()
            )
        return

    if text == "✅ KONFIRMASI SELESAI":
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Akses ditolak.")
            return

        order = get_seller_confirmation_order()

        if not order:
            await update.message.reply_text(
                "❌ Tidak ada order yang menunggu konfirmasi seller."
            )
            return

        order_id = order["id"]
        update_status(order_id, "DONE")

        await context.bot.send_message(
            chat_id=order["user_id"],
            text=(
                "Orderan terkonfirmasi telah selesai, "
                "harap isi rnk di t.me/rephutasi/2. Terimakasih.\n"
                "— Akira"
            )
        )

        await update.message.reply_text(
            f"✅ Order #{order_id:04d} resmi ditandai SELESAI.",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # MENU PULSA / MASA AKTIF -> pilih provider
    if text in FIXED_BY_MENU:
        key = FIXED_BY_MENU[text]
        context.user_data.clear()
        context.user_data["fixed_key"] = key
        context.user_data["selecting_fixed_provider"] = True

        providers = list(FIXED_PRODUCTS[key]["providers"].keys())
        if len(providers) == 1:
            # cuma satu provider (mis. Token PLN): langsung tampilkan paket
            send_rich_message(
                BOT_TOKEN,
                update.effective_chat.id,
                {"blocks": fixed_package_menu(key, providers[0])}
            )
            return

        await update.message.reply_text(
            f"{FIXED_PRODUCTS[key]['menu_text']}\n\nPilih provider:",
            reply_markup=fixed_provider_menu(key)
        )
        return

    if context.user_data.get("selecting_fixed_provider"):
        key = context.user_data.get("fixed_key")
        fixed = FIXED_PRODUCTS.get(key)

        if text == "⬅️ Kembali":
            context.user_data.clear()
            await update.message.reply_text(
                "🛍️ Silakan pilih layanan:",
                reply_markup=ReplyKeyboardMarkup(
                    MAIN_KEYBOARD_ROWS,
                    resize_keyboard=True,
                    one_time_keyboard=False
                )
            )
            return

        if fixed and text in fixed["providers"]:
            context.user_data["awaiting_phone"] = False
            send_rich_message(
                BOT_TOKEN,
                update.effective_chat.id,
                {"blocks": fixed_package_menu(key, text)}
            )
            return

    # MENU STARS / GAME -> pilih kategori
    if text in GAME_BY_MENU:
        key = GAME_BY_MENU[text]
        context.user_data.clear()
        context.user_data["game_key"] = key
        context.user_data["selecting_game_category"] = True

        await update.message.reply_text(
            f"{GAME_PRODUCTS[key]['menu_text']}\n\nPilih kategori:",
            reply_markup=game_category_menu(key)
        )
        return

    # KATEGORI GAME / KEMBALI
    if context.user_data.get("selecting_game_category"):
        key = context.user_data.get("game_key")
        game = GAME_PRODUCTS.get(key)

        if text == "⬅️ Kembali":
            context.user_data.clear()
            await update.message.reply_text(
                "🛍️ Silakan pilih layanan:",
                reply_markup=ReplyKeyboardMarkup(
                    MAIN_KEYBOARD_ROWS,
                    resize_keyboard=True,
                    one_time_keyboard=False
                )
            )
            return

        if game:
            for cat_index, category in enumerate(game["categories"]):
                if text == category["name"]:
                    context.user_data["awaiting_target"] = False
                    send_rich_message(
                        BOT_TOKEN,
                        update.effective_chat.id,
                        {"blocks": game_package_menu(key, cat_index)}
                    )
                    return

    # INPUT TUJUAN (username Telegram / ID game)
    if context.user_data.get("awaiting_target"):
        key = context.user_data.get("game_key")
        target, error = validate_target(key, text)

        if error:
            await update.message.reply_text(error, parse_mode="Markdown")
            return

        # kolom `phone` di tabel orders dipakai untuk menyimpan tujuan
        context.user_data["phone"] = target
        context.user_data["awaiting_target"] = False

        provider = context.user_data["provider"]

        confirm_blocks = [
            {
                "type": "heading",
                "text": "📋 KONFIRMASI ORDER",
                "size": 3
            },
            {
                "type": "paragraph",
                "text": (
                    f"Layanan: {provider}\n"
                    f"Paket: {context.user_data['package']}\n"
                    f"{target_label(provider)}: {target}\n"
                    f"Total: {rupiah(context.user_data['price'])}\n\n"
                    "Pastikan semua data sudah benar."
                )
            },
            {
                "type": "buttons",
                "buttons": [{
                    "text": "✅ Lanjut Bayar",
                    "callback_data": "pay",
                    "style": "success"
                }]
            },
            {
                "type": "buttons",
                "buttons": [{
                    "text": "❌ Batal",
                    "callback_data": "cancel",
                    "style": "danger"
                }]
            }
        ]

        send_rich_message(
            BOT_TOKEN,
            update.effective_chat.id,
            {"blocks": confirm_blocks}
        )
        return

    if text == "📊 Kuota Internet":
        context.user_data.clear()
        context.user_data["selecting_provider"] = True
        await update.message.reply_text(
            "📶 *Pilih Provider*",
            parse_mode="Markdown",
            reply_markup=provider_menu()
        )
        return


    # NAVIGASI PROVIDER → DURASI → PAKET

    # KEMBALI DARI MENU PAKET → PROVIDER
    if context.user_data.get("selecting_package") and text == "⬅️ Kembali":
        context.user_data.pop("provider", None)
        context.user_data.pop("duration", None)
        context.user_data["selecting_package"] = False
        context.user_data["selecting_duration"] = False
        context.user_data["selecting_provider"] = True

        await update.message.reply_text(
            "📶 *Pilih Provider*",
            parse_mode="Markdown",
            reply_markup=provider_menu()
        )
        return

    # KEMBALI DARI MENU DURASI → PROVIDER
    if context.user_data.get("selecting_duration") and text == "⬅️ Kembali":
        context.user_data.pop("provider", None)
        context.user_data.pop("duration", None)
        context.user_data["selecting_duration"] = False
        context.user_data["selecting_package"] = False
        context.user_data["selecting_provider"] = True

        await update.message.reply_text(
            "📶 *Pilih Provider*",
            parse_mode="Markdown",
            reply_markup=provider_menu()
        )
        return

    # KEMBALI DARI MENU PROVIDER → MENU KUOTA
    if context.user_data.get("selecting_provider") and text == "⬅️ Kembali":
        context.user_data.clear()

        keyboard = MAIN_KEYBOARD_ROWS

        await update.message.reply_text(
            "🛍️ Silakan pilih layanan:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True,
                one_time_keyboard=False
            )
        )
        return

    # PILIH PROVIDER
    if context.user_data.get("selecting_provider"):
        if text in PRODUCTS:
            context.user_data["provider"] = text
            context.user_data["selecting_provider"] = False
            context.user_data["selecting_duration"] = True
            context.user_data["selecting_package"] = False

            await update.message.reply_text(
                f"📶 *{text}*\n\nSilakan pilih durasi:",
                parse_mode="Markdown",
                reply_markup=duration_menu(text)
            )
            return

    # PILIH DURASI
    # User BOLEH berpindah durasi berkali-kali tanpa /start.
    if context.user_data.get("selecting_duration") or context.user_data.get("selecting_package"):
        provider = context.user_data.get("provider")

        if provider:
            conn = db()
            row = conn.execute("""
                SELECT 1
                FROM pricelist
                WHERE provider = ?
                  AND duration = ?
                  AND available = 1
                LIMIT 1
            """, (SUPPLIER_PROVIDER_MAP.get(provider, provider), text)).fetchone()
            conn.close()

            if not row:
                await relay_buyer_message(update, context)
                return

            duration = text

            context.user_data["duration"] = duration
            context.user_data["selecting_duration"] = True
            context.user_data["selecting_package"] = True

            send_rich_message(
                BOT_TOKEN,
                update.effective_chat.id,
                {"blocks": package_menu(provider, duration)}
            )
            return

    if context.user_data.get("awaiting_phone"):
        phone = update.message.text.strip().replace(" ", "").replace("-", "")

        if context.user_data.get("provider") == "Token PLN":
            valid = phone.isdigit() and len(phone) in (11, 12)
            err = "❌ ID Pelanggan tidak valid.\nKirim 11 digit (No. Meter) atau 12 digit (ID Pelanggan)."
        else:
            valid = phone.isdigit() and 10 <= len(phone) <= 15
            err = "❌ Nomor HP tidak valid.\nKirim nomor HP 10–15 digit."

        if not valid:
            await update.message.reply_text(err)
            return

        context.user_data["phone"] = phone
        context.user_data["awaiting_phone"] = False
        duration_line = (
            "" if context.user_data["duration"] == "-"
            else f"Durasi: {context.user_data['duration']}\n"
        )

        confirm_blocks = [
            {
                "type": "heading",
                "text": "📋 KONFIRMASI ORDER",
                "size": 3
            },
            {
                "type": "paragraph",
                "text": (
                    f"Provider: {context.user_data['provider']}\n"
                    f"{duration_line}"
                    f"Paket: {context.user_data['package']}\n"
                    f"{target_label(context.user_data['provider']).split(' ', 1)[1]}: {phone}\n"
                    f"Total: {rupiah(context.user_data['price'])}\n\n"
                    "Pastikan semua data sudah benar."
                )
            },
            {
                "type": "buttons",
                "buttons": [{
                    "text": "✅ Lanjut Bayar",
                    "callback_data": "pay",
                    "style": "success"
                }]
            },
            {
                "type": "buttons",
                "buttons": [{
                    "text": "❌ Batal",
                    "callback_data": "cancel",
                    "style": "danger"
                }]
            }
        ]

        send_rich_message(
            BOT_TOKEN,
            update.effective_chat.id,
            {"blocks": confirm_blocks}
        )
        return

    if _is_button_text(update.message.text):
        await update.message.reply_text("Ketik /start untuk membuat order.")
        return

    await relay_buyer_message(update, context)

async def photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # ADMIN MENGIRIM STRUK
    if update.effective_user.id in ADMIN_IDS and context.user_data.get("awaiting_receipt"):
        order_id = context.user_data["awaiting_receipt"]
        order = get_order(order_id)

        if not order:
            context.user_data.pop("awaiting_receipt", None)
            await update.message.reply_text("❌ Order tidak ditemukan.")
            return

        photo = update.message.photo[-1]
        sn = update.message.caption or "-"
        try:
            save_receipt(order_id, photo.file_id)
        except Exception as e:
            logger.warning("gagal simpan struk order #%s: %s", order_id, e)
        context.user_data.pop("awaiting_receipt", None)
        is_game = any(g["name"] == order["provider"] for g in GAME_PRODUCTS.values())
        sn_label = "Token" if order["provider"] == "Token PLN" else "SN"
        sn_line = "" if is_game else f"🔑 {sn_label}: `{sn}`\n"

        # admin kirim struk = order langsung selesai, tanpa menunggu konfirmasi buyer
        update_status(order_id, "DONE")

        await context.bot.send_photo(
            chat_id=order["user_id"],
            photo=photo.file_id,
            caption=(
                f"🧾 *BUKTI TRANSAKSI ORDER #{order_id:04d}*\n\n"
                f"📦 {order['provider']} — {order['package']}\n"
                  f"{target_label(order['provider'])}: `{order['phone']}`\n"
                  f"{sn_line}\n"
                  f"Orderan telah selesai, "
                  f"harap isi rnk di t.me/rephutasi/2. Terimakasih.\n"
                  f"— Akira"
              ),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )

        await update.message.reply_text(
            f"✅ Struk order #{order_id:04d} terkirim. Order SELESAI."
        )
        return	

    if not context.user_data.get("awaiting_proof"):
        if await relay_buyer_photo(update, context):
            await update.message.reply_text(
                "✅ Foto kamu sudah diteruskan ke admin.\n\nUntuk order, ketik /start."
            )
            return
        await update.message.reply_text(
            "Belum ada order yang menunggu bukti pembayaran. Ketik /start untuk order."
        )
        return

    order_id = context.user_data.get("order_id")
    if not order_id:
        await update.message.reply_text("Order tidak ditemukan. Silakan mulai lagi dengan /start.")
        return

    photo = update.message.photo[-1]
    sn = update.message.caption or "-"
    update_proof(order_id, photo.file_id)
    context.user_data["awaiting_proof"] = False

    order = get_order(order_id)

    await update.message.reply_text(
        f"✅ *BUKTI PEMBAYARAN DITERIMA*\n\n"
        f"Order: #{order_id:04d}\n"
        f"Status: ⏳ Sedang diproses\n\n"
        f"Pesanan akan diproses secara manual. Mohon tunggu.",
        parse_mode="Markdown"
    )

    duration_line = (
        "" if order["duration"] == "-"
        else f"📅 Durasi: {order['duration']}\n"
    )

    caption = (
        f"🔔 <b>ORDER BARU #{order_id:04d}</b>\n\n"
        f"👤 @{order['username'] or '-'}\n"
        f"🆔 User ID: <tg-spoiler>{order['user_id']}</tg-spoiler>\n"
        f"📶 Provider: {order['provider']}\n"
        f"{duration_line}"
        f"📦 Paket: {order['package']}\n"
        f"{target_label(order['provider'])}: <tg-spoiler>{order['phone']}</tg-spoiler>\n"
        f"💰 Total: <b>{rupiah(order['price'])}</b>\n"
        f"📌 Status: PROCESSING"
    )

    await send_admin_photo(
        context.bot,
        photo=photo.file_id,
        caption=caption,
        parse_mode="HTML"
    )

    admin_blocks = [
        {
            "type": "paragraph",
            "text": f"📦 ORDER #{order_id:04d} — TINDAKAN ADMIN"
        },
        {
            "type": "buttons",
            "buttons": [{
                "text": "✅ SELESAI",
                "callback_data": f"admin_done|{order_id}",
                "style": "success"
            }]
        },
        {
            "type": "buttons",
            "buttons": [{
                "text": "❌ GAGAL",
                "callback_data": f"admin_failed|{order_id}",
                "style": "danger"
            }]
        }
    ]

    for admin_id in ADMIN_IDS:
        send_rich_message(
            BOT_TOKEN,
            admin_id,
            {"blocks": admin_blocks}
        )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Akses ditolak.")
        return

    conn = db()
    rows = conn.execute("""
        SELECT * FROM orders
        WHERE status='PROCESSING'
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📭 Tidak ada order yang sedang diproses.")
        return

    lines = ["📦 *ORDER AKTIF*\n"]
    for row in rows:
        lines.append(
            f"#{row['id']:04d} · {row['provider']} {row['package']} · "
            f"{rupiah(row['price'])}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Akses ditolak.")
        return

    conn = db()
    order = conn.execute("""
        SELECT * FROM orders
        WHERE status='PROCESSING'
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()
    conn.close()

    if not order:
        await update.message.reply_text("📭 Tidak ada order yang sedang diproses.")
        return

    order_id = order["id"]
    update_status(order_id, "DONE")

    await context.bot.send_message(
        chat_id=order["user_id"],
        text=(
            "Orderan terkonfirmasi telah selesai, "
            "harap isi rnk di t.me/rephutasi/2. Terimakasih.\\n"
            "— Akira"
        )
    )

    await send_admin_message(
        context.bot,
        text=f"✅ Order #{order_id:04d} berhasil diselesaikan via /done."
    )

    await update.message.reply_text(
        f"✅ Order #{order_id:04d} selesai."
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled exception", exc_info=context.error)

async def auto_finish_order(context: ContextTypes.DEFAULT_TYPE):
    order_id = context.job.data
    order = get_order(order_id)

    if not order:
        return

    if order["status"] != "PROCESSING":
        return

    update_status(order_id, "DONE")

    await context.bot.send_message(
        chat_id=order["user_id"],
        text=(
            "Orderan terkonfirmasi telah selesai, "
            "harap isi rnk di t.me/rephutasi/2. Terimakasih.\n"
            "— Akira"
        )
    )

    await send_admin_message(context.bot,
        text=f"⏱️ Order #{order_id:04d} otomatis SELESAI setelah 5 menit tanpa konfirmasi buyer."
    )

def main():
    if BOT_TOKEN == "ISI_BOT_TOKEN_DI_SINI":
        raise SystemExit(
            "Isi BOT_TOKEN di file bot.py terlebih dahulu."
        )

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(TypeHandler(Update, track_user), group=-2)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cekuser", cekuser))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.PHOTO, photo_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    app.add_error_handler(error_handler)

    print("Bot kuota berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()

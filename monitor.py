import os
import re
import json
import time
import sqlite3
from datetime import datetime, timedelta
import urllib.request
import urllib.parse
from html import unescape

INTERVAL = 900  # 15 menit
DATA_FILE = "price_snapshot.json"

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
REKAP_CHANNEL = "@rekapf"
MARKUP = 1000

URLS = {
    "BY.U": [
        "https://isipulsa.web.id/harga/paket-kuota/byu-kuota-harian?page=1",
        "https://isipulsa.web.id/harga/paket-kuota/byu-kuota-harian?page=2",
        "https://isipulsa.web.id/harga/paket-kuota/byu-kuota-bulanan?page=1",
        "https://isipulsa.web.id/harga/paket-kuota/byu-kuota-bulanan?page=2",
    ],

    "Indosat": [
        "https://isipulsa.web.id/harga/paket-internet/indosat-freedom-internet-mini?page=1",
        "https://isipulsa.web.id/harga/paket-internet/indosat-freedom-internet-mini?page=2",
        "https://isipulsa.web.id/harga/paket-internet/indosat-freedom-internet-mini?page=3",
        "https://isipulsa.web.id/harga/paket-internet/indosat-mini-kuota-bulanan?page=1",
        "https://isipulsa.web.id/harga/paket-internet/indosat-mini-kuota-bulanan?page=2",
    ],

    "Three": [
        "https://isipulsa.web.id/harga/paket-internet/three-happy?page=1",
        "https://isipulsa.web.id/harga/paket-internet/three-happy?page=2",
        "https://isipulsa.web.id/harga/paket-internet/three-happy?page=3",
        "https://isipulsa.web.id/harga/paket-internet/three-happy?page=4",
        "https://isipulsa.web.id/harga/paket-internet/three-data-bulanan?page=1",
        "https://isipulsa.web.id/harga/paket-internet/three-data-bulanan?page=2",
        "https://isipulsa.web.id/harga/paket-internet/three-happy-spesial",
    ],

    "Telkomsel": [
        "https://isipulsa.web.id/harga/paket-internet/telkomsel-kuota-mini?page=1",
        "https://isipulsa.web.id/harga/paket-internet/telkomsel-kuota-mini?page=2",
        "https://isipulsa.web.id/harga/paket-internet/telkomsel-kuota-mini?page=3",
        "https://isipulsa.web.id/harga/paket-internet/telkomsel-kuota-mini?page=4",
        "https://isipulsa.web.id/harga/paket-internet/telkomsel-tsel-flash?page=1",
        "https://isipulsa.web.id/harga/paket-internet/telkomsel-tsel-flash?page=2",
        "https://isipulsa.web.id/harga/paket-internet/telkomsel-tsel-flash?page=3",
    ],

    "Axis": [
        "https://isipulsa.web.id/harga/paket-internet/axis-kuota-harian-nasional?page=1",
        "https://isipulsa.web.id/harga/paket-internet/axis-kuota-harian-nasional?page=2",
        "https://isipulsa.web.id/harga/paket-internet/axis-paket-harian",
        "https://isipulsa.web.id/harga/paket-kuota/axis-masa-aktif-1-bulan?page=1",
        "https://isipulsa.web.id/harga/paket-kuota/axis-masa-aktif-1-bulan?page=2",
    ],

    "XL": [
        "https://isipulsa.web.id/harga/paket-internet/xl-kuota-mini?page=1",
        "https://isipulsa.web.id/harga/paket-internet/xl-kuota-mini?page=2",
        "https://isipulsa.web.id/harga/paket-internet/xl-kuota-mini?page=3",
        "https://isipulsa.web.id/harga/paket-internet/xl-kuota-mini?page=4",
        "https://isipulsa.web.id/harga/paket-internet/xl-flex-max-mini?page=1",
        "https://isipulsa.web.id/harga/paket-internet/xl-flex-max-mini?page=2",
        "https://isipulsa.web.id/harga/paket-internet/xl-flex-max",
    ],

    "Smartfren": [
        "https://isipulsa.web.id/harga/paket-internet/smart?page=1",
        "https://isipulsa.web.id/harga/paket-internet/smart?page=2",
        "https://isipulsa.web.id/harga/paket-internet/smartfren-mini-kuota-233",
        "https://isipulsa.web.id/harga/paket-internet/smartfren-kuota-non-stop?page=1",
        "https://isipulsa.web.id/harga/paket-internet/smartfren-kuota-non-stop?page=2",
        "https://isipulsa.web.id/harga/paket-internet/smartfren-kuota-non-stop?page=3",
        "https://isipulsa.web.id/harga/paket-internet/smartfren-super-kuota",
    ],
}


def sell_price(supplier_price):
    supplier_price = int(supplier_price)
    return (
        (supplier_price + MARKUP + supplier_price * 7 // 1000 + 499)
        // 500
    ) * 500


def rekap_format_price(price):
    return f"Rp{int(price):,}".replace(",", ".")


def get_display_prices(products):
    """
    Meniru get_display_packages() aktif di bot.py.
    Hasil: {(provider, duration, display_package): harga_jual}
    """
    grouped = {}

    for item in products.values():
        if item.get("status") != "TERSEDIA":
            continue

        original = str(item.get("paket", ""))
        provider = item.get("provider", "")

        if "malam" in original.lower():
            continue

        duration_match = re.search(
            r"(\d+)\s*(?:Hari|Hr|H)\b",
            original,
            re.I
        )
        if not duration_match:
            continue

        duration = duration_match.group(1) + " Hari"

        main = re.sub(r"\([^)]*\)", " ", original)

        values = [
            float(x.replace(",", "."))
            for x in re.findall(
                r"(\d+(?:[.,]\d+)?)\s*GB",
                main,
                re.I
            )
        ]

        if not values:
            values = [
                float(x.replace(",", ".")) / 1000
                for x in re.findall(
                    r"(\d+(?:[.,]\d+)?)\s*MB",
                    main,
                    re.I
                )
            ]

        if not values:
            continue

        low = values[0]
        high = max(values)
        size = round(low, 3)

        try:
            supplier_price = int(
                re.sub(r"\D", "", str(item.get("harga", "")))
            )
        except ValueError:
            continue

        key = (provider, duration)
        cheapest = grouped.setdefault(key, {})
        current = cheapest.get(size)

        if current is None or supplier_price < current["supplier_price"]:
            cheapest[size] = {
                "display": f"{low:g} GB",
                "supplier_price": supplier_price,
                "high": high,
            }

    result = {}

    for (provider, duration), cheapest in grouped.items():
        items = []
        min_price = None

        # Sama seperti bot.py: kapasitas terbesar diperiksa lebih dulu
        for size in sorted(cheapest, reverse=True):
            item = cheapest[size]
            price = sell_price(item["supplier_price"])

            if min_price is not None and price >= min_price:
                continue

            items.append(item)
            min_price = (
                price if min_price is None
                else min(min_price, price)
            )

        for item in items:
            key = (provider, duration, item["display"])
            result[key] = sell_price(item["supplier_price"])

    return result


def send_rekap(message):
    token = os.getenv("BOT_TOKEN", "")

    if not token:
        print("[REKAP ERROR] BOT_TOKEN belum tersedia.")
        return False

    data = urllib.parse.urlencode({
        "chat_id": REKAP_CHANNEL,
        "text": message,
    }).encode()

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            response.read()
        return True
    except Exception as e:
        print(f"[REKAP ERROR] {e}")
        return False


def post_price_changes(old_products, new_products):
    old_prices = get_display_prices(old_products)
    new_prices = get_display_prices(new_products)

    naik = []
    turun = []

    for key in sorted(set(old_prices) & set(new_prices)):
        old_price = old_prices[key]
        new_price = new_prices[key]

        if old_price == new_price:
            continue

        provider, duration, package = key

        line = (
            f"• {provider} {package} {duration}\n"
            f"  {rekap_format_price(old_price)} → "
            f"{rekap_format_price(new_price)}"
        )

        if new_price > old_price:
            naik.append(line)
        else:
            turun.append(line)

    if not naik and not turun:
        return

    message = "📊 UPDATE HARGA KUOTA\n"

    if naik:
        message += "\n📈 HARGA NAIK\n\n"
        message += "\n\n".join(naik)

    if turun:
        message += "\n\n📉 HARGA TURUN\n\n"
        message += "\n\n".join(turun)

    # Pecah jika terlalu panjang untuk Telegram
    chunks = []
    current = ""

    for line in message.splitlines(True):
        if len(current) + len(line) > 3800:
            if current.strip():
                chunks.append(current.rstrip())
            current = line
        else:
            current += line

    if current.strip():
        chunks.append(current.rstrip())

    for chunk in chunks:
        send_rekap(chunk)

    print(
        f"[REKAP] {len(naik)} naik, "
        f"{len(turun)} turun"
    )

GAME_URLS = {
    "mlbb": [
        f"https://isipulsa.web.id/harga/mobile-legend/diamond-143?page={i}"
        for i in range(1, 8)
    ],
    "ff": [
        f"https://isipulsa.web.id/harga/free-fire/diamond?page={i}"
        for i in range(1, 5)
    ],
}


def clean(text):
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_page(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Android) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse_page(html, provider, url):
    products = {}

    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, re.S | re.I)

    for row in rows:
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S | re.I)

        if len(cells) < 4:
            continue

        kode = clean(cells[0])
        paket = clean(cells[1])

        price_match = re.search(
            r"Rp\s*([\d.,]+)",
            cells[2],
            re.I
        )

        if not price_match:
            continue

        harga = price_match.group(1)

        button = cells[3]

        if re.search(r'class="[^"]*\bdisabled\b[^"]*"', button, re.I):
            status = "KOSONG"
        elif re.search(r'aria-disabled\s*=\s*["\']true["\']', button, re.I):
            status = "KOSONG"
        elif re.search(r">\s*KOSONG\s*<", button, re.I):
            status = "KOSONG"
        else:
            status = "TERSEDIA"

        produk_match = re.search(
            r"Paket Internet\s*-\s*(.*?)</b>",
            cells[1],
            re.S | re.I
        )

        if produk_match:
            nama = clean(produk_match.group(1))
        else:
            produk_match = re.search(
                r"<b[^>]*>(.*?)</b>",
                cells[1],
                re.S | re.I
            )
            nama = clean(produk_match.group(1)) if produk_match else paket

        key = kode

        products[key] = {
            "provider": provider,
            "kode": kode,
            "paket": nama,
            "harga": harga,
            "status": status,
            "url": url,
        }

    return products


def parse_game_item(game, paket_raw):
    """Tentukan apakah satu baris produk game boleh masuk, dan ambil
    (kind, amount). Return None kalau harus dibuang."""
    low = paket_raw.lower()

    if "starlight member" in low or "level up pass" in low or "booyah pass" in low:
        return None

    if game == "mlbb":
        if "weekly diamond pass" in low:
            m = re.search(r"total\s+(\d+)\s*diamond", low)
            return ("weekly_pass", int(m.group(1))) if m else None
        m = re.search(r"-\s*(\d+)\s*diamonds?\s*$", low)
        return ("diamond", int(m.group(1))) if m else None

    if game == "ff":
        if "membership mingguan" in low:
            m = re.search(r"total\s+(\d+)", low)
            return ("membership_mingguan", int(m.group(1)) if m else 0)
        if "membership bulanan" in low:
            m = re.search(r"total\s+(\d+)", low)
            return ("membership_bulanan", int(m.group(1)) if m else 0)
        m = re.search(r"-\s*(\d+)\s*diamonds?\s*$", low)
        return ("diamond", int(m.group(1))) if m else None

    return None


def save_game_pricelist(items):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS game_pricelist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game TEXT NOT NULL,
            kode TEXT NOT NULL,
            kind TEXT NOT NULL,
            amount INTEGER NOT NULL,
            label TEXT,
            supplier_price INTEGER NOT NULL,
            available INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(game, kode)
        )
    """)

    for item in items.values():
        harga = int(re.sub(r"\D", "", str(item["harga"])))
        available = 1 if item["status"] == "TERSEDIA" else 0

        conn.execute("""
            INSERT INTO game_pricelist
            (game, kode, kind, amount, label, supplier_price, available, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(game, kode) DO UPDATE SET
                kind=excluded.kind,
                amount=excluded.amount,
                label=excluded.label,
                supplier_price=excluded.supplier_price,
                available=excluded.available,
                updated_at=excluded.updated_at
        """, (
            item["game"], item["kode"], item["kind"], item["amount"], item["label"],
            harga, available, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    cutoff = (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE game_pricelist SET available=0 WHERE available=1 AND updated_at < ?",
        (cutoff,)
    )

    conn.commit()
    conn.close()


def scan_games():
    all_items = {}
    errors = []

    for game, urls in GAME_URLS.items():
        for url in urls:
            try:
                html = get_page(url)
                rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, re.S | re.I)
                count = 0

                for row in rows:
                    cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S | re.I)
                    if len(cells) < 4:
                        continue

                    kode = clean(cells[0])
                    paket_raw = clean(cells[1])
                    price_match = re.search(r"Rp\s*([\d.,]+)", cells[2], re.I)
                    if not price_match:
                        continue
                    harga = price_match.group(1)

                    button = cells[3]
                    if (re.search(r'class="[^"]*\bdisabled\b[^"]*"', button, re.I)
                            or re.search(r'aria-disabled\s*=\s*["\']true["\']', button, re.I)
                            or re.search(r">\s*KOSONG\s*<", button, re.I)):
                        status = "KOSONG"
                    else:
                        status = "TERSEDIA"

                    parsed = parse_game_item(game, paket_raw)
                    if not parsed:
                        continue
                    kind, amount = parsed
                    count += 1

                    all_items[(game, kode)] = {
                        "game": game, "kode": kode, "kind": kind, "amount": amount,
                        "label": paket_raw, "harga": harga, "status": status,
                    }

                print(f"[OK-GAME] {game} | {count} produk relevan | {url}")

            except Exception as e:
                print(f"[ERROR-GAME] {url} -> {e}")
                errors.append(f"{game}: {url}\n{e}")

    save_game_pricelist(all_items)
    return all_items, errors


def load_snapshot():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_snapshot(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def telegram(message):
    return

def format_price(price):
    return "Rp " + price


def compare(old, new):
    changes = []

    old_keys = set(old)
    new_keys = set(new)

    # Produk baru
    for key in sorted(new_keys - old_keys):
        p = new[key]

        changes.append(
            f"🆕 PRODUK BARU\n"
            f"{p['provider']} — {p['paket']}\n"
            f"{p['kode']} | {format_price(p['harga'])} | {p['status']}"
        )

    # Produk hilang
    for key in sorted(old_keys - new_keys):
        p = old[key]

        changes.append(
            f"⚠️ PRODUK HILANG\n"
            f"{p['provider']} — {p['paket']}\n"
            f"{p['kode']} | sebelumnya {format_price(p['harga'])}"
        )

    # Perubahan
    for key in sorted(old_keys & new_keys):
        a = old[key]
        b = new[key]

        if a["harga"] != b["harga"]:
            changes.append(
                f"💰 HARGA BERUBAH\n"
                f"{b['provider']} — {b['paket']}\n"
                f"{b['kode']}\n"
                f"{format_price(a['harga'])} → {format_price(b['harga'])}"
            )

        if a["status"] != b["status"]:
            if b["status"] == "TERSEDIA":
                icon = "🟢"
            else:
                icon = "🔴"

            changes.append(
                f"{icon} STATUS BERUBAH\n"
                f"{b['provider']} — {b['paket']}\n"
                f"{b['kode']}\n"
                f"{a['status']} → {b['status']}\n"
                f"Harga: {format_price(b['harga'])}"
            )

    return changes

DB_FILE = "/storage/emulated/0/Download/orders.db"

def save_pricelist(products):
    conn = sqlite3.connect(DB_FILE)

    for item in products.values():
        nama = item["paket"]

        durasi_match = re.search(
            r"(\d+)\s*(?:Hari|Hr|H)\b",
            nama,
            re.I
        )

        if not durasi_match:
            continue

        duration = durasi_match.group(1) + " Hari"

        harga = int(re.sub(r"\D", "", str(item["harga"])))
        available = 1 if item["status"] == "TERSEDIA" else 0

        conn.execute("""
            INSERT INTO pricelist
            (provider, duration, package, supplier_code,
             supplier_price, available, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, duration, package)
            DO UPDATE SET
                supplier_code=excluded.supplier_code,
                supplier_price=excluded.supplier_price,
                available=excluded.available,
                updated_at=excluded.updated_at
        """, (
            item["provider"],
            duration,
            nama,
            item["kode"],
            harga,
            available,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    # retire: produk yang >30 menit tidak muncul lagi di link manapun
    # (mis. linknya sudah dihapus) disembunyikan dari bot
    cutoff = (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE pricelist SET available=0 WHERE available=1 AND updated_at < ?",
        (cutoff,)
    )

    conn.commit()
    conn.close()

def scan():
    all_products = {}
    errors = []

    for provider, urls in URLS.items():
        for url in urls:
            try:
                html = get_page(url)
                products = parse_page(html, provider, url)

                print(
                    f"[OK] {provider} | "
                    f"{len(products)} produk | {url}"
                )

                all_products.update(products)

            except Exception as e:
                print(f"[ERROR] {url} -> {e}")
                errors.append(f"{provider}: {url}\n{e}")


    save_pricelist(all_products)
    return all_products, errors


def main():
    print("====================================")
    print(" ISIPULSA PRICE MONITOR")
    print(" Interval: 5 menit")
    print(f" URL: {sum(len(v) for v in URLS.values())} halaman")
    print("====================================")

    old = load_snapshot()

    first_run = not bool(old)

    while True:
        print("\nMemeriksa pricelist...")

        new, errors = scan()

        try:
            scan_games()
        except Exception as e:
            print(f"[ERROR-GAME-SCAN] {e}")

        if not new:
            print("Tidak ada data yang berhasil dibaca.")
            time.sleep(INTERVAL)
            continue

        if first_run:
            save_snapshot(new)

            telegram(
                "✅ MONITOR PRICELIST AKTIF\n\n"
                f"Berhasil membaca {len(new)} produk "
                f"dari {sum(len(v) for v in URLS.values())} halaman.\n\n"
                "Monitoring harga + ketersediaan setiap 5 menit."
            )

            first_run = False

        else:
            # Rekap harga jual yang benar-benar tampil di bot
            post_price_changes(old, new)

            changes = compare(old, new)

            if changes:
                message = "🔔 PERUBAHAN PRICELIST\n\n"

                # Telegram message limit ~4096 chars
                chunks = []
                current = message

                for change in changes:
                    block = change + "\n\n"

                    if len(current) + len(block) > 3800:
                        chunks.append(current)
                        current = block
                    else:
                        current += block

                if current.strip():
                    chunks.append(current)

                for chunk in chunks:
                    telegram(chunk)

                print(f"PERUBAHAN: {len(changes)}")
            else:
                print("Tidak ada perubahan.")

            if errors:
                telegram(
                    "⚠️ MONITOR WARNING\n\n"
                    "Beberapa halaman gagal dibaca:\n\n" +
                    "\n".join(errors[:10])
                )

        old = new
        save_snapshot(new)

        print("Tunggu 5 menit...")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()

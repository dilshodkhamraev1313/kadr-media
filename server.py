#!/usr/bin/env python3
# ============================================================
#  Kadr Media Dashboard — Backend (Python standart kutubxona)
#  Hech qanday o'rnatish shart emas. Ishga tushirish:
#      python3 server.py
#  Keyin brauzerda oching:  http://localhost:3000
# ============================================================

import json
import os
import sqlite3
import datetime
import threading
import urllib.request
import hashlib
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DB_PATH = os.path.join(BASE_DIR, "kadr-media.db")
PORT = int(os.environ.get("PORT", 3000))

# Internetda (Render) DATABASE_URL beriladi → Postgres (Neon) ishlatiladi.
# Mahalliy kompyuterda esa SQLite fayli ishlatiladi (hech narsa o'rnatish shart emas).
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
IS_PG = DATABASE_URL.startswith("postgres")

# Telegram bildirishnoma (ixtiyoriy) — Render env'da TELEGRAM_BOT_TOKEN va
# TELEGRAM_CHAT_ID o'rnatilsa ishlaydi. O'rnatilmasa, jim turadi.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# Toshkent vaqti — O'zbekiston UTC+5, yozgi vaqt yo'q.
UZ_TZ = datetime.timezone(datetime.timedelta(hours=5))

STAGES = ["ssenariy", "syomka", "montaj", "tasdiq", "joylash"]
STATUSES = ["kutilmoqda", "jarayonda", "tayyor"]
STAGE_LABEL = {
    "ssenariy": "Ssenariy", "syomka": "Syomka", "montaj": "Montaj",
    "tasdiq": "Tasdiq", "joylash": "Joylash",
}

# Video turlari. Rahbar montaj biriktirayotganda turini tanlaydi.
VIDEO_TYPES = {
    "reels":   "Reels",
    "podcast": "Podcast",
    "youtube": "YouTube video",
}
# Video darajalari va narxlari (so'm). Har daraja bitta turga tegishli.
# Qabul qilishda shu turga mos darajalardan biri tanlanadi — pul avtomatik hisoblanadi.
TIERS = {
    # Reels
    "oddiy":    {"label": "Oddiy Reels",     "price": 25000,  "type": "reels"},
    "standart": {"label": "Standart Reels",  "price": 35000,  "type": "reels"},
    "premium":  {"label": "Premium Reels",   "price": 50000,  "type": "reels"},
    # Podcast
    "podcast":  {"label": "Podcast",         "price": 200000, "type": "podcast"},
    # YouTube
    "yt_oddiy": {"label": "YouTube (oddiy)", "price": 25000,  "type": "youtube"},
    "yt_full":  {"label": "YouTube (to'liq)","price": 50000,  "type": "youtube"},
}

# Kadr Studio — syomka xonalari. To'lov har mijoz bilan alohida kelishilib,
# qo'lda kiritiladi (belgilangan soatlik narx yo'q).
STUDIO_ROOMS = {
    "white": {"label": "1-xona · White", "color": "#0A84FF"},
    "black": {"label": "2-xona · Black", "color": "#1C1C1E"},
}
# Kadr Studio: bron KIRITA oladiganlar (Dilshod + Gulmira). KO'RISH — barcha loyiha
# rahbarlari va CEO. Pul hisoboti faqat CEO'da.
STUDIO_EDIT_USERS = ("Dilshod Khamraev", "Gulmira")

# Syomka turlari va OPERATORGA to'lanadigan pul (mijoz to'lovidan ALOHIDA).
# Bu Kadr Studio bronlarida ham, Kadr Media loyiha syomkalarida ham ishlatiladi.
SHOOT_TYPES = {"reels": "Reels", "podcast": "Podcast", "youtube": "YouTube video", "vebinar": "Vebinar"}
OPERATOR_PAY = {"reels": 50000, "podcast": 100000, "youtube": 50000, "vebinar": 200000}
STUDIO_OPERATORS = ("Said", "Umid")

# Ssenaristlar va har tasdiqlangan ssenariy uchun haq (so'm).
# Ssenarist o'z kabinetidan tasdiqlangan ssenariyni kiritadi — pul avtomatik hisoblanadi.
SCENARIST_PAY = {"Xonzoda": 100000, "Umida": 50000}

# Kadr Studio xarajatlari uchun tayyor nomlar (+ "Boshqa" izoh bilan).
STUDIO_EXPENSE_NAMES = [
    "Studio ijarasi", "WiFi", "Kommunalka", "Kunlik tushlik", "Suv",
    "Shirinliklar", "Kofe", "Shakar", "Quruq Sut", "Salfetka",
]

# --- Maosh (payroll) konfiguratsiyasi ---
DEFAULT_USD_RATE = 12000  # 1$ = 12 000 so'm (sozlamadan o'zgartiriladi)
LEADERSHIP_USD_FULL = 50  # loyiha to'liq (deadline o'tmagan) bo'lsa
LEADERSHIP_USD_HALF = 25  # deadline o'tib ketgan bo'lsa
STUDIO_CLIENT_BONUS = 50000  # Gulmiraga studio mijozidan syomkaga kelgani uchun (har bron)

# Kunlik sarhisob yopish majburiyati shu 4 kishida.
DAILY_CLOSE_USERS = ("Said", "Gulmira", "Xonzoda", "Umida")
WORKDAYS_PER_MONTH = 25  # intizom bo'linadigan ish kunlari (yakshanba dam)
CLOSE_PENALTY_PER_DAY = 20000  # har yopilmagan ish kuni uchun jazo (hamma uchun bir xil)

# Kelish nazorati (intizom) — telegram kruzhok orqali. Telegram username → ism.
ATTENDANCE_USERS = ("Gulmira", "Said", "Xonzoda", "Umid", "Umida", "Sardor", "Shodiya")
TELEGRAM_ATTEND = {
    "baxt_mira": "Gulmira", "said_israilov": "Said", "pilotflight6": "Xonzoda",
    "kartal_ck": "Umid", "sardor0526": "Sardor", "mxmdjnva8": "Shodiya",
    "umiyanassu": "Umida",
}
ON_TIME_LIMIT = "10:15"      # shu vaqtgacha kelsa — o'z vaqtida
INTIZOM_PER_DAY = 20000      # har o'z vaqtida kelgan ish kuni uchun
INTIZOM_FULL = 500000        # to'liq intizom (25 kun × 20 000)

# Har xodim rahbarlik qiladigan loyihalar (nomi projects jadvalidagi bilan mos).
LEADERSHIP = {
    "Said": ["Namuna mebel", "Nova school", "Nodirbek Primqulov (arab tili)"],
    "Xonzoda": ["Amarkets (Bekzod Treding)", "Fidda kumush taqinchoqlar"],
    "Gulmira": ["Umida-targetolog", "Kadr studio"],
}

# Har xodim maoshi tarkibi:
#  som  — to'g'ridan-to'g'ri so'mda (fiksa, intizom)
#  usd  — dollarda (kursda so'mga aylanadi)
#  flags — dinamik qismlar: lead(rahbarlik), operator, scenarist, montaj, studio_bonus
SALARY = {
    "Dilshod Khamraev": {"title": "CEO", "usd": {"CEO maosh": 500}},
    "Gulmira": {"title": "Kadr Studio rahbari",
                "som": {"Fiksa": 2000000, "Intizom": 500000, "Operatsion boshqaruv": 500000},
                "lead": True, "close_link": "Operatsion boshqaruv"},
    "Said": {"title": "Operator + loyiha rahbari", "som": {"Fiksa": 2000000, "Intizom": 500000},
             "usd": {"Sifat nazorati": 100}, "lead": True, "operator": True,
             "close_link": "Sifat nazorati"},
    "Xonzoda": {"title": "Ssenarist + koordinator", "som": {"Fiksa": 2000000, "Intizom": 500000},
                "usd": {"Koordinatorlik": 100}, "lead": True, "scenarist": True,
                "close_link": "Koordinatorlik"},
    "Umida": {"title": "SMM + ssenarist yordamchi", "som": {"Intizom": 500000},
              "usd": {"Stories": 100, "SMM": 100}, "scenarist": True,
              "close_link": "Stories"},
    "Sardor": {"title": "Montajchi", "som": {"Fiksa": 500000, "Intizom": 500000}, "montaj": True},
    "Umid": {"title": "Montajchi + operator", "som": {"Fiksa": 500000, "Intizom": 500000},
             "montaj": True, "operator": True},
    "Shodiya": {"title": "Montajchi", "som": {"Fiksa": 500000, "Intizom": 500000}, "montaj": True},
}

# Montajyor lavozimlari (o'yin rank tizimi). Har lavozimga o'tish uchun
# RANK_STEP ta muvaffaqiyatli qabul qilingan video kerak.
RANK_STEP = 100
RANKS = [
    {"key": "junior",  "label": "Junior",  "icon": "🥉"},
    {"key": "pro",     "label": "Pro",     "icon": "🥈"},
    {"key": "elite",   "label": "Elite",   "icon": "🥇"},
    {"key": "master",  "label": "Master",  "icon": "💎"},
    {"key": "legenda", "label": "Legenda", "icon": "👑"},
    {"key": "titan",   "label": "Titan",   "icon": "🔱"},
]
# Lavozim + video turi bo'yicha montajyor haqi (so'm). Pul shu jadval bo'yicha
# avtomatik hisoblanadi — montajyor lavozimi qancha baland bo'lsa, haqi shuncha ko'p.
RANK_PRICES = {
    "junior":  {"reels": 25000, "podcast": 200000, "youtube": 25000},
    "pro":     {"reels": 35000, "podcast": 250000, "youtube": 35000},
    "elite":   {"reels": 50000, "podcast": 300000, "youtube": 50000},
    "master":  {"reels": 60000, "podcast": 350000, "youtube": 60000},
    "legenda": {"reels": 70000, "podcast": 400000, "youtube": 70000},
    "titan":   {"reels": 80000, "podcast": 450000, "youtube": 80000},
}


# Ba'zi montajyorlar yuqori lavozimdan boshlanadi — qabul soniga qo'shiladigan bonus.
# Oygul Pro lavozimidan boshlanib hisoblanadi (1 lavozim = RANK_STEP qabul).
EDITOR_RANK_BASE = {"Oygul": RANK_STEP}


def eff_count(name, accepted):
    """Lavozim hisobida ishlatiladigan samarali qabul soni (bazaviy bonus bilan)."""
    return int(accepted or 0) + EDITOR_RANK_BASE.get(name, 0)


# Montaj deadline (biriktirilgandan qabulgacha). Kechiksa: reels — pul yo'q, podcast/youtube — yarim.
DEADLINE_HOURS = {"reels": 24, "podcast": 48, "youtube": 48}


def _deadline_check(assigned_at, vtype, approved_at):
    """(kechikdimi, deadline_datetime) qaytaradi. Ikkalasi ham Toshkent vaqti (now_local formati)."""
    hours = DEADLINE_HOURS.get(vtype if vtype in DEADLINE_HOURS else "reels", 24)
    try:
        a = datetime.datetime.strptime((assigned_at or "")[:19], "%Y-%m-%d %H:%M:%S")
        p = datetime.datetime.strptime((approved_at or "")[:19], "%Y-%m-%d %H:%M:%S")
        deadline = a + datetime.timedelta(hours=hours)
        return (p > deadline), deadline
    except (ValueError, TypeError):
        return False, None


def rank_for_count(count):
    """Qabul qilingan video soniga qarab lavozim indeksi (0=Junior ... 5=Titan)."""
    return min(int(count) // RANK_STEP, len(RANKS) - 1)


def rank_info(count):
    """Lavozim + keyingi lavozimga progress ma'lumoti."""
    count = int(count or 0)
    idx = rank_for_count(count)
    rk = RANKS[idx]
    nxt = RANKS[idx + 1] if idx + 1 < len(RANKS) else None
    in_rank = count - idx * RANK_STEP          # joriy lavozimdagi qabul soni
    to_next = (RANK_STEP - (count % RANK_STEP)) if nxt else 0
    pct = 100 if not nxt else round(in_rank / RANK_STEP * 100)
    return {
        "rank_key": rk["key"], "rank_label": rk["label"], "rank_icon": rk["icon"],
        "rank_index": idx, "next_label": (nxt["label"] if nxt else None),
        "in_rank": in_rank, "to_next": to_next, "rank_pct": pct,
    }


def editor_pay(count, vtype):
    """Montajyor lavozimi (count bo'yicha) va video turiga qarab haq (so'm) + lavozim kaliti."""
    idx = rank_for_count(count)
    rk = RANKS[idx]["key"]
    vt = vtype if vtype in ("reels", "podcast", "youtube") else "reels"
    return RANK_PRICES[rk][vt], rk

# Mijoz bilan kelishilgan oylik video reja (har bir bosqich uchun shu son).
CLIENT_PLAN = {
    "Nova School": 40,
    "Zebo Rixsibayevna (Nova School asoschisi)": 15,
    "Nodirbek Primqulov Arab tili": 15,
    "Rohatoy Mamolog": 15,
    "Aziza Psixolog": 50,
    "Namuna Mebel": 30,
    "Mohira Valiyeva Kosmetolog": 15,
    'Bekzod Trading "AMARKETS"': 10,
}
DONE_COLS = ["done_ssenariy", "done_syomka", "done_montaj", "done_tasdiq", "done_joylash"]

# Rollar: ceo, coordinator, lead (rahbar), editor (montajchi), client (mijoz)
# Tasdiqlay oladiganlar (video/ssenariy):
APPROVER_ROLES = ("ceo", "coordinator", "lead")
# Hamma narsani ko'radiganlar:
ADMIN_ROLES = ("ceo", "coordinator")

# Jamoa va kirish ma'lumotlari. (name, username, password, role, title, color, client_name)
TEAM = [
    ("Dilshod Khamraev", "dilshod", "ceo2026",  "ceo",         "CEO",                    "#0A84FF", None),
    ("Xonzoda",          "xonzoda", "xonz2026", "coordinator", "Loyiha koordinatori",    "#BF5AF2", None),
    ("Said",             "said",    "said2026", "lead",        "Loyiha rahbari · Syomka", "#FF9F0A", None),
    ("Gulmira",          "gulmira", "gulm2026", "lead",        "Loyiha rahbari",          "#30D158", None),
    ("Robiya",           "robiya",  "robi2026", "lead",        "Loyiha rahbari",          "#FF375F", None),
    # Montajchilar
    ("Sardor",           "sardor",  "sard2026", "editor",      "Montajchi",               "#64D2FF", None),
    ("Talg'at",          "talgat",  "talg2026", "editor",      "Montajchi",               "#FFD60A", None),
    ("Oygul",            "oygul",   "oygu2026", "editor",      "Montajchi",               "#FF6482", None),
    ("Umid",             "umid",    "umid2026", "editor",      "Montajchi",               "#5E5CE6", None),
    ("Umida",            "umida",   "umid2027", "editor",      "Montajchi · Ssenarist",   "#AC8E68", None),
    ("Shodiya",          "shodiya", "shod2026", "editor",      "Montajchi",               "#32D74B", None),
    # SMM menejer (faqat joylash)
    ("Aisha",            "aisha",   "aisha2026","smm",         "SMM menejer · Joylash",   "#FF2D55", None),
    # Mijozlar (faqat o'z loyihasini ko'radi)
    ("Rohatoy Mamolog",                          "rohatoy",  "mijoz2601", "client", "Mijoz", "#0A84FF", "Rohatoy Mamolog"),
    ("Nova School",                              "novaschool","mijoz2602", "client", "Mijoz", "#30D158", "Nova School"),
    ("Aziza Psixolog",                           "aziza",    "mijoz2603", "client", "Mijoz", "#BF5AF2", "Aziza Psixolog"),
    ("Namuna Mebel",                             "namuna",   "mijoz2604", "client", "Mijoz", "#FF9F0A", "Namuna Mebel"),
    ('Bekzod Trading "AMARKETS"',                "bekzod",   "mijoz2605", "client", "Mijoz", "#64D2FF", 'Bekzod Trading "AMARKETS"'),
    ("Mohira Valiyeva Kosmetolog",               "mohira",   "mijoz2606", "client", "Mijoz", "#FF375F", "Mohira Valiyeva Kosmetolog"),
    ("Nodirbek Primqulov Arab tili",             "nodirbek", "mijoz2607", "client", "Mijoz", "#FFD60A", "Nodirbek Primqulov Arab tili"),
    ("Zebo Rixsibayevna (Nova School asoschisi)","zebo",     "mijoz2608", "client", "Mijoz", "#5E5CE6", "Zebo Rixsibayevna (Nova School asoschisi)"),
]


def make_salt():
    return secrets.token_hex(8)


def hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", (password or "").encode(), salt.encode(), 100000).hex()


def uz_now():
    """Toshkent vaqti bilan hozirgi sana-vaqt."""
    return datetime.datetime.now(UZ_TZ)


def uz_today():
    """Toshkent vaqti bilan bugungi sana."""
    return uz_now().date()


def send_telegram(text):
    """Telegram'ga xabar yuboradi (fon oqimida, xatolar yutiladi)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    def _send():
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = json.dumps({
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }).encode("utf-8")
            req = urllib.request.Request(
                url, data=payload, headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass  # bildirishnoma muvaffaqiyatsiz bo'lsa ham ilova ishlashda davom etadi

    threading.Thread(target=_send, daemon=True).start()


# ------------------------------------------------------------
#  Database — bitta interfeys, ikki dvigatel (SQLite / Postgres)
# ------------------------------------------------------------
class Conn:
    """Yagona ulanish o'rami: '?' belgilarini Postgres uchun '%s' ga aylantiradi."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        if IS_PG:
            sql = sql.replace("?", "%s")
        return self.raw.execute(sql, params)

    def executemany(self, sql, seq):
        if IS_PG:
            sql = sql.replace("?", "%s")
        cur = self.raw.cursor()
        cur.executemany(sql, seq)
        return cur

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()


def get_db():
    if IS_PG:
        import psycopg
        from psycopg.rows import dict_row
        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    else:
        raw = sqlite3.connect(DB_PATH)
        raw.row_factory = sqlite3.Row
    return Conn(raw)


def add_column_if_missing(conn, table, col, coltype):
    """users jadvaliga yangi ustun qo'shadi (agar yo'q bo'lsa). SQLite/Postgres."""
    if IS_PG:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {coltype}")
    else:
        cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")


def ensure_accounts(conn):
    """Jamoa va mijoz akkauntlarini ta'minlaydi (idempotent — qayta-qayta xavfsiz).
    Mavjud foydalanuvchi (ism bo'yicha) bo'lsa — login ma'lumotini qo'shadi,
    bo'lmasa — yangi yaratadi. Parol faqat bo'sh bo'lsa o'rnatiladi."""
    for name, username, password, role, title, color, client_name in TEAM:
        existing = conn.execute(
            "SELECT id, password_hash FROM users WHERE username=? OR name=?",
            (username, name),
        ).fetchone()
        salt = make_salt()
        ph = hash_pw(password, salt)
        if existing:
            # Parol allaqachon o'rnatilgan bo'lsa — tegmaymiz (foydalanuvchi o'zgartirgan bo'lishi mumkin)
            if existing["password_hash"]:
                conn.execute(
                    "UPDATE users SET username=?, role=?, title=?, color=?, client_name=? WHERE id=?",
                    (username, role, title, color, client_name, existing["id"]),
                )
            else:
                conn.execute(
                    "UPDATE users SET username=?, salt=?, password_hash=?, role=?, title=?, color=?, client_name=? WHERE id=?",
                    (username, salt, ph, role, title, color, client_name, existing["id"]),
                )
        else:
            conn.execute(
                "INSERT INTO users (name, username, salt, password_hash, role, title, color, client_name) VALUES (?,?,?,?,?,?,?,?)",
                (name, username, salt, ph, role, title, color, client_name),
            )
    conn.commit()


def init_db():
    conn = get_db()
    pk = "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    ts = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP" if IS_PG else "TEXT DEFAULT CURRENT_TIMESTAMP"

    conn.execute(f"""CREATE TABLE IF NOT EXISTS users (
        id {pk}, name TEXT NOT NULL, role TEXT NOT NULL, title TEXT, color TEXT)""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS clients (
        id {pk}, name TEXT NOT NULL)""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS projects (
        id {pk}, name TEXT NOT NULL, client TEXT, responsible TEXT,
        ssenariy TEXT DEFAULT 'kutilmoqda', syomka TEXT DEFAULT 'kutilmoqda',
        montaj TEXT DEFAULT 'kutilmoqda', tasdiq TEXT DEFAULT 'kutilmoqda',
        joylash TEXT DEFAULT 'kutilmoqda',
        deadline TEXT, muammo TEXT DEFAULT '', izoh TEXT DEFAULT '',
        created_at {ts}, updated_at {ts})""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS activity (
        id {pk}, project_id INTEGER, project_name TEXT, stage TEXT, status TEXT,
        actor TEXT, created_at TEXT)""")

    # --- Yangi modul jadvallari (mavjud ma'lumotga tegmaydi) ---
    conn.execute(f"""CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY, user_id INTEGER, created_at TEXT)""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS scripts (
        id {pk}, project_id INTEGER, project TEXT, client TEXT DEFAULT '', author TEXT, title TEXT,
        status TEXT DEFAULT 'yozilmoqda', hook TEXT DEFAULT '', story TEXT DEFAULT '',
        cta TEXT DEFAULT '', link TEXT DEFAULT '',
        approved_by TEXT DEFAULT '', approved_at TEXT DEFAULT '',
        expert_ok INTEGER DEFAULT 0, expert_note TEXT DEFAULT '', expert_at TEXT DEFAULT '',
        created_at {ts}, updated_at {ts})""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS script_versions (
        id {pk}, script_id INTEGER, version INTEGER, hook TEXT, story TEXT, cta TEXT,
        edited_by TEXT, created_at TEXT)""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS videos (
        id {pk}, project_id INTEGER, project TEXT, client TEXT DEFAULT '', script_id INTEGER,
        title TEXT, editor TEXT, vdate TEXT, drive_link TEXT DEFAULT '', note TEXT DEFAULT '',
        tier TEXT DEFAULT '', amount INTEGER DEFAULT 0, status TEXT DEFAULT 'topshirildi',
        approved_by TEXT DEFAULT '', approved_at TEXT DEFAULT '',
        instagram_link TEXT DEFAULT '', created_at {ts})""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS payments (
        id {pk}, editor TEXT, amount INTEGER, paid_by TEXT, note TEXT DEFAULT '',
        pdate TEXT, created_at {ts})""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS audit (
        id {pk}, actor TEXT, action TEXT, detail TEXT DEFAULT '', created_at TEXT)""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS studio_bookings (
        id {pk}, room TEXT, client_name TEXT, phone TEXT DEFAULT '',
        bdate TEXT, start_time TEXT, end_time TEXT, hours REAL DEFAULT 0,
        amount INTEGER DEFAULT 0, paid INTEGER DEFAULT 0, note TEXT DEFAULT '',
        created_by TEXT, created_at {ts})""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS shoots (
        id {pk}, project_id INTEGER, project TEXT, shoot_type TEXT DEFAULT 'reels',
        operator TEXT DEFAULT '', operator_pay INTEGER DEFAULT 0, sdate TEXT,
        status TEXT DEFAULT 'active', note TEXT DEFAULT '', created_by TEXT, created_at {ts})""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS scenarist_scripts (
        id {pk}, author TEXT, project TEXT DEFAULT '', client TEXT DEFAULT '', title TEXT,
        amount INTEGER DEFAULT 0, status TEXT DEFAULT 'active', sdate TEXT,
        note TEXT DEFAULT '', created_at {ts})""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS studio_expenses (
        id {pk}, name TEXT, amount INTEGER DEFAULT 0, edate TEXT,
        note TEXT DEFAULT '', created_by TEXT, created_at {ts})""")
    conn.execute("""CREATE TABLE IF NOT EXISTS settings (
        skey TEXT PRIMARY KEY, svalue TEXT)""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS daily_close (
        id {pk}, person TEXT, cdate TEXT, closed_at TEXT)""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS charity_ledger (
        id {pk}, kind TEXT, amount INTEGER DEFAULT 0, note TEXT DEFAULT '',
        cdate TEXT, created_by TEXT, created_at {ts})""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS attendance (
        id {pk}, person TEXT, adate TEXT, checkin_time TEXT,
        on_time INTEGER DEFAULT 0, source TEXT DEFAULT 'bot', created_at {ts})""")

    # users jadvaliga login ustunlarini qo'shish (idempotent)
    add_column_if_missing(conn, "users", "username", "TEXT")
    add_column_if_missing(conn, "users", "salt", "TEXT")
    add_column_if_missing(conn, "users", "password_hash", "TEXT")
    add_column_if_missing(conn, "users", "client_name", "TEXT")
    add_column_if_missing(conn, "users", "avatar", "TEXT")
    # projects: oylik reja + har bosqich bo'yicha bajarilgan sanoq
    add_column_if_missing(conn, "projects", "plan", "INTEGER DEFAULT 0")
    add_column_if_missing(conn, "projects", "monthly_fee", "INTEGER DEFAULT 0")
    for col in DONE_COLS:
        add_column_if_missing(conn, "projects", col, "INTEGER DEFAULT 0")
    # videos: ish jarayoni ustunlari
    for col in ("assigned_by", "qc_by", "qc_at", "posted_by", "posted_at", "montaj_at"):
        add_column_if_missing(conn, "videos", col, "TEXT")
    # videos: video turi (reels/podcast/youtube)
    add_column_if_missing(conn, "videos", "vtype", "TEXT DEFAULT 'reels'")
    # videos: deadline uchun biriktirilgan vaqt (Toshkent) va kechikish belgisi
    add_column_if_missing(conn, "videos", "assigned_at", "TEXT")
    add_column_if_missing(conn, "videos", "is_late", "INTEGER DEFAULT 0")
    # studio_bookings: operator, syomka turi, operator puli, avans, holat
    add_column_if_missing(conn, "studio_bookings", "operator", "TEXT DEFAULT ''")
    add_column_if_missing(conn, "studio_bookings", "shoot_type", "TEXT DEFAULT 'reels'")
    add_column_if_missing(conn, "studio_bookings", "operator_pay", "INTEGER DEFAULT 0")
    add_column_if_missing(conn, "studio_bookings", "paid_amount", "INTEGER DEFAULT 0")
    add_column_if_missing(conn, "studio_bookings", "status", "TEXT DEFAULT 'active'")
    conn.commit()

    # Seed (faqat bo'sh bo'lsa)
    if conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 0:
        users = [
            ("Dilshod Khamraev", "ceo", "CEO", "#0A84FF"),
            ("Xonzoda", "coordinator", "Loyiha koordinatori", "#BF5AF2"),
            ("Said", "lead", "Loyiha rahbari · Syomka bo'limi", "#FF9F0A"),
            ("Gulmira", "lead", "Loyiha rahbari", "#30D158"),
            ("Robiya", "lead", "Loyiha rahbari", "#FF375F"),
        ]
        conn.executemany("INSERT INTO users (name,role,title,color) VALUES (?,?,?,?)", users)

        clients = [
            "Rohatoy Mamolog", "Nova School", "Aziza Psixolog", "Namuna Mebel",
            'Bekzod Trading "AMARKETS"', "Mohira Valiyeva Kosmetolog",
            "Nodirbek Primqulov Arab tili", "Zebo Rixsibayevna (Nova School asoschisi)",
        ]
        conn.executemany("INSERT INTO clients (name) VALUES (?)", [(x,) for x in clients])

        today = uz_today()
        def d(off):
            return (today + datetime.timedelta(days=off)).isoformat()

        sample = [
            ("Reels: Ko'krak sog'lig'i", "Rohatoy Mamolog", "Gulmira",
             "tayyor", "tayyor", "jarayonda", "kutilmoqda", "kutilmoqda", d(2), "", "Mijoz ko'proq sub'titr so'radi"),
            ("Tanishuv video", "Nova School", "Robiya",
             "tayyor", "tayyor", "tayyor", "tayyor", "jarayonda", d(1), "", "Obloshka tayyor, caption yozilyapti"),
            ("Stress haqida 3 ta reels", "Aziza Psixolog", "Said",
             "tayyor", "jarayonda", "kutilmoqda", "kutilmoqda", "kutilmoqda", d(-1),
             "Syomka kuni mijoz kelmadi, qayta belgilanyapti", ""),
            ("Katalog syomka", "Namuna Mebel", "Xonzoda",
             "tayyor", "tayyor", "jarayonda", "kutilmoqda", "kutilmoqda", d(4), "", "Divan kolleksiyasi"),
            ('AMARKETS treyding reels', 'Bekzod Trading "AMARKETS"', "Said",
             "jarayonda", "kutilmoqda", "kutilmoqda", "kutilmoqda", "kutilmoqda", d(5), "", "Ssenariy 2-variant kutilyapti"),
            ("Yuz parvarishi", "Mohira Valiyeva Kosmetolog", "Gulmira",
             "tayyor", "tayyor", "tayyor", "jarayonda", "kutilmoqda", d(0), "", "Mijoz tasdig'i kutilmoqda"),
            ("Arab tili darslik reels", "Nodirbek Primqulov Arab tili", "Robiya",
             "jarayonda", "kutilmoqda", "kutilmoqda", "kutilmoqda", "kutilmoqda", d(7), "", ""),
            ("Asoschi intervyu", "Zebo Rixsibayevna (Nova School asoschisi)", "Xonzoda",
             "tayyor", "kutilmoqda", "kutilmoqda", "kutilmoqda", "kutilmoqda", d(-2),
             "Deadline o'tib ketdi, syomka sanasi kelishilmagan", "Asoschi bilan"),
        ]
        conn.executemany(
            """INSERT INTO projects
               (name,client,responsible,ssenariy,syomka,montaj,tasdiq,joylash,deadline,muammo,izoh)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            sample,
        )
        conn.commit()

    ensure_accounts(conn)
    ensure_project_plans(conn)
    conn.close()


def ensure_project_plans(conn):
    """Mavjud loyihalarga mijoz bo'yicha oylik rejani o'rnatadi.
    Faqat reja hali kiritilmagan (0/NULL) loyihalarga — qo'lda o'zgartirilganiga tegmaydi."""
    for client, plan in CLIENT_PLAN.items():
        conn.execute(
            "UPDATE projects SET plan=? WHERE client=? AND (plan IS NULL OR plan=0)",
            (plan, client),
        )
    conn.commit()


# ------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------
def decorate(row):
    p = dict(row)
    done = sum(1 for s in STAGES if p.get(s) == "tayyor")
    p["doneCount"] = done
    p["progress"] = round(done / len(STAGES) * 100)
    p["fullyDone"] = done == len(STAGES)

    days_left = None
    overdue = False
    if p.get("deadline"):
        try:
            dl = datetime.date.fromisoformat(p["deadline"])
            days_left = (dl - uz_today()).days
            overdue = (not p["fullyDone"]) and days_left < 0
        except ValueError:
            pass
    p["daysLeft"] = days_left
    p["overdue"] = overdue

    has_problem = bool((p.get("muammo") or "").strip())
    p["atRisk"] = (not p["fullyDone"]) and (
        (days_left is not None and days_left <= 2 and p["progress"] < 60) or has_problem
    )

    # Oylik reja progressi (har bosqich uchun plan dona)
    plan = p.get("plan") or 0
    done_total = sum(p.get(c) or 0 for c in DONE_COLS)
    p["planTotal"] = plan * len(STAGES)
    p["planDone"] = done_total
    p["planPct"] = round(done_total / (plan * len(STAGES)) * 100) if plan else 0
    return p


def now_local():
    return uz_now().strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------
#  API logic
# ------------------------------------------------------------
def api_users():
    conn = get_db()
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def api_clients():
    conn = get_db()
    rows = conn.execute("SELECT * FROM clients ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def api_projects():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM projects ORDER BY deadline IS NULL, deadline ASC"
    ).fetchall()
    conn.close()
    return [decorate(r) for r in rows]


def api_get_project(pid):
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    conn.close()
    return decorate(row) if row else None


def api_create_project(b):
    def st(v):
        return v if v in STATUSES else "kutilmoqda"

    def iv(k):
        try:
            return int(b.get(k) or 0)
        except (ValueError, TypeError):
            return 0
    conn = get_db()
    sql = """INSERT INTO projects
           (name,client,responsible,ssenariy,syomka,montaj,tasdiq,joylash,deadline,muammo,izoh,
            plan,monthly_fee,done_ssenariy,done_syomka,done_montaj,done_tasdiq,done_joylash)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    params = (
        b.get("name") or "Nomsiz loyiha", b.get("client") or "",
        b.get("responsible") or "", st(b.get("ssenariy")), st(b.get("syomka")),
        st(b.get("montaj")), st(b.get("tasdiq")), st(b.get("joylash")),
        b.get("deadline") or None, b.get("muammo") or "", b.get("izoh") or "",
        iv("plan"), iv("monthly_fee"), iv("done_ssenariy"), iv("done_syomka"), iv("done_montaj"), iv("done_tasdiq"), iv("done_joylash"),
    )
    if IS_PG:
        pid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        pid = conn.execute(sql, params).lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    conn.close()

    p = decorate(row)
    send_telegram(
        f"🆕 <b>Yangi loyiha qo'shildi</b>\n"
        f"📁 {p['name']}\n"
        f"👤 Javobgar: {p['responsible'] or '—'}\n"
        f"🏢 Mijoz: {p['client'] or '—'}\n"
        f"📅 Deadline: {p['deadline'] or '—'}"
    )
    return p


def api_update_project(pid, b):
    conn = get_db()
    existing = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not existing:
        conn.close()
        return None
    existing = dict(existing)
    actor = b.get("_actor") or "Tizim"

    def pick(key):
        v = b.get(key)
        return v if v in STATUSES else existing[key]

    def iv(key):
        if key not in b or b.get(key) is None or b.get(key) == "":
            return existing.get(key) or 0
        try:
            return int(b.get(key))
        except (ValueError, TypeError):
            return existing.get(key) or 0

    merged = {
        "name": b.get("name", existing["name"]),
        "client": b.get("client", existing["client"]),
        "responsible": b.get("responsible", existing["responsible"]),
        "ssenariy": pick("ssenariy"), "syomka": pick("syomka"),
        "montaj": pick("montaj"), "tasdiq": pick("tasdiq"), "joylash": pick("joylash"),
        "deadline": b["deadline"] if "deadline" in b else existing["deadline"],
        "muammo": b.get("muammo", existing["muammo"]),
        "izoh": b.get("izoh", existing["izoh"]),
        "plan": iv("plan"),
        "monthly_fee": iv("monthly_fee"),
        "done_ssenariy": iv("done_ssenariy"), "done_syomka": iv("done_syomka"),
        "done_montaj": iv("done_montaj"), "done_tasdiq": iv("done_tasdiq"),
        "done_joylash": iv("done_joylash"),
    }

    # Faollik jurnali — qaysi bosqich "tayyor" bo'ldi
    completed_stages = []
    for s in STAGES:
        if merged[s] != existing[s] and merged[s] == "tayyor":
            completed_stages.append(s)
            conn.execute(
                "INSERT INTO activity (project_id,project_name,stage,status,actor,created_at) VALUES (?,?,?,?,?,?)",
                (pid, merged["name"], s, "tayyor", actor, now_local()),
            )

    # Yangi muammo qo'shildimi?
    new_problem = (
        (merged["muammo"] or "").strip()
        and (merged["muammo"] or "").strip() != (existing["muammo"] or "").strip()
    )

    conn.execute(
        """UPDATE projects SET name=?,client=?,responsible=?,ssenariy=?,syomka=?,montaj=?,
           tasdiq=?,joylash=?,deadline=?,muammo=?,izoh=?,
           plan=?,monthly_fee=?,done_ssenariy=?,done_syomka=?,done_montaj=?,done_tasdiq=?,done_joylash=?,
           updated_at=CURRENT_TIMESTAMP WHERE id=?""",
        (
            merged["name"], merged["client"], merged["responsible"], merged["ssenariy"],
            merged["syomka"], merged["montaj"], merged["tasdiq"], merged["joylash"],
            merged["deadline"], merged["muammo"], merged["izoh"],
            merged["plan"], merged["monthly_fee"], merged["done_ssenariy"], merged["done_syomka"],
            merged["done_montaj"], merged["done_tasdiq"], merged["done_joylash"], pid,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    conn.close()

    p = decorate(row)
    # Telegram bildirishnomalar
    if p["fullyDone"] and not all(existing[s] == "tayyor" for s in STAGES):
        send_telegram(f"🎉 <b>Loyiha to'liq yakunlandi!</b>\n📁 {p['name']} — {p['responsible'] or '—'}")
    else:
        for s in completed_stages:
            send_telegram(
                f"✅ <b>{STAGE_LABEL[s]} tayyor</b>\n"
                f"📁 {p['name']}\n👤 {actor} · {p['progress']}% bajarildi"
            )
    if new_problem:
        send_telegram(
            f"⚠️ <b>Muammo qayd etildi</b>\n📁 {p['name']} ({p['responsible'] or '—'})\n💬 {merged['muammo']}"
        )
    return p


def api_delete_project(pid):
    conn = get_db()
    conn.execute("DELETE FROM projects WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return {"ok": True}


def lead_project_names(name):
    """Rahbar javobgar bo'lgan loyiha nomlari to'plami."""
    conn = get_db()
    rows = conn.execute("SELECT name FROM projects WHERE responsible=?", (name,)).fetchall()
    conn.close()
    return set(r["name"] for r in rows)


def visible_projects(user, show_all=False):
    """Foydalanuvchi rolига qarab ko'rinadigan loyihalar."""
    rows = api_projects()
    if not user:
        return rows
    role = user["role"]
    if role == "client":
        return [p for p in rows if p.get("client") == user.get("client_name")]
    if role == "lead" and not show_all:
        return [p for p in rows if p.get("responsible") == user["name"]]
    return rows


def api_stats(user=None, show_all=False):
    rows = visible_projects(user, show_all)
    total = len(rows)
    completed = sum(1 for p in rows if p["fullyDone"])
    overdue = sum(1 for p in rows if p["overdue"])
    at_risk = sum(1 for p in rows if p["atRisk"])

    conn = get_db()
    today = uz_today().isoformat()
    if user and user["role"] == "lead" and not show_all:
        names = set(p["name"] for p in rows)
        acts = conn.execute(
            "SELECT project_name FROM activity WHERE substr(created_at,1,10)=?", (today,)
        ).fetchall()
        today_tasks = sum(1 for a in acts if a["project_name"] in names)
    else:
        today_tasks = conn.execute(
            "SELECT COUNT(*) AS n FROM activity WHERE substr(created_at,1,10)=?", (today,)
        ).fetchone()["n"]
    leads = conn.execute(
        "SELECT name FROM users WHERE role IN ('lead','coordinator')"
    ).fetchall()
    recent = conn.execute(
        "SELECT * FROM activity ORDER BY id DESC LIMIT 15"
    ).fetchall()

    # Joylash statistikasi (rahbar o'z loyihalari bo'yicha, admin hammasi)
    if user and user["role"] == "lead" and not show_all:
        proj_names = tuple(p["name"] for p in rows)
        if proj_names:
            ph = ",".join(["?"] * len(proj_names))
            ready_to_post = conn.execute(
                f"SELECT COUNT(*) AS n FROM videos WHERE status='qabul_qilindi' AND project IN ({ph})",
                proj_names,
            ).fetchone()["n"]
            posted_count = conn.execute(
                f"SELECT COUNT(*) AS n FROM videos WHERE status='joylandi' AND project IN ({ph})",
                proj_names,
            ).fetchone()["n"]
        else:
            ready_to_post = 0
            posted_count = 0
    else:
        ready_to_post = conn.execute(
            "SELECT COUNT(*) AS n FROM videos WHERE status='qabul_qilindi'"
        ).fetchone()["n"]
        posted_count = conn.execute(
            "SELECT COUNT(*) AS n FROM videos WHERE status='joylandi'"
        ).fetchone()["n"]

    conn.close()

    # Workload har doim BARCHA loyihalardan (faqat admin team view'da ishlatiladi)
    allrows = api_projects()

    workload = []
    for u in leads:
        mine = [p for p in allrows if p["responsible"] == u["name"]]
        workload.append({
            "name": u["name"], "total": len(mine),
            "active": sum(1 for p in mine if not p["fullyDone"]),
            "overdue": sum(1 for p in mine if p["overdue"]),
            "atRisk": sum(1 for p in mine if p["atRisk"]),
        })

    return {
        "total": total, "active": total - completed, "completed": completed,
        "overdue": overdue, "atRisk": at_risk, "todayTasks": today_tasks,
        "readyToPost": ready_to_post, "postedCount": posted_count,
        "workload": workload, "recent": [dict(r) for r in recent],
    }


def api_telegram_test():
    """Telegram ulanishini sinash uchun test xabari yuboradi."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"ok": False, "error": "Telegram sozlanmagan (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID yo'q)"}
    send_telegram("🤖 <b>Kadr Media Dashboard</b>\nTelegram bildirishnoma muvaffaqiyatli ulandi! ✅")
    return {"ok": True}


def api_telegram_digest():
    """Kechikkan va muddati yaqin loyihalar bo'yicha kunlik hisobot yuboradi.
    Buni bepul cron xizmati (masalan cron-job.org) har kuni chaqirishi mumkin."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"ok": False, "error": "Telegram sozlanmagan"}
    rows = api_projects()
    overdue = [p for p in rows if p["overdue"]]
    soon = [
        p for p in rows
        if not p["overdue"] and not p["fullyDone"]
        and p["daysLeft"] is not None and 0 <= p["daysLeft"] <= 2
    ]
    lines = [f"📊 <b>Kunlik hisobot — {uz_today().isoformat()}</b>"]
    if overdue:
        lines.append("\n⏱ <b>Kechikkan loyihalar:</b>")
        for p in overdue:
            lines.append(f"• {p['name']} — {p['responsible'] or '—'} ({abs(p['daysLeft'])} kun kechikdi)")
    if soon:
        lines.append("\n🔔 <b>Muddati yaqin (≤2 kun):</b>")
        for p in soon:
            when = "bugun" if p["daysLeft"] == 0 else f"{p['daysLeft']} kun qoldi"
            lines.append(f"• {p['name']} — {p['responsible'] or '—'} ({when})")
    if not overdue and not soon:
        lines.append("\n✅ Kechikkan yoki muddati yaqin loyiha yo'q. Zo'r!")
    send_telegram("\n".join(lines))
    return {"ok": True, "overdue": len(overdue), "soon": len(soon)}


# ============================================================
#  AUTH (login / parol)
# ============================================================
def public_user(u):
    if not u:
        return None
    d = dict(u)
    d.pop("salt", None)
    d.pop("password_hash", None)
    d["hasPassword"] = True
    return d


def user_from_token(token):
    if not token:
        return None
    conn = get_db()
    row = conn.execute(
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
        (token,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def api_login(b):
    username = (b.get("username") or "").strip().lower()
    password = b.get("password") or ""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE lower(username) = ?", (username,)).fetchone()
    if not row or not row["password_hash"] or hash_pw(password, row["salt"]) != row["password_hash"]:
        conn.close()
        return None
    token = secrets.token_hex(24)
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at) VALUES (?,?,?)",
        (token, row["id"], now_local()),
    )
    log_audit(conn, row["name"], "kirdi", "")
    conn.commit()
    conn.close()
    return {"token": token, "user": public_user(dict(row))}


def api_logout(token):
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return {"ok": True}


def api_change_password(user, b):
    old = b.get("old") or ""
    new = b.get("new") or ""
    if len(new) < 4:
        return {"ok": False, "error": "Yangi parol kamida 4 ta belgi bo'lsin"}
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    if hash_pw(old, row["salt"]) != row["password_hash"]:
        conn.close()
        return {"ok": False, "error": "Eski parol noto'g'ri"}
    salt = make_salt()
    conn.execute(
        "UPDATE users SET salt=?, password_hash=? WHERE id=?",
        (salt, hash_pw(new, salt), user["id"]),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


def api_set_avatar(user, b):
    """Foydalanuvchi o'z avatar rasmini yuklaydi (data URL, kichraytirilgan JPEG)."""
    avatar = b.get("avatar")
    if avatar is not None and avatar != "":
        if not isinstance(avatar, str) or not avatar.startswith("data:image"):
            return {"ok": False, "error": "Rasm formati noto'g'ri"}
        if len(avatar) > 400000:  # ~300KB rasm chegarasi
            return {"ok": False, "error": "Rasm juda katta (kichikroq tanlang)"}
    conn = get_db()
    conn.execute("UPDATE users SET avatar=? WHERE id=?", (avatar or None, user["id"]))
    conn.commit()
    conn.close()
    return {"ok": True, "avatar": avatar or None}


def log_audit(conn, actor, action, detail=""):
    conn.execute(
        "INSERT INTO audit (actor, action, detail, created_at) VALUES (?,?,?,?)",
        (actor, action, detail, now_local()),
    )


def api_team():
    """Login uchun emas — boshqaruvda ishlatish uchun jamoa ro'yxati (parolsiz)."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()
    return [public_user(dict(r)) for r in rows]


# ============================================================
#  SSENARIYLAR (scripts)
# ============================================================
SCRIPT_STATUSES = ["yozilmoqda", "tasdiq_kutilmoqda", "tasdiqlandi", "qaytarildi"]


def api_scripts(user, show_all=False):
    conn = get_db()
    if user["role"] == "client":
        rows = conn.execute(
            "SELECT * FROM scripts WHERE client = ? ORDER BY id DESC",
            (user.get("client_name") or "",),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM scripts ORDER BY id DESC").fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    if user["role"] == "lead" and not show_all:
        names = lead_project_names(user["name"])
        result = [r for r in result if r.get("project") in names]
    return result


def api_create_script(user, b):
    conn = get_db()
    title = b.get("title") or "Nomsiz ssenariy"
    project = b.get("project") or ""
    client = b.get("client") or ""
    author = b.get("author") or user["name"]
    sql = """INSERT INTO scripts (project_id, project, client, author, title, status, hook, story, cta, link)
             VALUES (?,?,?,?,?,?,?,?,?,?)"""
    params = (
        b.get("project_id"), project, client, author, title, "yozilmoqda",
        b.get("hook") or "", b.get("story") or "", b.get("cta") or "", b.get("link") or "",
    )
    if IS_PG:
        sid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        sid = conn.execute(sql, params).lastrowid
    conn.execute(
        "INSERT INTO script_versions (script_id, version, hook, story, cta, edited_by, created_at) VALUES (?,?,?,?,?,?,?)",
        (sid, 1, b.get("hook") or "", b.get("story") or "", b.get("cta") or "", author, now_local()),
    )
    log_audit(conn, user["name"], "ssenariy yaratdi", f"#{sid} {title}")
    conn.commit()
    row = conn.execute("SELECT * FROM scripts WHERE id=?", (sid,)).fetchone()
    conn.close()
    return dict(row)


def api_update_script(user, sid, b):
    conn = get_db()
    ex = conn.execute("SELECT * FROM scripts WHERE id=?", (sid,)).fetchone()
    if not ex:
        conn.close()
        return None
    ex = dict(ex)
    new = {
        "title": b.get("title", ex["title"]),
        "project": b.get("project", ex["project"]),
        "client": b.get("client", ex["client"]),
        "hook": b.get("hook", ex["hook"]),
        "story": b.get("story", ex["story"]),
        "cta": b.get("cta", ex["cta"]),
        "link": b.get("link", ex["link"]),
    }
    text_changed = (new["hook"], new["story"], new["cta"]) != (ex["hook"], ex["story"], ex["cta"])
    if text_changed:
        ver = conn.execute("SELECT COUNT(*) AS n FROM script_versions WHERE script_id=?", (sid,)).fetchone()["n"] + 1
        conn.execute(
            "INSERT INTO script_versions (script_id, version, hook, story, cta, edited_by, created_at) VALUES (?,?,?,?,?,?,?)",
            (sid, ver, new["hook"], new["story"], new["cta"], user["name"], now_local()),
        )
        log_audit(conn, user["name"], "ssenariy tahrirladi", f"#{sid} v{ver}")
    conn.execute(
        "UPDATE scripts SET title=?, project=?, client=?, hook=?, story=?, cta=?, link=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (new["title"], new["project"], new["client"], new["hook"], new["story"], new["cta"], new["link"], sid),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM scripts WHERE id=?", (sid,)).fetchone()
    conn.close()
    return dict(row)


def api_script_action(user, sid, b):
    """submit | approve | return | expert — ssenariy holatini o'zgartiradi."""
    action = b.get("action")
    conn = get_db()
    ex = conn.execute("SELECT * FROM scripts WHERE id=?", (sid,)).fetchone()
    if not ex:
        conn.close()
        return None
    ex = dict(ex)
    if action == "submit":
        conn.execute("UPDATE scripts SET status='tasdiq_kutilmoqda', updated_at=CURRENT_TIMESTAMP WHERE id=?", (sid,))
        log_audit(conn, user["name"], "ssenariy tasdiqqa yubordi", f"#{sid} {ex['title']}")
    elif action == "approve" and user["role"] in APPROVER_ROLES:
        conn.execute(
            "UPDATE scripts SET status='tasdiqlandi', approved_by=?, approved_at=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (user["name"], now_local(), sid),
        )
        log_audit(conn, user["name"], "ssenariy tasdiqladi", f"#{sid} {ex['title']}")
        send_telegram(f"📝 <b>Ssenariy tasdiqlandi</b>\n{ex['title']} — {ex['project']}\n✅ {user['name']}")
    elif action == "return" and user["role"] in APPROVER_ROLES:
        conn.execute(
            "UPDATE scripts SET status='qaytarildi', approved_by=?, approved_at=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (user["name"], now_local(), sid),
        )
        log_audit(conn, user["name"], "ssenariy qaytardi", f"#{sid} {ex['title']}")
    elif action == "expert" and user["role"] in APPROVER_ROLES:
        ok = 1 if b.get("expert_ok") else 0
        conn.execute(
            "UPDATE scripts SET expert_ok=?, expert_note=?, expert_at=? WHERE id=?",
            (ok, b.get("expert_note") or "", now_local(), sid),
        )
        log_audit(conn, user["name"], "ekspert tasdig'i", f"#{sid} {'ha' if ok else 'yoq'}")
    else:
        conn.close()
        return {"error": "Ruxsat yo'q yoki noto'g'ri amal"}
    conn.commit()
    row = conn.execute("SELECT * FROM scripts WHERE id=?", (sid,)).fetchone()
    conn.close()
    return dict(row)


def api_script_versions(sid):
    conn = get_db()
    rows = conn.execute("SELECT * FROM script_versions WHERE script_id=? ORDER BY version DESC", (sid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def api_script_stats():
    """Har bir ssenarist bo'yicha statistika."""
    conn = get_db()
    rows = conn.execute("SELECT author, status FROM scripts").fetchall()
    conn.close()
    by = {}
    for r in rows:
        a = r["author"] or "—"
        by.setdefault(a, {"author": a, "total": 0, "approved": 0, "returned": 0})
        by[a]["total"] += 1
        if r["status"] == "tasdiqlandi":
            by[a]["approved"] += 1
        if r["status"] == "qaytarildi":
            by[a]["returned"] += 1
    for v in by.values():
        v["rate"] = round(v["approved"] / v["total"] * 100) if v["total"] else 0
    return sorted(by.values(), key=lambda x: -x["total"])


# ============================================================
#  VIDEOLAR (montaj) + pul hisobi
# ============================================================
# Video ish jarayoni:
#  biriktirildi  → rahbar montajchiga biriktirdi (montajchi montaj qilishi kerak)
#  montaj_qilindi→ montajchi tugatdi → sifat nazoratiga (Said)
#  sifat_ok      → sifat nazorati o'tdi → loyiha rahbari yakuniy qabuliga
#  qabul_qilindi → rahbar qabul qildi → PUL hisoblandi → joylashga (Aisha)
#  joylandi      → SMM Instagram'ga joyladi (tugadi)
#  qaytarildi    → qaytarildi (montajchi qayta ishlaydi)
VIDEO_STATUSES = ["biriktirildi", "montaj_qilindi", "sifat_ok", "qabul_qilindi", "joylandi", "qaytarildi", "bekor_qilindi"]
DONE_STATUSES = ("qabul_qilindi", "joylandi")  # pul hisoblanadigan holatlar
SMM_ROLES = ("smm", "ceo", "coordinator")


def _editor_accepted_counts(conn):
    """Har montajyor uchun qabul qilingan video soni (lavozim hisobi uchun)."""
    counts = {}
    for r in conn.execute(
        "SELECT editor, COUNT(*) AS n FROM videos WHERE status IN ('qabul_qilindi','joylandi') GROUP BY editor"
    ).fetchall():
        counts[r["editor"] or ""] = r["n"]
    return counts


def decorate_video(d, counts, role, username):
    """Videoga montajyor lavozimini qo'shadi va pulni faqat CEO/o'z montajyoriga ko'rsatadi."""
    ed = d.get("editor") or ""
    cnt = eff_count(ed, counts.get(ed, 0))
    info = rank_info(cnt)
    d["editor_rank"] = info["rank_key"]
    d["editor_rank_label"] = info["rank_label"]
    d["editor_rank_icon"] = info["rank_icon"]
    own = (role == "editor" and ed == username)
    if role == "ceo" or own:
        # Hali qabul qilinmagan bo'lsa — lavozim+tur bo'yicha prognoz haq ko'rsatiladi
        if d.get("status") not in DONE_STATUSES:
            d["amount"] = editor_pay(cnt, d.get("vtype") or "reels")[0]
        d["pay_visible"] = True
    else:
        d["amount"] = None
        d["pay_visible"] = False
    # Deadline ma'lumoti (hali jarayonda bo'lgan videolar uchun)
    d["deadline_hours"] = DEADLINE_HOURS.get(d.get("vtype") or "reels", 24)
    if d.get("assigned_at") and d.get("status") in ("biriktirildi", "montaj_qilindi", "sifat_ok", "qaytarildi"):
        try:
            a = datetime.datetime.strptime(d["assigned_at"][:19], "%Y-%m-%d %H:%M:%S")
            deadline = a + datetime.timedelta(hours=d["deadline_hours"])
            now = uz_now().replace(tzinfo=None)
            d["deadline_at"] = deadline.strftime("%Y-%m-%d %H:%M")
            d["overdue"] = now > deadline
            d["hours_left"] = round((deadline - now).total_seconds() / 3600, 1)
        except (ValueError, TypeError):
            pass
    return d


def api_videos(user, show_all=False):
    conn = get_db()
    role = user["role"]
    if role == "client":
        rows = conn.execute("SELECT * FROM videos WHERE client=? ORDER BY id DESC", (user.get("client_name") or "",)).fetchall()
    elif role == "editor":
        rows = conn.execute("SELECT * FROM videos WHERE editor=? ORDER BY id DESC", (user["name"],)).fetchall()
    elif role == "smm":
        # Aisha faqat qabul qilingan (joylash kutayotgan) va joylangan videolarni ko'radi
        rows = conn.execute(
            "SELECT * FROM videos WHERE status IN ('qabul_qilindi','joylandi') ORDER BY id DESC"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM videos ORDER BY id DESC").fetchall()
    counts = _editor_accepted_counts(conn)
    conn.close()
    result = [decorate_video(dict(r), counts, role, user["name"]) for r in rows]
    if role == "lead" and not show_all:
        names = lead_project_names(user["name"])
        result = [r for r in result if r.get("project") in names]
    return result


def api_qc(user):
    """Sifat nazorati uchun — montaj qilingan, tasdiq kutayotgan videolar (hammasi)."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM videos WHERE status='montaj_qilindi' ORDER BY id DESC").fetchall()
    counts = _editor_accepted_counts(conn)
    conn.close()
    return [decorate_video(dict(r), counts, user["role"], user["name"]) for r in rows]


def api_create_video(user, b):
    """Loyiha rahbari videoni montajchiga BIRIKTIRADI."""
    conn = get_db()
    editor = b.get("editor") or ""
    title = b.get("title") or "Nomsiz video"
    vtype = b.get("vtype") if b.get("vtype") in VIDEO_TYPES else "reels"
    sql = """INSERT INTO videos (project_id, project, client, script_id, title, editor, vdate, drive_link, note, status, assigned_by, vtype, assigned_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    params = (
        b.get("project_id"), b.get("project") or "", b.get("client") or "", b.get("script_id"),
        title, editor, b.get("vdate") or uz_today().isoformat(),
        b.get("drive_link") or "", b.get("note") or "", "biriktirildi", user["name"], vtype, now_local(),
    )
    if IS_PG:
        vid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        vid = conn.execute(sql, params).lastrowid
    log_audit(conn, user["name"], "video biriktirdi", f"#{vid} {title} → {editor}")
    conn.commit()
    row = conn.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
    conn.close()
    send_telegram(f"🎬 <b>Yangi montaj biriktirildi</b>\n{title}\n🎞 Tur: {VIDEO_TYPES.get(vtype, vtype)}\n👤 Montajchi: {editor}\n📁 {b.get('project') or '—'}\n👮 {user['name']}")
    return dict(row)


def api_video_action(user, vid, b):
    """Ish jarayoni amallari: montaj_done | qc_ok | qc_return | accept | return | posted."""
    action = b.get("action")
    role = user["role"]
    conn = get_db()
    ex = conn.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
    if not ex:
        conn.close()
        return None
    ex = dict(ex)

    if action == "montaj_done" and (ex["editor"] == user["name"] or role in ADMIN_ROLES):
        conn.execute(
            "UPDATE videos SET status='montaj_qilindi', drive_link=?, note=?, montaj_at=? WHERE id=?",
            (b.get("drive_link") or ex["drive_link"], b.get("note") or ex["note"], now_local(), vid),
        )
        log_audit(conn, user["name"], "montaj tugatdi", f"#{vid} {ex['title']}")
        send_telegram(f"🎞 <b>Montaj tugatildi</b>\n{ex['title']}\n👤 {ex['editor']}\n→ Sifat nazoratiga")
    elif action == "qc_ok" and role in APPROVER_ROLES:
        conn.execute(
            "UPDATE videos SET status='sifat_ok', qc_by=?, qc_at=? WHERE id=?",
            (user["name"], now_local(), vid),
        )
        log_audit(conn, user["name"], "sifat tasdiqladi", f"#{vid} {ex['title']}")
        send_telegram(f"🔎 <b>Sifat nazorati o'tdi</b>\n{ex['title']}\n👮 {user['name']} → Rahbar qabuliga")
    elif action == "qc_return" and role in APPROVER_ROLES:
        conn.execute(
            "UPDATE videos SET status='qaytarildi', qc_by=?, qc_at=?, note=? WHERE id=?",
            (user["name"], now_local(), b.get("note") or ex["note"], vid),
        )
        log_audit(conn, user["name"], "sifat qaytardi", f"#{vid} {ex['title']}")
        send_telegram(f"↩️ <b>Sifatdan qaytarildi</b>\n{ex['title']}\n👤 {ex['editor']}\n👮 {user['name']}")
    elif action == "accept" and role in APPROVER_ROLES:
        # Montajyor lavozimiga (shu paytgacha qabul qilingan video soni) qarab pul avtomatik hisoblanadi
        prev_accepted = conn.execute(
            "SELECT COUNT(*) AS n FROM videos WHERE editor=? AND status IN ('qabul_qilindi','joylandi')",
            (ex["editor"],),
        ).fetchone()["n"]
        vt = ex.get("vtype") or "reels"
        amount, rk = editor_pay(eff_count(ex["editor"], prev_accepted), vt)
        rk_label = next((r["label"] for r in RANKS if r["key"] == rk), rk)
        now_s = now_local()
        # Deadline: kechiksa reels — pul yo'q, podcast/youtube — yarim
        late, _ = _deadline_check(ex.get("assigned_at") or ex.get("created_at"), vt, now_s)
        late_note = ""
        if late:
            if vt == "reels":
                amount = 0
                late_note = " · ⏰ KECHIKKAN (pul yo'q)"
            else:
                amount = amount // 2
                late_note = " · ⏰ KECHIKKAN (yarim pul)"
        conn.execute(
            "UPDATE videos SET status='qabul_qilindi', tier=?, amount=?, approved_by=?, approved_at=?, is_late=? WHERE id=?",
            (rk, amount, user["name"], now_s, 1 if late else 0, vid),
        )
        log_audit(conn, user["name"], "video qabul qildi", f"#{vid} {ex['title']} · {VIDEO_TYPES.get(vt, vt)} · {rk_label}{late_note}")
        log_audit(conn, "Tizim", "pul hisoblandi", f"#{vid} {ex['editor']} ({rk_label}) +{amount} so'm{late_note}")
        send_telegram(
            f"✅ <b>Video QABUL QILINDI</b>\n{ex['title']}\n👤 {ex['editor']} · {rk_label}\n"
            f"💰 {VIDEO_TYPES.get(vt, vt)} — {amount:,} so'm hisoblandi{late_note}\n👮 Tasdiqladi: {user['name']}\n→ Joylashga".replace(",", " ")
        )
    elif action == "return" and role in APPROVER_ROLES:
        conn.execute(
            "UPDATE videos SET status='qaytarildi', approved_by=?, approved_at=?, note=? WHERE id=?",
            (user["name"], now_local(), b.get("note") or ex["note"], vid),
        )
        log_audit(conn, user["name"], "video qaytardi", f"#{vid} {ex['title']}")
        send_telegram(f"↩️ <b>Video qaytarildi</b>\n{ex['title']}\n👤 {ex['editor']}\n👮 {user['name']}")
    elif action == "cancel" and role in APPROVER_ROLES:
        conn.execute(
            "UPDATE videos SET status='bekor_qilindi', note=? WHERE id=?",
            (b.get("note") or ex["note"], vid),
        )
        log_audit(conn, user["name"], "biriktirishni bekor qildi", f"#{vid} {ex['title']}")
        send_telegram(f"🚫 <b>Biriktirish bekor qilindi</b>\n{ex['title']}\n👤 {ex['editor']}\n👮 {user['name']}")
    elif action == "posted" and role in SMM_ROLES:
        conn.execute(
            "UPDATE videos SET status='joylandi', instagram_link=?, posted_by=?, posted_at=? WHERE id=?",
            (b.get("instagram_link") or ex["instagram_link"], user["name"], now_local(), vid),
        )
        log_audit(conn, user["name"], "Instagram'ga joyladi", f"#{vid} {ex['title']}")
        send_telegram(f"📷 <b>Instagram'ga joylandi</b>\n{ex['title']}\n📁 {ex['project']}\n👤 {user['name']}")
    else:
        conn.close()
        return {"error": "Ruxsat yo'q yoki noto'g'ri amal"}
    conn.commit()
    row = conn.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
    conn.close()
    return dict(row)


def api_delete_video(user, vid):
    conn = get_db()
    conn.execute("DELETE FROM videos WHERE id=?", (vid,))
    log_audit(conn, user["name"], "video o'chirdi", f"#{vid}")
    conn.commit()
    conn.close()
    return {"ok": True}


# ============================================================
#  MONTAJCHILAR KABINETI + STATISTIKA
# ============================================================
def editor_summary(conn, name):
    vids = [dict(r) for r in conn.execute("SELECT * FROM videos WHERE editor=?", (name,)).fetchall()]
    accepted = [v for v in vids if v["status"] in DONE_STATUSES]
    earned = sum(v["amount"] or 0 for v in accepted)
    paid = conn.execute("SELECT COALESCE(SUM(amount),0) AS s FROM payments WHERE editor=?", (name,)).fetchone()["s"] or 0
    by_project = {}
    for v in accepted:
        by_project[v["project"]] = by_project.get(v["project"], 0) + 1
    rinfo = rank_info(eff_count(name, len(accepted)))
    return {
        "name": name,
        "videos": len(vids),
        "accepted": len(accepted),
        **rinfo,
        # montaj qilishi kerak: biriktirilgan + qaytarilgan
        "toDo": sum(1 for v in vids if v["status"] in ("biriktirildi", "qaytarildi")),
        # tasdiq jarayonida: montaj qilingan + sifat o'tgan
        "inReview": sum(1 for v in vids if v["status"] in ("montaj_qilindi", "sifat_ok")),
        "returned": sum(1 for v in vids if v["status"] == "qaytarildi"),
        "pending": sum(1 for v in vids if v["status"] in ("biriktirildi", "qaytarildi")),
        "earned": earned,
        "paid": paid,
        "remaining": earned - paid,
        "avg": round(earned / len(accepted)) if accepted else 0,
        "byProject": [{"project": k, "count": v} for k, v in sorted(by_project.items(), key=lambda x: -x[1])],
    }


def api_editors(user):
    conn = get_db()
    editors = conn.execute("SELECT name, color, title, avatar FROM users WHERE role='editor' ORDER BY name").fetchall()
    result = []
    for e in editors:
        s = editor_summary(conn, e["name"])
        s["color"] = e["color"]
        s["title"] = e["title"]
        s["avatar"] = e["avatar"]
        result.append(s)
    conn.close()
    return result


def api_editor_cabinet(user):
    """Montajchining o'z kabineti (o'zi uchun)."""
    conn = get_db()
    s = editor_summary(conn, user["name"])
    vids = [dict(r) for r in conn.execute("SELECT * FROM videos WHERE editor=? ORDER BY id DESC", (user["name"],)).fetchall()]
    pays = [dict(r) for r in conn.execute("SELECT * FROM payments WHERE editor=? ORDER BY id DESC", (user["name"],)).fetchall()]
    conn.close()
    s["videosList"] = vids
    s["payments"] = pays
    s["color"] = user.get("color")
    return s


# ============================================================
#  TO'LOVLAR
# ============================================================
def api_payments(user):
    conn = get_db()
    if user["role"] == "editor":
        rows = conn.execute("SELECT * FROM payments WHERE editor=? ORDER BY id DESC", (user["name"],)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def api_create_payment(user, b):
    conn = get_db()
    editor = b.get("editor") or ""
    amount = int(b.get("amount") or 0)
    sql = "INSERT INTO payments (editor, amount, paid_by, note, pdate) VALUES (?,?,?,?,?)"
    params = (editor, amount, user["name"], b.get("note") or "", b.get("pdate") or uz_today().isoformat())
    if IS_PG:
        pid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        pid = conn.execute(sql, params).lastrowid
    log_audit(conn, user["name"], "to'lov qildi", f"{editor} +{amount} so'm — {b.get('note') or ''}")
    conn.commit()
    conn.close()
    send_telegram(
        f"💸 <b>To'lov amalga oshirildi</b>\n👤 {editor}\n💰 {amount:,} so'm\n👮 To'lagan: {user['name']}".replace(",", " ")
        + (f"\n📝 {b.get('note')}" if b.get("note") else "")
    )
    return {"ok": True, "id": pid}


# ============================================================
#  AUDIT LOG
# ============================================================
def api_audit(limit=200):
    conn = get_db()
    rows = conn.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
#  CEO MOLIYA PANELI
# ============================================================
def api_finance():
    conn = get_db()
    month = uz_now().strftime("%Y-%m")
    editors = api_editors({"role": "ceo"})
    total_earned = sum(e["earned"] for e in editors)
    total_paid = sum(e["paid"] for e in editors)
    # Shu oydagi xarajat (qabul qilingan videolar)
    accepted = [dict(r) for r in conn.execute("SELECT * FROM videos WHERE status IN ('qabul_qilindi','joylandi')").fetchall()]
    month_cost = sum(v["amount"] or 0 for v in accepted if (v["approved_at"] or "").startswith(month))
    # Loyiha bo'yicha montaj xarajati
    by_project = {}
    for v in accepted:
        by_project[v["project"] or "—"] = by_project.get(v["project"] or "—", 0) + (v["amount"] or 0)
    # Kadr Media P&L: loyiha daromadi − jamoa maoshi
    rate = get_usd_rate()
    fee_rows = [dict(r) for r in conn.execute("SELECT name, monthly_fee FROM projects WHERE monthly_fee>0 ORDER BY monthly_fee DESC").fetchall()]
    media_income = sum(p["monthly_fee"] or 0 for p in fee_rows)
    payroll_total = 0
    for n in SALARY:
        s = compute_salary(conn, n, rate)
        if s:
            payroll_total += s["total"]
    conn.close()
    top = max(editors, key=lambda e: e["accepted"], default=None)
    return {
        "month": month,
        "totalEarned": total_earned,
        "totalPaid": total_paid,
        "totalRemaining": total_earned - total_paid,
        "monthCost": month_cost,
        "topEditor": (top["name"] if top and top["accepted"] else None),
        "topEditorVideos": (top["accepted"] if top else 0),
        "editors": editors,
        "byProject": [{"project": k, "cost": v} for k, v in sorted(by_project.items(), key=lambda x: -x[1])],
        "mediaIncome": media_income,
        "payrollTotal": payroll_total,
        "mediaNet": media_income - payroll_total,
        "projectIncome": [{"name": p["name"], "fee": p["monthly_fee"]} for p in fee_rows],
    }


def api_tiers():
    return TIERS


def api_ranks():
    """Lavozim tizimi: ketma-ketlik, narxlar va o'tish sharti — frontend ko'rsatishi uchun."""
    return {"ranks": RANKS, "prices": RANK_PRICES, "step": RANK_STEP}


# ------------------------------------------------------------
#  KADR STUDIO — syomka bronlari va xona daromadi
# ------------------------------------------------------------
def can_view_studio(user):
    """Studio kalendarini ko'rish — barcha loyiha rahbarlari, koordinator va CEO."""
    return bool(user) and user["role"] in ("ceo", "coordinator", "lead")


def can_edit_studio(user):
    """Studio broni kiritish/o'zgartirish — faqat Dilshod va Gulmira."""
    return bool(user) and user["name"] in STUDIO_EDIT_USERS


def _op_pay(operator, shoot_type):
    """Operator belgilangan bo'lsa — syomka turiga qarab operator puli."""
    if not operator:
        return 0
    return OPERATOR_PAY.get(shoot_type if shoot_type in SHOOT_TYPES else "reels", 0)


def _calc_hours(start, end):
    """HH:MM dan HH:MM gacha soatlar (yarim soat aniqlikda)."""
    try:
        sh, sm = (int(x) for x in start.split(":")[:2])
        eh, em = (int(x) for x in end.split(":")[:2])
        mins = (eh * 60 + em) - (sh * 60 + sm)
        if mins <= 0:
            mins += 24 * 60  # yarim tunni kesib o'tsa
        return round(mins / 60, 2)
    except (ValueError, AttributeError):
        return 0


def api_studio(user):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM studio_bookings ORDER BY bdate DESC, start_time"
    ).fetchall()
    conn.close()
    return {
        "rooms": STUDIO_ROOMS,
        "operators": list(STUDIO_OPERATORS),
        "shootTypes": SHOOT_TYPES,
        "operatorPay": OPERATOR_PAY,
        "canFinance": can_edit_studio(user),
        "canEdit": can_edit_studio(user),
        "me": user["name"],
        "bookings": [dict(r) for r in rows],
    }


def api_create_studio_booking(user, b):
    room = b.get("room") if b.get("room") in STUDIO_ROOMS else "white"
    start = b.get("start_time") or "10:00"
    end = b.get("end_time") or "11:00"
    hours = _calc_hours(start, end)
    operator = b.get("operator") if b.get("operator") in STUDIO_OPERATORS else ""
    shoot_type = b.get("shoot_type") if b.get("shoot_type") in SHOOT_TYPES else "reels"
    operator_pay = _op_pay(operator, shoot_type)
    # Umumiy to'lov va to'langan (avans) qo'lda kiritiladi
    try:
        amount = int(b.get("amount") or 0)
    except (ValueError, TypeError):
        amount = 0
    try:
        paid_amount = int(b.get("paid_amount") or 0)
    except (ValueError, TypeError):
        paid_amount = 0
    fully_paid = 1 if (amount > 0 and paid_amount >= amount) else 0
    bdate = b.get("bdate") or uz_today().isoformat()
    conn = get_db()
    sql = """INSERT INTO studio_bookings
             (room, client_name, phone, bdate, start_time, end_time, hours, amount,
              paid, paid_amount, operator, shoot_type, operator_pay, status, note, created_by)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    params = (
        room, b.get("client_name") or "Mijoz", b.get("phone") or "", bdate,
        start, end, hours, amount, fully_paid, paid_amount,
        operator, shoot_type, operator_pay, "active",
        b.get("note") or "", user["name"],
    )
    if IS_PG:
        bid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        bid = conn.execute(sql, params).lastrowid
    log_audit(conn, user["name"], "studio bron qildi",
              f"#{bid} {b.get('client_name')} · {STUDIO_ROOMS[room]['label']} · {SHOOT_TYPES[shoot_type]}"
              + (f" · operator {operator} (+{operator_pay})" if operator else ""))
    conn.commit()
    row = conn.execute("SELECT * FROM studio_bookings WHERE id=?", (bid,)).fetchone()
    conn.close()
    send_telegram(
        f"🎥 <b>Studio bron</b>\n{b.get('client_name') or 'Mijoz'}\n"
        f"🏠 {STUDIO_ROOMS[room]['label']} · 🎬 {SHOOT_TYPES[shoot_type]}\n"
        + (f"👤 Operator: {operator} (+{operator_pay:,} so'm)\n".replace(",", " ") if operator else "")
        + f"📅 {bdate}  {start}–{end}  ({hours} soat)\n"
        f"💰 Umumiy: {amount:,} so'm · To'langan: {paid_amount:,} so'm".replace(",", " ")
        + ("\n✅ <b>To'liq to'landi</b>" if fully_paid else "")
    )
    return dict(row)


def api_studio_pay(user, bid, b):
    """Bronga to'lov qo'shish (avansdan keyin qolganini). To'liq to'lansa — guruhga xabar."""
    try:
        add = int(b.get("amount") or 0)
    except (ValueError, TypeError):
        add = 0
    conn = get_db()
    ex = conn.execute("SELECT * FROM studio_bookings WHERE id=?", (bid,)).fetchone()
    if not ex:
        conn.close()
        return None
    ex = dict(ex)
    new_paid = (ex.get("paid_amount") or 0) + add
    total = ex.get("amount") or 0
    fully = 1 if (total > 0 and new_paid >= total) else 0
    was_full = ex.get("paid") or 0
    conn.execute("UPDATE studio_bookings SET paid_amount=?, paid=? WHERE id=?", (new_paid, fully, bid))
    log_audit(conn, user["name"], "studio to'lov qo'shdi", f"#{bid} +{add} so'm (jami {new_paid}/{total})")
    conn.commit()
    row = dict(conn.execute("SELECT * FROM studio_bookings WHERE id=?", (bid,)).fetchone())
    conn.close()
    if fully and not was_full:
        send_telegram(
            f"✅ <b>Studio to'lov yakunlandi</b>\n{ex['client_name']}\n"
            f"💰 To'liq to'landi: {new_paid:,} so'm\n👤 {user['name']}".replace(",", " ")
        )
    return row


def api_cancel_studio_booking(user, bid):
    """Syomkani bekor qilish — o'chirilmaydi, tarixda qizil 'bekor qilindi' bo'lib qoladi.
    Bekor bo'lganda operatorga pul hisoblanmaydi (hisobotdan chiqadi)."""
    conn = get_db()
    ex = conn.execute("SELECT * FROM studio_bookings WHERE id=?", (bid,)).fetchone()
    if not ex:
        conn.close()
        return None
    ex = dict(ex)
    conn.execute("UPDATE studio_bookings SET status='bekor_qilindi' WHERE id=?", (bid,))
    log_audit(conn, user["name"], "studio bron bekor qildi", f"#{bid} {ex['client_name']}")
    conn.commit()
    row = dict(conn.execute("SELECT * FROM studio_bookings WHERE id=?", (bid,)).fetchone())
    conn.close()
    send_telegram(f"🚫 <b>Studio bron bekor qilindi</b>\n{ex['client_name']}\n👮 {user['name']}")
    return row


def api_delete_studio_booking(user, bid):
    conn = get_db()
    conn.execute("DELETE FROM studio_bookings WHERE id=?", (bid,))
    log_audit(conn, user["name"], "studio bron o'chirdi", f"#{bid}")
    conn.commit()
    conn.close()
    return {"ok": True}


def api_studio_finance(user):
    """Dilshod+Gulmira — oyma-oy tushum, operator puli, xarajat, sof foyda.
    Bekor qilingan bronlar hisobga OLINMAYDI. Sof foyda = tushum − operator puli − xarajatlar."""
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM studio_bookings").fetchall()]
    exps = [dict(r) for r in conn.execute("SELECT * FROM studio_expenses").fetchall()]
    conn.close()
    active = [r for r in rows if (r.get("status") or "active") != "bekor_qilindi"]
    months = {}

    def M(ym):
        return months.setdefault(ym or "—", {
            "month": ym or "—", "total": 0, "operatorPay": 0, "expenses": 0, "net": 0,
            "paid": 0, "debt": 0, "count": 0, "white": 0, "black": 0,
        })

    for r in active:
        m = M((r.get("bdate") or "")[:7])
        amt = r["amount"] or 0
        pa = r.get("paid_amount") or 0
        m["total"] += amt
        m["operatorPay"] += r.get("operator_pay") or 0
        m["paid"] += pa
        m["debt"] += max(amt - pa, 0)
        m["count"] += 1
        if r["room"] in ("white", "black"):
            m[r["room"]] += amt
    for e in exps:
        M((e.get("edate") or "")[:7])["expenses"] += e.get("amount") or 0
    for m in months.values():
        m["net"] = m["total"] - m["operatorPay"] - m["expenses"]

    total_all = sum(r["amount"] or 0 for r in active)
    op_all = sum(r.get("operator_pay") or 0 for r in active)
    paid_all = sum(r.get("paid_amount") or 0 for r in active)
    exp_all = sum(e.get("amount") or 0 for e in exps)
    return {
        "rooms": STUDIO_ROOMS,
        "months": sorted(months.values(), key=lambda x: x["month"], reverse=True),
        "totalAll": total_all,
        "operatorPayAll": op_all,
        "expensesAll": exp_all,
        "netAll": total_all - op_all - exp_all,
        "paidAll": paid_all,
        "debtAll": max(total_all - paid_all, 0),
        "count": len(active),
    }


def api_studio_expenses(user):
    """Kadr Studio xarajatlari — Dilshod+Gulmira ko'radi va kiritadi."""
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM studio_expenses ORDER BY edate DESC, id DESC").fetchall()]
    conn.close()
    by_month = {}
    for r in rows:
        ym = (r.get("edate") or "")[:7] or "—"
        by_month[ym] = by_month.get(ym, 0) + (r.get("amount") or 0)
    return {
        "names": STUDIO_EXPENSE_NAMES,
        "expenses": rows,
        "totalAll": sum(r.get("amount") or 0 for r in rows),
        "byMonth": [{"month": k, "total": v} for k, v in sorted(by_month.items(), reverse=True)],
    }


def api_create_studio_expense(user, b):
    try:
        amount = int(b.get("amount") or 0)
    except (ValueError, TypeError):
        amount = 0
    name = (b.get("name") or "Boshqa").strip() or "Boshqa"
    edate = b.get("edate") or uz_today().isoformat()
    conn = get_db()
    sql = "INSERT INTO studio_expenses (name, amount, edate, note, created_by) VALUES (?,?,?,?,?)"
    params = (name, amount, edate, b.get("note") or "", user["name"])
    if IS_PG:
        eid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        eid = conn.execute(sql, params).lastrowid
    log_audit(conn, user["name"], "studio xarajat kiritdi", f"#{eid} {name} · {amount} so'm")
    conn.commit()
    row = dict(conn.execute("SELECT * FROM studio_expenses WHERE id=?", (eid,)).fetchone())
    conn.close()
    return row


def api_delete_studio_expense(user, eid):
    conn = get_db()
    conn.execute("DELETE FROM studio_expenses WHERE id=?", (eid,))
    log_audit(conn, user["name"], "studio xarajat o'chirdi", f"#{eid}")
    conn.commit()
    conn.close()
    return {"ok": True}


# ------------------------------------------------------------
#  KADR MEDIA SYOMKALARI (loyiha syomkalari, operator puli bilan)
# ------------------------------------------------------------
def api_shoots(user, show_all=False):
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM shoots ORDER BY sdate DESC, id DESC").fetchall()]
    conn.close()
    if user["role"] == "lead" and not show_all:
        names = lead_project_names(user["name"])
        rows = [r for r in rows if r.get("project") in names]
    # Operator daromadi (bekor qilinganlar hisobga olinmaydi)
    op_totals = {}
    for r in rows:
        if (r.get("status") or "active") != "bekor_qilindi" and r.get("operator"):
            op_totals[r["operator"]] = op_totals.get(r["operator"], 0) + (r.get("operator_pay") or 0)
    return {
        "operators": list(STUDIO_OPERATORS),
        "shootTypes": SHOOT_TYPES,
        "operatorPay": OPERATOR_PAY,
        "operatorTotals": op_totals,
        "shoots": rows,
    }


def api_create_shoot(user, b):
    """Loyiha rahbari loyihaga syomka belgilaydi — operator va turga qarab operator puli avtomatik."""
    shoot_type = b.get("shoot_type") if b.get("shoot_type") in SHOOT_TYPES else "reels"
    operator = b.get("operator") if b.get("operator") in STUDIO_OPERATORS else ""
    operator_pay = _op_pay(operator, shoot_type)
    sdate = b.get("sdate") or uz_today().isoformat()
    conn = get_db()
    sql = """INSERT INTO shoots (project_id, project, shoot_type, operator, operator_pay, sdate, status, note, created_by)
             VALUES (?,?,?,?,?,?,?,?,?)"""
    params = (b.get("project_id"), b.get("project") or "", shoot_type, operator,
              operator_pay, sdate, "active", b.get("note") or "", user["name"])
    if IS_PG:
        sid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        sid = conn.execute(sql, params).lastrowid
    log_audit(conn, user["name"], "syomka belgiladi",
              f"#{sid} {b.get('project')} · {SHOOT_TYPES[shoot_type]}"
              + (f" · {operator} (+{operator_pay})" if operator else ""))
    conn.commit()
    row = dict(conn.execute("SELECT * FROM shoots WHERE id=?", (sid,)).fetchone())
    conn.close()
    send_telegram(
        f"🎬 <b>Syomka belgilandi</b>\n📁 {b.get('project') or '—'}\n🎥 {SHOOT_TYPES[shoot_type]}"
        + (f"\n👤 Operator: {operator} (+{operator_pay:,} so'm)".replace(",", " ") if operator else "")
        + f"\n📅 {sdate}\n👮 {user['name']}"
    )
    return row


def api_cancel_shoot(user, sid):
    """Syomkani bekor qilish — operator puli hisoblanmaydi, tarixda qizil qoladi."""
    conn = get_db()
    ex = conn.execute("SELECT * FROM shoots WHERE id=?", (sid,)).fetchone()
    if not ex:
        conn.close()
        return None
    ex = dict(ex)
    conn.execute("UPDATE shoots SET status='bekor_qilindi' WHERE id=?", (sid,))
    log_audit(conn, user["name"], "syomka bekor qildi", f"#{sid} {ex['project']}")
    conn.commit()
    row = dict(conn.execute("SELECT * FROM shoots WHERE id=?", (sid,)).fetchone())
    conn.close()
    send_telegram(f"🚫 <b>Syomka bekor qilindi</b>\n📁 {ex['project']}\n👮 {user['name']}")
    return row


def api_delete_shoot(user, sid):
    conn = get_db()
    conn.execute("DELETE FROM shoots WHERE id=?", (sid,))
    log_audit(conn, user["name"], "syomka o'chirdi", f"#{sid}")
    conn.commit()
    conn.close()
    return {"ok": True}


# ------------------------------------------------------------
#  SSENARIST KABINETI (tasdiqlangan ssenariy uchun pul)
# ------------------------------------------------------------
def is_scenarist(user):
    return bool(user) and user["name"] in SCENARIST_PAY


def api_scenarist(user):
    """Ssenaristning o'z kabineti — tasdiqlangan ssenariylar va hisoblangan pul."""
    conn = get_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM scenarist_scripts WHERE author=? ORDER BY id DESC", (user["name"],)
    ).fetchall()]
    conn.close()
    active = [r for r in rows if (r.get("status") or "active") != "bekor_qilindi"]
    rate = SCENARIST_PAY.get(user["name"], 0)
    return {
        "rate": rate,
        "count": len(active),
        "earned": sum(r.get("amount") or 0 for r in active),
        "scripts": rows,
    }


def api_create_scenarist_script(user, b):
    rate = SCENARIST_PAY.get(user["name"], 0)
    sdate = b.get("sdate") or uz_today().isoformat()
    conn = get_db()
    sql = """INSERT INTO scenarist_scripts (author, project, client, title, amount, status, sdate, note)
             VALUES (?,?,?,?,?,?,?,?)"""
    params = (user["name"], b.get("project") or "", b.get("client") or "",
              b.get("title") or "Nomsiz ssenariy", rate, "active", sdate, b.get("note") or "")
    if IS_PG:
        sid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        sid = conn.execute(sql, params).lastrowid
    log_audit(conn, user["name"], "ssenariy kiritdi", f"#{sid} {b.get('title')} (+{rate})")
    conn.commit()
    row = dict(conn.execute("SELECT * FROM scenarist_scripts WHERE id=?", (sid,)).fetchone())
    conn.close()
    send_telegram(
        f"✍️ <b>Ssenariy kiritildi</b>\n{b.get('title') or ''}\n"
        f"👤 {user['name']} (+{rate:,} so'm)".replace(",", " ")
        + (f"\n📁 {b.get('project')}" if b.get("project") else "")
    )
    return row


def api_cancel_scenarist_script(user, sid):
    """Mijoz bekor qilsa — pul kabinetdan minus bo'ladi (bekor qilindi holati)."""
    conn = get_db()
    ex = conn.execute("SELECT * FROM scenarist_scripts WHERE id=? AND author=?", (sid, user["name"])).fetchone()
    if not ex:
        conn.close()
        return None
    ex = dict(ex)
    conn.execute("UPDATE scenarist_scripts SET status='bekor_qilindi' WHERE id=?", (sid,))
    log_audit(conn, user["name"], "ssenariy bekor qildi", f"#{sid} {ex['title']} (−{ex['amount']})")
    conn.commit()
    row = dict(conn.execute("SELECT * FROM scenarist_scripts WHERE id=?", (sid,)).fetchone())
    conn.close()
    return row


def api_delete_scenarist_script(user, sid):
    conn = get_db()
    conn.execute("DELETE FROM scenarist_scripts WHERE id=? AND author=?", (sid, user["name"]))
    log_audit(conn, user["name"], "ssenariy o'chirdi", f"#{sid}")
    conn.commit()
    conn.close()
    return {"ok": True}


# ------------------------------------------------------------
#  MAOSH (payroll) — fiksa + rahbarlik + dinamik daromadlar
# ------------------------------------------------------------
def get_usd_rate():
    conn = get_db()
    row = conn.execute("SELECT svalue FROM settings WHERE skey='usd_rate'").fetchone()
    conn.close()
    try:
        return int(row["svalue"]) if row and row["svalue"] else DEFAULT_USD_RATE
    except (ValueError, TypeError):
        return DEFAULT_USD_RATE


def api_set_usd_rate(user, b):
    try:
        v = int(b.get("rate") or 0)
    except (ValueError, TypeError):
        v = 0
    if v <= 0:
        return {"error": "Noto'g'ri kurs"}
    conn = get_db()
    conn.execute("DELETE FROM settings WHERE skey='usd_rate'")
    conn.execute("INSERT INTO settings (skey, svalue) VALUES ('usd_rate', ?)", (str(v),))
    log_audit(conn, user["name"], "USD kursini o'zgartirdi", f"1$ = {v} so'm")
    conn.commit()
    conn.close()
    return {"ok": True, "rate": v}


def _op_earn(conn, name):
    a = conn.execute("SELECT COALESCE(SUM(operator_pay),0) AS s FROM studio_bookings WHERE operator=? AND (status IS NULL OR status<>'bekor_qilindi')", (name,)).fetchone()["s"] or 0
    b = conn.execute("SELECT COALESCE(SUM(operator_pay),0) AS s FROM shoots WHERE operator=? AND (status IS NULL OR status<>'bekor_qilindi')", (name,)).fetchone()["s"] or 0
    return a + b


def _scenarist_earn(conn, name):
    return conn.execute("SELECT COALESCE(SUM(amount),0) AS s FROM scenarist_scripts WHERE author=? AND (status IS NULL OR status<>'bekor_qilindi')", (name,)).fetchone()["s"] or 0


def _montaj_earn(conn, name):
    return conn.execute("SELECT COALESCE(SUM(amount),0) AS s FROM videos WHERE editor=? AND status IN ('qabul_qilindi','joylandi')", (name,)).fetchone()["s"] or 0


LEAD_STAGES = ("ssenariy", "syomka", "montaj", "tasdiq", "joylash")


def _norm_name(s):
    """Loyiha nomini taqqoslash uchun soddalashtiradi (registrsiz, umumiy so'zlarsiz)."""
    s = (s or "").lower().strip()
    for w in ("loyihasi", "loyiha", "treding", "trading", "(", ")"):
        s = s.replace(w, " ")
    return " ".join(s.split())


def _find_project(projects, cfg_name):
    """Config nomiga mos loyihani topadi (aniq yoki kuchli so'z mosligi bo'yicha)."""
    key = _norm_name(cfg_name)
    ktok = set(key.split())
    for p in projects:
        pn = _norm_name(p["name"])
        if pn == key:
            return p
        common = ktok & set(pn.split())
        if any(len(w) > 3 for w in common):  # kamida bitta uzun so'z umumiy
            return p
    return None


def _leadership_pay(conn, name, rate):
    """Har rahbarlik loyihasi uchun: 5 bosqich (ssenariy/syomka/montaj/tasdiq/joylash)
    hammasi 'tayyor' bo'lsa — to'liq $50, aks holda $25. Loyiha topilmasa — to'liq (baholab bo'lmaydi)."""
    projects = [dict(r) for r in conn.execute("SELECT * FROM projects").fetchall()]
    total, details = 0, []
    for cfg_name in LEADERSHIP.get(name, []):
        p = _find_project(projects, cfg_name)
        if p:
            fully = all((p.get(st) or "") == "tayyor" for st in LEAD_STAGES)
            matched = p["name"]
        else:
            fully = True  # dashboard'da yo'q — to'liq deb hisoblanadi
            matched = None
        usd = LEADERSHIP_USD_FULL if fully else LEADERSHIP_USD_HALF
        total += usd * rate
        details.append({"project": cfg_name, "matched": matched, "usd": usd, "full": fully})
    return total, details


def _studio_client_bonus(conn):
    n = conn.execute("SELECT COUNT(*) AS n FROM studio_bookings WHERE (status IS NULL OR status<>'bekor_qilindi')").fetchone()["n"]
    return (n or 0) * STUDIO_CLIENT_BONUS


def _smm_pay(conn, full, today):
    """SMM = to'liq × (shu oy joylangan / shu oy tasdiqlangan). Video bo'lmasa 0."""
    ym = today.strftime("%Y-%m")
    accepted = conn.execute(
        "SELECT COUNT(*) AS n FROM videos WHERE status IN ('qabul_qilindi','joylandi') AND approved_at LIKE ?",
        (ym + "%",)).fetchone()["n"] or 0
    posted = conn.execute(
        "SELECT COUNT(*) AS n FROM videos WHERE status='joylandi' AND approved_at LIKE ?",
        (ym + "%",)).fetchone()["n"] or 0
    if accepted == 0:
        return 0, posted, accepted
    return int(round(full * posted / accepted)), posted, accepted


def compute_salary(conn, name, rate):
    cfg = SALARY.get(name)
    if not cfg:
        return None
    comps = []
    close_link = cfg.get("close_link")  # qaysi komponent kun yopishga bog'langan
    for label, som in (cfg.get("som") or {}).items():
        amt = int(som)
        lbl = label
        kind = "fixed"
        if label == "Intizom" and name in ATTENDANCE_USERS:
            ot = _ontime_days(conn, name, uz_today())
            amt = min(ot * INTIZOM_PER_DAY, INTIZOM_FULL)
            lbl = f"Intizom · {ot} kun o'z vaqtida"
            kind = "auto"
        elif label == close_link and name in DAILY_CLOSE_USERS:
            amt, missed = _kpi_after_discipline(conn, name, amt, uz_today())
            kind = "auto"
            if missed:
                lbl = f"{label} · −{missed} kun yopilmagan"
        comps.append({"label": lbl, "amount": amt, "kind": kind})
    for label, usd in (cfg.get("usd") or {}).items():
        amt = int(usd) * rate
        lbl = f"{label} (${usd})"
        kind = "fixed"
        if label == close_link and name in DAILY_CLOSE_USERS:
            # Kun yopishga bog'langan: har yopilmagan ish kuni −qiymat/25
            amt, missed = _kpi_after_discipline(conn, name, amt, uz_today())
            kind = "auto"
            if missed:
                lbl = f"{label} (${usd}) · −{missed} kun yopilmagan"
        elif label == "SMM":
            amt, posted, accepted = _smm_pay(conn, amt, uz_today())
            kind = "auto"
            lbl = f"SMM (${usd}) · {posted}/{accepted} joylandi"
        comps.append({"label": lbl, "amount": amt, "kind": kind})
    if cfg.get("lead"):
        lp, det = _leadership_pay(conn, name, rate)
        nfull = sum(1 for d in det if d["full"])
        nhalf = len(det) - nfull
        lbl = f"Rahbarlik ({len(det)} loyiha"
        lbl += f" · {nfull} to'liq" + (f", {nhalf} yarim" if nhalf else "") + ")"
        comps.append({"label": lbl, "amount": lp, "kind": "lead", "detail": det})
    if cfg.get("operator"):
        comps.append({"label": "Operator syomka puli", "amount": _op_earn(conn, name), "kind": "auto"})
    if cfg.get("scenarist"):
        comps.append({"label": "Ssenariy puli", "amount": _scenarist_earn(conn, name), "kind": "auto"})
    if cfg.get("montaj"):
        comps.append({"label": "Montaj puli", "amount": _montaj_earn(conn, name), "kind": "auto"})
    if cfg.get("studio_bonus"):
        comps.append({"label": "Studio mijoz bonusi", "amount": _studio_client_bonus(conn), "kind": "auto"})
    return {"name": name, "title": cfg.get("title", ""), "components": comps,
            "total": sum(c["amount"] for c in comps)}


def api_payroll(user):
    rate = get_usd_rate()
    conn = get_db()
    if user["role"] == "ceo":
        people = [p for p in (compute_salary(conn, n, rate) for n in SALARY) if p]
        conn.close()
        return {"rate": rate, "isCeo": True, "people": people,
                "grandTotal": sum(p["total"] for p in people)}
    me = compute_salary(conn, user["name"], rate)
    conn.close()
    return {"rate": rate, "isCeo": False, "me": me}


# ------------------------------------------------------------
#  XAYRIYA FONDI (Media+Studio sof foydasidan 5%) — Dilshod+Gulmira
# ------------------------------------------------------------
CHARITY_PCT = 0.05
CHARITY_USERS = ("Dilshod Khamraev", "Gulmira")


def is_charity_user(user):
    return bool(user) and user["name"] in CHARITY_USERS


def api_charity(user):
    conn = get_db()
    contrib = conn.execute("SELECT COALESCE(SUM(amount),0) AS s FROM charity_ledger WHERE kind='contribution'").fetchone()["s"] or 0
    withdraw = conn.execute("SELECT COALESCE(SUM(amount),0) AS s FROM charity_ledger WHERE kind='withdrawal'").fetchone()["s"] or 0
    ledger = [dict(r) for r in conn.execute("SELECT * FROM charity_ledger ORDER BY id DESC LIMIT 50").fetchall()]

    # Gulmira — faqat umumiy xayriya fondi (Media daromadi/foyda ko'rinmaydi)
    if user["role"] != "ceo":
        conn.close()
        return {"limited": True, "isCeo": False, "pct": int(CHARITY_PCT * 100),
                "balance": contrib - withdraw, "contributed": contrib, "withdrawn": withdraw,
                "ledger": ledger}

    # CEO (Dilshod) — to'liq hisob-kitob
    rate = get_usd_rate()
    projects = [dict(r) for r in conn.execute("SELECT name, monthly_fee FROM projects WHERE monthly_fee>0 ORDER BY monthly_fee DESC").fetchall()]
    media_income = sum(p["monthly_fee"] or 0 for p in projects)
    studio_income = conn.execute("SELECT COALESCE(SUM(amount),0) AS s FROM studio_bookings WHERE (status IS NULL OR status<>'bekor_qilindi')").fetchone()["s"] or 0
    studio_exp = conn.execute("SELECT COALESCE(SUM(amount),0) AS s FROM studio_expenses").fetchone()["s"] or 0
    payroll = 0
    for n in SALARY:
        s = compute_salary(conn, n, rate)
        if s:
            payroll += s["total"]
    conn.close()
    total_income = media_income + studio_income
    total_expense = payroll + studio_exp
    profit = total_income - total_expense
    return {
        "isCeo": True, "limited": False,
        "mediaIncome": media_income, "studioIncome": studio_income, "totalIncome": total_income,
        "payroll": payroll, "studioExpenses": studio_exp, "totalExpense": total_expense,
        "profit": profit, "pct": int(CHARITY_PCT * 100),
        "charityShare": int(round(max(profit, 0) * CHARITY_PCT)),
        "balance": contrib - withdraw, "contributed": contrib, "withdrawn": withdraw,
        "ledger": ledger, "projectIncome": [{"name": p["name"], "fee": p["monthly_fee"]} for p in projects],
    }


def api_charity_add(user, b):
    kind = "withdrawal" if b.get("kind") == "withdrawal" else "contribution"
    try:
        amount = int(b.get("amount") or 0)
    except (ValueError, TypeError):
        amount = 0
    if amount <= 0:
        return {"error": "Summani kiriting"}
    conn = get_db()
    conn.execute(
        "INSERT INTO charity_ledger (kind, amount, note, cdate, created_by) VALUES (?,?,?,?,?)",
        (kind, amount, b.get("note") or "", uz_today().isoformat(), user["name"]),
    )
    log_audit(conn, user["name"], "xayriya " + ("berdi" if kind == "withdrawal" else "qo'shdi"), f"{amount} so'm")
    conn.commit()
    conn.close()
    return {"ok": True}


# ------------------------------------------------------------
#  OYLIK STATISTIKA (har oy noldan; o'tgan oylar faqat ko'rish)
# ------------------------------------------------------------
def api_month_stats(user, ym):
    """Berilgan oy (YYYY-MM) uchun statistika. O'tgan oylar faqat ko'rish uchun."""
    cur = uz_now().strftime("%Y-%m")
    if not ym or len(ym) != 7:
        ym = cur
    if ym > cur:
        ym = cur  # kelajak oy ko'rsatilmaydi
    like = ym + "%"
    conn = get_db()

    def cnt(sql, params):
        return conn.execute(sql, params).fetchone()["n"] or 0

    # Umumiy (loyihalar bo'yicha bosqichlar) — shu oyda
    totals = {
        "ssenariy": cnt("SELECT COUNT(*) AS n FROM scenarist_scripts WHERE (status IS NULL OR status<>'bekor_qilindi') AND sdate LIKE ?", (like,)),
        "syomka": cnt("SELECT COUNT(*) AS n FROM shoots WHERE (status IS NULL OR status<>'bekor_qilindi') AND sdate LIKE ?", (like,)),
        "montaj": cnt("SELECT COUNT(*) AS n FROM videos WHERE montaj_at LIKE ?", (like,)),
        "tasdiq": cnt("SELECT COUNT(*) AS n FROM videos WHERE approved_at LIKE ? AND status IN ('qabul_qilindi','joylandi')", (like,)),
        "joylash": cnt("SELECT COUNT(*) AS n FROM videos WHERE posted_at LIKE ? AND status='joylandi'", (like,)),
    }

    # Jamoa (kimga tegishli bo'lsa) — shu oyda
    scenarists = [{"name": nm,
                   "count": cnt("SELECT COUNT(*) AS n FROM scenarist_scripts WHERE author=? AND (status IS NULL OR status<>'bekor_qilindi') AND sdate LIKE ?", (nm, like))}
                  for nm in SCENARIST_PAY]
    operators = [{"name": nm,
                  "count": cnt("SELECT COUNT(*) AS n FROM shoots WHERE operator=? AND (status IS NULL OR status<>'bekor_qilindi') AND sdate LIKE ?", (nm, like))
                            + cnt("SELECT COUNT(*) AS n FROM studio_bookings WHERE operator=? AND (status IS NULL OR status<>'bekor_qilindi') AND bdate LIKE ?", (nm, like))}
                 for nm in STUDIO_OPERATORS]
    ed_rows = conn.execute("SELECT name FROM users WHERE role='editor' ORDER BY name").fetchall()
    editors = [{"name": e["name"],
                "count": cnt("SELECT COUNT(*) AS n FROM videos WHERE editor=? AND approved_at LIKE ? AND status IN ('qabul_qilindi','joylandi')", (e["name"], like))}
               for e in ed_rows]
    conn.close()
    return {
        "month": ym, "current": cur, "isPast": ym < cur,
        "totals": totals,
        "scenarists": scenarists, "operators": operators, "editors": editors,
    }


# ------------------------------------------------------------
#  KUNLIK SARHISOB (kun yopish) + KPI intizomi
# ------------------------------------------------------------
def is_daily_user(user):
    return bool(user) and user["name"] in DAILY_CLOSE_USERS


def _closed_dates(conn, name, ym):
    return {r["cdate"] for r in conn.execute(
        "SELECT cdate FROM daily_close WHERE person=? AND cdate LIKE ?", (name, ym + "%")
    ).fetchall()}


def _missed_workdays(conn, name, today):
    """Shu oyda bugundan OLDINGI ish kunlari (yakshanbadan tashqari) — yopilmaganlari."""
    ym = today.strftime("%Y-%m")
    closed = _closed_dates(conn, name, ym)
    missed = 0
    for d in range(1, today.day):  # bugundan oldingi kunlar
        dt = datetime.date(today.year, today.month, d)
        if dt.weekday() != 6 and dt.isoformat() not in closed:  # 6 = yakshanba
            missed += 1
    return missed


def _kpi_after_discipline(conn, name, full, today):
    """Kun yopishga bog'langan komponent: har yopilmagan ish kuni uchun flat −20 000
    (komponent qiymatidan qat'i nazar — hamma uchun bir xil)."""
    missed = _missed_workdays(conn, name, today)
    ded = min(missed * CLOSE_PENALTY_PER_DAY, full)
    return max(int(round(full - ded)), 0), missed


def api_daily(user):
    conn = get_db()
    today = uz_today()
    tstr = today.isoformat()
    ym = today.strftime("%Y-%m")
    res = {"today": tstr, "isWorkday": today.weekday() != 6, "amDaily": is_daily_user(user)}
    if is_daily_user(user):
        closed = _closed_dates(conn, user["name"], ym)
        elapsed = sum(1 for d in range(1, today.day + 1)
                      if datetime.date(today.year, today.month, d).weekday() != 6)
        res["closedToday"] = tstr in closed
        res["closedCount"] = len(closed)
        res["workdaysElapsed"] = elapsed
        res["missed"] = _missed_workdays(conn, user["name"], today)
        res["summary"] = {
            "bookings": conn.execute("SELECT COUNT(*) AS n FROM studio_bookings WHERE bdate=? AND (status IS NULL OR status<>'bekor_qilindi')", (tstr,)).fetchone()["n"],
            "shoots": conn.execute("SELECT COUNT(*) AS n FROM shoots WHERE sdate=? AND (status IS NULL OR status<>'bekor_qilindi')", (tstr,)).fetchone()["n"],
            "scripts": conn.execute("SELECT COUNT(*) AS n FROM scenarist_scripts WHERE sdate=? AND (status IS NULL OR status<>'bekor_qilindi')", (tstr,)).fetchone()["n"],
            "accepted": conn.execute("SELECT COUNT(*) AS n FROM videos WHERE approved_at LIKE ? AND status IN ('qabul_qilindi','joylandi')", (tstr + "%",)).fetchone()["n"],
        }
    if user["role"] == "ceo":
        res["overview"] = [{
            "name": nm, "closedToday": tstr in _closed_dates(conn, nm, ym),
            "closedCount": len(_closed_dates(conn, nm, ym)),
            "missed": _missed_workdays(conn, nm, today),
        } for nm in DAILY_CLOSE_USERS]
    conn.close()
    return res


def api_close_day(user):
    if not is_daily_user(user):
        return {"error": "Ruxsat yo'q"}
    conn = get_db()
    today = uz_today().isoformat()
    ex = conn.execute("SELECT id FROM daily_close WHERE person=? AND cdate=?", (user["name"], today)).fetchone()
    if not ex:
        conn.execute("INSERT INTO daily_close (person, cdate, closed_at) VALUES (?,?,?)",
                     (user["name"], today, now_local()))
        log_audit(conn, user["name"], "kunni yopdi", today)
        conn.commit()
    conn.close()
    return {"ok": True, "closedToday": True}


def api_cron_daily_check():
    """22:00 da tashqi cron chaqiradi — bugun kun yopmaganlarni guruhda eslatadi."""
    today = uz_today()
    if today.weekday() == 6:
        return {"ok": True, "skipped": "yakshanba"}
    tstr = today.isoformat()
    conn = get_db()
    not_closed = [nm for nm in DAILY_CLOSE_USERS
                  if not conn.execute("SELECT id FROM daily_close WHERE person=? AND cdate=?", (nm, tstr)).fetchone()]
    conn.close()
    if not_closed:
        send_telegram(
            "⚠️ <b>Kun sarhisobi yopilmadi!</b>\n📅 " + tstr + "\n\n"
            "Yopmaganlar: <b>" + ", ".join(not_closed) + "</b>\n\n"
            "❗️ Kun yopilmasa KPI puli kamayadi (har yopilmagan kun uchun −KPI/25)."
        )
    return {"ok": True, "notClosed": not_closed}


# ------------------------------------------------------------
#  KELISH NAZORATI (intizom) — ertalabki kruzhok / qo'lda "Keldim"
# ------------------------------------------------------------
def is_attend_user(user):
    return bool(user) and user["name"] in ATTENDANCE_USERS


def _ontime_days(conn, name, today):
    """Shu oyda o'z vaqtida kelgan ish kunlari (yakshanba hisobga olinmaydi)."""
    ym = today.strftime("%Y-%m")
    rows = conn.execute(
        "SELECT adate FROM attendance WHERE person=? AND adate LIKE ? AND on_time=1",
        (name, ym + "%"),
    ).fetchall()
    cnt = 0
    for r in rows:
        try:
            if datetime.date.fromisoformat(r["adate"]).weekday() != 6:  # yakshanba emas
                cnt += 1
        except (ValueError, TypeError):
            cnt += 1
    return cnt


def _record_attendance(conn, person, source):
    """Bugun uchun birinchi kelishni yozadi. Takror bo'lsa — o'zgartirmaydi."""
    today = uz_today().isoformat()
    ex = conn.execute("SELECT id FROM attendance WHERE person=? AND adate=?", (person, today)).fetchone()
    if ex:
        return None  # bugun allaqachon belgilangan
    now = uz_now()
    ctime = now.strftime("%H:%M")
    on_time = 1 if ctime <= ON_TIME_LIMIT else 0
    conn.execute(
        "INSERT INTO attendance (person, adate, checkin_time, on_time, source) VALUES (?,?,?,?,?)",
        (person, today, ctime, on_time, source),
    )
    tag = "o'z vaqtida" if on_time else "kech"
    log_audit(conn, person, "ishga keldi", f"{ctime} ({tag}, {source})")
    return {"time": ctime, "on_time": on_time}


def _save_last_webhook(update):
    """Diagnostika: oxirgi kelgan xabar xulosasini saqlaydi (nima kelganini ko'rish uchun)."""
    try:
        msg = (update or {}).get("message") or (update or {}).get("edited_message") \
            or (update or {}).get("channel_post") or {}
        frm = msg.get("from") or {}
        summary = {
            "ts": now_local(),
            "username": frm.get("username"),
            "name": frm.get("first_name"),
            "video_note": bool(msg.get("video_note")),
            "video": bool(msg.get("video")),
            "chat_id": (msg.get("chat") or {}).get("id"),
            "thread_id": msg.get("message_thread_id"),
            "keys": list(msg.keys())[:15],
        }
        conn = get_db()
        conn.execute("DELETE FROM settings WHERE skey='last_webhook'")
        conn.execute("INSERT INTO settings (skey, svalue) VALUES ('last_webhook', ?)", (json.dumps(summary),))
        conn.commit()
        conn.close()
    except Exception:
        pass


def api_last_webhook():
    conn = get_db()
    row = conn.execute("SELECT svalue FROM settings WHERE skey='last_webhook'").fetchone()
    conn.close()
    if not row or not row["svalue"]:
        return {"empty": True, "note": "Hali hech qanday xabar kelmagan"}
    try:
        return json.loads(row["svalue"])
    except (ValueError, TypeError):
        return {"empty": True}


def api_webhook_info():
    """Telegram getWebhookInfo — webhook sog'ligi, xatolar, kutayotgan xabarlar."""
    if not TELEGRAM_BOT_TOKEN:
        return {"error": "TELEGRAM_BOT_TOKEN yo'q"}
    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


def api_telegram_webhook(update):
    """Telegram botdan keladigan yangilanishlar. 'ish voxti' topikdagi kruzhok (video_note)
    ma'lum foydalanuvchidan kelsa — o'sha kishi ishga keldi deb belgilanadi."""
    try:
        _save_last_webhook(update)
        msg = (update or {}).get("message") or (update or {}).get("edited_message") or {}
        if not msg.get("video_note"):
            return {"ok": True}
        uname = ((msg.get("from") or {}).get("username") or "").lower()
        person = TELEGRAM_ATTEND.get(uname)
        if not person:
            return {"ok": True}
        conn = get_db()
        rec = _record_attendance(conn, person, "bot")
        conn.commit()
        conn.close()
        if rec:
            tag = "✅ o'z vaqtida" if rec["on_time"] else "🟡 kech"
            send_telegram(f"🟢 <b>{person}</b> ishga keldi — {rec['time']} ({tag})")
    except Exception:
        pass  # webhook hech qachon xato qaytarmasligi kerak
    return {"ok": True}


def api_checkin(user):
    """Qo'lda 'Keldim' (zaxira) — bot ishlamay qolsa."""
    if not is_attend_user(user):
        return {"error": "Ruxsat yo'q"}
    conn = get_db()
    rec = _record_attendance(conn, user["name"], "manual")
    conn.commit()
    conn.close()
    if not rec:
        return {"ok": True, "already": True}
    return {"ok": True, "time": rec["time"], "on_time": bool(rec["on_time"])}


def _attend_month(conn, name, today):
    ym = today.strftime("%Y-%m")
    rows = {r["adate"]: dict(r) for r in conn.execute(
        "SELECT * FROM attendance WHERE person=? AND adate LIKE ?", (name, ym + "%")).fetchall()}
    tstr = today.isoformat()
    on_time = sum(1 for r in rows.values() if r["on_time"])
    late = sum(1 for r in rows.values() if not r["on_time"])
    t = rows.get(tstr)
    return {
        "name": name, "onTimeDays": on_time, "lateDays": late,
        "todayIn": bool(t), "todayTime": (t["checkin_time"] if t else None),
        "todayOnTime": (bool(t["on_time"]) if t else None),
        "intizom": min(on_time * INTIZOM_PER_DAY, INTIZOM_FULL),
    }


def api_attendance(user):
    conn = get_db()
    today = uz_today()
    res = {"today": today.isoformat(), "limit": ON_TIME_LIMIT, "amAttend": is_attend_user(user)}
    if is_attend_user(user):
        res["me"] = _attend_month(conn, user["name"], today)
    if user["role"] == "ceo":
        res["overview"] = [_attend_month(conn, nm, today) for nm in ATTENDANCE_USERS]
    conn.close()
    return res


def api_clear_attendance(user, b):
    """CEO — noto'g'ri belgilangan kelishni tozalaydi (person + sana)."""
    person = b.get("person") or ""
    adate = b.get("date") or uz_today().isoformat()
    conn = get_db()
    conn.execute("DELETE FROM attendance WHERE person=? AND adate=?", (person, adate))
    log_audit(conn, user["name"], "kelishni tozaladi", f"{person} · {adate}")
    conn.commit()
    conn.close()
    return {"ok": True}


def api_setup_webhook(user):
    """CEO — botning webhook manzilini Telegramga ro'yxatdan o'tkazadi."""
    base = os.environ.get("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if not base:
        return {"error": "RENDER_EXTERNAL_URL topilmadi (Render env)"}
    if not TELEGRAM_BOT_TOKEN:
        return {"error": "TELEGRAM_BOT_TOKEN sozlanmagan"}
    hook = f"{base}/api/telegram/webhook"
    try:
        import urllib.request
        import urllib.parse
        api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        data = urllib.parse.urlencode({
            "url": hook,
            "allowed_updates": json.dumps(["message", "edited_message"]),
        }).encode()
        with urllib.request.urlopen(api_url, data=data, timeout=10) as r:
            res = json.loads(r.read().decode())
        return {"ok": res.get("ok", False), "webhook": hook, "telegram": res}
    except Exception as e:
        return {"error": str(e), "webhook": hook}


# ------------------------------------------------------------
#  HTTP Handler
# ------------------------------------------------------------
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    def _json(self, data, code=200):
        # default=str — Postgres'dan keladigan sana-vaqt (datetime) obyektlarini
        # matnga aylantiradi, aks holda JSON serializatsiya xato beradi.
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _serve_static(self, path):
        if path == "/" or path == "":
            path = "/index.html"
        safe = os.path.normpath(path).lstrip("/")
        full = os.path.join(PUBLIC_DIR, safe)
        if not full.startswith(PUBLIC_DIR) or not os.path.isfile(full):
            full = os.path.join(PUBLIC_DIR, "index.html")  # SPA fallback
        ext = os.path.splitext(full)[1]
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _auth(self):
        return user_from_token(self.headers.get("X-Token", ""))

    @staticmethod
    def _int(s):
        try:
            return int(s)
        except (ValueError, TypeError):
            return None

    def _forbid(self):
        return self._json({"error": "Ruxsat yo'q"}, 403)

    def do_GET(self):
        path = urlparse(self.path).path
        # --- Ochiq (auth shart emas) ---
        if path == "/api/ping":
            # Serverni uxlatmaslik uchun yengil ping (bazaga tegmaydi)
            return self._json({"ok": True, "ts": now_local()})
        if path == "/api/tiers":
            return self._json(api_tiers())
        if path == "/api/ranks":
            return self._json(api_ranks())
        if path == "/api/telegram/test":
            return self._json(api_telegram_test())
        if path == "/api/telegram/digest":
            return self._json(api_telegram_digest())
        if path == "/api/cron/daily-check":
            return self._json(api_cron_daily_check())
        if not path.startswith("/api/"):
            return self._serve_static(path)

        # --- Auth talab qilinadi ---
        user = self._auth()
        if not user:
            return self._json({"error": "Avtorizatsiya kerak"}, 401)
        seg = [s for s in path.split("/") if s]
        role = user["role"]
        show_all = "all=1" in (urlparse(self.path).query or "")

        if path == "/api/me":
            return self._json(public_user(user))
        if path == "/api/telegram/last":
            return self._forbid() if role != "ceo" else self._json(api_last_webhook())
        if path == "/api/telegram/webhook-info":
            return self._forbid() if role != "ceo" else self._json(api_webhook_info())
        if path == "/api/team":
            return self._json(api_team())
        if path == "/api/clients":
            return self._json(api_clients())
        if path == "/api/projects":
            return self._json(visible_projects(user, show_all))
        if path == "/api/stats":
            return self._json(api_stats(user, show_all))
        if path == "/api/scripts":
            return self._json(api_scripts(user, show_all))
        if path == "/api/script-stats":
            return self._json(api_script_stats())
        if path == "/api/videos":
            return self._json(api_videos(user, show_all))
        if path == "/api/qc":
            return self._forbid() if role not in APPROVER_ROLES else self._json(api_qc(user))
        if path == "/api/payments":
            return self._json(api_payments(user))
        if path == "/api/cabinet":
            return self._json(api_editor_cabinet(user))
        if path == "/api/editors":
            return self._forbid() if role not in APPROVER_ROLES else self._json(api_editors(user))
        if path == "/api/audit":
            return self._forbid() if role not in ADMIN_ROLES else self._json(api_audit())
        if path == "/api/finance":
            return self._forbid() if role != "ceo" else self._json(api_finance())
        if path == "/api/studio":
            return self._forbid() if not can_view_studio(user) else self._json(api_studio(user))
        if path == "/api/studio/finance":
            return self._forbid() if not can_edit_studio(user) else self._json(api_studio_finance(user))
        if path == "/api/studio/expenses":
            return self._forbid() if not can_edit_studio(user) else self._json(api_studio_expenses(user))
        if path == "/api/shoots":
            return self._forbid() if role not in APPROVER_ROLES else self._json(api_shoots(user, show_all))
        if path == "/api/scenarist":
            return self._forbid() if not is_scenarist(user) else self._json(api_scenarist(user))
        if path == "/api/payroll":
            if role != "ceo" and user["name"] not in SALARY:
                return self._forbid()
            return self._json(api_payroll(user))
        if path == "/api/daily":
            if not is_daily_user(user) and role != "ceo":
                return self._forbid()
            return self._json(api_daily(user))
        if path == "/api/month-stats":
            if role not in APPROVER_ROLES:
                return self._forbid()
            ym = (parse_qs(urlparse(self.path).query).get("ym") or [""])[0]
            return self._json(api_month_stats(user, ym))
        if path == "/api/charity":
            return self._forbid() if not is_charity_user(user) else self._json(api_charity(user))
        if path == "/api/attendance":
            if not is_attend_user(user) and role != "ceo":
                return self._forbid()
            return self._json(api_attendance(user))
        if len(seg) == 4 and seg[1] == "scripts" and seg[3] == "versions":
            sid = self._int(seg[2])
            return self._json(api_script_versions(sid)) if sid else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 3 and seg[1] == "projects":
            pid = self._int(seg[2])
            row = api_get_project(pid) if pid else None
            return self._json(row) if row else self._json({"error": "Topilmadi"}, 404)
        return self._json({"error": "Topilmadi"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/login":
            res = api_login(self._body())
            return self._json(res) if res else self._json({"error": "Login yoki parol noto'g'ri"}, 401)
        # Telegram webhook — ochiq (bot chaqiradi, auth yo'q)
        if path == "/api/telegram/webhook":
            return self._json(api_telegram_webhook(self._body()))

        user = self._auth()
        if not user:
            return self._json({"error": "Avtorizatsiya kerak"}, 401)
        b = self._body()
        seg = [s for s in path.split("/") if s]
        r = user["role"]

        if path == "/api/logout":
            return self._json(api_logout(self.headers.get("X-Token", "")))
        if path == "/api/change-password":
            return self._json(api_change_password(user, b))
        if path == "/api/avatar":
            return self._json(api_set_avatar(user, b))
        if path == "/api/projects":
            if r not in APPROVER_ROLES:
                return self._forbid()
            b["_actor"] = user["name"]
            return self._json(api_create_project(b), 201)
        if path == "/api/scripts":
            if r == "client":
                return self._forbid()
            return self._json(api_create_script(user, b), 201)
        if path == "/api/videos":
            if r not in APPROVER_ROLES:
                return self._forbid()
            return self._json(api_create_video(user, b), 201)
        if path == "/api/payments":
            if r not in ADMIN_ROLES:
                return self._forbid()
            return self._json(api_create_payment(user, b), 201)
        if path == "/api/studio":
            if not can_edit_studio(user):
                return self._forbid()
            return self._json(api_create_studio_booking(user, b), 201)
        if path == "/api/studio/expenses":
            if not can_edit_studio(user):
                return self._forbid()
            return self._json(api_create_studio_expense(user, b), 201)
        if len(seg) == 4 and seg[1] == "studio" and seg[3] == "pay":
            if not can_edit_studio(user):
                return self._forbid()
            bid = self._int(seg[2])
            res = api_studio_pay(user, bid, b) if bid else None
            return self._json(res) if res else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 4 and seg[1] == "studio" and seg[3] == "cancel":
            if not can_edit_studio(user):
                return self._forbid()
            bid = self._int(seg[2])
            res = api_cancel_studio_booking(user, bid) if bid else None
            return self._json(res) if res else self._json({"error": "Topilmadi"}, 404)
        if path == "/api/shoots":
            if r not in APPROVER_ROLES:
                return self._forbid()
            return self._json(api_create_shoot(user, b), 201)
        if len(seg) == 4 and seg[1] == "shoots" and seg[3] == "cancel":
            if r not in APPROVER_ROLES:
                return self._forbid()
            sid = self._int(seg[2])
            res = api_cancel_shoot(user, sid) if sid else None
            return self._json(res) if res else self._json({"error": "Topilmadi"}, 404)
        if path == "/api/scenarist":
            if not is_scenarist(user):
                return self._forbid()
            return self._json(api_create_scenarist_script(user, b), 201)
        if path == "/api/settings/usd-rate":
            if r != "ceo":
                return self._forbid()
            return self._json(api_set_usd_rate(user, b))
        if path == "/api/daily/close":
            if not is_daily_user(user):
                return self._forbid()
            return self._json(api_close_day(user))
        if path == "/api/attendance/checkin":
            if not is_attend_user(user):
                return self._forbid()
            return self._json(api_checkin(user))
        if path == "/api/charity":
            if r != "ceo":
                return self._forbid()
            return self._json(api_charity_add(user, b))
        if path == "/api/telegram/setup-webhook":
            if r != "ceo":
                return self._forbid()
            return self._json(api_setup_webhook(user))
        if path == "/api/attendance/clear":
            if r != "ceo":
                return self._forbid()
            return self._json(api_clear_attendance(user, b))
        if len(seg) == 4 and seg[1] == "scenarist" and seg[3] == "cancel":
            if not is_scenarist(user):
                return self._forbid()
            sid = self._int(seg[2])
            res = api_cancel_scenarist_script(user, sid) if sid else None
            return self._json(res) if res else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 4 and seg[1] == "scripts" and seg[3] == "action":
            sid = self._int(seg[2])
            res = api_script_action(user, sid, b) if sid else None
            return self._json(res) if res else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 4 and seg[1] == "videos" and seg[3] == "action":
            vid = self._int(seg[2])
            res = api_video_action(user, vid, b) if vid else None
            return self._json(res) if res else self._json({"error": "Topilmadi"}, 404)
        return self._json({"error": "Topilmadi"}, 404)

    def do_PUT(self):
        path = urlparse(self.path).path
        user = self._auth()
        if not user:
            return self._json({"error": "Avtorizatsiya kerak"}, 401)
        b = self._body()
        seg = [s for s in path.split("/") if s]
        if len(seg) == 3 and seg[1] == "projects":
            pid = self._int(seg[2])
            if pid is None:
                return self._json({"error": "Topilmadi"}, 404)
            b["_actor"] = user["name"]
            row = api_update_project(pid, b)
            return self._json(row) if row else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 3 and seg[1] == "scripts":
            sid = self._int(seg[2])
            if sid is None:
                return self._json({"error": "Topilmadi"}, 404)
            row = api_update_script(user, sid, b)
            return self._json(row) if row else self._json({"error": "Topilmadi"}, 404)
        return self._json({"error": "Topilmadi"}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        user = self._auth()
        if not user:
            return self._json({"error": "Avtorizatsiya kerak"}, 401)
        seg = [s for s in path.split("/") if s]
        r = user["role"]
        if len(seg) == 3 and seg[1] == "projects":
            if r not in APPROVER_ROLES:
                return self._forbid()
            pid = self._int(seg[2])
            return self._json(api_delete_project(pid)) if pid else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 3 and seg[1] == "videos":
            vid = self._int(seg[2])
            return self._json(api_delete_video(user, vid)) if vid else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 4 and seg[1] == "studio" and seg[2] == "expenses":
            if not can_edit_studio(user):
                return self._forbid()
            eid = self._int(seg[3])
            return self._json(api_delete_studio_expense(user, eid)) if eid else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 3 and seg[1] == "studio":
            if not can_edit_studio(user):
                return self._forbid()
            bid = self._int(seg[2])
            return self._json(api_delete_studio_booking(user, bid)) if bid else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 3 and seg[1] == "shoots":
            if r not in APPROVER_ROLES:
                return self._forbid()
            sid = self._int(seg[2])
            return self._json(api_delete_shoot(user, sid)) if sid else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 3 and seg[1] == "scenarist":
            if not is_scenarist(user):
                return self._forbid()
            sid = self._int(seg[2])
            return self._json(api_delete_scenarist_script(user, sid)) if sid else self._json({"error": "Topilmadi"}, 404)
        return self._json({"error": "Topilmadi"}, 404)

    def log_message(self, *args):
        pass  # konsolni toza ushlab turamiz


def local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    init_db()
    print("\n  ✅ Kadr Media Dashboard ishga tushdi")
    print(f"  \U0001F310 Shu kompyuterda:  http://localhost:{PORT}")
    print(f"  \U0001F4F1 Telefonda (bir Wi-Fi):  http://{local_ip()}:{PORT}")
    print("  (To'xtatish uchun: Control + C)\n")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

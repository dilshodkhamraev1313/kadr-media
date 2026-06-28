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
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DB_PATH = os.path.join(BASE_DIR, "kadr-media.db")
PORT = int(os.environ.get("PORT", 3000))

# --- Avtomatik montaj dvigateli (autoedit paketi) ---
# Agar paket yoki ffmpeg yo'q bo'lsa ham, asosiy dashboard ishlayveradi.
MONTAJ_DIR = os.path.join(BASE_DIR, "montaj_out")
MONTAJ_OK = False
MONTAJ_IMPORT_ERROR = ""
try:
    from autoedit.jobs import JobManager
    from autoedit.styles import list_styles as montaj_list_styles
    from autoedit.ffmpeg_utils import tools_status as montaj_tools
    from autoedit.web import parse_multipart, save_uploads, MAX_UPLOAD
    MONTAJ = JobManager(MONTAJ_DIR)
    MONTAJ_OK = True
except Exception as _e:  # noqa: BLE001
    MONTAJ = None
    MONTAJ_IMPORT_ERROR = str(_e)

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

# Video darajalari va narxlari (so'm). Rahbar daraja tanlaydi, tizim avtomatik hisoblaydi.
TIERS = {
    "oddiy":    {"label": "Oddiy Reels",    "price": 25000},
    "standart": {"label": "Standart Reels", "price": 35000},
    "premium":  {"label": "Premium Reels",  "price": 50000},
}

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

    # users jadvaliga login ustunlarini qo'shish (idempotent)
    add_column_if_missing(conn, "users", "username", "TEXT")
    add_column_if_missing(conn, "users", "salt", "TEXT")
    add_column_if_missing(conn, "users", "password_hash", "TEXT")
    add_column_if_missing(conn, "users", "client_name", "TEXT")
    # projects: oylik reja + har bosqich bo'yicha bajarilgan sanoq
    add_column_if_missing(conn, "projects", "plan", "INTEGER DEFAULT 0")
    for col in DONE_COLS:
        add_column_if_missing(conn, "projects", col, "INTEGER DEFAULT 0")
    # videos: ish jarayoni ustunlari
    for col in ("assigned_by", "qc_by", "qc_at", "posted_by", "posted_at"):
        add_column_if_missing(conn, "videos", col, "TEXT")
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
            plan,done_ssenariy,done_syomka,done_montaj,done_tasdiq,done_joylash)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    params = (
        b.get("name") or "Nomsiz loyiha", b.get("client") or "",
        b.get("responsible") or "", st(b.get("ssenariy")), st(b.get("syomka")),
        st(b.get("montaj")), st(b.get("tasdiq")), st(b.get("joylash")),
        b.get("deadline") or None, b.get("muammo") or "", b.get("izoh") or "",
        iv("plan"), iv("done_ssenariy"), iv("done_syomka"), iv("done_montaj"), iv("done_tasdiq"), iv("done_joylash"),
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
           plan=?,done_ssenariy=?,done_syomka=?,done_montaj=?,done_tasdiq=?,done_joylash=?,
           updated_at=CURRENT_TIMESTAMP WHERE id=?""",
        (
            merged["name"], merged["client"], merged["responsible"], merged["ssenariy"],
            merged["syomka"], merged["montaj"], merged["tasdiq"], merged["joylash"],
            merged["deadline"], merged["muammo"], merged["izoh"],
            merged["plan"], merged["done_ssenariy"], merged["done_syomka"],
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
VIDEO_STATUSES = ["biriktirildi", "montaj_qilindi", "sifat_ok", "qabul_qilindi", "joylandi", "qaytarildi"]
DONE_STATUSES = ("qabul_qilindi", "joylandi")  # pul hisoblanadigan holatlar
SMM_ROLES = ("smm", "ceo", "coordinator")


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
    conn.close()
    result = [dict(r) for r in rows]
    if role == "lead" and not show_all:
        names = lead_project_names(user["name"])
        result = [r for r in result if r.get("project") in names]
    return result


def api_qc(user):
    """Sifat nazorati uchun — montaj qilingan, tasdiq kutayotgan videolar (hammasi)."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM videos WHERE status='montaj_qilindi' ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def api_create_video(user, b):
    """Loyiha rahbari videoni montajchiga BIRIKTIRADI."""
    conn = get_db()
    editor = b.get("editor") or ""
    title = b.get("title") or "Nomsiz video"
    sql = """INSERT INTO videos (project_id, project, client, script_id, title, editor, vdate, drive_link, note, status, assigned_by)
             VALUES (?,?,?,?,?,?,?,?,?,?,?)"""
    params = (
        b.get("project_id"), b.get("project") or "", b.get("client") or "", b.get("script_id"),
        title, editor, b.get("vdate") or uz_today().isoformat(),
        b.get("drive_link") or "", b.get("note") or "", "biriktirildi", user["name"],
    )
    if IS_PG:
        vid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        vid = conn.execute(sql, params).lastrowid
    log_audit(conn, user["name"], "video biriktirdi", f"#{vid} {title} → {editor}")
    conn.commit()
    row = conn.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
    conn.close()
    send_telegram(f"🎬 <b>Yangi montaj biriktirildi</b>\n{title}\n👤 Montajchi: {editor}\n📁 {b.get('project') or '—'}\n👮 {user['name']}")
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
            "UPDATE videos SET status='montaj_qilindi', drive_link=?, note=? WHERE id=?",
            (b.get("drive_link") or ex["drive_link"], b.get("note") or ex["note"], vid),
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
        tier = b.get("tier") if b.get("tier") in TIERS else "standart"
        amount = TIERS[tier]["price"]
        conn.execute(
            "UPDATE videos SET status='qabul_qilindi', tier=?, amount=?, approved_by=?, approved_at=? WHERE id=?",
            (tier, amount, user["name"], now_local(), vid),
        )
        log_audit(conn, user["name"], "video qabul qildi", f"#{vid} {ex['title']} · {TIERS[tier]['label']} · {amount} so'm")
        log_audit(conn, "Tizim", "pul hisoblandi", f"#{vid} {ex['editor']} +{amount} so'm")
        send_telegram(
            f"✅ <b>Video QABUL QILINDI</b>\n{ex['title']}\n👤 {ex['editor']}\n"
            f"💰 {TIERS[tier]['label']} — {amount:,} so'm hisoblandi\n👮 Tasdiqladi: {user['name']}\n→ Joylashga".replace(",", " ")
        )
    elif action == "return" and role in APPROVER_ROLES:
        conn.execute(
            "UPDATE videos SET status='qaytarildi', approved_by=?, approved_at=?, note=? WHERE id=?",
            (user["name"], now_local(), b.get("note") or ex["note"], vid),
        )
        log_audit(conn, user["name"], "video qaytardi", f"#{vid} {ex['title']}")
        send_telegram(f"↩️ <b>Video qaytarildi</b>\n{ex['title']}\n👤 {ex['editor']}\n👮 {user['name']}")
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
    return {
        "name": name,
        "videos": len(vids),
        "accepted": len(accepted),
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
    editors = conn.execute("SELECT name, color, title FROM users WHERE role='editor' ORDER BY name").fetchall()
    result = []
    for e in editors:
        s = editor_summary(conn, e["name"])
        s["color"] = e["color"]
        s["title"] = e["title"]
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
    }


def api_tiers():
    return TIERS


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

    def _montaj_create(self, user):
        """Multipart fayl yuklash → yangi montaj vazifasi yaratish."""
        if not MONTAJ_OK:
            return self._json({"error": "Montaj moduli yuklanmadi",
                               "detail": MONTAJ_IMPORT_ERROR}, 500)
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            return self._json({"error": "multipart/form-data kerak"}, 400)
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return self._json({"error": "Bo'sh so'rov"}, 400)
        if length > MAX_UPLOAD:
            return self._json({"error": "Fayl(lar) juda katta (max 800MB)"}, 413)
        body = self.rfile.read(length)
        try:
            parsed = parse_multipart(body, ctype)
        except ValueError as e:
            return self._json({"error": str(e)}, 400)

        upload_dir = os.path.join(MONTAJ_DIR, "upload_" + secrets.token_hex(4))
        saved = save_uploads(parsed["files"], upload_dir)
        if not saved["videos"]:
            return self._json({"error": "Kamida bitta video yuklang"}, 400)

        fields = parsed["fields"]
        job = MONTAJ.create(
            inputs=saved["videos"],
            style_name=fields.get("style"),
            reference=saved["reference"],
            music=saved["music"],
            language=fields.get("language", "uz"),
            title=fields.get("title") or ("Montaj — " + user["name"]),
        )
        return self._json(job, 201)

    def _montaj_download(self, job_id):
        """Tayyor videoni jo'natadi."""
        if not MONTAJ_OK:
            return self._json({"error": "Montaj moduli yuklanmadi"}, 500)
        path = MONTAJ.output_path(job_id)
        if not path:
            return self._json({"error": "Tayyor emas yoki topilmadi"}, 404)
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Disposition",
                         f'attachment; filename="kadr-montaj-{job_id}.mp4"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        # --- Ochiq (auth shart emas) ---
        if path == "/api/tiers":
            return self._json(api_tiers())
        if path == "/api/telegram/test":
            return self._json(api_telegram_test())
        if path == "/api/telegram/digest":
            return self._json(api_telegram_digest())
        # Tayyor videoni yuklab olish — brauzer havolasi orqali (token sarlavhasiz),
        # job_id tasodifiy va taxmin qilib bo'lmaydi.
        if path.startswith("/api/montaj/jobs/") and path.endswith("/download"):
            jid = path[len("/api/montaj/jobs/"):-len("/download")]
            return self._montaj_download(jid)
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
            return self._forbid() if role not in ADMIN_ROLES else self._json(api_finance())
        # --- Avtomatik montaj ---
        if path == "/api/montaj/styles":
            if not MONTAJ_OK:
                return self._json({"error": "Montaj moduli yuklanmadi",
                                   "detail": MONTAJ_IMPORT_ERROR}, 500)
            return self._json({"styles": montaj_list_styles(), "tools": montaj_tools()})
        if len(seg) == 4 and seg[1] == "montaj" and seg[2] == "jobs":
            if not MONTAJ_OK:
                return self._json({"error": "Montaj moduli yuklanmadi"}, 500)
            j = MONTAJ.public(seg[3])
            return self._json(j) if j else self._json({"error": "Topilmadi"}, 404)
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

        user = self._auth()
        if not user:
            return self._json({"error": "Avtorizatsiya kerak"}, 401)
        # Montaj vazifasi — multipart fayl yuklash (JSON body'dan oldin o'qiymiz)
        if path == "/api/montaj/jobs":
            return self._montaj_create(user)
        b = self._body()
        seg = [s for s in path.split("/") if s]
        r = user["role"]

        if path == "/api/logout":
            return self._json(api_logout(self.headers.get("X-Token", "")))
        if path == "/api/change-password":
            return self._json(api_change_password(user, b))
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

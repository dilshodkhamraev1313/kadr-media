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
SHOOT_TYPES = {"reels": "Reels", "podcast": "Podcast", "youtube": "YouTube video", "vebinar": "Vebinar", "kadr_media": "Kadr Media (ichki)"}
OPERATOR_PAY = {"reels": 50000, "podcast": 100000, "youtube": 50000, "vebinar": 200000, "kadr_media": 50000}
# Kadr Media (ichki syomka) — studio TUSHUMIga pul hisoblanmaydi (faqat xona/vaqt band + operator puli)
STUDIO_NO_INCOME_TYPES = ("kadr_media",)
STUDIO_OPERATORS = ("Said", "Umid")

# Kelib tushgan pullar shaffofligi — kim qabul qildi + qanday usul.
INCOME_RECEIVERS = ("Dilshod Khamraev", "Gulmira")
INCOME_METHODS = ("naqt", "plastik")
METHOD_LABEL = {"naqt": "Naqt", "plastik": "Plastik"}

# Ssenaristlar va har tasdiqlangan ssenariy uchun haq (so'm).
# Ssenarist o'z kabinetidan tasdiqlangan ssenariyni kiritadi — pul avtomatik hisoblanadi.
SCENARIST_PAY = {"Xonzoda": 100000, "Umida": 50000}

# Umida SMM qiladigan loyihalar. SMM to'liq daromadi shu loyihalar bajarilishiga bog'liq
# (hammasi bajarilsa — to'liq; qismi bajarilsa — foizi). Umida oy davomida belgilaydi.
SMM_PROJECTS = ["Namuna mebel", "Nodirbek arab tili", "Kadr studio"]

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

# Kun yopish cheklisti — har kishi uchun tayyor vazifalar (loyihalarigacha).
# Dashboardda tahrirlanadi; bular faqat boshlang'ich (seed) qiymatlar.
DEFAULT_CHECKLIST = {
    "Said": [
        "Namuna Mebel — syomka/loyiha nazorati",
        "Nodirbek (arab tili) — loyiha nazorati",
        "Sifat nazorati — montaj videolarni tekshirdim",
        "Bugungi syomkalar bajarildi",
    ],
    "Gulmira": [
        "Kadr Studio operatsion boshqaruv",
        "Bugungi studio bronlar nazorati",
        "1 reels tayyorlandi",
        "5 stories joylandi",
        "Umida-targetolog loyihasi nazorati",
    ],
    "Xonzoda": [
        "Kunlik koordinatsiya hisoboti (barcha loyihalar holati)",
        "Amarkets — ssenariy/nazorat",
        "Fidda kumush — ssenariy/nazorat",
        "Bugungi ssenariylar yozildi",
    ],
    "Umida": [
        "Stories joylandi",
        "SMM: persona / caption / oblojka / opisaniya",
        "Videolar Instagram'ga joylandi",
        "Ssenarist yordami (Xonzodaga)",
    ],
}

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
    "Shodiya": ["Estetik Korreya Mastura"],
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
    "Umida": {"title": "SMM + ssenarist + montajchi", "som": {"Intizom": 500000},
              "usd": {"Stories": 100, "SMM": 100}, "scenarist": True, "montaj": True,
              "close_link": ["Stories", "SMM"]},
    "Sardor": {"title": "Montajchi", "som": {"Fiksa": 500000, "Intizom": 500000}, "montaj": True},
    "Umid": {"title": "Montajchi + operator", "som": {"Fiksa": 500000, "Intizom": 500000},
             "montaj": True, "operator": True},
    "Shodiya": {"title": "Loyiha rahbari + montajchi", "som": {"Fiksa": 500000, "Intizom": 500000},
                "lead": True, "montaj": True},
}

# Rol='lead' bo'lsa ham montaj qiladigan rahbarlar (Shodiya): montajchi ro'yxatiga
# (video biriktirish, reyting, Bugun, pay) SALARY montaj+lead bayrog'i orqali qo'shiladi.
MONTAJ_LEADS = tuple(n for n, c in SALARY.items() if c.get("montaj") and c.get("lead"))


def is_montajchi_name(name, role=None):
    """Montajchi (video biriktiriladigan): role='editor' yoki montaj qiluvchi rahbar."""
    return role == "editor" or name in MONTAJ_LEADS


def _montajchi_where():
    """users jadvalidan montajchilarni tanlash uchun WHERE (role='editor' + montaj-rahbarlar)."""
    if MONTAJ_LEADS:
        ph = ",".join(["?"] * len(MONTAJ_LEADS))
        return "(role='editor' OR name IN (%s))" % ph, list(MONTAJ_LEADS)
    return "role='editor'", []

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
# Oygul Elite lavozimidan boshlanib hisoblanadi (2 lavozim = 2×RANK_STEP qabul).
EDITOR_RANK_BASE = {"Oygul": 2 * RANK_STEP}


def eff_count(name, accepted):
    """Lavozim hisobida ishlatiladigan samarali qabul soni (bazaviy bonus bilan)."""
    return int(accepted or 0) + EDITOR_RANK_BASE.get(name, 0)


# Montaj deadline (biriktirilgandan qabulgacha). Kechiksa: reels — pul yo'q, podcast/youtube — yarim.
DEADLINE_HOURS = {"reels": 24, "podcast": 48, "youtube": 48}
REELS_PER_DAY = 3  # montajchiga kuniga nechta reels deadline (24 soatlik) qo'yiladi


def _parse_dt(s):
    try:
        return datetime.datetime.strptime((s or "")[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _norm_due(s):
    """Qo'lda kiritilgan muddatni 'YYYY-MM-DD HH:MM:SS' ko'rinishiga keltiradi.
    Faqat sana berilsa — o'sha kun oxiri (23:59). Bo'sh bo'lsa None."""
    s = (s or "").strip().replace("T", " ")
    if not s:
        return None
    s = s[:19]
    if len(s) <= 10:
        return s[:10] + " 23:59:00"
    if len(s) == 16:  # YYYY-MM-DD HH:MM
        return s + ":00"
    return s


def _video_deadline_dt(v):
    """Videoning deadline datetime'i: rejalashtirilgan due_at bo'lsa o'sha,
    aks holda assigned_at + tur bo'yicha soat."""
    due = _parse_dt(v.get("due_at"))
    if due:
        return due
    vt = v.get("vtype") if v.get("vtype") in DEADLINE_HOURS else "reels"
    a = _parse_dt(v.get("assigned_at") or v.get("created_at"))
    return (a + datetime.timedelta(hours=DEADLINE_HOURS.get(vt, 24))) if a else None


def _next_reel_slot(conn, editor, assign_date):
    """Montajchiga yangi reels uchun keyingi bo'sh kun-slot deadline'i.
    Kuniga REELS_PER_DAY ta, ertadan boshlab, yakshanba o'tkaziladi;
    montajchining hozir turgan (bajarilmagan) reelslari ham hisobga olinadi."""
    day_counts = {}
    for r in conn.execute(
        "SELECT assigned_at, due_at, vtype, created_at FROM videos "
        "WHERE editor=? AND vtype='reels' AND status IN ('biriktirildi','qaytarildi')",
        (editor,)).fetchall():
        dl = _video_deadline_dt(dict(r))
        if dl:
            day_counts[dl.date()] = day_counts.get(dl.date(), 0) + 1
    day = assign_date + datetime.timedelta(days=1)  # ertadan boshlaymiz (24 soat)
    for _ in range(180):
        if day.weekday() == 6:  # yakshanba — dam kuni, o'tkazamiz
            day += datetime.timedelta(days=1)
            continue
        if day_counts.get(day, 0) < REELS_PER_DAY:
            break
        day += datetime.timedelta(days=1)
    return datetime.datetime(day.year, day.month, day.day, 23, 59, 59)


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
# Sifat nazorati — videoni tasdiqlash/qabul qilish FAQAT Said (+ CEO zaxira).
# Loyiha rahbarlari videoni faqat biriktiradi, tasdiqlay olmaydi.
QC_APPROVER = "Said"


def is_qc_approver(user):
    return bool(user) and (user["name"] == QC_APPROVER or user["role"] == "ceo")

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
    ("Shodiya",          "shodiya", "shod2026", "lead",        "Loyiha rahbari + montajchi", "#32D74B", None),
    # SMM menejer (faqat joylash)
    ("Aisha",            "aisha",   "aisha2026","smm",         "SMM menejer · Joylash",   "#FF2D55", None),
    # Jarvis (AI yordamchi, Kadr Jarvis OS loyihasi) — coordinator darajasi: operatsion
    # ma'lumotlarni (loyiha/vazifa/montaj/oy statistikasi) o'qiy oladi, lekin moliya/
    # payroll (role=="ceo"ga qat'iy bog'langan) KO'RMAYDI — ovoz-biometrika xavfsizlik
    # qatlami (Kadr Jarvis OS Phase 9) qo'shilmaguncha ataylab shunday cheklangan.
    ("Jarvis",           "jarvis",  "BRcIaecCe01qqr1vkcnZ", "coordinator", "AI Yordamchi", "#5AC8FA", None),
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
    conn.execute("""CREATE TABLE IF NOT EXISTS budgets (
        category TEXT PRIMARY KEY, monthly INTEGER DEFAULT 0, responsible TEXT DEFAULT '')""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS daily_close (
        id {pk}, person TEXT, cdate TEXT, closed_at TEXT)""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS charity_ledger (
        id {pk}, kind TEXT, amount INTEGER DEFAULT 0, note TEXT DEFAULT '',
        cdate TEXT, created_by TEXT, created_at {ts})""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS attendance (
        id {pk}, person TEXT, adate TEXT, checkin_time TEXT,
        on_time INTEGER DEFAULT 0, source TEXT DEFAULT 'bot', created_at {ts})""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS smm_done (
        id {pk}, person TEXT, project TEXT, ym TEXT)""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS client_payments (
        id {pk}, project TEXT, ym TEXT, amount INTEGER DEFAULT 0,
        pdate TEXT, note TEXT DEFAULT '', created_by TEXT, created_at {ts})""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS checklist_items (
        id {pk}, person TEXT, text TEXT, sort INTEGER DEFAULT 0, active INTEGER DEFAULT 1)""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS checklist_done (
        id {pk}, person TEXT, cdate TEXT, item_id INTEGER)""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS assigned_tasks (
        id {pk}, assignee TEXT, text TEXT, tdate TEXT, done INTEGER DEFAULT 0,
        note TEXT DEFAULT '', done_at TEXT DEFAULT '', assigned_by TEXT, created_at {ts})""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS monthly_archive (
        ym TEXT PRIMARY KEY, data TEXT, net INTEGER DEFAULT 0,
        created_by TEXT, created_at {ts})""")
    conn.execute(f"""CREATE TABLE IF NOT EXISTS income_ledger (
        id {pk}, source_type TEXT, source_id INTEGER, source_label TEXT, amount INTEGER DEFAULT 0,
        received_by TEXT, method TEXT, pdate TEXT, note TEXT DEFAULT '', created_by TEXT, created_at {ts})""")

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
    add_column_if_missing(conn, "videos", "deadline_reminded", "INTEGER DEFAULT 0")
    # videos: deadline uchun biriktirilgan vaqt (Toshkent) va kechikish belgisi
    add_column_if_missing(conn, "videos", "assigned_at", "TEXT")
    add_column_if_missing(conn, "videos", "is_late", "INTEGER DEFAULT 0")
    # reels deadline avtomatik taqsimoti uchun rejalashtirilgan muddat (Toshkent)
    add_column_if_missing(conn, "videos", "due_at", "TEXT")
    # studio_bookings: operator, syomka turi, operator puli, avans, holat
    add_column_if_missing(conn, "studio_bookings", "operator", "TEXT DEFAULT ''")
    add_column_if_missing(conn, "studio_bookings", "shoot_type", "TEXT DEFAULT 'reels'")
    add_column_if_missing(conn, "studio_bookings", "operator_pay", "INTEGER DEFAULT 0")
    add_column_if_missing(conn, "studio_bookings", "paid_amount", "INTEGER DEFAULT 0")
    add_column_if_missing(conn, "studio_bookings", "status", "TEXT DEFAULT 'active'")
    # shoots (Kadr Media syomkalari): syomka vaqti (nechidan nechigacha)
    add_column_if_missing(conn, "shoots", "start_time", "TEXT DEFAULT ''")
    add_column_if_missing(conn, "shoots", "end_time", "TEXT DEFAULT ''")
    # xarajatlar: qayerdan pul chiqdi — usul (naqt/plastik) + kim to'ladi (Dilshod/Gulmira)
    add_column_if_missing(conn, "studio_expenses", "method", "TEXT DEFAULT 'naqt'")
    add_column_if_missing(conn, "studio_expenses", "paid_by", "TEXT DEFAULT ''")
    # jamoa maosh to'lovlari: qaysi hisobdan (Dilshod/Gulmira) + usul (naqt/plastik)
    add_column_if_missing(conn, "payments", "paid_from", "TEXT DEFAULT ''")
    add_column_if_missing(conn, "payments", "method", "TEXT DEFAULT 'naqt'")
    # checklist_done: belgi (done) + qo'lda izoh (note — masalan nechta ssenariy)
    add_column_if_missing(conn, "checklist_done", "done", "INTEGER DEFAULT 1")
    add_column_if_missing(conn, "checklist_done", "note", "TEXT DEFAULT ''")
    # projects: mijoz o'zi joylaydigan loyihalar (joylash bosqichi yo'q)
    add_column_if_missing(conn, "projects", "self_post", "INTEGER DEFAULT 0")
    _seed_checklist(conn)
    _backfill_studio_ledger(conn)
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
    self_post = bool(p.get("self_post"))
    p["selfPost"] = self_post
    # Mijoz o'zi joylaydigan loyihalarda "joylash" bosqichi hisobga olinmaydi
    stages = [s for s in STAGES if not (self_post and s == "joylash")]
    done = sum(1 for s in stages if p.get(s) == "tayyor")
    p["doneCount"] = done
    p["stageCount"] = len(stages)
    p["progress"] = round(done / len(stages) * 100) if stages else 0
    p["fullyDone"] = done == len(stages)

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

    # Oylik reja progressi (har bosqich uchun plan dona) — selfPost'da joylash yo'q
    plan = p.get("plan") or 0
    done_cols = [c for c in DONE_COLS if not (self_post and c == "done_joylash")]
    done_total = sum(p.get(c) or 0 for c in done_cols)
    p["planTotal"] = plan * len(done_cols)
    p["planDone"] = done_total
    p["planPct"] = round(done_total / (plan * len(done_cols)) * 100) if plan and done_cols else 0
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


def api_reset_project_stats(user):
    """CEO — yangi oy uchun barcha loyihalar statistikasini nolga tushiradi:
    har bosqich soni (done_) = 0 va bosqich holati = kutilmoqda. Yozuvlar o'chmaydi."""
    if user["role"] != "ceo":
        return {"error": "Ruxsat yo'q"}, 403
    conn = get_db()
    sets = ", ".join([f"{c}=0" for c in DONE_COLS] + [f"{s}='kutilmoqda'" for s in STAGES])
    conn.execute(f"UPDATE projects SET {sets}, updated_at=CURRENT_TIMESTAMP")
    n = conn.execute("SELECT COUNT(*) AS n FROM projects").fetchone()["n"]
    log_audit(conn, user["name"], "loyiha statistikasi reset qilindi", f"{n} loyiha · {uz_today().isoformat()}")
    conn.commit()
    conn.close()
    return {"ok": True, "count": n}


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
            plan,monthly_fee,done_ssenariy,done_syomka,done_montaj,done_tasdiq,done_joylash,self_post)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    params = (
        b.get("name") or "Nomsiz loyiha", b.get("client") or "",
        b.get("responsible") or "", st(b.get("ssenariy")), st(b.get("syomka")),
        st(b.get("montaj")), st(b.get("tasdiq")), st(b.get("joylash")),
        b.get("deadline") or None, b.get("muammo") or "", b.get("izoh") or "",
        iv("plan"), iv("monthly_fee"), iv("done_ssenariy"), iv("done_syomka"), iv("done_montaj"), iv("done_tasdiq"), iv("done_joylash"),
        1 if b.get("self_post") else 0,
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
        "self_post": (1 if b.get("self_post") else 0) if "self_post" in b else (existing.get("self_post") or 0),
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
           self_post=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
        (
            merged["name"], merged["client"], merged["responsible"], merged["ssenariy"],
            merged["syomka"], merged["montaj"], merged["tasdiq"], merged["joylash"],
            merged["deadline"], merged["muammo"], merged["izoh"],
            merged["plan"], merged["monthly_fee"], merged["done_ssenariy"], merged["done_syomka"],
            merged["done_montaj"], merged["done_tasdiq"], merged["done_joylash"], merged["self_post"], pid,
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
def _is_budget_user(name):
    """Foydalanuvchi biror budjet kategoriyasiga mas'ul qilib biriktirilganmi."""
    conn = get_db()
    row = conn.execute("SELECT 1 FROM budgets WHERE responsible=? LIMIT 1", (name,)).fetchone()
    conn.close()
    return bool(row)


def public_user(u):
    if not u:
        return None
    d = dict(u)
    d.pop("salt", None)
    d.pop("password_hash", None)
    d["hasPassword"] = True
    d["budgetUser"] = _is_budget_user(d.get("name"))
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
    """Har montajyor uchun qabul qilingan video soni (haqiqiy dona — ko'rsatish uchun)."""
    counts = {}
    for r in conn.execute(
        "SELECT editor, COUNT(*) AS n FROM videos WHERE status IN ('qabul_qilindi','joylandi') GROUP BY editor"
    ).fetchall():
        counts[r["editor"] or ""] = r["n"]
    return counts


# Podcast ko'p vaqt oladi — lavozim (rank) uchun 1 podcast = PODCAST_RANK_WEIGHT video.
PODCAST_RANK_WEIGHT = 3


def _video_rank_points(v):
    """Bitta videoning lavozimga qo'shadigan ball: podcast — 3, boshqasi — 1."""
    return PODCAST_RANK_WEIGHT if (v.get("vtype") == "podcast") else 1


def _editor_rank_points(conn):
    """Har montajyor uchun lavozim ballari (podcast=3). rank_info shu ballardan hisoblanadi."""
    pts = {}
    for r in conn.execute(
        "SELECT editor, SUM(CASE WHEN vtype='podcast' THEN %d ELSE 1 END) AS n "
        "FROM videos WHERE status IN ('qabul_qilindi','joylandi') GROUP BY editor" % PODCAST_RANK_WEIGHT
    ).fetchall():
        pts[r["editor"] or ""] = r["n"] or 0
    return pts


def _self_post_names(conn):
    """Mijoz o'zi joylaydigan loyihalar nomlari (joylash bosqichi yo'q)."""
    return {r["name"] for r in conn.execute(
        "SELECT name FROM projects WHERE self_post=1").fetchall()}


def decorate_video(d, counts, role, username, self_post_names=None):
    """Videoga montajyor lavozimini qo'shadi va pulni faqat CEO/o'z montajyoriga ko'rsatadi."""
    if self_post_names is not None:
        d["self_post"] = d.get("project") in self_post_names
    ed = d.get("editor") or ""
    cnt = eff_count(ed, counts.get(ed, 0))
    info = rank_info(cnt)
    d["editor_rank"] = info["rank_key"]
    d["editor_rank_label"] = info["rank_label"]
    d["editor_rank_icon"] = info["rank_icon"]
    own = (ed == username and is_montajchi_name(username, role))
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
    if (d.get("assigned_at") or d.get("due_at")) and d.get("status") in ("biriktirildi", "montaj_qilindi", "sifat_ok", "qaytarildi"):
        deadline = _video_deadline_dt(d)
        if deadline:
            now = uz_now().replace(tzinfo=None)
            d["deadline_at"] = deadline.strftime("%Y-%m-%d %H:%M")
            d["overdue"] = now > deadline
            d["hours_left"] = round((deadline - now).total_seconds() / 3600, 1)
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
    counts = _editor_rank_points(conn)
    sp = _self_post_names(conn)
    conn.close()
    result = [decorate_video(dict(r), counts, role, user["name"], sp) for r in rows]
    # SMM (joylash) — mijoz o'zi joylaydigan loyihalarni ko'rsatmaymiz
    if role == "smm":
        result = [r for r in result if not r.get("self_post")]
    if role == "lead" and not show_all:
        names = lead_project_names(user["name"])
        result = [r for r in result if r.get("project") in names]
    return result


def api_my_tasks(user):
    """Foydalanuvchining bugungi vazifalari — rolga qarab (montaj, sifat, qabul, joylash, syomka)."""
    conn = get_db()
    role = user["role"]
    name = user["name"]
    counts = _editor_rank_points(conn)
    sp = _self_post_names(conn)

    def dec(rows):
        return [decorate_video(dict(r), counts, role, name, sp) for r in rows]

    tasks = {}
    # Montaj qilish kerak (montajchi) — muddat bilan
    if is_montajchi_name(name, role):
        tasks["montaj"] = dec(conn.execute(
            "SELECT * FROM videos WHERE editor=? AND status IN ('biriktirildi','qaytarildi') ORDER BY id DESC",
            (name,)).fetchall())
    # Sifat nazorati + qabul — FAQAT Said (+ CEO). Loyiha rahbarlari tasdiqlamaydi.
    if is_qc_approver(user):
        tasks["qc"] = dec(conn.execute(
            "SELECT * FROM videos WHERE status='montaj_qilindi' ORDER BY id DESC").fetchall())
        tasks["accept"] = dec(conn.execute(
            "SELECT * FROM videos WHERE status='sifat_ok' ORDER BY id DESC").fetchall())
    # Joylash (SMM / CEO / koordinator) — mijoz o'zi joylaydiganlar bundan mustasno
    if role in SMM_ROLES:
        tasks["post"] = [v for v in dec(conn.execute(
            "SELECT * FROM videos WHERE status='qabul_qilindi' ORDER BY id DESC").fetchall())
            if not v.get("self_post")]
    # Bugungi syomkalar (operator)
    today = uz_today().isoformat()
    if name in STUDIO_OPERATORS:
        b = [dict(r) for r in conn.execute(
            "SELECT * FROM studio_bookings WHERE operator=? AND bdate=? AND (status IS NULL OR status<>'bekor_qilindi') ORDER BY start_time",
            (name, today)).fetchall()]
        s = [dict(r) for r in conn.execute(
            "SELECT * FROM shoots WHERE operator=? AND sdate=? AND (status IS NULL OR status<>'bekor_qilindi')",
            (name, today)).fetchall()]
        tasks["shoots"] = b + s
    conn.close()
    total = sum(len(v) for v in tasks.values())
    return {"tasks": tasks, "total": total, "name": name}


def api_qc(user):
    """Sifat nazorati uchun — montaj qilingan, tasdiq kutayotgan videolar (hammasi)."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM videos WHERE status='montaj_qilindi' ORDER BY id DESC").fetchall()
    counts = _editor_rank_points(conn)
    conn.close()
    return [decorate_video(dict(r), counts, user["role"], user["name"]) for r in rows]


def api_create_video(user, b):
    """Loyiha rahbari videoni montajchiga BIRIKTIRADI."""
    conn = get_db()
    editor = b.get("editor") or ""
    title = b.get("title") or "Nomsiz video"
    vtype = b.get("vtype") if b.get("vtype") in VIDEO_TYPES else "reels"
    # Muddat: qo'lda kiritilsa — o'sha (override). Aks holda:
    #  Reels — avtomatik taqsimlanadi (kuniga 3 ta, yakshanba o'tkaziladi).
    #  Boshqa turlar (podcast/youtube) — assigned_at + soat bo'yicha (due_at bo'sh).
    # Muddatni qo'lda belgilash — FAQAT CEO. Boshqalar uchun avtomatik (avvalgidek).
    manual_due = _norm_due(b.get("due_at")) if user["role"] == "ceo" else None
    due_at = None
    if manual_due:
        due_at = manual_due
    elif vtype == "reels" and editor:
        due_at = _next_reel_slot(conn, editor, uz_today()).strftime("%Y-%m-%d %H:%M:%S")
    sql = """INSERT INTO videos (project_id, project, client, script_id, title, editor, vdate, drive_link, note, status, assigned_by, vtype, assigned_at, due_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    params = (
        b.get("project_id"), b.get("project") or "", b.get("client") or "", b.get("script_id"),
        title, editor, b.get("vdate") or uz_today().isoformat(),
        b.get("drive_link") or "", b.get("note") or "", "biriktirildi", user["name"], vtype, now_local(), due_at,
    )
    if IS_PG:
        vid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        vid = conn.execute(sql, params).lastrowid
    log_audit(conn, user["name"], "video biriktirdi", f"#{vid} {title} → {editor}")
    conn.commit()
    row = conn.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
    conn.close()
    dline = (" ".join(due_at.split(" ")[:1]) if due_at else "")
    send_telegram(f"🎬 <b>Yangi montaj biriktirildi</b>\n{title}\n🎞 Tur: {VIDEO_TYPES.get(vtype, vtype)}\n👤 Montajchi: {editor}\n📁 {b.get('project') or '—'}"
                  + (f"\n⏰ Muddat: {dline}" if dline else "")
                  + f"\n👮 {user['name']}")
    return dict(row)


def api_update_video(user, vid, b):
    """Biriktirilgan videoni tahrirlash (rahbar): montajchi, tur, muddat, nom, loyiha, izoh.
    Faqat hali montaj bosqichiga o'tmagan (biriktirildi/qaytarildi) videolar."""
    if user["role"] not in APPROVER_ROLES:
        return {"error": "Ruxsat yo'q"}, 403
    conn = get_db()
    ex = conn.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
    if not ex:
        conn.close()
        return None
    ex = dict(ex)
    if ex["status"] not in ("biriktirildi", "qaytarildi"):
        conn.close()
        return {"error": "Bu video allaqachon montaj bosqichida — tahrirlab bo'lmaydi"}, 400
    title = (b.get("title") or ex["title"]).strip() or ex["title"]
    editor = (b.get("editor") if b.get("editor") is not None else ex["editor"]) or ex["editor"]
    vtype = b.get("vtype") if b.get("vtype") in VIDEO_TYPES else (ex.get("vtype") or "reels")
    project = b.get("project", ex["project"])
    client = b.get("client", ex["client"])
    note = b.get("note", ex["note"])
    drive = b.get("drive_link", ex["drive_link"])
    vdate = b.get("vdate") or ex["vdate"]
    # Muddat: qo'lda kiritilsa — override (FAQAT CEO); aks holda mavjud due_at saqlanadi.
    manual_due = _norm_due(b.get("due_at")) if user["role"] == "ceo" else None
    due_at = manual_due if manual_due else ex.get("due_at")
    conn.execute(
        "UPDATE videos SET title=?, editor=?, vtype=?, project=?, client=?, note=?, drive_link=?, vdate=?, due_at=? WHERE id=?",
        (title, editor, vtype, project, client, note, drive, vdate, due_at, vid),
    )
    log_audit(conn, user["name"], "videoni tahrirladi", f"#{vid} {title} → {editor}")
    conn.commit()
    row = conn.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
    conn.close()
    dline = (" ".join(due_at.split(" ")[:1]) if due_at else "")
    send_telegram(f"✏️ <b>Video tahrirlandi</b>\n{title}\n🎞 {VIDEO_TYPES.get(vtype, vtype)}\n👤 Montajchi: {editor}"
                  + (f"\n⏰ Muddat: {dline}" if dline else "")
                  + f"\n👮 {user['name']}")
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
    elif action == "qc_ok" and is_qc_approver(user):
        conn.execute(
            "UPDATE videos SET status='sifat_ok', qc_by=?, qc_at=? WHERE id=?",
            (user["name"], now_local(), vid),
        )
        log_audit(conn, user["name"], "sifat tasdiqladi", f"#{vid} {ex['title']}")
        send_telegram(f"🔎 <b>Sifat nazorati o'tdi</b>\n{ex['title']}\n👮 {user['name']} → qabulga")
    elif action == "qc_return" and is_qc_approver(user):
        conn.execute(
            "UPDATE videos SET status='qaytarildi', qc_by=?, qc_at=?, note=? WHERE id=?",
            (user["name"], now_local(), b.get("note") or ex["note"], vid),
        )
        log_audit(conn, user["name"], "sifat qaytardi", f"#{vid} {ex['title']}")
        send_telegram(f"↩️ <b>Sifatdan qaytarildi</b>\n{ex['title']}\n👤 {ex['editor']}\n👮 {user['name']}")
    elif action == "accept" and is_qc_approver(user):
        # Montajyor lavozimiga (shu paytgacha to'plangan lavozim ballari — podcast=3) qarab pul avtomatik
        prev_points = conn.execute(
            "SELECT SUM(CASE WHEN vtype='podcast' THEN %d ELSE 1 END) AS n "
            "FROM videos WHERE editor=? AND status IN ('qabul_qilindi','joylandi')" % PODCAST_RANK_WEIGHT,
            (ex["editor"],),
        ).fetchone()["n"] or 0
        vt = ex.get("vtype") or "reels"
        amount, rk = editor_pay(eff_count(ex["editor"], prev_points), vt)
        rk_label = next((r["label"] for r in RANKS if r["key"] == rk), rk)
        now_s = now_local()
        # Deadline: kechiksa reels — pul yo'q, podcast/youtube — yarim.
        # Reelsda rejalashtirilgan due_at (3/kun taqsimot), aks holda assigned_at + soat.
        _dl = _video_deadline_dt(ex)
        _now_dt = _parse_dt(now_s)
        late = bool(_dl and _now_dt and _now_dt > _dl)
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
    elif action == "return" and is_qc_approver(user):
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
    if user["role"] not in ADMIN_ROLES:
        return {"error": "Ruxsat yo'q"}, 403
    conn = get_db()
    conn.execute("DELETE FROM videos WHERE id=?", (vid,))
    log_audit(conn, user["name"], "video o'chirdi", f"#{vid}")
    conn.commit()
    conn.close()
    return {"ok": True}


def api_recompute_editor(user, editor):
    """CEO — montajchining qabul qilingan videolari summasini JORIY lavozimi
    bo'yicha qayta hisoblaydi (kechikish holati saqlanadi). Lavozim o'zgargach ishlatiladi."""
    if user["role"] != "ceo":
        return {"error": "Ruxsat yo'q"}, 403
    conn = get_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM videos WHERE editor=? AND status IN ('qabul_qilindi','joylandi') "
        "ORDER BY approved_at, id", (editor,)).fetchall()]
    prev_points = 0
    changed = []
    for v in rows:
        vt = v.get("vtype") or "reels"
        amount, rk = editor_pay(eff_count(editor, prev_points), vt)
        if v.get("is_late"):
            amount = 0 if vt == "reels" else amount // 2
        if (v.get("amount") or 0) != amount or (v.get("tier") or "") != rk:
            conn.execute("UPDATE videos SET amount=?, tier=? WHERE id=?", (amount, rk, v["id"]))
            changed.append({"id": v["id"], "title": v.get("title"),
                            "old": v.get("amount") or 0, "new": amount, "rank": rk})
        prev_points += _video_rank_points(v)
    log_audit(conn, user["name"], "montaj summalari qayta hisoblandi", f"{editor}: {len(changed)} video")
    conn.commit()
    conn.close()
    return {"ok": True, "editor": editor, "changed": changed}


def api_set_video_project(user, b):
    """CEO/koordinator — videolarga loyiha (yoki mijoz nomi) biriktiradi."""
    if user["role"] not in ADMIN_ROLES:
        return {"error": "Ruxsat yo'q"}, 403
    ids = b.get("ids") or []
    project = (b.get("project") or "").strip()
    if not ids:
        return {"error": "ids kerak"}, 400
    conn = get_db()
    n = 0
    for vid in ids:
        try:
            vid = int(vid)
        except (ValueError, TypeError):
            continue
        conn.execute("UPDATE videos SET project=? WHERE id=?", (project, vid))
        n += 1
    log_audit(conn, user["name"], "video loyihasi biriktirildi", f"{n} video → {project or '—'}")
    conn.commit()
    conn.close()
    return {"ok": True, "updated": n, "project": project}


def api_backfill_videos(user, b):
    """CEO — hisoblanmay qolib ketgan montajlarni kiritadi: to'g'ridan-to'g'ri
    'qabul_qilindi' holatда, joriy lavozim bo'yicha pul bilan (Telegramsiz, kechikishsiz)."""
    if user["role"] != "ceo":
        return {"error": "Ruxsat yo'q"}, 403
    editor = (b.get("editor") or "").strip()
    items = b.get("videos") or []
    if not editor or not items:
        return {"error": "editor va videos kerak"}, 400
    conn = get_db()
    now_s = now_local()
    prev_points = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN vtype='podcast' THEN %d ELSE 1 END),0) AS n "
        "FROM videos WHERE editor=? AND status IN ('qabul_qilindi','joylandi')" % PODCAST_RANK_WEIGHT,
        (editor,)).fetchone()["n"] or 0
    created = []
    for it in items:
        title = (it.get("title") or "Nomsiz").strip()
        project = (it.get("project") or "").strip()
        vt = it.get("vtype") if it.get("vtype") in VIDEO_TYPES else "reels"
        amount, rk = editor_pay(eff_count(editor, prev_points), vt)
        sql = ("INSERT INTO videos (project, title, editor, vtype, status, amount, tier, approved_by, approved_at, is_late, vdate, assigned_by) "
               "VALUES (?,?,?,?,'qabul_qilindi',?,?,?,?,0,?,?)")
        params = (project, title, editor, vt, amount, rk, user["name"], now_s, uz_today().isoformat(), user["name"])
        if IS_PG:
            vid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
        else:
            vid = conn.execute(sql, params).lastrowid
        created.append({"id": vid, "title": title, "project": project, "amount": amount})
        prev_points += PODCAST_RANK_WEIGHT if vt == "podcast" else 1
    log_audit(conn, user["name"], "montaj backfill (hisoblanmagan)", f"{editor}: {len(created)} video")
    conn.commit()
    conn.close()
    return {"ok": True, "editor": editor, "created": created, "total": sum(c["amount"] for c in created)}


def _full_pay(v):
    """Videoning kechikishsiz (to'liq) haqi — saqlangan lavozim (tier) va turi bo'yicha."""
    vt = v.get("vtype") if v.get("vtype") in ("reels", "podcast", "youtube") else "reels"
    tier = v.get("tier") if v.get("tier") in RANK_PRICES else "junior"
    return RANK_PRICES.get(tier, RANK_PRICES["junior"]).get(vt, 0)


def api_late_videos(user):
    """CEO — deadline o'tib puli kamaygan/hisoblanmagan qabul qilingan videolar ro'yxati."""
    if user["role"] != "ceo":
        return {"error": "Ruxsat yo'q"}, 403
    conn = get_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM videos WHERE is_late=1 AND status IN ('qabul_qilindi','joylandi') "
        "ORDER BY approved_at DESC, id DESC").fetchall()]
    conn.close()
    return [{
        "id": v["id"], "title": v.get("title"), "editor": v.get("editor"),
        "project": v.get("project"), "vtype": v.get("vtype") or "reels",
        "amount": v.get("amount") or 0, "full": _full_pay(v),
        "rank": v.get("tier") or "junior", "approved_at": v.get("approved_at"),
    } for v in rows]


def api_restore_video_pay(user, vid):
    """CEO — kechikkan videoning to'liq pulini tiklaydi (is_late olib tashlanadi)."""
    if user["role"] != "ceo":
        return {"error": "Ruxsat yo'q"}, 403
    conn = get_db()
    row = conn.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
    if not row:
        conn.close()
        return {"error": "Topilmadi"}, 404
    v = dict(row)
    if v["status"] not in DONE_STATUSES:
        conn.close()
        return {"error": "Faqat qabul qilingan video"}, 400
    full = _full_pay(v)
    conn.execute("UPDATE videos SET amount=?, is_late=0 WHERE id=?", (full, vid))
    log_audit(conn, user["name"], "kechikkan video puli tiklandi",
              f"#{vid} {v.get('title')} · {v.get('editor')} → {full} so'm")
    conn.commit()
    conn.close()
    send_telegram(f"💰 <b>Kechikkan video puli tiklandi</b>\n{v.get('title')}\n👤 {v.get('editor')}\n"
                  f"{full:,} so'm hisoblandi\n👮 {user['name']}".replace(",", " "))
    return {"ok": True, "amount": full}


# ============================================================
#  MONTAJCHILAR KABINETI + STATISTIKA
# ============================================================
def editor_summary(conn, name):
    ym = uz_now().strftime("%Y-%m")
    vids = [dict(r) for r in conn.execute("SELECT * FROM videos WHERE editor=?", (name,)).fetchall()]
    accepted_all = [v for v in vids if v["status"] in DONE_STATUSES]
    # Daromad/to'lov — FAQAT shu oy (oylik birlik; qolgan = shu oy ishlagan − shu oy to'langan)
    accepted_m = [v for v in accepted_all if (v.get("approved_at") or "").startswith(ym)]
    montaj_earned = sum(v["amount"] or 0 for v in accepted_m)
    paid = _paid_to(conn, name, ym)
    # Salaried montajchi (SALARYda bor) uchun "ishlagan" = TO'LIQ oylik maosh
    # (fiksa+intizom+montaj+...), aks holda (sof piece-rate) faqat montaj puli.
    if name in SALARY:
        _sal = compute_salary(conn, name, get_usd_rate())
        earned = _sal["total"] if _sal else montaj_earned
    else:
        earned = montaj_earned
    by_project = {}
    for v in accepted_m:
        by_project[v["project"]] = by_project.get(v["project"], 0) + 1
    # Lavozim — butun kariyera ballari (podcast=3); "accepted" jami kariyera dona
    rank_points = sum(_video_rank_points(v) for v in accepted_all)
    rinfo = rank_info(eff_count(name, rank_points))
    return {
        "name": name,
        "videos": len(vids),
        "accepted": len(accepted_all),         # jami (kariyera) — lavozim uchun
        "acceptedMonth": len(accepted_m),      # shu oy qabul qilingan
        **rinfo,
        # montaj qilishi kerak: biriktirilgan + qaytarilgan
        "toDo": sum(1 for v in vids if v["status"] in ("biriktirildi", "qaytarildi")),
        # tasdiq jarayonida: montaj qilingan + sifat o'tgan
        "inReview": sum(1 for v in vids if v["status"] in ("montaj_qilindi", "sifat_ok")),
        "returned": sum(1 for v in vids if v["status"] == "qaytarildi"),
        "pending": sum(1 for v in vids if v["status"] in ("biriktirildi", "qaytarildi")),
        "earned": earned,
        "montajEarned": montaj_earned,
        "paid": paid,
        "remaining": earned - paid,
        "month": ym,
        "avg": round(montaj_earned / len(accepted_m)) if accepted_m else 0,
        "byProject": [{"project": k, "count": v} for k, v in sorted(by_project.items(), key=lambda x: -x[1])],
    }


def api_editors(user):
    conn = get_db()
    _mw, _mp = _montajchi_where()
    editors = conn.execute("SELECT name, color, title, avatar FROM users WHERE " + _mw + " ORDER BY name", _mp).fetchall()
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
    method, paid_from = _norm_pay_source(b, user)   # usul + qaysi hisobdan (Dilshod/Gulmira)
    sql = "INSERT INTO payments (editor, amount, paid_by, note, pdate, paid_from, method) VALUES (?,?,?,?,?,?,?)"
    params = (editor, amount, user["name"], b.get("note") or "",
              b.get("pdate") or uz_today().isoformat(), paid_from, method)
    if IS_PG:
        pid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        pid = conn.execute(sql, params).lastrowid
    log_audit(conn, user["name"], "maosh to'ladi", f"{editor} +{amount} so'm · {paid_from} {method}")
    conn.commit()
    conn.close()
    mlbl = "💳 Plastik" if method == "plastik" else "💵 Naqt"
    send_telegram(
        f"💸 <b>Maosh to'landi</b>\n👤 {editor}\n💰 {amount:,} so'm\n🏦 Hisob: {paid_from} · {mlbl}\n👮 Kiritdi: {user['name']}".replace(",", " ")
        + (f"\n📝 {b.get('note')}" if b.get("note") else "")
    )
    return {"ok": True, "id": pid}


def api_delete_payment(user, pid):
    """CEO — xato kiritilgan maosh to'lovini o'chiradi."""
    if user["role"] != "ceo":
        return {"error": "Ruxsat yo'q"}, 403
    conn = get_db()
    row = conn.execute("SELECT editor, amount FROM payments WHERE id=?", (pid,)).fetchone()
    if not row:
        conn.close()
        return {"error": "Topilmadi"}, 404
    conn.execute("DELETE FROM payments WHERE id=?", (pid,))
    log_audit(conn, user["name"], "maosh to'lovini o'chirdi", f"#{pid} {row['editor']} −{row['amount']}")
    conn.commit()
    conn.close()
    return {"ok": True}


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
    # Shu oydagi xarajat (shu oy qabul qilingan videolar)
    accepted = [dict(r) for r in conn.execute("SELECT * FROM videos WHERE status IN ('qabul_qilindi','joylandi')").fetchall()]
    accepted_m = [v for v in accepted if (v["approved_at"] or "").startswith(month)]
    month_cost = sum(v["amount"] or 0 for v in accepted_m)
    # Loyiha bo'yicha montaj xarajati (SHU OY) — qaysi loyihani kimlar montaj qilgani bilan
    by_project = {}
    for v in accepted_m:
        p = v["project"] or "—"
        d = by_project.setdefault(p, {"cost": 0, "editors": {}})
        d["cost"] += v["amount"] or 0
        ed = v["editor"] or "—"
        e = d["editors"].setdefault(ed, {"count": 0, "amount": 0})
        e["count"] += 1
        e["amount"] += v["amount"] or 0
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
        "byProject": [{"project": k, "cost": d["cost"],
                       "editors": sorted(
                           [{"name": en, "count": ev["count"], "amount": ev["amount"]}
                            for en, ev in d["editors"].items()], key=lambda x: -x["amount"])}
                      for k, d in sorted(by_project.items(), key=lambda x: -x[1]["cost"])],
        "mediaIncome": media_income,
        "payrollTotal": payroll_total,
        "mediaNet": media_income - payroll_total,
        "projectIncome": [{"name": p["name"], "fee": p["monthly_fee"]} for p in fee_rows],
    }


def api_cashflow(user):
    """CEO uchun — mijoz to'lovlari holati + umumiy pul oqimi (kirim/chiqim/sof).
    Kadr Media (mijoz oylik to'lovlari) + Kadr Studio bronlari kirim;
    payroll + studio xarajatlari chiqim."""
    conn = get_db()
    ym = uz_now().strftime("%Y-%m")
    rate = get_usd_rate()

    # --- Mijoz oylik to'lovlari (loyihalar) ---
    fee_rows = [dict(r) for r in conn.execute(
        "SELECT name, monthly_fee, responsible FROM projects WHERE monthly_fee>0 ORDER BY monthly_fee DESC").fetchall()]
    paid_rows = conn.execute(
        "SELECT project, COALESCE(SUM(amount),0) AS s FROM client_payments WHERE ym=? GROUP BY project",
        (ym,)).fetchall()
    paid_map = {r["project"]: (r["s"] or 0) for r in paid_rows}
    clients = []
    media_expected = 0
    media_received = 0
    for p in fee_rows:
        fee = p["monthly_fee"] or 0
        rec = paid_map.get(p["name"], 0)
        media_expected += fee
        media_received += rec
        clients.append({
            "project": p["name"],
            "responsible": p.get("responsible") or "",
            "fee": fee,
            "received": rec,
            "paid": rec >= fee and fee > 0,
        })
    media_outstanding = max(media_expected - media_received, 0)

    # --- Kadr Studio bronlari (shu oy) — paid_amount (qisman to'lovlar ham) + operator puli ---
    srows = [dict(r) for r in conn.execute(
        "SELECT amount, paid_amount, operator_pay FROM studio_bookings WHERE bdate LIKE ? "
        "AND (status IS NULL OR status<>'bekor_qilindi')", (ym + "%",)).fetchall()]
    studio_total = sum(r["amount"] or 0 for r in srows)
    studio_paid = sum(r.get("paid_amount") or 0 for r in srows)
    studio_unpaid = max(studio_total - studio_paid, 0)
    studio_op = sum(r.get("operator_pay") or 0 for r in srows)

    # --- Chiqim: payroll + studio xarajatlari (shu oy) ---
    payroll_total = 0
    payroll_paid = 0
    for n in SALARY:
        s = compute_salary(conn, n, rate)
        if s:
            payroll_total += s["total"]
            payroll_paid += s["paid"]
    studio_exp = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS s FROM studio_expenses WHERE edate LIKE ?",
        (ym + "%",)).fetchone()["s"] or 0
    conn.close()

    income_received = media_received + studio_paid
    income_expected = media_expected + studio_total
    expenses_total = payroll_total + studio_exp
    payroll_remaining = max(payroll_total - payroll_paid, 0)

    # --- Bo'linma P&L (double-count YO'Q: studio operator studioда, media qolganда) ---
    studio_costs = studio_op + studio_exp
    studio_net = studio_total - studio_costs
    media_cost = payroll_total - studio_op          # jamoa maoshi (studio operatorдан tashqari)
    media_net = media_expected - media_cost
    company_net = studio_net + media_net            # = income − studio_exp − payroll (2 marta emas)

    # --- Naqd holat (cash-flow) ---
    cash_out = studio_exp + payroll_paid            # ketgan pul (xarajat + to'langan maosh)
    cash_now = income_received - cash_out           # hozir qo'lда
    to_collect = media_outstanding + studio_unpaid  # yig'ilishi kerak
    need_for_salary = max(payroll_remaining - cash_now, 0)  # maoshга yetishi uchun yig'ilishi shart

    return {
        "month": ym,
        "clients": clients,
        "mediaExpected": media_expected,
        "mediaReceived": media_received,
        "mediaOutstanding": media_outstanding,
        "studioTotal": studio_total,
        "studioPaid": studio_paid,
        "studioUnpaid": studio_unpaid,
        "studioOperator": studio_op,
        "payrollTotal": payroll_total,
        "payrollPaid": payroll_paid,
        "payrollRemaining": payroll_remaining,
        "studioExpenses": studio_exp,
        "expensesTotal": expenses_total,
        "incomeReceived": income_received,
        "incomeExpected": income_expected,
        "netReceived": income_received - expenses_total,
        "netExpected": income_expected - expenses_total,
        # Bo'linma P&L
        "studioPL": {"income": studio_total, "operator": studio_op, "expenses": studio_exp,
                     "net": studio_net, "breakeven": studio_costs},
        "mediaPL": {"income": media_expected, "cost": media_cost, "net": media_net},
        "companyNet": company_net,
        # Naqd holat
        "cashNow": cash_now,
        "toCollect": to_collect,
        "needForSalary": need_for_salary,
    }


def som(n):
    """Pul summasini o'qishли ko'rinishда: 14 450 000 so'm."""
    return "{:,}".format(int(round(n or 0))).replace(",", " ") + " so'm"


def api_advisor(user):
    """MOLIYACHI — CEO uchun avtomatik moliyaviy tahlilchi.
    Har kuni yangilanadigan holat (minus/xavf/musbat) + ogohlantirishlar +
    o'tgan oy bilan trend + oy oxiri prognoz. api_cashflow raqamlaridan foydalanadi."""
    cf = api_cashflow(user)
    ym = cf["month"]
    company_net = cf["companyNet"]
    studio = cf["studioPL"]
    media = cf["mediaPL"]
    cash_now = cf["cashNow"]
    need_salary = cf["needForSalary"]
    to_collect = cf["toCollect"]
    payroll_remaining = cf["payrollRemaining"]
    payroll_total = cf["payrollTotal"]
    studio_exp = cf["studioExpenses"]

    # --- Oy bo'yicha kunlar (prognoz uchun) ---
    from calendar import monthrange
    today = uz_now()
    dim = monthrange(today.year, today.month)[1]
    day = today.day
    frac = day / dim if dim else 1.0

    # --- O'tgan oy arxivi bilan trend ---
    py, pm = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    prev_ym = "%04d-%02d" % (py, pm)
    conn = get_db()
    prow = conn.execute("SELECT data FROM monthly_archive WHERE ym=?", (prev_ym,)).fetchone()
    conn.close()
    last = None
    if prow:
        try:
            last = json.loads(prow["data"])
        except (ValueError, TypeError):
            last = None

    alerts = []  # {level: critical|warn|good|info, icon, title, text}

    # 1) Kompaniya sof foyda — minus/musbat
    if company_net < 0:
        alerts.append({"level": "critical", "icon": "🔴",
            "title": "Kompaniya MINUSда",
            "text": "Bu oy sof natija manfiy: " + som(company_net) +
                    ". Zudlik bilan xarajatni kamaytiring yoki tushumni oshiring."})
    else:
        alerts.append({"level": "good", "icon": "🟢",
            "title": "Kompaniya foydада",
            "text": "Bu oy sof foyda: +" + som(company_net) + " (Studio " +
                    som(studio["net"]) + " + Media " + som(media["net"]) + ")."})

    # 2) Naqd — maoshга yetadimi
    if need_salary > 0:
        alerts.append({"level": "warn", "icon": "💸",
            "title": "Maoshга naqd yetmaydi",
            "text": "Qolgan maosh " + som(payroll_remaining) + ", hozir qo'lда " +
                    som(cash_now) + ". Yana kamida " + som(need_salary) +
                    " yig'ish kerak (qarzda " + som(to_collect) + ")."})
    else:
        alerts.append({"level": "good", "icon": "💵",
            "title": "Maoshга naqd yetarli",
            "text": "Qo'lда " + som(cash_now) + " — qolgan maosh " +
                    som(payroll_remaining) + " uchun yetarli."})

    # 3) Studio marjasi (yupqa foyda / zarar)
    st_inc = studio["income"] or 0
    st_net = studio["net"]
    margin = (st_net / st_inc) if st_inc else 0
    if st_net < 0:
        alerts.append({"level": "critical", "icon": "🎥",
            "title": "Kadr Studio ZARARда",
            "text": "Studio xarajati (" + som(studio["expenses"] + studio["operator"]) +
                    ") tushumдан (" + som(st_inc) + ") oshди. Sof: " + som(st_net) + "."})
    elif margin < 0.15:
        alerts.append({"level": "warn", "icon": "🎥",
            "title": "Studio foydası juda yupqa",
            "text": "Marja atigi " + str(round(margin * 100)) + "% (sof " + som(st_net) +
                    "). Xarajat/ijara yuqori — break-even " + som(studio["breakeven"]) + "."})

    # 4) Yig'ilmagan qarz katta
    if to_collect > 0 and to_collect >= payroll_remaining and payroll_remaining > 0:
        alerts.append({"level": "warn", "icon": "📥",
            "title": "Katta qarz yig'ilmagan",
            "text": som(to_collect) + " hali yig'ilmagan (mijoz + studio). " +
                    "Inkassatsiya qilinса naqd muammosi yopiladi."})

    # 5) Xarajat trendi — o'tgan oy bilan
    trend = None
    if last:
        last_payroll = last.get("payrollTotal", 0) or 0
        last_st_exp = (last.get("studio") or {}).get("expenses", 0) or 0
        # Maosh fondi (to'liq oylik) — to'g'ridan-to'g'ri taqqoslanadi
        if payroll_total > last_payroll * 1.03:
            alerts.append({"level": "warn", "icon": "📈",
                "title": "Maosh fondi oshди",
                "text": "Bu oy " + som(payroll_total) + " (o'tган oy " + som(last_payroll) +
                        ", +" + som(payroll_total - last_payroll) + ")."})
        # Studio xarajati hali oshib boradi — oy oxirigача prognoz
        proj_st_exp = round(studio_exp / frac) if frac > 0 else studio_exp
        if studio_exp > last_st_exp:
            alerts.append({"level": "warn", "icon": "📈",
                "title": "Studio xarajati o'tган oydан oshди",
                "text": "Bu oy allaqачон " + som(studio_exp) + " (o'tган oy jami " +
                        som(last_st_exp) + "). Xarajatни nazorat qiling."})
        elif proj_st_exp > last_st_exp * 1.1:
            alerts.append({"level": "info", "icon": "📊",
                "title": "Studio xarajati oshib ketishi mumkin",
                "text": "Hozircha " + som(studio_exp) + ", shu suръатда oy oxiri ~" +
                        som(proj_st_exp) + " (o'tган oy " + som(last_st_exp) + ")."})
        trend = {"prevYm": prev_ym, "prevNet": last.get("companyNet", 0),
                 "prevPayroll": last_payroll, "prevStudioExp": last_st_exp}

    # --- Oy oxiri prognoz (barcha kutilган tushum yig'ilса, xarajat shu holда) ---
    forecast_net = cf["netExpected"]

    # --- Umumiy holat ---
    if company_net < 0:
        status, status_label = "minus", "MINUSда"
    elif need_salary > 0 or st_net < 0:
        status, status_label = "xavf", "Ehtiyot bo'ling"
    else:
        status, status_label = "musbat", "Barqaror"

    # Ogohlantirishlarни jiddiylik bo'yicha tartiblash
    order = {"critical": 0, "warn": 1, "info": 2, "good": 3}
    alerts.sort(key=lambda a: order.get(a["level"], 9))

    return {
        "month": ym,
        "status": status,
        "statusLabel": status_label,
        "day": day, "daysInMonth": dim,
        "companyNet": company_net,
        "forecastNet": forecast_net,
        "payrollTotal": payroll_total,
        "cashNow": cash_now,
        "needForSalary": need_salary,
        "toCollect": to_collect,
        "studioPL": studio, "mediaPL": media,
        "alerts": alerts,
        "trend": trend,
        "hasPrev": last is not None,
    }


def api_mark_client_payment(user, b):
    """CEO loyiha uchun shu oy mijoz to'lovini belgilaydi/olib tashlaydi (toggle)."""
    project = (b.get("project") or "").strip()
    if not project:
        return {"error": "Loyiha kerak"}, 400
    ym = (b.get("ym") or uz_now().strftime("%Y-%m")).strip()
    conn = get_db()
    ex = conn.execute("SELECT id FROM client_payments WHERE project=? AND ym=?", (project, ym)).fetchone()
    if ex:
        # toggle OFF — to'lov yozuvi (client_payments) VA daftar (income_ledger) birga o'chadi (drift yo'q)
        conn.execute("DELETE FROM income_ledger WHERE source_type='client' AND source_id=?", (ex["id"],))
        conn.execute("DELETE FROM client_payments WHERE id=?", (ex["id"],))
        conn.commit()
        conn.close()
        return {"ok": True, "paid": False}
    prow = conn.execute("SELECT monthly_fee FROM projects WHERE name=?", (project,)).fetchone()
    # to'lov summasi: naqt+plastik (split) yoki amount yoki loyiha oylik to'lovi
    def _iamt(k):
        try:
            return max(int(b.get(k) or 0), 0)
        except (ValueError, TypeError):
            return 0
    total = _iamt("naqt") + _iamt("plastik")
    if total == 0:
        total = _iamt("amount") or ((prow["monthly_fee"] if prow else 0) or 0)
    sql = "INSERT INTO client_payments (project, ym, amount, pdate, note, created_by) VALUES (?,?,?,?,?,?)"
    params = (project, ym, int(total), uz_today().isoformat(), (b.get("note") or ""), user["name"])
    if IS_PG:
        cpid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        cpid = conn.execute(sql, params).lastrowid
    # daftarga naqt/plastik bo'lib yoziladi, client_payment idga bog'lanadi
    _add_income_split(conn, "client", cpid, project, b, user,
                      note="Mijoz oylik to'lovi", default_amount=total)
    conn.commit()
    conn.close()
    return {"ok": True, "paid": True, "amount": int(total)}


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
    # Har bronning to'lov yozuvlari (daftardan — kim/naqt-plastik/sana)
    pays = {}
    for p in conn.execute(
            "SELECT id, source_id, amount, received_by, method, pdate, note FROM income_ledger "
            "WHERE source_type='studio' ORDER BY id").fetchall():
        pays.setdefault(p["source_id"], []).append(dict(p))
    conn.close()
    bookings = []
    for r in rows:
        d = dict(r)
        d["ledger"] = pays.get(d["id"], [])
        bookings.append(d)
    return {
        "rooms": STUDIO_ROOMS,
        "operators": list(STUDIO_OPERATORS),
        "shootTypes": SHOOT_TYPES,
        "operatorPay": OPERATOR_PAY,
        "methods": list(INCOME_METHODS),
        "receivers": list(INCOME_RECEIVERS),
        "canFinance": can_edit_studio(user),
        "canEdit": can_edit_studio(user),
        "me": user["name"],
        "bookings": bookings,
    }


def api_delete_income(user, lid):
    """Daftardagi bitta to'lov yozuvini o'chirish — manba bronning paid'i qayta hisoblanadi."""
    if not can_edit_studio(user):
        return {"error": "Ruxsat yo'q"}, 403
    conn = get_db()
    row = conn.execute("SELECT source_type, source_id FROM income_ledger WHERE id=?", (lid,)).fetchone()
    if not row:
        conn.close()
        return {"error": "Topilmadi"}, 404
    conn.execute("DELETE FROM income_ledger WHERE id=?", (lid,))
    if row["source_type"] == "studio" and row["source_id"]:
        _recalc_studio_paid(conn, row["source_id"])
    log_audit(conn, user["name"], "to'lov yozuvi o'chirdi", f"ledger #{lid}")
    conn.commit()
    conn.close()
    return {"ok": True}


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
    # Kadr Media (ichki) — studio tushumiga pul hisoblanmaydi (faqat xona/vaqt + operator puli)
    if shoot_type in STUDIO_NO_INCOME_TYPES:
        amount = 0
        paid_amount = 0
        b = {k: v for k, v in b.items() if k not in ("naqt", "plastik", "amount", "method")}
    bdate = b.get("bdate") or uz_today().isoformat()
    conn = get_db()
    # paid/paid_amount daftardan hisoblanadi — dastlab 0, keyin _recalc
    sql = """INSERT INTO studio_bookings
             (room, client_name, phone, bdate, start_time, end_time, hours, amount,
              paid, paid_amount, operator, shoot_type, operator_pay, status, note, created_by)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    params = (
        room, b.get("client_name") or "Mijoz", b.get("phone") or "", bdate,
        start, end, hours, amount, 0, 0,
        operator, shoot_type, operator_pay, "active",
        b.get("note") or "", user["name"],
    )
    if IS_PG:
        bid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        bid = conn.execute(sql, params).lastrowid
    _add_income_split(conn, "studio", bid, b.get("client_name") or "Studio", b, user,
                      note="Studio avans", default_amount=paid_amount)
    paid_amount = _recalc_studio_paid(conn, bid)
    fully_paid = 1 if (amount > 0 and paid_amount >= amount) else 0
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


def _norm_pay_source(b, user):
    """Xarajat uchun: qayerdan pul chiqdi — usul (naqt/plastik) + kim to'ladi (Dilshod/Gulmira)."""
    method = (b.get("method") or "naqt").strip().lower()
    if method not in INCOME_METHODS:
        method = "naqt"
    paid_by = (b.get("paid_by") or "").strip()
    if paid_by not in INCOME_RECEIVERS:
        paid_by = user["name"] if user["name"] in INCOME_RECEIVERS else INCOME_RECEIVERS[0]
    return method, paid_by


def _add_income(conn, source_type, source_id, label, amount, b, user, note=""):
    """Kelib tushgan pulni shaffoflik daftariga yozadi (kim qabul qildi + naqt/plastik)."""
    if not amount or amount <= 0:
        return
    received_by = (b.get("received_by") or "").strip()
    if received_by not in INCOME_RECEIVERS:
        received_by = user["name"] if user["name"] in INCOME_RECEIVERS else INCOME_RECEIVERS[0]
    method = (b.get("method") or "").strip().lower()
    if method not in INCOME_METHODS:
        method = "naqt"
    conn.execute(
        "INSERT INTO income_ledger (source_type, source_id, source_label, amount, received_by, method, pdate, note, created_by) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (source_type, source_id, label, int(amount), received_by, method,
         b.get("pdate") or uz_today().isoformat(), note, user["name"]))


def _add_income_split(conn, source_type, source_id, label, b, user, note="", default_amount=0):
    """To'lovni naqt/plastik bo'lib daftarga yozadi — har qismga ALOHIDA yozuv.
    b'da naqt/plastik summalari bo'lsa — shu; aks holda default_amount (usul: b['method'] yoki naqt).
    Jami to'langan summani qaytaradi."""
    def _iamt(k):
        try:
            return max(int(b.get(k) or 0), 0)
        except (ValueError, TypeError):
            return 0
    naqt = _iamt("naqt")
    plastik = _iamt("plastik")
    if naqt == 0 and plastik == 0:      # orqaga moslik: bitta summa + usul
        amt = max(int(default_amount or 0), 0)
        m = (b.get("method") or "naqt").strip().lower()
        if m == "plastik":
            plastik = amt
        else:
            naqt = amt
    received_by = (b.get("received_by") or "").strip()
    if received_by not in INCOME_RECEIVERS:
        received_by = user["name"] if user["name"] in INCOME_RECEIVERS else INCOME_RECEIVERS[0]
    pdate = b.get("pdate") or uz_today().isoformat()
    total = 0
    for method, amt in (("naqt", naqt), ("plastik", plastik)):
        if amt > 0:
            conn.execute(
                "INSERT INTO income_ledger (source_type, source_id, source_label, amount, received_by, method, pdate, note, created_by) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (source_type, source_id, label, amt, received_by, method, pdate, note, user["name"]))
            total += amt
    return total


def _backfill_studio_ledger(conn):
    """MIGRATSIYA (bir marta): daftar joriy etilishidan oldingi bronlar paid_amount>0
    lekin daftarda yozuvsiz — har biriga bitta yozuv qo'shadi (aks holda _recalc ularni nolga tushiradi)."""
    try:
        rows = conn.execute(
            "SELECT id, client_name, paid_amount, bdate, created_by FROM studio_bookings "
            "WHERE COALESCE(paid_amount,0) > 0").fetchall()
    except Exception:
        return
    for r in rows:
        has = conn.execute(
            "SELECT 1 FROM income_ledger WHERE source_type='studio' AND source_id=? LIMIT 1", (r["id"],)).fetchone()
        if has:
            continue
        recv = r["created_by"] if r["created_by"] in INCOME_RECEIVERS else INCOME_RECEIVERS[0]
        conn.execute(
            "INSERT INTO income_ledger (source_type, source_id, source_label, amount, received_by, method, pdate, note, created_by) "
            "VALUES ('studio',?,?,?,?,?,?,?,?)",
            (r["id"], r["client_name"] or "Studio", r["paid_amount"], recv, "naqt",
             r["bdate"] or uz_today().isoformat(), "eski to'lov (migratsiya)", "Tizim"))


def _ledger_paid(conn, source_type, source_id):
    """Manba (studio bron) uchun daftardan jami to'langan — YAGONA HAQIQAT."""
    return conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS s FROM income_ledger WHERE source_type=? AND source_id=?",
        (source_type, source_id)).fetchone()["s"] or 0


def _recalc_studio_paid(conn, bid):
    """Bronning paid_amount/paid ustunini daftardagi to'lovlardan qayta hisoblaydi (kesh)."""
    paid = _ledger_paid(conn, "studio", bid)
    row = conn.execute("SELECT amount FROM studio_bookings WHERE id=?", (bid,)).fetchone()
    total = (row["amount"] or 0) if row else 0
    conn.execute("UPDATE studio_bookings SET paid_amount=?, paid=? WHERE id=?",
                 (paid, 1 if (total > 0 and paid >= total) else 0, bid))
    return paid


def api_income_ledger(user):
    """CEO — barcha kelib tushgan pullar: kim qabul qildi, naqt/plastik, qayerdan. Shaffof."""
    if user["role"] != "ceo":
        return {"error": "Ruxsat yo'q"}, 403
    conn = get_db()
    ym = uz_now().strftime("%Y-%m")
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM income_ledger ORDER BY pdate DESC, id DESC LIMIT 300").fetchall()]
    conn.close()
    month_rows = [r for r in rows if (r.get("pdate") or "").startswith(ym)]
    by_receiver = {}
    by_method = {}
    for r in month_rows:
        by_receiver[r["received_by"]] = by_receiver.get(r["received_by"], 0) + (r["amount"] or 0)
        by_method[r["method"]] = by_method.get(r["method"], 0) + (r["amount"] or 0)
    return {
        "month": ym,
        "rows": rows,
        "monthTotal": sum(r["amount"] or 0 for r in month_rows),
        "byReceiver": by_receiver,
        "byMethod": by_method,
        "receivers": list(INCOME_RECEIVERS),
        "methods": list(INCOME_METHODS),
    }


def api_studio_pay(user, bid, b):
    """Bronga to'lov qo'shish (naqt/plastik bo'lib ham). To'liq to'lansa — guruhga xabar."""
    conn = get_db()
    ex = conn.execute("SELECT * FROM studio_bookings WHERE id=?", (bid,)).fetchone()
    if not ex:
        conn.close()
        return None
    ex = dict(ex)
    total = ex.get("amount") or 0
    was_full = ex.get("paid") or 0
    # To'lov faqat daftarga yoziladi (naqt/plastik bo'lib); paid_amount daftardan hisoblanadi
    add = _add_income_split(conn, "studio", bid, ex.get("client_name") or "Studio", b, user,
                            note="Studio to'lov", default_amount=b.get("amount") or 0)
    new_paid = _recalc_studio_paid(conn, bid)
    fully = 1 if (total > 0 and new_paid >= total) else 0
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
    # Bekor bo'lganda kelib tushgan pul ham hisobdan chiqadi (daftardan olib tashlanadi)
    conn.execute("DELETE FROM income_ledger WHERE source_type='studio' AND source_id=?", (bid,))
    _recalc_studio_paid(conn, bid)
    log_audit(conn, user["name"], "studio bron bekor qildi", f"#{bid} {ex['client_name']}")
    conn.commit()
    row = dict(conn.execute("SELECT * FROM studio_bookings WHERE id=?", (bid,)).fetchone())
    conn.close()
    send_telegram(f"🚫 <b>Studio bron bekor qilindi</b>\n{ex['client_name']}\n👮 {user['name']}")
    return row


def api_delete_studio_booking(user, bid):
    conn = get_db()
    conn.execute("DELETE FROM studio_bookings WHERE id=?", (bid,))
    # Bron o'chsa — uning to'lov yozuvlari ham daftardan ketadi (kirim to'g'rilanadi)
    conn.execute("DELETE FROM income_ledger WHERE source_type='studio' AND source_id=?", (bid,))
    log_audit(conn, user["name"], "studio bron o'chirdi", f"#{bid}")
    conn.commit()
    conn.close()
    return {"ok": True}


def api_update_studio_booking(user, bid, b):
    """Mavjud bronni tahrirlash (Dilshod+Gulmira)."""
    conn = get_db()
    ex = conn.execute("SELECT * FROM studio_bookings WHERE id=?", (bid,)).fetchone()
    if not ex:
        conn.close()
        return None
    ex = dict(ex)
    room = b.get("room") if b.get("room") in STUDIO_ROOMS else (ex.get("room") or "white")
    start = b.get("start_time") or ex.get("start_time") or "10:00"
    end = b.get("end_time") or ex.get("end_time") or "11:00"
    hours = _calc_hours(start, end)
    operator = (b.get("operator") if "operator" in b else ex.get("operator")) or ""
    if operator not in STUDIO_OPERATORS:
        operator = ""
    shoot_type = b.get("shoot_type") if b.get("shoot_type") in SHOOT_TYPES else (ex.get("shoot_type") or "reels")
    operator_pay = _op_pay(operator, shoot_type)

    def iv(key, default):
        v = b.get(key)
        if v is None or v == "":
            return default
        try:
            return int(v)
        except (ValueError, TypeError):
            return default
    amount = iv("amount", ex.get("amount") or 0)
    if shoot_type in STUDIO_NO_INCOME_TYPES:
        amount = 0  # Kadr Media (ichki) — studio tushumiga hisoblanmaydi
    bdate = b.get("bdate") or ex.get("bdate")
    # paid/paid_amount TAHRIR QILINMAYDI — u daftardan hisoblanadi (to'lov qo'shish/o'chirish orqali)
    conn.execute(
        """UPDATE studio_bookings SET room=?, client_name=?, phone=?, bdate=?, start_time=?, end_time=?,
           hours=?, amount=?, operator=?, shoot_type=?, operator_pay=?, note=? WHERE id=?""",
        (room, b.get("client_name") or ex.get("client_name"),
         (b.get("phone") if "phone" in b else ex.get("phone")) or "", bdate, start, end,
         hours, amount, operator, shoot_type, operator_pay,
         (b.get("note") if "note" in b else ex.get("note")) or "", bid))
    _recalc_studio_paid(conn, bid)  # summa o'zgargan bo'lsa — paid flag qayta hisoblanadi
    log_audit(conn, user["name"], "studio bron tahrirladi",
              f"#{bid} {b.get('client_name') or ex.get('client_name')} · {bdate}")
    conn.commit()
    row = dict(conn.execute("SELECT * FROM studio_bookings WHERE id=?", (bid,)).fetchone())
    conn.close()
    return row


def api_studio_finance(user):
    """Dilshod+Gulmira — oyma-oy tushum, operator puli, xarajat, sof foyda.
    Bekor qilingan bronlar hisobga OLINMAYDI. Sof foyda = tushum − operator puli − xarajatlar."""
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM studio_bookings").fetchall()]
    exps = [dict(r) for r in conn.execute("SELECT * FROM studio_expenses").fetchall()]
    # Gulmira (studio hisobidan) to'lagan jamoa maoshlari — studio pulidan chiqim
    team_pays = [dict(r) for r in conn.execute(
        "SELECT editor, amount, pdate, method FROM payments WHERE paid_from='Gulmira'").fetchall()]
    conn.close()
    active = [r for r in rows if (r.get("status") or "active") != "bekor_qilindi"]
    months = {}

    def M(ym):
        return months.setdefault(ym or "—", {
            "month": ym or "—", "total": 0, "operatorPay": 0, "expenses": 0, "net": 0,
            "paid": 0, "debt": 0, "count": 0, "white": 0, "black": 0, "teamSalary": 0,
            "bookings": [], "expensesList": [], "teamSalaryList": [],
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
        m["bookings"].append({
            "client": r.get("client_name"), "bdate": r.get("bdate"),
            "shoot_type": r.get("shoot_type"), "operator": r.get("operator") or "",
            "amount": amt, "paid": pa, "debt": max(amt - pa, 0),
            "operator_pay": r.get("operator_pay") or 0,
        })
    for e in exps:
        m = M((e.get("edate") or "")[:7])
        m["expenses"] += e.get("amount") or 0
        m["expensesList"].append({"name": e.get("name"), "amount": e.get("amount") or 0,
                                  "edate": e.get("edate"), "note": e.get("note") or "",
                                  "method": e.get("method") or "naqt", "paid_by": e.get("paid_by") or ""})
    for p in team_pays:
        m = M((p.get("pdate") or "")[:7])
        m["teamSalary"] += p.get("amount") or 0
        m["teamSalaryList"].append({"name": p.get("editor"), "amount": p.get("amount") or 0,
                                    "method": p.get("method") or "naqt"})
    for m in months.values():
        m["bookings"].sort(key=lambda x: (x.get("bdate") or ""))
    for m in months.values():
        m["net"] = m["total"] - m["operatorPay"] - m["expenses"]
        # Studio real naqd qoldiq = tushgan pul − xarajat − Gulmira to'lagan maosh
        m["cash"] = m["paid"] - m["expenses"] - m["teamSalary"]

    total_all = sum(r["amount"] or 0 for r in active)
    op_all = sum(r.get("operator_pay") or 0 for r in active)
    paid_all = sum(r.get("paid_amount") or 0 for r in active)
    exp_all = sum(e.get("amount") or 0 for e in exps)
    team_all = sum(p.get("amount") or 0 for p in team_pays)
    return {
        "rooms": STUDIO_ROOMS,
        "months": sorted(months.values(), key=lambda x: x["month"], reverse=True),
        "totalAll": total_all,
        "operatorPayAll": op_all,
        "expensesAll": exp_all,
        "netAll": total_all - op_all - exp_all,
        "paidAll": paid_all,
        "debtAll": max(total_all - paid_all, 0),
        "teamSalaryAll": team_all,
        "cashAll": paid_all - exp_all - team_all,
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
    method, paid_by = _norm_pay_source(b, user)
    conn = get_db()
    sql = "INSERT INTO studio_expenses (name, amount, edate, note, created_by, method, paid_by) VALUES (?,?,?,?,?,?,?)"
    params = (name, amount, edate, b.get("note") or "", user["name"], method, paid_by)
    if IS_PG:
        eid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        eid = conn.execute(sql, params).lastrowid
    log_audit(conn, user["name"], "studio xarajat kiritdi", f"#{eid} {name} · {amount} so'm · {paid_by} {method}")
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
#  BUDJET — kategoriya bo'yicha oylik budjet + mas'ul kishi
#  Xarajatlar studio_expenses jadvalida (name = kategoriya) saqlanadi.
# ------------------------------------------------------------
def _category_responsible(conn, category):
    row = conn.execute("SELECT responsible FROM budgets WHERE category=?", (category,)).fetchone()
    return (row["responsible"] if row else "") or ""


def can_spend_category(user, category):
    """Kategoriyaga xarajat yozish huquqi: CEO yoki shu kategoriya mas'uli."""
    if user["role"] == "ceo":
        return True
    conn = get_db()
    resp = _category_responsible(conn, category)
    conn.close()
    return resp == user["name"]


def api_budget(user):
    ym = uz_now().strftime("%Y-%m")
    conn = get_db()
    buds = {r["category"]: dict(r) for r in conn.execute("SELECT * FROM budgets ORDER BY category").fetchall()}
    spent = {}
    for r in conn.execute(
        "SELECT name, COALESCE(SUM(amount),0) AS s FROM studio_expenses WHERE edate LIKE ? GROUP BY name",
        (ym + "%",),
    ).fetchall():
        spent[r["name"]] = r["s"] or 0
    # Bu oydagi xarajatlar ro'yxati (kategoriya bo'yicha)
    exp_rows = [dict(r) for r in conn.execute(
        "SELECT * FROM studio_expenses WHERE edate LIKE ? ORDER BY edate DESC, id DESC", (ym + "%",)).fetchall()]
    conn.close()
    is_ceo = user["role"] == "ceo"
    cats = list(dict.fromkeys(list(buds.keys()) + STUDIO_EXPENSE_NAMES + list(spent.keys())))
    result = []
    for c in cats:
        b = buds.get(c, {})
        monthly = b.get("monthly", 0) or 0
        sp = spent.get(c, 0) or 0
        resp = b.get("responsible", "") or ""
        mine = resp == user["name"]
        if not (is_ceo or mine or c in buds or sp):
            # boshqalar uchun faqat o'zi mas'ul yoki budjetli/sarflangan kategoriyalar
            pass
        result.append({
            "category": c, "monthly": monthly, "responsible": resp,
            "spent": sp, "remaining": monthly - sp,
            "pct": (round(sp / monthly * 100) if monthly else 0),
            "canSpend": is_ceo or mine,
        })
    # Mas'ul bo'lmagan oddiy foydalanuvchi — faqat o'zi mas'ul kategoriyalari
    if not is_ceo:
        result = [r for r in result if r["responsible"] == user["name"]]
    return {
        "ym": ym, "isCeo": is_ceo,
        "categories": result,
        "totalBudget": sum(r["monthly"] for r in result),
        "totalSpent": sum(r["spent"] for r in result),
        "expenses": exp_rows if is_ceo else [e for e in exp_rows if _cat_is_mine(buds, e.get("name"), user["name"])],
    }


def _cat_is_mine(buds, category, name):
    b = buds.get(category, {})
    return (b.get("responsible") or "") == name


def api_set_budget(user, b):
    """CEO — kategoriya oylik budjeti va mas'ulini o'rnatadi."""
    category = (b.get("category") or "").strip()
    if not category:
        return {"error": "Kategoriya nomi kerak"}
    try:
        monthly = int(b.get("monthly") or 0)
    except (ValueError, TypeError):
        monthly = 0
    responsible = (b.get("responsible") or "").strip()
    conn = get_db()
    conn.execute("DELETE FROM budgets WHERE category=?", (category,))
    conn.execute("INSERT INTO budgets (category, monthly, responsible) VALUES (?,?,?)",
                 (category, monthly, responsible))
    log_audit(conn, user["name"], "budjet o'rnatdi", f"{category}: {monthly} so'm · mas'ul {responsible or '—'}")
    conn.commit()
    conn.close()
    return {"ok": True}


def api_delete_budget(user, b):
    category = (b.get("category") or "").strip()
    conn = get_db()
    conn.execute("DELETE FROM budgets WHERE category=?", (category,))
    log_audit(conn, user["name"], "budjet o'chirdi", category)
    conn.commit()
    conn.close()
    return {"ok": True}


def api_budget_spend(user, b):
    """Kategoriyaga xarajat yozish (CEO yoki mas'ul). studio_expenses'ga tushadi."""
    category = (b.get("category") or "").strip()
    if not category:
        return {"error": "Kategoriya kerak"}
    if not can_spend_category(user, category):
        return {"error": "Bu kategoriyaga ruxsat yo'q"}
    try:
        amount = int(b.get("amount") or 0)
    except (ValueError, TypeError):
        amount = 0
    if amount <= 0:
        return {"error": "Summani kiriting"}
    edate = b.get("edate") or uz_today().isoformat()
    method, paid_by = _norm_pay_source(b, user)
    conn = get_db()
    conn.execute("INSERT INTO studio_expenses (name, amount, edate, note, created_by, method, paid_by) VALUES (?,?,?,?,?,?,?)",
                 (category, amount, edate, b.get("note") or "", user["name"], method, paid_by))
    log_audit(conn, user["name"], "budjet xarajat", f"{category}: {amount} so'm · {paid_by} {method}")
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
    start_time = (b.get("start_time") or "").strip()
    end_time = (b.get("end_time") or "").strip()
    conn = get_db()
    sql = """INSERT INTO shoots (project_id, project, shoot_type, operator, operator_pay, sdate, start_time, end_time, status, note, created_by)
             VALUES (?,?,?,?,?,?,?,?,?,?,?)"""
    params = (b.get("project_id"), b.get("project") or "", shoot_type, operator,
              operator_pay, sdate, start_time, end_time, "active", b.get("note") or "", user["name"])
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
    time_str = (f" {start_time}–{end_time}" if start_time and end_time else (f" {start_time}" if start_time else ""))
    send_telegram(
        f"🎬 <b>Syomka belgilandi</b>\n📁 {b.get('project') or '—'}\n🎥 {SHOOT_TYPES[shoot_type]}"
        + (f"\n👤 Operator: {operator} (+{operator_pay:,} so'm)".replace(",", " ") if operator else "")
        + f"\n📅 {sdate}{time_str}\n👮 {user['name']}"
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


# Piece-work daromadlari — FAQAT shu oy (maosh oylik bo'lishi uchun; sana bo'yicha filtr).
def _op_earn(conn, name, ym=None):
    ym = ym or uz_now().strftime("%Y-%m")
    like = ym + "%"
    a = conn.execute("SELECT COALESCE(SUM(operator_pay),0) AS s FROM studio_bookings WHERE operator=? AND bdate LIKE ? AND (status IS NULL OR status<>'bekor_qilindi')", (name, like)).fetchone()["s"] or 0
    b = conn.execute("SELECT COALESCE(SUM(operator_pay),0) AS s FROM shoots WHERE operator=? AND sdate LIKE ? AND (status IS NULL OR status<>'bekor_qilindi')", (name, like)).fetchone()["s"] or 0
    return a + b


def _scenarist_earn(conn, name, ym=None):
    ym = ym or uz_now().strftime("%Y-%m")
    return conn.execute("SELECT COALESCE(SUM(amount),0) AS s FROM scenarist_scripts WHERE author=? AND sdate LIKE ? AND (status IS NULL OR status<>'bekor_qilindi')", (name, ym + "%")).fetchone()["s"] or 0


def _montaj_earn(conn, name, ym=None):
    ym = ym or uz_now().strftime("%Y-%m")
    return conn.execute("SELECT COALESCE(SUM(amount),0) AS s FROM videos WHERE editor=? AND approved_at LIKE ? AND status IN ('qabul_qilindi','joylandi')", (name, ym + "%")).fetchone()["s"] or 0


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
    """Rahbarlik puli oylik REJAGA proportsional: $50 × (bajarilgan/reja foizi, cap 100%).
    Reja kiritilmagan bo'lsa — eski 5-bosqich mantiqi ('tayyor' → $50, aks holda $25).
    Loyiha dashboard'da topilmasa — to'liq (baholab bo'lmaydi)."""
    projects = [dict(r) for r in conn.execute("SELECT * FROM projects").fetchall()]
    total, details = 0, []
    for cfg_name in LEADERSHIP.get(name, []):
        p = _find_project(projects, cfg_name)
        if p:
            self_post = bool(p.get("self_post"))
            plan = p.get("plan") or 0
            done_cols = [c for c in DONE_COLS if not (self_post and c == "done_joylash")]
            if plan > 0 and done_cols:
                done_total = sum(p.get(c) or 0 for c in done_cols)
                denom = plan * len(done_cols)
                pct = min(done_total / denom, 1.0) if denom else 0.0
                by_plan = True
            else:
                stages = [s for s in LEAD_STAGES if not (self_post and s == "joylash")]
                pct = 1.0 if all((p.get(st) or "") == "tayyor" for st in stages) else 0.5
                by_plan = False
            matched = p["name"]
        else:
            pct, by_plan = 1.0, False
            matched = None
        usd = int(round(LEADERSHIP_USD_FULL * pct))
        total += usd * rate
        details.append({"project": cfg_name, "matched": matched, "usd": usd,
                        "pct": int(round(pct * 100)), "byPlan": by_plan, "full": pct >= 1.0})
    return total, details


def _studio_client_bonus(conn):
    n = conn.execute("SELECT COUNT(*) AS n FROM studio_bookings WHERE (status IS NULL OR status<>'bekor_qilindi')").fetchone()["n"]
    return (n or 0) * STUDIO_CLIENT_BONUS


def _smm_done_count(conn, name, ym):
    """Shu oyda bajarilgan deb belgilangan SMM loyihalari soni."""
    ph = ",".join(["?"] * len(SMM_PROJECTS))
    return conn.execute(
        f"SELECT COUNT(DISTINCT project) AS n FROM smm_done WHERE person=? AND ym=? AND project IN ({ph})",
        tuple([name, ym] + SMM_PROJECTS),
    ).fetchone()["n"] or 0


def is_smm_user(user):
    return bool(user) and (SALARY.get(user["name"], {}).get("usd") or {}).get("SMM") is not None


def api_smm(user):
    ym = uz_now().strftime("%Y-%m")
    conn = get_db()
    done = {r["project"] for r in conn.execute(
        "SELECT project FROM smm_done WHERE person=? AND ym=?", (user["name"], ym)).fetchall()}
    conn.close()
    return {"ym": ym, "projects": [{"name": p, "done": p in done} for p in SMM_PROJECTS]}


def api_smm_toggle(user, b):
    project = b.get("project")
    if project not in SMM_PROJECTS:
        return {"error": "Noto'g'ri loyiha"}
    ym = uz_now().strftime("%Y-%m")
    conn = get_db()
    ex = conn.execute("SELECT id FROM smm_done WHERE person=? AND ym=? AND project=?",
                      (user["name"], ym, project)).fetchone()
    if ex:
        conn.execute("DELETE FROM smm_done WHERE id=?", (ex["id"],))
        done = False
    else:
        conn.execute("INSERT INTO smm_done (person, project, ym) VALUES (?,?,?)", (user["name"], project, ym))
        done = True
    log_audit(conn, user["name"], "SMM loyiha belgiladi", f"{project} · {'bajarildi' if done else 'olib tashlandi'}")
    conn.commit()
    conn.close()
    return {"ok": True, "project": project, "done": done}


def compute_salary(conn, name, rate):
    cfg = SALARY.get(name)
    if not cfg:
        return None
    comps = []
    today = uz_today()
    ym = today.strftime("%Y-%m")
    cl = cfg.get("close_link") or []          # kun yopishga bog'langan komponent(lar)
    close_links = [cl] if isinstance(cl, str) else list(cl)
    is_close = name in DAILY_CLOSE_USERS
    for label, som in (cfg.get("som") or {}).items():
        amt = int(som)
        lbl = label
        kind = "fixed"
        if label == "Intizom" and name in ATTENDANCE_USERS:
            ot = _ontime_days(conn, name, today)
            amt = min(ot * INTIZOM_PER_DAY, INTIZOM_FULL)
            lbl = f"Intizom · {ot} kun o'z vaqtida"
            kind = "auto"
        elif label in close_links and is_close:
            amt, missed = _kpi_after_discipline(conn, name, amt, today)
            kind = "auto"
            if missed:
                lbl = f"{label} · −{missed} kun yopilmagan"
        comps.append({"label": lbl, "amount": amt, "kind": kind})
    for label, usd in (cfg.get("usd") or {}).items():
        amt = int(usd) * rate
        lbl = f"{label} (${usd})"
        kind = "fixed"
        if label == "SMM":
            # SMM = to'liq × (bajarilgan SMM loyihalar ÷ jami); + kun yopishga bog'liq bo'lsa jazo
            done = _smm_done_count(conn, name, ym)
            total = len(SMM_PROJECTS) or 1
            amt = int(round(amt * done / total))
            kind = "auto"
            parts = [f"{done}/{total} loyiha"]
            if "SMM" in close_links and is_close:
                amt, missed = _kpi_after_discipline(conn, name, amt, today)
                if missed:
                    parts.append(f"−{missed} kun")
            lbl = f"SMM (${usd}) · " + " · ".join(parts)
        elif label in close_links and is_close:
            amt, missed = _kpi_after_discipline(conn, name, amt, today)
            kind = "auto"
            if missed:
                lbl = f"{label} (${usd}) · −{missed} kun yopilmagan"
        comps.append({"label": lbl, "amount": amt, "kind": kind})
    if cfg.get("lead"):
        lp, det = _leadership_pay(conn, name, rate)
        lbl = f"Rahbarlik ({len(det)} loyiha · reja bajarilishiga qarab)"
        comps.append({"label": lbl, "amount": lp, "kind": "lead", "detail": det})
    if cfg.get("operator"):
        comps.append({"label": "Operator syomka puli (shu oy)", "amount": _op_earn(conn, name, ym), "kind": "auto"})
    if cfg.get("scenarist"):
        comps.append({"label": "Ssenariy puli (shu oy)", "amount": _scenarist_earn(conn, name, ym), "kind": "auto"})
    if cfg.get("montaj"):
        comps.append({"label": "Montaj puli (shu oy)", "amount": _montaj_earn(conn, name, ym), "kind": "auto"})
    if cfg.get("studio_bonus"):
        comps.append({"label": "Studio mijoz bonusi", "amount": _studio_client_bonus(conn), "kind": "auto"})
    total = sum(c["amount"] for c in comps)
    ym = uz_now().strftime("%Y-%m")
    paid = _paid_to(conn, name, ym)
    return {"name": name, "title": cfg.get("title", ""), "components": comps,
            "total": total, "paid": paid, "remaining": total - paid}


def _paid_to(conn, name, ym):
    """Shu oyda xodimga to'langan pul (payments jadvali, pdate shu oy)."""
    return conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS s FROM payments WHERE editor=? AND pdate LIKE ?",
        (name, ym + "%")).fetchone()["s"] or 0


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
#  OYLIK ARXIV (payroll + moliya snapshot — "muzlatish")
# ------------------------------------------------------------
def _month_snapshot(conn, ym, actor):
    """Berilgan oyning to'liq moliyaviy holatini yig'adi (arxiv uchun)."""
    rate = get_usd_rate()
    salaries, payroll_total = [], 0
    for n in SALARY:
        s = compute_salary(conn, n, rate)
        if s:
            payroll_total += s["total"]
            salaries.append({"name": n, "title": s.get("title", ""), "total": s["total"],
                             "paid": s["paid"], "remaining": s["remaining"]})
    media_income = conn.execute("SELECT COALESCE(SUM(monthly_fee),0) AS s FROM projects WHERE monthly_fee>0").fetchone()["s"] or 0
    like = ym + "%"
    active = [dict(r) for r in conn.execute(
        "SELECT amount, paid_amount, operator_pay FROM studio_bookings "
        "WHERE bdate LIKE ? AND (status IS NULL OR status<>'bekor_qilindi')", (like,)).fetchall()]
    st_total = sum(r["amount"] or 0 for r in active)
    st_op = sum(r.get("operator_pay") or 0 for r in active)
    st_paid = sum(r.get("paid_amount") or 0 for r in active)
    st_exp = conn.execute("SELECT COALESCE(SUM(amount),0) AS s FROM studio_expenses WHERE edate LIKE ?", (like,)).fetchone()["s"] or 0
    st_net = st_total - st_op - st_exp
    ss = _shoot_stats(conn, ym)
    return {
        "ym": ym, "rate": rate, "salaries": salaries, "payrollTotal": payroll_total,
        "mediaIncome": media_income,
        "studio": {"total": st_total, "operatorPay": st_op, "expenses": st_exp,
                   "net": st_net, "paid": st_paid, "debt": max(st_total - st_paid, 0)},
        # Kompaniya sof foyda = jami kirim − payroll − studio xarajat.
        # Operator puli payroll ICHIDA (_op_earn) — shuning uchun studio net'dan qayta ayirilmaydi (2 marta emas).
        "companyNet": media_income + st_total - payroll_total - st_exp,
        "shoots": {"totalHours": ss["totalHours"], "studioHours": ss["studioHours"],
                   "mediaHours": ss["mediaHours"], "count": ss["count"], "byOperator": ss["byOperator"]},
        "generatedAt": now_local(), "by": actor,
    }


def api_archive_month(user):
    """CEO — joriy oyni arxivlaydi (muzlatadi). Qayta bosilsa yangilanadi."""
    if user["role"] != "ceo":
        return {"error": "Ruxsat yo'q"}, 403
    ym = uz_now().strftime("%Y-%m")
    conn = get_db()
    snap = _month_snapshot(conn, ym, user["name"])
    data = json.dumps(snap, ensure_ascii=False)
    ex = conn.execute("SELECT ym FROM monthly_archive WHERE ym=?", (ym,)).fetchone()
    if ex:
        conn.execute("UPDATE monthly_archive SET data=?, net=?, created_by=?, created_at=? WHERE ym=?",
                     (data, snap["companyNet"], user["name"], now_local(), ym))
    else:
        conn.execute("INSERT INTO monthly_archive (ym, data, net, created_by, created_at) VALUES (?,?,?,?,?)",
                     (ym, data, snap["companyNet"], user["name"], now_local()))
    log_audit(conn, user["name"], "oy arxivlandi (muzlatildi)", ym)
    conn.commit()
    conn.close()
    return {"ok": True, "ym": ym, "snapshot": snap}


def api_archives(user):
    """CEO — muzlatilgan oylar ro'yxati + joriy oy (jonli) ko'rinishi."""
    if user["role"] != "ceo":
        return {"error": "Ruxsat yo'q"}, 403
    conn = get_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT ym, net, created_by, created_at FROM monthly_archive ORDER BY ym DESC").fetchall()]
    cur_ym = uz_now().strftime("%Y-%m")
    preview = _month_snapshot(conn, cur_ym, user["name"])
    conn.close()
    return {
        "archived": [{"ym": r["ym"], "net": r["net"], "by": r["created_by"], "at": r["created_at"]} for r in rows],
        "current": preview,
        "currentArchived": any(r["ym"] == cur_ym for r in rows),
    }


def api_archive_get(user, ym):
    """CEO — muzlatilgan oyning to'liq snapshot'i."""
    if user["role"] != "ceo":
        return {"error": "Ruxsat yo'q"}, 403
    conn = get_db()
    row = conn.execute("SELECT data FROM monthly_archive WHERE ym=?", (ym,)).fetchone()
    conn.close()
    if not row:
        return {"error": "Topilmadi"}, 404
    return json.loads(row["data"])


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
def _shoot_stats(conn, ym):
    """Berilgan oydagi barcha syomkalar (Kadr Studio bronlari + Kadr Media syomkalari):
    jami soat, kim, qaysi vaqtда, qaysi xonada."""
    like = ym + "%"
    sb = [dict(r) for r in conn.execute(
        "SELECT * FROM studio_bookings WHERE bdate LIKE ? AND (status IS NULL OR status<>'bekor_qilindi')",
        (like,)).fetchall()]
    sh = [dict(r) for r in conn.execute(
        "SELECT * FROM shoots WHERE sdate LIKE ? AND (status IS NULL OR status<>'bekor_qilindi')",
        (like,)).fetchall()]
    items, by_op = [], {}
    studio_h = media_h = 0.0
    for b in sb:
        h = b.get("hours") or _calc_hours(b.get("start_time"), b.get("end_time"))
        op = b.get("operator") or "—"
        studio_h += h
        e = by_op.setdefault(op, {"hours": 0.0, "count": 0}); e["hours"] += h; e["count"] += 1
        items.append({"source": "studio", "date": b.get("bdate"), "start": (b.get("start_time") or "")[:5],
                      "end": (b.get("end_time") or "")[:5], "hours": round(h, 1), "operator": op,
                      "room": b.get("room") or "", "who": b.get("client_name") or "",
                      "shoot_type": b.get("shoot_type")})
    for s in sh:
        h = _calc_hours(s.get("start_time"), s.get("end_time")) if s.get("start_time") else 0
        op = s.get("operator") or "—"
        media_h += h
        e = by_op.setdefault(op, {"hours": 0.0, "count": 0}); e["hours"] += h; e["count"] += 1
        items.append({"source": "media", "date": s.get("sdate"), "start": (s.get("start_time") or "")[:5],
                      "end": (s.get("end_time") or "")[:5], "hours": round(h, 1), "operator": op,
                      "room": "", "who": s.get("project") or "", "shoot_type": s.get("shoot_type")})
    items.sort(key=lambda x: ((x["date"] or ""), (x["start"] or "")))
    return {
        "month": ym,
        "totalHours": round(studio_h + media_h, 1),
        "studioHours": round(studio_h, 1),
        "mediaHours": round(media_h, 1),
        "count": len(items),
        "byOperator": sorted([{"name": k, "hours": round(v["hours"], 1), "count": v["count"]}
                              for k, v in by_op.items()], key=lambda x: -x["hours"]),
        "items": items,
    }


def api_shoot_stats(user, ym):
    """Syomka statistikasi (soat/vaqt/kim/xona) — CEO/koordinator/rahbar. Har oy uchun."""
    if user["role"] not in APPROVER_ROLES:
        return {"error": "Ruxsat yo'q"}, 403
    cur = uz_now().strftime("%Y-%m")
    if not ym or len(ym) != 7:
        ym = cur
    if ym > cur:
        ym = cur
    conn = get_db()
    res = _shoot_stats(conn, ym)
    conn.close()
    res["current"] = cur
    res["isPast"] = ym < cur
    res["rooms"] = STUDIO_ROOMS
    res["shootTypes"] = SHOOT_TYPES
    return res


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
    _mw, _mp = _montajchi_where()
    ed_rows = conn.execute("SELECT name FROM users WHERE " + _mw + " ORDER BY name", _mp).fetchall()
    editors = [{"name": e["name"],
                "count": cnt("SELECT COUNT(*) AS n FROM videos WHERE editor=? AND approved_at LIKE ? AND status IN ('qabul_qilindi','joylandi')", (e["name"], like))}
               for e in ed_rows]
    conn.close()
    return {
        "month": ym, "current": cur, "isPast": ym < cur,
        "totals": totals,
        "scenarists": scenarists, "operators": operators, "editors": editors,
    }


def api_leaderboard(user):
    """Reyting + trend: montajchilar/ssenaristlar/operatorlar shu oy bo'yicha
    reytingi + oxirgi 6 oy jamoaviy trend (qabul qilingan / joylangan videolar)."""
    conn = get_db()
    cur = uz_now()
    ym = cur.strftime("%Y-%m")
    like = ym + "%"

    def cnt(sql, params):
        return conn.execute(sql, params).fetchone()["n"] or 0

    allc = _editor_accepted_counts(conn)   # haqiqiy dona (jami)
    pts = _editor_rank_points(conn)        # lavozim ballari (podcast=3)
    _mw, _mp = _montajchi_where()
    ed_rows = conn.execute("SELECT name FROM users WHERE " + _mw + " ORDER BY name", _mp).fetchall()
    montaj = []
    for e in ed_rows:
        nm = e["name"]
        mo = cnt("SELECT COUNT(*) AS n FROM videos WHERE editor=? AND approved_at LIKE ? "
                 "AND status IN ('qabul_qilindi','joylandi')", (nm, like))
        ri = rank_info(eff_count(nm, pts.get(nm, 0)))
        montaj.append({"name": nm, "month": mo, "allTime": allc.get(nm, 0),
                       "rankLabel": ri["rank_label"], "rankIcon": ri["rank_icon"]})
    montaj.sort(key=lambda x: (-x["month"], -x["allTime"]))

    scen = [{"name": nm,
             "month": cnt("SELECT COUNT(*) AS n FROM scenarist_scripts WHERE author=? "
                          "AND (status IS NULL OR status<>'bekor_qilindi') AND sdate LIKE ?", (nm, like))}
            for nm in SCENARIST_PAY]
    scen.sort(key=lambda x: -x["month"])

    ops = [{"name": nm,
            "month": cnt("SELECT COUNT(*) AS n FROM shoots WHERE operator=? "
                         "AND (status IS NULL OR status<>'bekor_qilindi') AND sdate LIKE ?", (nm, like))
                     + cnt("SELECT COUNT(*) AS n FROM studio_bookings WHERE operator=? "
                           "AND (status IS NULL OR status<>'bekor_qilindi') AND bdate LIKE ?", (nm, like))}
           for nm in STUDIO_OPERATORS]
    ops.sort(key=lambda x: -x["month"])

    # oxirgi 6 oy
    y, m = cur.year, cur.month
    months = []
    for i in range(5, -1, -1):
        mm, yy = m - i, y
        while mm <= 0:
            mm += 12
            yy -= 1
        months.append("%04d-%02d" % (yy, mm))
    trend = []
    for mo in months:
        trend.append({
            "ym": mo,
            "accepted": cnt("SELECT COUNT(*) AS n FROM videos WHERE approved_at LIKE ? "
                            "AND status IN ('qabul_qilindi','joylandi')", (mo + "%",)),
            "posted": cnt("SELECT COUNT(*) AS n FROM videos WHERE posted_at LIKE ? AND status='joylandi'", (mo + "%",)),
        })
    conn.close()
    return {"month": ym, "montaj": montaj, "scenarists": scen, "operators": ops, "trend": trend}


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


def _close_streak(conn, name, today):
    """Ketma-ket yopilgan ish kunlari soni (yakshanba streak'ni buzmaydi).
    Bugun hali yopilmagan bo'lsa — kechadan sanaydi."""
    closed = {r["cdate"] for r in conn.execute(
        "SELECT cdate FROM daily_close WHERE person=?", (name,)).fetchall()}
    d = today
    if d.isoformat() not in closed and d.weekday() != 6:
        d = d - datetime.timedelta(days=1)  # bugun hali yopiladi — kechadan
    streak = 0
    for _ in range(90):
        if d.weekday() == 6:  # yakshanba — o'tkazamiz
            d = d - datetime.timedelta(days=1)
            continue
        if d.isoformat() in closed:
            streak += 1
            d = d - datetime.timedelta(days=1)
        else:
            break
    return streak


def _seed_checklist(conn):
    """Har kishiga tayyor cheklist (faqat o'sha kishida hech narsa bo'lmasa)."""
    for person, items in DEFAULT_CHECKLIST.items():
        n = conn.execute("SELECT COUNT(*) AS n FROM checklist_items WHERE person=?", (person,)).fetchone()["n"]
        if n == 0:
            for i, text in enumerate(items):
                conn.execute("INSERT INTO checklist_items (person, text, sort, active) VALUES (?,?,?,1)",
                             (person, text, i))


def _checklist_for(conn, person, cdate=None):
    """Kishining faol cheklisti; cdate berilsa — o'sha kundagi belgi + qo'lda izoh bilan."""
    items = conn.execute(
        "SELECT id, text FROM checklist_items WHERE person=? AND active=1 ORDER BY sort, id",
        (person,)).fetchall()
    state = {}
    if cdate:
        for r in conn.execute(
                "SELECT item_id, done, note FROM checklist_done WHERE person=? AND cdate=?",
                (person, cdate)).fetchall():
            state[r["item_id"]] = {"done": bool(r["done"]), "note": r["note"] or ""}
    out = []
    for r in items:
        s = state.get(r["id"], {})
        out.append({"id": r["id"], "text": r["text"],
                    "done": s.get("done", False), "note": s.get("note", "")})
    return out


def can_edit_checklist(user, person):
    return bool(user) and (user["name"] == person or user["role"] == "ceo")


# Kunlik vazifa biriktirish — Dilshod (CEO) va Xonzoda.
def can_assign_tasks(user):
    return bool(user) and (user["role"] == "ceo" or user["name"] == "Xonzoda")


def _assigned_tasks_for(conn, person, tdate):
    """Kishiga o'sha kunga biriktirilgan vazifalar (majburiy — kun yopishga bog'liq)."""
    return [{"id": r["id"], "text": r["text"], "done": bool(r["done"]),
             "note": r["note"] or "", "assigned_by": r["assigned_by"]}
            for r in conn.execute(
                "SELECT id, text, done, note, assigned_by FROM assigned_tasks "
                "WHERE assignee=? AND tdate=? ORDER BY id", (person, tdate)).fetchall()]


def api_assign_task(user, b):
    """Dilshod/Xonzoda jamoa a'zosiga (kun yopadigan 4 kishiga) kunlik vazifa biriktiradi."""
    if not can_assign_tasks(user):
        return {"error": "Ruxsat yo'q"}, 403
    assignee = (b.get("assignee") or "").strip()
    if assignee not in DAILY_CLOSE_USERS:
        return {"error": "Faqat kun yopadigan 4 kishiga biriktirish mumkin"}, 400
    text = (b.get("text") or "").strip()
    if not text:
        return {"error": "Vazifa matni kerak"}, 400
    tdate = (b.get("tdate") or uz_today().isoformat()).strip()
    conn = get_db()
    sql = "INSERT INTO assigned_tasks (assignee, text, tdate, assigned_by) VALUES (?,?,?,?)"
    params = (assignee, text, tdate, user["name"])
    if IS_PG:
        tid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        tid = conn.execute(sql, params).lastrowid
    log_audit(conn, user["name"], "vazifa biriktirdi", f"{assignee} · {tdate}: {text[:40]}")
    conn.commit()
    conn.close()
    send_telegram(f"📌 <b>Yangi vazifa</b>\n👤 {assignee}\n📅 {tdate}\n📝 {text}\n👮 {user['name']}")
    return {"ok": True, "id": tid}


def api_delete_assigned_task(user, tid):
    conn = get_db()
    row = conn.execute("SELECT assigned_by FROM assigned_tasks WHERE id=?", (tid,)).fetchone()
    if not row:
        conn.close()
        return {"error": "Topilmadi"}, 404
    if not can_assign_tasks(user):
        conn.close()
        return {"error": "Ruxsat yo'q"}, 403
    conn.execute("DELETE FROM assigned_tasks WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    return {"ok": True}


def api_assigned_list(user, person, date):
    """Biriktiruvchi (Dilshod/Xonzoda) — tanlangan kun/odam bo'yicha vazifalar ro'yxati."""
    if not can_assign_tasks(user):
        return {"error": "Ruxsat yo'q"}, 403
    tdate = (date or uz_today().isoformat())
    conn = get_db()
    if person and person in DAILY_CLOSE_USERS:
        people = [person]
    else:
        people = list(DAILY_CLOSE_USERS)
    out = {p: _assigned_tasks_for(conn, p, tdate) for p in people}
    conn.close()
    return {"date": tdate, "tasks": out, "people": list(DAILY_CLOSE_USERS)}


# Har kishi uchun "bugun tizimda qayd etilgan" real faoliyat (obyektiv dalil).
EVIDENCE_FIELDS = {
    "Said": ["shoots", "qc", "accepted"],
    "Gulmira": ["studio_created"],
    "Xonzoda": ["scripts"],
    "Umida": ["posted", "scripts"],
}
EVIDENCE_LABEL = {
    "shoots": "🎥 Syomka", "qc": "🔎 Sifat tekshirdi", "accepted": "✅ Video qabul qildi",
    "studio_created": "🎬 Studio bron kiritdi", "scripts": "✍️ Ssenariy", "posted": "📷 Instagram'ga joyladi",
}


def _today_evidence(conn, person, today):
    """Kishining bugungi real tizim faoliyati — qo'l bilan emas, tizim sanaydi."""
    tstr = today.isoformat()
    like = tstr + "%"

    def c(sql, params):
        return conn.execute(sql, params).fetchone()["n"] or 0

    metrics = {
        "shoots": (lambda: c("SELECT COUNT(*) AS n FROM shoots WHERE operator=? AND sdate=? AND (status IS NULL OR status<>'bekor_qilindi')", (person, tstr))
                           + c("SELECT COUNT(*) AS n FROM studio_bookings WHERE operator=? AND bdate=? AND (status IS NULL OR status<>'bekor_qilindi')", (person, tstr))),
        "qc": (lambda: c("SELECT COUNT(*) AS n FROM videos WHERE qc_by=? AND qc_at LIKE ?", (person, like))),
        "accepted": (lambda: c("SELECT COUNT(*) AS n FROM videos WHERE approved_by=? AND approved_at LIKE ? AND status IN ('qabul_qilindi','joylandi')", (person, like))),
        "studio_created": (lambda: c("SELECT COUNT(*) AS n FROM studio_bookings WHERE created_by=? AND CAST(created_at AS TEXT) LIKE ? AND (status IS NULL OR status<>'bekor_qilindi')", (person, like))),
        "scripts": (lambda: c("SELECT COUNT(*) AS n FROM scenarist_scripts WHERE author=? AND sdate=? AND (status IS NULL OR status<>'bekor_qilindi')", (person, tstr))),
        "posted": (lambda: c("SELECT COUNT(*) AS n FROM videos WHERE posted_by=? AND posted_at LIKE ? AND status='joylandi'", (person, like))),
    }
    out = []
    for key in EVIDENCE_FIELDS.get(person, []):
        fn = metrics.get(key)
        if fn:
            out.append({"label": EVIDENCE_LABEL.get(key, key), "count": fn()})
    return out


def _studio_debt_on(conn, tdate):
    """O'sha kundagi Kadr Studio bronlaridan qarzli (to'liq to'lanmagan) bo'lganlari."""
    out = []
    for r in conn.execute(
        "SELECT id, client_name, amount, paid_amount FROM studio_bookings "
        "WHERE bdate=? AND (status IS NULL OR status<>'bekor_qilindi')", (tdate,)).fetchall():
        amt = r["amount"] or 0
        paid = r["paid_amount"] or 0
        if amt > 0 and paid < amt:
            out.append({"id": r["id"], "client": r["client_name"], "amount": amt,
                        "paid": paid, "debt": amt - paid})
    return out


# Kadr Studio qarzi kun yopishga bog'langan xodim.
STUDIO_DEBT_CLOSER = "Gulmira"


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
        res["streak"] = _close_streak(conn, user["name"], today)
        res["checklist"] = _checklist_for(conn, user["name"], tstr)
        res["evidence"] = _today_evidence(conn, user["name"], today)
        res["assignedTasks"] = _assigned_tasks_for(conn, user["name"], tstr)
        if user["name"] == STUDIO_DEBT_CLOSER:
            res["studioDebt"] = _studio_debt_on(conn, tstr)
    res["canAssign"] = can_assign_tasks(user)
    if user["role"] == "ceo":
        res["overview"] = [{
            "name": nm, "closedToday": tstr in _closed_dates(conn, nm, ym),
            "closedCount": len(_closed_dates(conn, nm, ym)),
            "missed": _missed_workdays(conn, nm, today),
            "streak": _close_streak(conn, nm, today),
            "checklist": _checklist_for(conn, nm, tstr),
            "evidence": _today_evidence(conn, nm, today),
            "assignedTasks": _assigned_tasks_for(conn, nm, tstr),
        } for nm in DAILY_CLOSE_USERS]
    conn.close()
    return res


MIN_CLOSE_NOTE_LEN = 3  # belgilangan vazifa izohining eng kam uzunligi


def api_close_day(user, b=None):
    if not is_daily_user(user):
        return {"error": "Ruxsat yo'q"}
    b = b or {}
    conn = get_db()
    today = uz_today().isoformat()

    # Kelgan vazifalarni normallashtiramiz (id, done, note)
    raw = b.get("items")
    valid = {r["id"] for r in conn.execute(
        "SELECT id FROM checklist_items WHERE person=?", (user["name"],)).fetchall()}
    parsed = []
    for it in (raw or []):
        if isinstance(it, dict):
            iid, done, note = it.get("id"), (1 if it.get("done") else 0), (it.get("note") or "").strip()
        else:  # eski format: shunchaki id ro'yxati
            iid, done, note = it, 1, ""
        try:
            iid = int(iid)
        except (ValueError, TypeError):
            continue
        if iid in valid:
            parsed.append({"id": iid, "done": done, "note": note})

    # Biriktirilgan vazifalar (Dilshod/Xonzoda bergan) — bugungisi + kelayotgan holat
    assigned_in = {}
    for a in (b.get("assigned") or []):
        try:
            aid = int(a.get("id"))
        except (ValueError, TypeError):
            continue
        assigned_in[aid] = {"done": 1 if a.get("done") else 0, "note": (a.get("note") or "").strip()}
    assigned_today = conn.execute(
        "SELECT id, text, done FROM assigned_tasks WHERE assignee=? AND tdate=?",
        (user["name"], today)).fetchall()

    # --- Tekshiruv (faqat items yuborilganda, ya'ni haqiqiy yopish) ---
    if raw is not None:
        # 0) Gulmira — bugungi Kadr Studio bronlarida qarz bo'lsa kun yopilmaydi
        if user["name"] == STUDIO_DEBT_CLOSER:
            debts = _studio_debt_on(conn, today)
            if debts:
                names = ", ".join(f"{d['client']} ({d['debt']:,} so'm)".replace(",", " ") for d in debts)
                conn.close()
                return {"error": f"Kadr Studio qarzdorligi bor — avval to'lovni kiriting: {names}"}, 400
        # 1) Barcha biriktirilgan vazifa bajarilishi shart
        for a in assigned_today:
            eff_done = assigned_in.get(a["id"], {}).get("done", a["done"])
            if not eff_done:
                conn.close()
                return {"error": f"Sizga biriktirilgan vazifa bajarilmagan: «{a['text']}». Bajarib belgilang."}, 400
        ticked = [p for p in parsed if p["done"]]
        # 2) Kamida bitta ish qilingan bo'lsin (cheklist yoki biriktirilgan vazifa)
        if not ticked and not assigned_today:
            conn.close()
            return {"error": "Kunni yopish uchun kamida bitta bajarilgan vazifani belgilang."}, 400
        # 3) Belgilangan cheklist vazifalariga izoh majburiy
        no_note = [p for p in ticked if len(p["note"]) < MIN_CLOSE_NOTE_LEN]
        if no_note:
            texts = conn.execute(
                "SELECT id, text FROM checklist_items WHERE person=?", (user["name"],)).fetchall()
            tmap = {r["id"]: r["text"] for r in texts}
            first = tmap.get(no_note[0]["id"], "vazifa")
            conn.close()
            return {"error": f"Belgilangan har vazifaga izoh yozing (nima qildingiz). Masalan: «{first}»"}, 400

    # Biriktirilgan vazifalar holatini saqlaymiz (belgi + izoh)
    if raw is not None and assigned_in:
        for aid, st in assigned_in.items():
            conn.execute(
                "UPDATE assigned_tasks SET done=?, note=?, done_at=? WHERE id=? AND assignee=?",
                (st["done"], st["note"], now_local() if st["done"] else "", aid, user["name"]))

    ex = conn.execute("SELECT id FROM daily_close WHERE person=? AND cdate=?", (user["name"], today)).fetchone()
    if not ex:
        conn.execute("INSERT INTO daily_close (person, cdate, closed_at) VALUES (?,?,?)",
                     (user["name"], today, now_local()))
        log_audit(conn, user["name"], "kunni yopdi", today)
    # Belgilangan vazifalar (galochka + qo'lda izoh) — bugungi to'plamni qayta yozamiz
    if raw is not None:
        conn.execute("DELETE FROM checklist_done WHERE person=? AND cdate=?", (user["name"], today))
        seen = set()
        for p in parsed:
            if p["id"] not in seen and (p["done"] or p["note"]):
                seen.add(p["id"])
                conn.execute(
                    "INSERT INTO checklist_done (person, cdate, item_id, done, note) VALUES (?,?,?,?,?)",
                    (user["name"], today, p["id"], p["done"], p["note"]))
    conn.commit()
    conn.close()
    return {"ok": True, "closedToday": True}


def api_reopen_day(user, b):
    """CEO xato yopilgan kunni qayta ochadi (bugungi belgilar ham tozalanadi)."""
    if user["role"] != "ceo":
        return {"error": "Ruxsat yo'q"}, 403
    person = (b.get("person") or "").strip()
    if person not in DAILY_CLOSE_USERS:
        return {"error": "Noto'g'ri xodim"}, 400
    today = uz_today().isoformat()
    conn = get_db()
    conn.execute("DELETE FROM daily_close WHERE person=? AND cdate=?", (person, today))
    conn.execute("DELETE FROM checklist_done WHERE person=? AND cdate=?", (person, today))
    conn.execute("UPDATE assigned_tasks SET done=0, done_at='' WHERE assignee=? AND tdate=?", (person, today))
    log_audit(conn, user["name"], "kunni qayta ochdi", f"{person} · {today}")
    conn.commit()
    conn.close()
    return {"ok": True, "closedToday": False}


def api_checklist_get(user, person):
    """Kishining cheklist shabloni (tahrirlash uchun) — CEO yoki o'zi."""
    person = person or user["name"]
    if not can_edit_checklist(user, person):
        return {"error": "Ruxsat yo'q"}, 403
    if person not in DAILY_CLOSE_USERS:
        return {"error": "Bu foydalanuvchida kun yopish yo'q"}, 400
    conn = get_db()
    items = [dict(r) for r in conn.execute(
        "SELECT id, text, sort FROM checklist_items WHERE person=? AND active=1 ORDER BY sort, id",
        (person,)).fetchall()]
    conn.close()
    return {"person": person, "items": items}


def api_checklist_add(user, b):
    person = (b.get("person") or user["name"]).strip()
    if not can_edit_checklist(user, person):
        return {"error": "Ruxsat yo'q"}, 403
    if person not in DAILY_CLOSE_USERS:
        return {"error": "Bu foydalanuvchida kun yopish yo'q"}, 400
    text = (b.get("text") or "").strip()
    if not text:
        return {"error": "Vazifa matni kerak"}, 400
    conn = get_db()
    mx = conn.execute("SELECT COALESCE(MAX(sort),0) AS m FROM checklist_items WHERE person=?", (person,)).fetchone()["m"]
    sql = "INSERT INTO checklist_items (person, text, sort, active) VALUES (?,?,?,1)"
    params = (person, text, (mx or 0) + 1)
    if IS_PG:
        iid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        iid = conn.execute(sql, params).lastrowid
    conn.commit()
    conn.close()
    return {"ok": True, "id": iid, "text": text}


def api_checklist_update(user, b):
    iid = b.get("id")
    text = (b.get("text") or "").strip()
    conn = get_db()
    row = conn.execute("SELECT person FROM checklist_items WHERE id=?", (iid,)).fetchone()
    if not row:
        conn.close()
        return {"error": "Topilmadi"}, 404
    if not can_edit_checklist(user, row["person"]):
        conn.close()
        return {"error": "Ruxsat yo'q"}, 403
    if not text:
        conn.close()
        return {"error": "Matn kerak"}, 400
    conn.execute("UPDATE checklist_items SET text=? WHERE id=?", (text, iid))
    conn.commit()
    conn.close()
    return {"ok": True}


def api_checklist_delete(user, b):
    iid = b.get("id")
    conn = get_db()
    row = conn.execute("SELECT person FROM checklist_items WHERE id=?", (iid,)).fetchone()
    if not row:
        conn.close()
        return {"error": "Topilmadi"}, 404
    if not can_edit_checklist(user, row["person"]):
        conn.close()
        return {"error": "Ruxsat yo'q"}, 403
    conn.execute("UPDATE checklist_items SET active=0 WHERE id=?", (iid,))
    conn.commit()
    conn.close()
    return {"ok": True}


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
            "❗️ Kun yopilmasa maoshdan −20 000 so'm ushlab qolinadi (har yopilmagan kun uchun)."
        )
    return {"ok": True, "notClosed": not_closed}


def api_cron_deadline_check():
    """Har ~soatda tashqi cron chaqiradi — montaj muddati yaqinlashgan/o'tgan
    videolar uchun bir marta Telegram eslatmasi yuboradi (deadline_reminded flag)."""
    conn = get_db()
    now = uz_now().replace(tzinfo=None)
    rows = conn.execute(
        "SELECT * FROM videos WHERE status IN ('biriktirildi','qaytarildi') "
        "AND (assigned_at IS NOT NULL AND assigned_at<>'' OR due_at IS NOT NULL) "
        "AND (deadline_reminded IS NULL OR deadline_reminded=0)"
    ).fetchall()
    warned, expired = [], []
    for r in rows:
        v = dict(r)
        vtype = v.get("vtype") or "reels"
        deadline = _video_deadline_dt(v)
        if not deadline:
            continue
        left = (deadline - now).total_seconds() / 3600.0
        if left > 2:
            continue  # hali erta — 2 soat qolganda ogohlantiramiz
        conn.execute("UPDATE videos SET deadline_reminded=1 WHERE id=?", (v["id"],))
        editor = v.get("editor") or "—"
        title = v.get("title") or "—"
        if left > 0:
            send_telegram(
                "⏰ <b>Muddat yaqinlashdi!</b>\n" + title + "\n"
                "👤 " + editor + "\n"
                "⏳ ~" + str(round(left, 1)) + " soat qoldi — tez montaj qiling!"
            )
            warned.append(title)
        else:
            note = ("kechiksa pul hisoblanmaydi" if vtype == "reels" else "kechiksa yarim pul")
            send_telegram(
                "🔴 <b>Muddat o'tdi!</b>\n" + title + "\n"
                "👤 " + editor + "\n"
                "(" + note + ")"
            )
            expired.append(title)
    conn.commit()
    conn.close()
    return {"ok": True, "warned": warned, "expired": expired}


def api_cron_morning_digest():
    """~09:00 da tashqi cron chaqiradi — jamoaga bugungi kun uchun qisqa digest yuboradi."""
    today = uz_today()
    if today.weekday() == 6:
        return {"ok": True, "skipped": "yakshanba"}
    tstr = today.isoformat()
    yesterday = (today - datetime.timedelta(days=1)).isoformat()
    conn = get_db()

    def _count(sql, params=()):
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else 0

    bookings = _count(
        "SELECT COUNT(*) FROM studio_bookings WHERE bdate=? "
        "AND (status IS NULL OR status<>'bekor_qilindi')", (tstr,))
    shoots = _count(
        "SELECT COUNT(*) FROM shoots WHERE sdate=? "
        "AND (status IS NULL OR status<>'bekor_qilindi')", (tstr,))
    montaj = _count("SELECT COUNT(*) FROM videos WHERE status IN ('biriktirildi','qaytarildi')")
    qc = _count("SELECT COUNT(*) FROM videos WHERE status='montaj_qilindi'")
    post = _count("SELECT COUNT(*) FROM videos WHERE status='qabul_qilindi'")

    # kecha kun yopmaganlar (ish kuni bo'lsa)
    not_closed = []
    if datetime.date.fromisoformat(yesterday).weekday() != 6:
        not_closed = [nm for nm in DAILY_CLOSE_USERS
                      if not conn.execute("SELECT id FROM daily_close WHERE person=? AND cdate=?",
                                          (nm, yesterday)).fetchone()]
    conn.close()

    lines = ["☀️ <b>Xayrli tong, Kadr jamoasi!</b>", "📅 " + tstr, ""]
    total_shoot = bookings + shoots
    if total_shoot:
        lines.append("🎥 Bugungi syomkalar: <b>" + str(total_shoot) + "</b>")
    lines.append("🎬 Montaj kutmoqda: <b>" + str(montaj) + "</b>")
    lines.append("🔎 Sifat nazorati: <b>" + str(qc) + "</b>")
    lines.append("📷 Joylashga tayyor: <b>" + str(post) + "</b>")
    if not_closed:
        lines.append("")
        lines.append("⚠️ Kecha kun yopmaganlar: <b>" + ", ".join(not_closed) + "</b>")
    lines.append("")
    lines.append("Kuningiz barakali o'tsin! 💪")
    send_telegram("\n".join(lines))
    return {"ok": True, "shoots": total_shoot, "montaj": montaj, "qc": qc,
            "post": post, "notClosed": not_closed}


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
        # Funksiya ({...}, kod) tuple qaytarsa — statusni ajratamiz (xato javoblari uchun).
        if isinstance(data, tuple) and len(data) == 2 and isinstance(data[1], int):
            data, code = data
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
        if path == "/api/cron/deadline-check":
            return self._json(api_cron_deadline_check())
        if path == "/api/cron/morning-digest":
            return self._json(api_cron_morning_digest())
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
        if path == "/api/my-tasks":
            return self._json(api_my_tasks(user))
        if path == "/api/qc":
            return self._forbid() if not is_qc_approver(user) else self._json(api_qc(user))
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
        if path == "/api/cashflow":
            return self._forbid() if role != "ceo" else self._json(api_cashflow(user))
        if path == "/api/advisor":
            return self._forbid() if role != "ceo" else self._json(api_advisor(user))
        if path == "/api/late-videos":
            return self._forbid() if role != "ceo" else self._json(api_late_videos(user))
        if path == "/api/archives":
            return self._forbid() if role != "ceo" else self._json(api_archives(user))
        if path == "/api/archive":
            ym = (parse_qs(urlparse(self.path).query).get("ym") or [""])[0]
            return self._forbid() if role != "ceo" else self._json(api_archive_get(user, ym))
        if path == "/api/income-ledger":
            return self._forbid() if role != "ceo" else self._json(api_income_ledger(user))
        if path == "/api/studio":
            return self._forbid() if not can_view_studio(user) else self._json(api_studio(user))
        if path == "/api/studio/finance":
            return self._forbid() if not can_edit_studio(user) else self._json(api_studio_finance(user))
        if path == "/api/studio/expenses":
            return self._forbid() if not can_edit_studio(user) else self._json(api_studio_expenses(user))
        if path == "/api/budget":
            if role != "ceo" and not _is_budget_user(user["name"]):
                return self._forbid()
            return self._json(api_budget(user))
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
        if path == "/api/checklist":
            person = (parse_qs(urlparse(self.path).query).get("person") or [""])[0]
            return self._json(api_checklist_get(user, person))
        if path == "/api/tasks":
            q = parse_qs(urlparse(self.path).query)
            return self._json(api_assigned_list(user, (q.get("person") or [""])[0], (q.get("date") or [""])[0]))
        if path == "/api/month-stats":
            if role not in APPROVER_ROLES:
                return self._forbid()
            ym = (parse_qs(urlparse(self.path).query).get("ym") or [""])[0]
            return self._json(api_month_stats(user, ym))
        if path == "/api/shoot-stats":
            ym = (parse_qs(urlparse(self.path).query).get("ym") or [""])[0]
            return self._json(api_shoot_stats(user, ym))
        if path == "/api/leaderboard":
            if role not in APPROVER_ROLES:
                return self._forbid()
            return self._json(api_leaderboard(user))
        if path == "/api/charity":
            return self._forbid() if not is_charity_user(user) else self._json(api_charity(user))
        if path == "/api/attendance":
            if not is_attend_user(user) and role != "ceo":
                return self._forbid()
            return self._json(api_attendance(user))
        if path == "/api/smm":
            if not is_smm_user(user) and role != "ceo":
                return self._forbid()
            return self._json(api_smm(user))
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
        if path == "/api/projects/reset-stats":
            return self._json(api_reset_project_stats(user))
        if path == "/api/archive":
            return self._json(api_archive_month(user))
        if path == "/api/editors/recompute":
            return self._json(api_recompute_editor(user, (b.get("editor") or "").strip()))
        if path == "/api/videos/backfill":
            return self._json(api_backfill_videos(user, b))
        if path == "/api/videos/set-project":
            return self._json(api_set_video_project(user, b))
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
        if path == "/api/cashflow/pay":
            if r != "ceo":
                return self._forbid()
            return self._json(api_mark_client_payment(user, b))
        if path == "/api/studio":
            if not can_edit_studio(user):
                return self._forbid()
            return self._json(api_create_studio_booking(user, b), 201)
        if path == "/api/studio/expenses":
            if not can_edit_studio(user):
                return self._forbid()
            return self._json(api_create_studio_expense(user, b), 201)
        if path == "/api/budget/set":
            if r != "ceo":
                return self._forbid()
            return self._json(api_set_budget(user, b))
        if path == "/api/budget/delete":
            if r != "ceo":
                return self._forbid()
            return self._json(api_delete_budget(user, b))
        if path == "/api/budget/spend":
            return self._json(api_budget_spend(user, b))
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
            return self._json(api_close_day(user, b))
        if path == "/api/daily/reopen":
            return self._json(api_reopen_day(user, b))
        if path == "/api/checklist/add":
            return self._json(api_checklist_add(user, b))
        if path == "/api/checklist/update":
            return self._json(api_checklist_update(user, b))
        if path == "/api/checklist/delete":
            return self._json(api_checklist_delete(user, b))
        if path == "/api/tasks/assign":
            return self._json(api_assign_task(user, b))
        if path == "/api/attendance/checkin":
            if not is_attend_user(user):
                return self._forbid()
            return self._json(api_checkin(user))
        if path == "/api/smm/toggle":
            if not is_smm_user(user):
                return self._forbid()
            return self._json(api_smm_toggle(user, b))
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
        if len(seg) == 4 and seg[1] == "videos" and seg[3] == "restore-pay":
            vid = self._int(seg[2])
            return self._json(api_restore_video_pay(user, vid)) if vid else self._json({"error": "Topilmadi"}, 404)
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
        if len(seg) == 3 and seg[1] == "videos":
            vid = self._int(seg[2])
            if vid is None:
                return self._json({"error": "Topilmadi"}, 404)
            row = api_update_video(user, vid, b)
            return self._json(row) if row else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 3 and seg[1] == "scripts":
            sid = self._int(seg[2])
            if sid is None:
                return self._json({"error": "Topilmadi"}, 404)
            row = api_update_script(user, sid, b)
            return self._json(row) if row else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 3 and seg[1] == "studio":
            if not can_edit_studio(user):
                return self._forbid()
            bid = self._int(seg[2])
            if bid is None:
                return self._json({"error": "Topilmadi"}, 404)
            row = api_update_studio_booking(user, bid, b)
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
            if r not in ADMIN_ROLES:
                return self._forbid()
            vid = self._int(seg[2])
            return self._json(api_delete_video(user, vid)) if vid else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 3 and seg[1] == "tasks":
            tid = self._int(seg[2])
            return self._json(api_delete_assigned_task(user, tid)) if tid else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 3 and seg[1] == "income":
            lid = self._int(seg[2])
            return self._json(api_delete_income(user, lid)) if lid else self._json({"error": "Topilmadi"}, 404)
        if len(seg) == 3 and seg[1] == "payments":
            pid = self._int(seg[2])
            return self._json(api_delete_payment(user, pid)) if pid else self._json({"error": "Topilmadi"}, 404)
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

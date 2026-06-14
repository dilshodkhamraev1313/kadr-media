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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DB_PATH = os.path.join(BASE_DIR, "kadr-media.db")
PORT = int(os.environ.get("PORT", 3000))

# Internetda (Render) DATABASE_URL beriladi → Postgres (Neon) ishlatiladi.
# Mahalliy kompyuterda esa SQLite fayli ishlatiladi (hech narsa o'rnatish shart emas).
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
IS_PG = DATABASE_URL.startswith("postgres")

STAGES = ["ssenariy", "syomka", "montaj", "tasdiq", "joylash"]
STATUSES = ["kutilmoqda", "jarayonda", "tayyor"]


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

        today = datetime.date.today()
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
    conn.close()


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
            days_left = (dl - datetime.date.today()).days
            overdue = (not p["fullyDone"]) and days_left < 0
        except ValueError:
            pass
    p["daysLeft"] = days_left
    p["overdue"] = overdue

    has_problem = bool((p.get("muammo") or "").strip())
    p["atRisk"] = (not p["fullyDone"]) and (
        (days_left is not None and days_left <= 2 and p["progress"] < 60) or has_problem
    )
    return p


def now_local():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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

    conn = get_db()
    sql = """INSERT INTO projects
           (name,client,responsible,ssenariy,syomka,montaj,tasdiq,joylash,deadline,muammo,izoh)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)"""
    params = (
        b.get("name") or "Nomsiz loyiha", b.get("client") or "",
        b.get("responsible") or "", st(b.get("ssenariy")), st(b.get("syomka")),
        st(b.get("montaj")), st(b.get("tasdiq")), st(b.get("joylash")),
        b.get("deadline") or None, b.get("muammo") or "", b.get("izoh") or "",
    )
    if IS_PG:
        pid = conn.execute(sql + " RETURNING id", params).fetchone()["id"]
    else:
        pid = conn.execute(sql, params).lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    conn.close()
    return decorate(row)


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

    merged = {
        "name": b.get("name", existing["name"]),
        "client": b.get("client", existing["client"]),
        "responsible": b.get("responsible", existing["responsible"]),
        "ssenariy": pick("ssenariy"), "syomka": pick("syomka"),
        "montaj": pick("montaj"), "tasdiq": pick("tasdiq"), "joylash": pick("joylash"),
        "deadline": b["deadline"] if "deadline" in b else existing["deadline"],
        "muammo": b.get("muammo", existing["muammo"]),
        "izoh": b.get("izoh", existing["izoh"]),
    }

    # Faollik jurnali — qaysi bosqich "tayyor" bo'ldi
    for s in STAGES:
        if merged[s] != existing[s] and merged[s] == "tayyor":
            conn.execute(
                "INSERT INTO activity (project_id,project_name,stage,status,actor,created_at) VALUES (?,?,?,?,?,?)",
                (pid, merged["name"], s, "tayyor", actor, now_local()),
            )

    conn.execute(
        """UPDATE projects SET name=?,client=?,responsible=?,ssenariy=?,syomka=?,montaj=?,
           tasdiq=?,joylash=?,deadline=?,muammo=?,izoh=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
        (
            merged["name"], merged["client"], merged["responsible"], merged["ssenariy"],
            merged["syomka"], merged["montaj"], merged["tasdiq"], merged["joylash"],
            merged["deadline"], merged["muammo"], merged["izoh"], pid,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    conn.close()
    return decorate(row)


def api_delete_project(pid):
    conn = get_db()
    conn.execute("DELETE FROM projects WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return {"ok": True}


def api_stats():
    rows = api_projects()
    total = len(rows)
    completed = sum(1 for p in rows if p["fullyDone"])
    overdue = sum(1 for p in rows if p["overdue"])
    at_risk = sum(1 for p in rows if p["atRisk"])

    conn = get_db()
    today = datetime.date.today().isoformat()
    today_tasks = conn.execute(
        "SELECT COUNT(*) AS n FROM activity WHERE substr(created_at,1,10)=?", (today,)
    ).fetchone()["n"]
    leads = conn.execute(
        "SELECT name FROM users WHERE role IN ('lead','coordinator')"
    ).fetchall()
    recent = conn.execute(
        "SELECT * FROM activity ORDER BY id DESC LIMIT 15"
    ).fetchall()
    conn.close()

    workload = []
    for u in leads:
        mine = [p for p in rows if p["responsible"] == u["name"]]
        workload.append({
            "name": u["name"], "total": len(mine),
            "active": sum(1 for p in mine if not p["fullyDone"]),
            "overdue": sum(1 for p in mine if p["overdue"]),
            "atRisk": sum(1 for p in mine if p["atRisk"]),
        })

    return {
        "total": total, "active": total - completed, "completed": completed,
        "overdue": overdue, "atRisk": at_risk, "todayTasks": today_tasks,
        "workload": workload, "recent": [dict(r) for r in recent],
    }


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

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/users":
            return self._json(api_users())
        if path == "/api/clients":
            return self._json(api_clients())
        if path == "/api/projects":
            return self._json(api_projects())
        if path == "/api/stats":
            return self._json(api_stats())
        if path.startswith("/api/projects/"):
            pid = self._pid(path)
            if pid is None:
                return self._json({"error": "Topilmadi"}, 404)
            row = api_get_project(pid)
            return self._json(row) if row else self._json({"error": "Topilmadi"}, 404)
        if path.startswith("/api/"):
            return self._json({"error": "Topilmadi"}, 404)
        return self._serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/projects":
            return self._json(api_create_project(self._body()), 201)
        return self._json({"error": "Topilmadi"}, 404)

    def do_PUT(self):
        path = urlparse(self.path).path
        if path.startswith("/api/projects/"):
            pid = self._pid(path)
            if pid is None:
                return self._json({"error": "Topilmadi"}, 404)
            row = api_update_project(pid, self._body())
            return self._json(row) if row else self._json({"error": "Topilmadi"}, 404)
        return self._json({"error": "Topilmadi"}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path.startswith("/api/projects/"):
            pid = self._pid(path)
            if pid is None:
                return self._json({"error": "Topilmadi"}, 404)
            return self._json(api_delete_project(pid))
        return self._json({"error": "Topilmadi"}, 404)

    @staticmethod
    def _pid(path):
        try:
            return int(path.rsplit("/", 1)[-1])
        except ValueError:
            return None

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

# ============================================================
#  Web yordamchilari: multipart/form-data ni o'qish (fayl yuklash)
#  Standart kutubxonali HTTP server uchun yengil parser.
#  (cgi moduli Python 3.13'da olib tashlangani uchun o'zimiz yozamiz.)
# ============================================================

import os
import re
import uuid


MAX_UPLOAD = 800 * 1024 * 1024   # 800 MB umumiy chegara (prototip)
ALLOWED_VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
ALLOWED_AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}


def parse_multipart(body, content_type):
    """
    body — to'liq so'rov tanasi (bytes).
    content_type — 'multipart/form-data; boundary=...'
    Qaytaradi: {"fields": {name: str}, "files": [{"field","filename","data"}]}
    """
    m = re.search(r"boundary=([^;]+)", content_type or "")
    if not m:
        raise ValueError("boundary topilmadi")
    boundary = m.group(1).strip().strip('"').encode()
    delim = b"--" + boundary

    fields, files = {}, []
    # qismlarga ajratamiz
    for part in body.split(delim):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        if b"\r\n\r\n" not in part:
            continue
        raw_head, data = part.split(b"\r\n\r\n", 1)
        head = raw_head.decode("utf-8", "replace")

        name = _header_param(head, "name")
        filename = _header_param(head, "filename")
        if name is None:
            continue
        if filename:
            files.append({"field": name, "filename": filename, "data": data})
        else:
            fields[name] = data.decode("utf-8", "replace").strip()

    return {"fields": fields, "files": files}


def _header_param(head, key):
    m = re.search(rf'{key}="([^"]*)"', head)
    return m.group(1) if m else None


def save_uploads(files, dest_dir):
    """
    Yuklangan fayllarni diskka saqlaydi. Video va musiqa fayllarini ajratadi.
    Qaytaradi: {"videos": [path...], "music": path|None, "reference": path|None}
    """
    os.makedirs(dest_dir, exist_ok=True)
    videos, music, reference = [], None, None

    for f in files:
        ext = os.path.splitext(f["filename"])[1].lower()
        safe = uuid.uuid4().hex[:8] + ext
        path = os.path.join(dest_dir, safe)

        field = f["field"]
        if field == "music" and ext in ALLOWED_AUDIO:
            with open(path, "wb") as out:
                out.write(f["data"])
            music = path
        elif field == "reference" and ext in ALLOWED_VIDEO:
            with open(path, "wb") as out:
                out.write(f["data"])
            reference = path
        elif ext in ALLOWED_VIDEO:        # field == "videos" yoki boshqa
            with open(path, "wb") as out:
                out.write(f["data"])
            videos.append(path)
        # ruxsatsiz kengaytmalar jim o'tkazib yuboriladi

    return {"videos": videos, "music": music, "reference": reference}

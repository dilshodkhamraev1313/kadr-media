# ============================================================
#  Montaj vazifalari (jobs) menejeri — web uchun
#  Yuklangan videolar fonda (background thread) montaj qilinadi.
#  Holat: queued → processing → done / error.
#  Eslatma: bu prototip xotirada saqlaydi (server qayta ishga
#  tushsa, vazifalar ro'yxati yo'qoladi — tayyor fayllar diskda qoladi).
# ============================================================

import os
import threading
import time
import uuid

from .engine import auto_edit, EditOptions
from .styles import get_style, derived_from_reference
from .analyze import analyze_reference


class JobManager:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.jobs = {}
        self.lock = threading.Lock()
        os.makedirs(base_dir, exist_ok=True)

    def create(self, inputs, style_name=None, reference=None, music=None,
               language="uz", title=None):
        """Yangi montaj vazifasini yaratadi va fonda boshlaydi."""
        job_id = uuid.uuid4().hex[:12]
        out_dir = os.path.join(self.base_dir, job_id)
        os.makedirs(out_dir, exist_ok=True)
        output = os.path.join(out_dir, "tayyor.mp4")

        job = {
            "id": job_id,
            "title": title or "Montaj",
            "status": "queued",
            "progress": "Navbatda…",
            "created": time.time(),
            "output": output,
            "download_ready": False,
            "error": None,
            "result": None,
            "warnings": [],
        }
        with self.lock:
            self.jobs[job_id] = job

        t = threading.Thread(
            target=self._run,
            args=(job_id, inputs, style_name, reference, music, language, output),
            daemon=True,
        )
        t.start()
        return self.public(job_id)

    def _run(self, job_id, inputs, style_name, reference, music, language, output):
        def progress(msg):
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id]["progress"] = msg
                    self.jobs[job_id]["status"] = "processing"

        try:
            # referens berilgan bo'lsa — undan stil chiqaramiz
            if reference and os.path.isfile(reference):
                progress("Referens video tahlil qilinmoqda…")
                analysis = analyze_reference(reference)
                style = derived_from_reference(analysis, base=style_name or "trend_fast")
            else:
                style = get_style(style_name)

            opts = EditOptions(
                inputs=inputs, style=style, output=output,
                music=music, language=language,
            )
            result = auto_edit(opts, progress=progress)

            with self.lock:
                j = self.jobs[job_id]
                j["status"] = "done"
                j["progress"] = "Tayyor ✅"
                j["download_ready"] = True
                j["warnings"] = result.warnings
                j["result"] = {
                    "duration": result.duration,
                    "segments": result.segments,
                    "subtitled": result.subtitled,
                }
        except Exception as e:  # noqa: BLE001 — foydalanuvchiga xabar berish uchun
            with self.lock:
                j = self.jobs[job_id]
                j["status"] = "error"
                j["error"] = str(e)
                j["progress"] = "Xatolik"
        finally:
            # kirish fayllarini tozalaymiz (tayyor video qoladi)
            for p in inputs + ([music] if music else []) + ([reference] if reference else []):
                try:
                    if p and os.path.isfile(p) and self.base_dir in os.path.abspath(p):
                        os.remove(p)
                except OSError:
                    pass

    def public(self, job_id):
        """Frontend uchun xavfsiz holat (ichki yo'llarsiz)."""
        with self.lock:
            j = self.jobs.get(job_id)
            if not j:
                return None
            return {
                "id": j["id"], "title": j["title"], "status": j["status"],
                "progress": j["progress"], "download_ready": j["download_ready"],
                "error": j["error"], "result": j["result"],
                "warnings": j["warnings"],
            }

    def output_path(self, job_id):
        with self.lock:
            j = self.jobs.get(job_id)
            if j and j["download_ready"] and os.path.isfile(j["output"]):
                return j["output"]
        return None

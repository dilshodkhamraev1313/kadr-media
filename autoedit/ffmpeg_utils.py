# ============================================================
#  ffmpeg / ffprobe yordamchilari
#  Dvigatel video ishlash uchun tizimdagi ffmpeg'ni chaqiradi.
#  ffmpeg sizning serveringizda o'rnatilgan bo'lishi kerak.
# ============================================================

import json
import shutil
import subprocess


class FfmpegError(RuntimeError):
    """ffmpeg chaqiruvi xato bilan tugaganda."""


def have(tool):
    """Tizimda dastur bor-yo'qligini tekshiradi (ffmpeg/ffprobe)."""
    return shutil.which(tool) is not None


def tools_status():
    """
    Qaysi vositalar mavjudligini qaytaradi. Frontend/diagnostika uchun.
    whisper va librosa ixtiyoriy — bo'lmasa subtitr/beat o'tkazib yuboriladi.
    """
    status = {
        "ffmpeg": have("ffmpeg"),
        "ffprobe": have("ffprobe"),
        "whisper": _module_exists("faster_whisper") or _module_exists("whisper"),
        "librosa": _module_exists("librosa"),
        "pillow": _module_exists("PIL"),
    }
    status["ready"] = status["ffmpeg"] and status["ffprobe"]
    return status


def _module_exists(name):
    import importlib.util
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def run(cmd, timeout=3600):
    """ffmpeg/ffprobe buyrug'ini ishga tushiradi. Xato bo'lsa FfmpegError."""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise FfmpegError(f"Dastur topilmadi: {cmd[0]} — ffmpeg o'rnatilganmi?") from e
    except subprocess.TimeoutExpired as e:
        raise FfmpegError("ffmpeg vaqt chegarasidan oshib ketdi.") from e
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace")[-1500:]
        raise FfmpegError(f"ffmpeg xatosi (kod {proc.returncode}):\n{tail}")
    return proc


def probe(path):
    """
    Video haqida ma'lumot: davomiyligi, o'lchami, fps, ovozi bor-yo'qligi.
    """
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    out = run(cmd, timeout=120).stdout.decode("utf-8", "replace")
    data = json.loads(out)

    info = {"path": path, "duration": 0.0, "width": 0, "height": 0,
            "fps": 0.0, "has_audio": False, "has_video": False}

    try:
        info["duration"] = float(data.get("format", {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        pass

    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and not info["has_video"]:
            info["has_video"] = True
            info["width"] = int(s.get("width") or 0)
            info["height"] = int(s.get("height") or 0)
            info["fps"] = _parse_fps(s.get("avg_frame_rate") or s.get("r_frame_rate"))
            if not info["duration"]:
                try:
                    info["duration"] = float(s.get("duration") or 0.0)
                except (TypeError, ValueError):
                    pass
        elif s.get("codec_type") == "audio":
            info["has_audio"] = True

    return info


def _parse_fps(rate):
    """'30000/1001' kabi kasrli fpsни floatga aylantiradi."""
    if not rate:
        return 0.0
    try:
        if "/" in rate:
            num, den = rate.split("/")
            den = float(den)
            return float(num) / den if den else 0.0
        return float(rate)
    except (ValueError, ZeroDivisionError):
        return 0.0


def detect_silence(path, noise_db=-30, min_dur=0.5):
    """
    Sukunat (gapsiz) oraliqlarni topadi: [(start, end), ...].
    ffmpeg silencedetect filtridan foydalanadi.
    """
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", path,
        "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}",
        "-f", "null", "-",
    ]
    # silencedetect natijasi stderr'ga chiqadi
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=600)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    text = proc.stderr.decode("utf-8", "replace")

    silences = []
    start = None
    for line in text.splitlines():
        line = line.strip()
        if "silence_start:" in line:
            try:
                start = float(line.split("silence_start:")[1].strip())
            except (ValueError, IndexError):
                start = None
        elif "silence_end:" in line and start is not None:
            try:
                end = float(line.split("silence_end:")[1].split("|")[0].strip())
                silences.append((start, end))
            except (ValueError, IndexError):
                pass
            start = None
    return silences

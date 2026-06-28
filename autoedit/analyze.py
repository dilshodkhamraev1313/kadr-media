# ============================================================
#  Referens video tahlili
#  Siz bergan namuna videodan montaj "retsepti"ni o'qib oladi:
#   - kadr ritmi (o'rtacha kesim uzunligi) — scene detection orqali
#   - musiqa tempi (BPM) — librosa bo'lsa
#   - rang to'yinganligi — Pillow/numpy bo'lsa
#  Natija styles.derived_from_reference() ga beriladi.
# ============================================================

import subprocess

from .ffmpeg_utils import probe, have


def analyze_reference(path):
    """Referens videodan o'lchanadigan stil belgilarini qaytaradi."""
    result = {"shot_len": None, "tempo": None, "saturation": None,
              "duration": None, "notes": []}

    if not have("ffmpeg"):
        result["notes"].append("ffmpeg yo'q — referens tahlil qilinmadi.")
        return result

    info = probe(path)
    result["duration"] = info["duration"]

    shot = _avg_shot_length(path, info["duration"])
    if shot:
        result["shot_len"] = shot
    else:
        result["notes"].append("Kadr ritmi aniqlanmadi.")

    tempo = _tempo(path) if info["has_audio"] else None
    if tempo:
        result["tempo"] = tempo

    sat = _saturation(path)
    if sat:
        result["saturation"] = sat

    return result


def _avg_shot_length(path, duration):
    """
    Scene detection: kadr almashish sonini sanaб, o'rtacha kesim uzunligini
    chiqaradi. ffmpeg 'select=gt(scene,...)' + showinfo dan foydalanadi.
    """
    if not duration or duration <= 0:
        return None
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", path,
        "-filter:v", "select='gt(scene,0.35)',showinfo",
        "-f", "null", "-",
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=600)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    text = proc.stderr.decode("utf-8", "replace")
    scene_changes = text.count("pts_time:")
    cuts = scene_changes + 1  # N ta kesim chizig'i → N+1 ta kadr
    if cuts <= 0:
        return None
    return round(duration / cuts, 2)


def _tempo(path):
    """Musiqa tempini (BPM) librosa orqali o'lchaydi (bo'lsa)."""
    try:
        import librosa
    except ImportError:
        return None
    try:
        # avval audioni vaqtinchalik wav'ga ajratamiz
        import tempfile
        import os
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-nostats", "-i", path,
             "-vn", "-ac", "1", "-ar", "22050", tmp.name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
        )
        y, sr = librosa.load(tmp.name, sr=22050, mono=True)
        os.unlink(tmp.name)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        return round(float(tempo), 1)
    except Exception:
        return None


def _saturation(path):
    """
    Bir nechta kadrdan o'rtacha to'yinganlikni baholaydi (1.0 = neytral).
    Pillow + numpy bo'lsa ishlaydi, bo'lmasa None.
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return None
    try:
        import tempfile
        import os
        import glob
        d = tempfile.mkdtemp()
        # videodan har 2 soniyada bitta kadr olamiz
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-nostats", "-i", path,
             "-vf", "fps=1/2,scale=160:-1", os.path.join(d, "f%03d.jpg")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
        )
        sats = []
        for f in sorted(glob.glob(os.path.join(d, "*.jpg")))[:20]:
            img = np.asarray(Image.open(f).convert("HSV"), dtype="float32")
            sats.append(img[:, :, 1].mean() / 255.0)
            os.unlink(f)
        os.rmdir(d)
        if not sats:
            return None
        avg = sum(sats) / len(sats)
        # 0.45 ni neytral (1.0) deb hisoblaymiz, nisbat sifatida qaytaramiz
        return round(avg / 0.45, 2)
    except Exception:
        return None

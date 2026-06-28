# ============================================================
#  Avtomatik montaj dvigateli — asosiy quvur (pipeline)
#  Bosqichlar:
#   1) Isxodniklarni o'lchash (probe)
#   2) Sukunatni kesib, "kerakli" bo'laklarni tanlash
#   3) Stil ritmiga ko'ra timeline yig'ish (+max uzunlik)
#   4) Qora montaj (rough cut): 9:16 kadrlash, rang, musiqa
#   5) Avto-subtitr (Whisper) → ASS
#   6) Subtitrni videoga "kuydirish" → tayyor video
# ============================================================

import os
import random
import shutil
import tempfile
from dataclasses import dataclass, field

from . import ffmpeg_utils as ff
from . import subtitles as subs
from .styles import get_style


@dataclass
class EditOptions:
    inputs: list                      # isxodnik video fayllar (yo'llar)
    style: dict                       # styles.get_style(...) natijasi
    output: str                       # tayyor video yo'li
    music: str = None                 # fon musiqa (ixtiyoriy)
    language: str = "uz"              # subtitr tili
    whisper_model: str = "small"      # Whisper model o'lchami
    seed: int = 42                    # takrorlanadigan tasodifiylik uchun
    workdir: str = None               # vaqtinchalik papka (yo'q bo'lsa yaratiladi)


@dataclass
class EditResult:
    output: str
    duration: float
    segments: int
    subtitled: bool
    warnings: list = field(default_factory=list)


def _noop(msg):
    pass


def auto_edit(opts: EditOptions, progress=None):
    """
    Asosiy kirish nuqtasi. progress(msg) — bosqichlar haqida xabar beruvchi
    ixtiyoriy callback (web job uchun).
    """
    progress = progress or _noop
    if not ff.have("ffmpeg") or not ff.have("ffprobe"):
        raise ff.FfmpegError(
            "ffmpeg/ffprobe topilmadi. Serverda o'rnating: "
            "Ubuntu — 'apt install ffmpeg', Mac — 'brew install ffmpeg'."
        )
    if not opts.inputs:
        raise ValueError("Hech qanday isxodnik video berilmadi.")

    rnd = random.Random(opts.seed)
    warnings = []
    own_workdir = opts.workdir is None
    workdir = opts.workdir or tempfile.mkdtemp(prefix="kadr_montaj_")

    try:
        # 1) o'lchash
        progress("Isxodniklar o'lchanmoqda…")
        probes = []
        for p in opts.inputs:
            if not os.path.isfile(p):
                warnings.append(f"Fayl topilmadi, o'tkazib yuborildi: {p}")
                continue
            info = ff.probe(p)
            if not info["has_video"]:
                warnings.append(f"Video oqimi yo'q, o'tkazib yuborildi: {p}")
                continue
            probes.append(info)
        if not probes:
            raise ValueError("Yaroqli video topilmadi.")

        # 2) bo'laklarni tanlash (sukunatni kesish)
        progress("Bo'sh va sukunatli joylar kesilmoqda…")
        takes = _select_takes(probes, opts.style)

        # 3) ritmga ko'ra timeline
        progress("Montaj ritmi yig'ilmoqda…")
        segments = _plan_timeline(takes, opts.style, rnd)
        if not segments:
            raise ValueError("Montaj uchun yetarli material topilmadi.")

        # 4) qora montaj (rough cut)
        progress(f"Qora montaj render qilinmoqda ({len(segments)} kadr)…")
        rough = os.path.join(workdir, "rough.mp4")
        total = _render_rough(segments, opts, rough)

        # 5) + 6) subtitr
        subtitled = False
        if subs.available():
            progress("Nutq matnga aylantirilmoqda (subtitr)…")
            tr = subs.transcribe(rough, language=opts.language,
                                 model_size=opts.whisper_model)
            if tr:
                ass_path = os.path.join(workdir, "subs.ass")
                with open(ass_path, "w", encoding="utf-8") as f:
                    f.write(subs.build_ass(tr, opts.style["subtitle"]))
                progress("Subtitr videoga qo'shilmoqda…")
                _burn_subtitles(rough, ass_path, opts.output, opts.style)
                subtitled = True
            else:
                warnings.append("Nutq aniqlanmadi — subtitrsiz chiqdi.")
                shutil.move(rough, opts.output)
        else:
            warnings.append(
                "Whisper o'rnatilmagan — subtitrsiz chiqdi. "
                "O'rnatish: pip install faster-whisper"
            )
            shutil.move(rough, opts.output)

        progress("Tayyor ✅")
        return EditResult(
            output=opts.output,
            duration=round(total, 2),
            segments=len(segments),
            subtitled=subtitled,
            warnings=warnings,
        )
    finally:
        if own_workdir and os.path.isdir(workdir):
            shutil.rmtree(workdir, ignore_errors=True)


# ---------- bosqich yordamchilari ----------

def _select_takes(probes, style):
    """
    Har bir klipdan saqlanadigan oraliqlarni qaytaradi:
    [{"path","start","end","has_audio","dur"}]. Sukunat kesiladi.
    """
    takes = []
    for info in probes:
        dur = info["duration"]
        if dur <= 0:
            continue
        keeps = [(0.0, dur)]
        if style.get("remove_silence") and info["has_audio"]:
            sil = ff.detect_silence(
                info["path"],
                noise_db=style.get("silence_db", -30),
                min_dur=style.get("silence_min", 0.5),
            )
            if sil:
                keeps = _invert_ranges(sil, dur)
        for (s, e) in keeps:
            if e - s < 0.4:        # juda qisqa bo'laklarni tashlaymiz
                continue
            takes.append({"path": info["path"], "start": s, "end": e,
                          "has_audio": info["has_audio"], "dur": e - s})
    return takes


def _invert_ranges(silences, total):
    """Sukunat oraliqlaridan 'gapli' (saqlanadigan) oraliqlarni chiqaradi."""
    keeps, cur = [], 0.0
    for (s, e) in sorted(silences):
        if s - cur > 0.25:
            keeps.append((cur, s))
        cur = max(cur, e)
    if total - cur > 0.25:
        keeps.append((cur, total))
    return keeps


def _plan_timeline(takes, style, rnd):
    """
    Tanlangan bo'laklarni stil ritmiga (shot_len) bo'lib, max_duration'gacha
    timeline yig'adi. Uzun bo'laklar shot_len bo'yicha bo'linadi.
    """
    shot = style.get("shot_len", 2.0)
    jitter = style.get("shot_len_jitter", 0.0)
    max_dur = style.get("max_duration", 60)
    zoom = style.get("punch_zoom", False)

    segments, total = [], 0.0
    for t in takes:
        pos = t["start"]
        while pos < t["end"] - 0.2:
            target = shot + (rnd.uniform(-jitter, jitter) if jitter else 0)
            target = max(0.7, target)
            seg_end = min(pos + target, t["end"])
            if seg_end - pos < 0.5:        # qoldiq juda qisqa — to'liq olamiz
                seg_end = t["end"]
            if total + (seg_end - pos) > max_dur:
                seg_end = pos + (max_dur - total)
            if seg_end - pos < 0.4:
                break
            segments.append({
                "path": t["path"], "start": round(pos, 3),
                "end": round(seg_end, 3), "has_audio": t["has_audio"],
                "zoom": zoom,
            })
            total += seg_end - pos
            pos = seg_end
            if total >= max_dur:
                return segments
    return segments


# ---------- render ----------

def _render_rough(segments, opts, out_path):
    """Barcha bo'laklarni bitta filtergraph bilan birlashtirib render qiladi."""
    style = opts.style
    fps = style.get("fps", 30)
    color = style.get("color", "")
    total = sum(s["end"] - s["start"] for s in segments)

    cmd = ["ffmpeg", "-y", "-hide_banner", "-nostats"]
    filt = []
    vlabels, alabels = [], []
    idx = 0

    for n, seg in enumerate(segments):
        # har bir bo'lak uchun faylni alohida ochamiz (split shart emas)
        cmd += ["-ss", f"{seg['start']:.3f}", "-to", f"{seg['end']:.3f}",
                "-i", seg["path"]]
        vchain = (
            f"[{idx}:v]setpts=PTS-STARTPTS,"
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1,fps={fps}"
        )
        if color:
            vchain += f",{color}"
        if seg.get("zoom"):
            # xavfsiz statik zoom (8%) — har kadrga ozgina jonlilik
            vchain += ",scale=iw*1.08:ih*1.08,crop=1080:1920"
        vchain += f"[v{n}]"
        filt.append(vchain)
        vlabels.append(f"[v{n}]")

        if seg["has_audio"]:
            filt.append(f"[{idx}:a]asetpts=PTS-STARTPTS[a{n}]")
        else:
            # ovozsiz klip uchun jim audio yasaymiz
            dur = seg["end"] - seg["start"]
            filt.append(
                f"anullsrc=r=44100:cl=stereo,atrim=0:{dur:.3f},"
                f"asetpts=PTS-STARTPTS[a{n}]"
            )
        alabels.append(f"[a{n}]")
        idx += 1

    # birlashtirish (concat)
    concat_in = "".join(v + a for v, a in zip(vlabels, alabels))
    filt.append(f"{concat_in}concat=n={len(segments)}:v=1:a=1[vc][ac]")

    # musiqa (ixtiyoriy) — gap ustidan past balandlikda aralashtiramiz
    aout = "[ac]"
    if opts.music and os.path.isfile(opts.music):
        cmd += ["-stream_loop", "-1", "-i", opts.music]
        mus_idx = idx
        mv = style.get("music_volume", 0.2)
        filt.append(
            f"[{mus_idx}:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
            f"volume={mv}[mus]"
        )
        filt.append(
            "[ac][mus]amix=inputs=2:duration=first:dropout_transition=2:"
            "normalize=0[aout]"
        )
        aout = "[aout]"

    cmd += [
        "-filter_complex", ";".join(filt),
        "-map", "[vc]", "-map", aout,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        out_path,
    ]
    ff.run(cmd)
    return total


def _burn_subtitles(in_path, ass_path, out_path, style):
    """ASS subtitrni videoga kuydiradi (qayta kodlash)."""
    # ffmpeg subtitles filtri uchun yo'lni ekranlash
    safe = ass_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    fps = style.get("fps", 30)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-nostats", "-i", in_path,
        "-vf", f"subtitles='{safe}'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "copy",
        "-movflags", "+faststart",
        out_path,
    ]
    ff.run(cmd)

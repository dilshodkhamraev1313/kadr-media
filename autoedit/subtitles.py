# ============================================================
#  Avto-subtitr: nutqni matnga aylantirib (Whisper), trenddagi
#  "so'zma-so'z" (karaoke) ASS subtitr fayli yasaydi.
#  faster-whisper yoki whisper o'rnatilmagan bo'lsa — jim o'tib ketadi
#  (subtitrsiz montaj baribir chiqadi).
# ============================================================


def available():
    import importlib.util
    for name in ("faster_whisper", "whisper"):
        try:
            if importlib.util.find_spec(name) is not None:
                return True
        except (ImportError, ValueError):
            continue
    return False


def transcribe(audio_or_video_path, language="uz", model_size="small"):
    """
    Videodan so'zlarni vaqt belgilari bilan oladi.
    Natija: [{"start":s,"end":e,"words":[{"w":..,"start":..,"end":..}]}, ...]
    Hech narsa topilmasa yoki Whisper yo'q bo'lsa — bo'sh ro'yxat.
    """
    # 1-variant: faster-whisper (tezroq, kam xotira)
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_size, device="auto", compute_type="int8")
        segments, _ = model.transcribe(
            audio_or_video_path, language=language, word_timestamps=True
        )
        out = []
        for seg in segments:
            words = [
                {"w": w.word.strip(), "start": float(w.start), "end": float(w.end)}
                for w in (seg.words or []) if w.word.strip()
            ]
            out.append({"start": float(seg.start), "end": float(seg.end),
                        "words": words, "text": seg.text.strip()})
        return out
    except ImportError:
        pass
    except Exception:
        # model yuklash / chiqarish xatosi — subtitrsiz davom etamiz
        return []

    # 2-variant: original openai-whisper
    try:
        import whisper
        model = whisper.load_model(model_size)
        res = model.transcribe(audio_or_video_path, language=language,
                               word_timestamps=True)
        out = []
        for seg in res.get("segments", []):
            words = [
                {"w": w["word"].strip(), "start": float(w["start"]),
                 "end": float(w["end"])}
                for w in seg.get("words", []) if w["word"].strip()
            ]
            out.append({"start": float(seg["start"]), "end": float(seg["end"]),
                        "words": words, "text": seg["text"].strip()})
        return out
    except ImportError:
        return []
    except Exception:
        return []


def _ass_time(t):
    """Soniyani ASS vaqt formatiga: H:MM:SS.cc"""
    if t < 0:
        t = 0
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _chunk_words(words, max_chars=22, max_words=4):
    """
    So'zlarni qisqa bo'laklarga ajratadi (ekranga 1-4 so'zdan chiqishi uchun —
    trend Reels uslubi). Har bo'lak: {"start","end","words":[...]}
    """
    chunks, cur, cur_len = [], [], 0
    for w in words:
        wlen = len(w["w"]) + 1
        if cur and (len(cur) >= max_words or cur_len + wlen > max_chars):
            chunks.append(cur)
            cur, cur_len = [], 0
        cur.append(w)
        cur_len += wlen
    if cur:
        chunks.append(cur)
    return [{"start": c[0]["start"], "end": c[-1]["end"], "words": c}
            for c in chunks]


def build_ass(segments, style_sub, video_w=1080, video_h=1920):
    """
    Whisper natijasidan ASS subtitr matnini yasaydi.
    style_sub — styles.py'dagi stilning "subtitle" qismi.
    Karaoke yoqilgan bo'lsa, so'zlar navbatma-navbat yonib o'tadi.
    """
    s = style_sub
    bold = -1 if s.get("bold") else 0
    align = 2  # pastda markaz (ASS numpad: 2 = bottom-center)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Kadr,{s['font']},{int(video_w * s['size'] / 100)},{s['primary']},{s['secondary']},{s['outline']},&H64000000,{bold},0,0,0,100,100,0,0,1,{s['outline_w']},1,{align},60,60,{s['margin_v']},1

[Events]
Format: Layer, Start, End, Style, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = []
    upper = s.get("uppercase")
    karaoke = s.get("karaoke")

    for seg in segments:
        words = seg.get("words") or []
        if not words:
            # so'z-vaqti yo'q bo'lsa, butun segmentni bitta qator qilamiz
            text = seg.get("text", "")
            if not text:
                continue
            if upper:
                text = text.upper()
            lines.append(_dialogue(seg["start"], seg["end"], text))
            continue

        for chunk in _chunk_words(words):
            start, end = chunk["start"], chunk["end"]
            if karaoke:
                parts = []
                for w in chunk["words"]:
                    dur_cs = max(1, int(round((w["end"] - w["start"]) * 100)))
                    word = w["w"].upper() if upper else w["w"]
                    parts.append(f"{{\\kf{dur_cs}}}{word} ")
                text = "".join(parts).strip()
            else:
                text = " ".join(w["w"] for w in chunk["words"])
                if upper:
                    text = text.upper()
            lines.append(_dialogue(start, end, text))

    return header + "\n".join(lines) + "\n"


def _dialogue(start, end, text):
    return (f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Kadr,,0,0,0,,"
            f"{text}")

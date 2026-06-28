# ============================================================
#  Montaj stillari (presetlar)
#  Har bir stil — bu "retsept": kadr ritmi, rang gradatsiyasi,
#  subtitr ko'rinishi, musiqa balandligi va h.k.
#  Referens videodan ham shu ko'rinishdagi retsept chiqariladi.
# ============================================================

from copy import deepcopy


# Asosiy presetlar. Qiymatlar ffmpeg filtrlariga aylantiriladi (engine.py).
STYLES = {
    "trend_fast": {
        "label": "Trend — tez kesim",
        "desc": "Eng trenddagi qisqa Reels: tez hard-kesimlar, yorqin ranglar, "
                "so'zma-so'z 'karaoke' subtitr.",
        "shot_len": 1.8,          # o'rtacha bitta kadr necha soniya
        "shot_len_jitter": 0.6,   # tasodifiy o'zgaruvchanlik (jonli ko'rinish uchun)
        "remove_silence": True,   # gapsiz/bo'sh joylarni kesish
        "silence_db": -30,        # shu darajadan past = sukunat
        "silence_min": 0.45,      # shuncha soniyadan uzun sukunat kesiladi
        "max_duration": 60,       # tayyor video maksimal uzunligi (soniya)
        "snap_to_beat": True,     # kesimlarni musiqa ritmiga moslash
        "color": "eq=contrast=1.10:saturation=1.28:brightness=0.02:gamma=0.98",
        "fps": 30,
        "music_volume": 0.28,     # musiqa ovozi (0..1), gap ustidan past turadi
        "subtitle": {
            "font": "Arial",
            "size": 22,
            "primary": "&H00FFFFFF",     # oq (faol so'z)
            "secondary": "&H0000E5FF",   # sariq (kelayotgan so'z)
            "outline": "&H00000000",
            "outline_w": 3,
            "bold": True,
            "uppercase": True,
            "margin_v": 220,             # pastdan balandlik (px)
            "karaoke": True,             # so'z bo'yicha yonib o'tuvchi effekt
        },
    },
    "clean_minimal": {
        "label": "Toza — minimal",
        "desc": "Sokin, professional ko'rinish: yumshoq kesimlar, tabiiy ranglar, "
                "oddiy o'qiladigan subtitr.",
        "shot_len": 3.2,
        "shot_len_jitter": 0.8,
        "remove_silence": True,
        "silence_db": -33,
        "silence_min": 0.6,
        "max_duration": 90,
        "snap_to_beat": False,
        "color": "eq=contrast=1.04:saturation=1.08:brightness=0.01",
        "fps": 30,
        "music_volume": 0.18,
        "subtitle": {
            "font": "Arial",
            "size": 18,
            "primary": "&H00FFFFFF",
            "secondary": "&H00FFFFFF",
            "outline": "&H00202020",
            "outline_w": 2,
            "bold": True,
            "uppercase": False,
            "margin_v": 180,
            "karaoke": False,
        },
    },
    "energetic_vlog": {
        "label": "Energik — vlog",
        "desc": "Gapiruvchi odam uchun: zich kesim, ozgina zoom, yorqin subtitr.",
        "shot_len": 2.4,
        "shot_len_jitter": 0.7,
        "remove_silence": True,
        "silence_db": -28,
        "silence_min": 0.4,
        "max_duration": 75,
        "snap_to_beat": False,
        "punch_zoom": True,       # har kesimda yengil zoom (jonli ko'rinish)
        "color": "eq=contrast=1.12:saturation=1.18:brightness=0.015",
        "fps": 30,
        "music_volume": 0.15,
        "subtitle": {
            "font": "Arial",
            "size": 21,
            "primary": "&H00FFFFFF",
            "secondary": "&H0000D7FF",
            "outline": "&H00101010",
            "outline_w": 3,
            "bold": True,
            "uppercase": True,
            "margin_v": 240,
            "karaoke": True,
        },
    },
}

DEFAULT_STYLE = "trend_fast"


def list_styles():
    """Frontend uchun stillar ro'yxati (kalit + label + tavsif)."""
    return [
        {"id": k, "label": v["label"], "desc": v["desc"]}
        for k, v in STYLES.items()
    ]


def get_style(name):
    """Stilni nomi bo'yicha oladi. Topilmasa — standart stil."""
    return deepcopy(STYLES.get(name or DEFAULT_STYLE, STYLES[DEFAULT_STYLE]))


def derived_from_reference(analysis, base="trend_fast"):
    """
    Referens video tahlilidan (analyze.py natijasi) yangi stil yasaydi:
    eng yaqin presetni oladi va o'lchangan qiymatlar bilan ustiga yozadi.
    `analysis` — dict: {"shot_len":..., "tempo":..., "saturation":...}
    """
    style = get_style(base)
    if not analysis:
        return style

    shot = analysis.get("shot_len")
    if shot and shot > 0:
        # o'lchangan ritmni mantiqiy chegaralarda qabul qilamiz
        style["shot_len"] = max(0.7, min(6.0, float(shot)))

    tempo = analysis.get("tempo")
    if tempo and tempo > 0:
        # tez musiqa (>110 BPM) bo'lsa kesimni ritmga moslaymiz
        style["snap_to_beat"] = tempo >= 100

    sat = analysis.get("saturation")
    if sat and sat > 0:
        # referensning to'yinganligiga moslab rangni sozlaymiz
        s = max(0.9, min(1.5, 1.0 + (float(sat) - 1.0) * 0.8))
        style["color"] = f"eq=contrast=1.08:saturation={s:.2f}:brightness=0.015"

    style["label"] = "Referensdan olingan stil"
    style["desc"] = "Siz bergan referens videodan avtomatik o'qilgan montaj retsepti."
    return style

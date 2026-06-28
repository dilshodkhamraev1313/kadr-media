# 🎬 Avto Montaj — dvigatel (prototip)

Vertikal **Reels** uchun avtomatik montaj. Isxodnik videolarni berasiz,
stil tanlaysiz (yoki referens video) — tizim o'zi tayyor video chiqaradi:

1. Isxodniklarni o'lchaydi (`ffprobe`)
2. **Sukunat / bo'sh joylarni** kesadi
3. Stil ritmiga ko'ra **timeline** yig'adi (kadr uzunligi, max davomiylik)
4. **9:16 kadrlash + rang gradatsiyasi + fon musiqasi** bilan render qiladi
5. **Avto-subtitr** (Whisper) — trenddagi "so'zma-so'z" karaoke uslubda
6. Subtitrni videoga kuydirib **tayyor mp4** beradi

> Bu prototip. Maqsad — montajchining ishini ~80-90% avtomatlashtirish,
> qolgan sayqalni odam 5-10 daqiqada qiladi. "100% mukammal" sehrli tugma emas.

---

## O'rnatish

**Majburiy:** `ffmpeg` (va `ffprobe`) tizimda bo'lishi shart:

```bash
# Ubuntu / Debian (server)
apt install ffmpeg
# Mac
brew install ffmpeg
```

**Ixtiyoriy** (bo'lmasa tegishli qadam o'tkazib yuboriladi):

```bash
pip install faster-whisper   # subtitr (nutq → matn)
pip install librosa          # musiqa ritmiga (beat) moslash
pip install pillow numpy     # referens rangini o'lchash
```

Tekshirish:

```bash
python3 -m autoedit check
```

---

## Buyruq qatori (CLI)

```bash
# Mavjud stillar
python3 -m autoedit styles

# Bitta yoki bir nechta klipdan tayyor Reels
python3 -m autoedit edit --inputs klip1.mp4 klip2.mp4 \
        --style trend_fast --music fon.mp3 --out tayyor.mp4

# Referens video uslubida montaj
python3 -m autoedit edit --inputs klip1.mp4 --ref namuna.mp4 --out tayyor.mp4

# Faqat referensni tahlil qilish (ritm, tempo, rang)
python3 -m autoedit analyze --ref namuna.mp4
```

---

## Web (dashboard ichida)

Server ishga tushganda: **`/montaj.html`** sahifasi (sidebardagi
"🎬 Avto Montaj" havolasi). Login qilingan foydalanuvchilar:
video yuklaydi → stil tanlaydi → tayyor videoni yuklab oladi.

API:
- `GET  /api/montaj/styles` — stillar + tizim holati
- `POST /api/montaj/jobs` — multipart (videos, reference?, music?, style, language)
- `GET  /api/montaj/jobs/<id>` — holat (queued/processing/done/error)
- `GET  /api/montaj/jobs/<id>/download` — tayyor mp4

---

## Stillar (`styles.py`)

| Kalit | Tavsif |
|-------|--------|
| `trend_fast` | Trend tez kesim + karaoke subtitr (standart) |
| `clean_minimal` | Sokin, professional, tabiiy ranglar |
| `energetic_vlog` | Gapiruvchi odam uchun zich kesim |

Yangi stil qo'shish: `STYLES` lug'atiga yangi yozuv qo'shing.
Referensdan stil: `analyze.py` o'lchaydi → `styles.derived_from_reference()` yasaydi.

---

## Cheklovlar (prototip)

- Vazifalar xotirada (server qayta ishga tushsa ro'yxat yo'qoladi; fayllar diskda qoladi)
- Render sinxron, bitta thread'da — kuchli server tavsiya etiladi (GPU Whisper'ni tezlashtiradi)
- O'tishlar hozircha hard-kesim (trend uslubi); animatsion zoom keyingi bosqichda
- B-roll avtomatik qo'shish, brend logo/intro, ovozni tozalash — keyingi bosqichlarda

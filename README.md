# Kadr Media — Dashboard

Content production agentligi uchun loyihalarni boshqarish paneli.
Telefon va kompyuterda ishlaydi. Hech qanday dasturiy ta'minot o'rnatish shart emas (faqat Mac'da bor Python ishlatiladi).

---

## 🚀 Ishga tushirish (eng oson yo'l)

1. `kadr-media-dashboard` papkasini oching.
2. **`ISHGA-TUSHIRISH.command`** faylini ikki marta bosing.
3. Brauzer avtomatik ochiladi: **http://localhost:3000**

> Birinchi marta Mac "Open" tasdiqini so'rashi mumkin — **Open** ni bosing.
> To'xtatish: ochilgan qora oynada **Control + C** bosing yoki oynani yoping.

### Yoki terminal orqali
```bash
cd kadr-media-dashboard
python3 server.py
```

---

## 📱 Telefonda ochish (butun jamoa uchun)

Server ishga tushganda qora oynada manzil chiqadi, masalan:
```
📱 Telefonda (bir Wi-Fi):  http://192.168.1.45:3000
```
Telefon va kompyuter **bir xil Wi-Fi**'da bo'lsa, telefon brauzeriga shu manzilni yozing.
Butun jamoa shu tarzda kira oladi.

> Eslatma: kompyuter yoqiq va server ishlab turishi kerak. Internetdan (Wi-Fi'dan tashqarida)
> kirish kerak bo'lsa, "Doimiy onlayn joylash" bo'limiga qarang.

---

## 👤 Kim sifatida kirish

Kirishda jamoa a'zosini tanlaysiz. Har kim o'z huquqiga ega:

| Rol | Kim | Ko'radi |
|-----|-----|---------|
| **CEO** | Dilshod Khamraev | Bitta ekranda: qaysi loyiha qayerda, kim kechikyapti, xavf ostidagilar, bugungi natijalar |
| **Koordinator** | Xonzoda | Barcha loyihalarni ko'radi va boshqaradi |
| **Rahbar** | Said, Gulmira, Robiya | Barcha loyihalar + "Mening loyihalarim" filtri |

---

## 🧩 Imkoniyatlar

- **Loyiha kartochkalari** — nomi, mijoz, javobgar, 5 bosqich, progress, deadline, muammo, izoh
- **Bosqichlar:** Ssenariy → Syomka → Montaj → Tasdiq → Joylash (har biri: Kutilmoqda / Jarayonda / Tayyor)
- **Statistikalar:** jami loyihalar, kechikayotganlar, bugun bajarilgan vazifalar, xavf ostidagilar
- **Jamoa yuklamasi** — har bir rahbarda nechta faol/kechikkan loyiha bor
- **CEO paneli** — butun agentlik bitta ekranda
- **Qidiruv va filtrlar** — Faol, Kechikkan, Xavf ostida, Yakunlangan, Mening loyihalarim
- **Avtomatik belgilar** — deadline o'tsa "Kechikkan", muddat yaqin va ish kam bo'lsa "Xavf ostida"

---

## 💾 Ma'lumotlar qayerda saqlanadi

Barcha ma'lumotlar `kadr-media.db` (SQLite database) faylida, shu papka ichida saqlanadi.
Server o'chsa ham ma'lumotlar yo'qolmaydi. Zaxira nusxa olish uchun shu faylni nusxalang.

Boshidan toza boshlash kerak bo'lsa: `kadr-media.db` faylini o'chiring — qayta ishga tushganda
namuna ma'lumotlar bilan yangidan yaratiladi.

---

## ☁️ Doimiy onlayn joylash (ixtiyoriy)

Kompyuterni o'chirsangiz ham jamoa kirsin desangiz, dasturni bepul/arzon serverga joylash mumkin
(Railway, Render, yoki o'z VPS). Bu uchun yordam kerak bo'lsa, ayting — sozlab beraman.

---

## ☁️ Internetga joylash

Istalgan joydan kirish uchun to'liq qo'llanma: **`JOYLASH-QOLLANMA.md`** (Render + Neon, 100% bepul).

## 🎬 Avto Montaj (yangi — prototip)

Isxodnik videolarni yuklang → stil tanlang (yoki referens video bering) → tizim
avtomatik **vertikal Reels** montaj qiladi: sukunatni kesadi, ritmga sinxron kesim,
9:16 kadrlash, rang gradatsiyasi, fon musiqasi va o'zbekcha **avto-subtitr** (karaoke).

- Sidebardagi **"🎬 Avto Montaj"** havolasi orqali oching (`/montaj.html`)
- Terminal orqali: `python3 -m autoedit edit --inputs a.mp4 --style trend_fast --out tayyor.mp4`
- To'liq qo'llanma va o'rnatish: **`autoedit/README.md`**

> ⚠️ Ishlashi uchun serverga **ffmpeg** o'rnatilgan bo'lishi shart
> (`apt install ffmpeg` / `brew install ffmpeg`). Subtitr uchun: `pip install faster-whisper`.

## 🛠 Texnik ma'lumot

- **Backend:** Python (standart kutubxona) — `server.py`
- **Database:** mahalliyda SQLite (`kadr-media.db`), internetda Postgres (`DATABASE_URL` orqali, avtomatik)
- **Frontend:** HTML / CSS / JavaScript — `public/`
- Joylash fayllari: `requirements.txt`, `render.yaml`, `Procfile`, `runtime.txt`

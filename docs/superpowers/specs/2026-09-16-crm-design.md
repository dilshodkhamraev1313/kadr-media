# CRM (Sotuv/Lid boshqaruvi) — dizayn spetsifikatsiyasi

Sana: 2026-09-16
Holat: Tasdiqlangan (foydalanuvchi bilan brainstorming orqali kelishilgan)

## 1. Maqsad va qamrov

Kadr Media Dashboard'ga sotuv bo'limi (hozircha yagona xodim — Nodira, "Sotuv
operatori") uchun **lid boshqaruv (CRM) tizimi** qo'shiladi.

**Qamrov**: faqat "lid" bosqichi — hali shartnoma tuzmagan, Nodira bilan
muloqotda bo'lgan potentsial mijozlar. Lid "Mijoz bo'ldi" bosqichiga
o'tganda, mavjud **"Loyihalar" (`projects`)** tizimiga bir martalik
ko'chiriladi — CRM ikkinchi "mijoz bazasi" bo'lib qolmaydi, faqat sotuvgacha
bo'lgan jarayonni boshqaradi.

**Qamrovdan tashqarida** (keyingi bosqichlar uchun qoldiriladi):
- Allaqachon mijoz bo'lgan kompaniyalar bilan ishlash (buning uchun
  "Loyihalar" bor)
- Ko'p sotuvchili taqsimot/territoriya boshqaruvi (hozircha 1 kishi)
- Email/SMS integratsiyasi (Nodira faqat telefon orqali ishlaydi)

## 2. Arxitektura qarori

**Kadr Media Dashboard ichiga to'liq integratsiya** (`server.py` + `app.js`,
bitta baza, bitta login tizimi). Sabablari:
- Nodira va CEO uchun yangi login shart emas
- Mavjud Telegram bot infratuzilmasi (`send_telegram`) qayta ishlatiladi
- Lid → Loyiha konversiyasi bitta bazada — atomik, ishonchli
- Qo'shimcha xosting/xizmat xarajati yo'q

Kod tashkiloti: CRM funksiyalari `server.py` ichida, boshqa bo'limlar
(Kassa, Studio, Payroll) qanday tashkil qilingan bo'lsa, xuddi shunday izchil
bo'limlar tarzida yoziladi (mavjud kodda modul-fayllarga bo'lish patterni
yo'q — shu izchillik saqlanadi).

**Kelajak eslatmasi**: 10+ sotuvchi bo'lganda kengaytirish uchun
`assigned_to` maydoni allaqachon "bitta kishiga qattiq bog'lanmagan" tarzda
loyihalangan (bo'lim 3) — o'sha payt filtri sifatida "faqat o'z lidlarim"
qo'shiladi, bugungi arxitektura buzilmaydi.

## 3. Ma'lumotlar modeli

### `leads`
| Ustun | Tur | Izoh |
|---|---|---|
| id | PK | |
| name | TEXT | Mijoz/kompaniya nomi |
| phone | TEXT | |
| source | TEXT | `LEAD_SOURCES` kalitlaridan biri |
| stage | TEXT | `LEAD_STAGES` kalitlaridan biri, default `yangi` |
| value_estimate | INTEGER | Taxminiy oylik to'lov (so'm), ixtiyoriy |
| assigned_to | TEXT | Default `"Nodira"` — kelajakda ko'p qiymatli bo'ladi |
| lost_reason | TEXT | `stage='rad'` bo'lsa, ixtiyoriy |
| converted_project | TEXT | `stage='mijoz'` bo'lganda yozilgan loyiha nomi |
| created_by, created_at, updated_at | | |

### `lead_notes`
Har lid bo'yicha yagona xronologik tarix — qo'lda yozuv va AI qo'ng'iroq
tahlili shu bitta jadvalda, `kind` bilan farqlanadi.

| Ustun | Tur | Izoh |
|---|---|---|
| id | PK | |
| lead_id | FK → leads.id | |
| kind | TEXT | `note` (qo'lda) yoki `ai_call` (avtomatik AI tahlili) |
| text | TEXT | |
| created_by | TEXT | `note` uchun foydalanuvchi ismi, `ai_call` uchun `"AI"` |
| created_at | | |

### `lead_followups`
| Ustun | Tur | Izoh |
|---|---|---|
| id | PK | |
| lead_id | FK → leads.id | |
| due_at | TEXT (ISO datetime) | Keyingi aloqa vaqti |
| note | TEXT | Masalan "Narxni so'rash uchun qo'ng'iroq qilish" |
| done | INTEGER | 0/1 |
| done_at | TEXT | |
| warned | INTEGER | Cron eslatma yuborganini belgilaydi (bir martalik) |
| created_by, created_at | | |

### Konstantalar (mavjud `STUDIO_ROOMS`/`SHOOT_TYPES` uslubida)
```python
LEAD_STAGES = {
    "yangi":      "🆕 Yangi",
    "boglanildi": "📞 Bog'lanildi",
    "qiziqdi":    "🔥 Qiziqdi",
    "taklif":     "📨 Taklif yuborildi",
    "mijoz":      "✅ Mijoz bo'ldi",
    "rad":        "❌ Rad etildi",
}
LEAD_SOURCES = {
    "reklama": "Instagram/Telegram reklama",
    "tavsiya": "Tavsiya",
    "sovuq":   "Sovuq qidiruv",
    "boshqa":  "Sayt/boshqa",
}
CRM_USERS = ("Nodira",)  # kelajakda ko'p sotuvchi qo'shilganda kengayadi
```

## 4. API

Barchasi `role in ('ceo', 'sales')` bilan himoyalangan; `sales` roli faqat
o'z (`assigned_to == user.name`) lidlarini yaratadi/tahrirlaydi, CEO
hammasini ko'radi/tahrirlaydi.

- `GET /api/crm/leads?stage=...` — ro'yxat (bosqich bo'yicha filtr,
  ixtiyoriy)
- `GET /api/crm/leads/{id}` — detali: lid + `lead_notes` + `lead_followups`
- `POST /api/crm/leads` — yangi lid
- `PUT /api/crm/leads/{id}` — tahrirlash (bosqich o'zgarishi ham shu orqali;
  `stage` `mijoz`ga o'tsa — bo'lim 6dagi konversiya ishga tushadi)
- `DELETE /api/crm/leads/{id}` — faqat CEO (xato kiritilganini o'chirish)
- `POST /api/crm/leads/{id}/notes` — qo'lda yozuv qo'shish
- `POST /api/crm/leads/{id}/followups` — follow-up reja qo'yish
- `POST /api/crm/leads/{id}/followups/{fid}/done` — bajarildi belgilash
- `POST /api/crm/leads/{id}/call` — audio yuklash (bo'lim 7)
- `GET /api/crm/stats` — faqat CEO: bosqichlar bo'yicha son, konversiya %,
  manba taqsimoti (shu oy + jami)
- `GET /api/cron/crm-followup-check` — ochiq (auth shart emas, mavjud
  backstage/kassa cron'lari kabi), tashqi cron-job.org tomonidan chaqiriladi

## 5. Telegram — follow-up eslatmasi ("LID" topic)

`send_telegram(text, chat_id=None, thread_id=None)` funksiyasiga
`message_thread_id` parametri qo'shiladi (Telegram Bot API'ning shu
maydoni orqali guruh ichidagi aniq topic'ga xabar yuboriladi).

Yangi konstanta: `CRM_TOPIC_ID` — foydalanuvchi Telegram guruhida "LID"
nomli topic yaratgach, uning ID'sini topib shu yerga yoziladi (amalga
oshirish bosqichida bir martalik qo'lda qadam).

`api_cron_crm_followup_check()` (`api_cron_backstage_check` bilan bir xil
shakl): `lead_followups` dan `due_at <= now AND done=0 AND warned=0`
bo'lganlarni topadi, "LID" topic'ga eslatma yuboradi, `warned=1` qiladi.
Jarima yo'q — bu faqat eslatma, backstage/kassa'dan farqli o'laroq.

## 6. Lid → Loyiha konversiyasi

`PUT /api/crm/leads/{id}` orqali `stage` `mijoz`ga o'zgartirilganda (va
`converted_project` hali bo'sh bo'lsa):
1. `projects` jadvaliga yangi qator: `name=lead.name`,
   `monthly_fee=lead.value_estimate or 0`, `responsible=''` (CEO keyin
   qo'lda belgilaydi — brainstorming'da shunday kelishildi).
2. `leads.converted_project = <yangi loyiha nomi>` yoziladi.
3. Agar shu nom bilan loyiha allaqachon mavjud bo'lsa — xato qaytariladi
   (CEO'ga qo'lda hal qilish uchun), duplikat yaratilmaydi.

## 7. AI qo'ng'iroq tahlili

**Oqim**: Nodira telefon suhbatini o'z telefonining qo'ng'iroq yozib oluvchi
ilovasi bilan yozadi → tugagach audio faylni lid sahifasiga yuklaydi →
tizim fon rejimida (background thread, `send_telegram` bilan bir xil
pattern) qayta ishlaydi → natija (transkript + tahlil) `lead_notes`ga
`kind='ai_call'` bilan avtomatik qo'shiladi → **audio fayl saqlanmaydi**,
faqat matn.

**Texnik amalga oshirish** (mavjud `_ai_read_amount` — Kassa'dagi AI rasm
o'qish funksiyasi — bilan bir xil pattern, xuddi shu `OPENAI_API_KEY`):
1. Frontend audio faylni base64 (`data:audio/...`) sifatida yuboradi.
2. Backend: agar `OPENAI_API_KEY` yo'q bo'lsa — aniq xato ("AI o'chirilgan").
3. `POST https://api.openai.com/v1/audio/transcriptions`
   (`model=whisper-1`, `language=uz`) — multipart/form-data (stdlib
   `urllib` bilan qo'lda tuziladi, image yuklashdan farqli, chunki bu
   endpoint JSON emas, fayl kutadi).
4. Transkript matni `POST /v1/chat/completions`ga o'zbekcha rubrika bilan
   yuboriladi: "professional sotuv qo'ng'irog'i sifatida tahlil qil — qayer
   yaxshi, qayer xato/yaxshilash kerak, umumiy baho /10".
5. Natija formatlab `lead_notes`ga yoziladi.

**Ma'lum cheklov (amalga oshirish bosqichida hal qilinadi)**: OpenAI
Whisper API fayl hajmi chegarasi ~25MB — 20 daqiqalik yaxshi siqilgan
(m4a/ogg) audio odatda shu chegaraga sig'adi, lekin siqilmagan/uzun fayl
rad etilishi mumkin. Agar bu muammo chiqsa, foydalanuvchiga aniq xato
xabari beriladi ("faylni siqib qayta yuklang").

## 8. Frontend (UX)

- Yangi menyu bandi: **"CRM"** — faqat `role in ('sales','ceo')`
- Asosiy sahifa: bosqichlar bo'yicha ustunlar (Kanban-uslub, drag-and-drop
  EMAS — mavjud kodda bunday pattern yo'q; o'rniga kartochkada "Keyingi
  bosqich" tugmasi/dropdown, mavjud video-status tugmalari uslubida)
- Lid sahifasi (modal): kontakt ma'lumoti, yozuvlar tarixi (qo'lda +
  AI aralash, vaqt bo'yicha), follow-up qo'yish formasi, 🎙 audio yuklash
  tugmasi
- CEO uchun "CRM statistika" sahifasi: `statTile()` mavjud komponenti bilan
  — jami lid, konversiya %, manba taqsimoti

## 9. Ruxsatlar

| Amal | Nodira (`sales`) | CEO |
|---|---|---|
| Lid yaratish/tahrirlash | ✅ (faqat o'ziniki) | ✅ (hammasi) |
| Lid o'chirish | ❌ | ✅ |
| Statistika | ❌ | ✅ |
| Boshqa xodimlar | Ko'rmaydi (hozircha yagona sotuvchi) | — |

## 10. Test rejasi

- Backend: `python3 -m py_compile`, mahalliy smoke-test (curl orqali: lid
  yaratish → yozuv qo'shish → follow-up qo'yish → cron endpoint chaqirish →
  bosqichni `mijoz`ga o'zgartirib loyiha avtomatik yaratilganini tekshirish)
- Frontend: `node -c`, brauzerda Nodira hisobi bilan to'liq oqim (lid
  yaratish → bosqichlar bo'ylab o'tkazish → yozuv → follow-up)
- AI tahlil: qisqa (1-2 daqiqalik) test audio bilan uchidan-uchiga tekshirish
  (transkript + tahlil to'g'ri qaytishi, audio saqlanmasligi)
- Telegram: "LID" topic ID sozlangach, test follow-up bilan xabar
  yetib borishini tekshirish

## 11. Ochiq/kelishilgan qarorlar (brainstorming xulosasi)

- CRM faqat lid bosqichini qamraydi, mijozlar "Loyihalar"da qoladi
- Bosqichlar va manbalar ro'yxati keyin ham osongina o'zgartiriladi (qattiq
  belgilanmagan)
- Follow-up eslatmasi — faqat Telegram "LID" topic'ga, jarima yo'q
- Konversiyada loyiha mas'uli bo'sh qoladi, CEO qo'lda belgilaydi
- Audio fayl tahlildan keyin saqlanmaydi, faqat matn+tahlil
- Ruxsat: faqat Nodira + CEO (boshqa rahbarlarga hozircha yopiq)

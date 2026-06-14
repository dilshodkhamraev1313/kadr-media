# 🌐 Internetga joylash — to'liq qo'llanma

Maqsad: dashboard'ni **istalgan joydan** (uy, ofis, ko'cha, telefon) kiriladigan qilish.
**100% bepul**, bank kartasi kerak emas.

Uchta bepul xizmat ishlatamiz:
1. **GitHub** — kod saqlanadigan joy
2. **Neon** — bepul doimiy database (ma'lumotlar yo'qolmaydi)
3. **Render** — saytni internetga chiqaradigan server

⏱ Hammasi ~15-20 daqiqa. Hech qanday dasturlash bilim shart emas — faqat tugmalar bosiladi.

---

## 1-QADAM — GitHub (kodni internetga qo'yish)

1. **https://github.com/signup** — ro'yxatdan o'ting (email, parol, foydalanuvchi nomi). Bepul.
2. Kirgach, o'ng yuqoridagi **+** belgisini bosib → **New repository** ni tanlang.
3. **Repository name:** `kadr-media` deb yozing.
4. **Public** ni tanlab qoldiring → pastdan **Create repository** ni bosing.
5. Ochilgan sahifada **"uploading an existing file"** havolasini bosing.
6. Kompyuterdan **`kadr-media-dashboard` papkasini oching**, ichidagi **hamma fayllarni** (va `public` papkasini) tanlab, brauzerga **sudrab tashlang** (drag & drop).
   - ⚠️ `kadr-media.db` faylini yuklamang (agar bo'lsa). Qolganini hammasini yuklang.
7. Pastda yashil **Commit changes** tugmasini bosing.

✅ Kod endi GitHub'da. Bu sahifa manzilini eslab qoling (masalan `github.com/sizning-nomingiz/kadr-media`).

---

## 2-QADAM — Neon (bepul database)

1. **https://neon.tech** → **Sign up** → **GitHub bilan kirish** ni tanlang (eng oson, yangi parol kerak emas).
2. Avtomatik yangi loyiha (project) yaratiladi. Bo'lmasa **Create project** bosing — nom: `kadr-media`, qolganini default qoldiring.
3. Ochilgan sahifada **Connection string** (yoki **Connection Details**) bo'limini toping.
4. U yerda shunday matn bo'ladi:
   ```
   postgresql://user:parol@ep-xxxx.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```
5. Shu **butun matnni nusxa oling** (Copy tugmasi bor). Keyingi qadamda kerak bo'ladi.
   - 📌 Vaqtincha biror joyga (Notes) saqlab qo'ying.

---

## 3-QADAM — Render (saytni ishga tushirish)

1. **https://render.com** → **Get Started** → **GitHub bilan kirish**.
2. Render GitHub'ga ulanishga ruxsat so'raydi → **Authorize** bosing.
3. Yuqoridan **New +** → **Web Service** ni tanlang.
4. Ro'yxatdan **`kadr-media`** repozitoriyangizni toping → **Connect** bosing.
   - Ko'rinmasa: **Configure account** → repozitoriyga ruxsat bering.
5. Sozlamalar sahifasi ochiladi. Quyidagilarni tekshiring (odatda avtomatik to'ldiriladi):
   - **Name:** `kadr-media` (yoki xohlagan nom — bu sayt manzili bo'ladi)
   - **Region:** Frankfurt (yoki yaqinrog'i)
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python server.py`
   - **Instance Type:** **Free** ni tanlang
6. Pastga tushib **Environment Variables** (yoki **Advanced** → **Add Environment Variable**) bo'limiga o'ting:
   - **Key:** `DATABASE_URL`
   - **Value:** 2-qadamda Neon'dan nusxa olgan matnni shu yerga **joylashtiring**.
7. Pastdagi **Create Web Service** tugmasini bosing.

⏳ 2-4 daqiqa kutiladi (qurilyapti). "Live" yoki yashil belgi chiqsa — tayyor!

---

## ✅ TAYYOR!

Yuqorida saytingiz manzili chiqadi, masalan:
```
https://kadr-media.onrender.com
```

Bu manzilni:
- 📱 Telefon brauzeriga saqlang (Home ekranga qo'shsangiz — ilovadek bo'ladi)
- 👥 Butun jamoaga yuboring — har kim istalgan joydan kiradi
- 💻 Kompyuter yoqiq bo'lishi shart emas — endi internetda doim ishlaydi

---

## ℹ️ Bilib qo'yish kerak

- **Birinchi ochilish sekin:** Bepul tarifda kun bo'yi hech kim kirmasa, server "uxlaydi". Keyingi ochilishda **~30-50 soniya** kutiladi, keyin yana tez. (Bu bepul tarif sharti — pul to'lansa, doim tez bo'ladi.)
- **Ma'lumotlar yo'qolmaydi:** Hammasi Neon database'da saqlanadi.
- **Telefonga ilova qilib qo'yish:** Safari/Chrome'da saytni oching → **Share** → **Add to Home Screen**. Ekranda Kadr Media ikonkasi paydo bo'ladi.

---

## 🔄 Kelajakda o'zgartirish kiritsangiz

Kodni o'zgartirsangiz, GitHub'dagi faylni yangilang (yoki menga ayting) — Render **avtomatik** yangilab oladi.

Savol yoki muammo bo'lsa — menga ayting, har bir qadamda yordam beraman. 💪

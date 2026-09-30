# Odoo Telegram Bot - Maxsus Buyruqlar Va Login Qoidalari

Ushbu faylda botga yuborilishi mumkin bo'lgan maxsus parollar va buyruqlar, shuningdek ularning vazifalari to'liq keltirilgan.

## Kirish (Login) Buyruqlari
- **`login:umar3229`** 
  Tizimga **Bosh Admin** (Super Admin) sifatida kirish uchun ishlatiladi.
- **`login:<menejer_paroli>`**
  Tizimga menejer sifatida kirish. Har bir menejer uchun uning Odoo dagi logini yoki berilgan maxsus paroli yoziladi (Masalan: `login:123456`). Shu orqali menejer o'z profiliga ulanadi.

## Foydalanuvchilarni Nazorat Qilish Va Kuzatish
- **`login:admin`**
  Tizimda aynan Bosh Admin sifatida o'tirgan foydalanuvchilarni (ya'ni `login:umar3229` paroli orqali kirganlarni) aniqlab, faqat ularning ro'yxatini ko'rsatadi.
- **`login:user`** yoki **`login:kimlar`**
  Tizimga kirgan barcha **menejerlarni** hamda **qaysi menejer profiliga nechta telegram akkaunt ulanganligini** guruhlab, faqat menejerlar haqidagi statistikani ko'rsatib beradi.
- **`istoriya:<menejer_ismi>:<daqiqa>`** yoki **`menejer:<menejer_ismi>:<daqiqa>`**
  Aynan bitta menejer (yoki user) bot bilan nimalar haqida yozishganini va bot nima javob berganligini ko'rsatib beradi. *(Faqat Bosh Admin uchun)*
  _Masalan:_ `istoriya:mirahmad:5` (Mirahmad profilidagi oxirgi 5 daqiqalik yozishmalar).
- **`login:kick-<telegram_id>`**
  Ko'rsatilgan Telegram ID ga ega foydalanuvchini tizimdan (akkauntdan) chiqarib yuborish. (U qaytadan parol kiritishi kerak bo'ladi). *(Faqat Bosh Admin uchun)*
- **`kick:<telegram_ismi>:<menejer_ismi>`**
  Foydalanuvchini telegramdagi ismi va qaysi menejer profilida ekanligi bo'yicha qidirib, tizimdan chiqarib yuborish. *(Faqat Bosh Admin uchun)*

## Bloklash Va Blokdan Chiqarish
- **`login:block-<telegram_id>`**
  Ko'rsatilgan ID ga ega foydalanuvchini botdan butunlay bloklash. Bot uni boshqa tanimaydi va u qora ro'yxatga tushadi. *(Faqat Bosh Admin uchun)*
- **`login:unblock-<telegram_id>`**
  Bloklangan (qora ro'yxatga tushgan) foydalanuvchidan blokni olib tashlash va botdan yana foydalanishga ruxsat berish. *(Faqat Bosh Admin uchun)*

## Parol O'zgartirish
- **`change:<Menejer_Ismi>:login:<yangi_parol>`**
  Muayyan menejer profilining botga ulanish parolini yangisiga o'zgartirish. *(Faqat Bosh Admin uchun)*

## Boshqa Maxsus Buyruqlar
- **`tovar-nomlari`**
  Odoo bazasidan barcha tovarlar ro'yxatini yangilab (sinxronizatsiya qilib), bot xotirasiga o'qitish. Bu tovarlar qidirilganda imloviy xatolar bo'lsa ham bot to'g'ri topishi uchun xizmat qiladi.

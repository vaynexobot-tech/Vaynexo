# VAYNEXO — admin panel qo'llanmasi

Admin panelga kirish: botda **Sozlamalar → Admin panel** yoki `/admin` (kompyuterda — `/administ` havolasi).
Pastki menyu: **Bosh · Buyurtmalar · Katalog · Odamlar · Ko'proq**. Hamma narsa «Ko'proq» ichida bo'limlarga ajratilgan.

## 1. Bot
| Bo'lim | Nima qiladi |
|---|---|
| Botni ochish va mehmonlar | Botni hamma uchun ochish/yopish, yopiq paytda ruxsat berilgan ID'lar |
| Bo'limlar: ochish / Tez kunda | Har bo'limni bitta tugma bilan yoqish/o'chirish: savdo, ijara, boost, Telegram, Arena, Daromad, Top, AI, **Do'konlar, Plus, Jamg'arma, Birgalikda, Striminer, Pro, Draft Jang, VAY**. O'chirilgan bo'lim foydalanuvchiga ko'rinmaydi yoki «Tez kunda» bo'ladi |
| Ommaviy xabar | Hammaga yoki tanlangan guruhga (sotuvchilar, KYC'dan o'tganlar, ...) xabar |

## 2. Pul
| Bo'lim | Nima qiladi |
|---|---|
| Kirimlar va to'lov kartalari | P2P kartalar, SMS/bank bot, tekshiruvdagi to'lovlar |
| Pul yechish | So'rovlarni tasdiqlash/rad etish. **Pul yechish uchun KYC majburiy** |
| Daromad va hisobot | Kunlik, oylik grafik |
| Promo-kodlar | Bonus kodlar |

## 3. Xizmatlar
| Bo'lim | Nima qiladi |
|---|---|
| **API taqsimoti** | Har bo'lim (har o'yin, Telegram Premium, Telegram Stars) qaysi API orqali sotilishini tanlash. Ommaviy: «hamma o'yinlarni API 2 ga o'tkaz». Faqat shu API'da paketi bor bo'limlar o'tadi |
| Katalog → API'lar | Yangi API qo'shish (manzil + kalit), tekshirish, sinxronlash, balans |
| Donat, Telegram, Boost, Ijara, E'lonlar | Buyurtmalar va moderatsiya |
| Qo'lda paketlar | API'siz paket qo'shish |

## 4. Arena
Turnirlar va setka (homiy — brend nomi, logo, havola; «faqat Plus» turnir), prognozlar, viktorina, Daromad (hamkor videolari).

## 5. Premium
| Bo'lim | Nima qiladi |
|---|---|
| **Premium boshqaruvi** | Umumiy ko'rsatkichlar va 7 ta yorliq: **Do'konlar** (tahrirlash, to'xtatish), **Plus** (kun qo'shish/sovg'a), **Jamg'arma** (yopish — pul qaytadi), **Striminer** (to'xtatish, nomaqbul donatni yashirish), **Pro** (auksionni bekor qilish — pul qaytadi), **Birga** (yig'ishni yopish — ulushlar qaytadi), **Draft** (ELO tuzatish) |
| Ikki barobar almaz signali | Obunachilarga darhol xabar |
| Pro auksion | Pro arizalarini tasdiqlash, nizolarni hal qilish |

## 6. Xavfsizlik
| Bo'lim | Nima qiladi |
|---|---|
| **Identifikatsiya (KYC)** | Kutayotgan / tasdiqlangan / rad etilganlar, qidiruv. Tasdiqlash, rad etish (sabab bilan), bekor qilish. Hujjat rasmlari serverda saqlanmaydi — botda admin guruhiga keladi (`/kyc_guruh`) |
| Nizolar | Akkaunt savdo nizolari |
| Admin jurnali | Kim, qachon, nima qildi — har admin amali avtomatik yoziladi |
| **Sozlamalar va matnlar** | Barcha narx, foiz, muddat va limitlar guruhlarga ajratilgan. **Matnlar** guruhi: bot /start salomi, yopiq paytdagi xabar, bosh sahifa sarlavhasi/izohi, bosh sahifadagi e'lon, support username |

## KYC qayerda majburiy
Sozlamalar → «Identifikatsiya (KYC)»: **Account savdo**, **Account ijara**, **Pul yechish** — uchalasi standart holatda «Majburiy».

## Muhim
- `.env` dagi `ENCRYPTION_KEY` ni yo'qotmang: API kalitlar va akkaunt parollari u bilan shifrlangan.
- Pul bilan bog'liq har amal (qaytarish, bekor qilish) hamyon jurnali orqali bajariladi va ikki marta bajarilmaydi.

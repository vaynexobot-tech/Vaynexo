# Rone Arena'ga xat (tijoriy foydalanish uchun kelishuv)

Qayerga: https://arena.rone.dev saytidagi aloqa (Contact) yoki https://rone.dev/contact
Tili: ingliz (ular Indoneziyada, ingliz tilida yozish yaxshi).

---

**Subject:** Commercial use request — VAYNEXO (Telegram Mini App, Uzbekistan)

Hello Rone Arena team,

I run VAYNEXO, a Telegram Mini App for Mobile Legends players in Uzbekistan
(game top-ups, account marketplace, tournaments and a community section).

We would like to show hero statistics from your hosted API inside the app:

- Endpoints: `/api/heroes/rank` (win / pick / ban rates by rank, 7 and 30 days)
  and `/api/heroes/{id}/counters`.
- Expected load: very low. Our server caches every response for 6 hours, so it is
  roughly **15–30 requests per day** in total, not per user. Users never call your
  API directly.
- Attribution: every screen that shows the data has a visible credit
  "Statistika: Rone Arena" linking to https://arena.rone.dev.
- We do not use player-facing (login) endpoints.

The app is commercial (we sell game top-ups), so per your Hosted API Terms we are
asking for permission. If you have conditions (a request limit, a different host,
a fee or a specific attribution text), please let me know and we will follow them.

If you prefer we stop, we can switch the feature off immediately.

Thank you for the project!

Best regards,
<Ismingiz>
VAYNEXO — https://t.me/vaynexobot

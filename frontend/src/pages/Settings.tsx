import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type HistoryItem, type Me } from "../api";
import { t } from "../i18n";
import { openTg } from "../tg";
import { BottomBar, Chips, Copy, dateTime, Empty, Field, GameLogo, Header, Icon, Loadable, money, Seg, som, Status, useAction, useApp, useLoad } from "../ui";

export const SUPPORT = "vaynexo_support";

export function Referral() {
  const { me } = useApp();
  if (!me) return null;
  const link = me.ref_link;
  const share = () => link && openTg(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(t("VAYNEXO — ML almaz, akkaunt savdo va boost 🎮"))}`);
  return (
    <>
      <Header title={t("Taklif qilish")} sub={t("Referal tizimi")} />
      <div className="page">
        <div className="hero">
          <span className="badge g">REFERAL</span>
          <div className="hf bb" style={{ fontSize: 19, margin: "10px 0 4px" }}>{t("Do'stlaringizni taklif qiling")}</div>
          <div className="sm" style={{ color: "#d6dbe8" }}>
            {me.referral_bonus > 0
              ? <>{t("Do'stingiz ro'yxatdan o'tib, hamyonini kamida {m} to'ldirsa, sizga", { m: som(me.referral_min_topup) })} <b className="y">{som(me.referral_bonus)}</b> {t("bonus tushadi.")}</>
              : t("Hozircha bonus o'chirilgan.")}
          </div>
        </div>
        <div className="card col">
          <div className="mut xs">{t("Sizning taklif havolangiz")}</div>
          {link ? <Copy value={link} /> : <div className="mut sm">{t("Havola tez orada paydo bo'ladi")}</div>}
          <button className="btn full" disabled={!link} onClick={share}>{t("Telegramda ulashish")}</button>
        </div>
        <div className="grid3 center">
          <div className="card tight"><div className="bb mono">{me.ref_invited}</div><div className="mut xs">{t("Taklif qilingan")}</div></div>
          <div className="card tight"><div className="bb mono">{me.ref_paid}</div><div className="mut xs">{t("To'ldirgan")}</div></div>
          <div className="card tight"><div className="bb mono g">{money(me.ref_earned)}</div><div className="mut xs">{t("Bonus, so'm")}</div></div>
        </div>
        <div className="card col">
          <div className="b">{t("Qanday ishlaydi")}</div>
          {[t("Havolani do'stingizga yuboring"), t("Do'stingiz shu havola orqali VAYNEXO'da ro'yxatdan o'tadi"),
            t("U hamyonini kamida {m} to'ldirgach, bonus avtomatik hamyoningizga tushadi", { m: som(me.referral_min_topup) })].map((x, i) => (
            <div key={i} className="row sm" style={{ alignItems: "flex-start" }}><span className="badge y">{i + 1}</span><span>{x}</span></div>
          ))}
          <div className="mut xs">{t("Faqat botni ochish (/start) uchun bonus berilmaydi. Bitta do'st uchun bonus bir marta beriladi.")}</div>
        </div>
      </div>
    </>
  );
}

export function ProfileEdit() {
  const nav = useNavigate();
  const { me, setMe, toast } = useApp();
  const [f, setF] = useState({ first_name: me?.name ?? "", phone: me?.phone ?? "", ml_id: me?.ml_id ?? "", bio: me?.bio ?? "" });
  const { busy, run } = useAction();
  if (!me) return null;
  return (
    <>
      <Header title={t("Profilni tahrirlash")} />
      <div className="page">
        <Field label={t("Ism")}><input className="input" maxLength={128} value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} /></Field>
        <Field label={t("Telefon")}><input className="input" inputMode="tel" maxLength={32} placeholder="+998 90 123 45 67" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
        <Field label={t("ML ID (ixtiyoriy)")}><input className="input mono" inputMode="numeric" maxLength={32} value={f.ml_id} onChange={(e) => setF({ ...f, ml_id: e.target.value.replace(/\D/g, "") })} /></Field>
        <Field label={t("O'zingiz haqingizda")}><textarea className="input" maxLength={300} value={f.bio} onChange={(e) => setF({ ...f, bio: e.target.value })} /></Field>
      </div>
      <BottomBar>
        <button className="btn full" disabled={busy || !f.first_name.trim()} onClick={() => run(async () => {
          const u = await api.patch<Me>("/me", f);
          setMe({ ...me, ...u });
          toast(t("Saqlandi"), "ok");
          nav(-1);
        })}>{t("Saqlash")}</button>
      </BottomBar>
    </>
  );
}

const HIST_LINK: Record<string, (id: number) => string> = {
  account: (id) => `/deal/${id}`, boost: (id) => `/boost/${id}`,
};

export function History() {
  const nav = useNavigate();
  const [type, setType] = useState("all");
  const st = useLoad(() => api.get<{ items: HistoryItem[]; spent: number; count: number }>(`/history?type=${type}`), [type]);
  return (
    <>
      <Header title={t("Xaridlar tarixi")} sub={t("Barcha xaridlaringiz")} />
      <div className="page">
        <div className="quick5">
          {[
            ["bag", t("Bitimlar"), "/deals"], ["chat", t("Chatlar"), "/chats"], ["rocket", "Boost", "/boosts"],
            ["send", "Telegram", "/tg/orders"], ["clock", t("Ijaralar"), "/rentals"],
          ].map(([ic, label, to]) => (
            <button key={to} onClick={() => nav(to)}><span className="rowico y"><Icon name={ic} /></span><span className="xs b">{label}</span></button>
          ))}
        </div>
        <Chips value={type} onChange={setType} options={[
          { v: "all", label: t("Hammasi") }, { v: "donate", label: t("Donat") }, { v: "account", label: t("Akkaunt") },
          { v: "boost", label: "Boost" }, { v: "telegram", label: "Telegram" }, { v: "wallet", label: t("Hamyon") },
        ]} />
        <Loadable state={st}>
          {(d) => d.items.length === 0 ? <Empty icon="🧾" text={t("Hali xaridlar yo'q")} /> : (
            <>
              <div className="card row between"><span className="mut sm">{t("Jami sarflangan")}</span><span className="y bb mono">{som(d.spent)}</span></div>
              <div className="card" style={{ padding: "4px 14px" }}>
                {d.items.map((i) => (
                  <div key={i.type + i.id} className="listrow" style={HIST_LINK[i.type] ? { cursor: "pointer" } : undefined} onClick={() => HIST_LINK[i.type] && nav(HIST_LINK[i.type](i.id))}>
                    <GameLogo game={i.game} size={38} />
                    <div className="grow">
                      <div className="b ell sm">{i.title}</div>
                      <div className="mut xs ell">{i.sub} · {dateTime(i.created_at)}</div>
                    </div>
                    <div className="col" style={{ alignItems: "flex-end", gap: 4 }}>
                      <span className={"mono b sm " + (i.amount > 0 ? "g" : "")}>{i.amount > 0 ? "+" : "−"}{money(Math.abs(i.amount))}</span>
                      <Status s={i.status} />
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </Loadable>
      </div>
    </>
  );
}

const FAQ: [string, string][] = [
  ["Garant qanday ishlaydi?", "To'lov VAYNEXO'da saqlanadi. Akkauntni tekshirib tasdiqlaganingizdan so'ng pul sotuvchiga o'tkaziladi. Muammo bo'lsa nizo ochasiz va admin hal qiladi."],
  ["Hamyonni qanday to'ldiraman?", "Hamyon → To'ldirish. Tizim bergan ANIQ summani ko'rsatilgan kartaga o'tkazing. To'lov avtomatik topiladi va 1–3 daqiqada balansga tushadi."],
  ["Noto'g'ri summa o'tkazib yubordim", "Xavotir olmang — @vaynexo_support ga chek (skrinshot) yuboring, admin qo'lda biriktiradi."],
  ["Almaz qancha vaqtda tushadi?", "Odatda 1–5 daqiqa. Agar provayder bajara olmasa, pul avtomatik hamyonga qaytariladi."],
  ["Pulni qanday yechib olaman?", "Hamyon → Yechish. Karta raqamini kiriting, so'rov 24 soat ichida bajariladi."],
  ["Akkauntimni qanday sotaman?", "E'lon joylash → ma'lumotlarni to'ldiring → moderatsiyadan so'ng e'lon ko'rinadi. Sotilganda login/parolni bitim sahifasida yuborasiz."],
];

export function Help() {
  const [open, setOpen] = useState<number | null>(0);
  const [text, setText] = useState("");
  const { toast } = useApp();
  const { busy, run } = useAction();
  return (
    <>
      <Header title={t("Yordam va aloqa")} sub={t("Savollar va qo'llab-quvvatlash")} />
      <div className="page withbar">
        <button className="card click row" style={{ color: "inherit", textAlign: "left" }} onClick={() => openTg(`https://t.me/${SUPPORT}`)}>
          <span className="y"><Icon name="chat" size={24} /></span>
          <div className="grow"><div className="b">{t("Operator bilan chat")}</div><div className="mut xs">@{SUPPORT} · 24/7</div></div>
          <Icon name="right" />
        </button>
        <div className="mut xs mono">{t("KO'P SO'RALADIGAN SAVOLLAR")}</div>
        {FAQ.map(([q, a], i) => (
          <div key={i} className="card click" onClick={() => setOpen(open === i ? null : i)}>
            <div className="row between"><span className="b">{t(q)}</span><span className="y">{open === i ? "−" : "+"}</span></div>
            {open === i && <div className="mut sm" style={{ marginTop: 8 }}>{t(a)}</div>}
          </div>
        ))}
        <Field label={t("Muammoni yozing")}>
          <textarea className="input" rows={4} maxLength={1500} placeholder={t("Savolingizni batafsil yozing...")} value={text} onChange={(e) => setText(e.target.value)} />
        </Field>
      </div>
      <BottomBar>
        <button className="btn full" disabled={text.trim().length < 5 || busy} onClick={() => run(async () => {
          await api.post("/support", { text });
          setText("");
          toast(t("Xabaringiz yuborildi. Operator tez orada botda javob beradi."), "ok");
        })}>{t("Yuborish")}</button>
      </BottomBar>
    </>
  );
}

const TERMS = `1. Umumiy qoidalar
1.1. Ushbu kelishuv VAYNEXO platformasi (Telegram Mini App) va foydalanuvchi o'rtasidagi munosabatlarni tartibga soladi.
1.2. Platformadan foydalanish orqali siz ushbu shartlarga rozilik bildirasiz.

2. Hamyon va to'lovlar
2.1. Barcha hisob-kitoblar so'mda amalga oshiriladi.
2.2. Hamyonni to'ldirishda tizim bergan aniq summani o'tkazish foydalanuvchi zimmasida.
2.3. Pul yechish so'rovlari 24 soat ichida ko'rib chiqiladi.

3. Akkaunt savdosi
3.1. Har bir savdo garant orqali amalga oshiriladi: to'lov xaridor tasdiqlaguncha platformada saqlanadi.
3.2. Sotilgan akkauntni qaytarib olish (pochta yoki parolni tiklash orqali) qat'iyan taqiqlanadi va hisobni bloklash hamda javobgarlikka olib keladi.
3.3. Platforma har bir bitimdan komissiya oladi; komissiya sotuvchi oladigan summadan ushlanadi.
3.4. Xaridor tasdiqlamasa va nizo ochmasa, bitim belgilangan muddatdan so'ng avtomatik yakunlanadi.

4. Nizolar
4.1. Nizolar admin tomonidan ikkala tomonning dalillari asosida hal qilinadi. Admin qarori yakuniy hisoblanadi.

5. Taqiqlar
5.1. Platformadan tashqarida to'lov qilishga undash, firibgarlik, boshqalarning ma'lumotlaridan foydalanish taqiqlanadi.

6. Javobgarlik
6.1. Platforma o'yin ishlab chiquvchilari (Moonton va boshqalar) bilan bog'liq emas.`;

const PRIVACY = `1. Qanday ma'lumotlar yig'iladi
Telegram ID, ism, username, siz kiritgan telefon va o'yin ID raqamlari, savdo va to'lov tarixi.

2. Ma'lumotlardan foydalanish
Faqat buyurtmalarni bajarish, firibgarlikka qarshi kurash va qo'llab-quvvatlash uchun.

3. Akkaunt parollari
Bitim va boost uchun berilgan login/parollar shifrlangan holda saqlanadi va faqat tegishli tomonga ko'rsatiladi. Boost tugagach parol o'chiriladi.

4. Uchinchi tomonlar
Ma'lumotlar uchinchi shaxslarga sotilmaydi. Faqat buyurtmani bajarish uchun zarur bo'lgan qism (masalan, o'yin ID) provayderga uzatiladi.

5. Aloqa
Savollar bo'yicha: @vaynexo_support`;

export function Legal() {
  const nav = useNavigate();
  const doc = useParams().doc;
  const isTerms = doc !== "privacy";
  return (
    <>
      <Header title={t("Qoidalar va shartlar")} right={<span />} />
      <div className="page">
        <Seg value={isTerms ? "terms" : "privacy"} onChange={(v) => nav(`/legal/${v}`, { replace: true })}
          options={[{ v: "terms", label: t("Foydalanuvchi kelishuvi") }, { v: "privacy", label: t("Maxfiylik siyosati") }]} />
        <div className="card pre sm" style={{ lineHeight: 1.6 }}>{isTerms ? TERMS : PRIVACY}</div>
      </div>
    </>
  );
}


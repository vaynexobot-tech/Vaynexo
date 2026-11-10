import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type HistoryItem, type Me } from "../api";
import { t } from "../i18n";
import { openTg, tgPhoto } from "../tg";
import { BottomBar, BottomNav, Chips, Copy, dateTime, Empty, Field, GameLogo, Header, Icon, Loadable, money, Row, som, Status, useAction, useApp, useLoad } from "../ui";

export const SUPPORT = "vaynexo_support";

export function Settings() {
  const nav = useNavigate();
  const { me, setMe, toast, fail } = useApp();
  if (!me) return null;
  const photo = tgPhoto();
  const setLang = async (lang: "uz" | "ru") => {
    try {
      const u = await api.patch<Me>("/me", { lang });
      setMe({ ...me, ...u });
    } catch (e) {
      fail(e);
    }
  };
  return (
    <>
      <Header title={t("Sozlamalar")} sub={t("Profil va ilova sozlamalari")} back={false} />
      <div className="page">
        <div className="card col">
          <div className="row">
            <div style={{ width: 56, height: 56, borderRadius: "50%", padding: 2, background: "linear-gradient(135deg,#ffd60a,#1de9b6)", flex: "none" }}>
              {photo ? <img src={photo} alt="" style={{ width: "100%", height: "100%", borderRadius: "50%" }} /> : <div style={{ width: "100%", height: "100%", borderRadius: "50%", background: "linear-gradient(135deg,#3a2f6b,#e7a84a)" }} />}
            </div>
            <div className="grow">
              <div className="bb" style={{ fontSize: 17 }}>{me.name || "—"}</div>
              <div className="mut xs mono">ID: {me.id}{me.username ? ` · @${me.username}` : ""}</div>
            </div>
            <button className="btn small ghost" onClick={() => nav("/profile")}>{t("Tahrirlash")}</button>
          </div>
          <div className="grid3 center">
            <div><div className="bb y">{me.rating ?? "—"}</div><div className="mut xs">{t("{n} ta baho", { n: me.rating_count })}</div></div>
            <div><div className="bb">{me.sales}</div><div className="mut xs">{t("Savdo")}</div></div>
            <div><div className="bb g">{me.positive_percent != null ? me.positive_percent + "%" : "—"}</div><div className="mut xs">{t("Yaxshi baho")}</div></div>
          </div>
        </div>

        <div className="card" style={{ padding: "4px 14px" }}>
          <Row icon={<Icon name="wallet" />} title={t("Hamyon")} sub={som(me.balance)} onClick={() => nav("/wallet")} />
          <Row icon={<Icon name="list" />} title={t("Xaridlar tarixi")} onClick={() => nav("/history")} />
          <Row icon={<Icon name="doc" />} title={t("Mening e'lonlarim")} sub={t("{n} faol", { n: me.active_listings })} onClick={() => nav("/my-listings")} />
          <Row icon={<Icon name="bag" />} title={t("Mening bitimlarim")} onClick={() => nav("/deals")} />
          <Row icon={<Icon name="chat" />} title={t("Chatlar")} onClick={() => nav("/chats")} />
          <Row icon={<Icon name="rocket" />} title={t("Boost buyurtmalarim")} onClick={() => nav("/boosts")} />
          <Row icon={<span className="y"><Icon name="gift" /></span>} title={t("Do'stlarni taklif qilish")}
            sub={me.referral_bonus > 0 ? t("Har bir do'st uchun {s}", { s: som(me.referral_bonus) }) : undefined}
            right={<><span className="badge g">+ bonus</span><span className="mut"><Icon name="right" size={18} /></span></>}
            onClick={() => nav("/referral")} />
        </div>

        <div className="card col">
          <div className="row"><Icon name="globe" /><div className="b">{t("Til")}</div></div>
          <Chips value={me.lang} onChange={(v) => setLang(v)} options={[{ v: "uz", label: "O'zbekcha" }, { v: "ru", label: "Русский" }]} />
        </div>

        <div className="card" style={{ padding: "4px 14px" }}>
          <Row icon={<Icon name="help" />} title={t("Yordam")} sub={"@" + SUPPORT + " · 24/7"} onClick={() => nav("/help")} />
          <Row icon={<Icon name="shield" />} title={t("Foydalanuvchi kelishuvi")} onClick={() => nav("/legal/terms")} />
          <Row icon={<Icon name="doc" />} title={t("Maxfiylik siyosati")} onClick={() => nav("/legal/privacy")} />
          {me.is_admin && <Row icon={<span className="y"><Icon name="admin" /></span>} title={<span className="y">{t("Admin panel")}</span>} onClick={() => nav("/admin")} />}
        </div>
        <div className="mut xs center" onClick={() => toast("VAYNEXO Mini App v1.0")}>VAYNEXO · v1.0</div>
      </div>
      <BottomNav />
    </>
  );
}

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
              ? <>{t("Do'stingiz birinchi marta hamyonini to'ldirsa, sizga")} <b className="y">{som(me.referral_bonus)}</b> {t("bonus tushadi.")}</>
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
          {[t("Havolani do'stingizga yuboring"), t("Do'stingiz shu havola orqali VAYNEXO'ni ochadi"), t("U birinchi marta hamyonini to'ldirgach, bonus avtomatik hamyoningizga tushadi")].map((x, i) => (
            <div key={i} className="row sm" style={{ alignItems: "flex-start" }}><span className="badge y">{i + 1}</span><span>{x}</span></div>
          ))}
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
  return (
    <>
      <Header title={t("Yordam")} sub={t("Savollar va qo'llab-quvvatlash")} />
      <div className="page">
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
      </div>
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
  const doc = useParams().doc;
  const isTerms = doc !== "privacy";
  return (
    <>
      <Header title={isTerms ? t("Foydalanuvchi kelishuvi") : t("Maxfiylik siyosati")} right={<span />} />
      <div className="page"><div className="card pre sm" style={{ lineHeight: 1.6 }}>{isTerms ? TERMS : PRIVACY}</div></div>
    </>
  );
}


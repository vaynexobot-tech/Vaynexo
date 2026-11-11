import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type HistoryItem, type Me } from "../api";
import { t } from "../i18n";
import { openTg, tgPhoto } from "../tg";
import { BottomBar, Chips, Copy, Empty, Field, GameLogo, Header, Icon, Loadable, money, Seg, som, Status, useAction, useApp, useLoad } from "../ui";

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
      <Header title={t("Profilni tahrirlash")} sub={t("Shaxsiy ma'lumotlar")} />
      <div className="page withbar">
        <div className="col" style={{ alignItems: "center", gap: 8, margin: "8px 0" }}>
          <div className="big-ava">{tgPhoto() ? <img src={tgPhoto()!} alt="" /> : <Icon name="user" size={38} />}</div>
          <span className="mut xs">{t("Rasm Telegram profilingizdan olinadi")}</span>
        </div>
        <Field label={t("Ism")}><input className="input" maxLength={128} value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} /></Field>
        <Field label={t("Foydalanuvchi nomi")}><input className="input" value={me.username ? "@" + me.username : "—"} readOnly disabled /></Field>
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
  account: (id) => `/deal/${id}`, boost: (id) => `/boost/${id}`, rent: (id) => `/rental/${id}`, telegram: (id) => `/tg/order/${id}`,
};

export function History() {
  const nav = useNavigate();
  const [type, setType] = useState("all");
  const st = useLoad(() => api.get<{ items: HistoryItem[]; spent: number; count: number }>(`/history?type=${type}`), [type]);
  return (
    <>
      <Header title={t("Xaridlar tarixi")} sub={t("Barcha xaridlaringiz")} />
      <div className="page">
        {st.data && (
          <div className="hero row between">
            <div><div className="mut xs">{t("Jami sarflangan")}</div><div className="y hf bb" style={{ fontSize: 26 }}>{money(st.data.spent)} <span className="mut sm">so'm</span></div></div>
            <div style={{ textAlign: "right" }}><div className="hf bb" style={{ fontSize: 22 }}>{st.data.count}</div><div className="mut xs">{t("ta xarid")}</div></div>
          </div>
        )}
        <Chips wrap value={type} onChange={setType} options={[
          { v: "all", label: t("Hammasi") }, { v: "donate", label: t("Donat") }, { v: "account", label: t("Akkaunt") }, { v: "rent", label: t("Ijara") },
          { v: "boost", label: "Boost" }, { v: "telegram", label: "Telegram" }, { v: "wallet", label: t("Hamyon") },
        ]} />
        <Loadable state={st}>
          {(d) => d.items.length === 0 ? <Empty icon="🧾" text={t("Hali xaridlar yo'q")} /> : (
            <>
              {groupByDay(d.items).map(([day, items]) => (
                <div key={day} className="col">
                  <div className="mut xs mono b" style={{ marginTop: 4 }}>{day}</div>
                  {items.map((i) => (
                    <div key={i.type + i.id} className="card row tight" style={HIST_LINK[i.type] ? { cursor: "pointer" } : undefined} onClick={() => HIST_LINK[i.type] && nav(HIST_LINK[i.type](i.id))}>
                      <GameLogo game={i.game} size={42} />
                      <div className="grow" style={{ minWidth: 0 }}>
                        <div className="b ell">{t(i.title)}</div>
                        <div className="mut xs ell">{t(i.sub)} · {timeOnly(i.created_at)}</div>
                      </div>
                      <div className="col" style={{ alignItems: "flex-end", gap: 4 }}>
                        <span className={"mono bb " + (i.amount > 0 ? "g" : "")}>{i.amount > 0 ? "+" : ""}{money(Math.abs(i.amount))}</span>
                        <Status s={i.status} />
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </>
          )}
        </Loadable>
        <div className="mut xs mono b" style={{ marginTop: 8 }}>{t("BUYURTMALARIM")}</div>
        <div className="quick5">
          {[
            ["bag", t("Bitimlar"), "/deals"], ["chat", t("Chatlar"), "/chats"], ["rocket", "Boost", "/boosts"],
            ["send", "Telegram", "/tg/orders"], ["clock", t("Ijaralar"), "/rentals"],
          ].map(([ic, label, to]) => (
            <button key={to} onClick={() => nav(to)}><span className="rowico y"><Icon name={ic} /></span><span className="xs b">{label}</span></button>
          ))}
        </div>
      </div>
    </>
  );
}

function timeOnly(iso: string) {
  const d = new Date(iso);
  return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

function groupByDay(items: HistoryItem[]): [string, HistoryItem[]][] {
  const out: [string, HistoryItem[]][] = [];
  const today = new Date().toDateString();
  const yest = new Date(Date.now() - 86400000).toDateString();
  const months = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"];
  for (const i of items) {
    const d = new Date(i.created_at);
    const key = d.toDateString() === today ? t("BUGUN") : d.toDateString() === yest ? t("KECHA") : `${d.getDate()}-${t(months[d.getMonth()])}`.toUpperCase();
    const last = out[out.length - 1];
    if (last && last[0] === key) last[1].push(i);
    else out.push([key, [i]]);
  }
  return out;
}

const FAQ: [string, string][] = [
  ["Garant qanday ishlaydi?", "To'lov VAYNEXO'da saqlanadi. Akkauntni tekshirib tasdiqlaganingizdan so'ng pul sotuvchiga o'tkaziladi. Muammo bo'lsa nizo ochasiz va admin hal qiladi."],
  ["Hamyonni qanday to'ldiraman?", "Hamyon → To'ldirish. Tizim bergan ANIQ summani ko'rsatilgan kartaga o'tkazing. To'lov avtomatik topiladi va 1–3 daqiqada balansga tushadi."],
  ["Pulni qanday yechib olaman?", "Pul yechish faqat sotuvchi, ijaraga beruvchi va boosterlar uchun: sotuv, ijara va boost daromadi Hamyon → Yechish orqali kartaga chiqariladi (24 soat ichida). To'ldirilgan pul yechilmaydi — u xizmatlar uchun."],
  ["Noto'g'ri summa o'tkazib yubordim", "Xavotir olmang — @vaynexo_support ga chek (skrinshot) yuboring, admin qo'lda biriktiradi."],
  ["Almaz qancha vaqtda tushadi?", "Odatda 1–5 daqiqa. Agar provayder bajara olmasa, pul avtomatik hamyonga qaytariladi."],
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
2.3. To'ldirilgan pul faqat VAYNEXO xizmatlari uchun ishlatiladi va yechib olinmaydi.
2.4. Sotuv, ijara va boost daromadini yechish mumkin; so'rov 24 soat ichida bajariladi.
2.5. Har bir foydalanuvchiga hamyon ID beriladi. Uni qo'llab-quvvatlash xizmatiga murojaatda ko'rsatasiz; hech kimga parol yoki kod bermang.

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

const RENT = `1. Umumiy shartlar
1.1. Ushbu shartnoma akkaunt egasi (ijaraga beruvchi) va ijarachi o'rtasida VAYNEXO platformasi orqali tuziladi.
1.2. Ijara muddati: 12 soat, 24 soat, 3 kun yoki 1 hafta. Narx egasi belgilagan soatlik narx asosida hisoblanadi.

2. To'lov va garant
2.1. Ijara puli va depozit to'lov paytida hamyondan yechiladi va ijara tugaguncha garantda saqlanadi.
2.2. Ijara muvaffaqiyatli yakunlansa: egasiga ijara puli (platforma komissiyasi ushlangan holda), ijarachiga depozit to'liq qaytariladi.

3. Ijarachining majburiyatlari
3.1. Akkauntning parolini, pochtasini, telefon raqamini yoki bog'langan hisoblarini o'zgartirish qat'iyan taqiqlanadi.
3.2. Akkauntdagi almazni sarflash, skin yoki qahramonni sotish, akkauntni boshqa shaxsga berish taqiqlanadi.
3.3. Muddat tugagach akkauntdan chiqish shart.
3.4. Qoidabuzarlik aniqlansa depozit egasiga beriladi va hisob bloklanadi.

4. Egasining majburiyatlari
4.1. Kirish ma'lumotlari to'g'ri va ishlaydigan bo'lishi kerak.
4.2. Muddat tugagach parolni almashtirib, «Akkaunt qaytdi» tugmasini bosish kerak. 24 soat ichida bosilmasa, ijara avtomatik yakunlanadi.

5. Nizolar
5.1. Egasi «Muammo bor», ijarachi «Akkaunt ishlamayapti» orqali nizo ochishi mumkin.
5.2. Admin qarori: egasi haq — depozit egasiga; oddiy yakun — depozit ijarachiga; ijarachi haq — ijarachiga barcha pul qaytariladi. Admin qarori yakuniy.`;

const DOCS: Record<string, { title: string; date: string; key: string; body: string }> = {
  terms: { title: "Foydalanuvchi kelishuvi", date: "10.11.2026", body: TERMS,
    key: "Shartlarni o'qib, ularga rozilik berasiz. Kelishuvni buzish, ayniqsa sotilgan akkauntni qaytarib olish, bloklanish va javobgarlikka olib keladi." },
  privacy: { title: "Maxfiylik siyosati", date: "10.11.2026", body: PRIVACY,
    key: "VAYNEXO sizning ma'lumotlaringizni himoya qiladi va faqat xizmat ko'rsatish uchun ishlatadi." },
  rent: { title: "Ijara shartnomasi", date: "10.11.2026", body: RENT,
    key: "Ijaraga olishdan oldin shartlarni o'qing. Parol yoki pochtani o'zgartirish depozitni yo'qotishga va bloklanishga olib keladi." },
};

/** Matnni bo'limlarga ajratadi: "1. Sarlavha", "1.1. band", oddiy qator. */
function DocBody({ body }: { body: string }) {
  const sections = body.split(/\n\s*\n/).map((block) => {
    const [head, ...rest] = block.trim().split("\n");
    const m = head.match(/^(\d+)\.\s+(.*)$/);
    return { num: m?.[1] ?? "", title: m ? m[2] : head, lines: m ? rest : rest };
  });
  return (
    <>
      {sections.map((sec, i) => (
        <div key={i} className="card col">
          <div className="row"><span className="stepnum on">{sec.num || "•"}</span><span className="b">{t(sec.title)}</span></div>
          {sec.lines.map((ln, j) => {
            const m = ln.match(/^(\d+\.\d+)\.\s+(.*)$/);
            return m ? (
              <div key={j} className="row sm" style={{ alignItems: "flex-start" }}>
                <span className="y mono xs b" style={{ minWidth: 26, paddingTop: 2 }}>{m[1]}</span><span style={{ color: "#d6dbe8" }}>{t(m[2])}</span>
              </div>
            ) : <div key={j} className="sm" style={{ color: "#d6dbe8" }}>{t(ln)}</div>;
          })}
        </div>
      ))}
    </>
  );
}

export function Legal() {
  const nav = useNavigate();
  const docKey = useParams().doc ?? "terms";
  const doc = DOCS[docKey] ?? DOCS.terms;
  return (
    <>
      <Header title={t(doc.title)} sub={t("Kuchga kirgan sana: {d}", { d: doc.date })} right={<span />} />
      <div className="page withbar">
        {docKey !== "rent" && (
          <Seg value={docKey === "privacy" ? "privacy" : "terms"} onChange={(v) => nav(`/legal/${v}`, { replace: true })}
            options={[{ v: "terms", label: t("Foydalanuvchi kelishuvi") }, { v: "privacy", label: t("Maxfiylik siyosati") }]} />
        )}
        <div className="card row" style={{ borderColor: "rgba(29,233,182,.4)", background: "rgba(29,233,182,.06)", alignItems: "flex-start" }}>
          <span className="g"><Icon name="shield" /></span><span className="sm">{t(doc.key)}</span>
        </div>
        <DocBody body={doc.body} />
      </div>
      <BottomBar>
        <button className="btn full" onClick={() => nav(-1)}>{t("Roziman")}</button>
      </BottomBar>
    </>
  );
}

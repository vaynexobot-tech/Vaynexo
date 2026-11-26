import { useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import { openTg } from "../tg";
import { BottomNav, Copy, Empty, Field, Header, Loadable, money, som, useAction, useApp, useLoad } from "../ui";

interface Level { level: number; name: string; icon: string; pct: number; from: number; next: { name: string; icon: string; pct: number; need: number; at: number } | null }
interface Overview {
  enabled: boolean;
  levels: { name: string; icon: string; pct: number; from: number }[];
  shop: { slug: string; name: string; tagline: string; active: boolean; link: string | null; qr?: string | null } | null;
  level?: Level;
  sales_total?: number;
  rank?: number;
  stats?: { customers: number; buyers: number; orders: number; earned: number; week: { orders: number; earned: number }; today: { orders: number; earned: number } };
}
interface TopItem { place: number; name: string; slug: string; icon: string; level: string; orders: number; sales: number }

export default function Shop() {
  const st = useLoad(() => api.get<Overview>("/shop/my"));
  const top = useLoad(() => api.get<{ items: TopItem[] }>("/shop/top"));
  return (
    <>
      <Header title={t("Mening do'konim")} sub={t("Do'kon oching — komissiya oling")} icon="gift" />
      <div className="page">
        <Loadable state={st}>
          {(d) => !d.enabled ? <Empty icon="🏪" text={t("Do'konlar hozircha yopiq")} /> : d.shop ? <MyShop d={d} reload={st.reload} /> : <Create d={d} done={() => { st.reload(); top.reload(); }} />}
        </Loadable>
        <div className="sec-title">🏆 {t("Top do'konlar")} · {t("30 kun")}</div>
        {top.data && top.data.items.length === 0 && <div className="mut sm">{t("Hali savdo yo'q — birinchi bo'ling!")}</div>}
        <div className="col" style={{ gap: 8 }}>
          {(top.data?.items ?? []).map((x) => (
            <div key={x.slug} className="card row between tight">
              <div className="row">
                <span className="bb" style={{ width: 26 }}>{x.place <= 3 ? ["🥇", "🥈", "🥉"][x.place - 1] : x.place}</span>
                <div><div className="b">{x.name}</div><div className="mut xs">{x.icon} {x.level} · {x.orders} {t("ta buyurtma")}</div></div>
              </div>
              <span className="mono y b">{money(x.sales)}</span>
            </div>
          ))}
        </div>
      </div>
      <BottomNav />
    </>
  );
}

function Levels({ levels, cur }: { levels: Overview["levels"]; cur?: number }) {
  return (
    <div className="shop-levels">
      {levels.map((l, i) => (
        <div key={l.name} className={"shop-lvl" + (cur === i + 1 ? " on" : "")}>
          <span style={{ fontSize: 22 }}>{l.icon}</span>
          <b>{l.pct}%</b>
          <span className="mut xs">{l.name}</span>
          <span className="mut xs">{i === 0 ? t("boshlang'ich") : t("{n} dan", { n: money(l.from) })}</span>
        </div>
      ))}
    </div>
  );
}

function Create({ d, done }: { d: Overview; done: () => void }) {
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [tag, setTag] = useState("");
  const { busy, run } = useAction();
  const { toast } = useApp();
  const go = () => run(async () => { await api.post("/shop", { slug, name, tagline: tag }); toast(t("Do'kon ochildi!")); done(); });
  return (
    <>
      <div className="hero col" style={{ gap: 8, borderColor: "rgba(255,214,10,.45)" }}>
        <div className="hf bb" style={{ fontSize: 20 }}>🏪 {t("O'z donat do'koningni och")}</div>
        <div className="sm" style={{ color: "#d6dbe8" }}>{t("Shaxsiy havola oling. Kanal yoki guruhingizga qo'ying — u orqali kelganlar har xarid qilganda sizga komissiya avtomatik hamyonga tushadi.")}</div>
      </div>
      <Levels levels={d.levels} />
      <div className="card col">
        <Field label={t("Do'kon nomi")}><input className="input" value={name} maxLength={48} placeholder={t("Masalan: Aziz Gaming")} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label={t("Havola nomi (lotin harf, raqam, _)")}><input className="input" value={slug} maxLength={24} placeholder="aziz_gaming" onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))} /></Field>
        <Field label={t("Qisqa tavsif")}><input className="input" value={tag} maxLength={120} placeholder={t("Eng arzon almaz — kanal obunachilariga")} onChange={(e) => setTag(e.target.value)} /></Field>
        <button className="btn full" disabled={busy || name.trim().length < 2 || slug.length < 3} onClick={go}>{t("Do'kon ochish")}</button>
      </div>
    </>
  );
}

function MyShop({ d, reload }: { d: Overview; reload: () => void }) {
  const s = d.shop!, lv = d.level!, st = d.stats!;
  const link = s.link;
  const share = () => link && openTg(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(`${s.name} — ${s.tagline || t("Donat, Premium va Stars")}`)}`);
  const span = lv.next ? lv.next.at - lv.from : 1;
  const pct = lv.next ? Math.min(100, Math.max(0, Math.round(((d.sales_total! - lv.from) / span) * 100))) : 100;
  const { toast } = useApp();
  const [edit, setEdit] = useState(false);
  const [name, setName] = useState(s.name);
  const [tag, setTag] = useState(s.tagline);
  const { busy, run } = useAction();
  const save = () => run(async () => { await api.put("/shop", { name, tagline: tag }); setEdit(false); reload(); });
  return (
    <>
      <div className="hero col" style={{ gap: 6, borderColor: "rgba(255,214,10,.45)" }}>
        <div className="row between">
          <span className="badge g">{lv.icon} {lv.name} · {lv.pct}%</span>
          <span className="mut xs">{t("O'rningiz")}: #{d.rank}</span>
        </div>
        <div className="hf bb" style={{ fontSize: 20 }}>{s.name}</div>
        {s.tagline && <div className="mut sm">{s.tagline}</div>}
        <div className="bb mono y" style={{ fontSize: 26, marginTop: 4 }}>{som(st.earned)}</div>
        <div className="mut xs">{t("jami topilgan komissiya")} · {t("bugun")} +{money(st.today.earned)}</div>
      </div>

      <div className="card col">
        <div className="mut xs">{t("Do'kon havolangiz")}</div>
        {link ? <Copy value={link} /> : <div className="mut sm">{t("Havola tez orada paydo bo'ladi")}</div>}
        <button className="btn full" disabled={!link} onClick={share}>{t("Telegramda ulashish")}</button>
        {s.qr && (
          <div className="row" style={{ alignItems: "center", gap: 14 }}>
            <img src={s.qr} alt="QR" style={{ width: 120, height: 120, borderRadius: 12, background: "#fff", flexShrink: 0 }} />
            <div className="mut xs">{t("QR-kod: kanal, stream yoki do'koningiz rasmiga qo'ying. Skanerlagan odam sizning mijozingiz bo'ladi.")}</div>
          </div>
        )}
        <button className="btn ghost full" disabled={busy} onClick={() => run(async () => { await api.post("/shop/card"); toast(t("Reklama rasmi botga yuborildi"), "ok"); })}>🖼 {t("Reklama rasmini botga yubor")}</button>
      </div>

      <div className="grid3 center">
        <div className="card tight"><div className="bb mono">{st.customers}</div><div className="mut xs">{t("Mijozlar")}</div></div>
        <div className="card tight"><div className="bb mono">{st.orders}</div><div className="mut xs">{t("Buyurtmalar")}</div></div>
        <div className="card tight"><div className="bb mono g">{money(st.week.earned)}</div><div className="mut xs">{t("7 kun, so'm")}</div></div>
      </div>

      <div className="card col">
        {lv.next ? (
          <>
            <div className="row between"><b>{lv.icon} {lv.name}</b><b>{lv.next.icon} {lv.next.name} · {lv.next.pct}%</b></div>
            <div className="progress big"><i style={{ width: pct + "%" }} /></div>
            <div className="mut xs">{t("{n} savdo qoldi — komissiya {p}% ga oshadi", { n: som(lv.next.need), p: lv.next.pct })}</div>
          </>
        ) : <div className="b">💎 {t("Eng yuqori daraja!")}</div>}
      </div>
      <Levels levels={d.levels} cur={lv.level} />

      <div className="card col">
        <div className="b">{t("Qanday ishlaydi")}</div>
        {[t("Havolani kanal yoki guruhingizga joylang"), t("Kim birinchi marta shu havola orqali kirsa, doim sizning mijozingiz bo'ladi"),
          t("U har xarid qilganda komissiya hamyoningizga avtomatik tushadi va yechib olish mumkin"), t("Savdo oshgani sari daraja va foiz oshadi")].map((x, i) => (
          <div key={i} className="row" style={{ alignItems: "flex-start" }}><span className="mono y b">{i + 1}</span><span className="sm">{x}</span></div>
        ))}
      </div>

      {edit ? (
        <div className="card col">
          <Field label={t("Do'kon nomi")}><input className="input" value={name} maxLength={48} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label={t("Qisqa tavsif")}><input className="input" value={tag} maxLength={120} onChange={(e) => setTag(e.target.value)} /></Field>
          <button className="btn full" disabled={busy || name.trim().length < 2} onClick={save}>{t("Saqlash")}</button>
        </div>
      ) : <button className="btn ghost full" onClick={() => setEdit(true)}>{t("Nom va tavsifni o'zgartirish")}</button>}
    </>
  );
}

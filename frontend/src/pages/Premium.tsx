import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Pkg } from "../api";
import { t } from "../i18n";
import { confirmDialog, openTg } from "../tg";
import {
  BottomNav, Copy, dateTime, Empty, Field, Header, Icon, Loadable, money, MoneyInput, Seg, Sheet, som, Toggle, useAction, useApp, useFeature, useLoad,
} from "../ui";

// ================================================================ umumiy
export function PkgPicker({ value, onChange }: { value: number | null; onChange: (p: Pkg) => void }) {
  const pkgs = useLoad(() => api.get<Pkg[]>("/donate/packages?game=ML"));
  return (
    <Loadable state={pkgs}>
      {(list) => list.length === 0 ? <div className="mut sm">{t("Paketlar hozircha yo'q")}</div> : (
        <div className="grid3">
          {list.map((p) => (
            <button key={p.id} className={"pkg" + (value === p.id ? " on" : "")} onClick={() => onChange(p)}>
              <div className="b" style={{ fontSize: p.name.length > 14 ? 12 : 14, lineHeight: 1.2 }}>{p.name}</div>
              <div className="y b mono sm" style={{ marginTop: 6 }}>{money(p.price)}</div>
            </button>
          ))}
        </div>
      )}
    </Loadable>
  );
}

export function IdFields({ uid, zid, setUid, setZid }: { uid: string; zid: string; setUid: (v: string) => void; setZid: (v: string) => void }) {
  return (
    <div className="row" style={{ alignItems: "flex-end" }}>
      <div className="grow"><Field label="MLBB User ID"><input className="input mono" inputMode="numeric" placeholder="12345678" value={uid} onChange={(e) => setUid(e.target.value.replace(/\D/g, "").slice(0, 20))} /></Field></div>
      <div style={{ width: 110 }}><Field label="Zone ID"><input className="input mono" inputMode="numeric" placeholder="1234" value={zid} onChange={(e) => setZid(e.target.value.replace(/\D/g, "").slice(0, 10))} /></Field></div>
    </div>
  );
}

function leftText(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return t("tugadi");
  const m = Math.floor(ms / 60000), h = Math.floor(m / 60), d = Math.floor(h / 24);
  if (d > 0) return t("{d} kun {h} soat", { d, h: h % 24 });
  if (h > 0) return t("{h} soat {m} daq", { h, m: m % 60 });
  const s = Math.floor(ms / 1000) % 60;
  return t("{m} daq {s} son", { m, s });
}

function useTick(ms = 1000) {
  const [, set] = useState(0);
  useEffect(() => { const id = setInterval(() => set((x) => x + 1), ms); return () => clearInterval(id); }, [ms]);
}

/** Bosh sahifadagi premium bo'limlar kartasi. */
export function PremiumTiles() {
  const nav = useNavigate();
  const { me } = useApp();
  const top = useFeature("top"), market = useFeature("market");
  const tiles = [
    ...(me?.vay ? [{ to: "/vay", icon: me.vay.icon, title: `${me.vay.name} · ${money(me.vay.xp)} VAY`, sub: t("Daraja va keshbek") }] : []),
    { to: "/plus", icon: "💎", title: "VAYNEXO Plus", sub: me?.plus ? t("Faol · keshbek") : t("Har xariddan keshbek") },
    { to: "/savings", icon: "🏦", title: t("Skin jamg'armasi"), sub: t("Oz-ozdan yig'ib, bonus bilan ol") },
    { to: "/together", icon: "🤝", title: t("Birgalikda"), sub: t("Do'stlar bilan to'lov va orzular") },
    { to: "/shop", icon: "🏪", title: t("O'z do'koningni och"), sub: t("Mijozlardan 3–6% komissiya") },
    ...(top ? [{ to: "/top", icon: "🏆", title: t("Top xaridorlar"), sub: t("Top 100 reyting") }] : []),
    ...(market ? [{ to: "/sell", icon: "🛒", title: t("E'lon berish"), sub: t("Account sotish") }] : []),
  ];
  return (
    <>
      <div className="sec-title">✨ {t("Imkoniyatlar")}</div>
      <div className="arena-grid">
        {tiles.map((x) => (
          <button key={x.to} className={"arena-tile" + (x.to === "/plus" ? " hot" : "")} style={{ minHeight: 104 }} onClick={() => nav(x.to)}>
            <span className="arena-ico">{x.icon}</span>
            <span className="arena-t" style={{ fontSize: 15 }}>{x.title}</span>
            <span className="arena-s">{x.sub}</span>
          </button>
        ))}
      </div>
    </>
  );
}

// ================================================================ VAYNEXO Plus
interface PlusData {
  enabled: boolean; price: number; cashback: number; active: boolean; until: string | null; days_left: number; months: number;
  auto_renew: boolean; cashback_total: number;
  auto: { package_id: number; title: string; price: number; player_id: string; zone_id: string; next_at: string | null } | null;
}

export function PlusPage() {
  const st = useLoad(() => api.get<PlusData>("/plus"));
  const { me, refreshMe, toast } = useApp();
  const nav = useNavigate();
  const { busy, run } = useAction();
  const [setup, setSetup] = useState(false);
  const [pick, setPick] = useState<Pkg | null>(null);
  const [uid, setUid] = useState(me?.ml_id?.replace(/\D/g, "") ?? "");
  const [zid, setZid] = useState("");
  const buy = () => run(async () => { await api.post("/plus/buy"); toast(t("VAYNEXO Plus faollashtirildi!"), "ok"); st.reload(); refreshMe(); });
  const save = (body: object) => run(async () => { await api.put("/plus", body); st.reload(); });
  return (
    <>
      <Header title="VAYNEXO Plus" sub={t("Premium obuna")} icon="gem" />
      <div className="page">
        <Loadable state={st}>
          {(d) => !d.enabled ? <Empty icon="💎" text={t("Tez kunda")} /> : (
            <>
              <div className="hero col plus-hero" style={{ gap: 8 }}>
                <div className="row between">
                  <span className="badge y" style={{ background: "var(--y)", color: "#111" }}>💎 PLUS</span>
                  {d.active && <span className="g b xs">● {t("Faol")} · {t("{n} kun qoldi", { n: d.days_left })}</span>}
                </div>
                <div className="hf bb" style={{ fontSize: 22 }}>{d.active ? t("Siz Plus a'zosisiz") : t("Har xariddan pul qaytadi")}</div>
                <div className="row" style={{ alignItems: "baseline", gap: 6 }}>
                  <span className="bb mono y" style={{ fontSize: 28 }}>{money(d.price)}</span><span className="mut sm">{t("so'm / oy")}</span>
                </div>
                {d.active && d.until && <div className="mut xs">{t("Amal qiladi")}: {dateTime(d.until)}</div>}
              </div>

              <div className="card col" style={{ gap: 12 }}>
                {[
                  ["💰", t("{p}% keshbek", { p: d.cashback }), t("Har bajarilgan donat va Telegram xizmatidan hamyonga qaytadi")],
                  ["🔁", t("Haftalik avto-xarid"), t("Weekly Pass yoki boshqa paket har 7 kunda o'zi tushadi — unutmaysiz")],
                  ["🏆", t("Plus turnirlar"), t("Faqat a'zolar uchun yopiq turnirlar va sovrinlar")],
                  ["⚡️", t("Birinchi navbat"), t("Buyurtmalaringiz va murojaatlaringiz birinchi ko'riladi")],
                ].map(([i, a, b]) => (
                  <div key={a} className="row" style={{ alignItems: "flex-start" }}>
                    <span style={{ fontSize: 22, width: 30 }}>{i}</span>
                    <div><div className="b">{a}</div><div className="mut xs">{b}</div></div>
                  </div>
                ))}
              </div>

              {d.active && (
                <div className="grid3 center">
                  <div className="card tight"><div className="bb mono g">{money(d.cashback_total)}</div><div className="mut xs">{t("Keshbek, so'm")}</div></div>
                  <div className="card tight"><div className="bb mono">{d.months}</div><div className="mut xs">{t("Oy a'zolik")}</div></div>
                  <div className="card tight"><div className="bb mono">{d.days_left}</div><div className="mut xs">{t("Kun qoldi")}</div></div>
                </div>
              )}

              {(me?.balance ?? 0) < d.price && !d.active && (
                <div className="card tight sm">{t("Hamyonda {n} yetmayapti", { n: som(d.price - (me?.balance ?? 0)) })} · <a className="y b" onClick={() => nav("/wallet")}>{t("To'ldirish")}</a></div>
              )}
              <button className="btn full" disabled={busy || (me?.balance ?? 0) < d.price} onClick={buy}>
                {d.active ? t("30 kunga uzaytirish") : t("Obuna bo'lish")} · {som(d.price)}
              </button>

              {d.active && (
                <>
                  <div className="card row between">
                    <div><div className="b">{t("Avto-uzaytirish")}</div><div className="mut xs">{t("Muddat tugashidan oldin hamyondan avtomatik")}</div></div>
                    <Toggle on={d.auto_renew} onChange={(v) => save({ auto_renew: v })} />
                  </div>
                  <div className="card col">
                    <div className="b">🔁 {t("Haftalik avto-xarid")}</div>
                    {d.auto ? (
                      <>
                        <div className="kv"><span>{t("Paket")}</span><span className="b">{d.auto.title}</span></div>
                        <div className="kv"><span>ID</span><span className="mono">{d.auto.player_id}{d.auto.zone_id ? ` (${d.auto.zone_id})` : ""}</span></div>
                        <div className="kv"><span>{t("Keyingisi")}</span><span>{d.auto.next_at ? dateTime(d.auto.next_at) : "—"}</span></div>
                        <button className="btn ghost full" disabled={busy} onClick={() => save({ clear_auto: true })}>{t("O'chirish")}</button>
                      </>
                    ) : (
                      <>
                        <div className="mut sm">{t("Paketni tanlang — har 7 kunda hamyondan o'zi xarid qilinadi (keshbek bilan).")}</div>
                        <button className="btn ghost full" onClick={() => setSetup(true)}>{t("Sozlash")}</button>
                      </>
                    )}
                  </div>
                </>
              )}
            </>
          )}
        </Loadable>
      </div>
      <Sheet open={setup} onClose={() => setSetup(false)}>
        <div className="sec-title">🔁 {t("Haftalik avto-xarid")}</div>
        <IdFields uid={uid} zid={zid} setUid={setUid} setZid={setZid} />
        <PkgPicker value={pick?.id ?? null} onChange={setPick} />
        <button className="btn full" disabled={busy || !pick || uid.length < 5} onClick={() => run(async () => {
          await api.put("/plus", { package_id: pick!.id, player_id: uid, zone_id: zid }); setSetup(false); st.reload(); toast(t("Saqlandi"), "ok");
        })}>{t("Saqlash")}</button>
      </Sheet>
      <BottomNav />
    </>
  );
}

// ================================================================ Skin jamg'armasi
interface SavingItem {
  id: number; title: string; target: number; saved: number; weekly: number; status: string; pct: number; next_at: string | null; buy_at: string | null;
  bonus_pct: number; bonus_ready: boolean; bonus_amount: number; bonus_in_days: number | null; bonus: number; order_id: number | null;
}
interface SavingsData { enabled: boolean; bonus_pct: number; min_days: number; items: SavingItem[]; total_saved: number }

export function SavingsPage() {
  const st = useLoad(() => api.get<SavingsData>("/savings"));
  const { me, refreshMe, toast } = useApp();
  const nav = useNavigate();
  const { busy, run } = useAction();
  const [create, setCreate] = useState(false);
  const [pick, setPick] = useState<Pkg | null>(null);
  const [uid, setUid] = useState(me?.ml_id?.replace(/\D/g, "") ?? "");
  const [zid, setZid] = useState("");
  const [first, setFirst] = useState<number | "">("");
  const [weekly, setWeekly] = useState<number | "">("");
  const [buyAt, setBuyAt] = useState("");
  const [dep, setDep] = useState<SavingItem | null>(null);
  const [amt, setAmt] = useState<number | "">("");
  const done = async (d?: SavingsData) => { if (d) st.reload(); await refreshMe(); };
  return (
    <>
      <Header title={t("Skin jamg'armasi")} sub={t("Kutilayotgan skin uchun yig'ing")} icon="gift" />
      <div className="page">
        <Loadable state={st}>
          {(d) => !d.enabled ? <Empty icon="🏦" text={t("Tez kunda")} /> : (
            <>
              <div className="hero col" style={{ gap: 6, borderColor: "rgba(29,233,182,.4)" }}>
                <div className="hf bb" style={{ fontSize: 20 }}>🏦 {t("Yig'ing — bonus bilan oling")}</div>
                <div className="sm" style={{ color: "#d6dbe8" }}>{t("Yangi skin yoki event uchun pulni oz-ozdan yig'ing. Maqsadga yetganda +{p}% bonus bilan sotib olasiz.", { p: d.bonus_pct })}</div>
                {d.total_saved > 0 && <div className="mono b g">{t("Jamg'armada")}: {som(d.total_saved)}</div>}
              </div>
              <button className="btn full" onClick={() => setCreate(true)}>+ {t("Yangi jamg'arma")}</button>
              {d.items.length === 0 && <div className="mut sm center">{t("Hali jamg'arma yo'q")}</div>}
              {d.items.map((s) => (
                <div key={s.id} className="card col" style={{ gap: 8, opacity: s.status === "active" ? 1 : 0.6 }}>
                  <div className="row between">
                    <span className="b">{s.title}</span>
                    <span className={"pill-b " + (s.status === "active" ? "g" : s.status === "done" ? "y" : "m")}>
                      {s.status === "active" ? `${s.pct}%` : s.status === "done" ? t("Sotib olindi") : t("Bekor")}
                    </span>
                  </div>
                  <div className="progress big"><i style={{ width: s.pct + "%" }} /></div>
                  <div className="row between mut xs"><span className="mono">{money(s.saved)} / {money(s.target)}</span>
                    {s.weekly > 0 && s.status === "active" && <span>🔁 {money(s.weekly)} / {t("hafta")}</span>}</div>
                  {s.status === "active" && (
                    <div className="xs">{s.bonus_ready ? <span className="g">🎁 {t("Bonus tayyor: +{n}", { n: som(s.bonus_amount) })}</span>
                      : s.bonus_in_days != null ? <span className="mut">🎁 {t("Bonus {n} kundan keyin ochiladi", { n: s.bonus_in_days })}</span>
                        : <span className="mut">🎁 {t("Yarmini yig'ing — {d} kundan keyin +{p}% bonus", { d: d.min_days, p: s.bonus_pct })}</span>}</div>
                  )}
                  {s.buy_at && s.status === "active" && <div className="mut xs">📅 {t("Avtomatik xarid")}: {dateTime(s.buy_at)}</div>}
                  {s.status === "done" && s.bonus > 0 && <div className="g xs">+{som(s.bonus)} {t("bonus olindi")}</div>}
                  {s.status === "active" && (
                    <div className="row">
                      {s.saved < s.target
                        ? <button className="btn small grow" onClick={() => { setDep(s); setAmt(""); }}>+ {t("Qo'shish")}</button>
                        : <button className="btn small grow" disabled={busy} onClick={() => run(async () => {
                          const r = await api.post<SavingsData & { order_id: number }>(`/savings/${s.id}/buy`); await done(r); toast(t("Buyurtma berildi!"), "ok"); nav(`/donate/order/${r.order_id}`);
                        })}>🛒 {t("Sotib olish")}</button>}
                      <button className="btn small ghost" disabled={busy} onClick={() => run(async () => {
                        if (!(await confirmDialog(t("Jamg'arma bekor qilinsinmi? Pul hamyonga qaytadi, bonus yo'qoladi.")))) return;
                        await done(await api.post<SavingsData>(`/savings/${s.id}/cancel`));
                      })}>{t("Bekor")}</button>
                    </div>
                  )}
                </div>
              ))}
              <div className="card col">
                <div className="b">{t("Qanday ishlaydi")}</div>
                {[t("Paketni tanlang (masalan, kollab skin uchun almaz)"), t("Pulni istalgan paytda qo'shing yoki haftalik avto-yig'ishni yoqing"),
                  t("Pulning yarmi {d} kun tursa — xaridda +{p}% bonus", { d: d.min_days, p: d.bonus_pct }), t("Fikringiz o'zgarsa — bekor qiling, pul to'liq qaytadi")].map((x, i) => (
                  <div key={i} className="row" style={{ alignItems: "flex-start" }}><span className="mono y b">{i + 1}</span><span className="sm">{x}</span></div>
                ))}
              </div>
            </>
          )}
        </Loadable>
      </div>
      <Sheet open={create} onClose={() => setCreate(false)}>
        <div className="sec-title">{t("Yangi jamg'arma")}</div>
        <PkgPicker value={pick?.id ?? null} onChange={setPick} />
        <IdFields uid={uid} zid={zid} setUid={setUid} setZid={setZid} />
        <Field label={t("Hozir qo'yish (ixtiyoriy)")}><MoneyInput value={first} onChange={setFirst} placeholder="0" /></Field>
        <Field label={t("Har hafta avtomatik (ixtiyoriy)")}><MoneyInput value={weekly} onChange={setWeekly} placeholder="0" /></Field>
        <Field label={t("Shu kuni avtomatik sotib olish (ixtiyoriy)")}><input className="input" type="datetime-local" value={buyAt} onChange={(e) => setBuyAt(e.target.value)} /></Field>
        <button className="btn full" disabled={busy || !pick || uid.length < 5} onClick={() => run(async () => {
          await done(await api.post<SavingsData>("/savings", { package_id: pick!.id, player_id: uid, zone_id: zid, first: first || 0, weekly: weekly || 0, buy_at: buyAt ? new Date(buyAt).toISOString() : null }));
          setCreate(false); setFirst(""); setWeekly(""); setBuyAt("");
        })}>{t("Jamg'arma ochish")}</button>
      </Sheet>
      <Sheet open={!!dep} onClose={() => setDep(null)}>
        {dep && (
          <>
            <div className="sec-title">{dep.title}</div>
            <div className="mut sm">{t("Qoldi")}: {som(dep.target - dep.saved)} · {t("Hamyon")}: {som(me?.balance ?? 0)}</div>
            <Field label={t("Summa")}><MoneyInput value={amt} onChange={setAmt} /></Field>
            <div className="row">
              {[10_000, 25_000, dep.target - dep.saved].filter((v, i, a) => v > 0 && a.indexOf(v) === i).map((v) => (
                <button key={v} className="btn small ghost grow" onClick={() => setAmt(v)}>{money(v)}</button>
              ))}
            </div>
            <button className="btn full" disabled={busy || !amt || Number(amt) < 1000} onClick={() => run(async () => {
              await done(await api.post<SavingsData>(`/savings/${dep.id}/deposit`, { amount: amt })); setDep(null);
            })}>{t("Qo'shish")}</button>
          </>
        )}
      </Sheet>
      <BottomNav />
    </>
  );
}

// ================================================================ Efirda donat (tomoshabin sahifasi)
interface SDon { id: number; name: string; kind: string; title: string; amount: number; message: string; at: string | null; payout?: number; hidden?: boolean }
interface StreamPub { slug: string; name: string; about: string; count: number; enabled: boolean; min_money: number; top: { name: string; total: number }[]; recent: SDon[] }

export function StreamPage() {
  const slug = useParams().slug ?? "";
  const st = useLoad(() => api.get<StreamPub>(`/stream/s/${slug}`), [slug]);
  const { me, refreshMe, toast } = useApp();
  const { busy, run } = useAction();
  const [kind, setKind] = useState<"pack" | "money">("pack");
  const [pick, setPick] = useState<Pkg | null>(null);
  const [amt, setAmt] = useState<number | "">("");
  const [msg, setMsg] = useState("");
  const [anon, setAnon] = useState(false);
  const price = kind === "pack" ? pick?.price ?? 0 : Number(amt || 0);
  return (
    <>
      <Header title={st.data?.name ?? t("Striminer")} sub={t("Efirda donat")} icon="play" />
      <div className="page">
        <Loadable state={st}>
          {(d) => (
            <>
              <div className="hero col" style={{ gap: 6, borderColor: "rgba(255,90,140,.45)" }}>
                <div className="row between"><span className="badge r">● LIVE</span><span className="mut xs">{t("{n} ta donat", { n: d.count })}</span></div>
                <div className="hf bb" style={{ fontSize: 22 }}>🎥 {d.name}</div>
                {d.about && <div className="mut sm">{d.about}</div>}
                <div className="mut xs">{t("Donatingiz efirda ekranga chiqadi")}</div>
              </div>
              {!d.enabled ? <Empty icon="🎥" text={t("Bo'lim hozircha yopiq")} /> : (
                <>
                  <Seg value={kind} onChange={setKind} options={[{ v: "pack", label: "💎 " + t("Almaz") }, { v: "money", label: "💸 " + t("Pul") }]} />
                  {kind === "pack" ? (
                    <>
                      <div className="mut xs">{t("Almaz to'g'ridan-to'g'ri striminerning MLBB akkauntiga tushadi")}</div>
                      <PkgPicker value={pick?.id ?? null} onChange={setPick} />
                    </>
                  ) : (
                    <>
                      <Field label={t("Summa (kamida {n})", { n: money(d.min_money) })}><MoneyInput value={amt} onChange={setAmt} /></Field>
                      <div className="row">{[10_000, 20_000, 50_000, 100_000].map((v) => <button key={v} className="btn small ghost grow" onClick={() => setAmt(v)}>{money(v)}</button>)}</div>
                    </>
                  )}
                  <Field label={t("Xabar (efirda ko'rinadi)")}><textarea className="input" maxLength={150} value={msg} placeholder={t("Salom! Zo'r o'yin 🔥")} onChange={(e) => setMsg(e.target.value)} /></Field>
                  <div className="row between"><span className="sm">{t("Ismimni yashirish")}</span><Toggle on={anon} onChange={setAnon} /></div>
                  <button className="btn full" disabled={busy || price <= 0 || (me?.balance ?? 0) < price || (kind === "money" && price < d.min_money)} onClick={() => run(async () => {
                    await api.post(`/stream/s/${slug}/donate`, { kind, package_id: pick?.id, amount: kind === "money" ? price : 0, message: msg, anon });
                    toast(t("Donat yuborildi! Efirda ko'rinadi 🎉"), "ok"); setMsg(""); st.reload(); refreshMe();
                  })}>{t("Yuborish")}{price ? ` · ${som(price)}` : ""}</button>
                  {(me?.balance ?? 0) < price && <div className="mut xs center">{t("Hamyonda mablag' yetarli emas")}</div>}
                </>
              )}
              {d.top.length > 0 && (
                <>
                  <div className="sec-title">🏆 {t("Top donatchilar")} · {t("30 kun")}</div>
                  {d.top.map((x, i) => <div key={x.name} className="card tight row between"><span>{["🥇", "🥈", "🥉", "4", "5"][i]} <b>{x.name}</b></span><span className="mono y">{money(x.total)}</span></div>)}
                </>
              )}
              {d.recent.length > 0 && (
                <>
                  <div className="sec-title">{t("So'nggi donatlar")}</div>
                  {d.recent.map((x) => (
                    <div key={x.id} className="card tight col" style={{ gap: 2 }}>
                      <div className="row between"><b>{x.name}</b><span className="y xs">{x.kind === "money" ? "💸" : "💎"} {x.title}</span></div>
                      {x.message && <div className="mut sm">{x.message}</div>}
                    </div>
                  ))}
                </>
              )}
            </>
          )}
        </Loadable>
      </div>
      <BottomNav />
    </>
  );
}

// ================================================================ Striminer paneli
interface StreamDash {
  enabled: boolean; fee: number; min_money: number;
  streamer: null | { slug: string; name: string; about: string; player_id: string; zone_id: string; link: string | null; widget: string;
    total_count: number; total_packs: number; total_money: number; today: { money: number; count: number }; items: SDon[] };
}

export function StreamerPanel() {
  const st = useLoad(() => api.get<StreamDash>("/stream/me"));
  const { toast } = useApp();
  const { busy, run } = useAction();
  const [edit, setEdit] = useState(false);
  const [f, setF] = useState({ slug: "", name: "", about: "", player_id: "", zone_id: "" });
  const s = st.data?.streamer;
  useEffect(() => { if (s) setF({ slug: s.slug, name: s.name, about: s.about, player_id: s.player_id, zone_id: s.zone_id }); }, [s?.slug]); // eslint-disable-line react-hooks/exhaustive-deps
  const submit = () => run(async () => { await api.post("/stream/me", f); setEdit(false); st.reload(); toast(t("Saqlandi"), "ok"); });
  const form = (
    <div className="card col">
      <Field label={t("Kanal / nik")}><input className="input" value={f.name} maxLength={48} placeholder="Aziz Live" onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
      {!s && <Field label={t("Havola nomi (lotin harf, raqam, _)")}><input className="input" value={f.slug} maxLength={24} placeholder="aziz_live" onChange={(e) => setF({ ...f, slug: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "") })} /></Field>}
      <Field label={t("Qisqa tavsif")}><input className="input" value={f.about} maxLength={160} placeholder={t("Har kuni 20:00 da Mythic rank")} onChange={(e) => setF({ ...f, about: e.target.value })} /></Field>
      <IdFields uid={f.player_id} zid={f.zone_id} setUid={(v) => setF({ ...f, player_id: v })} setZid={(v) => setF({ ...f, zone_id: v })} />
      <div className="mut xs">{t("Almaz donatlari shu MLBB akkauntga tushadi")}</div>
      <button className="btn full" disabled={busy || f.name.trim().length < 2 || (!s && f.slug.length < 3) || f.player_id.length < 5 || !f.zone_id} onClick={submit}>{s ? t("Saqlash") : t("Striminer bo'lish")}</button>
    </div>
  );
  return (
    <>
      <Header title={t("Striminer paneli")} sub={t("Efirda almaz donati")} icon="play" />
      <div className="page">
        <Loadable state={st}>
          {(d) => !d.enabled ? <Empty icon="🎥" text={t("Tez kunda")} /> : !d.streamer ? (
            <>
              <div className="hero col" style={{ gap: 8, borderColor: "rgba(255,90,140,.45)" }}>
                <div className="hf bb" style={{ fontSize: 20 }}>🎥 {t("Efirda almaz oling")}</div>
                <div className="sm" style={{ color: "#d6dbe8" }}>{t("Tomoshabinlar sizga almaz paketi yoki pul yuboradi — efirda chiroyli alert chiqadi. Almaz to'g'ridan-to'g'ri MLBB akkauntingizga tushadi, pul hamyoningizga (yechib olish mumkin).")}</div>
              </div>
              {form}
            </>
          ) : (() => {
            const x = d.streamer!;
            return (
              <>
                <div className="hero col" style={{ gap: 6 }}>
                  <div className="row between"><span className="badge r">● LIVE</span><span className="mut xs">/{x.slug}</span></div>
                  <div className="hf bb" style={{ fontSize: 20 }}>{x.name}</div>
                  <div className="bb mono y" style={{ fontSize: 24 }}>{som(x.total_money)}</div>
                  <div className="mut xs">{t("hamyonga tushgan")} · {t("bugun")} +{money(x.today.money)} · {x.today.count} {t("donat")}</div>
                </div>
                <div className="grid3 center">
                  <div className="card tight"><div className="bb mono">{x.total_count}</div><div className="mut xs">{t("Donatlar")}</div></div>
                  <div className="card tight"><div className="bb mono">{money(x.total_packs)}</div><div className="mut xs">{t("Almaz, so'm")}</div></div>
                  <div className="card tight"><div className="bb mono">{d.fee}%</div><div className="mut xs">{t("Ulush (pul)")}</div></div>
                </div>
                <div className="card col">
                  <div className="b">🔗 {t("Donat havolasi")}</div>
                  <div className="mut xs">{t("Efir tavsifiga va chatga qo'ying")}</div>
                  {x.link ? <Copy value={x.link} /> : null}
                  <button className="btn full" disabled={!x.link} onClick={() => x.link && openTg(`https://t.me/share/url?url=${encodeURIComponent(x.link)}&text=${encodeURIComponent(t("Efirda almaz yuboring 💎"))}`)}>{t("Telegramda ulashish")}</button>
                </div>
                <div className="card col">
                  <div className="b">🖥 {t("OBS vidjet (alert)")}</div>
                  <div className="mut xs">{t("OBS → Sources → Browser → URL ga qo'ying. O'lcham: 800 × 300. Havolani hech kimga bermang.")}</div>
                  <Copy value={x.widget} />
                  <div className="row">
                    <button className="btn small grow" disabled={busy} onClick={() => run(async () => { await api.post("/stream/me/test"); toast(t("Sinov alerti yuborildi"), "ok"); })}>▶️ {t("Sinov alerti")}</button>
                    <button className="btn small ghost" disabled={busy} onClick={() => run(async () => {
                      if (!(await confirmDialog(t("Eski vidjet havolasi ishlamay qoladi. Davom etasizmi?")))) return;
                      await api.post("/stream/me/rotate"); st.reload();
                    })}>{t("Yangilash")}</button>
                  </div>
                </div>
                {edit ? form : <button className="btn ghost full" onClick={() => setEdit(true)}>{t("Ma'lumotlarni o'zgartirish")}</button>}
                <div className="sec-title">{t("So'nggi donatlar")}</div>
                {x.items.length === 0 && <div className="mut sm">{t("Hali donat yo'q")}</div>}
                {x.items.map((it) => (
                  <div key={it.id} className="card tight col" style={{ gap: 2, opacity: it.hidden ? 0.5 : 1 }}>
                    <div className="row between"><b>{it.name}</b><span className="y xs">{it.kind === "money" ? `💸 +${money(it.payout ?? 0)}` : it.kind === "test" ? "🧪 test" : `💎 ${it.title}`}</span></div>
                    {it.message && <div className="mut sm">{it.message}</div>}
                    <div className="row between"><span className="mut xs">{it.at ? dateTime(it.at) : ""}</span>
                      {!it.hidden && <a className="mut xs" onClick={() => run(async () => { await api.post(`/stream/me/hide/${it.id}`); st.reload(); })}>{t("Yashirish")}</a>}</div>
                  </div>
                ))}
              </>
            );
          })()}
        </Loadable>
      </div>
      <BottomNav />
    </>
  );
}

// ================================================================ Pro bilan o'yna
interface Slot {
  id: number; title: string; details: string; play_at: string; ends_at: string; min_bid: number; step: number; price: number; bids: number; status: string;
  next_bid: number; pro: { id: number; name: string; rank: string; bio: string; link: string }; mine: boolean; winner: boolean; leading: boolean;
  history?: { amount: number; at: string | null; me: boolean }[]; contact?: string;
}
interface ProMyData {
  enabled: boolean; fee: number; min_bid: number; earned: number;
  profile: { name: string; bio: string; link: string; rank: string; status: string; note: string } | null; own: Slot[]; won: Slot[];
}

const SLOT_STATUS: Record<string, [string, string]> = {
  open: ["Auksion", "g"], sold: ["Sotildi", "y"], done: ["Yakunlandi", "m"], disputed: ["Nizo", "r"], expired: ["Stavkasiz", "m"], cancelled: ["Bekor", "m"],
};

function SlotCard({ s, onClick }: { s: Slot; onClick: () => void }) {
  const st = SLOT_STATUS[s.status] ?? [s.status, "m"];
  return (
    <button className="card col click" style={{ gap: 6, textAlign: "left", borderColor: s.leading ? "rgba(29,233,182,.5)" : undefined }} onClick={onClick}>
      <div className="row between"><span className="b">🎮 {s.pro.name}{s.pro.rank ? <span className="mut xs"> · {s.pro.rank}</span> : null}</span><span className={"pill-b " + st[1]}>{t(st[0])}</span></div>
      <div className="sm">{s.title}</div>
      <div className="row between">
        <span className="mono y b">{money(s.price || s.min_bid)}</span>
        <span className="mut xs">{s.status === "open" ? `⏱ ${leftText(s.ends_at)} · ${s.bids} ${t("stavka")}` : dateTime(s.play_at)}</span>
      </div>
      {s.leading && s.status === "open" && <div className="g xs">✓ {t("Sizning stavkangiz yuqorida")}</div>}
    </button>
  );
}

export function ProList() {
  const st = useLoad(() => api.get<{ items: Slot[] }>("/pro"));
  const nav = useNavigate();
  useTick(30000);
  return (
    <>
      <Header title={t("Pro bilan o'yna")} sub={t("Auksion")} icon="trophy" />
      <div className="page">
        <div className="hero col" style={{ gap: 6, borderColor: "rgba(155,107,255,.5)" }}>
          <div className="hf bb" style={{ fontSize: 20 }}>🎮 {t("Mashhur o'yinchi bilan bir jamoada o'yna")}</div>
          <div className="sm" style={{ color: "#d6dbe8" }}>{t("Pro va striminerlar o'yin joyini auksionga qo'yadi. Eng yuqori stavka yutadi. Pul o'yin bo'lgach pro'ga o'tadi, bo'lmasa qaytariladi.")}</div>
        </div>
        <button className="btn ghost full" onClick={() => nav("/pro/my")}>{t("Mening auksionlarim / Pro bo'lish")}</button>
        <Loadable state={st}>
          {(d) => d.items.length === 0 ? <Empty icon="🎮" text={t("Hozircha ochiq auksion yo'q")} /> : (
            <>{d.items.map((s) => <SlotCard key={s.id} s={s} onClick={() => nav(`/pro/${s.id}`)} />)}</>
          )}
        </Loadable>
      </div>
      <BottomNav />
    </>
  );
}

export function ProSlotPage() {
  const id = useParams().id;
  const st = useLoad(() => api.get<Slot>(`/pro/${id}`), [id]);
  const { me, refreshMe } = useApp();
  const { busy, run } = useAction();
  const [amt, setAmt] = useState<number | "">("");
  const [reason, setReason] = useState("");
  const [disp, setDisp] = useState(false);
  useTick(1000);
  useEffect(() => { if (st.data && st.data.status === "open") setAmt(st.data.next_bid); }, [st.data?.next_bid]); // eslint-disable-line react-hooks/exhaustive-deps
  const act = (path: string, body: object = {}) => run(async () => { await api.post(`/pro/${id}/${path}`, body); st.reload(); refreshMe(); });
  return (
    <>
      <Header title={t("Auksion")} sub={st.data?.pro.name} icon="trophy" />
      <div className="page">
        <Loadable state={st}>
          {(s) => (
            <>
              <div className="hero col" style={{ gap: 6 }}>
                <div className="row between"><span className={"badge " + (SLOT_STATUS[s.status]?.[1] ?? "m")}>{t(SLOT_STATUS[s.status]?.[0] ?? s.status)}</span>
                  {s.status === "open" && <span className="mono b y">⏱ {leftText(s.ends_at)}</span>}</div>
                <div className="hf bb" style={{ fontSize: 20 }}>{s.title}</div>
                {s.details && <div className="mut sm pre">{s.details}</div>}
                <div className="kv"><span>{t("Joriy narx")}</span><span className="mono bb y">{money(s.price || s.min_bid)}</span></div>
                <div className="kv"><span>{t("O'yin vaqti")}</span><span>{dateTime(s.play_at)}</span></div>
                <div className="kv"><span>{t("Stavkalar")}</span><span className="mono">{s.bids}</span></div>
              </div>
              <div className="card col" style={{ gap: 4 }}>
                <div className="b">🎮 {s.pro.name} {s.pro.rank && <span className="mut xs">· {s.pro.rank}</span>}</div>
                {s.pro.bio && <div className="mut sm">{s.pro.bio}</div>}
                {s.pro.link && <div className="y xs ell">{s.pro.link}</div>}
              </div>
              {s.status === "open" && !s.mine && (
                <div className="card col">
                  {s.leading ? <div className="g b">✓ {t("Eng yuqori stavka sizniki")}</div> : (
                    <>
                      <Field label={t("Stavka (kamida {n})", { n: money(s.next_bid) })}><MoneyInput value={amt} onChange={setAmt} /></Field>
                      <div className="mut xs">{t("Summa hamyondan bloklanadi. Kimdir oshirsa — darhol qaytadi.")}</div>
                      <button className="btn full" disabled={busy || !amt || Number(amt) < s.next_bid || (me?.balance ?? 0) < Number(amt)} onClick={() => act("bid", { amount: amt })}>{t("Stavka qo'yish")} · {som(Number(amt || 0))}</button>
                    </>
                  )}
                </div>
              )}
              {s.contact && <div className="card col"><div className="b">📞 {t("Bog'lanish")}</div><div className="mono">{s.contact}</div></div>}
              {s.winner && s.status === "sold" && (
                <div className="card col">
                  <div className="sm">{t("O'yin bo'lgach tasdiqlang — pul pro'ga o'tadi. O'yin vaqtidan 24 soat o'tsa, avtomatik o'tadi.")}</div>
                  <button className="btn full" disabled={busy} onClick={() => act("confirm")}>✅ {t("O'yin bo'ldi")}</button>
                  {disp ? (
                    <>
                      <textarea className="input" maxLength={300} placeholder={t("Nima bo'ldi?")} value={reason} onChange={(e) => setReason(e.target.value)} />
                      <button className="btn ghost full" disabled={busy || reason.trim().length < 3} onClick={() => act("dispute", { reason })}>{t("Adminga yuborish")}</button>
                    </>
                  ) : <button className="btn ghost full" onClick={() => setDisp(true)}>⚠️ {t("O'yin bo'lmadi")}</button>}
                </div>
              )}
              {s.mine && (s.status === "open" || s.status === "sold") && (
                <button className="btn ghost full" disabled={busy} onClick={async () => {
                  if (await confirmDialog(t("Auksion bekor qilinsinmi? Stavka egasiga pul qaytadi."))) act("cancel");
                }}>{t("Bekor qilish")}</button>
              )}
              {s.history && s.history.length > 0 && (
                <>
                  <div className="sec-title">{t("Stavkalar tarixi")}</div>
                  {s.history.map((h, i) => <div key={i} className="kv"><span className="mut xs">{h.at ? dateTime(h.at) : ""}{h.me ? ` · ${t("siz")}` : ""}</span><span className="mono b">{money(h.amount)}</span></div>)}
                </>
              )}
              {s.status === "open" && <div className="mut xs center">{t("Oxirgi 2 daqiqada stavka qo'yilsa, auksion 2 daqiqaga uzayadi.")}</div>}
            </>
          )}
        </Loadable>
      </div>
      <BottomNav />
    </>
  );
}

export function ProMy() {
  const st = useLoad(() => api.get<ProMyData>("/pro/my"));
  const nav = useNavigate();
  const { toast } = useApp();
  const { busy, run } = useAction();
  const [ap, setAp] = useState({ name: "", bio: "", link: "", rank: "" });
  const [slot, setSlot] = useState(false);
  const [sf, setSf] = useState({ title: "", details: "", hours: 24, play: "", min_bid: "" as number | "", step: 5000 as number | "" });
  useEffect(() => { const p = st.data?.profile; if (p) setAp({ name: p.name, bio: p.bio, link: p.link, rank: p.rank }); }, [st.data?.profile?.name]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <Header title={t("Mening auksionlarim")} sub={t("Pro bilan o'yna")} icon="trophy" />
      <div className="page">
        <Loadable state={st}>
          {(d) => {
            const p = d.profile;
            const approved = p?.status === "approved";
            return (
              <>
                {d.won.length > 0 && <><div className="sec-title">🏆 {t("Yutgan auksionlarim")}</div>{d.won.map((s) => <SlotCard key={s.id} s={s} onClick={() => nav(`/pro/${s.id}`)} />)}</>}
                {approved ? (
                  <>
                    <div className="hero col" style={{ gap: 4 }}>
                      <div className="row between"><span className="badge g">✓ PRO</span><span className="mut xs">{t("Platforma ulushi")}: {d.fee}%</span></div>
                      <div className="hf bb" style={{ fontSize: 20 }}>{p!.name}</div>
                      <div className="mono y b">{t("Sotilgan")}: {som(d.earned)}</div>
                    </div>
                    <button className="btn full" onClick={() => { setSf({ ...sf, min_bid: d.min_bid, play: new Date(Date.now() + 2 * 86400000).toISOString().slice(0, 16) }); setSlot(true); }}>+ {t("Auksion ochish")}</button>
                    {d.own.map((s) => <SlotCard key={s.id} s={s} onClick={() => nav(`/pro/${s.id}`)} />)}
                  </>
                ) : (
                  <>
                    <div className="hero col" style={{ gap: 6 }}>
                      <div className="hf bb" style={{ fontSize: 20 }}>🎮 {t("Pro bo'ling")}</div>
                      <div className="sm" style={{ color: "#d6dbe8" }}>{t("Siz mashhur o'yinchi yoki striminermisiz? Muxlislaringiz siz bilan o'ynash uchun pul to'laydi.")}</div>
                      {p?.status === "pending" && <div className="y b sm">⏳ {t("Arizangiz ko'rib chiqilmoqda")}</div>}
                      {p?.status === "rejected" && <div className="r sm">❌ {t("Rad etildi")}{p.note ? `: ${p.note}` : ""}</div>}
                    </div>
                    {!d.enabled ? <Empty icon="🎮" text={t("Tez kunda")} /> : (
                      <div className="card col">
                        <Field label={t("Nik / kanal nomi")}><input className="input" maxLength={48} value={ap.name} onChange={(e) => setAp({ ...ap, name: e.target.value })} /></Field>
                        <Field label={t("Rank")}><input className="input" maxLength={32} value={ap.rank} placeholder="Mythical Immortal 150★" onChange={(e) => setAp({ ...ap, rank: e.target.value })} /></Field>
                        <Field label={t("Kanal / TikTok / YouTube havolasi")}><input className="input" maxLength={200} value={ap.link} onChange={(e) => setAp({ ...ap, link: e.target.value })} /></Field>
                        <Field label={t("O'zingiz haqingizda")}><textarea className="input" maxLength={300} value={ap.bio} onChange={(e) => setAp({ ...ap, bio: e.target.value })} /></Field>
                        <button className="btn full" disabled={busy || ap.name.trim().length < 2} onClick={() => run(async () => { await api.post("/pro/apply", ap); st.reload(); toast(t("Ariza yuborildi"), "ok"); })}>{t("Ariza yuborish")}</button>
                      </div>
                    )}
                  </>
                )}
              </>
            );
          }}
        </Loadable>
      </div>
      <Sheet open={slot} onClose={() => setSlot(false)}>
        <div className="sec-title">{t("Yangi auksion")}</div>
        <Field label={t("Nima taklif qilasiz")}><input className="input" maxLength={120} value={sf.title} placeholder={t("Men bilan 1 ta ranked o'yin (Mythic)")} onChange={(e) => setSf({ ...sf, title: e.target.value })} /></Field>
        <Field label={t("Batafsil (ixtiyoriy)")}><textarea className="input" maxLength={500} value={sf.details} placeholder={t("Discord/ovozli chat, efirda ko'rsataman")} onChange={(e) => setSf({ ...sf, details: e.target.value })} /></Field>
        <Field label={t("Auksion davomiyligi")}><Seg value={String(sf.hours)} onChange={(v) => setSf({ ...sf, hours: Number(v) })} options={[1, 6, 24, 48, 72].map((h) => ({ v: String(h), label: h < 24 ? `${h} ${t("soat")}` : `${h / 24} ${t("kun")}` }))} /></Field>
        <Field label={t("O'yin vaqti")}><input className="input" type="datetime-local" value={sf.play} onChange={(e) => setSf({ ...sf, play: e.target.value })} /></Field>
        <div className="row">
          <div className="grow"><Field label={t("Boshlang'ich narx")}><MoneyInput value={sf.min_bid} onChange={(v) => setSf({ ...sf, min_bid: v })} /></Field></div>
          <div className="grow"><Field label={t("Qadam")}><MoneyInput value={sf.step} onChange={(v) => setSf({ ...sf, step: v })} /></Field></div>
        </div>
        <button className="btn full" disabled={busy || sf.title.trim().length < 3 || !sf.min_bid || !sf.step || !sf.play} onClick={() => run(async () => {
          const r = await api.post<Slot>("/pro/slots", { title: sf.title, details: sf.details, min_bid: sf.min_bid, step: sf.step,
            ends_at: new Date(Date.now() + sf.hours * 3600000).toISOString(), play_at: new Date(sf.play).toISOString() });
          setSlot(false); nav(`/pro/${r.id}`);
        })}>{t("Auksionni boshlash")}</button>
      </Sheet>
      <BottomNav />
    </>
  );
}

// ================================================================ admin
export function SignalAdmin() {
  const st = useLoad(() => api.get<{ subscribers: number; default_text: string; history: { id: number; text: string; sent: number; at: string }[] }>("/admin/signals"));
  const { toast } = useApp();
  const { busy, run } = useAction();
  const [text, setText] = useState("");
  return (
    <Loadable state={st}>
      {(d) => (
        <>
          <div className="hero col" style={{ gap: 4 }}>
            <div className="hf bb" style={{ fontSize: 18 }}>⚡️ Ikki barobar almaz signali</div>
            <div className="mut sm">MLBB birinchi to'ldirish bonusini yangilaganda obunachilarga darhol xabar yuboring. Katalogda «double» paket paydo bo'lsa, bot sizga o'zi eslatadi.</div>
            <div className="bb mono y" style={{ fontSize: 24 }}>{d.subscribers} <span className="mut sm">obunachi</span></div>
          </div>
          <Field label="Xabar matni (bo'sh qolsa — standart)"><textarea className="input" rows={5} value={text} placeholder={d.default_text} onChange={(e) => setText(e.target.value)} /></Field>
          <button className="btn full" disabled={busy || d.subscribers === 0} onClick={() => run(async () => {
            if (!(await confirmDialog(`${d.subscribers} ta obunachiga yuborilsinmi?`))) return;
            const r = await api.post<{ sent: number }>("/admin/signals/double", { text }); toast(`Yuborildi: ${r.sent}`, "ok"); setText(""); st.reload();
          })}>⚡️ Signal yuborish</button>
          {d.history.length > 0 && <div className="sec-title">Tarix</div>}
          {d.history.map((h) => <div key={h.id} className="card tight col" style={{ gap: 2 }}><div className="row between"><span className="mut xs">{dateTime(h.at)}</span><span className="b xs">{h.sent} ta</span></div><div className="sm ell">{h.text}</div></div>)}
        </>
      )}
    </Loadable>
  );
}

export function ProAdmin() {
  const st = useLoad(() => api.get<{ applications: { user_id: number; name: string; bio: string; link: string; rank: string }[];
    disputes: { id: number; title: string; price: number; reason: string; pro_id: number; winner_id: number }[] }>("/admin/pro"));
  const { busy, run } = useAction();
  return (
    <Loadable state={st}>
      {(d) => (
        <>
          <div className="sec-title">Pro arizalar</div>
          {d.applications.length === 0 && <div className="mut sm">Yangi ariza yo'q</div>}
          {d.applications.map((a) => (
            <div key={a.user_id} className="card col" style={{ gap: 4 }}>
              <div className="b">{a.name} <span className="mut xs">· {a.rank} · ID {a.user_id}</span></div>
              {a.link && <div className="y xs ell">{a.link}</div>}
              {a.bio && <div className="mut sm">{a.bio}</div>}
              <div className="row">
                <button className="btn small grow" disabled={busy} onClick={() => run(async () => { await api.post(`/admin/pro/apps/${a.user_id}`, { approve: true }); st.reload(); })}>✅ Tasdiqlash</button>
                <button className="btn small ghost grow" disabled={busy} onClick={() => run(async () => { await api.post(`/admin/pro/apps/${a.user_id}`, { approve: false }); st.reload(); })}>Rad etish</button>
              </div>
            </div>
          ))}
          <div className="sec-title">Nizolar</div>
          {d.disputes.length === 0 && <div className="mut sm">Nizo yo'q</div>}
          {d.disputes.map((x) => (
            <div key={x.id} className="card col" style={{ gap: 4 }}>
              <div className="b">#{x.id} {x.title} · <span className="y mono">{money(x.price)}</span></div>
              <div className="mut xs">Pro: {x.pro_id} · G'olib: {x.winner_id}</div>
              <div className="sm">«{x.reason}»</div>
              <div className="row">
                <button className="btn small grow" disabled={busy} onClick={() => run(async () => { await api.post(`/admin/pro/disputes/${x.id}`, { pay: true }); st.reload(); })}>Pro'ga to'lash</button>
                <button className="btn small ghost grow" disabled={busy} onClick={() => run(async () => { await api.post(`/admin/pro/disputes/${x.id}`, { pay: false }); st.reload(); })}>G'olibga qaytarish</button>
              </div>
            </div>
          ))}
        </>
      )}
    </Loadable>
  );
}

/** Donat sahifasidagi «Ikki barobar qaytganda xabar ber» kartasi. */
export function DoubleSignalCard() {
  const st = useLoad(() => api.get<{ double: boolean }>("/signals"));
  const { run } = useAction();
  const on = !!st.data?.double;
  return (
    <div className="card row between" style={{ borderColor: on ? "rgba(255,214,10,.45)" : undefined }}>
      <div style={{ minWidth: 0 }}>
        <div className="b">⚡️ {t("Ikki barobar almaz signali")}</div>
        <div className="mut xs">{t("Birinchi to'ldirish bonusi qaytganda darhol xabar beramiz")}</div>
      </div>
      <Toggle on={on} onChange={(v) => run(async () => { await api.put("/signals/double", { on: v }); st.reload(); })} />
    </div>
  );
}

// ================================================================ VAY ball
interface VayData {
  enabled: boolean; xp: number; per: number; level: number; name: string; icon: string; cashback: number; from: number;
  next: { name: string; icon: string; need: number; at: number; cashback: number } | null;
  levels: { name: string; icon: string; from: number; cashback: number }[];
}

/** Bosh sahifadagi VAY darajasi kartasi. */
export function VayStrip() {
  const { me } = useApp();
  const nav = useNavigate();
  if (!me?.vay) return null;
  return (
    <button className="card row click between" style={{ textAlign: "left", borderColor: "rgba(155,107,255,.45)" }} onClick={() => nav("/vay")}>
      <div className="row"><span style={{ fontSize: 28 }}>{me.vay.icon}</span>
        <div><div className="b">{me.vay.name} · {money(me.vay.xp)} VAY</div><div className="mut xs">{t("Xarid qiling — daraja va keshbek oshadi")}</div></div></div>
      <Icon name="right" size={18} className="mut" />
    </button>
  );
}

export function VayPage() {
  const st = useLoad(() => api.get<VayData>("/vay"));
  return (
    <>
      <Header title="VAY" sub={t("Daraja va keshbek")} icon="gem" />
      <div className="page">
        <Loadable state={st}>
          {(d) => !d.enabled ? <Empty icon="🏅" text={t("Tez kunda")} /> : (
            <>
              <div className="hero col" style={{ gap: 6, borderColor: "rgba(155,107,255,.5)" }}>
                <div className="row between"><span className="badge v">{d.icon} {d.name}</span><span className="g b xs">{d.cashback}% {t("keshbek")}</span></div>
                <div className="bb mono y" style={{ fontSize: 30 }}>{money(d.xp)} <span className="mut sm">VAY</span></div>
                {d.next ? (
                  <>
                    <div className="progress big"><i style={{ width: Math.min(100, Math.round(((d.xp - d.from) / Math.max(1, d.next.at - d.from)) * 100)) + "%" }} /></div>
                    <div className="mut xs">{t("{n} VAY dan keyin {name} — {p}% keshbek", { n: money(d.next.need), name: d.next.name, p: d.next.cashback })}</div>
                  </>
                ) : <div className="b">👑 {t("Eng yuqori daraja!")}</div>}
              </div>
              <div className="shop-levels">
                {d.levels.map((l, i) => (
                  <div key={l.name} className={"shop-lvl" + (d.level === i + 1 ? " on" : "")}>
                    <span style={{ fontSize: 22 }}>{l.icon}</span><b>{l.cashback}%</b>
                    <span className="mut xs">{l.name}</span><span className="mut xs">{i === 0 ? t("boshlang'ich") : t("{n} dan", { n: money(l.from) })}</span>
                  </div>
                ))}
              </div>
              <div className="card col">
                <div className="b">{t("VAYni qanday yig'asiz")}</div>
                {[t("Donat va Telegram xizmatlari: har {n} so'm = 1 VAY", { n: money(d.per) }), t("Arena: viktorina, vazifa, turnir ballari = 1 VAY"),
                  t("Daraja oshgani sari har xariddan hamyonga keshbek qaytadi (Plus keshbegiga qo'shiladi)")].map((x, i) => (
                  <div key={i} className="row" style={{ alignItems: "flex-start" }}><span className="mono y b">{i + 1}</span><span className="sm">{x}</span></div>
                ))}
                <div className="mut xs">{t("VAY pulga almashtirilmaydi va sarflanmaydi — faqat darajangizni belgilaydi.")}</div>
              </div>
            </>
          )}
        </Loadable>
      </div>
      <BottomNav />
    </>
  );
}

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Boost, type Deal, type DonateOrder, type ListingFull, type Me, type Pkg, type TgOrder, type Topup, type Withdrawal } from "../api";
import { t } from "../i18n";
import { confirmDialog, openTg } from "../tg";
import { Chips, Copy, dateTime, Empty, Field, Header, Loadable, money, MoneyInput, Seg, Sheet, som, Status, Toggle, useAction, useApp, useLoad } from "../ui";

type Tab = "stats" | "settings" | "rent" | "moderation" | "incoming" | "withdraw" | "disputes" | "donate" | "tg" | "boost" | "users" | "packages" | "tournaments" | "kyc" | "partner" | "matches";

type Section = { v: Tab; icon: string; label: string; count?: string[] };
const QUEUE: Section[] = [
  { v: "incoming", icon: "💳", label: "Kirimlar va to'lovlar", count: ["unmatched", "topup_checking"] },
  { v: "withdraw", icon: "💸", label: "Pul yechish", count: ["withdrawals"] },
  { v: "moderation", icon: "📝", label: "E'lonlar", count: ["moderation"] },
  { v: "rent", icon: "🔑", label: "Ijara", count: ["rent_moderation", "rent_disputes"] },
  { v: "disputes", icon: "⚖️", label: "Nizolar", count: ["disputes"] },
  { v: "donate", icon: "💎", label: "Donat", count: ["donate_review"] },
  { v: "tg", icon: "⭐️", label: "TG xizmatlar", count: ["tg_pending"] },
  { v: "boost", icon: "🚀", label: "Boost", count: ["boost_open"] },
  { v: "kyc", icon: "🪪", label: "Identifikatsiya", count: ["kyc_pending"] },
  { v: "partner", icon: "🎬", label: "Hamkor videolari", count: ["partner_pending"] },
];
const MANAGE: Section[] = [
  { v: "users", icon: "👥", label: "Foydalanuvchilar" },
  { v: "settings", icon: "⚙️", label: "Sozlamalar" },
  { v: "packages", icon: "📦", label: "Donat paketlari" },
  { v: "tournaments", icon: "🏆", label: "Turnirlar" },
  { v: "matches", icon: "🎯", label: "Prognozlar" },
];

export default function Admin() {
  const { me } = useApp();
  const [tab, setTab] = useState<Tab>("stats");
  if (!me?.is_admin) return <><Header title="Admin" /><Empty icon="🔒" text={t("Ruxsat yo'q")} /></>;
  const sec = [...QUEUE, ...MANAGE].find((x) => x.v === tab);
  return (
    <>
      <Header title={sec ? `${sec.icon} ${sec.label}` : t("Admin panel")} right={<span />} />
      <div className="page">
        {tab !== "stats" && <button className="btn small ghost" style={{ alignSelf: "flex-start" }} onClick={() => setTab("stats")}>‹ Bo'limlar</button>}
        {tab === "stats" && <Stats go={setTab} />}
        {tab === "settings" && <AppSettings />}
        {tab === "rent" && <RentAdmin />}
        {tab === "incoming" && <Incoming />}
        {tab === "withdraw" && <Withdrawals />}
        {tab === "moderation" && <Moderation />}
        {tab === "disputes" && <Disputes />}
        {tab === "donate" && <DonateReview />}
        {tab === "tg" && <TgAdmin />}
        {tab === "boost" && <BoostAdmin />}
        {tab === "users" && <Users />}
        {tab === "packages" && <Packages />}
        {tab === "tournaments" && <Tournaments />}
        {tab === "kyc" && <KycAdmin />}
        {tab === "partner" && <PartnerAdmin />}
        {tab === "matches" && <MatchesAdmin />}
      </div>
    </>
  );
}

function Stats({ go }: { go: (t: Tab) => void }) {
  const st = useLoad(() => api.get<Record<string, number>>("/admin/stats"));
  const tile = (x: Section, s: Record<string, number>) => {
    const n = (x.count ?? []).reduce((a, k) => a + (s[k] || 0), 0);
    return (
      <button key={x.v} className={"adm-tile" + (n ? " hot" : "")} onClick={() => go(x.v)}>
        <span className="adm-ico">{x.icon}</span>
        <span className="adm-lbl">{x.label}</span>
        {x.count && <span className={"adm-n" + (n ? " on" : "")}>{n}</span>}
      </button>
    );
  };
  return (
    <Loadable state={st}>
      {(s) => {
        const total = QUEUE.reduce((a, x) => a + (x.count ?? []).reduce((b, k) => b + (s[k] || 0), 0), 0);
        return (
          <>
            <div className="grid2">
              <StatCard label="Foydalanuvchilar" value={money(s.users)} sub={`+${s.users_today} bugun`} />
              <StatCard label="Jami balanslar" value={money(s.balances_total)} sub="so'm (majburiyat)" />
              <StatCard label="To'ldirish (24 soat)" value={money(s.topups_today)} sub="so'm" />
              <StatCard label="Donat (24 soat)" value={money(s.donate_today)} sub="so'm" />
            </div>
            <div className="row between"><div className="sec-title">Navbat</div><span className={"badge " + (total ? "y" : "g")}>{total ? `${total} ta ish` : "Hammasi bajarilgan ✓"}</span></div>
            <div className="adm-grid">{QUEUE.map((x) => tile(x, s))}</div>
            <div className="sec-title">Boshqaruv</div>
            <div className="adm-grid">{MANAGE.map((x) => tile(x, s))}</div>
          </>
        );
      }}
    </Loadable>
  );
}

const StatCard = ({ label, value, sub }: { label: string; value: string; sub: string }) => (
  <div className="card"><div className="mut xs">{label}</div><div className="bb mono" style={{ fontSize: 18 }}>{value}</div><div className="mut xs">{sub}</div></div>
);

interface Incoming { id: number; amount: number; source: string; raw_text: string | null; status: string; created_at: string }

function Incoming() {
  const { toast } = useApp();
  const st = useLoad(() => api.get<Incoming[]>("/admin/incoming"));
  const [text, setText] = useState("");
  const [amount, setAmount] = useState<number | "">("");
  const [assign, setAssign] = useState<Incoming | null>(null);
  const { busy, run } = useAction();
  return (
    <>
      <div className="card col">
        <div className="b">Kirimni qo'lda kiritish</div>
        <div className="mut xs">Bank SMS/bildirishnoma matnini qo'ying yoki summani yozing. Mos so'rov topilsa, balans avtomatik to'ldiriladi. (Bank xabarini botga forward qilsangiz ham bo'ladi.)</div>
        <textarea className="input" placeholder="HUMOCARD *1234: Popolnenie 50 034.00 UZS" value={text} onChange={(e) => setText(e.target.value)} />
        <MoneyInput value={amount} onChange={setAmount} placeholder="yoki summa" />
        <button className="btn full" disabled={busy || (!text.trim() && !amount)} onClick={() => run(async () => {
          const r = await api.post<{ status: string; amount: number }>("/admin/incoming", { text: text || null, amount: amount || null });
          toast(r.status === "matched" ? `✅ ${money(r.amount)} biriktirildi` : `⚠️ ${money(r.amount)} — mos so'rov yo'q`, r.status === "matched" ? "ok" : "info");
          setText(""); setAmount(""); st.reload();
        })}>Qayd etish</button>
      </div>
      <TgBank />
      <SmsSetup />
      <CheckingTopups />
      <P2PCards />
      <div className="sec-title">Biriktirilmagan kirimlar</div>
      <Loadable state={st}>
        {(list) => list.length === 0 ? <Empty icon="✅" text="Hammasi biriktirilgan" /> : list.map((i) => (
          <div key={i.id} className="card col">
            <div className="row between"><span className="bb mono y">{som(i.amount)}</span><span className="mut xs">#{i.id} · {i.source} · {dateTime(i.created_at)}</span></div>
            {i.raw_text && <div className="mut xs pre">{i.raw_text}</div>}
            <div className="row">
              <button className="btn small grow" onClick={() => setAssign(i)}>So'rovga biriktirish</button>
              <button className="btn small ghost" onClick={async () => { if (await confirmDialog("E'tiborsiz qoldirasizmi?")) run(async () => { await api.post(`/admin/incoming/${i.id}/ignore`); st.reload(); }); }}>E'tiborsiz</button>
            </div>
          </div>
        ))}
      </Loadable>
      <AssignSheet inc={assign} onClose={() => setAssign(null)} onDone={() => { setAssign(null); st.reload(); }} />
    </>
  );
}

function AssignSheet({ inc, onClose, onDone }: { inc: Incoming | null; onClose: () => void; onDone: () => void }) {
  const [uid, setUid] = useState("");
  const list = useLoad(() => (inc ? api.get<Topup[]>(`/admin/topups?amount=${inc.amount}${uid ? `&user_id=${uid}` : ""}`) : Promise.resolve([])), [inc?.id, uid]);
  const { busy, run } = useAction();
  return (
    <Sheet open={!!inc} onClose={onClose}>
      <div className="sec-title">{inc ? som(inc.amount) : ""} — kimga?</div>
      <Field label="Foydalanuvchi ID (ixtiyoriy, chekdan)"><input className="input mono" inputMode="numeric" value={uid} onChange={(e) => setUid(e.target.value.replace(/\D/g, ""))} /></Field>
      <div className="mut xs">Summasi yaqin bo'lgan (±1000) to'lanmagan so'rovlar. Foydalanuvchiga KIRIMDAGI summa tushadi.</div>
      <Loadable state={list}>
        {(ts) => ts.length === 0 ? <Empty text="Mos so'rov yo'q" /> : (
          <div className="col">
            {ts.map((tp) => (
              <button key={tp.id} className="pkg row between" disabled={busy} onClick={() => run(async () => {
                if (!(await confirmDialog(`${som(inc!.amount)} → foydalanuvchi ${tp.user_id} (so'rov #${tp.id})?`))) return;
                await api.post(`/admin/incoming/${inc!.id}/assign`, { topup_id: tp.id });
                onDone();
              })}>
                <span><b className="mono">{money(tp.pay_amount)}</b><br /><span className="mut xs">user {tp.user_id} · #{tp.id} · {dateTime(tp.created_at)}</span></span>
                <Status s={tp.status} />
              </button>
            ))}
          </div>
        )}
      </Loadable>
    </Sheet>
  );
}

function Withdrawals() {
  const [status, setStatus] = useState("pending");
  const st = useLoad(() => api.get<Withdrawal[]>(`/admin/withdrawals?status=${status}`), [status]);
  const { busy, run } = useAction();
  const act = (w: Withdrawal, action: string) => run(async () => {
    const note = action === "reject" ? prompt("Rad etish sababi:") ?? "" : "";
    if (action === "paid" && !(await confirmDialog(`${som(w.amount)} → ${w.card} o'tkazildimi?`))) return;
    await api.post(`/admin/withdrawals/${w.id}`, { action, note });
    st.reload();
  });
  return (
    <>
      <Seg value={status} onChange={setStatus} options={[{ v: "pending", label: "Kutilmoqda" }, { v: "paid", label: "To'langan" }, { v: "rejected", label: "Rad etilgan" }]} />
      <Loadable state={st}>
        {(list) => list.length === 0 ? <Empty text="So'rovlar yo'q" /> : list.map((w) => (
          <div key={w.id} className="card col">
            <div className="row between"><span className="bb mono y">{som(w.amount)}</span><span className="mut xs">#{w.id} · user {w.user_id}</span></div>
            <Copy value={w.card.replace(/(\d{4})(?=\d)/g, "$1 ")} label={w.card_holder || "Karta"} />
            <div className="mut xs">{dateTime(w.created_at)}{w.admin_note ? " · " + w.admin_note : ""}</div>
            {w.status === "pending" && (
              <div className="row"><button className="btn small green grow" disabled={busy} onClick={() => act(w, "paid")}>To'landi</button><button className="btn small danger" disabled={busy} onClick={() => act(w, "reject")}>Rad etish</button></div>
            )}
          </div>
        ))}
      </Loadable>
    </>
  );
}

function Moderation() {
  const st = useLoad(() => api.get<ListingFull[]>("/admin/listings"));
  const { busy, run } = useAction();
  return (
    <Loadable state={st}>
      {(list) => list.length === 0 ? <Empty icon="✅" text="Moderatsiyada e'lon yo'q" /> : list.map((l) => (
        <div key={l.id} className="card col">
          {l.media.length > 0 && <div className="gallery">{l.media.map((m, i) => m.type === "video" ? <video key={i} src={m.url} controls preload="metadata" /> : <img key={i} src={m.url} alt="" />)}</div>}
          <div className="b">{l.title}</div>
          <div className="mut xs">#{l.id} · {l.game} · {l.rank} · {l.collection_level} · {l.skins} skin · {l.server}</div>
          <div className="y bb mono">{som(l.price)}</div>
          <div className="pre sm mut">{l.description}</div>
          <div className="mut xs">Sotuvchi: {l.seller.username ? "@" + l.seller.username : l.seller.name} (ID {l.seller.id})</div>
          <div className="row">
            <button className="btn small green grow" disabled={busy} onClick={() => run(async () => { await api.post(`/admin/listings/${l.id}/moderate`, { approve: true }); st.reload(); })}>Tasdiqlash</button>
            <button className="btn small danger" disabled={busy} onClick={() => { const reason = prompt("Rad etish sababi:"); if (reason !== null) run(async () => { await api.post(`/admin/listings/${l.id}/moderate`, { approve: false, reason }); st.reload(); }); }}>Rad etish</button>
          </div>
        </div>
      ))}
    </Loadable>
  );
}

function Disputes() {
  const nav = useNavigate();
  const st = useLoad(() => api.get<Deal[]>("/admin/deals"));
  const { busy, run } = useAction();
  const resolve = (d: Deal, winner: "buyer" | "seller") => run(async () => {
    const note = prompt(winner === "buyer" ? "Pul xaridorga qaytariladi. Izoh:" : "Pul sotuvchiga o'tadi. Izoh:");
    if (note === null) return;
    await api.post(`/admin/deals/${d.id}/resolve`, { winner, note });
    st.reload();
  });
  return (
    <Loadable state={st}>
      {(list) => list.length === 0 ? <Empty icon="✅" text="Ochiq nizolar yo'q" /> : list.map((d) => (
        <div key={d.id} className="card col">
          <div className="row between"><span className="b">Bitim #{d.id}</span><span className="y mono b">{som(d.price)}</span></div>
          <div className="mut xs">{d.listing.title} · xaridor {d.buyer_id} · sotuvchi {d.seller_id}</div>
          <div className="card tight sm pre">{d.dispute_reason}</div>
          {d.credentials && <div className="mut xs pre">🔐 {d.credentials}</div>}
          <button className="btn small ghost" onClick={() => nav(`/chat/${d.chat_id}`)}>Chatni ko'rish</button>
          <div className="row">
            <button className="btn small danger grow" disabled={busy} onClick={() => resolve(d, "buyer")}>Xaridor haq (qaytarish)</button>
            <button className="btn small green grow" disabled={busy} onClick={() => resolve(d, "seller")}>Sotuvchi haq</button>
          </div>
        </div>
      ))}
    </Loadable>
  );
}

function DonateReview() {
  const [status, setStatus] = useState("review");
  const st = useLoad(() => api.get<DonateOrder[]>(`/admin/donate?status=${status}`), [status]);
  const { busy, run } = useAction();
  const act = (o: DonateOrder, action: string, q: string) => run(async () => {
    if (!(await confirmDialog(q))) return;
    await api.post(`/admin/donate/${o.id}`, { action });
    st.reload();
  });
  return (
    <>
      <Seg value={status} onChange={setStatus} options={[{ v: "review", label: "Tekshiruv" }, { v: "processing", label: "Jarayonda" }, { v: "refunded", label: "Qaytarilgan" }, { v: "done", label: "Bajarilgan" }]} />
      <Loadable state={st}>
        {(list) => list.length === 0 ? <Empty text="Bo'sh" /> : list.map((o) => (
          <div key={o.id} className="card col">
            <div className="row between"><span className="b">{o.ref} · {o.title}</span><Status s={o.status} /></div>
            <div className="mut xs mono">Mijoz ID {o.user_id} · O'yin ID {o.player_id}{o.zone_id ? ` (${o.zone_id})` : ""} · {som(o.price)}</div>
            {o.error && <div className="r xs">{o.error}</div>}
            {o.status === "review" && (
              <div className="row">
                <button className="btn small green grow" disabled={busy} onClick={() => act(o, "done", "Provayderda bajarilganini tekshirdingizmi?")}>Bajarildi</button>
                <button className="btn small ghost" disabled={busy} onClick={() => act(o, "retry", "Provayderdan holatni qayta so'raysizmi?")}>Qayta tekshir</button>
                <button className="btn small danger" disabled={busy} onClick={() => act(o, "refund", "Pulni foydalanuvchiga qaytarasizmi?")}>Qaytarish</button>
              </div>
            )}
          </div>
        ))}
      </Loadable>
    </>
  );
}

const HIDE_TG = ["price_mode"];
const TG_LABEL: Record<string, string> = { months: "Muddat (oy)", stars: "Stars soni", gift: "Sovg'a", nft: "NFT", message: "Xabar", anonymous: "Anonim", link: "Havola", for_self: "O'ziga" };

function TgAdmin() {
  const [status, setStatus] = useState("processing");
  const st = useLoad(() => api.get<TgOrder[]>(`/admin/tg?status=${status}`), [status]);
  const { busy, run } = useAction();
  const act = (o: TgOrder, action: string) => run(async () => {
    const note = action === "refund" ? prompt("Qaytarish sababi:") : "";
    if (note === null) return;
    await api.post(`/admin/tg/${o.id}`, { action, note });
    st.reload();
  });
  return (
    <>
      <Seg value={status} onChange={setStatus} options={[{ v: "processing", label: "Yangi" }, { v: "done", label: "Bajarilgan" }, { v: "refunded", label: "Qaytarilgan" }]} />
      <Loadable state={st}>
        {(list) => list.length === 0 ? <Empty text="Buyurtmalar yo'q" /> : list.map((o) => (
          <div key={o.id} className="card col">
            <div className="row between"><span className="b">{o.title}</span><span className="y mono">{som(o.price)}</span></div>
            <Copy value={o.target_username} label={`Kimga · ${o.ref} · user ${o.user_id}`} />
            <div className="mut xs pre">{Object.entries(o.details).filter(([k, v]) => v !== "" && v !== false && v != null && !HIDE_TG.includes(k)).map(([k, v]) => `${TG_LABEL[k] ?? k}: ${v === true ? "ha" : v}`).join("\n")}</div>
            {o.status === "processing" && (
              <div className="row"><button className="btn small green grow" disabled={busy} onClick={() => act(o, "done")}>Bajarildi</button><button className="btn small danger" disabled={busy} onClick={() => act(o, "refund")}>Qaytarish</button></div>
            )}
          </div>
        ))}
      </Loadable>
    </>
  );
}

function BoostAdmin() {
  const [status, setStatus] = useState("searching");
  const st = useLoad(() => api.get<Boost[]>(`/admin/boost?status=${status}`), [status]);
  const { busy, run } = useAction();
  const act = (o: Boost, action: string) => run(async () => {
    if (!(await confirmDialog(action === "done" ? "Yakunlab, boosterga to'lansinmi?" : "Bekor qilib, mijozga pul qaytarilsinmi?"))) return;
    await api.post(`/admin/boost/${o.id}`, { action });
    st.reload();
  });
  return (
    <>
      <Chips value={status} onChange={setStatus} options={[["searching", "Booster kutmoqda"], ["accepted", "Qabul qilingan"], ["in_progress", "Jarayonda"], ["finished", "Tugatildi"], ["disputed", "Nizo"], ["done", "Yakunlangan"], ["refunded", "Qaytarilgan"]].map(([v, label]) => ({ v, label }))} />
      <Loadable state={st}>
        {(list) => list.length === 0 ? <Empty text="Bo'sh" /> : list.map((o) => (
          <div key={o.id} className="card col">
            <div className="row between"><span className="b">{o.ref} · {o.current_rank} → {o.target_rank}</span><span className="y mono">{som(o.price)}</span></div>
            <div className="mut xs pre">Mijoz ID {o.user_id} · kirish: {o.login_method} · booster: {o.booster_name ?? "—"}{o.note ? "\n" + o.note : ""}</div>
            {!["done", "refunded"].includes(o.status) && (
              <div className="row"><button className="btn small green grow" disabled={busy} onClick={() => act(o, "done")}>Yakunlash</button><button className="btn small danger" disabled={busy} onClick={() => act(o, "refund")}>Qaytarish</button></div>
            )}
          </div>
        ))}
      </Loadable>
    </>
  );
}

function Users() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const st = useLoad(() => api.get<(Me & { is_banned: boolean; created_at: string })[]>(`/admin/users?q=${encodeURIComponent(query)}`), [query]);
  const [adj, setAdj] = useState<{ id: number; name: string } | null>(null);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const { busy, run } = useAction();
  return (
    <>
      <form className="row" onSubmit={(e) => { e.preventDefault(); setQuery(q); }}><input className="input grow" placeholder="Hamyon ID, Telegram ID, @username yoki ism" value={q} onChange={(e) => setQ(e.target.value)} /><button className="btn">Qidirish</button></form>
      <Loadable state={st}>
        {(list) => list.map((u) => (
          <div key={u.id} className="card col">
            <div className="row between"><span className="b">{u.name} {u.username ? `@${u.username}` : ""}</span>{u.is_banned && <span className="badge r">BLOK</span>}</div>
            <div className="mut xs mono">{(u as Me & { wallet_id?: string }).wallet_id ?? ""} · ID {u.id} · {som(u.balance)} · {dateTime(u.created_at)}</div>
            <div className="row">
              <button className="btn small ghost grow" onClick={() => { setAdj({ id: u.id, name: u.name }); setAmount(""); setNote(""); }}>Balans</button>
              <button className={"btn small " + (u.is_banned ? "green" : "danger")} disabled={busy} onClick={async () => {
                if (await confirmDialog(u.is_banned ? "Blokdan chiqarasizmi?" : "Bloklaysizmi?")) run(async () => { await api.post(`/admin/users/${u.id}/ban`, { banned: !u.is_banned }); st.reload(); });
              }}>{u.is_banned ? "Blokdan chiqarish" : "Bloklash"}</button>
            </div>
          </div>
        ))}
      </Loadable>
      <Sheet open={!!adj} onClose={() => setAdj(null)}>
        <div className="sec-title">Balansni tuzatish · {adj?.name}</div>
        <Field label="Summa (ayirish uchun minus: -5000)"><input className="input mono" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^\d-]/g, ""))} /></Field>
        <Field label="Izoh (foydalanuvchiga ko'rinadi)"><input className="input" value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        <button className="btn full" disabled={busy || !Number(amount) || note.trim().length < 3} onClick={() => run(async () => {
          await api.post(`/admin/users/${adj!.id}/balance`, { amount: Number(amount), note, request_id: crypto.randomUUID() });
          setAdj(null); st.reload();
        })}>Saqlash</button>
      </Sheet>
    </>
  );
}

function Packages() {
  const st = useLoad(() => api.get<Pkg[]>("/admin/packages"));
  const [edit, setEdit] = useState<Partial<Pkg> | null>(null);
  const { busy, run } = useAction();
  const save = () => run(async () => {
    const body = { game: edit!.game ?? "ML", name: edit!.name, diamonds: edit!.diamonds ?? 0, bonus: edit!.bonus ?? 0, price: edit!.price, provider_sku: edit!.sku, is_active: edit!.is_active ?? true, is_hot: edit!.is_hot ?? false, sort: edit!.sort ?? 0 };
    if (edit!.id) await api.put(`/admin/packages/${edit!.id}`, body);
    else await api.post("/admin/packages", body);
    setEdit(null); st.reload();
  });
  return (
    <>
      <button className="btn full" onClick={() => setEdit({ game: "ML", is_active: true })}>+ Yangi paket</button>
      <Loadable state={st}>
        {(list) => list.map((p) => (
          <div key={p.id} className="card tight click row between" onClick={() => setEdit(p)} style={{ opacity: p.is_active ? 1 : 0.5 }}>
            <span><b>{p.game}</b> · {p.name} {p.is_hot && "🔥"}<br /><span className="mut xs mono">{p.sku}</span></span>
            <span className="y mono b">{money(p.price)}</span>
          </div>
        ))}
      </Loadable>
      <Sheet open={!!edit} onClose={() => setEdit(null)}>
        {edit && (
          <>
            <div className="sec-title">{edit.id ? "Paketni tahrirlash" : "Yangi paket"}</div>
            <Seg value={edit.game ?? "ML"} onChange={(g) => setEdit({ ...edit, game: g })} options={[{ v: "ML", label: "ML" }, { v: "MC", label: "MC" }]} />
            <Field label="Nomi"><input className="input" value={edit.name ?? ""} onChange={(e) => setEdit({ ...edit, name: e.target.value })} placeholder="172 almaz" /></Field>
            <div className="row">
              <Field label="Almaz"><input className="input mono" inputMode="numeric" value={edit.diamonds ?? ""} onChange={(e) => setEdit({ ...edit, diamonds: Number(e.target.value) || 0 })} /></Field>
              <Field label="Bonus"><input className="input mono" inputMode="numeric" value={edit.bonus ?? ""} onChange={(e) => setEdit({ ...edit, bonus: Number(e.target.value) || 0 })} /></Field>
              <Field label="Tartib"><input className="input mono" inputMode="numeric" value={edit.sort ?? ""} onChange={(e) => setEdit({ ...edit, sort: Number(e.target.value) || 0 })} /></Field>
            </div>
            <Field label="Narx (so'm)"><MoneyInput value={edit.price ?? ""} onChange={(v) => setEdit({ ...edit, price: v === "" ? undefined : v })} /></Field>
            <Field label="Provayder SKU (mahsulot kodi)"><input className="input mono" value={edit.sku ?? ""} onChange={(e) => setEdit({ ...edit, sku: e.target.value })} /></Field>
            <div className="row between"><span>Faol</span><Toggle on={edit.is_active ?? true} onChange={(v) => setEdit({ ...edit, is_active: v })} /></div>
            <div className="row between"><span>HOT belgisi</span><Toggle on={edit.is_hot ?? false} onChange={(v) => setEdit({ ...edit, is_hot: v })} /></div>
            <button className="btn full" disabled={busy || !edit.name || !edit.price || !edit.sku} onClick={save}>Saqlash</button>
          </>
        )}
      </Sheet>
    </>
  );
}

interface TourForm { id?: number; title: string; game: "ML" | "MC"; prize_fund: number | ""; entry_fee: number | ""; max_players: number; starts_at: string; rules: string; status: string }

function Tournaments() {
  const { toast } = useApp();
  const st = useLoad(() => Promise.all(["soon", "open", "running", "finished"].map((s) => api.get<(TourForm & { id: number; players_count: number })[]>(`/tournaments?status=${s}`))).then((r) => r.flat()));
  const [f, setF] = useState<TourForm | null>(null);
  const [entries, setEntries] = useState<{ user_id: number; nick: string; game_id: string; server: string; tg_username: string }[] | null>(null);
  const [entriesFor, setEntriesFor] = useState<number | null>(null);
  const { busy, run } = useAction();
  const blank: TourForm = { title: "", game: "ML", prize_fund: "", entry_fee: 0, max_players: 32, starts_at: new Date(Date.now() + 86400000 * 3).toISOString().slice(0, 16), rules: "", status: "open" };
  return (
    <>
      <button className="btn full" onClick={() => setF(blank)}>+ Turnir yaratish</button>
      <Loadable state={st}>
        {(list) => list.map((x) => (
          <div key={x.id} className="card col">
            <div className="row between"><span className="b">{x.title}</span><Status s={x.status} /></div>
            <div className="mut xs">{x.players_count}/{x.max_players} · {som(Number(x.prize_fund))} · {dateTime(x.starts_at)}</div>
            <div className="row">
              <button className="btn small ghost grow" onClick={() => setF({ ...x, starts_at: new Date(x.starts_at).toISOString().slice(0, 16) })}>Tahrirlash</button>
              <button className="btn small ghost grow" onClick={() => run(async () => { setEntriesFor(x.id); setEntries(await api.get(`/admin/tournaments/${x.id}/entries`)); })}>Ishtirokchilar</button>
            </div>
          </div>
        ))}
      </Loadable>
      <Sheet open={!!f} onClose={() => setF(null)}>
        {f && (
          <>
            <div className="sec-title">{f.id ? "Turnirni tahrirlash" : "Yangi turnir"}</div>
            <Field label="Nomi"><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
            <Seg value={f.game} onChange={(g) => setF({ ...f, game: g })} options={[{ v: "ML", label: "Mobile Legends" }, { v: "MC", label: "Magic Chess" }]} />
            <Field label="Sovrin fondi"><MoneyInput value={f.prize_fund} onChange={(v) => setF({ ...f, prize_fund: v })} /></Field>
            <Field label="Kirish to'lovi (0 = bepul)"><MoneyInput value={f.entry_fee} onChange={(v) => setF({ ...f, entry_fee: v })} /></Field>
            <Field label="Ishtirokchilar soni"><Chips value={f.max_players} onChange={(v) => setF({ ...f, max_players: v })} options={[16, 32, 64, 128, 256].map((v) => ({ v, label: String(v) }))} /></Field>
            <Field label="Boshlanish"><input className="input" type="datetime-local" value={f.starts_at} onChange={(e) => setF({ ...f, starts_at: e.target.value })} /></Field>
            <Field label="Qoidalar"><textarea className="input" value={f.rules} onChange={(e) => setF({ ...f, rules: e.target.value })} /></Field>
            <Field label="Holati"><Seg value={f.status} onChange={(s) => setF({ ...f, status: s })} options={[{ v: "soon", label: "Tez kunda" }, { v: "open", label: "Ochiq" }, { v: "running", label: "Davom" }, { v: "finished", label: "Tugagan" }]} /></Field>
            <button className="btn full" disabled={busy || !f.title || f.prize_fund === ""} onClick={() => run(async () => {
              const body = { ...f, entry_fee: f.entry_fee || 0, starts_at: new Date(f.starts_at).toISOString() };
              if (f.id) await api.put(`/admin/tournaments/${f.id}`, body);
              else await api.post("/admin/tournaments", body);
              setF(null); st.reload();
            })}>Saqlash</button>
            <div className="mut xs">G'oliblarga sovrinni «Foydalanuvchilar → Balans» orqali yozing.</div>
          </>
        )}
      </Sheet>
      <Sheet open={!!entries} onClose={() => setEntries(null)}>
        <div className="sec-title">Ishtirokchilar ({entries?.length})</div>
        {entries?.map((e, i) => <div key={e.user_id} className="listrow sm"><span className="mono">{i + 1}.</span><span className="grow"><b>{e.nick}</b> · {e.game_id} ({e.server})<br /><span className="mut xs">{e.tg_username} · user {e.user_id}</span></span>
          <button className="btn small ghost" onClick={() => run(async () => {
            if (!entriesFor || !(await confirmDialog(`${e.nick} — g'olib? Turnir yakunlanadi va ball beriladi.`))) return;
            await api.post(`/admin/tournaments/${entriesFor}/winner`, { user_id: e.user_id });
            toast("G'olib belgilandi", "ok"); setEntries(null); st.reload();
          })}>🏆</button></div>)}
      </Sheet>
    </>
  );
}

interface SettingRow { key: string; value: number | string; kind: "money" | "percent" | "choice"; min: number; max: number; label: string; group: string; choices: { v: string; label: string }[]; show_if?: { key: string; value: string } | null }

function AppSettings() {
  const { toast, refreshMe } = useApp();
  const st = useLoad(() => api.get<SettingRow[]>("/admin/settings"));
  const [draft, setDraft] = useState<Record<string, number | string | "">>({});
  const { busy, run } = useAction();
  const save = (key: string, value: number | string) => run(async () => {
    st.setData(await api.put<SettingRow[]>("/admin/settings", { key, value }));
    setDraft((d) => { const n = { ...d }; delete n[key]; return n; });
    toast("Saqlandi", "ok");
    refreshMe();
  });
  return (
    <Loadable state={st}>
      {(rows) => {
        const groups = [...new Set(rows.map((r) => r.group))];
        const val = Object.fromEntries(rows.map((r) => [r.key, r.value]));
        return (
          <>
            {groups.map((g) => (
              <div key={g} className="card col">
                <div className="sec-title" style={{ fontSize: 15 }}>{g}</div>
                {rows.filter((r) => r.group === g).map((r) => {
                  if (r.show_if && val[r.show_if.key] !== r.show_if.value) return null;
                  const v = draft[r.key] ?? r.value;
                  if (r.kind === "choice")
                    return (
                      <Field key={r.key} label={r.label}>
                        <Seg value={String(r.value)} onChange={(x) => save(r.key, x)} options={r.choices} />
                      </Field>
                    );
                  return (
                    <Field key={r.key} label={r.label}>
                      <div className="row">
                        {r.kind === "percent" ? (
                          <div className="row grow input" style={{ padding: "0 14px" }}>
                            <input className="grow mono" inputMode="numeric" style={{ background: "none", border: 0, outline: "none", height: "100%" }}
                              value={v} onChange={(e) => setDraft({ ...draft, [r.key]: e.target.value ? Number(e.target.value.replace(/\D/g, "").slice(0, 4)) : "" })} />
                            <span className="mut b">%</span>
                          </div>
                        ) : (
                          <div className="grow"><MoneyInput value={v as number | ""} onChange={(x) => setDraft({ ...draft, [r.key]: x })} /></div>
                        )}
                        <button className="btn" disabled={busy || v === "" || v === r.value} onClick={() => save(r.key, v as number)}>Saqlash</button>
                      </div>
                    </Field>
                  );
                })}
              </div>
            ))}
          </>
        );
      }}
    </Loadable>
  );
}

interface AdminRentListing { id: number; title: string; rank: string; skins: number; price_per_hour: number; description: string; media: { url: string; type: string }[]; owner: { id: number; name: string; username: string | null } }
interface AdminRental { id: number; listing: { title: string }; price: number; deposit: number; dispute_by: string | null; dispute_reason: string | null; renter_id: number; owner_id: number; credentials: string | null }

function RentAdmin() {
  const [view, setView] = useState<"moderation" | "disputes">("moderation");
  const mod = useLoad(() => api.get<AdminRentListing[]>("/admin/rent/listings"), [view]);
  const dis = useLoad(() => api.get<AdminRental[]>("/admin/rentals"), [view]);
  const { busy, run } = useAction();
  return (
    <>
      <Seg value={view} onChange={setView} options={[{ v: "moderation", label: "Moderatsiya" }, { v: "disputes", label: "Nizolar" }]} />
      {view === "moderation" ? (
        <Loadable state={mod}>
          {(list) => list.length === 0 ? <Empty icon="✅" text="Moderatsiyada ijara e'loni yo'q" /> : list.map((l) => (
            <div key={l.id} className="card col">
              {l.media.length > 0 && <div className="gallery">{l.media.map((m, i) => <img key={i} src={m.url} alt="" />)}</div>}
              <div className="b">{l.title}</div>
              <div className="mut xs">#{l.id} · {l.rank} · {l.skins} skin · {som(l.price_per_hour)}/soat · egasi {l.owner.username ? "@" + l.owner.username : l.owner.name} ({l.owner.id})</div>
              <div className="pre sm mut">{l.description}</div>
              <div className="row">
                <button className="btn small green grow" disabled={busy} onClick={() => run(async () => { await api.post(`/admin/rent/listings/${l.id}/moderate`, { approve: true }); mod.reload(); })}>Tasdiqlash</button>
                <button className="btn small danger" disabled={busy} onClick={() => { const reason = prompt("Rad etish sababi:"); if (reason !== null) run(async () => { await api.post(`/admin/rent/listings/${l.id}/moderate`, { approve: false, reason }); mod.reload(); }); }}>Rad etish</button>
              </div>
            </div>
          ))}
        </Loadable>
      ) : (
        <Loadable state={dis}>
          {(list) => list.length === 0 ? <Empty icon="✅" text="Ochiq ijara nizolari yo'q" /> : list.map((r) => (
            <div key={r.id} className="card col">
              <div className="row between"><span className="b">Ijara #{r.id} · {r.listing.title}</span><span className="badge r">{r.dispute_by === "owner" ? "Egasi" : "Ijarachi"}</span></div>
              <div className="mut xs">Narx {som(r.price)} · depozit {som(r.deposit)} · ijarachi {r.renter_id} · egasi {r.owner_id}</div>
              <div className="card tight sm pre">{r.dispute_reason}</div>
              {r.credentials && <div className="mut xs pre">🔐 {r.credentials}</div>}
              <div className="col">
                {([["owner", "Egasi haq: depozit egasiga"], ["normal", "Oddiy yakun: depozit ijarachiga"], ["renter", "Ijarachi haq: hammasi qaytariladi"]] as const).map(([d, label]) => (
                  <button key={d} className={"btn small " + (d === "renter" ? "danger" : d === "owner" ? "green" : "ghost")} disabled={busy} onClick={() => {
                    const note = prompt("Izoh:");
                    if (note !== null) run(async () => { await api.post(`/admin/rentals/${r.id}/resolve`, { decision: d, note }); dis.reload(); });
                  }}>{label}</button>
                ))}
              </div>
            </div>
          ))}
        </Loadable>
      )}
    </>
  );
}


function KycAdmin() {
  const { toast } = useApp();
  const st = useLoad(() => api.get<{ id: number; name: string; username: string | null; at: string | null }[]>("/admin/kyc"));
  const { run } = useAction();
  return (
    <Loadable state={st}>
      {(list) => list.length === 0 ? <Empty text="Kutilayotgan so'rov yo'q" /> : (
        <>
          <div className="mut xs">Rasmlar sizga botda yuborilgan. Shu yerda yoki botdagi tugmalar bilan qaror qiling.</div>
          {list.map((u) => (
            <div key={u.id} className="card row">
              <div className="grow"><div className="b">{u.name} {u.username ? `@${u.username}` : ""}</div><div className="mut xs">ID {u.id} · {u.at ? dateTime(u.at) : ""}</div></div>
              <button className="btn small green" onClick={() => run(async () => { await api.post(`/admin/kyc/${u.id}`, { approve: true }); toast("Tasdiqlandi", "ok"); st.reload(); })}>✓</button>
              <button className="btn small danger" onClick={() => run(async () => { const note = window.prompt("Rad etish sababi") ?? ""; await api.post(`/admin/kyc/${u.id}`, { approve: false, note }); st.reload(); })}>✕</button>
            </div>
          ))}
        </>
      )}
    </Loadable>
  );
}

interface PVideo { id: number; user_id: number; platform: string; url: string; status: string; created_at: string }

function PartnerAdmin() {
  const { toast } = useApp();
  const st = useLoad(() => api.get<PVideo[]>("/admin/partner/videos"));
  const [cur, setCur] = useState<PVideo | null>(null);
  const [views, setViews] = useState<number | "">("");
  const [likes, setLikes] = useState<number | "">("");
  const { busy, run } = useAction();
  const decide = (approve: boolean) => run(async () => {
    const note = approve ? null : (window.prompt("Rad etish sababi") ?? "Talablarga mos emas");
    await api.post(`/admin/partner/videos/${cur!.id}`, { approve, views: views || 0, likes: likes || 0, note });
    toast(approve ? "Tasdiqlandi, mukofot berildi" : "Rad etildi", "ok");
    setCur(null); st.reload();
  });
  return (
    <>
      <Loadable state={st}>
        {(list) => list.length === 0 ? <Empty text="Tekshiruvdagi video yo'q" /> : list.map((v) => (
          <div key={v.id} className="card row click" onClick={() => { setCur(v); setViews(""); setLikes(""); }}>
            <div className="grow" style={{ minWidth: 0 }}><div className="b ell sm">{v.url}</div><div className="mut xs">#{v.id} · {v.platform} · user {v.user_id} · {dateTime(v.created_at)}</div></div>
            <span className="y">›</span>
          </div>
        ))}
      </Loadable>
      <Sheet open={!!cur} onClose={() => setCur(null)}>
        <div className="sec-title" style={{ marginTop: 0 }}>Hamkor videosi #{cur?.id}</div>
        <div className="col">
          <button className="btn ghost full" onClick={() => cur && (window.Telegram?.WebApp?.openLink ? window.Telegram.WebApp.openLink(cur.url) : openTg(cur.url))}>Videoni ochish ↗</button>
          <div className="mut xs">Ko'rishlar video joylanganidan 10 kun o'tgach kiritiladi. Daraja ko'rishlarga qarab avtomatik aniqlanadi.</div>
          <Field label="Ko'rishlar"><MoneyInput value={views} onChange={setViews} /></Field>
          <Field label="Layklar"><MoneyInput value={likes} onChange={setLikes} /></Field>
          <div className="row">
            <button className="btn danger grow" disabled={busy} onClick={() => decide(false)}>Rad etish</button>
            <button className="btn green grow" disabled={busy || !views} onClick={() => decide(true)}>Tasdiqlash</button>
          </div>
        </div>
      </Sheet>
    </>
  );
}

interface MatchRow { id: number; title: string; team_a: string; team_b: string; starts_at: string; status: string; result: string | null }

function MatchesAdmin() {
  const { toast } = useApp();
  const st = useLoad(() => api.get<MatchRow[]>("/admin/arena/matches"));
  const [f, setF] = useState({ title: "", team_a: "", team_b: "", starts_at: "" });
  const { busy, run } = useAction();
  return (
    <>
      <div className="card col">
        <div className="b">Yangi bepul prognoz</div>
        <Field label="Nomi"><input className="input" placeholder="Noyabr kubogi · yarim final" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <div className="row">
          <input className="input grow" placeholder="1-jamoa" value={f.team_a} onChange={(e) => setF({ ...f, team_a: e.target.value })} />
          <input className="input grow" placeholder="2-jamoa" value={f.team_b} onChange={(e) => setF({ ...f, team_b: e.target.value })} />
        </div>
        <Field label="Boshlanish"><input className="input" type="datetime-local" value={f.starts_at} onChange={(e) => setF({ ...f, starts_at: e.target.value })} /></Field>
        <button className="btn full" disabled={busy || !f.title || !f.team_a || !f.team_b || !f.starts_at} onClick={() => run(async () => {
          await api.post("/admin/arena/matches", { ...f, starts_at: new Date(f.starts_at).toISOString() });
          setF({ title: "", team_a: "", team_b: "", starts_at: "" }); toast("Qo'shildi", "ok"); st.reload();
        })}>Qo'shish</button>
      </div>
      <Loadable state={st}>
        {(list) => list.map((m) => (
          <div key={m.id} className="card col">
            <div className="row between"><span className="b">{m.title}</span><span className="mut xs">{dateTime(m.starts_at)}</span></div>
            {m.status === "settled" ? <div className="g sm">G'olib: {m.result === "a" ? m.team_a : m.team_b}</div> : (
              <div className="row">
                <button className="btn small ghost grow" onClick={() => run(async () => { const r = await api.post<{ winners: number }>(`/admin/arena/matches/${m.id}/settle`, { result: "a" }); toast(`${r.winners} kishiga ball berildi`, "ok"); st.reload(); })}>🏆 {m.team_a}</button>
                <button className="btn small ghost grow" onClick={() => run(async () => { const r = await api.post<{ winners: number }>(`/admin/arena/matches/${m.id}/settle`, { result: "b" }); toast(`${r.winners} kishiga ball berildi`, "ok"); st.reload(); })}>🏆 {m.team_b}</button>
              </div>
            )}
          </div>
        ))}
      </Loadable>
    </>
  );
}


function CheckingTopups() {
  const { toast } = useApp();
  const st = useLoad(() => api.get<Topup[]>("/admin/topups/checking"));
  const { busy, run } = useAction();
  return (
    <>
      <div className="sec-title">«To'ladim» — tekshiruvda</div>
      <Loadable state={st}>
        {(list) => list.length === 0 ? <div className="mut sm">Tekshiruvda to'lov yo'q</div> : list.map((x) => (
          <div key={x.id} className="card col">
            <div className="row between"><span className="bb mono y">{som(x.pay_amount)}</span><span className="mut xs">#{x.id} · {x.user_name} · ID {x.user_id}</span></div>
            <div className="mut xs">Bank xabari hali kelmagan · kartaga aynan shu summa tushganini bank ilovasida tekshiring</div>
            <div className="row">
              <button className="btn small danger grow" disabled={busy} onClick={() => run(async () => {
                const reason = window.prompt("Rad etish sababi", "To'lov kartaga tushmagan") ?? "";
                await api.post(`/admin/topups/${x.id}/reject`, { reason }); st.reload();
              })}>Rad etish</button>
              <button className="btn small green grow" disabled={busy} onClick={() => run(async () => {
                if (!(await confirmDialog(`${money(x.pay_amount)} so'm kartaga tushganmi? Balans to'ldiriladi.`))) return;
                await api.post(`/admin/topups/${x.id}/confirm`); toast("Balans to'ldirildi", "ok"); st.reload();
              })}>Tasdiqlash</button>
            </div>
          </div>
        ))}
      </Loadable>
    </>
  );
}

interface P2PCardRow { id: number; number: string; holder: string; kind: string; active: boolean; sort: number }

function P2PCards() {
  const st = useLoad(() => api.get<P2PCardRow[]>("/admin/p2p-cards"));
  const [num, setNum] = useState("");
  const [holder, setHolder] = useState("");
  const { busy, run } = useAction();
  return (
    <>
      <div className="sec-title">To'lov kartalari</div>
      <div className="mut xs">Foydalanuvchilar pulni shu kartalarga o'tkazadi. Faol kartalarning hammasi to'lov ekranida ko'rinadi.</div>
      <Loadable state={st}>
        {(list) => (
          <>
            {list.length === 0 && <div className="mut sm">Karta qo'shilmagan — hozircha server sozlamasidagi karta ishlatiladi.</div>}
            {list.map((c) => (
              <div key={c.id} className="card row tight" style={{ opacity: c.active ? 1 : 0.5 }}>
                <div className="grow"><div className="b mono">{c.number}</div><div className="mut xs">{c.kind} · {c.holder || "—"}</div></div>
                <Toggle on={c.active} onChange={(v) => run(async () => { await api.put(`/admin/p2p-cards/${c.id}`, { ...c, active: v }); st.reload(); })} />
                <button className="iconbtn" aria-label="O'chirish" onClick={async () => { if (await confirmDialog("Kartani o'chirasizmi?")) run(async () => { await api.del(`/admin/p2p-cards/${c.id}`); st.reload(); }); }}>✕</button>
              </div>
            ))}
          </>
        )}
      </Loadable>
      <div className="card col">
        <div className="b">Karta qo'shish</div>
        <input className="input mono" inputMode="numeric" placeholder="8600 0000 0000 0000" value={num.replace(/(\d{4})(?=\d)/g, "$1 ")} onChange={(e) => setNum(e.target.value.replace(/\D/g, "").slice(0, 16))} />
        <input className="input" placeholder="ISM FAMILIYA" value={holder} onChange={(e) => setHolder(e.target.value.toUpperCase())} />
        <button className="btn full" disabled={busy || num.length !== 16} onClick={() => run(async () => {
          await api.post("/admin/p2p-cards", { number: num, holder });
          setNum(""); setHolder(""); st.reload();
        })}>Qo'shish</button>
      </div>
    </>
  );
}


interface TgInfo { api_ready: boolean; logged_in: boolean; account: string | null; connected: boolean; error: string | null; bots: string[]; seen: Record<string, { at: string; amount: number }>; login_step: "code" | "password" | null }

function TgBank() {
  const { toast } = useApp();
  const st = useLoad(() => api.get<TgInfo>("/admin/tg-bank"));
  const { busy, run } = useAction();
  const [apiId, setApiId] = useState("");
  const [apiHash, setApiHash] = useState("");
  const [phone, setPhone] = useState("+998");
  const [code, setCode] = useState("");
  const [pw, setPw] = useState("");
  const [bots, setBots] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const call = (p: Promise<TgInfo>, msg?: string) => run(async () => { await p; if (msg) toast(msg, "ok"); st.reload(); });
  return (
    <Loadable state={st}>
      {(d) => {
        const ok = d.logged_in && d.connected;
        return (
          <div className="card col" style={{ borderColor: ok ? "rgba(29,233,182,.45)" : "rgba(255,214,10,.45)" }}>
            <div className="row between">
              <span className="b">🤖 Bank botlari (Telegram)</span>
              <span className={"pill-b " + (ok ? "g" : "y")}>{ok ? "Ishlayapti" : d.logged_in ? "Ulanmoqda…" : "Ulanmagan"}</span>
            </div>
            <div className="mut xs">Server sizning Telegram akkauntingizdagi bank botlari xabarlarini o'qiydi va to'lovni o'zi biriktiradi. Telefon kerak emas.</div>
            {d.account && <div className="sm">Akkaunt: <b>{d.account}</b></div>}
            {d.error && <div className="r xs">⚠️ {d.error}</div>}
            {d.bots.map((b) => (
              <div key={b} className="row between sm"><span>@{b}</span><span className="mut xs">{d.seen[b] ? `oxirgi kirim: ${money(d.seen[b].amount)} · ${dateTime(d.seen[b].at)}` : "hali kirim yo'q"}</span></div>
            ))}
            {!d.logged_in && !d.api_ready && (
              <div className="col">
                <div className="sm"><b>1.</b> <a href="https://my.telegram.org/apps" target="_blank" rel="noreferrer">my.telegram.org</a> → kartalar ulangan Telegram raqam bilan kiring → «API development tools» → ilova yarating (nomi ixtiyoriy). <b>api_id</b> va <b>api_hash</b> ni shu yerga kiriting:</div>
                <input className="input mono" inputMode="numeric" placeholder="api_id" value={apiId} onChange={(e) => setApiId(e.target.value)} />
                <input className="input mono" placeholder="api_hash" value={apiHash} onChange={(e) => setApiHash(e.target.value)} />
                <button className="btn full" disabled={busy || !apiId || apiHash.length < 32} onClick={() => call(api.post("/admin/tg-bank/api", { api_id: apiId, api_hash: apiHash }), "Saqlandi")}>Saqlash</button>
              </div>
            )}
            {!d.logged_in && d.api_ready && d.login_step == null && (
              <div className="col">
                <div className="sm"><b>2.</b> @HUMOcardbot va @CardXabarBot ulangan Telegram raqamingiz:</div>
                <input className="input mono" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
                <button className="btn full" disabled={busy || phone.replace(/\D/g, "").length < 10} onClick={() => call(api.post("/admin/tg-bank/code", { phone }), "Kod Telegramga yuborildi")}>Kod olish</button>
              </div>
            )}
            {!d.logged_in && d.login_step === "code" && (
              <div className="col">
                <div className="sm"><b>3.</b> Telegram'ga kelgan kodni kiriting. <span className="r">Kodni hech kimga yubormang va forward qilmang.</span></div>
                <input className="input mono" inputMode="numeric" placeholder="12345" value={code} onChange={(e) => setCode(e.target.value)} />
                <button className="btn full" disabled={busy || code.length < 5} onClick={() => run(async () => { const r = await api.post<TgInfo & { need_password?: boolean }>("/admin/tg-bank/login", { code }); setCode(""); toast(r.need_password ? "Ikki bosqichli parolni kiriting" : "✅ Ulandi", "ok"); st.reload(); })}>Kirish</button>
              </div>
            )}
            {!d.logged_in && d.login_step === "password" && (
              <div className="col">
                <div className="sm">Akkauntda ikki bosqichli parol (2FA) bor — uni kiriting:</div>
                <input className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} />
                <button className="btn full" disabled={busy || !pw} onClick={() => run(async () => { await api.post("/admin/tg-bank/login", { password: pw }); setPw(""); toast("✅ Ulandi", "ok"); st.reload(); })}>Kirish</button>
              </div>
            )}
            <button className="btn small ghost" onClick={() => setOpen(!open)}>{open ? "Yopish" : "Sozlamalar"}</button>
            {open && (
              <div className="col">
                <div className="mut xs">Kuzatiladigan botlar (vergul bilan). Visa yoki boshqa bank boti bo'lsa — nomini qo'shing.</div>
                <input className="input" value={bots ?? d.bots.map((b) => "@" + b).join(", ")} onChange={(e) => setBots(e.target.value)} />
                <button className="btn small" disabled={busy || bots == null} onClick={() => call(api.put("/admin/tg-bank/bots", { bots: (bots ?? "").split(/[,\s]+/).filter(Boolean) }), "Saqlandi")}>Botlarni saqlash</button>
                {d.logged_in && <button className="btn small danger" disabled={busy} onClick={async () => { if (await confirmDialog("Akkauntni uzasizmi? Avtomatik tasdiqlash to'xtaydi.")) call(api.post("/admin/tg-bank/logout"), "Uzildi"); }}>Akkauntni uzish</button>}
              </div>
            )}
          </div>
        );
      }}
    </Loadable>
  );
}

interface SmsInfo { url: string; url_with_key: string | null; secret: string | null; header: string; ready: boolean; body_template: string; last_sms_at: string | null; last_sms_amount: number | null; last_24h: Record<string, number> }

function SmsSetup() {
  const st = useLoad(() => api.get<SmsInfo>("/admin/p2p/sms-setup"));
  const [open, setOpen] = useState(false);
  return (
    <Loadable state={st}>
      {(d) => (
        <div className="card col" style={{ borderColor: d.last_sms_at ? "rgba(29,233,182,.45)" : "rgba(255,214,10,.45)" }}>
          <div className="row between">
            <span className="b">📲 Avtomatik tasdiqlash (SMS)</span>
            <span className={"pill-b " + (d.last_sms_at ? "g" : "y")}>{d.last_sms_at ? "Ulangan" : "Ulanmagan"}</span>
          </div>
          <div className="mut xs">
            {d.last_sms_at ? `Oxirgi SMS: ${dateTime(d.last_sms_at)} · ${money(d.last_sms_amount ?? 0)} so'm` : "Hali bironta bank SMS'i kelmagan."}
            {" "}· 24 soatda: SMS {d.last_24h.sms ?? 0}, bot {d.last_24h.bot_forward ?? 0}, qo'lda {d.last_24h.admin ?? 0}
          </div>
          <button className="btn small ghost" onClick={() => setOpen(!open)}>{open ? "Yopish" : "Qanday ulash"}</button>
          {open && (
            <div className="col sm">
              {!d.ready && <div className="r b">Serverda P2P_SECRET sozlanmagan — Render → Environment.</div>}
              <div><b>1.</b> Karta SIM-kartasi turgan Android telefonga <b>«SMS Forwarder»</b> ilovasini o'rnating (Google Play: «SMS to URL Forwarder» yoki shunga o'xshash webhook ilova).</div>
              <div><b>2.</b> Yangi qoida: yuboruvchi — bankingiz (masalan HUMO, UZCARD, 900…), usul — <b>POST</b>, manzil:</div>
              {d.url_with_key && <Copy value={d.url_with_key} />}
              <div className="mut xs">Ilova sarlavha (header) qo'sha olsa, kalitni manzilga emas, sarlavhaga qo'ying: {d.header}</div>
              {d.secret && <Copy label={d.header} value={d.secret} />}
              <div><b>3.</b> Tana (JSON) shablon:</div>
              <Copy value={d.body_template} />
              <div><b>4.</b> Telefon internetga ulangan va ilova fonda ishlashiga ruxsat berilgan bo'lsin (batareya tejash o'chirilgan).</div>
              <div><b>5.</b> Sinov: kartaga kichik summa tushiring — bu yerda «Oxirgi SMS» paydo bo'ladi.</div>
              <div className="mut xs">SMS ulanmaguncha: bank xabarini (SMS yoki bank botidagi xabar) shu botga forward qilsangiz ham to'lov avtomatik topiladi. Kalitni hech kimga bermang.</div>
            </div>
          )}
        </div>
      )}
    </Loadable>
  );
}

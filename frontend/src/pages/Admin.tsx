import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Boost, type Deal, type DonateOrder, type ListingFull, type Me, type Pkg, type TgOrder, type Topup, type Withdrawal } from "../api";
import { t } from "../i18n";
import { confirmDialog } from "../tg";
import { Chips, Copy, dateTime, Empty, Field, Header, Loadable, money, MoneyInput, Seg, Sheet, som, Status, Toggle, useAction, useApp, useLoad } from "../ui";

type Tab = "stats" | "moderation" | "incoming" | "withdraw" | "disputes" | "donate" | "tg" | "boost" | "users" | "packages" | "tournaments";

export default function Admin() {
  const { me } = useApp();
  const [tab, setTab] = useState<Tab>("stats");
  if (!me?.is_admin) return <><Header title="Admin" /><Empty icon="🔒" text={t("Ruxsat yo'q")} /></>;
  return (
    <>
      <Header title={t("Admin panel")} right={<span />} />
      <div className="page">
        <Chips value={tab} onChange={setTab} options={[
          { v: "stats", label: "📊 Statistika" }, { v: "incoming", label: "💳 Kirimlar" }, { v: "withdraw", label: "💸 Yechish" },
          { v: "moderation", label: "📝 E'lonlar" }, { v: "disputes", label: "⚖️ Nizolar" }, { v: "donate", label: "💎 Donat" },
          { v: "tg", label: "⭐️ TG" }, { v: "boost", label: "🚀 Boost" }, { v: "users", label: "👥 Foydalanuvchilar" },
          { v: "packages", label: "📦 Paketlar" }, { v: "tournaments", label: "🏆 Turnirlar" },
        ]} />
        {tab === "stats" && <Stats go={setTab} />}
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
      </div>
    </>
  );
}

function Stats({ go }: { go: (t: Tab) => void }) {
  const st = useLoad(() => api.get<Record<string, number>>("/admin/stats"));
  return (
    <Loadable state={st}>
      {(s) => (
        <>
          <div className="grid2">
            <StatCard label="Foydalanuvchilar" value={money(s.users)} sub={`+${s.users_today} bugun`} />
            <StatCard label="Jami balanslar" value={money(s.balances_total)} sub="so'm (majburiyat)" />
            <StatCard label="To'ldirish (24 soat)" value={money(s.topups_today)} sub="so'm" />
            <StatCard label="Donat (24 soat)" value={money(s.donate_today)} sub="so'm" />
          </div>
          <div className="sec-title">Bajarilishi kerak</div>
          {([
            ["unmatched", "Biriktirilmagan kirimlar", "incoming"], ["withdrawals", "Pul yechish so'rovlari", "withdraw"],
            ["moderation", "Moderatsiyadagi e'lonlar", "moderation"], ["disputes", "Ochiq nizolar", "disputes"],
            ["donate_review", "Tekshiruvdagi donatlar", "donate"], ["tg_pending", "TG buyurtmalar", "tg"], ["boost_open", "Boost (qidiruv/nizo)", "boost"],
          ] as [string, string, Tab][]).map(([k, label, tabName]) => (
            <div key={k} className="card tight click row between" onClick={() => go(tabName)}>
              <span>{label}</span><span className={"badge " + (s[k] ? "y" : "m")}>{s[k]}</span>
            </div>
          ))}
        </>
      )}
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
            <div className="mut xs mono">user {o.user_id} · ID {o.player_id} ({o.zone_id}) · {som(o.price)} · urinish {o.attempts}</div>
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
            <div className="mut xs pre">{Object.entries(o.details).filter(([, v]) => v !== "" && v !== false).map(([k, v]) => `${k}: ${v}`).join("\n")}</div>
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
      <Chips value={status} onChange={setStatus} options={["searching", "accepted", "in_progress", "finished", "disputed", "done", "refunded"].map((v) => ({ v, label: v }))} />
      <Loadable state={st}>
        {(list) => list.length === 0 ? <Empty text="Bo'sh" /> : list.map((o) => (
          <div key={o.id} className="card col">
            <div className="row between"><span className="b">{o.ref} · {o.current_rank} → {o.target_rank}</span><span className="y mono">{som(o.price)}</span></div>
            <div className="mut xs pre">user {o.user_id} · {o.login_method} · booster: {o.booster_name ?? "—"}{o.note ? "\n" + o.note : ""}</div>
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
      <form className="row" onSubmit={(e) => { e.preventDefault(); setQuery(q); }}><input className="input grow" placeholder="ID, @username yoki ism" value={q} onChange={(e) => setQ(e.target.value)} /><button className="btn">Qidirish</button></form>
      <Loadable state={st}>
        {(list) => list.map((u) => (
          <div key={u.id} className="card col">
            <div className="row between"><span className="b">{u.name} {u.username ? `@${u.username}` : ""}</span>{u.is_banned && <span className="badge r">BLOK</span>}</div>
            <div className="mut xs mono">ID {u.id} · {som(u.balance)} · {dateTime(u.created_at)}</div>
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
  const st = useLoad(() => Promise.all(["open", "running", "finished"].map((s) => api.get<(TourForm & { id: number; players_count: number })[]>(`/tournaments?status=${s}`))).then((r) => r.flat()));
  const [f, setF] = useState<TourForm | null>(null);
  const [entries, setEntries] = useState<{ user_id: number; nick: string; game_id: string; server: string; tg_username: string }[] | null>(null);
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
              <button className="btn small ghost grow" onClick={() => run(async () => setEntries(await api.get(`/admin/tournaments/${x.id}/entries`)))}>Ishtirokchilar</button>
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
            <Field label="Holati"><Seg value={f.status} onChange={(s) => setF({ ...f, status: s })} options={[{ v: "open", label: "Ochiq" }, { v: "running", label: "Davom" }, { v: "finished", label: "Tugagan" }]} /></Field>
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
        {entries?.map((e, i) => <div key={e.user_id} className="listrow sm"><span className="mono">{i + 1}.</span><span className="grow"><b>{e.nick}</b> · {e.game_id} ({e.server})<br /><span className="mut xs">{e.tg_username} · user {e.user_id}</span></span></div>)}
      </Sheet>
    </>
  );
}

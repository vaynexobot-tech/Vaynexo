/* Admin: premium bo'limlar boshqaruvi va identifikatsiya (KYC). Har bo'lim — ro'yxat + aniq amallar. */
import { useState } from "react";
import { api } from "../api";
import { confirmDialog } from "../tg";
import { dateTime, Empty, Field, Loadable, money, Seg, Sheet, useAction, useApp, useLoad } from "../ui";

type Tab = "shops" | "plus" | "savings" | "streamers" | "pro" | "splits" | "duels";
const TABS: { v: Tab; label: string }[] = [
  { v: "shops", label: "🏪 Do'konlar" }, { v: "plus", label: "💎 Plus" }, { v: "savings", label: "🏦 Jamg'arma" }, { v: "streamers", label: "🎥 Striminer" },
  { v: "pro", label: "🎮 Pro" }, { v: "splits", label: "🤝 Birga" }, { v: "duels", label: "⚔️ Draft" },
];

interface Summary {
  shops: number; shop_sales: number; shop_commission: number; plus_active: number; savings_active: number; savings_locked: number; streamers: number;
  stream_money: number; pro_pending: number; pro_open: number; pro_disputes: number; splits_open: number; splits_locked: number; duels: number; kyc_pending: number;
}

function Stat({ label, value, warn }: { label: string; value: string | number; warn?: boolean }) {
  return (
    <div className="card tight col" style={{ gap: 2, borderColor: warn ? "rgba(255,214,10,.5)" : undefined }}>
      <div className="bb mono" style={{ fontSize: 18 }}>{value}</div><div className="mut xs">{label}</div>
    </div>
  );
}

function Pill({ s }: { s: string }) {
  const map: Record<string, [string, string]> = {
    active: ["Faol", "g"], open: ["Ochiq", "g"], done: ["Yakunlandi", "y"], cancelled: ["Bekor", "m"], expired: ["Muddati o'tgan", "m"],
    sold: ["Sotildi", "y"], disputed: ["Nizo", "r"], waiting: ["Kutilmoqda", "b"], picking: ["Tanlov", "b"], off: ["O'chiq", "r"],
  };
  const [l, c] = map[s] ?? [s, "m"];
  return <span className={"pill-b " + c}>{l}</span>;
}

export function PremiumAdmin() {
  const sum = useLoad(() => api.get<Summary>("/admin/premium/summary"));
  const [tab, setTab] = useState<Tab>("shops");
  return (
    <>
      <div className="mut xs">Barcha foiz, narx va muddatlar: Ko'proq → Sozlamalar (guruhlar: Do'konlar, VAYNEXO Plus, Skin jamg'armasi, Striminerlar, Pro bilan o'yna, Birgalikda to'lov, Draft Jang, VAY ball).</div>
      {sum.data && (
        <div className="grid3">
          <Stat label="Do'konlar savdosi" value={money(sum.data.shop_sales)} />
          <Stat label="Plus a'zolar" value={sum.data.plus_active} />
          <Stat label="Jamg'armada (so'm)" value={money(sum.data.savings_locked)} />
          <Stat label="Pro arizalar" value={sum.data.pro_pending} warn={sum.data.pro_pending > 0} />
          <Stat label="Pro nizolar" value={sum.data.pro_disputes} warn={sum.data.pro_disputes > 0} />
          <Stat label="KYC kutmoqda" value={sum.data.kyc_pending} warn={sum.data.kyc_pending > 0} />
        </div>
      )}
      <div className="tabs5">{TABS.map((x) => <button key={x.v} className={tab === x.v ? "on" : ""} onClick={() => setTab(x.v)}>{x.label}</button>)}</div>
      {tab === "shops" && <ShopsTab />}
      {tab === "plus" && <PlusTab />}
      {tab === "savings" && <SavingsTab />}
      {tab === "streamers" && <StreamersTab />}
      {tab === "pro" && <ProTab />}
      {tab === "splits" && <SplitsTab />}
      {tab === "duels" && <DuelsTab />}
    </>
  );
}

// ---------------------------------------------------------------- do'konlar
interface ShopRow { id: number; name: string; slug: string; tagline: string; active: boolean; owner_id: number; owner: string | null; sales: number; commission: number; orders: number; customers: number }

function ShopsTab() {
  const [q, setQ] = useState("");
  const st = useLoad(() => api.get<ShopRow[]>(`/admin/premium/shops?q=${encodeURIComponent(q)}`), [q]);
  const [edit, setEdit] = useState<ShopRow | null>(null);
  const { busy, run } = useAction();
  const { toast } = useApp();
  const save = (body: object) => run(async () => { await api.put(`/admin/premium/shops/${edit!.id}`, body); toast("Saqlandi", "ok"); setEdit(null); st.reload(); });
  return (
    <>
      <input className="input" placeholder="Nom yoki havola bo'yicha qidirish" value={q} onChange={(e) => setQ(e.target.value)} />
      <Loadable state={st}>
        {(rows) => rows.length === 0 ? <Empty text="Do'kon yo'q" /> : rows.map((s) => (
          <button key={s.id} className="card col click" style={{ gap: 4, textAlign: "left", opacity: s.active ? 1 : 0.6 }} onClick={() => setEdit(s)}>
            <div className="row between"><span className="b">{s.name} <span className="mut xs">/{s.slug}</span></span><Pill s={s.active ? "active" : "off"} /></div>
            <div className="mut xs">Egasi: {s.owner ?? s.owner_id} · mijoz {s.customers} · buyurtma {s.orders}</div>
            <div className="row between sm"><span>Savdo: <b className="mono">{money(s.sales)}</b></span><span>Komissiya: <b className="mono y">{money(s.commission)}</b></span></div>
          </button>
        ))}
      </Loadable>
      <Sheet open={!!edit} onClose={() => setEdit(null)}>
        {edit && <ShopEdit s={edit} busy={busy} onSave={save} />}
      </Sheet>
    </>
  );
}

function ShopEdit({ s, busy, onSave }: { s: ShopRow; busy: boolean; onSave: (b: object) => void }) {
  const [name, setName] = useState(s.name);
  const [tag, setTag] = useState(s.tagline);
  return (
    <>
      <div className="sec-title">{s.name}</div>
      <Field label="Nomi"><input className="input" maxLength={48} value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Tavsif"><input className="input" maxLength={120} value={tag} onChange={(e) => setTag(e.target.value)} /></Field>
      <button className="btn full" disabled={busy || name.trim().length < 2} onClick={() => onSave({ name, tagline: tag })}>Saqlash</button>
      <button className={"btn full " + (s.active ? "danger" : "green")} disabled={busy} onClick={() => onSave({ active: !s.active })}>
        {s.active ? "⛔️ Do'konni to'xtatish" : "✅ Qayta yoqish"}
      </button>
      <div className="mut xs">To'xtatilgan do'kon orqali yangi mijoz biriktirilmaydi va komissiya yozilmaydi. Egaga xabar boradi.</div>
    </>
  );
}

// ---------------------------------------------------------------- Plus
interface PlusRow { user_id: number; user: string | null; until: string; active: boolean; months: number; auto_renew: boolean; cashback_total: number }

function PlusTab() {
  const [active, setActive] = useState<"1" | "0">("1");
  const st = useLoad(() => api.get<PlusRow[]>(`/admin/premium/plus?active=${active}`), [active]);
  const [uid, setUid] = useState("");
  const [days, setDays] = useState("30");
  const { busy, run } = useAction();
  const { toast } = useApp();
  return (
    <>
      <div className="card col">
        <div className="b">🎁 Plus sovg'a qilish / muddatni o'zgartirish</div>
        <div className="row">
          <input className="input mono grow" inputMode="numeric" placeholder="Foydalanuvchi ID" value={uid} onChange={(e) => setUid(e.target.value.replace(/\D/g, ""))} />
          <input className="input mono" style={{ width: 90 }} inputMode="numeric" placeholder="kun" value={days} onChange={(e) => setDays(e.target.value.replace(/[^\d-]/g, ""))} />
        </div>
        <button className="btn full" disabled={busy || !uid || !Number(days)} onClick={() => run(async () => {
          await api.post(`/admin/premium/plus/${uid}/days`, { days: Number(days) }); toast("Bajarildi", "ok"); st.reload();
        })}>Qo'llash</button>
        <div className="mut xs">Musbat son — kun qo'shadi (obuna bo'lmasa yaratadi), manfiy — ayiradi.</div>
      </div>
      <Seg value={active} onChange={setActive} options={[{ v: "1", label: "Faol" }, { v: "0", label: "Hammasi" }]} />
      <Loadable state={st}>
        {(rows) => rows.length === 0 ? <Empty text="Obunachi yo'q" /> : rows.map((r) => (
          <div key={r.user_id} className="card tight col" style={{ gap: 2 }}>
            <div className="row between"><b>{r.user ?? r.user_id}</b><Pill s={r.active ? "active" : "expired"} /></div>
            <div className="mut xs">ID {r.user_id} · {dateTime(r.until)} gacha · {r.months} oy · keshbek {money(r.cashback_total)} · avto {r.auto_renew ? "✓" : "—"}</div>
          </div>
        ))}
      </Loadable>
    </>
  );
}

// ---------------------------------------------------------------- jamg'arma
interface SavingRow { id: number; user_id: number; user: string | null; title: string; target: number; saved: number; weekly: number; status: string }

function SavingsTab() {
  const [status, setStatus] = useState<"active" | "done" | "cancelled" | "all">("active");
  const st = useLoad(() => api.get<SavingRow[]>(`/admin/premium/savings?status=${status}`), [status]);
  const { run } = useAction();
  const { toast } = useApp();
  return (
    <>
      <Seg value={status} onChange={setStatus} options={[{ v: "active", label: "Faol" }, { v: "done", label: "Olingan" }, { v: "cancelled", label: "Bekor" }, { v: "all", label: "Hammasi" }]} />
      <Loadable state={st}>
        {(rows) => rows.length === 0 ? <Empty text="Ro'yxat bo'sh" /> : rows.map((r) => (
          <div key={r.id} className="card tight col" style={{ gap: 4 }}>
            <div className="row between"><b>{r.title}</b><Pill s={r.status} /></div>
            <div className="mut xs">{r.user ?? r.user_id} · {money(r.saved)} / {money(r.target)}{r.weekly ? ` · haftasiga ${money(r.weekly)}` : ""}</div>
            {r.status === "active" && (
              <button className="btn small ghost" onClick={async () => {
                if (await confirmDialog(`«${r.title}» yopilsinmi? ${money(r.saved)} so'm egasiga qaytadi.`)) run(async () => { await api.post(`/admin/premium/savings/${r.id}/cancel`); toast("Yopildi, pul qaytarildi", "ok"); st.reload(); });
              }}>Yopish va pulni qaytarish</button>
            )}
          </div>
        ))}
      </Loadable>
    </>
  );
}

// ---------------------------------------------------------------- striminerlar
interface StreamerRow { id: number; user_id: number; user: string | null; name: string; slug: string; active: boolean; count: number; packs: number; money: number }
interface DonRow { id: number; name: string; kind: string; title: string; amount: number; message: string; hidden: boolean; at: string | null }

function StreamersTab() {
  const st = useLoad(() => api.get<StreamerRow[]>("/admin/premium/streamers"));
  const [cur, setCur] = useState<StreamerRow | null>(null);
  const dons = useLoad(() => (cur ? api.get<DonRow[]>(`/admin/premium/streamers/${cur.id}/donations`) : Promise.resolve([] as DonRow[])), [cur?.id]);
  const { busy, run } = useAction();
  const { toast } = useApp();
  return (
    <>
      <Loadable state={st}>
        {(rows) => rows.length === 0 ? <Empty text="Striminer yo'q" /> : rows.map((r) => (
          <button key={r.id} className="card tight col click" style={{ gap: 2, textAlign: "left", opacity: r.active ? 1 : 0.6 }} onClick={() => setCur(r)}>
            <div className="row between"><b>{r.name} <span className="mut xs">/{r.slug}</span></b><Pill s={r.active ? "active" : "off"} /></div>
            <div className="mut xs">{r.user ?? r.user_id} · {r.count} donat · almaz {money(r.packs)} · pul {money(r.money)}</div>
          </button>
        ))}
      </Loadable>
      <Sheet open={!!cur} onClose={() => setCur(null)}>
        {cur && (
          <>
            <div className="sec-title">{cur.name}</div>
            <button className={"btn full " + (cur.active ? "danger" : "green")} disabled={busy} onClick={() => run(async () => {
              await api.put(`/admin/premium/streamers/${cur.id}`, { active: !cur.active }); toast("Saqlandi", "ok"); setCur(null); st.reload();
            })}>{cur.active ? "⛔️ To'xtatish" : "✅ Yoqish"}</button>
            <div className="sec-title">So'nggi donatlar</div>
            {(dons.data ?? []).map((d) => (
              <div key={d.id} className="card tight col" style={{ gap: 2, opacity: d.hidden ? 0.5 : 1 }}>
                <div className="row between"><b>{d.name}</b><span className="y xs">{d.kind === "money" ? "💸" : "💎"} {d.title}</span></div>
                {d.message && <div className="sm">{d.message}</div>}
                {!d.hidden && <button className="btn small ghost" onClick={() => run(async () => { await api.post(`/admin/premium/stream-donations/${d.id}/hide`); dons.reload(); })}>Yashirish (nomaqbul)</button>}
              </div>
            ))}
          </>
        )}
      </Sheet>
    </>
  );
}

// ---------------------------------------------------------------- Pro
interface SlotRow { id: number; title: string; pro: string | null; winner: string | null; price: number; bids: number; status: string; ends_at: string; play_at: string; dispute: string }

function ProTab() {
  const [status, setStatus] = useState<"active" | "done" | "all">("active");
  const st = useLoad(() => api.get<SlotRow[]>(`/admin/premium/pro/slots?status=${status}`), [status]);
  const { run } = useAction();
  const { toast } = useApp();
  return (
    <>
      <div className="mut xs">Arizalarni tasdiqlash va nizolarni hal qilish: Ko'proq → Premium → «Pro auksion».</div>
      <Seg value={status} onChange={setStatus} options={[{ v: "active", label: "Faol" }, { v: "done", label: "Yakunlangan" }, { v: "all", label: "Hammasi" }]} />
      <Loadable state={st}>
        {(rows) => rows.length === 0 ? <Empty text="Auksion yo'q" /> : rows.map((r) => (
          <div key={r.id} className="card tight col" style={{ gap: 4 }}>
            <div className="row between"><b className="ell">#{r.id} {r.title}</b><Pill s={r.status} /></div>
            <div className="mut xs">Pro: {r.pro} · {r.bids} stavka · {money(r.price)} · o'yin {dateTime(r.play_at)}{r.winner ? ` · g'olib ${r.winner}` : ""}</div>
            {r.dispute && <div className="r xs">Nizo: {r.dispute}</div>}
            {["open", "sold", "disputed"].includes(r.status) && (
              <button className="btn small ghost" onClick={async () => {
                if (await confirmDialog(`#${r.id} bekor qilinsinmi? Stavka egasiga pul qaytadi.`)) run(async () => { await api.post(`/admin/premium/pro/slots/${r.id}/cancel`); toast("Bekor qilindi", "ok"); st.reload(); });
              }}>Bekor qilish (pulni qaytarish)</button>
            )}
          </div>
        ))}
      </Loadable>
    </>
  );
}

// ---------------------------------------------------------------- Birgalikda to'lov
interface SplitRow { id: number; code: string; mode: string; title: string; creator: string | null; target: number; collected: number; parts: number; status: string; expires_at: string }

function SplitsTab() {
  const [status, setStatus] = useState<"open" | "done" | "expired" | "all">("open");
  const st = useLoad(() => api.get<SplitRow[]>(`/admin/premium/splits?status=${status}`), [status]);
  const { run } = useAction();
  const { toast } = useApp();
  return (
    <>
      <Seg value={status} onChange={setStatus} options={[{ v: "open", label: "Ochiq" }, { v: "done", label: "Yig'ilgan" }, { v: "expired", label: "Muddati o'tgan" }, { v: "all", label: "Hammasi" }]} />
      <Loadable state={st}>
        {(rows) => rows.length === 0 ? <Empty text="Ro'yxat bo'sh" /> : rows.map((r) => (
          <div key={r.id} className="card tight col" style={{ gap: 4 }}>
            <div className="row between"><b>{r.mode === "wish" ? "🎁" : "🤝"} {r.title}</b><Pill s={r.status} /></div>
            <div className="mut xs">{r.creator} · {money(r.collected)} / {money(r.target)} · {r.parts} kishi · {dateTime(r.expires_at)} gacha</div>
            {r.status === "open" && (
              <button className="btn small ghost" onClick={async () => {
                if (await confirmDialog("Yopilsinmi? Barcha ulushlar egalariga qaytadi.")) run(async () => { await api.post(`/admin/premium/splits/${r.code}/cancel`); toast("Yopildi", "ok"); st.reload(); });
              }}>Yopish va ulushlarni qaytarish</button>
            )}
          </div>
        ))}
      </Loadable>
    </>
  );
}

// ---------------------------------------------------------------- Draft Jang
interface DuelRow { id: number; code: string; a: string | null; b: string | null; status: string; a_score: number; b_score: number; winner: string | null; at: string | null }

function DuelsTab() {
  const st = useLoad(() => api.get<DuelRow[]>("/admin/premium/duels"));
  const [uid, setUid] = useState("");
  const [elo, setElo] = useState("1000");
  const { busy, run } = useAction();
  const { toast } = useApp();
  return (
    <>
      <div className="card col">
        <div className="b">Draft ELO ni tuzatish</div>
        <div className="row">
          <input className="input mono grow" inputMode="numeric" placeholder="Foydalanuvchi ID" value={uid} onChange={(e) => setUid(e.target.value.replace(/\D/g, ""))} />
          <input className="input mono" style={{ width: 100 }} inputMode="numeric" value={elo} onChange={(e) => setElo(e.target.value.replace(/\D/g, ""))} />
        </div>
        <button className="btn full" disabled={busy || !uid || !elo} onClick={() => run(async () => { await api.put(`/admin/premium/elo/${uid}`, { elo: Number(elo) }); toast("Saqlandi", "ok"); })}>Saqlash</button>
      </div>
      <Loadable state={st}>
        {(rows) => rows.length === 0 ? <Empty text="Jang yo'q" /> : rows.map((r) => (
          <div key={r.id} className="card tight row between">
            <span className="sm">{r.a ?? "—"} <b className="mono">{r.a_score}:{r.b_score}</b> {r.b ?? "—"}</span><Pill s={r.status} />
          </div>
        ))}
      </Loadable>
    </>
  );
}

// ================================================================ KYC
interface KycRow { id: number; name: string; username: string | null; status: string; note: string | null; at: string | null }

export function KycAdminFull() {
  const [status, setStatus] = useState<"pending" | "verified" | "rejected">("pending");
  const [q, setQ] = useState("");
  const st = useLoad(() => api.get<{ totals: Record<string, number>; items: KycRow[] }>(`/admin/premium/kyc?status=${status}&q=${encodeURIComponent(q)}`), [status, q]);
  const [cur, setCur] = useState<KycRow | null>(null);
  const [note, setNote] = useState("");
  const { busy, run } = useAction();
  const { toast } = useApp();
  const act = (action: "approve" | "reject" | "reset") => run(async () => {
    await api.post(`/admin/premium/kyc/${cur!.id}`, { action, note });
    toast(action === "approve" ? "Tasdiqlandi" : action === "reject" ? "Rad etildi" : "Bekor qilindi", "ok");
    setCur(null); setNote(""); st.reload();
  });
  const T = st.data?.totals;
  return (
    <>
      <div className="mut xs">Hujjat rasmlari serverda saqlanmaydi: ular yuborilganda admin guruhiga (yoki sizga) botda keladi. Qarorni shu yerda yoki botdagi tugmalar bilan bering.</div>
      <Seg value={status} onChange={setStatus} options={[
        { v: "pending", label: `Kutmoqda${T ? ` · ${T.pending}` : ""}` }, { v: "verified", label: `Tasdiqlangan${T ? ` · ${T.verified}` : ""}` }, { v: "rejected", label: `Rad${T ? ` · ${T.rejected}` : ""}` }]} />
      <input className="input" placeholder="Ism, @username yoki ID" value={q} onChange={(e) => setQ(e.target.value)} />
      <Loadable state={st}>
        {(d) => d.items.length === 0 ? <Empty text="Ro'yxat bo'sh" /> : d.items.map((u) => (
          <button key={u.id} className="card tight row between click" style={{ textAlign: "left" }} onClick={() => { setCur(u); setNote(""); }}>
            <div style={{ minWidth: 0 }}><div className="b ell">{u.name} {u.username ? `@${u.username}` : ""}</div><div className="mut xs">ID {u.id}{u.at ? ` · ${dateTime(u.at)}` : ""}{u.note ? ` · ${u.note}` : ""}</div></div>
            <span className="y">›</span>
          </button>
        ))}
      </Loadable>
      <Sheet open={!!cur} onClose={() => setCur(null)}>
        {cur && (
          <>
            <div className="sec-title">{cur.name} <span className="mut xs">ID {cur.id}</span></div>
            <Field label="Izoh / sabab (rad etish va bekor qilishda foydalanuvchiga yuboriladi)">
              <textarea className="input" maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Masalan: rasm xira, pasport to'liq ko'rinmaydi" />
            </Field>
            <div className="row">
              {cur.status !== "verified" && <button className="btn green grow" disabled={busy} onClick={() => act("approve")}>✓ Tasdiqlash</button>}
              {cur.status !== "rejected" && <button className="btn danger grow" disabled={busy} onClick={() => act("reject")}>✕ Rad etish</button>}
            </div>
            {cur.status !== "pending" && <button className="btn ghost full" disabled={busy} onClick={() => act("reset")}>Bekor qilish (qayta topshirsin)</button>}
          </>
        )}
      </Sheet>
    </>
  );
}

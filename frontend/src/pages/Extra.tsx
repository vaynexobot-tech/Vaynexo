import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Pkg } from "../api";
import { t } from "../i18n";
import { HeroAva, HeroPicker, HERO_BY_ID, roleLabel } from "../mlbb";
import { confirmDialog, openTg } from "../tg";
import { BottomNav, Copy, dateTime, Empty, Header, Loadable, money, MoneyInput, Seg, Sheet, som, useAction, useApp, useLoad } from "../ui";
import { IdFields, PkgPicker } from "./Premium";

function leftText(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return t("tugadi");
  const m = Math.floor(ms / 60000), h = Math.floor(m / 60);
  return h > 0 ? t("{h} soat {m} daq", { h, m: m % 60 }) : t("{m} daq", { m });
}

// ================================================================ Birgalikda to'laymiz / Orzu ro'yxati
interface SplitView {
  code: string; mode: "split" | "wish"; title: string; message: string; status: string; target: number; collected: number; remaining: number;
  expires_at: string; order_id: number | null; creator: { id: number; name: string }; mine: number; is_creator: boolean;
  parts: { name: string; amount: number }[]; game_id: string | null; link: string | null; min: number;
}
interface SplitRow { code: string; mode: string; title: string; status: string; target: number; collected: number; expires_at: string }

const SPLIT_STATUS: Record<string, [string, string]> = { open: ["Yig'ilmoqda", "g"], done: ["Yakunlandi", "y"], expired: ["Muddati o'tdi", "m"], cancelled: ["Bekor", "m"] };

function Bar({ pct }: { pct: number }) { return <div className="progress big"><i style={{ width: Math.min(100, pct) + "%" }} /></div>; }

function SplitRowCard({ x, onClick }: { x: SplitRow; onClick: () => void }) {
  const st = SPLIT_STATUS[x.status] ?? [x.status, "m"];
  return (
    <button className="card col click" style={{ gap: 6, textAlign: "left" }} onClick={onClick}>
      <div className="row between"><span className="b">{x.mode === "wish" ? "🎁" : "🤝"} {x.title}</span><span className={"pill-b " + st[1]}>{t(st[0])}</span></div>
      <Bar pct={Math.round((x.collected * 100) / Math.max(1, x.target))} />
      <div className="row between mut xs"><span className="mono">{money(x.collected)} / {money(x.target)}</span>{x.status === "open" && <span>⏱ {leftText(x.expires_at)}</span>}</div>
    </button>
  );
}

export function TogetherPage() {
  const st = useLoad(() => api.get<{ enabled: boolean; made: SplitRow[]; joined: SplitRow[] }>("/split/my"));
  const nav = useNavigate();
  const { me } = useApp();
  const [mode, setMode] = useState<"split" | "wish" | null>(null);
  const [pick, setPick] = useState<Pkg | null>(null);
  const [uid, setUid] = useState(me?.ml_id?.replace(/\D/g, "") ?? "");
  const [zid, setZid] = useState("");
  const [msg, setMsg] = useState("");
  const { busy, run } = useAction();
  const tiles = [
    { m: "split" as const, icon: "🤝", title: t("Birgalikda to'laymiz"), sub: t("Do'stlar bilan bo'lib to'lang") },
    { m: "wish" as const, icon: "🎁", title: t("Orzu ro'yxati"), sub: t("Do'stlar sizga sovg'a qilsin") },
  ];
  return (
    <>
      <Header title={t("Birgalikda")} sub={t("Do'stlar bilan to'lov va orzular")} icon="gift" />
      <div className="page">
        <Loadable state={st}>
          {(d) => !d.enabled ? <Empty icon="🤝" text={t("Tez kunda")} /> : (
            <>
              <div className="hero col" style={{ gap: 6, borderColor: "rgba(29,233,182,.4)" }}>
                <div className="hf bb" style={{ fontSize: 20 }}>{t("Almazni birga oling")}</div>
                <div className="sm" style={{ color: "#d6dbe8" }}>{t("Paketni tanlang, havolani do'stlaringizga yuboring — har kim o'z ulushini to'laydi. Yig'ilgach almaz tushadi, 24 soatda yig'ilmasa pul hammaga qaytadi.")}</div>
              </div>
              <div className="arena-grid">
                {tiles.map((x) => (
                  <button key={x.m} className="arena-tile" onClick={() => setMode(x.m)}>
                    <span className="arena-ico">{x.icon}</span><span className="arena-t">{x.title}</span><span className="arena-s">{x.sub}</span>
                  </button>
                ))}
              </div>
              {d.made.length > 0 && <div className="sec-title">{t("Mening yig'ishlarim")}</div>}
              {d.made.map((x) => <SplitRowCard key={x.code} x={x} onClick={() => nav(`/split/${x.code}`)} />)}
              {d.joined.length > 0 && <div className="sec-title">{t("Men qatnashganlar")}</div>}
              {d.joined.map((x) => <SplitRowCard key={x.code} x={x} onClick={() => nav(`/split/${x.code}`)} />)}
            </>
          )}
        </Loadable>
      </div>
      <Sheet open={!!mode} onClose={() => setMode(null)}>
        <div className="sec-title">{mode === "wish" ? "🎁 " + t("Orzu qo'shish") : "🤝 " + t("Birgalikda to'lash")}</div>
        <PkgPicker value={pick?.id ?? null} onChange={setPick} />
        <IdFields uid={uid} zid={zid} setUid={setUid} setZid={setZid} />
        <input className="input" maxLength={200} value={msg} placeholder={mode === "wish" ? t("Tug'ilgan kunim! 🎂") : t("Birga olamiz!")} onChange={(e) => setMsg(e.target.value)} />
        <div className="mut xs">{mode === "wish" ? t("Siz to'lamaysiz: do'stlaringiz ulush qo'shadi, almaz sizning akkauntingizga tushadi.") : t("Siz ham ulush qo'shasiz, do'stlar qolganini to'laydi. Almaz sizning akkauntingizga tushadi.")}</div>
        <button className="btn full" disabled={busy || !pick || uid.length < 5} onClick={() => run(async () => {
          const r = await api.post<SplitView>("/split", { mode, package_id: pick!.id, player_id: uid, zone_id: zid, message: msg });
          setMode(null); nav(`/split/${r.code}`);
        })}>{t("Havola yaratish")}</button>
      </Sheet>
      <BottomNav />
    </>
  );
}

export function SplitPage() {
  const code = useParams().code ?? "";
  const st = useLoad(() => api.get<SplitView>(`/split/${code}`), [code]);
  const { me, refreshMe, toast } = useApp();
  const nav = useNavigate();
  const { busy, run } = useAction();
  const [sheet, setSheet] = useState(false);
  const [amt, setAmt] = useState<number | "">("");
  const act = (fn: () => Promise<unknown>) => run(async () => { await fn(); await Promise.all([st.reload(), refreshMe()]); });
  return (
    <>
      <Header title={st.data?.mode === "wish" ? t("Orzu") : t("Birgalikda to'lov")} sub={st.data?.creator.name} icon="gift" />
      <div className="page">
        <Loadable state={st}>
          {(s) => {
            const open = s.status === "open";
            const pct = Math.round((s.collected * 100) / Math.max(1, s.target));
            const share = () => s.link && openTg(`https://t.me/share/url?url=${encodeURIComponent(s.link)}&text=${encodeURIComponent(s.mode === "wish" ? t("{n} orzusi: {t}. Ulush qo'shasizmi? 🎁", { n: s.creator.name, t: s.title }) : t("{t} ni birga olamiz! Ulush qo'shing 🤝", { t: s.title }))}`);
            return (
              <>
                <div className="hero col" style={{ gap: 8, borderColor: s.mode === "wish" ? "rgba(255,90,140,.5)" : "rgba(29,233,182,.45)" }}>
                  <div className="row between"><span className="badge g">{s.mode === "wish" ? "🎁 " + t("ORZU") : "🤝 " + t("BIRGALIKDA")}</span>
                    <span className={"pill-b " + (SPLIT_STATUS[s.status]?.[1] ?? "m")}>{t(SPLIT_STATUS[s.status]?.[0] ?? s.status)}</span></div>
                  <div className="hf bb" style={{ fontSize: 22 }}>{s.title}</div>
                  {s.message && <div className="sm" style={{ color: "#d6dbe8" }}>«{s.message}»</div>}
                  <Bar pct={pct} />
                  <div className="row between"><span className="bb mono y">{money(s.collected)} <span className="mut xs">/ {money(s.target)}</span></span><span className="mut xs">{pct}%</span></div>
                  {open && <div className="mut xs">⏱ {t("Qoldi")}: {leftText(s.expires_at)} · {t("Muddat tugasa, pul hammaga qaytadi")}</div>}
                </div>

                {s.status === "done" && <div className="card tight g sm">✅ {s.mode === "wish" ? t("Orzu amalga oshdi! Almaz yetkazildi.") : t("Yig'ildi! Almaz yetkazilmoqda.")}</div>}
                {s.status === "expired" && <div className="card tight sm">⌛️ {t("Muddatida yig'ilmadi. Ulushlar hamyonlarga qaytarilgan.")}</div>}
                {s.status === "cancelled" && <div className="card tight sm">↩️ {t("Bekor qilindi. Ulushlar qaytarilgan.")}</div>}

                {open && (
                  <div className="card col">
                    {s.mine > 0 && <div className="g sm">✓ {t("Sizning ulushingiz")}: {som(s.mine)}</div>}
                    <button className="btn full" onClick={() => { setAmt(Math.min(s.remaining, Math.max(s.min, Math.ceil(s.remaining / 2 / 1000) * 1000))); setSheet(true); }}>
                      {s.mode === "wish" && s.is_creator ? t("Ulush qo'shish") : s.mode === "wish" ? "🎁 " + t("Sovg'a qilish") : t("Ulush qo'shish")}
                    </button>
                    <button className="btn ghost full" onClick={share}>{t("Telegramda ulashish")}</button>
                    {s.link && <Copy value={s.link} />}
                  </div>
                )}

                <div className="sec-title">{t("Qatnashchilar")} · {s.parts.length}</div>
                {s.parts.length === 0 && <div className="mut sm">{t("Hali ulush yo'q — havolani yuboring!")}</div>}
                {s.parts.map((p, i) => <div key={i} className="card tight row between"><span>{p.name}</span><span className="mono y b">{money(p.amount)}</span></div>)}

                {s.is_creator && s.game_id && <div className="mut xs">{t("Almaz tushadi")}: ID {s.game_id}</div>}
                {s.is_creator && open && (
                  <button className="btn ghost full" disabled={busy} onClick={async () => {
                    if (await confirmDialog(t("Bekor qilinsinmi? Barcha ulushlar qaytariladi."))) act(async () => { await api.post(`/split/${code}/cancel`); toast(t("Bekor qilindi"), "ok"); });
                  }}>{t("Bekor qilish")}</button>
                )}
                {s.order_id && <button className="btn ghost full" onClick={() => nav(`/donate/order/${s.order_id}`)}>{t("Buyurtmani ochish")}</button>}
              </>
            );
          }}
        </Loadable>
      </div>
      <Sheet open={sheet} onClose={() => setSheet(false)}>
        {st.data && (
          <>
            <div className="sec-title">{t("Ulush qo'shish")}</div>
            <div className="mut sm">{t("Qoldi")}: {som(st.data.remaining)} · {t("Hamyon")}: {som(me?.balance ?? 0)}</div>
            <MoneyInput value={amt} onChange={setAmt} />
            <div className="row">
              {[...new Set([st.data.min, Math.ceil(st.data.remaining / 2 / 1000) * 1000, st.data.remaining])].filter((v) => v > 0 && v <= st.data!.remaining).map((v) => (
                <button key={v} className="btn small ghost grow" onClick={() => setAmt(v)}>{money(v)}</button>
              ))}
            </div>
            {(me?.balance ?? 0) < Number(amt || 0) && <div className="r xs">{t("Hamyonda mablag' yetarli emas")}</div>}
            <button className="btn full" disabled={busy || !amt || Number(amt) < Math.min(st.data.min, st.data.remaining) || (me?.balance ?? 0) < Number(amt)} onClick={() => act(async () => {
              await api.post(`/split/${code}/pay`, { amount: amt }); setSheet(false); toast(t("Rahmat! Ulush qo'shildi"), "ok");
            })}>{t("To'lash")} · {som(Number(amt || 0))}</button>
          </>
        )}
      </Sheet>
      <BottomNav />
    </>
  );
}

// ================================================================ Draft Jang
interface DHero { id: number; name: string; role: string; lane: string }
interface DuelView {
  code: string; status: string; side: "a" | "b" | null; opponent: { id: number; name: string; elo: number } | null; me: { id: number; name: string; elo: number } | null;
  expires_at: string; link: string | null; slots: { key: string; label: string }[]; my_picks: Record<string, DHero> | null; their_picks: Record<string, DHero> | null;
  opponent_ready: boolean;
  result: { a_score: number; b_score: number; winner_id: number | null; a_delta: number; b_delta: number; a: { id: number; name: string } | null; b: { id: number; name: string } | null;
    detail: { a: Record<string, number>; b: Record<string, number>; live_counters: boolean } | null } | null;
}
const PART_LABEL: Record<string, string> = { lane: "Liniyaga mosligi", front: "Oldingi qator", marksman: "Strelok", mage: "Mag", mixed: "Zarar balansi", spread: "Rollar xilma-xilligi", counter: "Counter" };

export function DuelHub() {
  const top = useLoad(() => api.get<{ items: { place: number; name: string; elo: number; id: number }[]; me: { elo: number } }>("/duel/top"));
  const nav = useNavigate();
  const { busy, run } = useAction();
  return (
    <>
      <Header title="Draft Jang" sub={t("Draft bilimi reytingi")} icon="arena" />
      <div className="page">
        <div className="hero col" style={{ gap: 8, borderColor: "rgba(155,107,255,.5)" }}>
          <div className="row between"><span className="badge v">⚔️ DRAFT ELO</span><span className="bb mono y" style={{ fontSize: 24 }}>{top.data?.me.elo ?? 1000}</span></div>
          <div className="sm" style={{ color: "#d6dbe8" }}>{t("Do'stingizni jangga chaqiring: ikkalangiz har liniyaga bittadan qahramon tanlaysiz, tizim draftlarni baholab g'olibni aytadi. G'olib ELO va ball oladi.")}</div>
          <button className="btn full" disabled={busy} onClick={() => run(async () => { const r = await api.post<DuelView>("/duel"); nav(`/duel/${r.code}`); })}>⚔️ {t("Jang boshlash")}</button>
        </div>
        <div className="sec-title">🏆 {t("Draft ELO reytingi")}</div>
        {top.data && top.data.items.length === 0 && <div className="mut sm">{t("Hali jang yo'q — birinchi bo'ling!")}</div>}
        {(top.data?.items ?? []).map((x) => (
          <div key={x.id} className="card tight row between"><span className="row"><b style={{ width: 26 }}>{x.place <= 3 ? ["🥇", "🥈", "🥉"][x.place - 1] : x.place}</b><span>{x.name}</span></span><span className="mono y b">{x.elo}</span></div>
        ))}
      </div>
      <BottomNav />
    </>
  );
}

export function DuelPage() {
  const code = useParams().code ?? "";
  const st = useLoad(() => api.get<DuelView>(`/duel/${code}`), [code]);
  const { refreshMe, toast } = useApp();
  const { busy, run } = useAction();
  const [picks, setPicks] = useState<Record<string, number>>({});
  const [slot, setSlot] = useState<string | null>(null);
  useEffect(() => { const i = setInterval(() => st.reload(), 8000); return () => clearInterval(i); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const act = (fn: () => Promise<unknown>) => run(async () => { await fn(); await Promise.all([st.reload(), refreshMe()]); });
  return (
    <>
      <Header title="Draft Jang" sub={st.data?.opponent ? `vs ${st.data.opponent.name}` : t("Raqib kutilmoqda")} icon="arena" />
      <div className="page">
        <Loadable state={st}>
          {(d) => {
            const share = () => d.link && openTg(`https://t.me/share/url?url=${encodeURIComponent(d.link)}&text=${encodeURIComponent(t("Draft Jangda kuchimni sinab ko'ring! ⚔️"))}`);
            const used = Object.values(picks);
            if (d.status === "expired" || d.status === "cancelled") return <Empty icon="⌛️" text={t("Jang muddati tugagan")} />;
            if (d.result) {
              const r = d.result, meA = d.side === "a";
              const mine = meA ? r.a_score : r.b_score, theirs = meA ? r.b_score : r.a_score, delta = meA ? r.a_delta : r.b_delta;
              const won = r.winner_id && d.me && r.winner_id === d.me.id;
              const parts = r.detail ? (meA ? r.detail.a : r.detail.b) : {};
              return (
                <>
                  <div className="hero col center" style={{ gap: 4, borderColor: won ? "rgba(29,233,182,.6)" : "rgba(255,255,255,.2)" }}>
                    <div className="hf bb" style={{ fontSize: 24 }}>{r.winner_id === null ? "🤝 " + t("Durang") : won ? "🏆 " + t("G'alaba!") : "💥 " + t("Mag'lubiyat")}</div>
                    <div className="bb mono y" style={{ fontSize: 34 }}>{mine} : {theirs}</div>
                    <div className="mut sm">Draft ELO {delta >= 0 ? "+" : ""}{delta}</div>
                  </div>
                  <div className="sec-title">{t("Sizning draftingiz")}</div>
                  <div className="row" style={{ justifyContent: "space-between" }}>{d.slots.map((s) => d.my_picks?.[s.key] && (
                    <div key={s.key} className="col center" style={{ gap: 2, alignItems: "center" }}><HeroAva id={d.my_picks[s.key].id} size={58} radius={16} /><span className="xs b">{d.my_picks[s.key].name}</span><span className="mut xs">{s.label}</span></div>))}</div>
                  <div className="sec-title">{t("Raqib drafti")}</div>
                  <div className="row" style={{ justifyContent: "space-between" }}>{d.slots.map((s) => d.their_picks?.[s.key] && (
                    <div key={s.key} className="col center" style={{ gap: 2, alignItems: "center" }}><HeroAva id={d.their_picks[s.key].id} size={58} radius={16} /><span className="xs b">{d.their_picks[s.key].name}</span><span className="mut xs">{s.label}</span></div>))}</div>
                  <div className="card col">
                    <div className="b">{t("Ball tafsiloti")}</div>
                    {Object.entries(parts).map(([k, v]) => <div key={k} className="kv"><span>{t(PART_LABEL[k] ?? k)}</span><span className="mono b">+{v}</span></div>)}
                    {r.detail && !r.detail.live_counters && <div className="mut xs">{t("Counter hisobi hozir ishlamadi — ball faqat tarkib bo'yicha.")}</div>}
                  </div>
                </>
              );
            }
            if (!d.side) {
              return (
                <div className="hero col center" style={{ gap: 10 }}>
                  <div className="hf bb" style={{ fontSize: 20 }}>⚔️ {d.opponent?.name} {t("sizni jangga chaqirdi")}</div>
                  <div className="mut sm">Draft ELO: {d.opponent?.elo}</div>
                  <button className="btn full" disabled={busy} onClick={() => act(() => api.post(`/duel/${code}/join`))}>{t("Jangga qo'shilish")}</button>
                </div>
              );
            }
            if (d.status === "waiting") {
              return (
                <div className="hero col" style={{ gap: 8 }}>
                  <div className="hf bb" style={{ fontSize: 20 }}>{t("Raqibni kutyapmiz")}</div>
                  <div className="mut sm">{t("Havolani do'stingizga yuboring. U qo'shilgach, ikkalangiz draft tanlaysiz.")}</div>
                  <button className="btn full" disabled={!d.link} onClick={share}>{t("Telegramda ulashish")}</button>
                  {d.link && <Copy value={d.link} />}
                  <div className="mut xs">⏱ {leftText(d.expires_at)}</div>
                </div>
              );
            }
            if (d.my_picks) {
              return (
                <div className="hero col center" style={{ gap: 8 }}>
                  <div className="hf bb" style={{ fontSize: 20 }}>{t("Draftingiz topshirildi")}</div>
                  <div className="row" style={{ justifyContent: "center" }}>{d.slots.map((s) => d.my_picks?.[s.key] && <HeroAva key={s.key} id={d.my_picks[s.key].id} size={52} radius={14} />)}</div>
                  <div className="mut sm">{d.opponent_ready ? t("Natija hisoblanmoqda…") : t("Raqib draftini kutyapmiz. Natija chiqqach xabar beramiz.")}</div>
                </div>
              );
            }
            return (
              <>
                <div className="card tight sm">{t("Har liniyaga bittadan qahramon tanlang. Liniyasiga mos qahramon, tank/support, strelok, mag va zarar balansi ball beradi. Raqib draftini ko'rmaydi.")}</div>
                {d.slots.map((s) => (
                  <button key={s.key} className="card row click between" style={{ textAlign: "left" }} onClick={() => setSlot(s.key)}>
                    <div className="row">{picks[s.key] ? <HeroAva id={picks[s.key]} size={48} radius={14} /> : <span style={{ width: 48, height: 48, borderRadius: 14, background: "rgba(255,255,255,.06)", display: "grid", placeItems: "center", fontSize: 22 }}>＋</span>}
                      <div><div className="b">{s.label}</div><div className="mut xs">{picks[s.key] ? `${HERO_BY_ID[picks[s.key]]?.name} · ${roleLabel(HERO_BY_ID[picks[s.key]]?.role ?? "")}` : t("Qahramon tanlang")}</div></div></div>
                  </button>
                ))}
                <button className="btn full" disabled={busy || used.length < 5} onClick={() => act(async () => { await api.post(`/duel/${code}/picks`, { picks }); toast(t("Draft topshirildi"), "ok"); })}>
                  {used.length < 5 ? `${used.length}/5` : t("Draftni topshirish")}
                </button>
                <HeroPicker open={!!slot} value={slot && picks[slot] ? [picks[slot]] : []} max={1} disabled={used.filter((x) => x !== (slot ? picks[slot] : 0))} onClose={() => setSlot(null)}
                  onChange={(v) => slot && setPicks((p) => ({ ...p, [slot]: v[0] }))} />
              </>
            );
          }}
        </Loadable>
        {st.data && <div className="mut xs center">{dateTime(st.data.expires_at)} {t("gacha")}</div>}
      </div>
      <BottomNav />
    </>
  );
}

// ================================================================ Kunlik seriya va Meta bashorat
interface HabitData { streak: number; done_today: boolean; points: number; hero: { id: number; name: string; role: string; lane: string }; next: { days: number; points: number; left: number } | null }

export function HabitCard() {
  const st = useLoad(() => api.get<HabitData>("/habit"));
  const { refreshMe, toast } = useApp();
  const { busy, run } = useAction();
  const d = st.data;
  if (!d) return null;
  return (
    <div className="card col" style={{ gap: 8, borderColor: "rgba(255,138,0,.45)", background: "linear-gradient(135deg, rgba(255,138,0,.10), var(--card))" }}>
      <div className="row between">
        <span className="b">🔥 {t("{n} kunlik seriya", { n: d.streak })}</span>
        {d.next && <span className="mut xs">{t("{d} kundan keyin +{p} ball", { d: d.next.left, p: d.next.points })}</span>}
      </div>
      <div className="row" style={{ gap: 10 }}>
        <HeroAva id={d.hero.id} size={46} radius={14} />
        <div className="grow"><div className="mut xs">{t("Bugungi qahramon")}</div><div className="b">{d.hero.name} <span className="mut xs">· {roleLabel(d.hero.role)}</span></div></div>
        <button className="btn small" disabled={busy || d.done_today} onClick={() => run(async () => {
          const r = await api.post<{ earned: number; bonus: number }>("/habit/checkin"); toast(`+${r.earned} ${t("ball")}${r.bonus ? " 🎉" : ""}`, "ok"); await Promise.all([st.reload(), refreshMe()]);
        })}>{d.done_today ? "✓" : `+${d.points}`}</button>
      </div>
      <div className="mut xs">{d.done_today ? t("Bugun belgilandi. Ertaga qaytib keling — seriya uzilmasin!") : t("Bugungi qahramon bilan o'ynang va belgilang. Har kun ketma-ket kirsangiz, bonus ball oshadi.")}</div>
    </div>
  );
}

interface MetaData {
  week: string; available: boolean; points: number; my_pick: number | null; candidates: { id: number; name: string; role: string; win: number }[];
  last: { winner: { id: number; name: string; delta: number }; my_hero: number | null; correct: boolean } | null;
}

export function MetaPage() {
  const st = useLoad(() => api.get<MetaData>("/meta"));
  const { toast, refreshMe } = useApp();
  const { busy, run } = useAction();
  const [q, setQ] = useState("");
  return (
    <>
      <Header title={t("Meta bashorat")} sub={t("Qaysi qahramon ko'tariladi?")} icon="arena" />
      <div className="page">
        <Loadable state={st}>
          {(d) => (
            <>
              <div className="hero col" style={{ gap: 6, borderColor: "rgba(155,107,255,.5)" }}>
                <div className="hf bb" style={{ fontSize: 20 }}>🔮 {t("Bu hafta kim ko'tariladi?")}</div>
                <div className="sm" style={{ color: "#d6dbe8" }}>{t("Haftasiga bitta qahramon tanlang. Hafta oxirida g'alaba foizi eng ko'p oshgan qahramonni topsangiz, +{p} ball. Pul tikilmaydi.", { p: d.points })}</div>
              </div>
              {d.last && (
                <div className="card tight sm" style={{ borderColor: d.last.correct ? "rgba(29,233,182,.5)" : undefined }}>
                  {t("O'tgan hafta eng ko'p o'sgan")}: <b>{d.last.winner.name}</b> (+{d.last.winner.delta}%) · {d.last.my_hero ? (d.last.correct ? "✅ " + t("Siz topdingiz!") : t("Sizning tanlovingiz: {n}", { n: HERO_BY_ID[d.last.my_hero]?.name ?? "" })) : t("Siz tanlamagan edingiz")}
                </div>
              )}
              {!d.available ? <Empty icon="🔮" text={t("Jonli statistika hozircha yo'q. Keyinroq urinib ko'ring.")} /> : d.my_pick ? (
                <div className="card row"><HeroAva id={d.my_pick} size={56} radius={16} /><div><div className="b">{t("Sizning tanlovingiz")}: {HERO_BY_ID[d.my_pick]?.name}</div><div className="mut xs">{t("Natija hafta oxirida")}</div></div></div>
              ) : (
                <>
                  <input className="input" placeholder={t("Qahramon qidirish...")} value={q} onChange={(e) => setQ(e.target.value)} />
                  <div className="hero-grid" style={{ maxHeight: "60vh" }}>
                    {d.candidates.filter((c) => !q || c.name.toLowerCase().includes(q.toLowerCase())).map((c) => (
                      <button key={c.id} className="hero-cell" disabled={busy} onClick={async () => {
                        if (await confirmDialog(t("{n} ni tanlaysizmi? Hafta davomida o'zgartirib bo'lmaydi.", { n: c.name }))) run(async () => { await api.post("/meta/pick", { hero_id: c.id }); toast(t("Tanlov qabul qilindi"), "ok"); await Promise.all([st.reload(), refreshMe()]); });
                      }}><HeroAva id={c.id} size={56} radius={14} /><span className="ell">{c.name}</span></button>
                    ))}
                  </div>
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

export { Seg };

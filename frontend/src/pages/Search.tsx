// Arena → Qidiruv: 5v5 bahs, 1v1 duel, rankedga sherik, jamoa (o'yinchi kerak / jamoa kerak / jamoalar).
import { useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import { HeroAva, HeroSlots, LANES, LanePicker, laneKey, laneLabel, MlIcon, rankKey, rankLabel } from "../mlbb";
import { Empty, Field, Icon, Loadable, Seg, Sheet, Toggle, useAction, useApp, useLoad } from "../ui";

interface Meta { regions: string[]; signal: boolean; my_rank: string; my_region: string; team_max: number }
interface Card { user_id: number; nick: string; rank: string; lane: string; heroes: number[]; region: string; verified: boolean }
interface Respect { good: number; bad: number; pct: number | null; toxic: boolean }
interface TeamS { id: number; name: string; tag: string; region: string; about: string; is_open: boolean; captain: string; captain_id: number; members: number; max: number; free: number; avg_rank: string }
interface TeamFull extends TeamS { roster: (Card & { role: string; respect: Respect | null })[]; is_member?: boolean; is_captain?: boolean; my_request?: string | null }
interface Post { id: number; kind: Kind; name: string; lane: string; rank: string; online: string; note: string; heroes: number[]; region: string; mine: boolean; author: Card | null; respect: Respect | null; team?: TeamS }
interface MyTeam { team: TeamFull | null; requests: (Card & { id: number; respect: Respect | null })[]; invites: { id: number; team: TeamS }[] }
type Kind = "player" | "team" | "duo" | "duel" | "scrim";

const editCard = () => window.dispatchEvent(new Event("vx:edit-mlcard"));

const INTRO: Record<Kind, { icon: string; title: string; text: string; empty: string; act: string }> = {
  scrim: { icon: "arena", title: "5v5 jamoaviy bahs", text: "Jamoangiz bilan boshqa jamoaga bahs e'lon qiling. Sardor qabul qiladi.", empty: "Hozircha 5v5 bahs e'lonlari yo'q", act: "Bahsni qabul qilish" },
  duel: { icon: "bolt", title: "1v1 duel", text: "Mahoratingizni sinang: qahramon va vaqtni yozing, raqib qabul qiladi.", empty: "Hozircha duel chaqiruvlari yo'q", act: "Qabul qilish" },
  duo: { icon: "user", title: "Rankedga sherik", text: "Rankingizga mos sherik bilan birga rank ko'taring.", empty: "Rankingizga mos sherik e'loni yo'q", act: "Birga o'ynash" },
  team: { icon: "grid", title: "Jamoalar o'yinchi qidirmoqda", text: "Jamoalar bo'sh rollarga o'yinchi qidirmoqda. E'lonni jamoa sardori beradi.", empty: "Rankingizga mos e'lon yo'q", act: "So'rov yuborish" },
  player: { icon: "user", title: "Jamoa qidirayotgan o'yinchilar", text: "Jamoasiz o'yinchilar. Jamoangizga o'yinchi kerak bo'lsa, sardor sifatida taklif yuboring.", empty: "Rankingizga mos e'lon yo'q", act: "Taklif yuborish" },
};

export function Search() {
  const meta = useLoad(() => api.get<Meta>("/arena/search/meta"));
  const [tab, setTab] = useState<"scrim" | "duel" | "duo" | "team">(() => (sessionStorage.getItem("vx_search_tab") as never) || "duo");
  const pick = (v: typeof tab) => { setTab(v); try { sessionStorage.setItem("vx_search_tab", v); } catch { /* yo'q */ } };
  return (
    <>
      <div className="mut xs">{t("5v5 jamoaviy bahs, 1v1 duel, rankedga sherik va jamoa — rankingizga mos o'yinchilar bilan")}</div>
      <div className="tabs5">
        {([["scrim", "5v5"], ["duel", "1v1 Duel"], ["duo", "Sherik"], ["team", "Jamoa"]] as const).map(([v, l]) => (
          <button key={v} className={tab === v ? "on" : ""} onClick={() => pick(v)}>{t(l)}</button>
        ))}
      </div>
      <Loadable state={meta}>
        {(m) => (
          <>
            {tab === "scrim" && <><MyTeamCard meta={m} compact /><Posts kind="scrim" meta={m} /></>}
            {tab === "duel" && <Posts kind="duel" meta={m} />}
            {tab === "duo" && (
              <>
                <Posts kind="duo" meta={m} extra={<><SignalCard meta={m} onChange={meta.reload} /><RespectCard /></>} />
              </>
            )}
            {tab === "team" && <TeamTab meta={m} />}
          </>
        )}
      </Loadable>
    </>
  );
}

// ---------------------------------------------------------------- umumiy: e'lonlar ro'yxati
function Posts({ kind, meta, extra }: { kind: Kind; meta: Meta; extra?: React.ReactNode }) {
  const { toast } = useApp();
  const [lane, setLane] = useState("");
  const [region, setRegion] = useState("");
  const [match, setMatch] = useState(!!meta.my_rank);
  const apiLane = LANES.find((l) => l.v === lane)?.label ?? "";
  const st = useLoad(() => api.get<Post[]>(`/arena/posts?kind=${kind}&lane=${apiLane}&region=${encodeURIComponent(region)}&match=${match ? 1 : 0}`), [kind, apiLane, region, match]);
  const [open, setOpen] = useState(false);
  const { busy, run } = useAction();
  const it = INTRO[kind];
  return (
    <>
      <div className="card col" style={{ borderColor: "rgba(255,214,10,.3)" }}>
        <div className="row">
          <span className="rowico y" style={{ width: 44, height: 44 }}><Icon name={it.icon} /></span>
          <div className="grow">
            <div className="b">{t(it.title)}</div>
            <div className="mut xs">
              {st.data ? (st.data.length ? t("Hozir {n} ta faol e'lon", { n: st.data.length }) : t("Hozircha faol e'lon yo'q")) : "…"}
              {!meta.my_rank && <> · <button className="linkbtn y xs b" onClick={editCard}>{t("Rankingizni kiriting")}</button></>}
            </div>
          </div>
          <button className="btn small" onClick={() => setOpen(true)}>{t("E'lon berish")}</button>
        </div>
        <div className="mut xs" style={{ border: "1px dashed var(--line)", borderRadius: 12, padding: "8px 10px" }}>{t(it.text)}</div>
      </div>
      {extra}
      <div className="card col" style={{ gap: 8 }}>
        <div className="row" style={{ gap: 6 }}>
          <div className="lane-mini">
            {LANES.map((l) => (
              <button key={l.v} className={lane === l.v ? "on" : ""} onClick={() => setLane(lane === l.v ? "" : l.v)} title={l.label}><MlIcon kind="lane" k={l.v} size={22} /></button>
            ))}
          </div>
          <RegionSelect value={region} onChange={setRegion} regions={meta.regions} />
        </div>
        <div className="row between">
          <button className={"chip row" + (match ? " on" : "")} style={{ gap: 4 }} disabled={!meta.my_rank} onClick={() => setMatch(!match)}><Icon name="check" size={14} />{t("Menga mos rank")}</button>
          <span className="mut xs">{t("{n} ta topildi", { n: st.data?.length ?? 0 })}</span>
        </div>
      </div>
      <Loadable state={st}>
        {(list) => list.length === 0 ? (
          <Empty icon="🤝" text={t(it.empty)}>
            {match && <div className="mut xs center">{t("Barcha e'lonlarni ko'rish uchun «Menga mos rank» filtrini o'chiring.")}</div>}
          </Empty>
        ) : list.map((p) => (
          <PostCard key={p.id} p={p} act={t(it.act)} busy={busy}
            onAct={() => run(async () => { const r = await api.post<{ text: string; username?: string | null }>(`/arena/posts/${p.id}/respond`); toast(t(r.text), "ok"); })}
            onClose={() => run(async () => { await api.post(`/arena/posts/${p.id}/close`); st.reload(); })} />
        ))}
      </Loadable>
      {open && <PostSheet kind={kind} meta={meta} onClose={() => setOpen(false)} onDone={() => { setOpen(false); st.reload(); }} />}
    </>
  );
}

function RespectBadge({ r }: { r: Respect | null | undefined }) {
  if (!r || r.pct == null) return null;
  if (r.toxic) return <span className="pill-b r" style={{ fontSize: 10, padding: "1px 7px" }}>⚠ {t("so'kinadi")}</span>;
  return <span className="pill-b g" style={{ fontSize: 10, padding: "1px 7px" }}>👍 {r.pct}%</span>;
}

function PostCard({ p, act, busy, onAct, onClose }: { p: Post; act: string; busy: boolean; onAct: () => void; onClose: () => void }) {
  const rk = rankKey(p.rank);
  const a = p.author;
  return (
    <div className="card col tight" style={{ gap: 8 }}>
      <div className="row">
        {p.team ? <span className="team-tag">{p.team.tag || p.team.name.slice(0, 3)}</span> : rk ? <MlIcon kind="rank" k={rk} size={44} /> : <span className="avatar-l" style={{ background: "#ffd60a" }}>{p.name[0]?.toUpperCase()}</span>}
        <div className="grow" style={{ minWidth: 0 }}>
          <div className="row" style={{ gap: 6 }}>
            <span className="b ell">{p.name}</span>
            {a?.verified && <span className="g xs b" title={t("Tasdiqlangan")}>✓</span>}
            {p.lane && <MlIcon kind="lane" k={laneKey(p.lane)} size={18} />}
            <RespectBadge r={p.respect} />
          </div>
          <div className="mut xs ell">
            {[p.team ? `👑 ${p.team.captain}` : "", rk ? rankLabel(rk) : p.rank, p.team?.avg_rank ? `${t("o'rtacha")} ${rankLabel(p.team.avg_rank)}` : "", p.region, p.online].filter(Boolean).join(" · ")}
          </div>
        </div>
        {p.mine ? <button className="btn small ghost" onClick={onClose}>{t("Yopish")}</button> : <button className="btn small" disabled={busy} onClick={onAct}>{act}</button>}
      </div>
      {(p.heroes.length > 0 || p.note || p.team) && (
        <div className="row" style={{ gap: 6 }}>
          {p.heroes.map((id) => <HeroAva key={id} id={id} size={28} radius={8} />)}
          {p.note && <span className="xs ell grow" style={{ color: "#d6dbe8" }}>{p.note}</span>}
          {p.team && <span className="pill-b g" style={{ fontSize: 10 }}>{p.team.members}/{p.team.max} · {t("{n} ta bo'sh joy", { n: p.team.free })}</span>}
        </div>
      )}
    </div>
  );
}

function RegionSelect({ value, onChange, regions, all = true }: { value: string; onChange: (v: string) => void; regions: string[]; all?: boolean }) {
  return (
    <select className="input region-sel" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">📍 {all ? t("Viloyat") : t("Viloyatni tanlang")}</option>
      {regions.map((r) => <option key={r} value={r}>{r}</option>)}
    </select>
  );
}

function PostSheet({ kind, meta, onClose, onDone }: { kind: Kind; meta: Meta; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ lane: "", online: "", note: "", region: meta.my_region, heroes: [] as number[] });
  const { busy, run } = useAction();
  const title: Record<Kind, string> = { scrim: "5v5 bahs e'loni", duel: "1v1 duel chaqiruvi", duo: "Rankedga sherik e'loni", team: "Jamoaga o'yinchi kerak", player: "Jamoa qidiryapman" };
  return (
    <Sheet open onClose={onClose}>
      <div className="sec-title" style={{ marginTop: 0 }}>{t(title[kind])}</div>
      <div className="col">
        {!meta.my_rank && <button className="card row click" onClick={editCard} style={{ textAlign: "left", borderColor: "rgba(255,214,10,.4)" }}><span className="grow sm">{t("Rank va liniya MLBB kartangizdan olinadi — avval kartani to'ldiring")}</span><Icon name="right" size={16} /></button>}
        {kind !== "scrim" && <Field label={kind === "team" ? t("Qaysi liniya kerak") : t("Liniya")}><LanePicker value={f.lane} onChange={(v) => setF({ ...f, lane: v })} /></Field>}
        {(kind === "duo" || kind === "player" || kind === "duel") && <Field label={kind === "duel" ? t("Qaysi qahramonda?") : t("Qahramonlar (3 tagacha)")}><HeroSlots max={kind === "duel" ? 1 : 3} value={f.heroes} onChange={(v) => setF({ ...f, heroes: v })} /></Field>}
        <Field label={kind === "scrim" || kind === "duel" ? t("Qachon?") : t("Onlayn vaqt")}><input className="input" maxLength={32} placeholder="20:00–24:00" value={f.online} onChange={(e) => setF({ ...f, online: e.target.value })} /></Field>
        <Field label={t("Viloyat")}><RegionSelect value={f.region} onChange={(v) => setF({ ...f, region: v })} regions={meta.regions} all={false} /></Field>
        <Field label={t("Izoh")}><input className="input" maxLength={300} placeholder={kind === "scrim" ? t("Masalan: BO3, Mythic+ jamoalar") : ""} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
        <div className="mut xs">{t("Javob berilganda bot sizga xabar yuboradi.")}</div>
        <button className="btn full" disabled={busy} onClick={() => run(async () => {
          await api.post("/arena/posts", { kind, ...f, lane: LANES.find((l) => l.v === f.lane)?.label ?? "" });
          onDone();
        })}>{t("Joylash")}</button>
      </div>
    </Sheet>
  );
}

// ---------------------------------------------------------------- sherik signali va hurmat
function SignalCard({ meta, onChange }: { meta: Meta; onChange: () => void }) {
  const { run } = useAction();
  return (
    <div className="card row">
      <span className="rowico y"><Icon name="bell" /></span>
      <div className="grow"><div className="b">{t("Sherik signali")}</div><div className="mut xs">{t("Rankingizga mos sherik e'loni chiqsa, bot darhol xabar beradi")}</div></div>
      <Toggle on={meta.signal} onChange={(v) => run(async () => { await api.post("/arena/signal", { enabled: v }); onChange(); })} />
    </div>
  );
}

interface Contact extends Card { my_rating: boolean | null; respect: Respect | null }

function RespectCard() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="card row click" style={{ textAlign: "left" }} onClick={() => setOpen(true)}>
        <span className="rowico g"><Icon name="star" /></span>
        <div className="grow"><div className="b">{t("Hurmat")}</div><div className="mut xs">{t("Birga o'ynaganlaringizni baholang: so'kinadiganlar belgilanadi")}</div></div>
        <Icon name="right" size={18} />
      </button>
      {open && <RespectSheet onClose={() => setOpen(false)} />}
    </>
  );
}

function RespectSheet({ onClose }: { onClose: () => void }) {
  const st = useLoad(() => api.get<Contact[]>("/arena/contacts"));
  const { run } = useAction();
  return (
    <Sheet open onClose={onClose}>
      <div className="sec-title" style={{ marginTop: 0 }}>{t("Hurmat")}</div>
      <div className="mut xs">{t("Faqat siz bilan bog'langan o'yinchilar. 👎 — so'kinish, o'yinni tashlab ketish.")}</div>
      <Loadable state={st}>
        {(list) => list.length === 0 ? <Empty icon="🤝" text={t("Hali hech kim bilan bog'lanmagansiz")} /> : list.map((c) => (
          <div key={c.user_id} className="card row tight">
            {rankKey(c.rank) ? <MlIcon kind="rank" k={rankKey(c.rank)} size={36} /> : <span className="avatar-l">{c.nick[0]?.toUpperCase()}</span>}
            <div className="grow" style={{ minWidth: 0 }}><div className="b ell">{c.nick} <RespectBadge r={c.respect} /></div><div className="mut xs">{[c.rank && rankLabel(rankKey(c.rank) || c.rank), c.lane && laneLabel(c.lane), c.region].filter(Boolean).join(" · ")}</div></div>
            <button className={"chip" + (c.my_rating === true ? " on" : "")} onClick={() => run(async () => { await api.post(`/arena/rate/${c.user_id}`, { good: true }); st.reload(); })}>👍</button>
            <button className={"chip" + (c.my_rating === false ? " on" : "")} onClick={() => run(async () => { await api.post(`/arena/rate/${c.user_id}`, { good: false }); st.reload(); })}>👎</button>
          </div>
        ))}
      </Loadable>
    </Sheet>
  );
}

// ---------------------------------------------------------------- jamoa
function TeamTab({ meta }: { meta: Meta }) {
  const [sub, setSub] = useState<"team" | "player" | "teams">("team");
  return (
    <>
      <MyTeamCard meta={meta} />
      <Seg value={sub} onChange={setSub} options={[{ v: "team", label: t("O'yinchi kerak") }, { v: "player", label: t("Jamoa kerak") }, { v: "teams", label: t("Jamoalar") }]} />
      {sub === "team" && <Posts kind="team" meta={meta} />}
      {sub === "player" && <Posts kind="player" meta={meta} />}
      {sub === "teams" && <Teams />}
    </>
  );
}

function MyTeamCard({ meta, compact }: { meta: Meta; compact?: boolean }) {
  const st = useLoad(() => api.get<MyTeam>("/arena/teams/my"));
  const [create, setCreate] = useState(false);
  const [manage, setManage] = useState(false);
  const { busy, run } = useAction();
  const { toast } = useApp();
  const d = st.data;
  if (!d) return null;
  if (d.team) {
    const tm = d.team;
    return (
      <>
        <button className="card row click" style={{ textAlign: "left", borderColor: "rgba(29,233,182,.4)" }} onClick={() => setManage(true)}>
          <span className="team-tag">{tm.tag || tm.name.slice(0, 3)}</span>
          <div className="grow" style={{ minWidth: 0 }}>
            <div className="b ell">{tm.name} {tm.is_captain && <span className="pill-b y" style={{ fontSize: 10 }}>👑 {t("sardor")}</span>}</div>
            <div className="mut xs">{t("Mening jamoam")} · {tm.members}/{tm.max}{tm.avg_rank ? ` · ${t("o'rtacha")} ${rankLabel(tm.avg_rank)}` : ""}</div>
          </div>
          {d.requests.length > 0 && <span className="adm-n on">{d.requests.length}</span>}
          <Icon name="right" size={18} />
        </button>
        {manage && <TeamSheet my={d} meta={meta} onClose={() => setManage(false)} onChange={(x) => st.setData(x)} />}
      </>
    );
  }
  if (compact) return (
    <div className="card row" style={{ borderColor: "rgba(255,214,10,.3)" }}>
      <div className="grow sm">{t("5v5 bahs uchun jamoa kerak.")}</div>
      <button className="btn small" onClick={() => setCreate(true)}>{t("Jamoa tuzish")}</button>
      {create && <CreateTeam meta={meta} onClose={() => setCreate(false)} onDone={(x) => { st.setData(x); setCreate(false); }} />}
    </div>
  );
  return (
    <>
      {d.invites.map((iv) => (
        <div key={iv.id} className="card col" style={{ borderColor: "rgba(255,214,10,.5)" }}>
          <div className="b">🤝 {t("«{n}» jamoasi sizni taklif qilmoqda", { n: iv.team.name })}</div>
          <div className="mut xs">{[`👑 ${iv.team.captain}`, iv.team.avg_rank && rankLabel(iv.team.avg_rank), iv.team.region, `${iv.team.members}/${iv.team.max}`].filter(Boolean).join(" · ")}</div>
          <div className="row">
            <button className="btn small grow" disabled={busy} onClick={() => run(async () => { st.setData(await api.post<MyTeam>(`/arena/requests/${iv.id}`, { accept: true })); toast(t("Jamoaga qo'shildingiz"), "ok"); })}>{t("Qabul qilish")}</button>
            <button className="btn small ghost" disabled={busy} onClick={() => run(async () => { st.setData(await api.post<MyTeam>(`/arena/requests/${iv.id}`, { accept: false })); })}>{t("Rad etish")}</button>
          </div>
        </div>
      ))}
      <div className="card row" style={{ borderColor: "rgba(255,214,10,.3)" }}>
        <span className="rowico y"><Icon name="grid" /></span>
        <div className="grow"><div className="b">{t("Jamoangiz yo'qmi?")}</div><div className="mut xs">{t("Jamoa tuzing yoki «Jamoalar» ro'yxatidan qo'shiling")}</div></div>
        <button className="btn small" onClick={() => setCreate(true)}>{t("Jamoa tuzish")}</button>
      </div>
      {create && <CreateTeam meta={meta} onClose={() => setCreate(false)} onDone={(x) => { st.setData(x); setCreate(false); }} />}
    </>
  );
}

function CreateTeam({ meta, onClose, onDone }: { meta: Meta; onClose: () => void; onDone: (x: MyTeam) => void }) {
  const [f, setF] = useState({ name: "", tag: "", region: meta.my_region, about: "", is_open: true });
  const { busy, run } = useAction();
  return (
    <Sheet open onClose={onClose}>
      <div className="sec-title" style={{ marginTop: 0 }}>{t("Jamoa tuzish")}</div>
      <div className="col">
        <Field label={t("Jamoa nomi")}><input className="input" maxLength={32} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label={t("Teg (2–6 harf)")}><input className="input mono" maxLength={6} placeholder="ORC" value={f.tag} onChange={(e) => setF({ ...f, tag: e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "") })} /></Field>
        <Field label={t("Viloyat")}><RegionSelect value={f.region} onChange={(v) => setF({ ...f, region: v })} regions={meta.regions} all={false} /></Field>
        <Field label={t("Jamoa haqida")}><input className="input" maxLength={200} value={f.about} onChange={(e) => setF({ ...f, about: e.target.value })} /></Field>
        <div className="row between"><span className="sm">{t("Yangi a'zolarni qabul qilish")}</span><Toggle on={f.is_open} onChange={(v) => setF({ ...f, is_open: v })} /></div>
        <div className="mut xs">{t("Jamoada 7 tagacha a'zo: 5 asosiy + 2 zaxira. Siz sardor bo'lasiz.")}</div>
        <button className="btn full" disabled={busy || f.name.trim().length < 2} onClick={() => run(async () => onDone(await api.post<MyTeam>("/arena/teams", f)))}>{t("Yaratish")}</button>
      </div>
    </Sheet>
  );
}

function Roster({ team, captain, onKick }: { team: TeamFull; captain: boolean; onKick?: (uid: number) => void }) {
  return (
    <div className="card" style={{ padding: "4px 12px" }}>
      {team.roster.map((m) => (
        <div key={m.user_id} className="listrow">
          {rankKey(m.rank) ? <MlIcon kind="rank" k={rankKey(m.rank)} size={34} /> : <span className="avatar-l" style={{ width: 34, height: 34 }}>{m.nick[0]?.toUpperCase()}</span>}
          <div className="grow" style={{ minWidth: 0 }}>
            <div className="b ell">{m.role === "captain" && "👑 "}{m.nick} {m.verified && <span className="g xs">✓</span>} <RespectBadge r={m.respect} /></div>
            <div className="mut xs">{[m.rank && rankLabel(rankKey(m.rank) || m.rank), m.lane && laneLabel(m.lane), m.region].filter(Boolean).join(" · ")}</div>
          </div>
          {m.lane && <MlIcon kind="lane" k={laneKey(m.lane)} size={20} />}
          {captain && m.role !== "captain" && onKick && <button className="btn small ghost" onClick={() => onKick(m.user_id)}>{t("Chiqarish")}</button>}
        </div>
      ))}
    </div>
  );
}

function TeamSheet({ my, meta, onClose, onChange }: { my: MyTeam; meta: Meta; onClose: () => void; onChange: (x: MyTeam) => void }) {
  const tm = my.team!;
  const { busy, run } = useAction();
  const { toast } = useApp();
  return (
    <Sheet open onClose={onClose}>
      <div className="row" style={{ marginBottom: 6 }}>
        <span className="team-tag">{tm.tag || tm.name.slice(0, 3)}</span>
        <div className="grow"><div className="hf bb" style={{ fontSize: 18 }}>{tm.name}</div><div className="mut xs">{[tm.region, `${tm.members}/${tm.max}`, tm.avg_rank && `${t("o'rtacha")} ${rankLabel(tm.avg_rank)}`].filter(Boolean).join(" · ")}</div></div>
      </div>
      {tm.about && <div className="mut sm">{tm.about}</div>}
      {tm.is_captain && my.requests.length > 0 && (
        <>
          <div className="sec-title">{t("Qo'shilish so'rovlari")}</div>
          {my.requests.map((r) => (
            <div key={r.id} className="card row tight">
              {rankKey(r.rank) ? <MlIcon kind="rank" k={rankKey(r.rank)} size={34} /> : <span className="avatar-l">{r.nick[0]?.toUpperCase()}</span>}
              <div className="grow" style={{ minWidth: 0 }}><div className="b ell">{r.nick} <RespectBadge r={r.respect} /></div><div className="mut xs">{[r.rank && rankLabel(rankKey(r.rank) || r.rank), r.lane && laneLabel(r.lane), r.region].filter(Boolean).join(" · ")}</div></div>
              <button className="btn small" disabled={busy} onClick={() => run(async () => { onChange(await api.post<MyTeam>(`/arena/requests/${r.id}`, { accept: true })); toast(t("Qabul qilindi"), "ok"); })}>✓</button>
              <button className="btn small ghost" disabled={busy} onClick={() => run(async () => onChange(await api.post<MyTeam>(`/arena/requests/${r.id}`, { accept: false })))}>✕</button>
            </div>
          ))}
        </>
      )}
      <div className="sec-title">{t("A'zolar")}</div>
      <Roster team={tm} captain={!!tm.is_captain} onKick={(uid) => run(async () => onChange(await api.post<MyTeam>("/arena/teams/kick", { user_id: uid })))} />
      {tm.is_captain && (
        <div className="card col">
          <div className="row between"><span className="sm">{t("Yangi a'zolarni qabul qilish")}</span><Toggle on={tm.is_open} onChange={(v) => run(async () => onChange(await api.patch<MyTeam>("/arena/teams/my", { is_open: v })))} /></div>
          <Field label={t("Viloyat")}><RegionSelect value={tm.region} onChange={(v) => run(async () => onChange(await api.patch<MyTeam>("/arena/teams/my", { region: v })))} regions={meta.regions} all={false} /></Field>
        </div>
      )}
      <button className="btn ghost full" disabled={busy} onClick={() => run(async () => { onChange(await api.post<MyTeam>("/arena/teams/leave")); onClose(); toast(t("Jamoadan chiqdingiz"), "ok"); })}>{t("Jamoadan chiqish")}</button>
    </Sheet>
  );
}

function Teams() {
  const [q, setQ] = useState("");
  const [free, setFree] = useState(false);
  const st = useLoad(() => api.get<TeamS[]>(`/arena/teams?q=${encodeURIComponent(q)}&open=${free ? 1 : 0}`), [q, free]);
  const [sel, setSel] = useState<number | null>(null);
  return (
    <>
      <div className="mut xs">{t("Barcha jamoalar: bo'sh joyi borlarga qo'shilish so'rovini yuboring.")}</div>
      <div className="row">
        <input className="input grow" placeholder={t("Jamoa nomi yoki tegi")} value={q} onChange={(e) => setQ(e.target.value)} />
        <button className={"chip" + (free ? " on" : "")} onClick={() => setFree(!free)}>{t("Bo'sh joy bor")}</button>
      </div>
      <Loadable state={st}>
        {(list) => list.length === 0 ? <Empty icon="🛡" text={t("Jamoalar topilmadi")} /> : list.map((x) => (
          <button key={x.id} className="card col click" style={{ textAlign: "left", gap: 8 }} onClick={() => setSel(x.id)}>
            <div className="row">
              <span className="team-tag">{x.tag || x.name.slice(0, 3)}</span>
              <div className="grow" style={{ minWidth: 0 }}>
                <div className="b ell" style={{ fontSize: 16 }}>{x.name}</div>
                <div className="mut xs ell">👑 {x.captain}{x.avg_rank ? ` · ${t("o'rtacha")} ${rankLabel(x.avg_rank)}` : ""}{x.region ? ` · ${x.region}` : ""}</div>
              </div>
              <div className="center"><div className="hf bb" style={{ fontSize: 18 }}>{x.members}/{x.max}</div><div className="mut xs">{t("a'zo")}</div></div>
            </div>
            {x.free > 0 && x.is_open && <span className="pill-b g" style={{ alignSelf: "flex-start" }}>{t("{n} ta bo'sh joy", { n: x.free })}</span>}
          </button>
        ))}
      </Loadable>
      {sel && <TeamView id={sel} onClose={() => setSel(null)} />}
    </>
  );
}

function TeamView({ id, onClose }: { id: number; onClose: () => void }) {
  const st = useLoad(() => api.get<TeamFull>(`/arena/teams/${id}`), [id]);
  const { busy, run } = useAction();
  const { toast } = useApp();
  return (
    <Sheet open onClose={onClose}>
      <Loadable state={st}>
        {(tm) => (
          <>
            <div className="row" style={{ marginBottom: 6 }}>
              <span className="team-tag">{tm.tag || tm.name.slice(0, 3)}</span>
              <div className="grow"><div className="hf bb" style={{ fontSize: 18 }}>{tm.name}</div><div className="mut xs">{[tm.region, `${tm.members}/${tm.max}`, tm.avg_rank && `${t("o'rtacha")} ${rankLabel(tm.avg_rank)}`].filter(Boolean).join(" · ")}</div></div>
            </div>
            {tm.about && <div className="mut sm">{tm.about}</div>}
            <Roster team={tm} captain={false} />
            {tm.is_member ? <div className="g sm center">✓ {t("Siz shu jamoadasiz")}</div> : tm.my_request ? (
              <div className="y sm center">⏳ {t("So'rovingiz sardorga yuborilgan")}</div>
            ) : (
              <button className="btn full" disabled={busy || tm.free <= 0 || !tm.is_open} onClick={() => run(async () => {
                await api.post(`/arena/teams/${tm.id}/join`);
                toast(t("So'rov sardorga yuborildi"), "ok");
                st.reload();
              })}>{tm.free <= 0 ? t("Bo'sh joy yo'q") : !tm.is_open ? t("Qabul yopiq") : t("Qo'shilish so'rovi")}</button>
            )}
          </>
        )}
      </Loadable>
    </Sheet>
  );
}

// MLBB qahramonlar ensiklopediyasi: rasmiy ma'lumot (mobilelegends.com) — skillar, tavsiya buyumlar, counter, juftlik.
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { t } from "../i18n";
import { HERO_BY_ID, HEROES, HeroAva, HeroPicker, LANES, laneLabel, MlIcon, ROLES, roleLabel } from "../mlbb";
import { BottomNav, Chips, Empty, Header, Spinner, useLoad } from "../ui";

interface Rel { id: number; tip: string }
interface HeroFull { attr: { phy: number; mag: number; alive: number; diff: number }; skills: { name: string; des: string }[]; build: number[]; best: Rel | null; counters: Rel | null; countered: Rel | null }
interface Item { id: number; name: string; des: string }
interface Full { heroes: Record<string, HeroFull>; items: Record<string, Item> }

let cache: Promise<Full> | null = null;
function loadFull(): Promise<Full> {
  if (!cache) cache = fetch("/mlbb/heroes_full.json").then((r) => { if (!r.ok) throw new Error("load"); return r.json(); }).catch((e) => { cache = null; throw e; });
  return cache;
}
function useFull() {
  const [d, setD] = useState<Full | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => { loadFull().then(setD).catch(() => setErr(true)); }, []);
  return { d, err };
}

const skillImg = (hid: number, i: number) => `/mlbb/skills/${hid}_${i}.webp`;
const itemImg = (id: number) => `/mlbb/items/${id}.webp`;
const hide = (e: React.SyntheticEvent<HTMLImageElement>) => { e.currentTarget.style.visibility = "hidden"; };

export function Heroes() {
  const nav = useNavigate();
  const [tab, setTab] = useState<"list" | "tier" | "counter" | "items">(() => (sessionStorage.getItem("vx_heroes_tab") as never) || "list");
  const pick = (v: typeof tab) => { setTab(v); try { sessionStorage.setItem("vx_heroes_tab", v); } catch { /* yo'q */ } };
  return (
    <>
      <Header title={t("Qahramonlar")} sub={t("{n} ta qahramon · rasmiy ma'lumot", { n: HEROES.length })} />
      <div className="page">
        <div className="tabs5">
          {([["list", "Ro'yxat"], ["tier", "Tier"], ["counter", "Counter"], ["items", "Buyumlar"]] as const).map(([v, l]) => (
            <button key={v} className={tab === v ? "on" : ""} onClick={() => pick(v)}>{t(l)}</button>
          ))}
        </div>
        {tab === "list" && <HeroList onOpen={(id) => nav(`/heroes/${id}`)} />}
        {tab === "tier" && <TierList onOpen={(id) => nav(`/heroes/${id}`)} />}
        {tab === "counter" && <CounterTool onOpen={(id) => nav(`/heroes/${id}`)} />}
        {tab === "items" && <Items />}
        <div className="mut xs center">{t("Ma'lumot manbasi: mobilelegends.com")} · {t("Statistika")}: <a className="y" href="https://arena.rone.dev" target="_blank" rel="noreferrer">Rone Arena</a></div>
      </div>
      <BottomNav />
    </>
  );
}

export interface Stat { hero: number; name: string; win: number; pick: number; ban: number; tier: string; mates: { hero: number; inc: number }[]; delta?: number }
interface StatsRes { items: Stat[] }
export const STAT_RANKS = [
  { v: "all", label: "Barcha ranklar", icon: "" }, { v: "epic", label: "Epic", icon: "epic" }, { v: "legend", label: "Legend", icon: "legend" },
  { v: "mythic", label: "Mythic", icon: "mythic" }, { v: "honor", label: "M. Honor", icon: "honor" }, { v: "glory", label: "M. Glory", icon: "glory" },
];
const TIER_COLOR: Record<string, string> = { S: "#ff5a6e", A: "#ff9f43", B: "#ffd60a", C: "#1de9b6", D: "#8a90a6" };
const pct = (x: number) => `${x.toFixed(1)}%`;

function RankChips({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="chips-scroll">
      {STAT_RANKS.map((r) => (
        <button key={r.v} className={"chip row" + (value === r.v ? " on" : "")} style={{ gap: 4 }} onClick={() => onChange(r.v)}>
          {r.icon && <MlIcon kind="rank" k={r.icon} size={18} />}{t(r.label)}
        </button>
      ))}
    </div>
  );
}

function TierList({ onOpen }: { onOpen: (id: number) => void }) {
  const [rank, setRank] = useState("all");
  const [days, setDays] = useState(7);
  const [view, setView] = useState<"tier" | "table">("tier");
  const [sort, setSort] = useState<"win" | "pick" | "ban">("win");
  const st = useLoad(() => api.get<StatsRes>(`/mlbb/stats?rank=${rank}&days=${days}`), [rank, days]);
  const items = (st.data?.items ?? []).filter((x) => HERO_BY_ID[x.hero]);
  return (
    <>
      <RankChips value={rank} onChange={setRank} />
      <div className="row between">
        <Chips value={String(days)} onChange={(v) => setDays(Number(v))} options={[{ v: "1", label: t("1 kun") }, { v: "7", label: t("7 kun") }, { v: "30", label: t("30 kun") }]} />
        <Chips value={view} onChange={setView} options={[{ v: "tier", label: "Tier" }, { v: "table", label: t("Jadval") }]} />
      </div>
      {st.error ? <Empty icon="📉" text={st.error} /> : !st.data ? <Spinner /> : view === "tier" ? (
        ["S", "A", "B", "C", "D"].map((tr) => {
          const row = items.filter((x) => x.tier === tr).sort((a, b) => b.win - a.win);
          if (!row.length) return null;
          return (
            <div key={tr} className="card row" style={{ alignItems: "flex-start", gap: 10 }}>
              <span className="tier-badge" style={{ background: TIER_COLOR[tr] }}>{tr}</span>
              <div className="tier-heroes">
                {row.map((x) => (
                  <button key={x.hero} className="tier-hero" onClick={() => onOpen(x.hero)} title={`${x.name} · ${pct(x.win)}`}>
                    <HeroAva id={x.hero} size={42} radius={10} />
                    <span>{x.win.toFixed(1)}</span>
                  </button>
                ))}
              </div>
            </div>
          );
        })
      ) : (
        <div className="card" style={{ padding: "4px 10px" }}>
          <div className="stat-row head">
            <span>#</span><span>{t("Qahramon")}</span>
            {(["win", "pick", "ban"] as const).map((k) => (
              <button key={k} className={sort === k ? "y" : ""} onClick={() => setSort(k)}>{k === "win" ? "WR" : k === "pick" ? "Pick" : "Ban"}{sort === k ? " ↓" : ""}</button>
            ))}
          </div>
          {[...items].sort((a, b) => b[sort] - a[sort]).map((x, i) => (
            <button key={x.hero} className="stat-row" onClick={() => onOpen(x.hero)}>
              <span className="mut mono">{i + 1}</span>
              <span className="row" style={{ gap: 8, minWidth: 0 }}><HeroAva id={x.hero} size={28} radius={8} /><span className="b ell">{x.name}</span></span>
              <span className="mono" style={{ color: x.win >= 50 ? "var(--g)" : "var(--r)" }}>{pct(x.win)}</span>
              <span className="mono">{pct(x.pick)}</span>
              <span className="mono">{pct(x.ban)}</span>
            </button>
          ))}
        </div>
      )}
      <div className="mut xs">{t("Tier: g'alaba foizi, tanlanish va ban asosida avtomatik baho. Ma'lumot har 6 soatda yangilanadi.")}</div>
    </>
  );
}

/** Qahramon sahifasi uchun: joriy statistika (barcha ranklar, 7 kun) va kuchli raqiblar. */
function LiveHero({ id, onOpen }: { id: number; onOpen: (id: number) => void }) {
  const [rank, setRank] = useState("all");
  const st = useLoad(() => api.get<StatsRes>(`/mlbb/stats?rank=${rank}&days=7`), [rank]);
  const ct = useLoad(() => api.get<{ counters: { hero: number; win: number; inc: number }[] }>(`/mlbb/counters/${id}?rank=${rank}`), [id, rank]);
  const me = st.data?.items.find((x) => x.hero === id);
  const total = st.data?.items.length ?? 0;
  const place = me ? [...(st.data?.items ?? [])].sort((a, b) => b.win - a.win).findIndex((x) => x.hero === id) + 1 : 0;
  if (st.error) return null;
  return (
    <>
      <div className="sec-title">{t("Statistika (7 kun)")}</div>
      <RankChips value={rank} onChange={setRank} />
      {!st.data ? <Spinner /> : me ? (
        <div className="card col">
          <div className="grid3 center">
            <div><div className="hf bb" style={{ fontSize: 20, color: me.win >= 50 ? "var(--g)" : "var(--r)" }}>{pct(me.win)}</div><div className="mut xs">{t("G'alaba")}</div></div>
            <div><div className="hf bb" style={{ fontSize: 20 }}>{pct(me.pick)}</div><div className="mut xs">{t("Tanlanish")}</div></div>
            <div><div className="hf bb" style={{ fontSize: 20 }}>{pct(me.ban)}</div><div className="mut xs">Ban</div></div>
          </div>
          <div className="row between sm"><span>Tier <b style={{ color: TIER_COLOR[me.tier] }}>{me.tier}</b></span><span className="mut">{t("G'alaba bo'yicha {p}-o'rin / {n}", { p: place, n: total })}</span></div>
          {me.mates.length > 0 && (
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <span className="xs mut">{t("Yaxshi juftlar")}:</span>
              {me.mates.filter((m) => HERO_BY_ID[m.hero]).map((m) => (
                <button key={m.hero} className="row chip" style={{ gap: 4 }} onClick={() => onOpen(m.hero)}><HeroAva id={m.hero} size={22} radius={6} /><span className="g xs">+{m.inc.toFixed(1)}%</span></button>
              ))}
            </div>
          )}
        </div>
      ) : <div className="mut sm">{t("Bu rank uchun statistika yo'q")}</div>}
      {ct.data && ct.data.counters.length > 0 && (
        <div className="card col">
          <div className="b sm r">⚔️ {t("Kuchli raqiblari (counter)")}</div>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            {ct.data.counters.filter((c) => HERO_BY_ID[c.hero]).map((c) => (
              <button key={c.hero} className="tier-hero" onClick={() => onOpen(c.hero)}>
                <HeroAva id={c.hero} size={42} radius={10} />
                <span className="r">+{c.inc.toFixed(1)}%</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

/** Arena uchun: oxirgi haftada kuchayganlar (7 kunlik g'alaba foizi 30 kunlikdan yuqori). */
export function Risers({ onOpen }: { onOpen: (id: number) => void }) {
  const st = useLoad(() => api.get<StatsRes>("/mlbb/risers"));
  const list = (st.data?.items ?? []).filter((x) => HERO_BY_ID[x.hero]).slice(0, 3);
  if (st.error || (st.data && !list.length)) return null;
  return (
    <div className="card col">
      <div className="b">⭐ {t("Bu hafta kuchayganlar")}</div>
      {!st.data ? <Spinner /> : (
        <div className="grid3">
          {list.map((x) => (
            <button key={x.hero} className="riser" onClick={() => onOpen(x.hero)}>
              <HeroAva id={x.hero} size={58} radius={29} ring />
              <span className="b sm ell">{x.name}</span>
              <span className="mut xs">WR {pct(x.win)}</span>
              <span className="g xs b">↗ +{(x.delta ?? 0).toFixed(1)}%</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function HeroList({ onOpen }: { onOpen: (id: number) => void }) {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [lane, setLane] = useState("");
  const list = useMemo(() => {
    const s = q.trim().toLowerCase();
    return HEROES.filter((h) => (!role || h.role === role) && (!lane || h.lane === lane) && (!s || h.name.toLowerCase().includes(s)));
  }, [q, role, lane]);
  return (
    <>
      <input className="input" placeholder={t("Qahramon qidirish...")} value={q} onChange={(e) => setQ(e.target.value)} />
      <Chips value={role} onChange={setRole} options={[{ v: "", label: t("Barcha rollar") }, ...ROLES.map((r) => ({ v: r.v, label: t(r.label) }))]} />
      <Chips value={lane} onChange={setLane} options={[{ v: "", label: t("Barcha liniyalar") }, ...LANES.map((l) => ({ v: l.v, label: l.label }))]} />
      {list.length === 0 ? <Empty icon="🔍" text={t("Topilmadi")} /> : (
        <div className="hero-grid" style={{ maxHeight: "none" }}>
          {list.map((h) => (
            <button key={h.id} className="hero-cell" onClick={() => onOpen(h.id)}>
              <HeroAva id={h.id} size={60} radius={16} />
              <span className="ell">{h.name}</span>
              <span className="row" style={{ gap: 3 }}><MlIcon kind="role" k={h.role} size={14} /><MlIcon kind="lane" k={h.lane} size={14} /></span>
            </button>
          ))}
        </div>
      )}
    </>
  );
}

function Bar({ label, v, color }: { label: string; v: number; color: string }) {
  return (
    <div className="col" style={{ gap: 3 }}>
      <div className="row between xs"><span className="mut">{label}</span><span className="mono b">{v}</span></div>
      <div className="progress"><i style={{ width: Math.min(100, v) + "%", background: color }} /></div>
    </div>
  );
}

function RelCard({ title, rel, color, onOpen }: { title: string; rel: Rel | null; color: string; onOpen: (id: number) => void }) {
  if (!rel) return null;
  const h = HERO_BY_ID[rel.id];
  return (
    <button className="card row click" style={{ textAlign: "left", alignItems: "flex-start", borderColor: color }} onClick={() => onOpen(rel.id)}>
      <HeroAva id={rel.id} size={48} radius={12} />
      <div className="grow" style={{ minWidth: 0 }}>
        <div className="xs b" style={{ color }}>{title}</div>
        <div className="b">{h?.name}</div>
        {rel.tip && <div className="mut xs">{rel.tip}</div>}
      </div>
    </button>
  );
}

export function HeroPage() {
  const id = Number(useParams().id);
  const nav = useNavigate();
  const { d, err } = useFull();
  const h = HERO_BY_ID[id];
  if (!h) return <><Header title={t("Qahramonlar")} /><Empty icon="🔍" text={t("Topilmadi")} /></>;
  const f = d?.heroes[String(id)];
  const open = (x: number) => nav(`/heroes/${x}`);
  return (
    <>
      <Header title={h.name} sub={`${roleLabel(h.role)} · ${laneLabel(h.lane)}`} />
      <div className="page">
        <div className="hero row" style={{ gap: 14 }}>
          <HeroAva id={id} size={88} radius={22} ring />
          <div className="col grow" style={{ gap: 6 }}>
            <div className="hf bb" style={{ fontSize: 22 }}>{h.name}</div>
            <div className="row" style={{ gap: 8 }}>
              <span className="pill-b y row" style={{ gap: 4 }}><MlIcon kind="role" k={h.role} size={16} />{roleLabel(h.role)}</span>
              <span className="pill-b b row" style={{ gap: 4 }}><MlIcon kind="lane" k={h.lane} size={16} />{laneLabel(h.lane)}</span>
            </div>
          </div>
        </div>
        <LiveHero id={id} onOpen={open} />
        {err && <div className="r sm">{t("Ma'lumotni yuklab bo'lmadi")}</div>}
        {!d && !err && <Spinner />}
        {f && (
          <>
            <div className="card col">
              <Bar label={t("Jismoniy hujum")} v={f.attr.phy} color="#ff9f43" />
              <Bar label={t("Sehrli hujum")} v={f.attr.mag} color="#a78bfa" />
              <Bar label={t("Chidamlilik")} v={f.attr.alive} color="var(--g)" />
              <Bar label={t("Qiyinlik")} v={f.attr.diff} color="var(--r)" />
            </div>
            {(f.best || f.counters || f.countered) && (
              <>
                <div className="sec-title">{t("Counter va juftlik")}</div>
                <RelCard title={t("Eng yaxshi jufti")} rel={f.best} color="rgba(29,233,182,.5)" onOpen={open} />
                <RelCard title={t("Kimni yengadi")} rel={f.counters} color="rgba(255,214,10,.5)" onOpen={open} />
                <RelCard title={t("Kim yengadi (ehtiyot bo'ling)")} rel={f.countered} color="rgba(255,90,110,.5)" onOpen={open} />
              </>
            )}
            {f.build.length > 0 && d && (
              <>
                <div className="sec-title">{t("Tavsiya etilgan buyumlar")}</div>
                <div className="card">
                  <div className="build-row">
                    {f.build.map((iid, i) => (
                      <div key={i} className="build-item" title={d.items[String(iid)]?.name}>
                        <img src={itemImg(iid)} alt="" onError={hide} />
                        <span className="ell">{d.items[String(iid)]?.name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
            <div className="sec-title">{t("Skillar")}</div>
            {f.skills.map((s, i) => (
              <div key={i} className="card row" style={{ alignItems: "flex-start" }}>
                <img src={skillImg(id, i)} alt="" onError={hide} style={{ width: 44, height: 44, borderRadius: 12, flexShrink: 0 }} />
                <div className="grow" style={{ minWidth: 0 }}>
                  <div className="b">{s.name} <span className="mut xs">{i === 0 ? t("Passiv") : `${t("Skill")} ${i}`}</span></div>
                  <div className="mut xs" style={{ whiteSpace: "pre-wrap" }}>{s.des}</div>
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </>
  );
}

/** Raqib jamoasini tanlang — ularni yengadigan qahramonlar tavsiya qilinadi (rasmiy counter ma'lumotlari asosida). */
function CounterTool({ onOpen }: { onOpen: (id: number) => void }) {
  const { d, err } = useFull();
  const [enemy, setEnemy] = useState<number[]>([]);
  const [open, setOpen] = useState(false);
  const [lane, setLane] = useState("");
  const [live, setLive] = useState<Record<number, { hero: number; inc: number }[]>>({});
  useEffect(() => {
    for (const e of enemy) {
      if (live[e]) continue;
      api.get<{ counters: { hero: number; inc: number }[] }>(`/mlbb/counters/${e}`)
        .then((r) => setLive((x) => ({ ...x, [e]: r.counters })))
        .catch(() => setLive((x) => ({ ...x, [e]: [] })));
    }
  }, [enemy]); // eslint-disable-line react-hooks/exhaustive-deps
  const recs = useMemo(() => {
    if (!d || !enemy.length) return [];
    const score = new Map<number, { s: number; vs: number[] }>();
    const add = (hid: number, vs: number, w: number) => {
      if (enemy.includes(hid)) return;
      const x = score.get(hid) ?? { s: 0, vs: [] };
      x.s += w;
      if (!x.vs.includes(vs)) x.vs.push(vs);
      score.set(hid, x);
    };
    for (const e of enemy) {
      for (const c of live[e] ?? []) add(c.hero, e, 2 + Math.max(0, c.inc)); // tirik statistika: raqibga qarshi g'alaba oshishi
      const f = d.heroes[String(e)];
      if (f?.countered) add(f.countered.id, e, 3); // dushmanni to'g'ridan-to'g'ri yengadi
      for (const [hid, g] of Object.entries(d.heroes)) {
        if (g.counters?.id === e) add(Number(hid), e, 2); // «kimni yengadi» ro'yxatida dushman bor
      }
    }
    return [...score.entries()].filter(([hid]) => !lane || HERO_BY_ID[hid]?.lane === lane)
      .sort((a, b) => b[1].s - a[1].s).slice(0, 12);
  }, [d, enemy, lane, live]);
  return (
    <>
      <div className="card col" style={{ borderColor: "rgba(255,90,110,.45)" }}>
        <div className="b r">⚔️ {t("Raqib jamoasi")}</div>
        <div className="row" style={{ gap: 6 }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <button key={i} className="hero-slot" style={{ width: "20%", minHeight: 64 }} onClick={() => setOpen(true)}>
              {enemy[i] ? <HeroAva id={enemy[i]} size={44} radius={12} /> : <span className="mut" style={{ fontSize: 20 }}>+</span>}
            </button>
          ))}
        </div>
        {enemy.length > 0 && <button className="linkbtn mut xs" onClick={() => setEnemy([])}>{t("Tozalash")}</button>}
      </div>
      <div className="mut xs">{t("Siz qaysi liniyada o'ynaysiz?")}</div>
      <Chips value={lane} onChange={setLane} options={[{ v: "", label: t("Barchasi") }, ...LANES.map((l) => ({ v: l.v, label: l.label }))]} />
      {err && <div className="r sm">{t("Ma'lumotni yuklab bo'lmadi")}</div>}
      {!enemy.length ? <Empty icon="🎯" text={t("Raqib qahramonlarini tanlang — ularga qarshi eng yaxshi tanlov ko'rsatiladi")} /> : !d ? <Spinner /> : recs.length === 0 ? (
        <Empty icon="🤷" text={t("Bu tanlov uchun counter ma'lumoti yo'q")} />
      ) : (
        <>
          <div className="sec-title">{t("Tavsiya")}</div>
          {recs.map(([hid, x]) => (
            <button key={hid} className="card row click" style={{ textAlign: "left" }} onClick={() => onOpen(hid)}>
              <HeroAva id={hid} size={44} radius={12} />
              <div className="grow" style={{ minWidth: 0 }}>
                <div className="row" style={{ gap: 6 }}><span className="b">{HERO_BY_ID[hid]?.name}</span><MlIcon kind="lane" k={HERO_BY_ID[hid]?.lane ?? ""} size={16} /></div>
                <div className="mut xs ell">{t("Qarshi")}: {x.vs.map((v) => HERO_BY_ID[v]?.name).join(", ")}</div>
              </div>
              <span className="pill-b g">{x.s >= 7 ? t("Juda mos") : t("Mos")}</span>
            </button>
          ))}
        </>
      )}
      <HeroPicker open={open} value={enemy} max={5} onClose={() => setOpen(false)} onChange={setEnemy} />
    </>
  );
}

function Items() {
  const { d, err } = useFull();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<Item | null>(null);
  if (err) return <div className="r sm">{t("Ma'lumotni yuklab bo'lmadi")}</div>;
  if (!d) return <Spinner />;
  const list = Object.values(d.items).filter((x) => !q.trim() || x.name.toLowerCase().includes(q.trim().toLowerCase())).sort((a, b) => a.name.localeCompare(b.name));
  const users = sel ? Object.entries(d.heroes).filter(([, h]) => h.build.includes(sel.id)).map(([id]) => Number(id)) : [];
  return (
    <>
      <input className="input" placeholder={t("Buyum qidirish...")} value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="item-grid">
        {list.map((x) => (
          <button key={x.id} className={"hero-cell" + (sel?.id === x.id ? " on" : "")} onClick={() => setSel(sel?.id === x.id ? null : x)}>
            <img src={itemImg(x.id)} alt="" onError={hide} style={{ width: 52, height: 52, borderRadius: 12 }} />
            <span className="ell">{x.name}</span>
          </button>
        ))}
      </div>
      {sel && (
        <div className="card col" style={{ borderColor: "rgba(255,214,10,.45)", position: "sticky", bottom: 100 }}>
          <div className="row"><img src={itemImg(sel.id)} alt="" onError={hide} style={{ width: 44, height: 44, borderRadius: 10 }} /><div className="b grow">{sel.name}</div></div>
          <div className="mut xs">{sel.des}</div>
          {users.length > 0 && (
            <div className="row" style={{ gap: 4, flexWrap: "wrap" }}><span className="xs mut">{t("Kimlar oladi")}:</span>{users.slice(0, 12).map((u) => <HeroAva key={u} id={u} size={26} radius={7} />)}</div>
          )}
        </div>
      )}
    </>
  );
}

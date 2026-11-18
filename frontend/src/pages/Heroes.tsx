// MLBB qahramonlar ensiklopediyasi: rasmiy ma'lumot (mobilelegends.com) — skillar, tavsiya buyumlar, counter, juftlik.
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { t } from "../i18n";
import { HERO_BY_ID, HEROES, HeroAva, HeroPicker, LANES, laneLabel, MlIcon, ROLES, roleLabel } from "../mlbb";
import { BottomNav, Chips, Empty, Header, Spinner } from "../ui";

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
  const [tab, setTab] = useState<"list" | "counter" | "items">(() => (sessionStorage.getItem("vx_heroes_tab") as never) || "list");
  const pick = (v: typeof tab) => { setTab(v); try { sessionStorage.setItem("vx_heroes_tab", v); } catch { /* yo'q */ } };
  return (
    <>
      <Header title={t("Qahramonlar")} sub={t("{n} ta qahramon · rasmiy ma'lumot", { n: HEROES.length })} />
      <div className="page">
        <div className="tabs5">
          {([["list", "Ro'yxat"], ["counter", "Counter"], ["items", "Buyumlar"]] as const).map(([v, l]) => (
            <button key={v} className={tab === v ? "on" : ""} onClick={() => pick(v)}>{t(l)}</button>
          ))}
        </div>
        {tab === "list" && <HeroList onOpen={(id) => nav(`/heroes/${id}`)} />}
        {tab === "counter" && <CounterTool onOpen={(id) => nav(`/heroes/${id}`)} />}
        {tab === "items" && <Items />}
        <div className="mut xs center">{t("Ma'lumot manbasi: mobilelegends.com")}</div>
      </div>
      <BottomNav />
    </>
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
      const f = d.heroes[String(e)];
      if (f?.countered) add(f.countered.id, e, 3); // dushmanni to'g'ridan-to'g'ri yengadi
      for (const [hid, g] of Object.entries(d.heroes)) {
        if (g.counters?.id === e) add(Number(hid), e, 2); // «kimni yengadi» ro'yxatida dushman bor
      }
    }
    return [...score.entries()].filter(([hid]) => !lane || HERO_BY_ID[hid]?.lane === lane)
      .sort((a, b) => b[1].s - a[1].s).slice(0, 12);
  }, [d, enemy, lane]);
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
              <span className="pill-b g">{x.s >= 5 ? t("Juda mos") : t("Mos")}</span>
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

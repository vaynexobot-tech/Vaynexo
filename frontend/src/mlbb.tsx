// MLBB: rasmiy qahramon portretlari, liniya / rol / rank ikonkalari (public/mlbb/*) va tanlash komponentlari.
import { useMemo, useState } from "react";
import HEROES_JSON from "./mlbb_heroes.json";
import { t } from "./i18n";
import { Chips, Sheet } from "./ui";

export interface Hero { id: number; name: string; role: string; lane: string; diff: number }
export const HEROES = HEROES_JSON as Hero[];
export const HERO_BY_ID: Record<number, Hero> = Object.fromEntries(HEROES.map((h) => [h.id, h]));

export const LANES = [
  { v: "gold", label: "Gold" }, { v: "exp", label: "EXP" }, { v: "mid", label: "Mid" }, { v: "jungle", label: "Jungle" }, { v: "roam", label: "Roam" },
];
export const ROLES = [
  { v: "tank", label: "Tank" }, { v: "fighter", label: "Jangchi" }, { v: "assassin", label: "Qotil" },
  { v: "mage", label: "Sehrgar" }, { v: "marksman", label: "Mergan" }, { v: "support", label: "Yordamchi" },
];
export const RANKS = [
  { v: "warrior", label: "Warrior" }, { v: "elite", label: "Elite" }, { v: "master", label: "Master" }, { v: "grandmaster", label: "Grandmaster" },
  { v: "epic", label: "Epic" }, { v: "legend", label: "Legend" }, { v: "mythic", label: "Mythic" }, { v: "honor", label: "Mythical Honor" },
  { v: "glory", label: "Mythical Glory" }, { v: "immortal", label: "Mythical Immortal" },
];

const base = "/mlbb";
export const heroImg = (id: number) => `${base}/heroes/${id}.webp`;
export const iconImg = (kind: "lane" | "role" | "rank", key: string) => `${base}/icons/${kind}-${key}.webp`;

/** Matndagi rank nomidan (Mythic 34★, M. Glory, Epic V) kalit topadi. */
export function rankKey(s: string | null | undefined): string {
  const x = (s || "").toLowerCase();
  if (!x) return "";
  if (x.includes("immortal")) return "immortal";
  if (x.includes("glory")) return "glory";
  if (x.includes("honor")) return "honor";
  for (const r of ["grandmaster", "master", "warrior", "elite", "epic", "legend", "mythic"]) if (x.includes(r)) return r;
  return RANKS.some((r) => r.v === x) ? x : "";
}
export const rankLabel = (k: string) => RANKS.find((r) => r.v === k)?.label ?? k;
export const laneKey = (s: string | null | undefined) => (s || "").toLowerCase();
export const laneLabel = (k: string) => LANES.find((l) => l.v === laneKey(k))?.label ?? k;
export const roleLabel = (k: string) => t(ROLES.find((r) => r.v === k)?.label ?? k);

export function HeroAva({ id, size = 40, radius = 12, ring }: { id: number; size?: number; radius?: number; ring?: boolean }) {
  const h = HERO_BY_ID[id];
  return (
    <img src={heroImg(id)} alt={h?.name ?? ""} title={h?.name} loading="lazy" className="hero-ava"
      style={{ width: size, height: size, borderRadius: radius, boxShadow: ring ? "0 0 0 2px var(--y)" : undefined }} />
  );
}

export function MlIcon({ kind, k, size = 22 }: { kind: "lane" | "role" | "rank"; k: string; size?: number }) {
  if (!k) return null;
  return <img src={iconImg(kind, k)} alt={k} title={kind === "rank" ? rankLabel(k) : kind === "lane" ? laneLabel(k) : roleLabel(k)} loading="lazy"
    style={{ width: size, height: size, objectFit: "contain", flexShrink: 0, borderRadius: kind === "lane" ? 6 : 0 }} />;
}

/** Liniya tanlash — rasmiy ikonkalar bilan. */
export function LanePicker({ value, onChange, allowEmpty = true }: { value: string; onChange: (v: string) => void; allowEmpty?: boolean }) {
  return (
    <div className="icon-pick">
      {LANES.map((l) => (
        <button key={l.v} type="button" className={laneKey(value) === l.v ? "on" : ""} onClick={() => onChange(allowEmpty && laneKey(value) === l.v ? "" : l.v)}>
          <MlIcon kind="lane" k={l.v} size={30} /><span>{l.label}</span>
        </button>
      ))}
    </div>
  );
}

/** Rank tanlash — rasmiy rank nishonlari. */
export function RankPicker({ value, onChange, only }: { value: string; onChange: (v: string) => void; only?: string[] }) {
  const list = only ? RANKS.filter((r) => only.includes(r.v)) : RANKS;
  return (
    <div className="icon-pick rank">
      {list.map((r) => (
        <button key={r.v} type="button" className={value === r.v ? "on" : ""} onClick={() => onChange(value === r.v ? "" : r.v)}>
          <MlIcon kind="rank" k={r.v} size={40} /><span>{r.label.replace("Mythical ", "M. ")}</span>
        </button>
      ))}
    </div>
  );
}

/** Qahramon tanlash oynasi: qidiruv + rol bo'yicha filtr, bir nechta tanlash. */
export function HeroPicker({ open, value, max = 3, onClose, onChange, disabled }: { open: boolean; value: number[]; max?: number; onClose: () => void; onChange: (v: number[]) => void; disabled?: number[] }) {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const list = useMemo(() => {
    const s = q.trim().toLowerCase();
    return HEROES.filter((h) => (!role || h.role === role) && (!s || h.name.toLowerCase().includes(s)));
  }, [q, role]);
  const toggle = (id: number) => {
    if (value.includes(id)) onChange(value.filter((x) => x !== id));
    else if (max === 1) { onChange([id]); onClose(); }
    else if (value.length < max) onChange([...value, id]);
  };
  return (
    <Sheet open={open} onClose={onClose}>
      <div className="row between"><div className="sec-title" style={{ margin: 0 }}>{t("Qahramon tanlang")}</div><span className="mut xs">{value.length}/{max}</span></div>
      <input className="input" placeholder={t("Qahramon qidirish...")} value={q} onChange={(e) => setQ(e.target.value)} />
      <Chips value={role} onChange={setRole} options={[{ v: "", label: t("Hammasi") }, ...ROLES.map((r) => ({ v: r.v, label: t(r.label) }))]} />
      <div className="hero-grid">
        {list.map((h) => (
          <button key={h.id} type="button" className={"hero-cell" + (value.includes(h.id) ? " on" : "")} disabled={disabled?.includes(h.id)}
            style={disabled?.includes(h.id) ? { opacity: 0.25, filter: "grayscale(1)" } : undefined} onClick={() => toggle(h.id)}>
            <HeroAva id={h.id} size={56} radius={14} />
            <span className="ell">{h.name}</span>
          </button>
        ))}
      </div>
      {max > 1 && <button className="btn full" onClick={onClose}>{t("Tayyor")}</button>}
    </Sheet>
  );
}

/** Tanlangan qahramonlar qatori (bosilganda tanlash oynasi). */
export function HeroSlots({ value, max = 3, onChange }: { value: number[]; max?: number; onChange: (v: number[]) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <div className="row" style={{ gap: 8 }}>
        {Array.from({ length: max }).map((_, i) => {
          const id = value[i];
          return (
            <button key={i} type="button" className="hero-slot" onClick={() => setOpen(true)} aria-label={t("Qahramon tanlang")}>
              {id ? <HeroAva id={id} size={54} radius={14} /> : <span className="mut" style={{ fontSize: 22 }}>+</span>}
              <span className="xs ell">{id ? HERO_BY_ID[id]?.name : t("Tanlash")}</span>
            </button>
          );
        })}
      </div>
      <HeroPicker open={open} value={value} max={max} onClose={() => setOpen(false)} onChange={onChange} />
    </>
  );
}

/** Matnli rank tanlash (Epic, Legend, Mythic Honor...) — rasmiy nishonlar bilan. */
export function RankChips({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <div className="icon-pick" style={{ gridTemplateColumns: `repeat(${Math.min(options.length, 3)}, 1fr)` }}>
      {options.map((o) => (
        <button key={o} type="button" className={value === o ? "on" : ""} onClick={() => onChange(o)}>
          <MlIcon kind="rank" k={rankKey(o)} size={40} /><span style={{ fontSize: 11 }}>{o}</span>
        </button>
      ))}
    </div>
  );
}

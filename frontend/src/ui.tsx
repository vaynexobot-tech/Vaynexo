import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { ApiError, type Me } from "./api";
import { t } from "./i18n";
import { haptic, openExternal, tg } from "./tg";

// Rasmiy o'yin ikonkalari (App Store'dan): assets/games/<slug>.webp
export const GAME_IMG: Record<string, string> = Object.fromEntries(
  Object.entries(import.meta.glob("./assets/games/*.webp", { eager: true, import: "default" }) as Record<string, string>).map(([k, v]) => [k.split("/").pop()!.replace(".webp", ""), v]),
);
// Rasm yuklanmagan o'yinlar uchun chiroyli zaxira ko'rinish: [rang1, rang2, belgi]
const GAME_STYLE: Record<string, [string, string, string]> = {
  "pubg-mobile": ["#f2a900", "#5b3a00", "🪖"],
  steam: ["#1b2838", "#2a75bb", "🎮"],
  "free-fire": ["#ff6a00", "#7a1500", "🔥"],
  "standoff-2": ["#3a4a5c", "#0e151d", "🎯"],
  "delta-force": ["#4b6b3a", "#14200f", "🪂"],
  "genshin-impact": ["#7fb8ff", "#3b2a6b", "✨"],
  roblox: ["#e2231a", "#3a0705", "🧱"],
  "honor-of-kings": ["#d4a84b", "#4a1d0c", "👑"],
  "blood-strike": ["#b3001b", "#1c0004", "🩸"],
  "arena-breakout": ["#6b5a3a", "#1a150c", "🎒"],
};

// ---------------------------------------------------------------- formatlash
export const money = (n: number) => Math.round(n).toLocaleString("ru-RU").replace(/,/g, " ");
export const som = (n: number) => `${money(n)} ${t("so'm")}`;

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const now = new Date();
  const hm = d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === now.toDateString()) return `${t("Bugun")}, ${hm}`;
  const y = new Date(now);
  y.setDate(now.getDate() - 1);
  if (d.toDateString() === y.toDateString()) return `${t("Kecha")}, ${hm}`;
  return `${d.toLocaleDateString("ru-RU")}, ${hm}`;
}

// ---------------------------------------------------------------- global holat
interface Ctx {
  me: Me | null;
  setMe: (m: Me) => void;
  refreshMe: () => Promise<void>;
  toast: (msg: string, kind?: "ok" | "err" | "info") => void;
  fail: (e: unknown) => void;
}
export const AppCtx = createContext<Ctx>(null as unknown as Ctx);
export const useApp = () => useContext(AppCtx);

export function useToastHost() {
  const [toast, setToast] = useState<{ msg: string; kind: string; id: number } | null>(null);
  const show = useCallback((msg: string, kind: "ok" | "err" | "info" = "info") => {
    const id = Date.now();
    setToast({ msg, kind, id });
    haptic(kind === "err" ? "error" : kind === "ok" ? "success" : "light");
    setTimeout(() => setToast((cur) => (cur?.id === id ? null : cur)), 3200);
  }, []);
  const node = toast ? <div className={`toast ${toast.kind}`}>{toast.msg}</div> : null;
  return { show, node };
}

export function errorText(e: unknown): string {
  if (e instanceof ApiError) return t(e.message);
  return t("Xatolik yuz berdi");
}

/** Ma'lumot yuklash hooki. `reload` qayta yuklaydi. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await fnRef.current());
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, setData, error, loading, reload };
}

/** Tugma bosilganda bir marta bajariladigan amal (ikki marta bosilmaydi). */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const { fail } = useApp();
  const run = useCallback(
    async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
      if (busy) return;
      setBusy(true);
      try {
        return await fn();
      } catch (e) {
        fail(e);
      } finally {
        setBusy(false);
      }
    },
    [busy, fail],
  );
  return { busy, run };
}

// ---------------------------------------------------------------- ikonkalar
const P: Record<string, ReactNode> = {
  home: <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" />,
  coin: <><circle cx="12" cy="12" r="9" /><path d="M14.6 9.3c-.5-.8-1.5-1.3-2.6-1.3-1.6 0-2.6.8-2.6 2 0 2.6 5.2 1.3 5.2 4 0 1.2-1.1 2.1-2.6 2.1-1.3 0-2.3-.5-2.8-1.5M12 6.3V8m0 8v1.7" /></>,
  ai: <path d="M12 3l1.8 4.6L18 9.5l-4.2 1.8L12 16l-1.8-4.7L6 9.5l4.2-1.9zM19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z" />,
  arena: <path d="M14.5 17.5 3 6V3h3l11.5 11.5M13 19l6-6M16 16l4 4M19 21l2-2M9.5 17.5 21 6V3h-3L6.5 14.5M11 19l-6-6M8 16l-4 4M5 21l-2-2" />,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></>,
  bag: <path d="M6 7h12l1 14H5zM9 7V5a3 3 0 0 1 6 0v2" />,
  back: <path d="M15 18l-6-6 6-6" />,
  right: <path d="M9 18l6-6-6-6" />,
  plus: <><circle cx="12" cy="12" r="9" /><path d="M12 8v8M8 12h8" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></>,
  filter: <path d="M4 6h16M7 12h10M10 18h4" />,
  wallet: <><path d="M3 7a2 2 0 0 1 2-2h13v4" /><path d="M3 7v11a2 2 0 0 0 2 2h15V9H5a2 2 0 0 1-2-2z" /><circle cx="16" cy="14.5" r="1" /></>,
  trophy: <path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0zM7 6H4a3 3 0 0 0 3 4M17 6h3a3 3 0 0 1-3 4" />,
  doc: <path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8zM14 3v5h5M9 13h6M9 17h6" />,
  chat: <path d="M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z" />,
  copy: <><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h10" /></>,
  shield: <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" />,
  rocket: <path d="M5 15c-1.5 1.5-2 5-2 5s3.5-.5 5-2M14 4c3-1 6-1 6-1s0 3-1 6l-7 7-5-5zM9 11l-4 1 2-4h4M13 15l-1 4 4-2v-4" />,
  star: <path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z" />,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  list: <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />,
  globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.7M12 17h.01" /></>,
  gift: <path d="M3 9h18v4H3zM5 13v8h14v-8M12 9v12M12 9S9 3 7 5s5 4 5 4zm0 0s3-6 5-4-5 4-5 4z" />,
  card: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 10h18" /></>,
  out: <path d="M15 12H3M7 8l-4 4 4 4M13 4h6a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-6" />,
  admin: <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4" />,
  upload: <path d="M12 16V4M7 9l5-5 5 5M4 20h16" />,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></>,
  play: <><rect x="3" y="5" width="18" height="14" rx="3" /><path d="M10 9l5 3-5 3z" /></>,
  grid: <path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" />,
  bolt: <path d="M13 2 4 14h7l-1 8 9-12h-7z" />,
  bell: <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0" />,
  lock: <><rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  check: <path d="M5 12l5 5L20 7" />,
  send: <path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" />,
  box: <><path d="M21 8 12 3 3 8v8l9 5 9-5z" /><path d="m3 8 9 5 9-5M12 13v8" /></>,
  users: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.8c2 .7 3.2 2.4 3.6 5.2" /></>,
  more: <><circle cx="5" cy="12" r="1.6" /><circle cx="12" cy="12" r="1.6" /><circle cx="19" cy="12" r="1.6" /></>,
  in: <path d="M12 4v11M7 10.5l5 5 5-5M4 19.5h16" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  mega: <path d="M3 10.5v3a1 1 0 0 0 1 1h2l5 4V5.5l-5 4H4a1 1 0 0 0-1 1zM15.5 8.5a4.5 4.5 0 0 1 0 7M18.5 6a8 8 0 0 1 0 12" />,
  ticket: <path d="M3 8.5V6a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v2.5a3 3 0 0 0 0 6V17a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-2.5a3 3 0 0 0 0-6zM14 5v13" />,
  flag: <path d="M5 21V4M5 4h11l-2 4 2 4H5" />,
  refresh: <path d="M20 11a8 8 0 0 0-14.6-4.5L4 8M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5L20 16M20 20v-4h-4" />,
  chart: <path d="M4 20V10M10 20V4M16 20v-7M21 20H3" />,
  brain: <path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 6 1V5a2 2 0 0 0-3-1zM15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-6 1" />,
  userplus: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5M19 8v6M16 11h6" /></>,
  up: <path d="M6 15l6-6 6 6" />,
  down: <path d="M6 9l6 6 6-6" />,
  alert: <path d="M12 3 2 20h20zM12 10v4.5M12 17.5v.01" />,
  link: <path d="M10 14a4.5 4.5 0 0 0 6.4 0l3.2-3.2a4.5 4.5 0 0 0-6.4-6.4L12 5.6M14 10a4.5 4.5 0 0 0-6.4 0l-3.2 3.2a4.5 4.5 0 0 0 6.4 6.4l1.2-1.2" />,
  gem: <path d="M6 3h12l3.5 5.5L12 21 2.5 8.5zM2.5 8.5h19M9 3l3 5.5L15 3M12 8.5V21" />,
};

export function Icon({ name, size = 20, className = "" }: { name: keyof typeof P | string; size?: number; className?: string }) {
  return (
    <svg className={"ico " + className} style={{ width: size, height: size }} viewBox="0 0 24 24" aria-hidden="true">
      {P[name]}
    </svg>
  );
}

// ---------------------------------------------------------------- tuzilma
export function BalancePill() {
  const { me } = useApp();
  const nav = useNavigate();
  return (
    <button className="balpill" style={{ border: "1px solid var(--line)" }} onClick={() => nav("/wallet")} aria-label={t("Hamyon")}>
      <span className="dot" />
      <span className="b mono" style={{ fontSize: 13 }}>{me ? money(me.balance) : "—"}</span>
      <span className="y" style={{ display: "flex" }}><Icon name="plus" size={18} /></span>
    </button>
  );
}

/** Ichki sahifa sarlavhasi. Telegram'ning tizim «Orqaga» tugmasi ham ulanadi. */
// ---------------------------------------------------------------- belgilar (Art)
// Bo'lim/tugma belgilari — botning o'z ranglarida: sariq (asosiy) va to'q fon.
const ART_ICON: Record<string, string> = { market: "grid", rent: "bag", boost: "bolt", tg: "send", top: "trophy", partner: "play", sell: "doc" };

export function Art({ name, size = 40, radius, solid = false }: { name: string; size?: number; radius?: number; solid?: boolean }) {
  return (
    <span className={"art" + (solid ? " solid" : "")} style={{ width: size, height: size, borderRadius: radius ?? size * 0.3 }}>
      <Icon name={ART_ICON[name] ?? name} size={Math.round(size * 0.5)} />
    </span>
  );
}

export function Header({ title, sub, right, back = true, icon }: { title: string; sub?: string; right?: ReactNode; back?: boolean; icon?: string }) {
  const nav = useNavigate();
  const goBack = useCallback(() => (window.history.length > 1 ? nav(-1) : nav("/")), [nav]);
  useEffect(() => {
    if (!tg || !back) return;
    tg.BackButton.show();
    tg.BackButton.onClick(goBack);
    return () => {
      tg?.BackButton.offClick(goBack);
      tg?.BackButton.hide();
    };
  }, [back, goBack]);
  return (
    <div className="hd">
      <div className="row grow">
        {back && !tg && (
          <button className="iconbtn" onClick={goBack} aria-label={t("Orqaga")}>
            <Icon name="back" />
          </button>
        )}
        {icon && (!back || tg) && <Art name={icon} size={38} radius={11} solid />}
        <div className="grow">
          <div className="hd-title ell">{title}</div>
          {sub && <div className="mut xs ell">{sub}</div>}
        </div>
      </div>
      {right ?? <BalancePill />}
    </div>
  );
}

const TRADE = ["/market", "/rent", "/boost", "/tg"];
const TRADE_ITEMS = [
  { to: "/market", icon: "grid", label: "Account savdo", f: "market" },
  { to: "/rent", icon: "bag", label: "Account ijara", f: "rent" },
  { to: "/boost", icon: "bolt", label: "Boost xizmati", f: "boost" },
  { to: "/tg", icon: "send", label: "TG xizmatlar", f: "tg" },
];

export function BottomNav() {
  const { pathname } = useLocation();
  const { me } = useApp();
  const on = (f: string) => !!me?.features?.[f];
  const trade = TRADE.some((p) => pathname === p || pathname.startsWith(p + "/"));
  const tradeItems = TRADE_ITEMS.filter((i) => on(i.f));
  if (trade && tradeItems.length) {
    return (
      <nav className="nav">
        <div className="nav-in">
          <NavLink to="/" className="hb" onClick={() => haptic()}>
            <Icon name="back" />
            {t("Bosh sahifa")}
          </NavLink>
          <div className="pill trade">
            {tradeItems.map((i) => (
              <NavLink key={i.to} to={i.to} end className={({ isActive }) => "ni" + (isActive ? " on" : "")} onClick={() => haptic()}>
                <Icon name={i.icon} />
                {t(i.label)}
              </NavLink>
            ))}
          </div>
        </div>
      </nav>
    );
  }
  const items = [
    { to: "/", icon: "home", label: t("Bosh sahifa") },
    on("partner") ? { to: "/partner", icon: "coin", label: t("Daromad") } : { to: "/wallet", icon: "wallet", label: t("Hamyon") },
    on("arena") ? { to: "/arena", icon: "arena", label: t("Arena") } : { to: "/history", icon: "clock", label: t("Tarix") },
    { to: "/settings", icon: "settings", label: t("Sozlamalar") },
  ];
  const first = tradeItems.length === TRADE_ITEMS.length ? tradeItems[0] : { to: "/soon" }; // biror bo'lim yopiq bo'lsa — «Tez kunda» ro'yxati
  return (
    <nav className="nav">
      <div className="nav-in">
        <div className="pill">
          {items.map((i) => (
            <NavLink key={i.to} to={i.to} end className={({ isActive }) => "ni" + (isActive ? " on" : "")} onClick={() => haptic()}>
              <Icon name={i.icon} />
              {i.label}
            </NavLink>
          ))}
        </div>
        {first && (
          <NavLink to={first.to} className="sv" onClick={() => haptic()}>
            <Icon name="bag" />
            {t("Savdo")}
          </NavLink>
        )}
      </div>
    </nav>
  );
}

export function BottomBar({ children, aboveNav }: { children: ReactNode; aboveNav?: boolean }) {
  return (
    <div className={"bottombar" + (aboveNav ? " abovenav" : "")}>
      <div className="bottombar-in">{children}</div>
    </div>
  );
}

export function Sheet({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  if (!open) return null;
  return (
    <div className="sheet-bg" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------- kichik komponentlar
export const Spinner = () => <div className="spinner" />;

export function Empty({ icon = "🗂", text, children }: { icon?: string; text: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <div className="em">{icon}</div>
      <div>{text}</div>
      {children && <div style={{ marginTop: 14 }}>{children}</div>}
    </div>
  );
}

export function Loadable<T>({ state, children }: { state: { data: T | null; error: string | null; loading: boolean; reload: () => void }; children: (d: T) => ReactNode }) {
  if (state.data) return <>{children(state.data)}</>;
  if (state.error)
    return (
      <Empty icon="⚠️" text={state.error}>
        <button className="btn small ghost" onClick={state.reload}>{t("Qayta urinish")}</button>
      </Empty>
    );
  return <Spinner />;
}

/** Bo'lim yoqilganmi (admin Sozlamalar → «Bo'limlar»). Admin o'zi hamma bo'limni to'g'ridan-to'g'ri ocha oladi. */
export function useFeature(name: string): boolean {
  const { me } = useApp();
  return !!me?.features?.[name];
}

/** O'yin belgisi: logo bo'lsa rasm, bo'lmasa bosh harflar. */
export function GameTile({ name, logo, slug, size = 64, radius = 16 }: { name: string; logo?: string | null; slug?: string; size?: number; radius?: number }) {
  // Admin yuklagan rasm > rasmiy ikonka > provayder logotipi
  const img = (logo && logo.includes("/game-image/") ? logo : undefined) || (slug ? GAME_IMG[slug] : undefined) || logo || undefined;
  if (img) return <img src={img} alt={name} loading="lazy" style={{ width: size, height: size, borderRadius: radius, objectFit: "cover", display: "block" }} />;
  const st = slug ? GAME_STYLE[slug] : undefined;
  const hue = [...name].reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
  const bg = st ? `linear-gradient(140deg, ${st[0]}, ${st[1]})` : `linear-gradient(135deg, hsl(${hue} 55% 38%), hsl(${(hue + 40) % 360} 60% 24%))`;
  const ini = name.split(/[\s-]+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return (
    <div aria-label={name} style={{ width: size, height: size, borderRadius: radius, position: "relative", overflow: "hidden", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "#fff", background: bg, boxShadow: "inset 0 0 0 1px rgba(255,255,255,.12)" }}>
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 30% 20%, rgba(255,255,255,.28), transparent 55%)" }} />
      <span style={{ fontSize: size / (st ? 2.4 : 3), lineHeight: 1, position: "relative" }}>{st ? st[2] : ini}</span>
      {st && size >= 56 && <span style={{ fontSize: Math.max(9, size / 8), fontWeight: 800, letterSpacing: ".04em", marginTop: size / 16, position: "relative", textShadow: "0 1px 2px rgba(0,0,0,.4)" }}>{ini}</span>}
    </div>
  );
}

export function GameLogo({ game, size = 44 }: { game: string; size?: number }) {
  if (GAME_IMG[game]) return <img className="glogo" src={GAME_IMG[game]} alt={game === "ML" ? "Mobile Legends" : "Magic Chess"} style={{ width: size, height: size, objectFit: "cover" }} />;
  return <div className={"glogo " + game} style={{ width: size, height: size, fontSize: size / 3 }}>{game === "UZS" ? "₴" : game}</div>;
}

export function Seg<T extends string>({ value, options, onChange }: { value: T; options: { v: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div className="seg">
      {options.map((o) => (
        <button key={o.v} className={value === o.v ? "on" : ""} onClick={() => { haptic(); onChange(o.v); }}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Chips<T extends string | number>({ value, options, onChange, wrap }: { value: T | null; options: { v: T; label: string }[]; onChange: (v: T) => void; wrap?: boolean }) {
  return (
    <div className={"chips" + (wrap ? " wrap" : "")}>
      {options.map((o) => (
        <button key={String(o.v)} className={"chip" + (value === o.v ? " on" : "")} onClick={() => { haptic(); onChange(o.v); }}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
    </div>
  );
}

export function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return <button className={"toggle" + (on ? " on" : "")} role="switch" aria-checked={on} onClick={() => onChange(!on)} />;
}

const STATUS: Record<string, [string, string]> = {
  processing: ["Bajarilmoqda", "y"], done: ["Bajarildi", "g"], completed: ["Yakunlandi", "g"], refunded: ["Qaytarildi", "r"],
  review: ["Tekshirilmoqda", "y"], paid: ["To'langan", "b"], holding: ["Himoya muddati", "y"], delivered: ["Ma'lumot berildi", "b"], disputed: ["Nizo", "r"],
  pending: ["Kutilmoqda", "y"], rejected: ["Rad etildi", "r"], expired: ["Muddati o'tdi", "m"], cancelled: ["Bekor qilindi", "m"],
  moderation: ["Moderatsiya", "y"], active: ["Faol", "g"], reserved: ["Band", "b"], sold: ["Sotilgan", "m"], closed: ["Yopilgan", "m"],
  searching: ["Booster qidirilmoqda", "y"], accepted: ["Booster topildi", "b"], in_progress: ["Jarayonda", "b"], finished: ["Tasdiqlang", "y"],
  open: ["Ochiq", "g"], running: ["Davom etmoqda", "b"],
  rent_active: ["Ijarada", "b"], rent_ended: ["Tekshiruvda", "y"], rent_completed: ["Yakunlandi", "g"], rent_disputed: ["Nizo", "r"],
  rent_refunded: ["Qaytarildi", "r"],
};

export function Status({ s }: { s: string }) {
  const [label, color] = STATUS[s] ?? [s, "m"];
  return <span className={"badge " + color}>{t(label)}</span>;
}

export function Copy({ value, label }: { value: string; label?: string }) {
  const { toast } = useApp();
  return (
    <button
      className="copy"
      style={{ width: "100%", color: "inherit", textAlign: "left" }}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value.replace(/\s/g, ""));
          toast(t("Nusxa olindi"), "ok");
        } catch {
          toast(value);
        }
      }}
    >
      <div>
        {label && <div className="mut xs">{label}</div>}
        <div className="mono bb" style={{ fontSize: value.length > 24 ? 13 : 18, letterSpacing: 0.5, wordBreak: "break-all" }}>{value}</div>
      </div>
      <span className="y"><Icon name="copy" /></span>
    </button>
  );
}

export function Row({ icon, title, sub, right, onClick }: { icon?: ReactNode; title: ReactNode; sub?: ReactNode; right?: ReactNode; onClick?: () => void }) {
  return (
    <div className="listrow" onClick={onClick} style={onClick ? { cursor: "pointer" } : undefined}>
      {icon && (typeof icon === "string" ? <Art name={icon} size={36} radius={10} /> : <span className="rowico">{icon}</span>)}
      <div className="grow">
        <div className="b ell">{title}</div>
        {sub && <div className="mut sm ell">{sub}</div>}
      </div>
      {right ?? (onClick ? <span className="mut"><Icon name="right" size={18} /></span> : null)}
    </div>
  );
}

/** Raqam kiritish: bo'sh joy bilan formatlaydi. */
export function MoneyInput({ value, onChange, placeholder }: { value: number | ""; onChange: (v: number | "") => void; placeholder?: string }) {
  return (
    <input
      className="input mono"
      inputMode="numeric"
      placeholder={placeholder}
      value={value === "" ? "" : money(value)}
      onChange={(e) => {
        const d = e.target.value.replace(/\D/g, "").slice(0, 10);
        onChange(d ? Number(d) : "");
      }}
    />
  );
}

/** «Identifikatsiya majburiy» banneri (Account savdo / ijara). */
export function KycBanner({ area }: { area: "marketplace" | "rental" | "withdraw" }) {
  const { me } = useApp();
  const nav = useNavigate();
  if (!me || !me.kyc_required?.[area] || me.kyc_status === "verified") return null;
  const pending = me.kyc_status === "pending";
  return (
    <div className="card row kyc-card" style={{ padding: "10px 12px" }}>
      <span className="y"><Icon name="lock" size={18} /></span>
      <div className="grow">
        <div className="y b sm">{pending ? t("Identifikatsiya tekshirilmoqda") : t("Identifikatsiya majburiy")}</div>
        <div className="mut xs">{area === "marketplace" ? t("Sotish va xarid uchun shaxsingizni tasdiqlang") : area === "rental" ? t("Ijara uchun shaxsingizni tasdiqlang") : t("Pul yechish uchun shaxsingizni tasdiqlang")}</div>
      </div>
      {!pending && <button className="btn small" onClick={() => nav("/kyc")}>{t("O'tish")} ›</button>}
    </div>
  );
}

/** Turnir homiysi (brend): logo, nom, matn va havola. */
export function SponsorLine({ s }: { s?: { name: string; logo: string; url: string; text: string } | null }) {
  if (!s) return null;
  const open = (e: React.MouseEvent) => { e.stopPropagation(); if (s.url) openExternal(s.url); };
  return (
    <div className="sponsor" onClick={open} role={s.url ? "link" : undefined}>
      {s.logo ? <img src={s.logo} alt="" /> : <span className="sponsor-ic">🤝</span>}
      <div className="grow" style={{ minWidth: 0 }}>
        <div className="mut xs">{t("Homiy")}</div>
        <div className="b ell">{s.name}</div>
        {s.text && <div className="mut xs ell">{s.text}</div>}
      </div>
      {s.url && <Icon name="right" size={16} className="mut" />}
    </div>
  );
}

/** Premium bo'lim admin tomonidan yopilmaganmi (Sozlamalar → bo'limlar). */
export function useSection(k: "shop" | "plus" | "savings" | "stream" | "pro" | "split" | "duel" | "vay"): boolean {
  const { me } = useApp();
  return me?.sections?.[k] !== false;
}

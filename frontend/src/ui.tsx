import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { ApiError, type Me } from "./api";
import { t } from "./i18n";
import mcImg from "./assets/mc.webp";
import mlImg from "./assets/ml.webp";
import { haptic, tg } from "./tg";

export const GAME_IMG: Record<string, string> = { ML: mlImg, MC: mcImg };

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
  if (e instanceof ApiError) return e.message;
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
  send: <path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" />,
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
export function Header({ title, sub, right, back = true }: { title: string; sub?: string; right?: ReactNode; back?: boolean }) {
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
        <div className="grow">
          <div className="hd-title ell">{title}</div>
          {sub && <div className="mut xs ell">{sub}</div>}
        </div>
      </div>
      {right ?? <BalancePill />}
    </div>
  );
}

export function BottomNav() {
  const { pathname } = useLocation();
  const items = [
    { to: "/", icon: "home", label: t("Bosh sahifa") },
    { to: "/tg", icon: "star", label: t("TG xizmat") },
    { to: "/arena", icon: "arena", label: t("Arena") },
    { to: "/settings", icon: "settings", label: t("Sozlamalar") },
  ];
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
        <NavLink to="/market" className={"sv" + (pathname.startsWith("/market") ? " on" : "")} onClick={() => haptic()}>
          <Icon name="bag" />
          {t("Savdo")}
        </NavLink>
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
  review: ["Tekshirilmoqda", "y"], paid: ["To'langan", "b"], delivered: ["Ma'lumot berildi", "b"], disputed: ["Nizo", "r"],
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
      {icon}
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

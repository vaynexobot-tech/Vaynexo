import { useEffect, useState, type ReactNode } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, type Deal, type ListingCard, type ListingFull } from "../api";
import { t } from "../i18n";
import { haptic } from "../tg";
import {
  BottomBar, BottomNav, Chips, Empty, Field, GAME_IMG, GameLogo, Header, Icon, Loadable, money, MoneyInput, Seg, Sheet, som, Spinner, Status,
  useAction, useApp, useLoad,
} from "../ui";

const LEVELS = ["Amateur", "Junior", "Senior", "Expert", "Renowned", "Exalted", "Mega", "World"];
type Cat = "all" | "fav" | "mythic" | "legend" | "epic" | "cheap" | "skins";

interface Filters {
  game: "" | "ML" | "MC";
  level: string;
  min_price: number | "";
  max_price: number | "";
  min_skins: number | "";
  sort: "new" | "cheap" | "skins" | "expensive";
}
const EMPTY: Filters = { game: "", level: "", min_price: "", max_price: "", min_skins: "", sort: "new" };

export function Market() {
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const [q, setQ] = useState(sp.get("q") ?? "");
  const [query, setQuery] = useState(sp.get("q") ?? "");
  const [cat, setCat] = useState<Cat>("all");
  const [f, setF] = useState<Filters>(EMPTY);
  const [showFilter, setShowFilter] = useState(sp.get("filter") === "1");
  const [items, setItems] = useState<ListingCard[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [total, setTotal] = useState(0);
  const { fail } = useApp();
  const toggleFav = async (x: ListingCard) => {
    haptic();
    setItems((p) => p && (cat === "fav" ? p.filter((i) => i.id !== x.id) : p.map((i) => (i.id === x.id ? { ...i, is_fav: !i.is_fav } : i))));
    try {
      await api.post(`/listings/${x.id}/favorite`);
    } catch (e) {
      fail(e);
    }
  };

  const params = (offset: number) => {
    const p = new URLSearchParams({ sort: f.sort, offset: String(offset), limit: "20" });
    if (query) p.set("q", query);
    if (f.game) p.set("game", f.game);
    if (f.level) p.set("level", f.level);
    let min = f.min_price, max = f.max_price;
    if (cat === "cheap") max = 500_000;
    if (cat === "mythic") p.set("rank", "Mythic");
    if (cat === "legend") p.set("rank", "Legend");
    if (cat === "epic") p.set("rank", "Epic");
    if (cat === "skins") p.set("min_skins", "100");
    if (cat === "fav") p.set("favorites", "true");
    if (min) p.set("min_price", String(min));
    if (max) p.set("max_price", String(max));
    if (f.min_skins) p.set("min_skins", String(f.min_skins));
    return p.toString();
  };

  const load = async (offset = 0) => {
    try {
      if (offset) setLoadingMore(true);
      const r = await api.get<{ items: ListingCard[]; has_more: boolean; total: number }>("/listings?" + params(offset));
      setItems((prev) => (offset ? [...(prev ?? []), ...r.items] : r.items));
      setHasMore(r.has_more);
      setTotal(r.total);
    } catch (e) {
      fail(e);
      setItems((p) => p ?? []);
    } finally {
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    setItems(null);
    load(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, cat, f]);

  return (
    <>
      <Header title={t("Account savdo")} sub={t("Tayyor akkauntlarni sotib oling")} back={false} icon="grid" />
      <div className="page">
        <div className="grid2">
          <button className="btn small" onClick={() => nav("/sell")}>+ {t("E'lon joylash")}</button>
          <button className="btn small ghost" onClick={() => nav("/deals")}>{t("Mening bitimlarim")}</button>
        </div>
        <form className="row" onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()); }}>
          <div className="row grow input" style={{ padding: "0 6px 0 14px" }}>
            <span className="mut"><Icon name="search" /></span>
            <input className="grow" style={{ background: "none", border: 0, outline: "none", height: "100%" }} placeholder={t("Qidirish: Mythic, skin...")} value={q} onChange={(e) => setQ(e.target.value)} onBlur={() => setQuery(q.trim())} />
          </div>
          <button type="button" className="iconbtn" style={{ width: 48, height: 48 }} onClick={() => setShowFilter(true)} aria-label={t("Filtr")}><Icon name="filter" /></button>
        </form>
        <Chips value={cat} onChange={setCat} options={[
          { v: "all", label: t("Hammasi") }, { v: "fav", label: "❤️ " + t("Sevimlilar") }, { v: "mythic", label: "Mythic" },
          { v: "legend", label: "Legend" }, { v: "epic", label: "Epic" }, { v: "cheap", label: t("500k gacha") }, { v: "skins", label: t("100+ skin") },
        ]} />
        <div className="row between sm">
          <span className="mut">{t("{n} ta e'lon", { n: total })}</span>
          <select className="sortsel" aria-label={t("Saralash")} value={f.sort} onChange={(e) => setF({ ...f, sort: e.target.value as Filters["sort"] })}>
            <option value="new">{t("Eng yangi")}</option>
            <option value="cheap">{t("Eng arzon")}</option>
            <option value="expensive">{t("Eng qimmat")}</option>
            <option value="skins">{t("Eng ko'p skin")}</option>
          </select>
        </div>

        {items === null ? <Spinner /> : items.length === 0 ? (
          <Empty icon={cat === "fav" ? "❤️" : "🔍"} text={cat === "fav" ? t("Sevimlilar bo'sh. Yoqqan e'londagi ❤️ ni bosing") : t("Hech narsa topilmadi")}>
            <button className="btn small ghost" onClick={() => { setF(EMPTY); setCat("all"); setQ(""); setQuery(""); }}>{t("Filtrni tozalash")}</button>
          </Empty>
        ) : (
          <>
            <div className="mgrid">
              {items.map((x) => <GridCard key={x.id} x={x} onClick={() => nav(`/listing/${x.id}`)} onFav={() => toggleFav(x)} />)}
            </div>
            {hasMore && <button className="btn ghost full" disabled={loadingMore} onClick={() => load(items.length)}>{loadingMore ? "..." : t("Ko'proq ko'rsatish")}</button>}
          </>
        )}
      </div>
      <FilterSheet open={showFilter} value={f} onClose={() => setShowFilter(false)} onApply={(v) => { setF(v); setShowFilter(false); }} />
      <BottomNav />
    </>
  );
}

const isNew = (iso: string) => Date.now() - Date.parse(iso) < 24 * 3600 * 1000;

export function GridCard({ x, onClick, onFav }: { x: ListingCard; onClick: () => void; onFav: () => void }) {
  return (
    <div className={"gcard" + (x.vip ? " vip" : "")} onClick={onClick}>
      <div className="gcov">
        <img src={x.cover ?? GAME_IMG[x.game]} alt="" loading="lazy" />
        {x.vip ? <span className="gflag vip">VIP</span> : isNew(x.created_at) ? <span className="gflag new">{t("YANGI")}</span> : null}
        <button className={"gheart" + (x.is_fav ? " on" : "")} aria-label={t("Sevimlilar")} onClick={(e) => { e.stopPropagation(); onFav(); }}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" /></svg>
        </button>
        {x.rank && <span className="grank">{x.rank.toUpperCase()}</span>}
      </div>
      <div className="gbody">
        <div className="b ell sm">{x.title}</div>
        <div className="mut xs ell">{x.skins} skin{x.heroes ? ` · ${x.heroes} ${t("qahr.")}` : ""}{x.game === "MC" ? " · Magic Chess" : ""}</div>
        <div className="y bb mono" style={{ fontSize: 14 }}>{money(x.price)} <span className="mut xs">{t("so'm")}</span></div>
        <div className="row between xs"><span className="mut">{x.seller_rating ? `★ ${x.seller_rating}` : t("Yangi sotuvchi")}</span><span className="g">🔒 {t("Garant")}</span></div>
      </div>
    </div>
  );
}

export function ListingRow({ x, onClick, extra }: { x: ListingCard; onClick?: () => void; extra?: ReactNode }) {
  return (
    <div className="card click" onClick={onClick} style={{ padding: 10 }}>
      <div className="row" style={{ alignItems: "stretch", gap: 12 }}>
        <img className="thumb" src={x.cover ?? GAME_IMG[x.game]} alt="" loading="lazy" />
        <div className="grow col" style={{ gap: 3 }}>
          <div className="row" style={{ gap: 6 }}>
            {x.rank && <span className="badge y">{x.rank.toUpperCase()}</span>}
            {x.status !== "active" && <Status s={x.status} />}
          </div>
          <div className="b ell">{x.title}</div>
          <div className="mut xs ell">{x.game === "ML" ? "Mobile Legends" : "Magic Chess"} · {x.skins} skin{x.collection_level ? " · " + x.collection_level : ""}</div>
          <div className="y bb mono">{som(x.price)}</div>
        </div>
      </div>
      {extra}
    </div>
  );
}

function FilterSheet({ open, value, onClose, onApply }: { open: boolean; value: Filters; onClose: () => void; onApply: (f: Filters) => void }) {
  const [f, setF] = useState(value);
  useEffect(() => setF(value), [value, open]);
  const set = <K extends keyof Filters>(k: K, v: Filters[K]) => setF((p) => ({ ...p, [k]: v }));
  return (
    <Sheet open={open} onClose={onClose}>
      <div className="row between"><div className="sec-title">{t("Filtr")}</div><button className="chip" onClick={() => setF(EMPTY)}>{t("Tozalash")}</button></div>
      <Field label={t("O'yin")}>
        <Seg value={f.game} onChange={(v) => set("game", v)} options={[{ v: "", label: t("Hammasi") }, { v: "ML", label: "Mobile Legends" }, { v: "MC", label: "Magic Chess" }]} />
      </Field>
      <Field label={t("Kolleksiya darajasi")}>
        <Chips wrap value={f.level} onChange={(v) => set("level", f.level === v ? "" : v)} options={LEVELS.map((l) => ({ v: l, label: l }))} />
      </Field>
      <Field label={t("Narx (so'm)")}>
        <div className="row"><MoneyInput value={f.min_price} onChange={(v) => set("min_price", v)} placeholder={t("dan")} /><MoneyInput value={f.max_price} onChange={(v) => set("max_price", v)} placeholder={t("gacha")} /></div>
      </Field>
      <Field label={t("Skinlar soni")}>
        <Chips value={f.min_skins} onChange={(v) => set("min_skins", f.min_skins === v ? "" : v)} options={[10, 50, 100, 200].map((v) => ({ v, label: `${v}+` }))} />
      </Field>
      <Field label={t("Saralash")}>
        <Chips wrap value={f.sort} onChange={(v) => set("sort", v)} options={[
          { v: "new", label: t("Eng yangi") }, { v: "cheap", label: t("Eng arzon") }, { v: "expensive", label: t("Eng qimmat") }, { v: "skins", label: t("Eng ko'p skin") },
        ]} />
      </Field>
      <button className="btn full" onClick={() => onApply(f)}>{t("Natijalarni ko'rsatish")}</button>
    </Sheet>
  );
}

export function ListingDetail() {
  const id = useParams().id;
  const nav = useNavigate();
  const st = useLoad(() => api.get<ListingFull>(`/listings/${id}`), [id]);
  const [buyOpen, setBuyOpen] = useState(false);
  const { busy, run } = useAction();
  const toggleFav = (l: ListingFull) => run(async () => {
    haptic();
    const r = await api.post<{ is_fav: boolean }>(`/listings/${l.id}/favorite`);
    st.setData({ ...l, is_fav: r.is_fav });
  });

  const openChat = (l: ListingFull) =>
    run(async () => {
      const c = l.chat_id ? { id: l.chat_id } : await api.post<{ id: number }>(`/listings/${l.id}/chat`);
      nav(`/chat/${c.id}`);
    });

  return (
    <>
      <Header title={t("Akkaunt tafsilotlari")} sub={t("Account savdo")} />
      <Loadable state={st}>
        {(l) => {
          return (
            <>
              <div className="page">
                {l.media.length ? (
                  <div className="gallery">
                    {l.media.map((m, i) => m.type === "video"
                      ? <video key={i} src={m.url} controls playsInline preload="metadata" />
                      : <img key={i} src={m.url} alt="" />)}
                  </div>
                ) : <img className="cover" src={GAME_IMG[l.game]} alt="" style={{ objectPosition: "center 25%" }} />}
                <div className="row" style={{ gap: 6 }}>
                  {l.vip && <span className="badge" style={{ background: "#ffb020", color: "#111" }}>VIP</span>}
                  {l.rank && <span className="badge y">{l.rank.toUpperCase()}</span>}
                  <span className="badge m mono">#VX-{l.id}</span>
                  {!l.is_mine && (
                    <button className={"gheart" + (l.is_fav ? " on" : "")} style={{ position: "static", marginLeft: "auto", background: "var(--card)", border: "1px solid var(--line)" }}
                      aria-label={t("Sevimlilar")} disabled={busy} onClick={() => toggleFav(l)}>
                      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" /></svg>
                    </button>
                  )}
                  {l.status !== "active" && <Status s={l.status} />}
                </div>
                <div>
                  <div className="hf bb" style={{ fontSize: 20 }}>{l.title}</div>
                  <div className="mut sm">{l.game === "ML" ? "Mobile Legends" : "Magic Chess"}{l.server ? ` · ${t("Server")}: ${l.server}` : ""}</div>
                </div>
                <div className="y bb mono" style={{ fontSize: 24 }}>{som(l.price)}</div>
                {l.collection_level ? <CollectionCard level={l.collection_level} skins={l.skins} heroes={l.heroes} /> : (
                  <div className="card">
                    <div className="kv"><span>{t("Skinlar")}</span><span>{l.skins}</span></div>
                    {l.heroes > 0 && <div className="kv"><span>{t("Qahramonlar")}</span><span>{l.heroes}</span></div>}
                  </div>
                )}
                <div className="card row">
                  <div className="seller-ava">{(l.seller.username || l.seller.name || "?")[0].toUpperCase()}</div>
                  <div className="grow">
                    <div className="b">{l.seller.username ? l.seller.username : l.seller.name}</div>
                    <div className="mut xs">
                      {l.seller.rating ? <span className="y">★ {l.seller.rating}</span> : t("Hali baho yo'q")} · {t("{n} ta savdo", { n: l.seller_stats?.sales ?? 0 })}
                    </div>
                  </div>
                  {(l.seller_verified || (l.seller_stats?.sales ?? 0) >= 5) && <span className="pill-b g">✓ {t("Ishonchli")}</span>}
                </div>
                {l.description && <div className="card"><div className="b" style={{ marginBottom: 6 }}>{t("Tavsif")}</div><div className="pre sm" style={{ color: "#d6dbe8" }}>{l.description}</div></div>}
                <div className="card col">
                  <div className="b">{t("Xavfsiz savdo")}</div>
                  {[t("Pul escrow'da saqlanadi — akkaunt topshirilgach sotuvchiga o'tadi"), t("Login va parol faqat to'lovdan keyin beriladi"),
                    t("Muammo bo'lsa nizo ochasiz — admin hal qiladi")].map((x) => (
                    <div key={x} className="row sm" style={{ alignItems: "flex-start" }}><span className="g"><Icon name="check" size={16} /></span><span>{x}</span></div>
                  ))}
                  <div className="mut xs">{t("Ko'rishlar")}: {l.views}</div>
                </div>
              </div>
              <BottomBar>
                {l.is_mine ? (
                  <button className="btn ghost full" onClick={() => nav(`/sell/${l.id}`)}>{t("Tahrirlash")}</button>
                ) : (
                  <>
                    <button className="btn ghost sq" disabled={busy} onClick={() => openChat(l)} aria-label={t("Chat")}><Icon name="chat" /></button>
                    <button className="btn grow" disabled={l.status !== "active"} onClick={() => setBuyOpen(true)}>{l.status === "active" ? t("Sotib olish") : t("Sotilgan")}</button>
                  </>
                )}
              </BottomBar>
              <BuyMethodSheet open={buyOpen} l={l} busy={busy} onClose={() => setBuyOpen(false)}
                onChat={() => { setBuyOpen(false); openChat(l); }}
                onGarant={() => { setBuyOpen(false); nav(`/pay/listing/${l.id}`); }} />
            </>
          );
        }}
      </Loadable>
    </>
  );
}

function CollectionCard({ level, skins, heroes }: { level: string; skins: number; heroes: number }) {
  const name = level.replace(" Collector", "");
  const idx = LEVELS.indexOf(name);
  const next = idx >= 0 && idx < LEVELS.length - 1 ? LEVELS[idx + 1] + " Collector" : null;
  const pct = idx >= 0 ? Math.round(((idx + 1) / LEVELS.length) * 100) : 50;
  return (
    <div className="card col coll-card">
      <div className="row">
        <div className="hd-ico" style={{ width: 40, height: 40, background: "rgba(255,214,10,.15)", color: "var(--y)" }}><Icon name="trophy" /></div>
        <div className="grow">
          <div className="mut xs">{t("Kolleksiya darajasi")}</div>
          <div className="y bb" style={{ fontSize: 17 }}>{level}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="hf bb" style={{ fontSize: 22 }}>{skins}</div>
          <div className="mut xs">{t("jami skin")}</div>
        </div>
      </div>
      <div className="row between mut xs">
        <span>{heroes > 0 ? t("Qahramonlar: {n}", { n: heroes }) : ""}</span>
        <span>{next ? t("Keyingisi: {l}", { l: next }) : t("Eng yuqori daraja")}</span>
      </div>
      <div className="progress"><i style={{ width: pct + "%" }} /></div>
    </div>
  );
}

/** «Qanday sotib olasiz?» — chat yoki garant orqali. */
function BuyMethodSheet({ open, l, busy, onClose, onChat, onGarant }: {
  open: boolean; l: ListingFull; busy: boolean; onClose: () => void; onChat: () => void; onGarant: () => void;
}) {
  const nav = useNavigate();
  const [agree, setAgree] = useState(false);
  return (
    <Sheet open={open} onClose={onClose}>
      <div className="row between" style={{ marginBottom: 10 }}>
        <div><div className="sec-title" style={{ margin: 0 }}>{t("Qanday sotib olasiz?")}</div><div className="mut xs">{t("O'zingizga qulay usulni tanlang")}</div></div>
        <button className="iconbtn" onClick={onClose} aria-label={t("Yopish")}>✕</button>
      </div>
      <div className="col">
        <div className="card row tight">
          <GameLogo game={l.game} size={44} />
          <div className="grow" style={{ minWidth: 0 }}><div className="b ell">{l.title}</div><div className="mut xs">{l.game === "ML" ? "Mobile Legends" : "Magic Chess"} · {l.skins} skin</div></div>
          <div className="y mono bb">{money(l.price)}</div>
        </div>
        <div className="card col">
          <div className="row"><span className="rowico"><Icon name="chat" /></span><div><div className="b">{t("Sotuvchi bilan chat")}</div><div className="mut xs">{t("Savol bering, narxni kelishing")}</div></div></div>
          <div className="row sm"><span className="g"><Icon name="check" size={14} /></span>{t("Akkaunt haqida batafsil so'rash")}</div>
          <div className="row sm"><span className="g"><Icon name="check" size={14} /></span>{t("Narx bo'yicha kelishish")}</div>
          <button className="btn ghost full" disabled={busy} onClick={onChat}><Icon name="chat" /> {t("Chatni ochish")}</button>
        </div>
        <div className="card col" style={{ borderColor: "rgba(255,214,10,.6)" }}>
          <div className="row"><span className="hd-ico" style={{ width: 36, height: 36 }}><Icon name="shield" size={18} /></span>
            <div><div className="b">{t("Garant orqali sotib olish")} <span className="pill-b g" style={{ fontSize: 10, padding: "2px 7px" }}>{t("Xavfsiz")}</span></div><div className="mut xs">{t("Pul kafolatlanadi, akkaunt tekshiriladi")}</div></div></div>
          <div className="row sm"><span className="g"><Icon name="check" size={14} /></span>{t("To'lov qilsangiz, akkaunt ma'lumotlari ochiladi")}</div>
          <div className="row sm"><span className="g"><Icon name="check" size={14} /></span>{t("Tasdiqlaganingizdan so'ng pul sotuvchiga o'tadi")}</div>
          <button className="btn full" disabled={!agree || l.status !== "active"} onClick={onGarant}>{t("Garant bilan davom etish")}</button>
        </div>
        <label className="row sm" style={{ cursor: "pointer" }}>
          <input type="checkbox" className="cbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          <span>{t("Men")} <a className="y" style={{ textDecoration: "underline" }} onClick={(e) => { e.preventDefault(); nav("/legal/terms"); }}>{t("Foydalanuvchi kelishuvi")}</a> {t("bilan tanishdim va unga roziman.")}</span>
        </label>
      </div>
    </Sheet>
  );
}

/** To'lov sahifasi: garant orqali akkaunt xaridi. */
export function PayListing() {
  const id = useParams().id;
  const nav = useNavigate();
  const { me, refreshMe } = useApp();
  const st = useLoad(() => api.get<ListingFull>(`/listings/${id}`), [id]);
  const { busy, run } = useAction();
  return (
    <>
      <Header title={t("To'lov")} sub={t("Xavfsiz savdo · pul kafolatlanadi")} />
      <Loadable state={st}>
        {(l) => {
          const bal = me?.balance ?? 0;
          const short = Math.max(0, l.price - bal);
          return (
            <>
              <div className="page withbar">
                <div className="card row">
                  <GameLogo game={l.game} size={52} />
                  <div className="grow" style={{ minWidth: 0 }}><div className="b ell">{l.title}</div><div className="mut xs">{l.game === "ML" ? "Mobile Legends" : "Magic Chess"}</div><div className="y mono bb">{som(l.price)}</div></div>
                </div>
                <div className="card col">
                  <div className="b">{t("Qanday ishlaydi")}</div>
                  {[[t("To'lov qilasiz"), t("Pul hamyon balansingizdan yechiladi va himoyada saqlanadi")],
                    [t("Akkaunt ma'lumotlari ochiladi"), t("Sotuvchi login va parolni bitim sahifasida yuboradi")],
                    [t("Tekshirib, tasdiqlaysiz"), t("Tasdiqlaganingizdan so'ng pul sotuvchiga o'tkaziladi")]].map(([a, b], i) => (
                    <div key={i} className="row" style={{ alignItems: "flex-start" }}>
                      <span className={"stepnum" + (i === 0 ? " on" : "")}>{i + 1}</span>
                      <div><div className="b sm">{a}</div><div className="mut xs">{b}</div></div>
                    </div>
                  ))}
                </div>
                <div className="card row">
                  <span className="hd-ico" style={{ width: 40, height: 40, background: "rgba(255,214,10,.12)", color: "var(--y)" }}><Icon name="wallet" /></span>
                  <div className="grow"><div className="mut xs mono">{t("HAMYON BALANSI")}</div><div className="bb">{som(bal)}</div></div>
                </div>
                <div className="card">
                  <div className="kv"><span>{t("Akkaunt narxi")}</span><span className="mono">{money(l.price)}</span></div>
                  <div className="kv"><span>{t("Xizmat haqi")}</span><span className="g">{t("Bepul")}</span></div>
                  <div className="kv"><span className="b">{t("Jami")}</span><span className="y bb mono" style={{ fontSize: 18 }}>{som(l.price)}</span></div>
                </div>
                {short > 0 && (
                  <div className="card row" style={{ borderColor: "rgba(255,90,110,.5)", background: "rgba(255,90,110,.06)" }}>
                    <span className="r"><Icon name="help" /></span>
                    <div><div className="r b">{t("Mablag' yetarli emas")}</div><div className="mut xs">{t("Yetishmaydi: {s}. Hamyonni to'ldiring.", { s: som(short) })}</div></div>
                  </div>
                )}
              </div>
              <BottomBar>
                {short > 0 ? (
                  <button className="btn full" onClick={() => nav("/wallet")}>+ {t("Balansni to'ldirish")}</button>
                ) : (
                  <button className="btn full" disabled={busy || l.status !== "active"} onClick={() => run(async () => {
                    const d = await api.post<Deal>(`/listings/${l.id}/buy`);
                    await refreshMe();
                    nav(`/deal/${d.id}`, { replace: true });
                  })}>{t("To'lash")} · {money(l.price)}</button>
                )}
              </BottomBar>
            </>
          );
        }}
      </Loadable>
    </>
  );
}

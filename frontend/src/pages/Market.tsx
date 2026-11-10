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
      <Header title={t("Account savdo")} sub={t("Tayyor akkauntlarni sotib oling")} back={false} />
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
  const { me, refreshMe } = useApp();
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
          const enough = (me?.balance ?? 0) >= l.price;
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
                <div className="card">
                  {l.collection_level && <div className="kv"><span>{t("Kolleksiya darajasi")}</span><span>{l.collection_level}</span></div>}
                  <div className="kv"><span>{t("Skinlar")}</span><span>{l.skins}</span></div>
                  {l.heroes > 0 && <div className="kv"><span>{t("Qahramonlar")}</span><span>{l.heroes}</span></div>}
                  <div className="kv"><span>{t("Ko'rishlar")}</span><span>{l.views}</span></div>
                </div>
                {l.description && <div className="card"><div className="b" style={{ marginBottom: 6 }}>{t("Tavsif")}</div><div className="pre sm">{l.description}</div></div>}
                <div className="card row">
                  <div className="glogo UZS" style={{ width: 40, height: 40, borderRadius: "50%", fontSize: 14 }}>{(l.seller.name || "?")[0]}</div>
                  <div className="grow">
                    <div className="b">{l.seller.username ? "@" + l.seller.username : l.seller.name}</div>
                    <div className="mut xs">
                      {l.seller.rating ? `★ ${l.seller.rating} (${l.seller.rating_count})` : t("Hali baho yo'q")} · {t("{n} ta savdo", { n: l.seller_stats?.sales ?? 0 })}
                    </div>
                  </div>
                  {l.seller_verified ? <span className="badge g">✔ {t("Tasdiqlangan")}</span> : <span className="badge g">GARANT</span>}
                </div>
                <div className="card tight sm mut">
                  🔒 {t("Garant: to'lov VAYNEXO'da saqlanadi va siz akkauntni tekshirib tasdiqlaganingizdan keyin sotuvchiga o'tkaziladi.")}
                </div>
              </div>
              <BottomBar>
                {l.is_mine ? (
                  <button className="btn ghost full" onClick={() => nav(`/sell/${l.id}`)}>{t("Tahrirlash")}</button>
                ) : (
                  <>
                    <button className="btn ghost" disabled={busy} onClick={() => openChat(l)}><Icon name="chat" /> {t("Chat")}</button>
                    <button className="btn grow" disabled={l.status !== "active"} onClick={() => setBuyOpen(true)}>{l.status === "active" ? t("Sotib olish") : t("Sotilgan")}</button>
                  </>
                )}
              </BottomBar>
              <Sheet open={buyOpen} onClose={() => setBuyOpen(false)}>
                <div className="sec-title">{t("Xaridni tasdiqlang")}</div>
                <div className="row"><GameLogo game={l.game} /><div className="grow"><div className="b ell">{l.title}</div><div className="y bb mono">{som(l.price)}</div></div></div>
                <div className="card">
                  {[t("Pul balansingizdan yechiladi va garantda saqlanadi"), t("Sotuvchi akkaunt ma'lumotlarini yuboradi"), t("Tekshirib, «Tasdiqlash» ni bosasiz — pul sotuvchiga o'tadi"), t("Muammo bo'lsa — nizo ochasiz, admin hal qiladi")].map((s, i) => (
                    <div key={i} className="row sm" style={{ padding: "4px 0", alignItems: "flex-start" }}><span className="badge y">{i + 1}</span><span>{s}</span></div>
                  ))}
                </div>
                <div className="kv"><span>{t("Balans")}</span><span className={enough ? "" : "r"}>{som(me?.balance ?? 0)}</span></div>
                {enough ? (
                  <button className="btn full" disabled={busy} onClick={() => run(async () => {
                    const d = await api.post<Deal>(`/listings/${l.id}/buy`);
                    await refreshMe();
                    nav(`/deal/${d.id}`, { replace: true });
                  })}>{t("To'lash")} · {money(l.price)}</button>
                ) : (
                  <button className="btn full" onClick={() => nav("/wallet")}>{t("Balansni to'ldirish")} (−{money(l.price - (me?.balance ?? 0))})</button>
                )}
              </Sheet>
            </>
          );
        }}
      </Loadable>
    </>
  );
}

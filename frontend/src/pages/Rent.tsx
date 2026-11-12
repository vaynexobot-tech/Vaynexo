import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Media } from "../api";
import { t } from "../i18n";
import { confirmDialog } from "../tg";
import {
  BottomBar, BottomNav, Chips, KycBanner, Copy, dateTime, Empty, Field, GAME_IMG, Header, Icon, Loadable, money, MoneyInput, Seg, Sheet, som,
  Spinner, Status, useAction, useApp, useLoad,
} from "../ui";

export interface RentCard {
  id: number; game: "ML" | "MC"; title: string; rank: string; server: string; collection_level?: string; skins: number; heroes: number; price_per_hour: number;
  status: string; reject_reason: string | null; cover: string | null; busy_until: string | null; owner_rating: number | null; created_at: string;
}
interface RentFull extends RentCard { description: string; media: Media[]; owner: { id: number; name: string; username: string | null; rating: number | null; rating_count: number }; is_mine: boolean }
interface RentConfig { durations: { hours: number; label: string; discount?: number }[]; rent_deposit_type: "percent" | "fixed"; rent_deposit_percent: number; rent_deposit_fixed: number; rent_commission_percent: number }
interface Rental {
  id: number; listing: RentCard; role: "renter" | "owner" | "admin"; hours: number; duration: string; price: number; deposit: number; commission: number;
  status: string; starts_at: string; ends_at: string; review_until: string | null; dispute_by: string | null; dispute_reason: string | null;
  resolution: string | null; credentials: string | null;
}

const RANKS = ["Epic", "Legend", "Mythic", "Mythic Honor", "Mythic Glory", "Mythic Immortal"];
const LEVELS = ["World", "Mega", "Exalted", "Renowned", "Expert", "Senior", "Junior"];
/** Narx = soatlik × soat − muddat chegirmasi (server ham xuddi shunday hisoblaydi). */
const priceOf = (pph: number, hours: number, c: RentConfig) => {
  const gross = pph * hours;
  const d = c.durations.find((x) => x.hours === hours)?.discount ?? 0;
  return gross - Math.floor((gross * d) / 100);
};
const depositOf = (price: number, c: RentConfig) => (c.rent_deposit_type === "fixed" ? c.rent_deposit_fixed : Math.floor((price * c.rent_deposit_percent) / 100));

function useCountdown(iso: string | null) {
  const [left, setLeft] = useState(() => (iso ? Date.parse(iso) - Date.now() : 0));
  useEffect(() => {
    if (!iso) return;
    setLeft(Date.parse(iso) - Date.now()); // darhol, bir soniya kutmasdan
    const id = setInterval(() => setLeft(Date.parse(iso) - Date.now()), 1000);
    return () => clearInterval(id);
  }, [iso]);
  if (!iso || left <= 0) return null;
  const h = Math.floor(left / 3600000), m = Math.floor((left % 3600000) / 60000), s = Math.floor((left % 60000) / 1000);
  return h >= 24 ? t("{d} kun {h} soat", { d: Math.floor(h / 24), h: h % 24 }) : `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function BusyLabel({ until }: { until: string | null }) {
  const left = useCountdown(until);
  return left ? <span style={{ color: "#ffb020" }}>● {t("Band")} · {left}</span> : <span className="g">● {t("Bo'sh")}</span>;
}

export function Rent() {
  const nav = useNavigate();
  const [cat, setCat] = useState("all"); // all | free | lv:<daraja>
  const [sort, setSort] = useState("cheap");
  const st = useLoad(() => {
    const p = new URLSearchParams({ sort });
    if (cat === "free") p.set("free", "true");
    if (cat.startsWith("lv:")) p.set("level", cat.slice(3));
    return api.get<{ items: RentCard[]; total: number; free: number }>("/rent/listings?" + p);
  }, [cat, sort]);
  return (
    <>
      <Header title={t("Account ijara")} sub={t("Soatbay ijaraga oling")} back={false} icon="bag" />
      <div className="page">
        <KycBanner area="rental" />
        <div className="grid2">
          <button className="btn small" onClick={() => nav("/rent/new")}>+ {t("Ijaraga berish")}</button>
          <button className="btn small ghost" onClick={() => nav("/rentals")}>{t("Mening ijaralarim")}</button>
        </div>
        <Chips value={cat} onChange={setCat} options={[
          { v: "all", label: t("Hammasi") }, { v: "free", label: t("Bo'sh") },
          ...LEVELS.map((l) => ({ v: "lv:" + l, label: l })),
        ]} />
        <div className="row between sm">
          <span className="mut">{st.data ? t("{n} ta akkaunt · {f} tasi bo'sh", { n: st.data.total, f: st.data.free }) : ""}</span>
          <select className="sortsel" aria-label={t("Saralash")} value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="cheap">{t("Eng arzon")}</option>
            <option value="expensive">{t("Eng qimmat")}</option>
            <option value="new">{t("Eng yangi")}</option>
            <option value="skins">{t("Eng ko'p skin")}</option>
          </select>
        </div>
        <Loadable state={st}>
          {(d) => d.items.length === 0 ? <Empty icon="🔑" text={t("Hozircha ijara uchun akkaunt yo'q")} /> : (
            <div className="mgrid">
              {d.items.map((x) => (
                <div key={x.id} className="gcard" style={x.busy_until ? { opacity: 0.75 } : undefined} onClick={() => nav(`/rent/${x.id}`)}>
                  <div className="gcov">
                    <img src={x.cover ?? GAME_IMG[x.game]} alt="" loading="lazy" style={x.busy_until ? { filter: "grayscale(.6) brightness(.75)" } : undefined} />
                    {(x.collection_level || x.rank) && <span className="grank">{(x.collection_level || x.rank).toUpperCase()}</span>}
                  </div>
                  <div className="gbody">
                    <div className="b ell sm">{x.title}</div>
                    <div className="mut xs ell">{x.skins} skin{x.server ? ` · ${x.server}` : ""}</div>
                    <div className="y bb mono" style={{ fontSize: 14 }}>{money(x.price_per_hour)} <span className="mut xs">{t("so'm/soat")}</span></div>
                    <div className="xs b"><BusyLabel until={x.busy_until} /></div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Loadable>
      </div>
      <BottomNav />
    </>
  );
}

export function RentDetail() {
  const id = useParams().id;
  const nav = useNavigate();
  const { me, refreshMe } = useApp();
  const st = useLoad(() => Promise.all([api.get<RentFull>(`/rent/listings/${id}`), api.get<RentConfig>("/rent/config")]), [id]);
  const [open, setOpen] = useState(false);
  const [hours, setHours] = useState(12);
  const [agree, setAgree] = useState(false);
  const { busy, run } = useAction();
  return (
    <>
      <Header title={t("Ijara tafsilotlari")} sub={t("Account ijara")} />
      <Loadable state={st}>
        {([l, cfg]) => {
          const price = priceOf(l.price_per_hour, hours, cfg);
          const deposit = depositOf(price, cfg);
          const total = price + deposit;
          const enough = (me?.balance ?? 0) >= total;
          return (
            <>
              <div className="page">
                {l.media.length ? (
                  <div className="gallery">{l.media.map((m, i) => (m.type === "video" ? <video key={i} src={m.url} controls playsInline preload="metadata" /> : <img key={i} src={m.url} alt="" />))}</div>
                ) : <img className="cover" src={GAME_IMG[l.game]} alt="" style={{ objectPosition: "center 25%" }} />}
                <div className="row" style={{ gap: 6 }}>
                  {l.rank && <span className="badge y">{l.rank.toUpperCase()}</span>}
                  <span className="badge m mono">#IJ-{l.id}</span>
                  <span className="xs b" style={{ marginLeft: "auto" }}><BusyLabel until={l.busy_until} /></span>
                </div>
                <div>
                  <div className="hf bb" style={{ fontSize: 20 }}>{l.title}</div>
                  <div className="mut sm">{l.game === "ML" ? "Mobile Legends" : "Magic Chess"}{l.server ? ` · ${t("Server")}: ${l.server}` : ""}</div>
                </div>
                <div className="y bb mono" style={{ fontSize: 22 }}>{som(l.price_per_hour)} <span className="mut sm">/ {t("soat")}</span></div>
                <div className="card">
                  <div className="kv"><span>{t("Skinlar")}</span><span>{l.skins}</span></div>
                  {l.heroes > 0 && <div className="kv"><span>{t("Qahramonlar")}</span><span>{l.heroes}</span></div>}
                  <div className="kv"><span>{t("Egasi")}</span><span>{l.owner.username ? "@" + l.owner.username : l.owner.name}{l.owner.rating ? ` · ★ ${l.owner.rating}` : ""}</span></div>
                </div>
                {l.description && <div className="card"><div className="b" style={{ marginBottom: 6 }}>{t("Tavsif")}</div><div className="pre sm">{l.description}</div></div>}
                <div className="card tight sm" style={{ background: "rgba(29,233,182,.06)", borderColor: "rgba(29,233,182,.25)" }}>
                  <div className="b" style={{ marginBottom: 6 }}>🔒 {t("Qanday himoyalangan")}</div>
                  {[t("Pul va depozit ijara tugaguncha garantda turadi"), t("Login va parol to'lovdan keyin darhol ochiladi"),
                    t("Parol yoki pochtani almashtirish taqiqlanadi: depozit ushlab qolinadi va hisob bloklanadi"),
                    t("Muddat tugagach egasi tasdiqlaydi va depozit sizga qaytadi")].map((x, i) => (
                    <div key={i} className="row xs" style={{ alignItems: "flex-start", padding: "3px 0" }}><span className="badge y">{i + 1}</span><span>{x}</span></div>
                  ))}
                </div>
              </div>
              <BottomBar>
                {l.is_mine ? (
                  <button className="btn ghost full" onClick={() => nav(`/rent/edit/${l.id}`)}>{t("Tahrirlash")}</button>
                ) : (
                  <button className="btn full" disabled={!!l.busy_until} onClick={() => setOpen(true)}>{l.busy_until ? t("Hozir band") : t("Ijaraga olish")}</button>
                )}
              </BottomBar>
              <Sheet open={open} onClose={() => setOpen(false)}>
                <div className="sec-title">{t("Ijara muddati")}</div>
                <div className="grid2">
                  {cfg.durations.map((d) => (
                    <button key={d.hours} className={"pkg center" + (hours === d.hours ? " on" : "")} onClick={() => setHours(d.hours)}>
                      <div className="b">{t(d.label)}</div><div className="y mono xs">{money(priceOf(l.price_per_hour, d.hours, cfg))}</div>
                      {d.discount ? <div className="g xs b">−{d.discount}%</div> : null}
                    </button>
                  ))}
                </div>
                <div className="card tight">
                  <div className="kv"><span>{t("Ijara")} ({t(cfg.durations.find((d) => d.hours === hours)!.label)}{cfg.durations.find((d) => d.hours === hours)?.discount ? `, −${cfg.durations.find((d) => d.hours === hours)!.discount}%` : ""})</span><span>{som(price)}</span></div>
                  <div className="kv"><span>{t("Depozit")} <span className="g xs">{t("qaytariladi")}</span></span><span>{som(deposit)}</span></div>
                  <div className="kv"><span>{t("Jami yechiladi")}</span><span className="y">{som(total)}</span></div>
                  <div className="kv"><span>{t("Balans")}</span><span className={enough ? "" : "r"}>{som(me?.balance ?? 0)}</span></div>
                </div>
                <label className="row sm" style={{ cursor: "pointer" }}>
                  <input id="rent-agree" type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} style={{ width: 18, height: 18, accentColor: "#ffd60a" }} />
                  <span><a className="y" style={{ textDecoration: "underline" }} onClick={(e) => { e.preventDefault(); nav("/legal/rent"); }}>{t("Ijara shartnomasi")}</a>{t("ni o'qidim va roziman: parol va pochtani o'zgartirmayman, muddat tugagach chiqaman")}</span>
                </label>
                {enough ? (
                  <button className="btn full" disabled={busy || !agree} onClick={() => run(async () => {
                    const r = await api.post<Rental>(`/rent/listings/${l.id}/rent`, { hours });
                    await refreshMe();
                    nav(`/rental/${r.id}`, { replace: true });
                  })}>{t("Garant bilan ijaraga olish")} · {money(total)}</button>
                ) : (
                  <button className="btn full" onClick={() => nav("/wallet")}>{t("Balansni to'ldirish")} (−{money(total - (me?.balance ?? 0))})</button>
                )}
              </Sheet>
            </>
          );
        }}
      </Loadable>
    </>
  );
}

export function RentSell() {
  const editId = useParams().id;
  const nav = useNavigate();
  const { toast, fail } = useApp();
  const [f, setF] = useState({ game: "ML" as "ML" | "MC", title: "", rank: "", server: "", collection_level: "", skins: "" as number | "", heroes: "" as number | "", price_per_hour: "" as number | "", description: "", credentials: "", media: [] as Media[] });
  const [loading, setLoading] = useState(!!editId);
  const [uploading, setUploading] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);
  const { busy, run } = useAction();
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }));
  useEffect(() => {
    if (!editId) return;
    api.get<RentFull>(`/rent/listings/${editId}`).then((l) => {
      setF({ game: l.game, title: l.title, rank: l.rank, server: l.server, collection_level: l.collection_level ?? "", skins: l.skins, heroes: l.heroes, price_per_hour: l.price_per_hour, description: l.description, credentials: "", media: l.media });
      setLoading(false);
    }).catch((e) => { fail(e); nav(-1); });
  }, [editId, fail, nav]);
  const onFiles = async (files: FileList | null) => {
    for (const file of Array.from(files ?? []).slice(0, 6 - f.media.length)) {
      if (!file.type.startsWith("image/")) { toast(t("Faqat rasm yuklang"), "err"); continue; }
      setUploading((n) => n + 1);
      try {
        const m = await api.upload(file);
        setF((p) => ({ ...p, media: [...p.media, m].slice(0, 6) }));
      } catch (e) { fail(e); } finally { setUploading((n) => n - 1); }
    }
    if (fileRef.current) fileRef.current.value = "";
  };
  const valid = f.title.trim().length >= 3 && f.rank && typeof f.price_per_hour === "number" && f.price_per_hour >= 500 && (editId || f.credentials.trim().length >= 3) && uploading === 0;
  if (loading) return <><Header title={t("Ijaraga berish")} /><Spinner /></>;
  return (
    <>
      <Header title={editId ? t("Ijara e'lonini tahrirlash") : t("Ijaraga berish")} sub={t("Akkauntingizni soatbay ijaraga qo'ying")} />
      <div className="page">
        <Seg value={f.game} onChange={(v) => set("game", v)} options={[{ v: "ML", label: "Mobile Legends" }, { v: "MC", label: "Magic Chess" }]} />
        <Field label={t("Sarlavha")}><input className="input" maxLength={120} placeholder={t("Masalan: Mythic akkaunt · 120 skin")} value={f.title} onChange={(e) => set("title", e.target.value)} /></Field>
        <Field label={t("Rank")}><Chips wrap value={f.rank} onChange={(v) => set("rank", v)} options={RANKS.map((r) => ({ v: r, label: r }))} /></Field>
        <Field label={t("Kolleksiya darajasi")}><Chips wrap value={f.collection_level} onChange={(v) => set("collection_level", f.collection_level === v ? "" : v)} options={LEVELS.map((l) => ({ v: l + " Collector", label: l }))} /></Field>
        <div className="grid3">
          <Field label={t("Skinlar")}><input className="input mono" inputMode="numeric" value={f.skins} onChange={(e) => set("skins", e.target.value ? Number(e.target.value.replace(/\D/g, "").slice(0, 4)) : "")} /></Field>
          <Field label={t("Qahramonlar")}><input className="input mono" inputMode="numeric" value={f.heroes} onChange={(e) => set("heroes", e.target.value ? Number(e.target.value.replace(/\D/g, "").slice(0, 3)) : "")} /></Field>
          <Field label={t("Server")}><input className="input" maxLength={32} placeholder="Asia" value={f.server} onChange={(e) => set("server", e.target.value)} /></Field>
        </div>
        <Field label={t("Narx (so'm / soat)")}><MoneyInput value={f.price_per_hour} onChange={(v) => set("price_per_hour", v)} placeholder="5 000" /></Field>
        {typeof f.price_per_hour === "number" && f.price_per_hour > 0 && (
          <div className="mut xs">12 {t("soat")} = {som(f.price_per_hour * 12)} · 24 {t("soat")} = {som(f.price_per_hour * 24)} · 1 {t("hafta")} = {som(f.price_per_hour * 168)}</div>
        )}
        <Field label={t("Tavsif")}><textarea className="input" maxLength={3000} value={f.description} onChange={(e) => set("description", e.target.value)} /></Field>
        <Field label={editId ? t("Kirish ma'lumotlari (o'zgartirish uchun yozing)") : t("Kirish ma'lumotlari")}>
          <textarea className="input" maxLength={2000} placeholder={"Moonton: example@gmail.com\nParol: ..."} value={f.credentials} onChange={(e) => set("credentials", e.target.value)} />
          <div className="mut xs">🔒 {t("Shifrlangan holda saqlanadi. Faqat to'lagan ijarachiga, ijara davomida ko'rinadi. Har ijaradan keyin parolni almashtiring.")}</div>
        </Field>
        <Field label={t("Rasmlar ({n}/6)", { n: f.media.length })}>
          <div className="uploader">
            {f.media.map((m, i) => <div key={m.url} className="tile"><img src={m.url} alt="" /><button className="x" aria-label={t("O'chirish")} onClick={() => set("media", f.media.filter((_, j) => j !== i))}>×</button></div>)}
            {Array.from({ length: uploading }).map((_, i) => <div key={"u" + i} className="tile"><div className="spinner" style={{ margin: 0 }} /></div>)}
            {f.media.length + uploading < 6 && <button className="tile" onClick={() => fileRef.current?.click()}><Icon name="upload" /></button>}
          </div>
          <input ref={fileRef} type="file" accept="image/*" multiple hidden onChange={(e) => onFiles(e.target.files)} />
        </Field>
      </div>
      <BottomBar>
        <button className="btn full" disabled={!valid || busy} onClick={() => run(async () => {
          const body = { ...f, skins: f.skins || 0, heroes: f.heroes || 0 };
          if (editId) await api.put(`/rent/listings/${editId}`, body);
          else await api.post("/rent/listings", body);
          toast(t("E'lon moderatsiyaga yuborildi"), "ok");
          nav("/rentals?tab=listings", { replace: true });
        })}>{t("E'lonni yuborish")}</button>
      </BottomBar>
    </>
  );
}

export function MyRentals() {
  const nav = useNavigate();
  const [tab, setTab] = useState<"renter" | "owner" | "listings">(new URLSearchParams(location.search).get("tab") === "listings" ? "listings" : "renter");
  const st = useLoad<(RentCard | Rental)[]>(() => (tab === "listings" ? api.get<RentCard[]>("/my/rent-listings") : api.get<Rental[]>(`/rentals?role=${tab}`)), [tab]);
  const { run } = useAction();
  return (
    <>
      <Header title={t("Mening ijaralarim")} />
      <div className="page">
        <Seg value={tab} onChange={setTab} options={[{ v: "renter", label: t("Olganlarim") }, { v: "owner", label: t("Berganlarim") }, { v: "listings", label: t("E'lonlarim") }]} />
        <Loadable state={st}>
          {(d) => {
            if (tab === "listings") {
              const items = d as RentCard[]; // eslint-disable-line
              return (
                <>
                  <button className="btn full" onClick={() => nav("/rent/new")}>+ {t("Ijaraga berish")}</button>
                  {items.length === 0 ? <Empty icon="🔑" text={t("Ijara e'lonlari yo'q")} /> : items.map((x) => (
                    <div key={x.id} className="card col">
                      <div className="row between"><span className="b ell">{x.title}</span><Status s={x.status} /></div>
                      <div className="row between sm"><span className="y mono b">{som(x.price_per_hour)}/{t("soat")}</span><BusyLabel until={x.busy_until} /></div>
                      {x.reject_reason && x.status === "rejected" && <div className="r xs">{t("Sabab")}: {x.reject_reason}</div>}
                      <div className="row">
                        <button className="btn small ghost grow" onClick={() => nav(`/rent/edit/${x.id}`)}>{t("Tahrirlash")}</button>
                        {x.status !== "closed" && <button className="btn small danger" onClick={async () => {
                          if (await confirmDialog(t("E'lonni yopasizmi?"))) run(async () => { await api.post(`/rent/listings/${x.id}/close`); st.reload(); });
                        }}>{t("Yopish")}</button>}
                      </div>
                    </div>
                  ))}
                </>
              );
            }
            const items = d as unknown as Rental[];
            return items.length === 0 ? <Empty icon="🔑" text={t("Ijaralar yo'q")}><button className="btn small" onClick={() => nav("/rent")}>{t("Account ijara")}</button></Empty> : (
              <>{items.map((r) => (
                <div key={r.id} className="card click" onClick={() => nav(`/rental/${r.id}`)}>
                  <div className="row between"><span className="b ell">{r.listing.title}</span><Status s={"rent_" + r.status} /></div>
                  <div className="mut xs">#{r.id} · {r.duration} · {som(r.price)} · {dateTime(r.starts_at)}</div>
                </div>
              ))}</>
            );
          }}
        </Loadable>
      </div>
    </>
  );
}

export function RentalPage() {
  const id = useParams().id;
  const { refreshMe, toast } = useApp();
  const st = useLoad(() => api.get<Rental>(`/rentals/${id}`), [id]);
  const [dispute, setDispute] = useState(false);
  const [reason, setReason] = useState("");
  const { busy, run } = useAction();
  const endsLeft = useCountdown(st.data?.status === "active" ? st.data.ends_at : null);
  const act = (path: string, body: unknown = {}, msg?: string) => run(async () => {
    st.setData(await api.post<Rental>(`/rentals/${id}/${path}`, body));
    setDispute(false);
    if (msg) toast(msg, "ok");
    refreshMe();
  });
  return (
    <>
      <Header title={t("Ijara #{id}", { id: id ?? "" })} sub={t("Garantli ijara")} />
      <Loadable state={st}>
        {(r) => {
          const owner = r.role === "owner";
          return (
            <>
              <div className="page">
                {r.status === "active" && (
                  <div className="hero center">
                    <div className="mut xs mono">{t("IJARA TUGASHIGA")}</div>
                    <div className="hf bb mono" style={{ fontSize: 30 }}>{endsLeft ?? "00:00:00"}</div>
                    <div className="mut xs">{dateTime(r.ends_at)} {t("gacha")}</div>
                  </div>
                )}
                <div className="card">
                  <div className="row between"><span className="b ell">{r.listing.title}</span><Status s={"rent_" + r.status} /></div>
                  <div className="kv"><span>{t("Muddat")}</span><span>{t(r.duration)}</span></div>
                  <div className="kv"><span>{t("Ijara narxi")}</span><span>{som(r.price)}</span></div>
                  <div className="kv"><span>{t("Depozit")}</span><span>{som(r.deposit)}</span></div>
                  {owner && <div className="kv"><span>{t("Sizga tushadi")}</span><span className="g">{som(r.price - r.commission)}</span></div>}
                  {r.review_until && <div className="kv"><span>{t("Egasining tekshiruvi")}</span><span>{dateTime(r.review_until)} {t("gacha")}</span></div>}
                </div>
                {r.credentials && (
                  <div className="card col">
                    <div className="b">🔐 {t("Akkauntga kirish")}</div>
                    <Copy value={r.credentials} />
                    <div className="mut xs">{t("Parol va pochtani o'zgartirmang. Muddat tugagach akkauntdan chiqing.")}</div>
                  </div>
                )}
                {owner && r.status === "active" && <div className="card tight sm">⏳ {t("Akkaunt hozir ijarachida. Muddat tugagach parolni almashtiring va «Akkaunt qaytdi» ni bosing.")}</div>}
                {owner && r.status === "ended" && <div className="card tight sm">🔑 {t("Ijara tugadi. Akkauntga kirib parolni almashtiring. Hammasi joyida bo'lsa «Akkaunt qaytdi», muammo bo'lsa «Muammo bor».")}</div>}
                {r.status === "disputed" && <div className="card tight sm">⚖️ {t("Nizo ochilgan. Admin ko'rib chiqadi.")}<div className="mut xs pre">{r.dispute_reason}</div></div>}
                {r.resolution && <div className="card tight sm">{t("Admin qarori")}: {r.resolution}</div>}
              </div>
              <BottomBar>
                {owner && r.status === "ended" && (
                  <>
                    <button className="btn danger" onClick={() => setDispute(true)}>{t("Muammo bor")}</button>
                    <button className="btn green grow" disabled={busy} onClick={async () => {
                      if (await confirmDialog(t("Akkaunt joyidami? Tasdiqlagach depozit ijarachiga qaytadi."))) act("confirm", {}, t("Ijara yakunlandi"));
                    }}>{t("Akkaunt qaytdi")}</button>
                  </>
                )}
                {!owner && r.status === "active" && <button className="btn danger full" onClick={() => setDispute(true)}>{t("Akkaunt ishlamayapti")}</button>}
              </BottomBar>
              <Sheet open={dispute} onClose={() => setDispute(false)}>
                <div className="sec-title">{t("Muammoni yozing")}</div>
                <div className="mut sm">{owner ? t("Masalan: parol yoki pochta almashtirilgan, skinlar yo'qolgan") : t("Masalan: login yoki parol to'g'ri kelmadi")}</div>
                <textarea className="input" maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} />
                <button className="btn danger full" disabled={reason.trim().length < 5 || busy} onClick={() => act("dispute", { reason }, t("Nizo ochildi"))}>{t("Nizo ochish")}</button>
              </Sheet>
            </>
          );
        }}
      </Loadable>
    </>
  );
}

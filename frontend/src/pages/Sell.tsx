import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ListingCard, type ListingFull, type Media } from "../api";
import { t } from "../i18n";
import { confirmDialog } from "../tg";
import { BottomBar, Chips, Empty, Field, Header, Icon, Loadable, money, MoneyInput, Seg, Sheet, som, Spinner, useAction, useApp, useLoad } from "../ui";
import { ListingRow } from "./Market";

const RANKS = ["Epic", "Legend", "Mythic", "Mythic Honor", "Mythic Glory", "Mythic Immortal"];
const LEVELS = ["World", "Mega", "Exalted", "Renowned", "Expert", "Senior", "Junior"].map((l) => l + " Collector");
const MAX_MEDIA = 6;

interface Form {
  game: "ML" | "MC";
  title: string;
  rank: string;
  server: string;
  collection_level: string;
  skins: number | "";
  heroes: number | "";
  price: number | "";
  description: string;
  media: Media[];
}

export function Sell() {
  const editId = useParams().id;
  const nav = useNavigate();
  const { toast, fail, me } = useApp();
  const [f, setF] = useState<Form>({ game: "ML", title: "", rank: "", server: "", collection_level: "", skins: "", heroes: "", price: "", description: "", media: [] });
  const [loading, setLoading] = useState(!!editId);
  const [uploading, setUploading] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);
  const { busy, run } = useAction();
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setF((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    if (!editId) return;
    api.get<ListingFull>(`/listings/${editId}`).then((l) => {
      setF({ game: l.game, title: l.title, rank: l.rank, server: l.server, collection_level: l.collection_level, skins: l.skins, heroes: l.heroes, price: l.price, description: l.description, media: l.media });
      setLoading(false);
    }).catch((e) => { fail(e); nav(-1); });
  }, [editId, fail, nav]);

  const onFiles = async (files: FileList | null) => {
    if (!files) return;
    const list = Array.from(files).slice(0, MAX_MEDIA - f.media.length);
    for (const file of list) {
      const isVideo = file.type.startsWith("video/");
      if (!isVideo && !file.type.startsWith("image/")) { toast(t("Faqat rasm yoki video"), "err"); continue; }
      if (file.size > (isVideo ? 50 : 5) * 1024 * 1024) { toast(isVideo ? t("Video 50 MB dan oshmasin") : t("Rasm 5 MB dan oshmasin"), "err"); continue; }
      setUploading((n) => n + 1);
      try {
        const m = await api.upload(file);
        setF((p) => ({ ...p, media: [...p.media, m].slice(0, MAX_MEDIA) }));
      } catch (e) {
        fail(e);
      } finally {
        setUploading((n) => n - 1);
      }
    }
    if (fileRef.current) fileRef.current.value = "";
  };

  const [aiBusy, setAiBusy] = useState(false);
  const aiFill = async () => {
    if (!f.rank) return toast(t("Avval rankni tanlang"), "info");
    setAiBusy(true);
    try {
      const r = await api.post<{ title: string; description: string }>("/ai/describe", {
        game: f.game, rank: f.rank, server: f.server, collection_level: f.collection_level,
        skins: f.skins || 0, heroes: f.heroes || 0, notes: f.description.slice(0, 500),
      });
      setF((p) => ({ ...p, title: r.title, description: r.description }));
      toast(t("AI sarlavha va tavsifni yozdi. Tekshirib, kerak bo'lsa tuzating"), "ok");
    } catch (e) {
      fail(e);
    } finally {
      setAiBusy(false);
    }
  };

  const valid = f.title.trim().length >= 3 && typeof f.price === "number" && f.price >= 1000 && f.rank && uploading === 0;

  const submit = () => run(async () => {
    const body = { ...f, skins: f.skins || 0, heroes: f.heroes || 0 };
    if (editId) await api.put(`/listings/${editId}`, body);
    else await api.post("/listings", body);
    setSent(true);
  });
  const [sent, setSent] = useState(false);

  if (loading) return <><Header title={t("E'lonni tahrirlash")} /><Spinner /></>;
  if (sent)
    return (
      <>
        <div className="page center" style={{ alignItems: "center", paddingTop: 90 }}>
          <div className="okcircle"><Icon name="check" size={40} /></div>
          <div className="hf bb" style={{ fontSize: 24 }}>{t("E'lon yuborildi")}</div>
          <div className="mut sm">{t("E'lon moderatsiyaga yuborildi. Tasdiqlangach Account savdo bo'limida ko'rinadi va bot orqali xabar beramiz.")}</div>
        </div>
        <BottomBar>
          <div className="col grow" style={{ gap: 8 }}>
            <button className="btn full" onClick={() => nav("/my-listings", { replace: true })}>{t("Mening e'lonlarim")}</button>
            <button className="btn ghost full" onClick={() => nav("/", { replace: true })}>{t("Bosh sahifaga")}</button>
          </div>
        </BottomBar>
      </>
    );

  return (
    <>
      <Header title={editId ? t("E'lonni tahrirlash") : t("E'lon joylash")} sub={t("Akkaunt sotish uchun ma'lumotlarni kiriting")} />
      <div className="page">
        <button className="card click row ai-fill" disabled={aiBusy} onClick={aiFill}>
          <span className="hd-ico" style={{ width: 36, height: 36 }}><Icon name="ai" size={18} /></span>
          <div className="grow" style={{ textAlign: "left" }}>
            <div className="b">{aiBusy ? t("AI yozmoqda...") : t("AI bilan to'ldirish")}</div>
            <div className="mut xs">{t("Rank va skinlarni tanlang — AI sarlavha va tavsifni yozib beradi")}</div>
          </div>
        </button>
        <Field label={t("O'yin")}>
          <Seg value={f.game} onChange={(v) => set("game", v)} options={[{ v: "ML", label: "Mobile Legends" }, { v: "MC", label: "Magic Chess" }]} />
        </Field>
        <Field label={t("Sarlavha")}>
          <input className="input" maxLength={120} placeholder={t("Masalan: Mythic akkaunt · 120 skin")} value={f.title} onChange={(e) => set("title", e.target.value)} />
        </Field>
        <Field label={t("Rank")}>
          <Chips wrap value={f.rank} onChange={(v) => set("rank", v)} options={RANKS.map((r) => ({ v: r, label: r }))} />
        </Field>
        <Field label={t("Kolleksiya darajasi")}>
          <Chips wrap value={f.collection_level} onChange={(v) => set("collection_level", f.collection_level === v ? "" : v)} options={LEVELS.map((r) => ({ v: r, label: r.replace(" Collector", "") }))} />
        </Field>
        <div className="grid3">
          <Field label={t("Skinlar")}><input className="input mono" inputMode="numeric" value={f.skins} onChange={(e) => set("skins", e.target.value ? Number(e.target.value.replace(/\D/g, "").slice(0, 4)) : "")} /></Field>
          <Field label={t("Qahramonlar")}><input className="input mono" inputMode="numeric" value={f.heroes} onChange={(e) => set("heroes", e.target.value ? Number(e.target.value.replace(/\D/g, "").slice(0, 3)) : "")} /></Field>
          <Field label={t("Server")}><input className="input" maxLength={32} placeholder="Asia" value={f.server} onChange={(e) => set("server", e.target.value)} /></Field>
        </div>
        <Field label={t("Narx (so'm)")}><MoneyInput value={f.price} onChange={(v) => set("price", v)} placeholder="500 000" /></Field>
        {typeof f.price === "number" && f.price > 0 && me && (
          <div className="mut xs">{t("Sizga tushadi: {s} (platforma komissiyasi {p}%)", { s: Math.round(f.price * (100 - me.commission_percent) / 100).toLocaleString("ru-RU"), p: me.commission_percent })}</div>
        )}
        <Field label={t("Tavsif")}>
          <textarea className="input" maxLength={3000} placeholder={t("Akkaunt haqida: skinlar, emblemalar, bog'langan pochta...")} value={f.description} onChange={(e) => set("description", e.target.value)} />
        </Field>
        <Field label={t("Rasm va video ({n}/{max})", { n: f.media.length, max: MAX_MEDIA })}>
          <div className="uploader">
            {f.media.map((m, i) => (
              <div key={m.url} className="tile">
                {m.type === "video" ? <video src={m.url} muted playsInline preload="metadata" /> : <img src={m.url} alt="" />}
                <button className="x" aria-label={t("O'chirish")} onClick={() => set("media", f.media.filter((_, j) => j !== i))}>×</button>
              </div>
            ))}
            {Array.from({ length: uploading }).map((_, i) => <div key={"u" + i} className="tile"><div className="spinner" style={{ margin: 0 }} /></div>)}
            {f.media.length + uploading < MAX_MEDIA && (
              <button className="tile" onClick={() => fileRef.current?.click()}><div className="col" style={{ alignItems: "center", gap: 4 }}><Icon name="upload" /><span className="xs">{t("Qo'shish")}</span></div></button>
            )}
          </div>
          <input ref={fileRef} type="file" accept="image/*,video/mp4,video/quicktime,video/webm" multiple hidden onChange={(e) => onFiles(e.target.files)} />
          <div className="mut xs">📷 {t("Rasm — 5 MB gacha")} · 🎬 {t("Video — 50 MB gacha")}</div>
        </Field>
        <div className="card tight mut sm">⚠️ {t("Sotilgan akkauntni qaytarib olish taqiqlanadi va bloklanishga olib keladi. Login/parolni e'longa yozmang — ular faqat sotuvdan keyin garant orqali beriladi.")}</div>
      </div>
      <BottomBar>
        <button className="btn full" disabled={!valid || busy} onClick={submit}>{t("E'lonni yuborish")}</button>
      </BottomBar>
    </>
  );
}

function VipSheet({ x, onClose, onDone }: { x: ListingCard | null; onClose: () => void; onDone: () => void }) {
  const { me, refreshMe, toast } = useApp();
  const price = useLoad(() => api.get<{ price_per_day: number }>("/vip/price"));
  const [days, setDays] = useState(3);
  const { busy, run } = useAction();
  const total = (price.data?.price_per_day ?? 0) * days;
  return (
    <Sheet open={!!x} onClose={onClose}>
      <div className="sec-title">⭐ {t("VIP e'lon")}</div>
      <div className="mut sm">{t("VIP e'lon Account savdo ro'yxatining eng tepasida, sariq ramka bilan turadi. Ko'proq odam ko'radi va tezroq sotiladi.")}</div>
      {x?.vip && x.vip_until && <div className="card tight sm">{t("Hozir VIP: {d} gacha. Sotib olsangiz muddat uzayadi.", { d: new Date(x.vip_until).toLocaleDateString("ru-RU") })}</div>}
      <Chips value={days} onChange={setDays} options={[1, 3, 7, 14].map((d) => ({ v: d, label: t("{n} kun", { n: d }) }))} />
      <div className="kv"><span>{t("Narx")}</span><span>{som(price.data?.price_per_day ?? 0)} × {days}</span></div>
      <div className="kv"><span>{t("Jami")}</span><span className="y">{som(total)}</span></div>
      <div className="kv"><span>{t("Balans")}</span><span className={(me?.balance ?? 0) >= total ? "" : "r"}>{som(me?.balance ?? 0)}</span></div>
      <button className="btn full" disabled={busy || !x || !price.data} onClick={() => run(async () => {
        await api.post(`/listings/${x!.id}/vip`, { days });
        toast(t("E'lon VIP qilindi"), "ok");
        await refreshMe();
        onDone();
      })}>{t("VIP qilish")} · {money(total)}</button>
    </Sheet>
  );
}

export function MyListings() {
  const nav = useNavigate();
  const st = useLoad(() => api.get<ListingCard[]>("/my/listings"));
  const [vipFor, setVipFor] = useState<ListingCard | null>(null);
  const [tab, setTab] = useState<"active" | "moderation" | "sold">("active");
  const { run } = useAction();
  const groups: Record<string, string[]> = { active: ["active", "reserved"], moderation: ["moderation", "rejected"], sold: ["sold", "closed"] };
  return (
    <>
      <Header title={t("Mening e'lonlarim")} sub={t("Sotuvdagi akkauntlaringiz")} />
      <div className="page withbar">
        <Loadable state={st}>
          {(list) => {
            const count = (k: string) => list.filter((x) => groups[k].includes(x.status)).length;
            const items = list.filter((x) => groups[tab].includes(x.status));
            return (
              <>
                <Seg value={tab} onChange={setTab} options={[
                  { v: "active", label: `${t("Faol")} · ${count("active")}` },
                  { v: "moderation", label: `${t("Moderatsiya")} · ${count("moderation")}` },
                  { v: "sold", label: `${t("Sotilgan")} · ${count("sold")}` },
                ]} />
                {items.length === 0 ? <Empty text={t("Bu bo'limda e'lon yo'q")} /> : items.map((x) => (
                  <ListingRow key={x.id} x={x} onClick={() => nav(`/listing/${x.id}`)} extra={
                    <div className="col" style={{ marginTop: 10, gap: 8 }}>
                      {x.reject_reason && x.status === "rejected" && <div className="r xs">{t("Sabab")}: {x.reject_reason}</div>}
                      <div className="row between">
                        <span className="mut xs">👁 {x.views} · 💬 {x.chats}</span>
                        {["active", "moderation", "rejected", "closed"].includes(x.status) && (
                          <div className="row" onClick={(e) => e.stopPropagation()}>
                            {x.status === "active" && <button className="btn small" style={{ background: "#ffb020" }} onClick={() => setVipFor(x)}>⭐ {x.vip ? t("VIP uzaytirish") : t("VIP qilish")}</button>}
                            <button className="btn small ghost" onClick={() => nav(`/sell/${x.id}`)}>{x.status === "closed" ? t("Qayta joylash") : t("Tahrirlash")}</button>
                            {x.status !== "closed" && (
                              <button className="btn small danger" onClick={async () => {
                                if (await confirmDialog(t("E'lonni yopasizmi?"))) run(async () => { await api.post(`/listings/${x.id}/close`); st.reload(); });
                              }}>{t("Yopish")}</button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  } />
                ))}
              </>
            );
          }}
        </Loadable>
      </div>
      <BottomBar>
        <button className="btn full" onClick={() => nav("/sell")}>+ {t("Yangi e'lon joylash")}</button>
      </BottomBar>
      <VipSheet x={vipFor} onClose={() => setVipFor(null)} onDone={() => { setVipFor(null); st.reload(); }} />
    </>
  );
}

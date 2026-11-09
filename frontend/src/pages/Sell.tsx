import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ListingCard, type ListingFull, type Media } from "../api";
import { t } from "../i18n";
import { confirmDialog } from "../tg";
import { BottomBar, Chips, Empty, Field, Header, Icon, Loadable, MoneyInput, Seg, Spinner, useAction, useApp, useLoad } from "../ui";
import { ListingRow } from "./Market";

const RANKS = ["Epic", "Legend", "Mythic", "Mythic Honor", "Mythic Glory", "Mythic Immortal"];
const LEVELS = ["Amateur", "Junior", "Senior", "Expert", "Renowned", "Exalted", "Mega", "World"].map((l) => l + " Collector");
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

  const valid = f.title.trim().length >= 3 && typeof f.price === "number" && f.price >= 1000 && f.rank && uploading === 0;

  const submit = () => run(async () => {
    const body = { ...f, skins: f.skins || 0, heroes: f.heroes || 0 };
    if (editId) await api.put(`/listings/${editId}`, body);
    else await api.post("/listings", body);
    toast(t("E'lon moderatsiyaga yuborildi"), "ok");
    nav("/my-listings", { replace: true });
  });

  if (loading) return <><Header title={t("E'lonni tahrirlash")} /><Spinner /></>;

  return (
    <>
      <Header title={editId ? t("E'lonni tahrirlash") : t("E'lon joylash")} sub={t("Akkaunt sotish uchun ma'lumotlarni kiriting")} />
      <div className="page">
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

export function MyListings() {
  const nav = useNavigate();
  const st = useLoad(() => api.get<ListingCard[]>("/my/listings"));
  const [tab, setTab] = useState<"active" | "moderation" | "sold">("active");
  const { run } = useAction();
  const groups: Record<string, string[]> = { active: ["active", "reserved"], moderation: ["moderation", "rejected"], sold: ["sold", "closed"] };
  return (
    <>
      <Header title={t("Mening e'lonlarim")} sub={t("Sotuvdagi akkauntlaringiz")} />
      <div className="page">
        <button className="btn full" onClick={() => nav("/sell")}>+ {t("Yangi e'lon")}</button>
        <Loadable state={st}>
          {(list) => {
            const count = (k: string) => list.filter((x) => groups[k].includes(x.status)).length;
            const items = list.filter((x) => groups[tab].includes(x.status));
            return (
              <>
                <Seg value={tab} onChange={setTab} options={[
                  { v: "active", label: `${t("Faol")} · ${count("active")}` },
                  { v: "moderation", label: `${t("Moderatsiya")} · ${count("moderation")}` },
                  { v: "sold", label: `${t("Arxiv")} · ${count("sold")}` },
                ]} />
                {items.length === 0 ? <Empty text={t("Bu bo'limda e'lon yo'q")} /> : items.map((x) => (
                  <ListingRow key={x.id} x={x} onClick={() => nav(`/listing/${x.id}`)} extra={
                    <div className="col" style={{ marginTop: 10, gap: 8 }}>
                      {x.reject_reason && x.status === "rejected" && <div className="r xs">{t("Sabab")}: {x.reject_reason}</div>}
                      <div className="row between">
                        <span className="mut xs">👁 {x.views} · 💬 {x.chats}</span>
                        {["active", "moderation", "rejected", "closed"].includes(x.status) && (
                          <div className="row" onClick={(e) => e.stopPropagation()}>
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
    </>
  );
}

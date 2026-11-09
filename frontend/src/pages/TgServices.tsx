import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Catalog, type TgOrder } from "../api";
import { t } from "../i18n";
import { BottomBar, BottomNav, Chips, Field, Header, Loadable, money, Seg, Sheet, som, Status, Toggle, useAction, useApp, useLoad } from "../ui";

type Kind = "premium" | "stars" | "gift" | "nft";
const GIFT_EMOJI: Record<string, string> = { heart: "❤️", bear: "🧸", box: "🎁", rose: "🌹", cup: "🏆", diamond: "💎" };

export default function TgServices() {
  const nav = useNavigate();
  const { me, refreshMe } = useApp();
  const cat = useLoad(() => api.get<Catalog>("/tg/catalog"));
  const [kind, setKind] = useState<Kind>("premium");
  const [months, setMonths] = useState(3);
  const [stars, setStars] = useState<number | "">(250);
  const [gift, setGift] = useState("box");
  const [nft, setNft] = useState("gift");
  const [forSelf, setForSelf] = useState(true);
  const [username, setUsername] = useState("");
  const [message, setMessage] = useState("");
  const [anonymous, setAnonymous] = useState(false);
  const [link, setLink] = useState("");
  const [done, setDone] = useState<TgOrder | null>(null);
  const { busy, run } = useAction();

  const price = (c: Catalog): number => {
    if (kind === "premium") return c.premium.find((p) => p.months === months)?.price ?? 0;
    if (kind === "stars") return typeof stars === "number" ? stars * c.stars.rate : 0;
    if (kind === "gift") return c.gifts.find((g) => g.code === gift)?.price ?? 0;
    return c.nft.find((n) => n.code === nft)?.price ?? 0;
  };
  const selfAllowed = kind !== "gift" && kind !== "nft";
  const target = selfAllowed && forSelf ? (me?.username ? "@" + me.username : "") : username;
  const userOk = /^@?[A-Za-z][A-Za-z0-9_]{3,31}$/.test(target);

  return (
    <>
      <Header title={t("TG xizmatlar")} sub={t("Telegram uchun xizmatlar")} back={false} />
      <Loadable state={cat}>
        {(c) => {
          const total = price(c);
          const valid = userOk && total > 0 && (kind !== "stars" || (typeof stars === "number" && stars >= c.stars.min && stars <= c.stars.max));
          const enough = (me?.balance ?? 0) >= total;
          return (
            <>
              <div className="page withbar">
                <Seg value={kind} onChange={setKind} options={[{ v: "premium", label: "Premium" }, { v: "stars", label: "Stars" }, { v: "gift", label: "Gift" }, { v: "nft", label: "NFT" }]} />

                {kind === "premium" && (
                  <Field label={t("Muddat")}>
                    <div className="grid2">
                      {c.premium.map((p) => (
                        <button key={p.months} className={"pkg" + (months === p.months ? " on" : "")} onClick={() => setMonths(p.months)}>
                          <div className="bb">⭐️ {t("{n} oy", { n: p.months })}</div>
                          <div className="y mono b sm" style={{ marginTop: 4 }}>{som(p.price)}</div>
                        </button>
                      ))}
                    </div>
                  </Field>
                )}
                {kind === "stars" && (
                  <>
                    <Field label={t("Stars miqdori")}>
                      <Chips wrap value={stars === "" ? null : stars} onChange={setStars} options={c.stars.presets.map((v) => ({ v, label: `${money(v)} ⭐️` }))} />
                    </Field>
                    <Field label={t("Yoki o'zingiz kiriting")}>
                      <input className="input mono" inputMode="numeric" value={stars} onChange={(e) => setStars(e.target.value ? Number(e.target.value.replace(/\D/g, "").slice(0, 6)) : "")} />
                    </Field>
                    <div className="mut xs">{t("Kurs: {r} so'm / Star · Eng kam: {m}", { r: c.stars.rate, m: c.stars.min })}</div>
                  </>
                )}
                {kind === "gift" && (
                  <>
                    <Field label={t("Sovg'ani tanlang")}>
                      <div className="grid3">
                        {c.gifts.map((g) => (
                          <button key={g.code} className={"pkg center" + (gift === g.code ? " on" : "")} onClick={() => setGift(g.code)}>
                            <div style={{ fontSize: 28 }}>{GIFT_EMOJI[g.code] ?? "🎁"}</div>
                            <div className="sm b">{t(g.name)}</div>
                            <div className="y mono xs">{money(g.price)}</div>
                          </button>
                        ))}
                      </div>
                    </Field>
                    <Field label={t("Xabar (ixtiyoriy)")}><input className="input" maxLength={200} value={message} onChange={(e) => setMessage(e.target.value)} /></Field>
                    <div className="card tight row between"><div><div className="b sm">{t("Anonim yuborish")}</div><div className="mut xs">{t("Sizning ismingiz ko'rinmaydi")}</div></div><Toggle on={anonymous} onChange={setAnonymous} /></div>
                  </>
                )}
                {kind === "nft" && (
                  <>
                    <Field label={t("NFT turini tanlang")}>
                      <div className="col">
                        {c.nft.map((n) => (
                          <button key={n.code} className={"pkg row between" + (nft === n.code ? " on" : "")} onClick={() => setNft(n.code)}>
                            <span className="b">{t(n.name)}</span><span className="y mono b">{som(n.price)}</span>
                          </button>
                        ))}
                      </div>
                    </Field>
                    <Field label={t("NFT nomi yoki havolasi")}><input className="input" maxLength={200} placeholder="t.me/nft/..." value={link} onChange={(e) => setLink(e.target.value)} /></Field>
                  </>
                )}

                {selfAllowed && <Seg value={forSelf ? "self" : "other"} onChange={(v) => setForSelf(v === "self")} options={[{ v: "self", label: t("O'zimga") }, { v: "other", label: t("Boshqa odamga") }]} />}
                {(!selfAllowed || !forSelf) && (
                  <Field label={t("Qabul qiluvchi username")}><input className="input" placeholder="@username" maxLength={33} value={username} onChange={(e) => setUsername(e.target.value.trim())} /></Field>
                )}
                {selfAllowed && forSelf && !me?.username && <div className="r sm">{t("Telegram profilingizda username yo'q. «Boshqa odamga» ni tanlab, username'ni qo'lda kiriting.")}</div>}
                <div className="card tight mut sm">⚡ {t("Yetkazish: odatda 5–30 daqiqa. Natija Telegram orqali xabar qilinadi.")}</div>
              </div>
              <BottomBar aboveNav>
                <div className="grow card tight" style={{ padding: "6px 12px" }}><div className="mut xs">{t("Jami")}</div><div className="y bb mono" style={{ fontSize: 18 }}>{som(total)}</div></div>
                {enough || !valid ? (
                  <button className="btn" disabled={!valid || busy} onClick={() => run(async () => {
                    const o = await api.post<TgOrder>("/tg/orders", { kind, months, stars, gift, nft, for_self: selfAllowed && forSelf, target_username: username, message, anonymous, link });
                    setDone(o);
                    await refreshMe();
                  })}>{t("Buyurtma berish")}</button>
                ) : (
                  <button className="btn" onClick={() => nav("/wallet")}>{t("Balansni to'ldirish")}</button>
                )}
              </BottomBar>
              <Sheet open={!!done} onClose={() => setDone(null)}>
                {done && (
                  <div className="col center" style={{ alignItems: "center" }}>
                    <div style={{ fontSize: 46 }}>✅</div>
                    <div className="sec-title">{t("Buyurtma qabul qilindi")}</div>
                    <div className="mut sm">{t("To'lov hamyoningizdan yechildi. Xizmat odatda 5–30 daqiqada bajariladi.")}</div>
                    <div className="card" style={{ width: "100%" }}>
                      <div className="kv"><span>{t("Buyurtma")}</span><span className="mono">{done.ref}</span></div>
                      <div className="kv"><span>{t("Xizmat")}</span><span>{done.title}</span></div>
                      <div className="kv"><span>{t("Kimga")}</span><span>{done.target_username}</span></div>
                      <div className="kv"><span>{t("Holati")}</span><Status s={done.status} /></div>
                    </div>
                    <button className="btn full" onClick={() => setDone(null)}>{t("Yaxshi")}</button>
                  </div>
                )}
              </Sheet>
            </>
          );
        }}
      </Loadable>
      <BottomNav />
    </>
  );
}

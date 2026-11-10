import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Catalog, type TgOrder } from "../api";
import { t } from "../i18n";
import {
  BottomBar, BottomNav, dateTime, Empty, Field, Header, Loadable, money, Seg, som, Status, Toggle, useAction, useApp, useLoad,
} from "../ui";

type Kind = "premium" | "stars" | "gift" | "nft";
const GIFT_EMOJI: Record<string, string> = { heart: "❤️", bear: "🧸", box: "🎁", rose: "🌹", cup: "🏆", diamond: "💎" };
const NFT_EMOJI: Record<string, string> = { gift: "🖼", username: "🔤", number: "📱" };
const TABS: { v: Kind; icon: string; label: string }[] = [
  { v: "premium", icon: "★", label: "Premium" }, { v: "stars", icon: "✦", label: "Stars" },
  { v: "gift", icon: "🎁", label: "Gift" }, { v: "nft", icon: "◆", label: "NFT" },
];
const USERNAME_RE = /^@?[A-Za-z][A-Za-z0-9_]{3,31}$/;

export default function TgServices() {
  const nav = useNavigate();
  const { me, refreshMe } = useApp();
  const cat = useLoad(() => api.get<Catalog & { stars: Catalog["stars"] & { preset_prices: Record<string, number> } }>("/tg/catalog"));
  const history = useLoad(() => api.get<TgOrder[]>("/tg/orders"));
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
  const { busy, run } = useAction();

  const selfAllowed = kind === "premium" || kind === "stars";
  const target = selfAllowed && forSelf ? (me?.username ? "@" + me.username : "") : username;
  const userOk = USERNAME_RE.test(target);

  return (
    <>
      <Header title={t("TG xizmatlar")} sub={t("Telegram uchun xizmatlar")} back={false} icon="send" />
      <Loadable state={cat}>
        {(c) => {
          const monthly1 = c.premium.find((p) => p.months === 1)?.price ?? 0;
          const price = kind === "premium" ? c.premium.find((p) => p.months === months)?.price ?? 0
            : kind === "stars" ? (typeof stars === "number" ? Math.ceil(stars * c.stars.rate) : 0)
            : kind === "gift" ? c.gifts.find((g) => g.code === gift)?.price ?? 0
            : c.nft.find((n) => n.code === nft)?.price ?? 0;
          const valid = userOk && price > 0 && (kind !== "stars" || (typeof stars === "number" && stars >= c.stars.min && stars <= c.stars.max));
          const enough = (me?.balance ?? 0) >= price;
          const summary = kind === "premium" ? t("Premium {n} oy", { n: months }) : kind === "stars" ? `${money(Number(stars) || 0)} ✦`
            : kind === "gift" ? t(c.gifts.find((g) => g.code === gift)?.name ?? "") : t(c.nft.find((n) => n.code === nft)?.name ?? "");
          return (
            <>
              <div className="page withbar">
                <div className="tg4">
                  {TABS.map((x) => (
                    <button key={x.v} className={kind === x.v ? "on" : ""} onClick={() => setKind(x.v)}><i>{x.icon}</i>{x.label}</button>
                  ))}
                </div>

                {kind === "premium" && (
                  <>
                    <div className="tghero"><div className="hf bb">Telegram Premium</div><div className="xs">{t("Reklamasiz, 4 GB fayl, tezkor yuklash, maxsus stikerlar")}</div></div>
                    <div className="grid2">
                      {c.premium.map((p) => {
                        const perMonth = Math.round(p.price / p.months);
                        const save = monthly1 ? Math.round((1 - perMonth / monthly1) * 100) : 0;
                        return (
                          <button key={p.months} className={"pkg plan" + (months === p.months ? " on" : "")} onClick={() => setMonths(p.months)}>
                            {save > 0 && <span className="save">−{save}%</span>}
                            <div className="bb">⭐ {t("{n} oy", { n: p.months })}</div>
                            <div className="y mono b sm" style={{ marginTop: 3 }}>{som(p.price)}</div>
                            <div className="mut xs">{t("{s} / oy", { s: som(perMonth) })}</div>
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}
                {kind === "stars" && (
                  <>
                    <div className="grid3">
                      {c.stars.presets.slice(0, 6).map((n) => (
                        <button key={n} className={"pkg center" + (stars === n ? " on" : "")} onClick={() => setStars(n)}>
                          <div className="bb">✦ {money(n)}</div>
                          <div className="y mono xs">{money(c.stars.preset_prices[String(n)] ?? Math.ceil(n * c.stars.rate))}</div>
                        </button>
                      ))}
                    </div>
                    <Field label={t("Yoki o'zingiz kiriting")}>
                      <div className="row input" style={{ padding: "0 14px" }}>
                        <input className="grow mono" inputMode="numeric" style={{ background: "none", border: 0, outline: "none", height: "100%" }}
                          value={stars} onChange={(e) => setStars(e.target.value ? Number(e.target.value.replace(/\D/g, "").slice(0, 6)) : "")} />
                        <span className="mut sm">✦ · {som(typeof stars === "number" ? Math.ceil(stars * c.stars.rate) : 0)}</span>
                      </div>
                    </Field>
                    <div className="mut xs">{t("Kurs: {r} so'm / Star · Eng kam: {m}", { r: c.stars.rate.toLocaleString("ru-RU"), m: c.stars.min })}</div>
                  </>
                )}
                {kind === "gift" && (
                  <>
                    <div className="grid3">
                      {c.gifts.map((g) => (
                        <button key={g.code} className={"pkg center" + (gift === g.code ? " on" : "")} onClick={() => setGift(g.code)}>
                          <div style={{ fontSize: 28 }}>{GIFT_EMOJI[g.code] ?? "🎁"}</div>
                          <div className="sm b">{t(g.name)}</div>
                          <div className="y mono xs">{money(g.price)}</div>
                        </button>
                      ))}
                    </div>
                    <Field label={t("Xabar (ixtiyoriy)")}><input id="tg-msg" className="input" maxLength={200} placeholder={t("Tug'ilgan kuning bilan! 🎉")} value={message} onChange={(e) => setMessage(e.target.value)} /></Field>
                    <div className="card tight row between"><div><div className="b sm">🕶 {t("Anonim yuborish")}</div><div className="mut xs">{t("Sizning ismingiz ko'rinmaydi")}</div></div><Toggle on={anonymous} onChange={setAnonymous} /></div>
                  </>
                )}
                {kind === "nft" && (
                  <>
                    <div className="col">
                      {c.nft.map((n) => (
                        <button key={n.code} className={"pkg row between" + (nft === n.code ? " on" : "")} onClick={() => setNft(n.code)}>
                          <span className="b">{NFT_EMOJI[n.code]} {t(n.name)}</span><span className="y mono b">{som(n.price)}</span>
                        </button>
                      ))}
                    </div>
                    <Field label={t("NFT nomi yoki havolasi")}><input id="tg-nft" className="input" maxLength={200} placeholder="t.me/nft/..." value={link} onChange={(e) => setLink(e.target.value)} /></Field>
                  </>
                )}

                {selfAllowed && <Seg value={forSelf ? "self" : "other"} onChange={(v) => setForSelf(v === "self")} options={[{ v: "self", label: t("O'zimga") }, { v: "other", label: t("Boshqa odamga") }]} />}
                {(!selfAllowed || !forSelf) && (
                  <Field label={t("Qabul qiluvchi username")}>
                    <input id="tg-user" className={"input" + (username && !USERNAME_RE.test(username) ? " err" : "")} placeholder="@username" maxLength={33} value={username} onChange={(e) => setUsername(e.target.value.trim())} />
                  </Field>
                )}
                {target && (
                  <div className={"card tight row" + (userOk ? "" : " r")} style={userOk ? { borderColor: "rgba(29,233,182,.35)" } : undefined}>
                    <span className="tgava">{target.replace("@", "")[0]?.toUpperCase()}</span>
                    <div className="grow"><div className="b sm">{target.startsWith("@") ? target : "@" + target}</div>
                      <div className={"xs " + (userOk ? "g" : "r")}>{userOk ? t("Username to'g'ri yozilgan") : t("Username noto'g'ri: harf bilan boshlanib, kamida 5 belgi")}</div></div>
                  </div>
                )}
                {selfAllowed && forSelf && !me?.username && <div className="r sm">{t("Telegram profilingizda username yo'q. «Boshqa odamga» ni tanlab, username'ni qo'lda kiriting.")}</div>}
                <div className="card tight mut xs">⚡ {t("Yetkazish: odatda 5–30 daqiqa. Bajarilmasa pul to'liq hamyoningizga qaytadi.")}</div>

                {history.data && history.data.length > 0 && (
                  <>
                    <div className="mut xs mono">{t("OLDINGI BUYURTMALAR")}</div>
                    {history.data.slice(0, 5).map((o) => (
                      <div key={o.id} className="card tight click row between" onClick={() => nav(`/tg/order/${o.id}`)}>
                        <div className="grow"><div className="b sm ell">{o.title}</div><div className="mut xs">{dateTime(o.created_at)} · {o.target_username}</div></div>
                        <Status s={o.status} />
                      </div>
                    ))}
                  </>
                )}
              </div>
              <BottomBar aboveNav>
                <div className="grow card tight" style={{ padding: "6px 12px" }}><div className="mut xs ell">{summary}</div><div className="y bb mono" style={{ fontSize: 17 }}>{som(price)}</div></div>
                {enough || !valid ? (
                  <button className="btn" disabled={!valid || busy} onClick={() => run(async () => {
                    const o = await api.post<TgOrder>("/tg/orders", { kind, months, stars, gift, nft, for_self: selfAllowed && forSelf, target_username: username, message, anonymous, link });
                    await refreshMe();
                    nav(`/tg/order/${o.id}`);
                  })}>{kind === "gift" ? t("Yuborish") : t("Buyurtma berish")}</button>
                ) : (
                  <button className="btn" onClick={() => nav("/wallet")}>{t("Balansni to'ldirish")}</button>
                )}
              </BottomBar>
            </>
          );
        }}
      </Loadable>
      <BottomNav />
    </>
  );
}

export function TgOrderPage() {
  const id = useParams().id;
  const st = useLoad(() => api.get<TgOrder>(`/tg/orders/${id}`), [id]);
  const { refreshMe } = useApp();
  // Bajarilguncha har 10 soniyada holatni yangilaymiz
  useEffect(() => {
    if (!st.data || st.data.status !== "processing") return;
    const iv = setInterval(async () => {
      try {
        const o = await api.get<TgOrder>(`/tg/orders/${id}`);
        if (o.status !== "processing") { st.setData(o); refreshMe(); }
      } catch { /* keyingi safar */ }
    }, 10000);
    return () => clearInterval(iv);
  }, [st, id, refreshMe]);
  const icon: Record<string, string> = { premium: "⭐", stars: "✦", gift: "🎁", nft: "◆" };
  return (
    <>
      <Header title={t("Buyurtma")} sub={st.data?.ref} />
      <Loadable state={st}>
        {(o) => {
          const done = o.status === "done", refunded = o.status === "refunded";
          return (
            <div className="page">
              <div className="tghero center" style={{ padding: 18 }}>
                <div style={{ fontSize: 34 }}>{refunded ? "↩️" : icon[o.kind] ?? "⭐"}</div>
                <div className="bb" style={{ fontSize: 16, marginTop: 4 }}>{done ? t("Yetkazildi!") : refunded ? t("Pul qaytarildi") : t("Bajarilmoqda...")}</div>
                <div className="xs">{o.title} · {o.target_username}</div>
              </div>
              <div className="card col">
                {[
                  { ok: true, title: t("To'lov qabul qilindi"), sub: `${dateTime(o.created_at)} · ${som(o.price)}` },
                  { ok: done || refunded, cur: !done && !refunded, title: refunded ? t("Bajarilmadi") : t("Bajarilmoqda"), sub: refunded ? o.admin_note ?? "" : t("Operator buyurtmani bajaryapti") },
                  { ok: done, title: refunded ? t("Pul hamyonga qaytdi") : t("Yetkazildi"), sub: t("Telegram orqali xabar keladi") },
                ].map((s, i) => (
                  <div key={i} className="row" style={{ alignItems: "flex-start", opacity: s.ok || s.cur ? 1 : 0.45 }}>
                    <span className={"badge " + (s.ok ? (refunded && i > 0 ? "r" : "g") : s.cur ? "y" : "m")}>{s.ok ? "✓" : i + 1}</span>
                    <div><div className="b sm">{s.title}</div>{s.sub && <div className="mut xs">{s.sub}</div>}</div>
                  </div>
                ))}
              </div>
              {o.status === "processing" && <div className="card tight mut xs">↩️ {t("Bajarilmasa (masalan, username xato bo'lsa) pul to'liq hamyoningizga qaytadi.")}</div>}
            </div>
          );
        }}
      </Loadable>
    </>
  );
}

export function TgOrders() {
  const nav = useNavigate();
  const st = useLoad(() => api.get<TgOrder[]>("/tg/orders"));
  return (
    <>
      <Header title={t("TG buyurtmalarim")} />
      <div className="page">
        <Loadable state={st}>
          {(list) => list.length === 0 ? <Empty icon="⭐" text={t("Buyurtmalar yo'q")} /> : list.map((o) => (
            <div key={o.id} className="card click row between" onClick={() => nav(`/tg/order/${o.id}`)}>
              <div className="grow"><div className="b sm ell">{o.title}</div><div className="mut xs">{o.ref} · {dateTime(o.created_at)}</div></div>
              <Status s={o.status} />
            </div>
          ))}
        </Loadable>
      </div>
    </>
  );
}

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PremiumTiles, VayStrip } from "./Premium";
import { api, type DonateGameCard, type DonateGames, type Tournament } from "../api";
import { t } from "../i18n";
import { tgPhoto } from "../tg";
import { Art, BalancePill, BottomNav, GameTile, Icon, Loadable, money, som, SponsorLine, useApp, useFeature, useLoad } from "../ui";

export default function Home() {
  const nav = useNavigate();
  const { me, toast } = useApp();
  const [q, setQ] = useState("");
  const games = useLoad(() => api.get<DonateGames>("/donate/games"));
  const arena = useFeature("arena");
  const home = useLoad(() => (arena ? api.get<{ tournament: Tournament | null }>("/home") : Promise.resolve({ tournament: null })), [arena]);
  const tour = home.data?.tournament;
  const f = { market: useFeature("market"), rent: useFeature("rent"), boost: useFeature("boost"), tg: useFeature("tg"), top: useFeature("top") };
  const trade = [
    { on: f.market, to: "/market", icon: "grid", title: t("Account savdo"), sub: t("Garant bilan xavfsiz") },
    { on: f.rent, to: "/rent", icon: "bag", title: t("Account ijara"), sub: t("Soatbay ijara") },
    { on: f.boost, to: "/boost", icon: "bolt", title: t("Boost xizmati"), sub: t("Reyting ko'tarish") },
    { on: f.tg, to: "/tg", icon: "send", title: t("TG xizmatlar"), sub: t("Premium va Stars") },
  ].filter((x) => x.on);
  const photo = tgPhoto();

  const open = (g: DonateGameCard) => (g.available ? nav(`/donate/${g.slug}`) : toast(t("{n} tez kunda ochiladi", { n: g.name }), "info"));
  const found = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? (games.data?.all ?? []).filter((g) => g.name.toLowerCase().includes(s)) : [];
  }, [q, games.data]);

  return (
    <>
      <div className="hd">
        <div className="row">
          <div className="hf" style={{ width: 36, height: 36, borderRadius: 10, background: "var(--y)", color: "#111", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700 }}>VX</div>
          <div>
            <div className="row" style={{ gap: 6 }}>
              <span className="hf bb" style={{ fontSize: 18, letterSpacing: ".03em" }}>VAYNEXO</span>
              <span className="badge y mono" style={{ height: 18, fontSize: 9 }}>MINI</span>
            </div>
            <div className="mut xs">{t("O'yinlar uchun donat")}</div>
          </div>
        </div>
        <div className="row">
          <BalancePill />
          <button onClick={() => nav("/settings")} aria-label={t("Profil")} style={{ width: 36, height: 36, borderRadius: "50%", padding: 2, border: 0, background: "linear-gradient(135deg,#ffd60a,#1de9b6)" }}>
            {photo ? <img src={photo} alt="" style={{ width: "100%", height: "100%", borderRadius: "50%" }} /> : <div style={{ width: "100%", height: "100%", borderRadius: "50%", background: "linear-gradient(135deg,#3a2f6b,#e7a84a)" }} />}
          </button>
        </div>
      </div>

      <div className="page">
        {tour ? (
          <div className="hero click" onClick={() => nav(`/arena/${tour.id}`)}>
            <div className="row between">
              <span className="badge g">● {t("KONKURS")} · {tour.game === "MC" ? "Magic Chess" : "Mobile Legends"}</span>
              <span className="mono y bb">{money(tour.prize_fund)} UZS</span>
            </div>
            <div className="hf bb" style={{ fontSize: 20, margin: "12px 0 4px" }}>{tour.title}</div>
            <SponsorLine s={tour.sponsor} />
            <div className="mut sm">{t("Sovrinli turnir — ro'yxatdan o'ting va ishtirok eting")}</div>
            <div className="divider" style={{ margin: "12px 0" }} />
            <div className="row between">
              <span className="mut sm">{tour.players_count} / {tour.max_players} {t("ishtirokchi")}</span>
              <button className="btn small">{tour.joined ? t("Batafsil") : t("Qatnashish")}</button>
            </div>
          </div>
        ) : (
          <div className="hero">
            <span className="badge g">● VAYNEXO</span>
            <div className="hf bb" style={{ fontSize: 20, margin: "12px 0 4px" }}>{trade.length ? t("Donat, akkaunt va xizmatlar — bir joyda") : t("Donat — tez va ishonchli")}</div>
            <div className="mut sm">{trade.length ? t("Har bir xarid garant bilan himoyalangan") : t("O'yinni tanlang, ID kiriting — qolganini biz bajaramiz")}</div>
          </div>
        )}

        <div className="row grow input" style={{ height: 52, borderRadius: 26, padding: "0 6px 0 16px" }}>
          <span className="mut"><Icon name="search" /></span>
          <input className="grow" style={{ background: "none", border: 0, outline: "none", height: "100%" }} placeholder={t("O'yin qidirish...")} value={q} onChange={(e) => setQ(e.target.value)} />
        </div>

        <Loadable state={games}>
          {(d) => q.trim() ? (
            found.length === 0 ? <div className="mut center sm">{t("Topilmadi")}</div> : (
              <div className="game-grid">{found.map((g) => <MiniGame key={g.slug} g={g} onOpen={open} />)}</div>
            )
          ) : (
            <>
              {d.featured.length > 0 && (
                <>
                  <div className="sec-title">{t("Asosiy o'yinlar")}</div>
                  <div className="feat-grid">
                    {d.featured.map((g) => (
                      <div key={g.slug} className={"card click feat" + (g.available ? "" : " soon")} onClick={() => open(g)}>
                        <div className="feat-img">
                          <GameTile name={g.name} logo={g.hero || g.logo} slug={g.slug} size={96} radius={14} />
                          <span className="badge y" style={{ position: "absolute", top: 6, right: 6, background: g.available ? "var(--y)" : "rgba(255,255,255,.18)", color: g.available ? "#111" : "#fff", fontSize: 9 }}>{g.available ? "DONAT" : t("Tez kunda")}</span>
                        </div>
                        <div className="b ell" style={{ marginTop: 8, fontSize: 13 }}>{g.name}</div>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {d.popular.length > 0 && (
                <>
                  <div className="sec-title">{t("Mashhur o'yinlar")}</div>
                  <div className="game-grid">{d.popular.map((g) => <MiniGame key={g.slug} g={g} onOpen={open} />)}</div>
                </>
              )}
            </>
          )}
        </Loadable>

        <div className="card row between">
          <div className="row">
            <Art name="wallet" size={44} />
            <div>
              <div className="mut xs mono">{t("BALANS")}</div>
              <div className="bb" style={{ fontSize: 18 }}>{som(me?.balance ?? 0)}</div>
            </div>
          </div>
          <button className="btn small ghost" onClick={() => nav("/wallet")}>+ {t("To'ldirish")}</button>
        </div>

        <VayStrip />

        {me?.shop && (
          <div className="card row shop-banner">
            <span style={{ fontSize: 26 }}>🏪</span>
            <div><div className="b">{me.shop.name}</div><div className="mut xs">{me.shop.tagline || t("sizga tavsiya qilgan do'kon")}</div></div>
          </div>
        )}

        <PremiumTiles />

        <div className="card click row between" onClick={() => nav("/shop")}>
          <div className="row"><span style={{ fontSize: 30 }}>🏪</span>
            <div><div className="b">{t("O'z do'koningni och")}</div><div className="mut xs">{t("Do'stlaring xarididan komissiya ol")}</div></div>
          </div>
          <span className="mono y b">3–6% ›</span>
        </div>

        {f.top && (
          <div className="card click row between" onClick={() => nav("/top")}>
            <div className="row">
              <Art name="top" size={44} />
              <div>
                <div className="b">{t("Top xaridorlar")}</div>
                <div className="mut xs">{t("Botda eng ko'p xarid qilganlar reytingi")}</div>
              </div>
            </div>
            <span className="mono y b">Top 100 ›</span>
          </div>
        )}

        {f.market && (
          <div className="card click row between" onClick={() => nav("/sell")}>
            <div className="row">
              <Art name="sell" size={44} />
              <div>
                <div className="b">{t("E'lon berish")}</div>
                <div className="mut xs">{t("Account sotish uchun e'lon joylang")}</div>
              </div>
            </div>
            <span className="y"><Icon name="right" /></span>
          </div>
        )}

      </div>
      <BottomNav />
    </>
  );
}

function MiniGame({ g, onOpen }: { g: DonateGameCard; onOpen: (g: DonateGameCard) => void }) {
  return (
    <button className={"mini-game" + (g.available ? "" : " soon")} onClick={() => onOpen(g)}>
      <GameTile name={g.name} logo={g.logo || g.hero} slug={g.slug} size={64} radius={16} />
      <span className="mg-name ell">{g.name}</span>
      {!g.available && <span className="mg-soon">{t("Tez kunda")}</span>}
    </button>
  );
}

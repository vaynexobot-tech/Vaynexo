import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type DonateGameCard, type DonateGames } from "../api";
import { t } from "../i18n";
import { tgPhoto } from "../tg";
import { BalancePill, BottomNav, GameTile, Icon, Loadable, som, useApp, useLoad } from "../ui";

export default function Home() {
  const nav = useNavigate();
  const { me, toast } = useApp();
  const [q, setQ] = useState("");
  const games = useLoad(() => api.get<DonateGames>("/donate/games"));
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
        <div className="hero">
          <span className="badge g">● VAYNEXO</span>
          <div className="hf bb" style={{ fontSize: 20, margin: "12px 0 4px" }}>{t("Donat — tez va ishonchli")}</div>
          <div className="mut sm">{t("O'yinni tanlang, ID kiriting — qolganini biz bajaramiz")}</div>
        </div>

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
            <div className="iconbtn" style={{ width: 44, height: 44, background: "rgba(255,214,10,.1)", borderColor: "rgba(255,214,10,.3)" }}><Icon name="wallet" /></div>
            <div>
              <div className="mut xs mono">{t("BALANS")}</div>
              <div className="bb" style={{ fontSize: 18 }}>{som(me?.balance ?? 0)}</div>
            </div>
          </div>
          <button className="btn small ghost" onClick={() => nav("/wallet")}>+ {t("To'ldirish")}</button>
        </div>
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

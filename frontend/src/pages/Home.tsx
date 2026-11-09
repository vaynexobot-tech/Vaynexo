import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Tournament } from "../api";
import { t } from "../i18n";
import { tgPhoto } from "../tg";
import { BalancePill, BottomNav, Icon, money, som, useApp, useLoad } from "../ui";

export default function Home() {
  const nav = useNavigate();
  const { me } = useApp();
  const [q, setQ] = useState("");
  const home = useLoad(() => api.get<{ balance: number; tickets: number; tournament: Tournament | null }>("/home"));
  const tour = home.data?.tournament;
  const photo = tgPhoto();

  return (
    <>
      <div className="hd">
        <div className="row">
          <div className="hf" style={{ width: 36, height: 36, borderRadius: 10, background: "var(--y)", color: "#111", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700 }}>VX</div>
          <div>
            <div className="row" style={{ gap: 6 }}>
              <span className="hf bb" style={{ fontSize: 17, letterSpacing: ".03em" }}>VAYNEXO</span>
              <span className="badge y mono" style={{ height: 18, fontSize: 9 }}>MINI</span>
            </div>
            <div className="mut xs">{t("Raqamli o'yin bozori")}</div>
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
          <div className="hero">
            <div className="row between">
              <span className="badge g">● {t("KONKURS")}</span>
              <span className="mono y bb">{money(tour.prize_fund)} UZS</span>
            </div>
            <div className="hf bb" style={{ fontSize: 20, margin: "12px 0 4px" }}>{tour.title}</div>
            <div className="mut sm">{t("Har bir donat va xarid uchun bonus biletlar beriladi")} · {t("Sizda {n} bilet", { n: me?.tickets ?? 0 })}</div>
            <div className="divider" style={{ margin: "12px 0" }} />
            <div className="row between">
              <span className="mut sm">{tour.players_count} / {tour.max_players} {t("ishtirokchi")}</span>
              <button className="btn small" onClick={() => nav(`/arena/${tour.id}`)}>{tour.joined ? t("Batafsil") : t("Qatnashish")}</button>
            </div>
          </div>
        ) : (
          <div className="hero">
            <span className="badge g">● VAYNEXO</span>
            <div className="hf bb" style={{ fontSize: 20, margin: "12px 0 4px" }}>{t("Donat, akkaunt va xizmatlar — bir joyda")}</div>
            <div className="mut sm">{t("Har bir xarid garant bilan himoyalangan")}</div>
          </div>
        )}

        <form className="row" onSubmit={(e) => { e.preventDefault(); nav(`/market?q=${encodeURIComponent(q)}`); }}>
          <div className="row grow input" style={{ height: 52, borderRadius: 26, padding: "0 6px 0 16px" }}>
            <span className="mut"><Icon name="search" /></span>
            <input className="grow" style={{ background: "none", border: 0, outline: "none", height: "100%" }} placeholder={t("Akkaunt qidirish...")} value={q} onChange={(e) => setQ(e.target.value)} />
            <button type="button" className="iconbtn" style={{ borderRadius: 20 }} onClick={() => nav("/market?filter=1")} aria-label={t("Filtr")}><Icon name="filter" /></button>
          </div>
        </form>

        <div>
          <div className="sec-title">{t("Bo'limlar")}</div>
          <div className="mut sm">{t("Donat uchun o'yinni tanlang")}</div>
        </div>
        <div className="grid2">
          {(["ML", "MC"] as const).map((g) => (
            <div key={g} className="card click" style={{ padding: 10 }} onClick={() => nav(`/donate/${g}`)}>
              <div className={"game-tile glogo " + g} style={{ width: "100%", height: 100, borderRadius: 14 }}>
                <span className="badge y" style={{ position: "absolute", top: 8, right: 8, background: "var(--y)", color: "#111" }}>DONAT</span>
                <span className="big">{g}</span>
              </div>
              <div className="b" style={{ marginTop: 10 }}>{g === "ML" ? "Mobile Legends" : "Magic Chess"}</div>
              <div className="row between"><span className="g xs b">{t("Almaz")}</span><span className="y"><Icon name="right" size={16} /></span></div>
            </div>
          ))}
        </div>

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

        <div className="grid2">
          <QuickTile icon="bag" title={t("Account savdo")} sub={t("Tayyor akkauntlar")} onClick={() => nav("/market")} />
          <QuickTile icon="rocket" title={t("Boost")} sub={t("Rank ko'tarish")} onClick={() => nav("/boost")} />
          <QuickTile icon="star" title={t("TG xizmatlar")} sub="Premium · Stars" onClick={() => nav("/tg")} />
          <QuickTile icon="doc" title={t("E'lon berish")} sub={t("Akkaunt sotish")} onClick={() => nav("/sell")} />
        </div>

        <div className="card click row between" onClick={() => nav("/top")}>
          <div className="row">
            <div className="iconbtn" style={{ width: 44, height: 44 }}><Icon name="trophy" /></div>
            <div>
              <div className="b">{t("Top donaterlar")}</div>
              <div className="mut xs">{t("Top 100 reytingi va yutuqlar")}</div>
            </div>
          </div>
          <span className="mono y b">Top 100 ›</span>
        </div>
      </div>
      <BottomNav />
    </>
  );
}

function QuickTile({ icon, title, sub, onClick }: { icon: string; title: string; sub: string; onClick: () => void }) {
  return (
    <div className="card click" onClick={onClick}>
      <span className="y"><Icon name={icon} size={22} /></span>
      <div className="b" style={{ marginTop: 8 }}>{title}</div>
      <div className="mut xs">{sub}</div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type DonateOrder, type Pkg } from "../api";
import { t } from "../i18n";
import { BottomBar, Field, GameLogo, Header, Loadable, money, som, Status, useAction, useApp, useLoad } from "../ui";

export default function Donate() {
  const game = useParams().game === "MC" ? "MC" : "ML";
  const nav = useNavigate();
  const { me, refreshMe } = useApp();
  const [step, setStep] = useState(1);
  const [uid, setUid] = useState(() => (game === "ML" ? me?.ml_id ?? "" : ""));
  const [zid, setZid] = useState("");
  const [nick, setNick] = useState<string | null>(null);
  const [pick, setPick] = useState<Pkg | null>(null);
  const [order, setOrder] = useState<DonateOrder | null>(null);
  const pkgs = useLoad(() => api.get<Pkg[]>(`/donate/packages?game=${game}`), [game]);
  const { busy, run } = useAction();
  const needZone = game === "ML";
  const idOk = /^\d{5,20}$/.test(uid) && (!needZone || /^\d{1,10}$/.test(zid));

  // Buyurtma natijasini kuzatish
  useEffect(() => {
    if (!order || order.status !== "processing") return;
    const id = setInterval(async () => {
      try {
        const o = await api.get<DonateOrder>(`/donate/orders/${order.id}`);
        if (o.status !== "processing") {
          setOrder(o);
          refreshMe();
        }
      } catch {
        /* keyingi safar */
      }
    }, 3000);
    return () => clearInterval(id);
  }, [order, refreshMe]);

  const checkPlayer = () =>
    run(async () => {
      const r = await api.post<{ found: boolean; nickname: string | null }>("/donate/check-player", { game, player_id: uid, zone_id: zid });
      setNick(r.found ? r.nickname || "✓" : "");
      if (r.found) setStep(2);
    });

  const pay = () =>
    run(async () => {
      const o = await api.post<DonateOrder>("/donate/orders", { package_id: pick!.id, player_id: uid, zone_id: zid });
      setOrder(o);
      setStep(4);
      await refreshMe();
    });

  const balance = me?.balance ?? 0;
  const enough = pick ? balance >= pick.price : false;
  const steps = [t("ID"), t("Paket"), t("To'lov"), t("Tasdiq")];

  return (
    <>
      <Header title={game === "ML" ? "Mobile Legends" : "Magic Chess"} sub={t("Almaz donat")} />
      <div className="page">
        <div className="card row" style={{ background: "linear-gradient(135deg,#0f2a3a,#1a1b2e)" }}>
          <GameLogo game={game} />
          <div>
            <div className="b">{t("Almaz to'ldirish")}</div>
            <div className="mut xs">⚡ {t("5–30 daqiqada")} · 🔒 {t("Kafolatlangan")}</div>
          </div>
        </div>

        <div className="steps">
          {steps.map((s, i) => (
            <div key={s} style={{ display: "contents" }}>
              {i > 0 && <div className="ln" />}
              <div className={"step" + (step === i + 1 ? " on" : step > i + 1 ? " done" : "")}><i>{step > i + 1 ? "✓" : i + 1}</i>{s}</div>
            </div>
          ))}
        </div>

        {step === 1 && (
          <>
            <div>
              <div className="sec-title">{t("O'yinchi ID'sini kiriting")}</div>
              <div className="mut sm">{t("Almaz shu akkauntga tushadi")}</div>
            </div>
            <div className="row" style={{ alignItems: "flex-end" }}>
              <div className="grow"><Field label="User ID"><input className="input mono" inputMode="numeric" placeholder="12345678" value={uid} onChange={(e) => { setUid(e.target.value.replace(/\D/g, "").slice(0, 20)); setNick(null); }} /></Field></div>
              {needZone && <div style={{ width: 120 }}><Field label="Zone ID"><input className="input mono" inputMode="numeric" placeholder="1234" value={zid} onChange={(e) => { setZid(e.target.value.replace(/\D/g, "").slice(0, 10)); setNick(null); }} /></Field></div>}
            </div>
            {nick === "" && (
              <div className="card tight col">
                <div className="r sm">{t("O'yinchi topilmadi. ID va Zone ID ni tekshiring.")}</div>
                <button className="btn small ghost" onClick={() => setStep(2)}>{t("ID to'g'ri, davom etish")}</button>
              </div>
            )}
            <div className="card tight mut sm">ℹ️ {t("O'yinda chap yuqoridagi profil rasmingizni bosing — ID va Zone ID qavs ichida yozilgan: 12345678 (1234)")}</div>
          </>
        )}

        {step === 2 && (
          <>
            {nick && <div className="card tight row"><span className="g">✓</span><span className="sm">{nick !== "✓" ? <>{t("O'yinchi")}: <b>{nick}</b> · </> : <>ID: </>}<b>{uid}{zid ? ` (${zid})` : ""}</b></span></div>}
            <div className="sec-title">{t("Paketni tanlang")}</div>
            <Loadable state={pkgs}>
              {(list) => (
                <div className="grid3">
                  {list.map((p) => (
                    <button key={p.id} className={"pkg" + (pick?.id === p.id ? " on" : "")} onClick={() => setPick(p)}>
                      {p.is_hot && <span className="badge y hot" style={{ background: "var(--y)", color: "#111" }}>HOT</span>}
                      <div className="bb" style={{ fontSize: 15 }}>💎 {p.name.replace(/ almaz$/, "")}</div>
                      {p.bonus > 0 && <div className="g xs">{p.diamonds}+{p.bonus} bonus</div>}
                      {p.diamonds === 0 && <div className="mut xs">&nbsp;</div>}
                      <div className="y b mono sm" style={{ marginTop: 6 }}>{money(p.price)}</div>
                    </button>
                  ))}
                </div>
              )}
            </Loadable>
          </>
        )}

        {step === 3 && pick && (
          <div className="card col">
            <div className="b">{t("Buyurtma")}</div>
            <div className="kv"><span>{t("O'yin")}</span><span>{game === "ML" ? "Mobile Legends" : "Magic Chess"}</span></div>
            <div className="kv"><span>{t("Paket")}</span><span>💎 {pick.name}</span></div>
            <div className="kv"><span>ID</span><span className="mono">{uid}{zid ? ` (${zid})` : ""}</span></div>
            {nick && nick !== "✓" && <div className="kv"><span>{t("Nik")}</span><span>{nick}</span></div>}
            <div className="divider" />
            <div className="kv"><span>{t("To'lov usuli")}</span><span>{t("Hamyon balansi")}</span></div>
            <div className="kv"><span>{t("Balans")}</span><span className={enough ? "" : "r"}>{som(balance)}</span></div>
            <div className="kv"><span>{t("Jami")}</span><span className="y" style={{ fontSize: 18 }}>{som(pick.price)}</span></div>
            {!enough && (
              <div className="card tight r sm">
                {t("Balansda {s} yetishmaydi.", { s: som(pick.price - balance) })}{" "}
                <button className="btn small" style={{ marginTop: 8 }} onClick={() => nav("/wallet")}>{t("Hamyonni to'ldirish")}</button>
              </div>
            )}
          </div>
        )}

        {step === 4 && order && (
          <div className="card col center" style={{ alignItems: "center", padding: 24 }}>
            <div style={{ fontSize: 48 }}>{order.status === "done" ? "💎" : order.status === "refunded" ? "↩️" : "⏳"}</div>
            <div className="bb" style={{ fontSize: 18 }}>
              {order.status === "done" ? t("Almaz yetkazildi!") : order.status === "refunded" ? t("Pul hamyonga qaytarildi") : t("Buyurtma bajarilmoqda...")}
            </div>
            <Status s={order.status} />
            <div className="mut sm">{order.title} · ID {order.player_id}{order.zone_id ? ` (${order.zone_id})` : ""}</div>
            <div className="mut xs mono">{order.ref}</div>
            {order.status === "refunded" && <div className="mut sm">{t("Provayder buyurtmani bajara olmadi. ID to'g'riligini tekshirib, qayta urinib ko'ring.")}</div>}
            {order.status === "review" && <div className="mut sm">{t("Buyurtma tekshirilmoqda. Natija Telegram orqali xabar qilinadi.")}</div>}
          </div>
        )}
      </div>

      <BottomBar>
        {step < 4 ? (
          <>
            <div className="grow">
              <div className="mut xs">{t("{n}-qadam", { n: step })} · {steps[step - 1]}</div>
              <div className="bb mono y" style={{ fontSize: 18 }}>{money(pick?.price ?? 0)} <span className="mut xs">{t("so'm")}</span></div>
            </div>
            {step === 1 && <button className="btn" disabled={!idOk || busy} onClick={checkPlayer}>{t("Davom etish")}</button>}
            {step === 2 && <button className="btn" disabled={!pick} onClick={() => setStep(3)}>{t("Davom etish")}</button>}
            {step === 3 && <button className="btn" disabled={!enough || busy} onClick={pay}>{t("To'lash")}</button>}
          </>
        ) : (
          <>
            <button className="btn ghost grow" onClick={() => nav("/history")}>{t("Tarix")}</button>
            <button className="btn grow" onClick={() => { setStep(2); setOrder(null); setPick(null); }}>{t("Yana olish")}</button>
          </>
        )}
      </BottomBar>
    </>
  );
}

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type DonateGameCard, type DonateGameField, type DonateOrder, type Pkg } from "../api";
import { t } from "../i18n";
import { BottomBar, Empty, Field, GameTile, Header, Loadable, money, som, Spinner, Status, useAction, useApp, useLoad } from "../ui";

const DEFAULT_FIELDS: DonateGameField[] = [{ key: "player_id", label: "ID", placeholder: "12345678", pattern: "" }];

export default function Donate() {
  const slug = useParams().game ?? "ML";
  const info = useLoad(() => api.get<DonateGameCard>(`/donate/games/${encodeURIComponent(slug)}`), [slug]);
  if (info.error) return <><Header title={t("O'yin")} /><Empty icon="🎮" text={t("O'yin topilmadi")} /></>;
  if (!info.data) return <><Header title={t("Donat")} /><Spinner /></>;
  return <DonateFlow key={slug} game={info.data} />;
}

function DonateFlow({ game: g }: { game: DonateGameCard }) {
  const game = g.slug;
  const fields = g.fields.length ? g.fields : DEFAULT_FIELDS;
  const nav = useNavigate();
  const { me, refreshMe } = useApp();
  const [step, setStep] = useState(1);
  const [uid, setUid] = useState(() => (game === "ML" ? me?.ml_id ?? "" : ""));
  const [zid, setZid] = useState("");
  const [nick, setNick] = useState<string | null>(null);
  const [pick, setPick] = useState<Pkg | null>(null);
  const [order, setOrder] = useState<DonateOrder | null>(null);
  const pkgs = useLoad(() => api.get<Pkg[]>(`/donate/packages?game=${encodeURIComponent(game)}`), [game]);
  const { busy, run } = useAction();
  const needZone = fields.length > 1;
  const okPattern = (f: DonateGameField, v: string) => {
    if (!v.trim()) return false;
    if (!f.pattern) return /^[A-Za-z0-9_.@:+-]{1,64}$/.test(v.trim());
    try { return new RegExp(f.pattern).test(v.trim()); } catch { return true; }
  };
  const idOk = okPattern(fields[0], uid) && (!needZone || okPattern(fields[1], zid));

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
      <Header title={g.name} sub={t("Donat")} />
      <div className="page">
        <div className="card row" style={{ background: "linear-gradient(135deg,#0f2a3a,#1a1b2e)" }}>
          <GameTile name={g.name} logo={g.logo || g.hero} slug={g.slug} size={44} radius={12} />
          <div>
            <div className="b">{t("Hisobni to'ldirish")}</div>
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
              <div className="mut sm">{t("Donat shu akkauntga tushadi")}</div>
            </div>
            <div className="row" style={{ alignItems: "flex-end" }}>
              <div className="grow"><Field label={fields[0].label || "ID"}><input className="input mono" inputMode={fields[0].pattern?.includes("\\d") ? "numeric" : "text"} autoCapitalize="off" placeholder={fields[0].placeholder || ""} value={uid} onChange={(e) => { setUid(e.target.value.replace(/\s/g, "").slice(0, 64)); setNick(null); }} /></Field></div>
              {needZone && <div style={{ width: 120 }}><Field label={fields[1].label || "Server"}><input className="input mono" inputMode={fields[1].pattern?.includes("\\d") ? "numeric" : "text"} placeholder={fields[1].placeholder || ""} value={zid} onChange={(e) => { setZid(e.target.value.replace(/\s/g, "").slice(0, 64)); setNick(null); }} /></Field></div>}
            </div>
            {nick === "" && (
              <div className="card tight col">
                <div className="r sm">{t("O'yinchi topilmadi. ID ni tekshiring.")}</div>
                <button className="btn small ghost" onClick={() => setStep(2)}>{t("ID to'g'ri, davom etish")}</button>
              </div>
            )}
            {game === "ML" && <div className="card tight mut sm">ℹ️ {t("O'yinda chap yuqoridagi profil rasmingizni bosing — ID va Zone ID qavs ichida yozilgan: 12345678 (1234)")}</div>}
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
                      <div className="bb" style={{ fontSize: p.name.length > 14 ? 12 : 15, lineHeight: 1.2 }}>{/almaz$/.test(p.name) ? `💎 ${p.name.replace(/ almaz$/, "")}` : p.name}</div>
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
            <div className="kv"><span>{t("O'yin")}</span><span>{g.name}</span></div>
            <div className="kv"><span>{t("Paket")}</span><span>{pick.name}</span></div>
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
              {order.status === "done" ? t("Yetkazildi!") : order.status === "refunded" ? t("Pul hamyonga qaytarildi") : t("Buyurtma bajarilmoqda...")}
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

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Boost as BoostT } from "../api";
import { t } from "../i18n";
import { confirmDialog } from "../tg";
import { BottomBar, Chips, dateTime, Empty, Field, Header, Loadable, money, Seg, Sheet, som, Status, useAction, useApp, useLoad } from "../ui";

const DIVS = ["V", "IV", "III", "II", "I"];
const LANES = ["Gold", "Mid", "EXP", "Jungle", "Roam"];
const METHODS = [
  { v: "telegram", label: "Telegram", sub: "Booster siz bilan Telegram orqali bog'lanadi" },
  { v: "moonton", label: "Moonton ID", sub: "Email va parol" },
  { v: "google", label: "Google", sub: "Google hisobi orqali kirish" },
  { v: "whatsapp", label: "WhatsApp", sub: "Booster WhatsApp orqali bog'lanadi" },
];

export function Boost() {
  const nav = useNavigate();
  const { me, refreshMe } = useApp();
  const [game, setGame] = useState<"ML" | "MC">("ML");
  const [cur, setCur] = useState("Epic");
  const [div, setDiv] = useState("V");
  const [curStars, setCurStars] = useState(0);
  const [target, setTarget] = useState("Mythic");
  const [stars, setStars] = useState(10);
  const [lane, setLane] = useState("");
  const [note, setNote] = useState("");
  const [method, setMethod] = useState("telegram");
  const [creds, setCreds] = useState("");
  const [quote, setQuote] = useState<{ price: number; stars: number; days: string } | null>(null);
  const [qErr, setQErr] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const { busy, run } = useAction();

  const body = { game, current_rank: cur, current_division: div, current_stars: curStars, target_rank: target, target_stars: stars, lane, note, login_method: method, credentials: creds };

  useEffect(() => {
    const id = setTimeout(async () => {
      try {
        setQuote(await api.post("/boost/quote", body));
        setQErr(null);
      } catch (e) {
        setQuote(null);
        setQErr(e instanceof Error ? e.message : "");
      }
    }, 250);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cur, div, curStars, target, stars]);

  const targets = ["Legend", "Mythic", "M. Glory"].filter((x) => !(cur === "Legend" && x === "Legend") && !(cur === "Mythic" && x === "Legend"));
  useEffect(() => { if (!targets.includes(target)) setTarget(targets[0]); }, [cur]); // eslint-disable-line react-hooks/exhaustive-deps
  const needCreds = method === "moonton" || method === "google";
  const enough = quote ? (me?.balance ?? 0) >= quote.price : false;

  return (
    <>
      <Header title={t("Boost xizmati")} sub={t("Rank ko'tarish xizmati")} />
      <div className="page">
        <div className="row between">
          <button className="chip" onClick={() => nav("/boosts")}>{t("Mening buyurtmalarim")}</button>
        </div>
        <Seg value={game} onChange={setGame} options={[{ v: "ML", label: "Mobile Legends" }, { v: "MC", label: "Magic Chess" }]} />
        <div className="card col">
          <div className="b">{t("Hozirgi rank")}</div>
          <Chips value={cur} onChange={setCur} options={["Epic", "Legend", "Mythic"].map((v) => ({ v, label: v }))} />
          {cur !== "Mythic" ? (
            <Field label={t("Daraja")}><Chips value={div} onChange={setDiv} options={DIVS.map((v) => ({ v, label: v }))} /></Field>
          ) : (
            <Field label={t("Hozirgi yulduzlar")}><Counter value={curStars} onChange={setCurStars} min={0} /></Field>
          )}
        </div>
        <div className="card col">
          <div className="b">{t("Kerakli rank")}</div>
          <Chips value={target} onChange={setTarget} options={targets.map((v) => ({ v, label: v }))} />
          {target !== "Legend" && (
            <Field label={t("Nechta yulduzgacha?")}>
              <Counter value={stars} onChange={setStars} min={target === "M. Glory" ? 50 : 1} />
            </Field>
          )}
        </div>
        <Field label={t("Liniya (ixtiyoriy)")}><Chips value={lane} onChange={(v) => setLane(lane === v ? "" : v)} options={LANES.map((v) => ({ v, label: v }))} /></Field>
        <Field label={t("Izoh booster uchun")}><textarea className="input" maxLength={500} placeholder={t("Masalan: shu qahramonda o'ynab bering")} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        {qErr && <div className="r sm">{qErr}</div>}
        {quote && (
          <div className="card">
            <div className="kv"><span>{t("Xizmat")}</span><span>{cur}{cur === "Mythic" ? ` ${curStars}★` : ` ${div}`} → {target}{target !== "Legend" ? ` ${stars}★` : " I"}</span></div>
            <div className="kv"><span>{t("Yulduzlar")}</span><span>{quote.stars}</span></div>
            <div className="kv"><span>{t("Taxminiy muddat")}</span><span>{t("{d} kun", { d: quote.days })}</span></div>
          </div>
        )}
      </div>
      <BottomBar>
        <div className="grow"><div className="mut xs">{t("Jami narx")}</div><div className="y bb mono" style={{ fontSize: 18 }}>{quote ? som(quote.price) : "—"}</div></div>
        <button className="btn" disabled={!quote} onClick={() => setConfirm(true)}>{t("Davom etish")}</button>
      </BottomBar>
      <Sheet open={confirm} onClose={() => setConfirm(false)}>
        <div className="sec-title">{t("Kirish usuli")}</div>
        <div className="col">
          {METHODS.map((m) => (
            <button key={m.v} className={"pkg" + (method === m.v ? " on" : "")} onClick={() => setMethod(m.v)}>
              <div className="b">{m.label}</div><div className="mut xs">{t(m.sub)}</div>
            </button>
          ))}
        </div>
        {needCreds && (
          <Field label={t("Kirish ma'lumotlari")}>
            <textarea className="input" maxLength={500} placeholder={"ID / email\nparol"} value={creds} onChange={(e) => setCreds(e.target.value)} />
            <div className="mut xs">🔒 {t("Shifrlangan holda saqlanadi, faqat buyurtmani olgan boosterga ko'rsatiladi va ish tugagach o'chiriladi. Ish tugagach parolni almashtiring.")}</div>
          </Field>
        )}
        <div className="kv"><span>{t("Jami")}</span><span className="y">{quote ? som(quote.price) : ""}</span></div>
        <div className="kv"><span>{t("Balans")}</span><span className={enough ? "" : "r"}>{som(me?.balance ?? 0)}</span></div>
        {enough ? (
          <button className="btn full" disabled={busy || (needCreds && creds.trim().length < 3)} onClick={() => run(async () => {
            const o = await api.post<BoostT>("/boost/orders", body);
            await refreshMe();
            nav(`/boost/${o.id}`, { replace: true });
          })}>{t("Buyurtmani tasdiqlash")} · {quote ? money(quote.price) : ""}</button>
        ) : (
          <button className="btn full" onClick={() => nav("/wallet")}>{t("Balansni to'ldirish")}</button>
        )}
      </Sheet>
    </>
  );
}

function Counter({ value, onChange, min }: { value: number; onChange: (v: number) => void; min: number }) {
  return (
    <div className="row">
      <button className="iconbtn" onClick={() => onChange(Math.max(min, value - 1))}>−</button>
      <input className="input mono center" style={{ width: 90 }} inputMode="numeric" value={value} onChange={(e) => onChange(Math.max(0, Math.min(300, Number(e.target.value.replace(/\D/g, "")) || 0)))} onBlur={() => onChange(Math.max(min, value))} />
      <button className="iconbtn" onClick={() => onChange(Math.min(300, value + 1))}>+</button>
      <span className="mut sm">★</span>
    </div>
  );
}

export function BoostOrders() {
  const nav = useNavigate();
  const st = useLoad(() => api.get<BoostT[]>("/boost/orders"));
  return (
    <>
      <Header title={t("Boost buyurtmalarim")} />
      <div className="page">
        <Loadable state={st}>
          {(list) => list.length === 0 ? <Empty icon="🚀" text={t("Buyurtmalar yo'q")}><button className="btn small" onClick={() => nav("/boost")}>{t("Boost buyurtma qilish")}</button></Empty> : list.map((o) => (
            <div key={o.id} className="card click" onClick={() => nav(`/boost/${o.id}`)}>
              <div className="row between"><span className="b">{o.current_rank} → {o.target_rank}</span><Status s={o.status} /></div>
              <div className="mut xs">{o.ref} · {dateTime(o.created_at)} · {som(o.price)}</div>
            </div>
          ))}
        </Loadable>
      </div>
    </>
  );
}

export function BoostOrderPage() {
  const id = useParams().id;
  const { refreshMe, toast } = useApp();
  const st = useLoad(() => api.get<BoostT>(`/boost/orders/${id}`), [id]);
  const [dispute, setDispute] = useState(false);
  const [reason, setReason] = useState("");
  const { busy, run } = useAction();
  const act = (a: string, body: unknown = {}) => run(async () => {
    st.setData(await api.post<BoostT>(`/boost/orders/${id}/${a}`, body));
    setDispute(false);
    toast(t("Bajarildi"), "ok");
    refreshMe();
  });
  const STEPS = ["searching", "accepted", "in_progress", "finished", "done"];
  const LABELS: Record<string, string> = { searching: "Booster qidirilmoqda", accepted: "Booster buyurtmani qabul qildi", in_progress: "Booster ishni boshladi", finished: "Booster ishni tugatdi", done: "Yakunlandi" };
  return (
    <>
      <Header title={t("Boost buyurtma")} />
      <Loadable state={st}>
        {(o) => {
          const idx = STEPS.indexOf(o.status);
          return (
            <>
              <div className="page">
                <div className="card">
                  <div className="row between"><span className="bb">{o.current_rank} → {o.target_rank}</span><Status s={o.status} /></div>
                  <div className="kv"><span>{t("Buyurtma")}</span><span className="mono">{o.ref}</span></div>
                  <div className="kv"><span>{t("Yulduzlar")}</span><span>{o.stars}</span></div>
                  <div className="kv"><span>{t("Liniya")}</span><span>{o.lane || t("Ixtiyoriy")}</span></div>
                  <div className="kv"><span>{t("Summa")}</span><span className="y">{som(o.price)}</span></div>
                  {o.booster_name && <div className="kv"><span>Booster</span><span>{o.booster_name}</span></div>}
                </div>
                <div className="card">
                  {STEPS.map((s, i) => (
                    <div key={s} className="row" style={{ padding: "6px 0", opacity: idx >= i || o.status === "done" ? 1 : 0.4 }}>
                      <span className={"badge " + (idx > i || o.status === "done" ? "g" : idx === i ? "y" : "m")}>{idx > i || o.status === "done" ? "✓" : i + 1}</span>
                      <span className="sm">{t(LABELS[s])}</span>
                    </div>
                  ))}
                </div>
                {o.status === "finished" && <div className="card tight sm">🏁 {t("Booster ishni tugatdi. Akkauntga kirib tekshiring va tasdiqlang.")}</div>}
                {o.status === "disputed" && <div className="card tight sm">⚖️ {t("Nizo ochilgan. Admin bog'lanadi.")}</div>}
              </div>
              <BottomBar>
                {o.status === "searching" && <button className="btn danger full" disabled={busy} onClick={async () => { if (await confirmDialog(t("Buyurtmani bekor qilasizmi? Pul qaytariladi."))) act("cancel"); }}>{t("Bekor qilish")}</button>}
                {["accepted", "in_progress", "finished"].includes(o.status) && <button className="btn ghost" onClick={() => setDispute(true)}>{t("Muammo bor")}</button>}
                {o.status === "finished" && <button className="btn green grow" disabled={busy} onClick={() => act("confirm")}>{t("Tasdiqlash")}</button>}
              </BottomBar>
              <Sheet open={dispute} onClose={() => setDispute(false)}>
                <div className="sec-title">{t("Muammoni yozing")}</div>
                <textarea className="input" maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} />
                <button className="btn danger full" disabled={reason.trim().length < 5 || busy} onClick={() => act("dispute", { reason })}>{t("Yuborish")}</button>
              </Sheet>
            </>
          );
        }}
      </Loadable>
    </>
  );
}

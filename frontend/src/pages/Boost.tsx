import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Boost as BoostT } from "../api";
import { t } from "../i18n";
import { confirmDialog } from "../tg";
import { BottomBar, BottomNav, Chips, dateTime, Empty, Field, Header, Loadable, money, Seg, Sheet, som, Status, Toggle, useAction, useApp, useLoad } from "../ui";

const DIVS = ["V", "IV", "III", "II", "I"];
const LANES = ["Gold", "Mid", "EXP", "Jungle", "Roam"];
const METHODS = [
  { v: "telegram", label: "Telegram", sub: "Booster siz bilan Telegram orqali bog'lanadi" },
  { v: "moonton", label: "Moonton ID", sub: "Email va parol" },
  { v: "google", label: "Google", sub: "Google hisobi orqali kirish" },
  { v: "whatsapp", label: "WhatsApp", sub: "Booster WhatsApp orqali bog'lanadi" },
];

interface Quote { base: number; price: number; stars: number; days: string; extras: { key: string; label: string; percent: number; amount: number }[]; percents: Record<string, number> }

export function Boost() {
  const nav = useNavigate();
  const { me, refreshMe } = useApp();
  const [game, setGame] = useState<"ML" | "MC">("ML");
  const [cur, setCur] = useState("Epic");
  const [div, setDiv] = useState("V");
  const [curStars, setCurStars] = useState(0);
  const [target, setTarget] = useState("Mythic");
  const [stars, setStars] = useState(10);
  const [express, setExpress] = useState(false);
  const [extra, setExtra] = useState(false);
  const [heroOn, setHeroOn] = useState(false);
  const [hero, setHero] = useState("");
  const [laneOn, setLaneOn] = useState(false);
  const [lane, setLane] = useState("");
  const [note, setNote] = useState("");
  const [method, setMethod] = useState("telegram");
  const [creds, setCreds] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [qErr, setQErr] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const { busy, run } = useAction();

  const body = {
    game, current_rank: cur, current_division: div, current_stars: curStars, target_rank: target, target_stars: stars, express,
    hero: extra && heroOn ? hero.trim() : "", lane: extra && laneOn ? lane : "", note, login_method: method, credentials: creds,
  };

  useEffect(() => {
    const id = setTimeout(async () => {
      try {
        setQuote(await api.post<Quote>("/boost/quote", body));
        setQErr(null);
      } catch (e) {
        setQuote(null);
        setQErr(e instanceof Error ? e.message : "");
      }
    }, 250);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cur, div, curStars, target, stars, express, extra, heroOn, hero, laneOn, lane]);

  const targets = ["Legend", "Mythic", "M. Glory"].filter((x) => !(cur === "Legend" && x === "Legend") && !(cur === "Mythic" && x === "Legend"));
  useEffect(() => { if (!targets.includes(target)) setTarget(targets[0]); }, [cur]); // eslint-disable-line react-hooks/exhaustive-deps
  const needCreds = method === "moonton" || method === "google";
  const enough = quote ? (me?.balance ?? 0) >= quote.price : false;
  const pct = quote?.percents ?? {};
  const extraInvalid = extra && ((heroOn && hero.trim().length < 2) || (laneOn && !lane));

  return (
    <>
      <Header title={t("Boost xizmati")} sub={t("Rank ko'tarish xizmati")} back={false} icon="bolt" />
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

        <div className="card row between">
          <div>
            <div className="b">⚡ {t("Express boost")} {pct.boost_express_percent != null && <span className="badge y">+{pct.boost_express_percent}%</span>}</div>
            <div className="mut xs">{t("Booster darhol boshlaydi, muddat qisqaradi")}</div>
          </div>
          <Toggle on={express} onChange={setExpress} />
        </div>
        <div className="card col">
          <div className="row between">
            <div>
              <div className="b">➕ {t("Qo'shimcha")}</div>
              <div className="mut xs">{t("Qahramon yoki liniya tanlash (alohida ustama)")}</div>
            </div>
            <Toggle on={extra} onChange={setExtra} />
          </div>
          {extra && (
            <>
              <div className="divider" />
              <div className="row between">
                <div className="b sm">{t("Qahramon tanlash")} {pct.boost_hero_percent != null && <span className="badge y">+{pct.boost_hero_percent}%</span>}</div>
                <Toggle on={heroOn} onChange={setHeroOn} />
              </div>
              {heroOn && <input className="input" maxLength={32} placeholder={t("Qahramon nomi, masalan: Fanny")} value={hero} onChange={(e) => setHero(e.target.value)} />}
              <div className="row between">
                <div className="b sm">{t("Liniya tanlash")} {pct.boost_lane_percent != null && <span className="badge y">+{pct.boost_lane_percent}%</span>}</div>
                <Toggle on={laneOn} onChange={setLaneOn} />
              </div>
              {laneOn && <Chips value={lane} onChange={setLane} options={LANES.map((v) => ({ v, label: v }))} />}
            </>
          )}
        </div>
        <Field label={t("Izoh booster uchun (ixtiyoriy)")}><textarea className="input" maxLength={400} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        {qErr && <div className="r sm">{qErr}</div>}
        {quote && (
          <div className="card">
            <div className="kv"><span>{cur}{cur === "Mythic" ? ` ${curStars}★` : ` ${div}`} → {target}{target !== "Legend" ? ` ${stars}★` : " I"} · {quote.stars}★</span><span>{money(quote.base)}</span></div>
            {quote.extras.map((x) => <div key={x.key} className="kv"><span>{x.label} (+{x.percent}%)</span><span>{money(x.amount)}</span></div>)}
            <div className="kv"><span>{t("Taxminiy muddat")}</span><span>{t("{d} kun", { d: quote.days })}</span></div>
          </div>
        )}
        <div className="card total-card row">
          <div className="grow"><div className="mut xs">{t("Jami narx")}</div><div className="y bb mono" style={{ fontSize: 20 }}>{quote ? som(quote.price) : "—"}</div></div>
          <button className="btn" disabled={!quote || !!extraInvalid} onClick={() => setConfirm(true)}>{t("Buyurtma berish")}</button>
        </div>
      </div>
      <BottomNav />
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
  const LABELS: Record<string, string> = { searching: "Buyurtma berildi", accepted: "Booster topildi", in_progress: "Ish jarayonda", finished: "Booster ishni tugatdi", done: "Tekshirish va tasdiqlash" };
  return (
    <>
      <Header title={t("Boost · jonli progress")} />
      <Loadable state={st}>
        {(o) => {
          const idx = STEPS.indexOf(o.status);
          return (
            <>
              <div className="page">
                <div className="hero col" style={{ gap: 10 }}>
                  <div className="row between"><span className="b">{o.current_rank}</span><span className="y b">{o.target_rank}</span></div>
                  <div className="progress" style={{ height: 10 }}><i style={{ width: Math.round(((o.status === "done" || o.status === "finished" ? o.stars : o.progress_stars ?? 0) / Math.max(1, o.stars)) * 100) + "%", background: "var(--g)" }} /></div>
                  <div className="grid3 center">
                    <div><div className="hf bb" style={{ fontSize: 20 }}>{o.status === "done" || o.status === "finished" ? o.stars : o.progress_stars ?? 0}</div><div className="mut xs">{t("yulduz olindi")}</div></div>
                    <div><div className="hf bb" style={{ fontSize: 20 }}>{o.status === "done" || o.status === "finished" ? 0 : o.stars - (o.progress_stars ?? 0)}</div><div className="mut xs">{t("qoldi")}</div></div>
                    <div><div className="g hf bb" style={{ fontSize: 20 }}>{o.winrate != null ? o.winrate + "%" : "—"}</div><div className="mut xs">{t("win-rate")}</div></div>
                  </div>
                  <div className="row between xs"><span className="mut">{o.ref}</span><Status s={o.status} /></div>
                </div>
                {o.booster_code && (
                  <div className="card row">
                    <div className="seller-ava">B</div>
                    <div className="grow"><div className="b">Booster {o.booster_code} ✓</div><div className="mut xs">{t("Shaxsi maxfiy — aloqa bot orqali")}</div></div>
                  </div>
                )}
                <div className="card">
                  {STEPS.map((s, i) => {
                    const done = idx > i || o.status === "done";
                    const when = s === "accepted" ? o.accepted_at : s === "in_progress" ? o.started_at : s === "searching" ? o.created_at : s === "finished" ? o.finished_at : null;
                    return (
                      <div key={s} className="row" style={{ padding: "7px 0", opacity: idx >= i || o.status === "done" ? 1 : 0.4 }}>
                        <span className={"stepnum" + (done ? " ok" : idx === i ? " on" : "")}>{done ? "✓" : i + 1}</span>
                        <div className="grow"><div className="sm b">{t(LABELS[s])}</div>{when && <div className="mut xs">{dateTime(when)}</div>}
                          {s === "in_progress" && idx === i && <div className="mut xs">{t("{n} / {m} yulduz", { n: o.progress_stars ?? 0, m: o.stars })}</div>}</div>
                      </div>
                    );
                  })}
                </div>
                <div className="card tight xs mut">🔒 {t("Pul garantda. Boost tugagach akkauntni tekshirib, «Tasdiqlash» ni bosing. Muammo bo'lsa «Muammo bor» orqali admin hal qiladi.")}</div>
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

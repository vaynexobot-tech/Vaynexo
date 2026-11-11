import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type ListingCard } from "../api";
import { t } from "../i18n";
import { errorText, GAME_IMG, Header, Icon, money } from "../ui";

interface Msg { role: "user" | "ai"; text: string; listings?: ListingCard[]; error?: boolean }
interface Status { enabled: boolean; limit: number; left: number }

const STORE = "vx_ai_chat";

function loadChat(): Msg[] {
  try {
    const v = JSON.parse(localStorage.getItem(STORE) || "[]");
    return Array.isArray(v) ? v.slice(-30) : [];
  } catch {
    return [];
  }
}

function saveChat(m: Msg[]) {
  try {
    localStorage.setItem(STORE, JSON.stringify(m.slice(-30)));
  } catch {
    /* yo'q */
  }
}

export default function Ai() {
  const nav = useNavigate();
  const [msgs, setMsgs] = useState<Msg[]>(loadChat);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [st, setSt] = useState<Status | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.get<Status>("/ai/status").then(setSt).catch(() => undefined);
  }, []);
  useEffect(() => {
    saveChat(msgs.filter((m) => !m.error));
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, busy]);

  const send = async (q: string) => {
    q = q.trim();
    if (q.length < 2 || busy) return;
    const history = msgs.filter((m) => !m.error).slice(-6).map((m) => ({ role: m.role, text: m.text }));
    setMsgs((m) => [...m, { role: "user", text: q }]);
    setText("");
    setBusy(true);
    try {
      const r = await api.post<{ reply: string; listings: ListingCard[]; left: number }>("/ai/ask", { text: q, history });
      setMsgs((m) => [...m, { role: "ai", text: r.reply, listings: r.listings }]);
      setSt((s) => (s ? { ...s, left: r.left } : s));
    } catch (e) {
      setMsgs((m) => [...m, { role: "ai", text: errorText(e), error: true }]);
    } finally {
      setBusy(false);
    }
  };

  const suggestions = [
    t("Mythic akkaunt, 50+ skin, 500 000 so'mgacha"),
    t("Hamyonni qanday to'ldiraman?"),
    t("Garant qanday ishlaydi?"),
  ];

  return (
    <>
      <Header title={t("AI yordamchi")} sub={t("Aqlli yordamchi")}
        right={st?.enabled ? <span className="ai-left mono">● {t("{n} so'rov", { n: st.left })}</span> : <span />} />
      <div className="page ai-page">
        <div className="ai-row">
          <span className="ai-ava"><Icon name="ai" size={14} /></span>
          <div className="ai-bubble first">{t("Salom! Men VAYNEXO yordamchisiman. Sizga qanday yordam bera olaman?")}</div>
        </div>
        {st && !st.enabled && <div className="note sm">{t("AI bo'limi hali ulanmagan. Tez orada ishga tushadi")}</div>}
        {msgs.length === 0 && st?.enabled && (
          <div className="chips" style={{ flexWrap: "wrap" }}>
            {suggestions.map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}
          </div>
        )}
        {msgs.map((m, i) => m.role === "user" ? (
          <div key={i} className="user-bubble">{m.text}</div>
        ) : (
          <div key={i} className="col" style={{ gap: 8 }}>
            <div className="ai-row">
              <span className="ai-ava"><Icon name="ai" size={14} /></span>
              <div className={"ai-bubble" + (m.error ? " r" : "")}>{m.text}</div>
            </div>
            {m.listings?.map((l, j) => (
              <div key={l.id} className={"ai-card" + (j === 0 ? " best" : "")} onClick={() => nav(`/listing/${l.id}`)}>
                <div className="ai-thumb">{l.cover ? <img src={l.cover} alt="" /> : <img src={GAME_IMG[l.game] ?? GAME_IMG.ML} alt="" />}</div>
                <div className="grow" style={{ minWidth: 0 }}>
                  <div className="b ell">{l.title}</div>
                  <div className="mut xs">{t("Sotuvchi")} {l.seller_rating ? `★ ${l.seller_rating}` : ""} · {t("Garant bor")}</div>
                  <div className="y mono bb" style={{ marginTop: 4 }}>{money(l.price)}</div>
                </div>
                <div className="col" style={{ alignItems: "flex-end", justifyContent: "space-between", alignSelf: "stretch" }}>
                  {j === 0 ? <span className="badge y" style={{ background: "var(--y)", color: "#111" }}>{t("Eng mos")}</span> : <span />}
                  <button className="btn small ghost">{t("Ko'rish")}</button>
                </div>
              </div>
            ))}
          </div>
        ))}
        {busy && (
          <div className="ai-row">
            <span className="ai-ava"><Icon name="ai" size={14} /></span>
            <div className="ai-bubble"><span className="dots"><i /><i /><i /></span></div>
          </div>
        )}
        <div ref={end} />
      </div>
      <form className="ai-input" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input className="grow" placeholder={t("Savol yozing...")} maxLength={500} value={text} onChange={(e) => setText(e.target.value)} disabled={busy || st?.enabled === false} />
        <button type="submit" className="ai-send" disabled={busy || text.trim().length < 2} aria-label={t("Yuborish")}>↑</button>
      </form>
    </>
  );
}

import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Chat, type Msg } from "../api";
import { t } from "../i18n";
import { dateTime, Empty, GameLogo, Header, Icon, Loadable, som, Spinner, Status, useApp, useLoad } from "../ui";

export function Chats() {
  const nav = useNavigate();
  const st = useLoad(() => api.get<Chat[]>("/chats"));
  return (
    <>
      <Header title={t("Chatlar")} />
      <div className="page">
        <Loadable state={st}>
          {(list) => list.length === 0 ? <Empty icon="💬" text={t("Hali chatlar yo'q")} /> : (
            <div className="card">
              {list.map((c) => (
                <div key={c.id} className="listrow" style={{ cursor: "pointer" }} onClick={() => nav(`/chat/${c.id}`)}>
                  <GameLogo game={c.listing.game} size={40} />
                  <div className="grow">
                    <div className="b ell">{c.listing.title}</div>
                    <div className="mut xs">{c.role === "buyer" ? t("Siz — xaridor") : t("Siz — sotuvchi")} · {dateTime(c.last_message_at)}</div>
                  </div>
                  <Icon name="right" size={18} />
                </div>
              ))}
            </div>
          )}
        </Loadable>
      </div>
    </>
  );
}

interface ChatData { chat: Chat; messages: Msg[]; deal: { id: number; status: string } | null }

export function ChatPage() {
  const id = Number(useParams().id);
  const nav = useNavigate();
  const { me, fail } = useApp();
  const [data, setData] = useState<ChatData | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const lastId = useRef(0);
  const bottom = useRef<HTMLDivElement>(null);

  // Yangi xabarlarni har 3 soniyada olamiz (faqat ochiq chat uchun — server yuklanmaydi).
  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const r = await api.get<ChatData>(`/chats/${id}?after=${lastId.current}`);
        if (stop) return;
        setData(r);
        if (r.messages.length) {
          lastId.current = r.messages[r.messages.length - 1].id;
          setMsgs((p) => [...p, ...r.messages.filter((m) => !p.some((x) => x.id === m.id))]);
        }
      } catch (e) {
        if (!data) fail(e);
      }
    };
    tick();
    const iv = setInterval(() => document.visibilityState === "visible" && tick(), 3000);
    return () => { stop = true; clearInterval(iv); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs.length]);

  const send = async () => {
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    try {
      const m = await api.post<Msg>(`/chats/${id}/messages`, { text: body });
      setText("");
      lastId.current = Math.max(lastId.current, m.id);
      setMsgs((p) => (p.some((x) => x.id === m.id) ? p : [...p, m]));
    } catch (e) {
      fail(e);
    } finally {
      setSending(false);
    }
  };

  if (!data) return <><Header title={t("Chat")} /><Spinner /></>;
  const c = data.chat;
  return (
    <>
      <Header title={c.listing.title} sub={c.role === "buyer" ? t("Sotuvchi bilan chat") : t("Xaridor bilan chat")} right={<span />} />
      <div className="page" style={{ paddingBottom: 100 }}>
        <div className="card tight row click" onClick={() => nav(data.deal ? `/deal/${data.deal.id}` : `/listing/${c.listing.id}`)}>
          <GameLogo game={c.listing.game} size={36} />
          <div className="grow"><div className="b ell sm">{c.listing.title}</div><div className="y mono sm">{som(c.listing.price)}</div></div>
          {data.deal ? <Status s={data.deal.status} /> : <span className="badge g">GARANT</span>}
        </div>
        <div className="card tight row xs" style={{ borderColor: "rgba(29,233,182,.4)", background: "rgba(29,233,182,.06)", alignItems: "flex-start" }}>
          <span className="g"><Icon name="shield" size={18} /></span>
          <span>{t("Garant yoqilgan: to'lovni faqat ilova orqali qiling. Kartaga to'g'ridan-to'g'ri pul o'tkazmang — bunday holatda platforma himoya qila olmaydi.")}</span>
        </div>
        <div className="msgs">
          {msgs.length === 0 && <div className="mut sm center">{t("Savolingizni yozing")}</div>}
          {msgs.map((m) => (
            <div key={m.id} className={"msg " + (m.sender_id === null ? "sys" : m.sender_id === me?.id ? "me" : "")}>
              <div className="pre sm">{m.text}</div>
              <div className="mut xs" style={{ textAlign: "right", marginTop: 2 }}>{new Date(m.created_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}</div>
            </div>
          ))}
          <div ref={bottom} />
        </div>
      </div>
      <div className="bottombar">
        {data.deal && c.role === "buyer" && data.deal.status === "delivered" && (
          <div className="bottombar-in" style={{ paddingBottom: 0 }}>
            <button className="btn full okbtn" onClick={() => nav(`/deal/${data.deal!.id}`)}>✓ {t("Akkauntni tasdiqlayman")}</button>
          </div>
        )}
        <form className="bottombar-in" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <input className="input grow" maxLength={2000} placeholder={t("Xabar yozing...")} value={text} onChange={(e) => setText(e.target.value)} />
          <button className="btn" style={{ width: 52, padding: 0 }} disabled={!text.trim() || sending} aria-label={t("Yuborish")}><Icon name="send" /></button>
        </form>
      </div>
    </>
  );
}


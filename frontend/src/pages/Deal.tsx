import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Deal } from "../api";
import { t } from "../i18n";
import { confirmDialog } from "../tg";
import { BottomBar, Chips, Copy, dateTime, Empty, Field, Header, Icon, Loadable, Seg, Sheet, som, Status, useAction, useApp, useLoad } from "../ui";
import { ListingRow } from "./Market";

export function Deals() {
  const nav = useNavigate();
  const [role, setRole] = useState<"buyer" | "seller">("buyer");
  const st = useLoad(() => api.get<Deal[]>(`/deals?role=${role}`), [role]);
  return (
    <>
      <Header title={t("Mening bitimlarim")} />
      <div className="page">
        <Seg value={role} onChange={setRole} options={[{ v: "buyer", label: t("Xaridlarim") }, { v: "seller", label: t("Sotuvlarim") }]} />
        <div className="grid2">
          <button className="btn small ghost" onClick={() => nav("/chats")}><Icon name="chat" size={16} /> {t("Chatlar")}</button>
          <button className="btn small ghost" onClick={() => nav("/my-listings")}>{t("E'lonlarim")}</button>
        </div>
        <Loadable state={st}>
          {(list) => list.length === 0 ? <Empty icon="🤝" text={t("Bitimlar yo'q")} /> : list.map((d) => (
            <ListingRow key={d.id} x={d.listing} onClick={() => nav(`/deal/${d.id}`)} extra={
              <div className="row between" style={{ marginTop: 8 }}><span className="mut xs">#{d.id} · {dateTime(d.created_at)}</span><Status s={d.status} /></div>
            } />
          ))}
        </Loadable>
      </div>
    </>
  );
}

const TAGS = ["Tez javob", "Halol sotuvchi", "Akkaunt aniq", "Qulay narx"];

export function DealPage() {
  const id = useParams().id;
  const nav = useNavigate();
  const { refreshMe, toast } = useApp();
  const st = useLoad(() => api.get<Deal>(`/deals/${id}`), [id]);
  const [creds, setCreds] = useState("");
  const [sheet, setSheet] = useState<"dispute" | "review" | null>(null);
  const [reason, setReason] = useState("");
  const [score, setScore] = useState(5);
  const [tags, setTags] = useState<string[]>([]);
  const [comment, setComment] = useState("");
  const { busy, run } = useAction();

  const act = (path: string, body: unknown = {}, msg?: string) => run(async () => {
    await api.post(`/deals/${id}/${path}`, body);
    if (msg) toast(msg, "ok");
    setSheet(null);
    await Promise.all([st.reload(), refreshMe()]);
  });

  return (
    <>
      <Header title={t("Bitim #{id}", { id: id ?? "" })} sub={t("Garantli savdo")} />
      <Loadable state={st}>
        {(d) => {
          const buyer = d.role === "buyer", seller = d.role === "seller";
          return (
            <>
              <div className="page">
                <ListingRow x={d.listing} onClick={() => nav(`/listing/${d.listing.id}`)} />
                <div className="card">
                  <div className="kv"><span>{t("Holati")}</span><Status s={d.status} /></div>
                  <div className="kv"><span>{t("Summa")}</span><span className="y mono">{som(d.price)}</span></div>
                  {seller && <div className="kv"><span>{t("Sizga tushadi")}</span><span className="g mono">{som(d.price - d.commission)}</span></div>}
                  <div className="kv"><span>{t("Sana")}</span><span>{dateTime(d.created_at)}</span></div>
                  {d.auto_release_at && <div className="kv"><span>{t("Avto-tasdiq")}</span><span>{dateTime(d.auto_release_at)}</span></div>}
                </div>

                <Timeline status={d.status} />

                {d.status === "paid" && seller && (
                  <div className="card col">
                    <div className="b">{t("Akkaunt ma'lumotlarini yuboring")}</div>
                    <div className="mut xs">{t("Login, parol, bog'langan pochta va boshqa kerakli ma'lumotlar. Faqat xaridor ko'radi, shifrlangan holda saqlanadi.")}</div>
                    <textarea className="input" maxLength={2000} placeholder={"Moonton: example@gmail.com\nParol: ..."} value={creds} onChange={(e) => setCreds(e.target.value)} />
                    <button className="btn full" disabled={creds.trim().length < 3 || busy} onClick={() => act("deliver", { credentials: creds }, t("Yuborildi"))}>{t("Yuborish")}</button>
                  </div>
                )}
                {d.status === "paid" && buyer && (
                  <div className="card tight sm mut">⏳ {t("Sotuvchi akkaunt ma'lumotlarini yuborishini kuting. {h} soat ichida yubormasa, bitimni bekor qilib pulingizni qaytarib olishingiz mumkin.", { h: d.seller_deliver_hours ?? 12 })}</div>
                )}
                {d.credentials && (
                  <div className="card col">
                    <div className="b">🔐 {t("Akkaunt ma'lumotlari")}</div>
                    <Copy value={d.credentials} />
                    {d.status === "delivered" && <div className="mut xs">{t("Kirib, parol va pochtani o'zingiznikiga almashtiring. Hammasi joyida bo'lsa — «Tasdiqlash».")}</div>}
                  </div>
                )}
                {d.status === "disputed" && <div className="card tight sm">⚖️ {t("Nizo ochilgan. Admin ikkala tomonni ko'rib chiqadi.")}<div className="mut xs pre" style={{ marginTop: 4 }}>{d.dispute_reason}</div></div>}
                {d.resolution && <div className="card tight sm">{t("Admin qarori")}: {d.resolution}</div>}
                <button className="btn ghost full" onClick={() => nav(`/chat/${d.chat_id}`)}><Icon name="chat" /> {buyer ? t("Sotuvchi bilan chat") : t("Xaridor bilan chat")}</button>
              </div>

              <BottomBar>
                {d.status === "delivered" && buyer && (
                  <>
                    <button className="btn danger" onClick={() => setSheet("dispute")}>{t("Nizo")}</button>
                    <button className="btn green grow" disabled={busy} onClick={async () => {
                      if (await confirmDialog(t("Akkauntni tekshirdingizmi? Tasdiqlagach pul sotuvchiga o'tadi."))) act("confirm", {}, t("Bitim yakunlandi"));
                    }}>{t("Tasdiqlash")}</button>
                  </>
                )}
                {d.status === "paid" && (
                  <>
                    <button className="btn danger grow" disabled={busy} onClick={async () => {
                      if (await confirmDialog(t("Bitimni bekor qilasizmi? Pul xaridorga qaytariladi."))) act("cancel");
                    }}>{t("Bekor qilish")}</button>
                    {buyer && <button className="btn ghost" onClick={() => setSheet("dispute")}>{t("Nizo")}</button>}
                  </>
                )}
                {d.status === "completed" && buyer && !d.reviewed && <button className="btn full" onClick={() => setSheet("review")}>★ {t("Sotuvchini baholash")}</button>}
                {(d.status === "completed" && (seller || d.reviewed)) || d.status === "refunded" ? <button className="btn ghost full" onClick={() => nav("/market")}>{t("Savdoga qaytish")}</button> : null}
              </BottomBar>

              <Sheet open={sheet === "dispute"} onClose={() => setSheet(null)}>
                <div className="sec-title">{t("Nizo ochish")}</div>
                <div className="mut sm">{t("Pul muzlatiladi va admin ko'rib chiqadi. Muammoni batafsil yozing.")}</div>
                <textarea className="input" maxLength={2000} placeholder={t("Masalan: parol to'g'ri kelmadi / skinlar soni boshqacha")} value={reason} onChange={(e) => setReason(e.target.value)} />
                <button className="btn danger full" disabled={reason.trim().length < 5 || busy} onClick={() => act("dispute", { reason }, t("Nizo ochildi"))}>{t("Nizo ochish")}</button>
              </Sheet>

              <Sheet open={sheet === "review"} onClose={() => setSheet(null)}>
                <div className="sec-title center">{t("Sotuvchini baholang")}</div>
                <div className="stars">
                  {[1, 2, 3, 4, 5].map((n) => <button key={n} className={n <= score ? "on" : ""} onClick={() => setScore(n)}>★</button>)}
                </div>
                <Field label={t("Nima yoqdi?")}>
                  <Chips wrap value={null} onChange={(v) => setTags((p) => (p.includes(v) ? p.filter((x) => x !== v) : [...p, v]))}
                    options={TAGS.map((x) => ({ v: x, label: (tags.includes(x) ? "✓ " : "") + t(x) }))} />
                </Field>
                <Field label={t("Izoh (ixtiyoriy)")}><textarea className="input" maxLength={500} value={comment} onChange={(e) => setComment(e.target.value)} /></Field>
                <button className="btn full" disabled={busy} onClick={() => act("review", { score, tags, text: comment }, t("Rahmat!"))}>{t("Bahoni yuborish")}</button>
              </Sheet>
            </>
          );
        }}
      </Loadable>
    </>
  );
}

function Timeline({ status }: { status: string }) {
  const steps = [
    { k: "paid", label: t("To'lov garantda") },
    { k: "delivered", label: t("Ma'lumot yuborildi") },
    { k: "completed", label: t("Yakunlandi") },
  ];
  const idx = { paid: 0, delivered: 1, completed: 2, disputed: 1, refunded: -1 }[status] ?? 0;
  return (
    <div className="steps">
      {steps.map((s, i) => (
        <div key={s.k} style={{ display: "contents" }}>
          {i > 0 && <div className="ln" />}
          <div className={"step" + (i < idx || status === "completed" ? " done" : i === idx ? " on" : "")}><i>{i < idx || status === "completed" ? "✓" : i + 1}</i>{s.label}</div>
        </div>
      ))}
    </div>
  );
}

import { useEffect, useState } from "react";
import { api, type Ledger, type PayCard, type Topup, type Withdrawal } from "../api";
import { t } from "../i18n";
import { confirmDialog } from "../tg";
import {
  BottomBar, Copy, dateTime, Empty, Field, Header, Icon, Loadable, money, MoneyInput, Seg, Sheet, som, Status, useAction, useApp, useLoad,
} from "../ui";

interface WalletInfo {
  balance: number;
  entries: Ledger[];
  pending_topup: Topup | null;
  limits: { topup_min: number; topup_max: number; withdraw_min: number; ttl_minutes: number };
  wallet_id?: string | null;
  withdraw?: { earned: number; withdrawn: number; available: number };
}

const KIND: Record<string, string> = {
  topup: "Hamyon to'ldirildi", donate: "Almaz donat", donate_refund: "Donat qaytarildi", deal_pay: "Akkaunt xaridi",
  deal_payout: "Akkaunt sotuvi", deal_refund: "Bitim qaytarildi", withdraw: "Pul yechish", withdraw_refund: "Yechish qaytarildi",
  tg_service: "Telegram xizmat", tg_refund: "TG xizmat qaytarildi", boost: "Boost", boost_refund: "Boost qaytarildi",
  boost_payout: "Boost daromadi", vip: "VIP e'lon", rent_pay: "Akkaunt ijarasi", rent_payout: "Ijara daromadi",
  rent_deposit_back: "Depozit qaytdi", rent_refund: "Ijara qaytarildi", tournament_fee: "Turnir to'lovi", referral: "Taklif bonusi", admin_adjust: "Admin tuzatishi",
};

export default function Wallet() {
  const [tab, setTab] = useState<"topup" | "withdraw" | "history">("topup");
  const w = useLoad(() => api.get<WalletInfo>("/wallet"));
  const canWithdraw = (w.data?.withdraw?.earned ?? 0) > 0;
  return (
    <>
      <Header title={t("Hamyon")} sub={t("Balans va to'lovlar")} />
      <div className="page withbar">
        <div className="hero">
          <div className="row between"><span className="mut xs mono">{t("JORIY BALANS")}</span><span className="pill-b" style={{ color: "#dfe3ef", borderColor: "rgba(255,255,255,.25)" }}>🥈 Silver</span></div>
          <div className="hf bb y" style={{ fontSize: 30 }}>{money(w.data?.balance ?? 0)} <span className="mut sm">so'm</span></div>
          {w.data?.wallet_id && (
            <div className="row between xs" style={{ marginTop: 8 }}>
              <span className="mut">{t("Hamyon ID")}</span>
              <WalletIdChip id={w.data.wallet_id} />
            </div>
          )}
          {w.data && (
            <div className="row between mut xs" style={{ marginTop: 8 }}>
              <span>{t("Bir martalik limit")}: <b className="mono" style={{ color: "#fff" }}>{money(w.data.limits.topup_max)}</b></span>
              <span>{t("Eng kam")}: {money(w.data.limits.topup_min)}</span>
            </div>
          )}
        </div>
        <Seg value={tab} onChange={setTab} options={[{ v: "topup", label: t("To'ldirish") }, ...(canWithdraw ? [{ v: "withdraw" as const, label: t("Yechish") }] : []), { v: "history", label: t("Tarix") }]} />
        <Loadable state={w}>
          {(d) =>
            tab === "topup" ? <TopupFlow info={d} onDone={w.reload} /> : tab === "withdraw" && canWithdraw ? <WithdrawForm info={d} onDone={w.reload} /> : <LedgerList entries={d.entries} />
          }
        </Loadable>
      </div>
    </>
  );
}

const APPS: [string, string, string][] = [
  ["Click", "C", "#2f6bff"], ["Payme", "P", "#14b8c4"], ["Xazna", "X", "#1f8a5b"], ["Zoomrad", "Z", "#8bc34a"],
  ["Paynet", "PN", "#16a34a"], ["Beepul", "B", "#f59e0b"], ["Oson", "O", "#2563eb"], ["Uzum", "U", "#7c3aed"],
  ["Alif", "A", "#4caf50"], ["Humo", "H", "#c9a227"],
];

function TopupFlow({ info, onDone }: { info: WalletInfo; onDone: () => void }) {
  const { refreshMe, toast } = useApp();
  const [amount, setAmount] = useState<number | "">("");
  const [app, setApp] = useState("card");
  const [topup, setTopup] = useState<Topup | null>(info.pending_topup);
  const { busy, run } = useAction();

  // To'lov kutilayotganda har 5 soniyada holatni tekshiramiz.
  useEffect(() => {
    if (!topup || (topup.status !== "pending" && topup.status !== "checking")) return;
    const id = setInterval(async () => {
      try {
        const fresh = await api.get<Topup>(`/wallet/topup/${topup.id}`);
        if (fresh.status !== topup.status) {
          setTopup(fresh);
          if (fresh.status === "paid") {
            toast(t("Balans to'ldirildi: +{s}", { s: som(fresh.pay_amount) }), "ok");
            await refreshMe();
            onDone();
          }
        }
      } catch {
        /* keyingi safar */
      }
    }, 5000);
    return () => clearInterval(id);
  }, [topup, refreshMe, toast, onDone]);

  if (topup && (topup.status === "pending" || topup.status === "checking")) return <PayInstructions topup={topup} app={app} onChange={setTopup} onCancel={() => run(async () => {
    await api.post(`/wallet/topup/${topup.id}/cancel`);
    setTopup(null);
  })} />;

  if (topup && (topup.status === "rejected" || topup.status === "expired"))
    return (
      <div className="card center col" style={{ alignItems: "center", padding: 24 }}>
        <div style={{ fontSize: 46 }}>{topup.status === "rejected" ? "❌" : "⏱"}</div>
        <div className="bb" style={{ fontSize: 18 }}>{topup.status === "rejected" ? t("To'lov tasdiqlanmadi") : t("Vaqt tugadi")}</div>
        <div className="mut sm">{topup.status === "rejected" ? (topup.reject_reason ? t(topup.reject_reason) : "") : t("Pul o'tkazgan bo'lsangiz, xavotir olmang: to'lov topilsa balans baribir to'ldiriladi yoki chekni @vaynexo_support ga yuboring.")}</div>
        <button className="btn full" onClick={() => setTopup(null)}>{t("Yangi so'rov")}</button>
      </div>
    );

  if (topup && topup.status === "paid")
    return (
      <div className="card center col" style={{ alignItems: "center", padding: 24 }}>
        <div style={{ fontSize: 46 }}>✅</div>
        <div className="bb" style={{ fontSize: 18 }}>{t("Balans to'ldirildi")}</div>
        <div className="g bb mono" style={{ fontSize: 22 }}>+{som(topup.pay_amount)}</div>
        <button className="btn ghost full" onClick={() => setTopup(null)}>{t("Yana to'ldirish")}</button>
      </div>
    );

  const valid = typeof amount === "number" && amount >= info.limits.topup_min && amount <= info.limits.topup_max;
  return (
    <>
      <div className="sec-title">{t("Summa")}</div>
      <MoneyInput value={amount} onChange={setAmount} placeholder={`${money(info.limits.topup_min)} – ${money(info.limits.topup_max)} so'm`} />
      <div className="qgrid">
        {[20_000, 50_000, 100_000, 200_000].map((v) => (
          <button key={v} className={"qchip" + (amount === v ? " on" : "")} onClick={() => setAmount(v)}>{v / 1000}k</button>
        ))}
      </div>
      <div className="sec-title">{t("To'lov usuli")}</div>
      <div className="paygrid">
        {APPS.map(([name, l, c]) => (
          <button key={name} className={"payopt" + (app === name ? " on" : "")} onClick={() => setApp(name)}>
            <span className="payico" style={{ background: c }}>{l}</span>
            <span className="grow b ell">{name}</span>
            <span className="avto">{t("AVTO")}</span>
          </button>
        ))}
        <button className={"payopt wide" + (app === "card" ? " on" : "")} onClick={() => setApp("card")}>
          <span className="payico" style={{ background: "var(--y)", color: "#111" }}>—</span>
          <span className="grow b ell">{t("Istalgan bank karta")}</span>
          <span className="avto">{t("AVTO")}</span>
        </button>
      </div>
      <div className="note sm">
        🔒 {t("Istalgan ilova yoki karta orqali kartamizga o'tkazasiz — to'lov avtomatik topiladi va balans 1–3 daqiqada to'ldiriladi. Balansdagi pul faqat VAYNEXO xizmatlari uchun ishlatiladi.")}
      </div>
      <BottomBar>
        <button className="btn full" disabled={!valid || busy} onClick={() => run(async () => {
          setTopup(await api.post<Topup>("/wallet/topup", { amount }));
        })}>
          {t("To'ldirish")}
        </button>
      </BottomBar>
    </>
  );
}

function PayInstructions({ topup, app, onCancel, onChange }: { topup: Topup; app: string; onCancel: () => void; onChange: (t: Topup) => void }) {
  const { toast } = useApp();
  const [left, setLeft] = useState(() => Math.max(0, new Date(topup.expires_at).getTime() - Date.now()));
  const [sheet, setSheet] = useState(false);
  const { busy, run } = useAction();
  useEffect(() => {
    const id = setInterval(() => setLeft(Math.max(0, new Date(topup.expires_at).getTime() - Date.now())), 1000);
    return () => clearInterval(id);
  }, [topup.expires_at]);
  const mm = String(Math.floor(left / 60000)).padStart(2, "0");
  const ss = String(Math.floor((left % 60000) / 1000)).padStart(2, "0");
  const cards = topup.cards?.length ? topup.cards : [{ id: 0, number: topup.card_number, holder: topup.card_holder, kind: "" }];
  const checking = topup.status === "checking";
  const paid = () => run(async () => {
    onChange(await api.post<Topup>(`/wallet/topup/${topup.id}/paid`));
    setSheet(false);
    toast(t("To'lov tekshiruvga yuborildi"), "ok");
  });

  if (checking)
    return (
      <>
        <div className="card center col" style={{ alignItems: "center", padding: 22, borderColor: "rgba(255,214,10,.45)" }}>
          <div className="spinner" style={{ margin: 0, width: 40, height: 40 }} />
          <div className="bb" style={{ fontSize: 18 }}>{t("Tekshirilmoqda")}</div>
          <div className="y bb mono" style={{ fontSize: 22 }}>{som(topup.pay_amount)}</div>
          <div className="mut sm">{t("To'lov avtomatik tekshirilmoqda — bank xabari kelishi bilan balans o'zi to'ldiriladi va botda xabar keladi. Odatda 1–3 daqiqa. Sahifani yopsangiz ham bo'ladi.")}</div>
        </div>
        <div className="card">
          <div className="kv"><span>{t("Summa")}</span><span className="mono">{som(topup.pay_amount)}</span></div>
          <div className="kv"><span>{t("Holati")}</span><span className="y">{t("Tekshirilmoqda")}</span></div>
        </div>
        <div className="note sm">{t("Pul o'tkazmagan bo'lsangiz, to'lov tasdiqlanmaydi. Savol bo'lsa: @vaynexo_support")}</div>
      </>
    );

  return (
    <>
      <div className="card col">
        <div className="row between">
          <span className="b">{t("Karta orqali o'tkazma")}</span>
          <span className={"badge mono " + (left < 60000 ? "r" : "y")}>⏱ {mm}:{ss}</span>
        </div>
        <Copy label={t("Aynan shu summani o'tkazing")} value={money(topup.pay_amount)} />
        <div className="r sm b">⚠️ {t("Summani yaxlitlamang! 1 so'm kam yoki ko'p bo'lsa ham to'lov avtomatik topilmaydi.")}</div>
      </div>
      <div className="card col">
        <div className="mut xs mono b">{cards.length > 1 ? t("KARTALARDAN BIRIGA O'TKAZING") : t("KARTA RAQAMI")}</div>
        {cards.map((c) => (
          <div key={c.id + c.number} className="col" style={{ gap: 4 }}>
            <Copy label={[c.kind, c.holder].filter(Boolean).join(" · ") || undefined} value={c.number} />
          </div>
        ))}
      </div>
      <div className="card col">
        <div className="mut xs mono b">{t("TO'LDIRISH BOSQICHLARI")}</div>
        {[
          app === "card" ? t("Istalgan bank ilovasini oching") : t("{a} ilovasini oching", { a: app }),
          t("«Kartaga o'tkazma» bo'limini tanlang va karta raqamini kiriting"),
          t("Aynan {s} so'm o'tkazing va to'lovni tasdiqlang", { s: money(topup.pay_amount) }),
          t("«To'ladim» ni bosing — to'lov avtomatik tekshiriladi va balans o'zi to'ldiriladi"),
        ].map((x, i) => (
          <div key={i} className="row sm"><span className={"stepnum" + (i === 0 ? " on" : "")}>{i + 1}</span><span>{x}</span></div>
        ))}
      </div>
      <button className="btn full" disabled={busy} onClick={() => setSheet(true)}>✓ {t("To'ladim")}</button>
      <button className="btn ghost full" onClick={async () => { if (await confirmDialog(t("So'rovni bekor qilasizmi? Agar pul o'tkazgan bo'lsangiz, bekor qilmang."))) onCancel(); }}>
        {t("Bekor qilish")}
      </button>
      <Sheet open={sheet} onClose={() => setSheet(false)}>
        <div className="sec-title" style={{ marginTop: 0 }}>{t("To'lovni tasdiqlash")}</div>
        <div className="col">
          <div className="sm">{t("Aynan {s} o'tkazganingizni tasdiqlaysizmi? Chek kerak emas — to'lov bank xabari orqali avtomatik tekshiriladi.", { s: som(topup.pay_amount) })}</div>
          <div className="mut xs">{t("Pul o'tkazmasdan «To'ladim» bosish hisobni bloklashga olib keladi.")}</div>
          <button className="btn full" disabled={busy} onClick={paid}>{busy ? t("Yuborilmoqda...") : t("Ha, to'ladim")}</button>
        </div>
      </Sheet>
    </>
  );
}

function LedgerList({ entries }: { entries: Ledger[] }) {
  if (!entries.length) return <Empty icon="🧾" text={t("Hali amallar yo'q")} />;
  return (
    <div className="card">
      {entries.map((e) => (
        <div key={e.id} className="listrow">
          <div className="grow">
            <div className="b ell">{t(KIND[e.kind] ?? e.kind)}</div>
            <div className="mut xs">{dateTime(e.created_at)}{e.note ? " · " + e.note : ""}</div>
          </div>
          <div className={"mono b " + (e.amount > 0 ? "g" : "")}>{e.amount > 0 ? "+" : "−"}{money(Math.abs(e.amount))}</div>
        </div>
      ))}
    </div>
  );
}

function WithdrawForm({ info, onDone }: { info: WalletInfo; onDone: () => void }) {
  const { refreshMe, toast } = useApp();
  const [amount, setAmount] = useState<number | "">("");
  const [card, setCard] = useState("");
  const [holder, setHolder] = useState("");
  const list = useLoad(() => api.get<Withdrawal[]>("/wallet/withdrawals"));
  const cards = useLoad(() => api.get<PayCard[]>("/me/cards"));
  const [cardId, setCardId] = useState<number | null>(null);
  useEffect(() => {
    const def = cards.data?.find((c) => c.is_default);
    if (def && cardId === null) setCardId(def.id);
  }, [cards.data]); // eslint-disable-line react-hooks/exhaustive-deps
  const { busy, run } = useAction();
  const digits = card.replace(/\D/g, "");
  const useSaved = cardId !== null && cardId > 0;
  const avail = info.withdraw?.available ?? 0;
  const valid = typeof amount === "number" && amount >= info.limits.withdraw_min && amount <= avail && (useSaved || digits.length === 16);
  return (
    <>
      <div className="card col">
        <Field label={t("Summa (so'm)")}>
          <MoneyInput value={amount} onChange={setAmount} placeholder={money(info.limits.withdraw_min)} />
        </Field>
        <div className="note sm">💼 {t("Yechish mumkin: {s}. Faqat sotuv, ijara va boost daromadi yechiladi — hamyonga to'ldirilgan pul yechilmaydi.", { s: som(avail) })}</div>
        {avail > 0 && <button className="chip" style={{ alignSelf: "flex-start" }} onClick={() => setAmount(avail)}>{t("Hammasi")}: {money(avail)}</button>}
        {cards.data && cards.data.length > 0 && (
          <Field label={t("Karta")}>
            <div className="col">
              {cards.data.map((c) => (
                <button key={c.id} className={"payopt" + (cardId === c.id ? " on" : "")} onClick={() => setCardId(c.id)}>
                  <span className="payico" style={{ background: "#2b2d45" }}><Icon name="card" size={16} /></span>
                  <span className="grow b">{c.brand} •••• {c.last4}</span>
                  {c.is_default && <span className="avto">{t("ASOSIY")}</span>}
                </button>
              ))}
              <button className={"payopt" + (cardId === 0 ? " on" : "")} onClick={() => setCardId(0)}>
                <span className="payico" style={{ background: "#2b2d45" }}>+</span>
                <span className="grow b">{t("Boshqa karta")}</span>
              </button>
            </div>
          </Field>
        )}
        {!useSaved && (
          <>
            <Field label={t("Karta raqami (Uzcard / Humo)")}>
              <input className="input mono" inputMode="numeric" placeholder="8600 0000 0000 0000" value={digits.replace(/(\d{4})(?=\d)/g, "$1 ")} onChange={(e) => setCard(e.target.value.replace(/\D/g, "").slice(0, 16))} />
            </Field>
            <Field label={t("Karta egasi")}>
              <input className="input" placeholder="ISM FAMILIYA" value={holder} onChange={(e) => setHolder(e.target.value.toUpperCase())} maxLength={64} />
            </Field>
          </>
        )}
        <div className="mut xs">{t("Eng kam yechish: {min}. So'rov admin tomonidan 24 soat ichida bajariladi.", { min: som(info.limits.withdraw_min) })}</div>
        <button className="btn full" disabled={!valid || busy} onClick={() => run(async () => {
          await api.post("/wallet/withdraw", useSaved ? { amount, card_id: cardId } : { amount, card_number: digits, card_holder: holder });
          toast(t("So'rov yuborildi"), "ok");
          setAmount("");
          await refreshMe();
          onDone();
          list.reload();
        })}>{t("Yechib olish")}</button>
      </div>
      {list.data && list.data.length > 0 && (
        <div className="card">
          <div className="b">{t("So'rovlar")}</div>
          {list.data.map((w) => (
            <div key={w.id} className="listrow">
              <div className="grow">
                <div className="b">{som(w.amount)}</div>
                <div className="mut xs">{w.card} · {dateTime(w.created_at)}</div>
                {w.admin_note && <div className="mut xs">{w.admin_note}</div>}
              </div>
              <Status s={w.status} />
            </div>
          ))}
        </div>
      )}
    </>
  );
}


function WalletIdChip({ id }: { id: string }) {
  const { toast } = useApp();
  return (
    <button className="wid-chip mono" onClick={async () => {
      try { await navigator.clipboard.writeText(id.replace(/\s/g, "")); toast(t("Nusxa olindi"), "ok"); } catch { toast(id); }
    }}>{id} <Icon name="copy" size={13} /></button>
  );
}

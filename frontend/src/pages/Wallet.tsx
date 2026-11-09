import { useEffect, useState } from "react";
import { api, type Ledger, type Topup, type Withdrawal } from "../api";
import { t } from "../i18n";
import { confirmDialog } from "../tg";
import {
  BottomBar, Chips, Copy, dateTime, Empty, Field, Header, Loadable, money, MoneyInput, Seg, som, Status, useAction, useApp, useLoad,
} from "../ui";

interface WalletInfo {
  balance: number;
  entries: Ledger[];
  pending_topup: Topup | null;
  limits: { topup_min: number; topup_max: number; withdraw_min: number; ttl_minutes: number };
}

const KIND: Record<string, string> = {
  topup: "Hamyon to'ldirildi", donate: "Almaz donat", donate_refund: "Donat qaytarildi", deal_pay: "Akkaunt xaridi",
  deal_payout: "Akkaunt sotuvi", deal_refund: "Bitim qaytarildi", withdraw: "Pul yechish", withdraw_refund: "Yechish qaytarildi",
  tg_service: "Telegram xizmat", tg_refund: "TG xizmat qaytarildi", boost: "Boost", boost_refund: "Boost qaytarildi",
  boost_payout: "Boost daromadi", tournament_fee: "Turnir to'lovi", referral: "Taklif bonusi", admin_adjust: "Admin tuzatishi",
};

export default function Wallet() {
  const [tab, setTab] = useState<"topup" | "withdraw" | "history">("topup");
  const w = useLoad(() => api.get<WalletInfo>("/wallet"));
  return (
    <>
      <Header title={t("Hamyon")} sub={t("Balans va to'lovlar")} />
      <div className="page">
        <div className="hero">
          <div className="mut xs mono">{t("JORIY BALANS")}</div>
          <div className="hf bb" style={{ fontSize: 30 }}>{som(w.data?.balance ?? 0)}</div>
        </div>
        <Seg value={tab} onChange={setTab} options={[{ v: "topup", label: t("To'ldirish") }, { v: "withdraw", label: t("Yechish") }, { v: "history", label: t("Tarix") }]} />
        <Loadable state={w}>
          {(d) =>
            tab === "topup" ? <TopupFlow info={d} onDone={w.reload} /> : tab === "withdraw" ? <WithdrawForm info={d} onDone={w.reload} /> : <LedgerList entries={d.entries} />
          }
        </Loadable>
      </div>
    </>
  );
}

function TopupFlow({ info, onDone }: { info: WalletInfo; onDone: () => void }) {
  const { refreshMe, toast } = useApp();
  const [amount, setAmount] = useState<number | "">("");
  const [topup, setTopup] = useState<Topup | null>(info.pending_topup);
  const { busy, run } = useAction();

  // To'lov kutilayotganda har 5 soniyada holatni tekshiramiz.
  useEffect(() => {
    if (!topup || topup.status !== "pending") return;
    const id = setInterval(async () => {
      try {
        const fresh = await api.get<Topup>(`/wallet/topup/${topup.id}`);
        if (fresh.status !== "pending") {
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

  if (topup && topup.status === "pending") return <PayInstructions topup={topup} onCancel={() => run(async () => {
    await api.post(`/wallet/topup/${topup.id}/cancel`);
    setTopup(null);
  })} />;

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
      <div className="card col">
        <Field label={t("Summa (so'm)")}>
          <MoneyInput value={amount} onChange={setAmount} placeholder={money(50_000)} />
        </Field>
        <Chips value={amount === "" ? null : amount} onChange={setAmount}
          options={[20_000, 50_000, 100_000, 200_000, 500_000].map((v) => ({ v, label: money(v) }))} />
        <div className="mut xs">{t("Eng kam: {min} · Eng ko'p: {max}", { min: som(info.limits.topup_min), max: som(info.limits.topup_max) })}</div>
      </div>
      <div className="card col">
        <div className="b">{t("Qanday ishlaydi")}</div>
        {[
          t("Summani kiriting — tizim sizga noyob summa beradi (masalan 50 034)"),
          t("Shu ANIQ summani ko'rsatilgan kartaga o'tkazing (Payme, Click, bank ilovasi)"),
          t("To'lov avtomatik topiladi va balans 1–3 daqiqada to'ldiriladi"),
        ].map((s, i) => (
          <div key={i} className="row" style={{ alignItems: "flex-start" }}>
            <span className="badge y" style={{ flex: "none" }}>{i + 1}</span>
            <span className="sm">{s}</span>
          </div>
        ))}
      </div>
      <BottomBar>
        <button className="btn full" disabled={!valid || busy} onClick={() => run(async () => {
          setTopup(await api.post<Topup>("/wallet/topup", { amount }));
        })}>
          {t("Davom etish")}
        </button>
      </BottomBar>
    </>
  );
}

function PayInstructions({ topup, onCancel }: { topup: Topup; onCancel: () => void }) {
  const [left, setLeft] = useState(() => Math.max(0, new Date(topup.expires_at).getTime() - Date.now()));
  useEffect(() => {
    const id = setInterval(() => setLeft(Math.max(0, new Date(topup.expires_at).getTime() - Date.now())), 1000);
    return () => clearInterval(id);
  }, [topup.expires_at]);
  const mm = String(Math.floor(left / 60000)).padStart(2, "0");
  const ss = String(Math.floor((left % 60000) / 1000)).padStart(2, "0");
  return (
    <>
      <div className="card col">
        <div className="row between">
          <span className="b">{t("To'lovni amalga oshiring")}</span>
          <span className="badge y mono">⏱ {mm}:{ss}</span>
        </div>
        <Copy label={t("Aynan shu summani o'tkazing")} value={money(topup.pay_amount)} />
        <div className="r sm b">⚠️ {t("Summani yaxlitlamang! Boshqa summa o'tkazilsa, to'lov avtomatik topilmaydi.")}</div>
        <Copy label={t("Karta raqami")} value={topup.card_number} />
        <div className="mut sm">{t("Qabul qiluvchi")}: <span className="b" style={{ color: "#fff" }}>{topup.card_holder}</span></div>
      </div>
      <div className="card row">
        <div className="spinner" style={{ margin: 0, width: 22, height: 22, flex: "none" }} />
        <div className="sm">{t("To'lov kutilmoqda. O'tkazganingizdan so'ng balans avtomatik to'ldiriladi — bu sahifani yopsangiz ham bo'ladi.")}</div>
      </div>
      <button className="btn danger full" onClick={async () => { if (await confirmDialog(t("So'rovni bekor qilasizmi? Agar pul o'tkazgan bo'lsangiz, bekor qilmang."))) onCancel(); }}>
        {t("Bekor qilish")}
      </button>
    </>
  );
}

function WithdrawForm({ info, onDone }: { info: WalletInfo; onDone: () => void }) {
  const { refreshMe, toast } = useApp();
  const [amount, setAmount] = useState<number | "">("");
  const [card, setCard] = useState("");
  const [holder, setHolder] = useState("");
  const list = useLoad(() => api.get<Withdrawal[]>("/wallet/withdrawals"));
  const { busy, run } = useAction();
  const digits = card.replace(/\D/g, "");
  const valid = typeof amount === "number" && amount >= info.limits.withdraw_min && amount <= info.balance && digits.length === 16;
  return (
    <>
      <div className="card col">
        <Field label={t("Summa (so'm)")}>
          <MoneyInput value={amount} onChange={setAmount} placeholder={money(info.limits.withdraw_min)} />
        </Field>
        <button className="chip" style={{ alignSelf: "flex-start" }} onClick={() => setAmount(info.balance)}>{t("Hammasi")}: {money(info.balance)}</button>
        <Field label={t("Karta raqami (Uzcard / Humo)")}>
          <input className="input mono" inputMode="numeric" placeholder="8600 0000 0000 0000" value={digits.replace(/(\d{4})(?=\d)/g, "$1 ")} onChange={(e) => setCard(e.target.value.replace(/\D/g, "").slice(0, 16))} />
        </Field>
        <Field label={t("Karta egasi")}>
          <input className="input" placeholder="ISM FAMILIYA" value={holder} onChange={(e) => setHolder(e.target.value.toUpperCase())} maxLength={64} />
        </Field>
        <div className="mut xs">{t("Eng kam yechish: {min}. So'rov admin tomonidan 24 soat ichida bajariladi.", { min: som(info.limits.withdraw_min) })}</div>
        <button className="btn full" disabled={!valid || busy} onClick={() => run(async () => {
          await api.post("/wallet/withdraw", { amount, card_number: digits, card_holder: holder });
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

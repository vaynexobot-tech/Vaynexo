import { useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, setPinToken, type Me, type PayCard } from "../api";
import { LANGS, t, type Lang } from "../i18n";
import { bioClear, bioManager, bioRead, bioSave, confirmDialog, haptic, tgPhoto } from "../tg";
import { BottomBar, BottomNav, errorText, Field, Header, Icon, Loadable, money, Row, Sheet, Toggle, useAction, useApp, useLoad } from "../ui";

const KYC_PILL: Record<Me["kyc_status"], [string, string]> = {
  none: ["Tasdiqlanmagan", "y"],
  pending: ["Tekshirilmoqda", "b"],
  verified: ["Tasdiqlangan", "g"],
  rejected: ["Rad etilgan", "r"],
};

// ---------------------------------------------------------------- Sozlamalar
export function Settings() {
  const nav = useNavigate();
  const { me, setMe, fail } = useApp();
  const [langOpen, setLangOpen] = useState(false);
  if (!me) return null;
  const photo = tgPhoto();
  const patch = async (body: Partial<Me>) => {
    try {
      setMe({ ...me, ...(await api.patch<Me>("/me", body)) });
    } catch (e) {
      fail(e);
    }
  };
  const notifOn = me.notify_chat || me.notify_tour;
  const [kycLabel, kycCls] = KYC_PILL[me.kyc_status];
  const chev = <span className="mut"><Icon name="right" size={18} /></span>;
  return (
    <>
      <Header title={t("Sozlamalar")} sub={t("Profil va ilova sozlamalari")} back={false} icon="settings" />
      <div className="page">
        <div className="card col">
          <div className="row" style={{ alignItems: "flex-start" }}>
            <div style={{ width: 56, height: 56, borderRadius: "50%", padding: 2, background: "linear-gradient(135deg,#ffd60a,#1de9b6)", flex: "none" }}>
              {photo ? <img src={photo} alt="" style={{ width: "100%", height: "100%", borderRadius: "50%" }} /> : <div style={{ width: "100%", height: "100%", borderRadius: "50%", background: "linear-gradient(135deg,#3a2f6b,#e7a84a)" }} />}
            </div>
            <div className="grow">
              <div className="bb ell" style={{ fontSize: 18 }}>{me.name || "—"}</div>
              <div className="mut xs mono">{me.wallet_id ? `${t("Hamyon ID")}: ${me.wallet_id}` : `ID: ${me.id}`}</div>
              <span className="balchip mono" onClick={() => nav("/wallet")}>● {money(me.balance)} so'm</span>
            </div>
            <button className="btn small ghost" onClick={() => nav("/profile")}>{t("Tahrirlash")}</button>
          </div>
          <div className="row between">
            <div className="row">
              <span className="hf bb y" style={{ fontSize: 26 }}>{me.rating ?? "—"}</span>
              <div>
                <div className="stars">{"★★★★★".slice(0, Math.round(me.rating ?? 0)).padEnd(5, "☆")}</div>
                <div className="mut xs">{t("{n} ta baho", { n: me.rating_count })}</div>
              </div>
            </div>
            {(me.kyc_status === "verified" || me.sales >= 5) && <span className="pill-b g">✓ {t("Ishonchli")}</span>}
          </div>
          <div className="stat3">
            <div><div className="bb">{me.sales}</div><div className="mut xs">{t("Savdo")}</div></div>
            <div><div className="bb">{me.rent_count}</div><div className="mut xs">{t("Ijara")}</div></div>
            <div><div className="bb g">{me.positive_percent != null ? me.positive_percent + "%" : "—"}</div><div className="mut xs">{t("Yaxshi baho")}</div></div>
          </div>
        </div>

        <div className="card click row kyc-card" onClick={() => nav("/kyc")}>
          <div className="hd-ico" style={{ width: 44, height: 44 }}><Icon name="shield" /></div>
          <div className="grow">
            <div className="b">{t("Identifikatsiya")}</div>
            <div className="mut xs">{t("Shaxsingizni tasdiqlang")}</div>
          </div>
          <span className={"pill-b " + kycCls}>{t(kycLabel)}</span>
          {chev}
        </div>

        <div className="card" style={{ padding: "4px 14px" }}>
          <Row icon={<Icon name="doc" />} title={t("Mening e'lonlarim")}
            right={<><span className="pill-b g">{t("{n} faol", { n: me.active_listings })}</span>{chev}</>} onClick={() => nav("/my-listings")} />
          <Row icon={<Icon name="clock" />} title={t("Xaridlar tarixi")}
            right={<><span className="pill-b y">{t("{n} ta", { n: me.purchases_count })}</span>{chev}</>} onClick={() => nav("/history")} />
          <Row icon={<Icon name="globe" />} title={t("Til")}
            right={<><span className="mut sm">{LANGS.find((l) => l.v === me.lang)?.label}</span>{chev}</>} onClick={() => setLangOpen(true)} />
          <Row icon={<Icon name="gift" />} title={t("Do'stlarni taklif qilish")}
            right={<><span className="pill-b g">+ bonus</span>{chev}</>} onClick={() => nav("/referral")} />
          <Row icon={<Icon name="bell" />} title={t("Bildirishnomalar")}
            right={<Toggle on={notifOn} onChange={(v) => patch({ notify_chat: v, notify_tour: v })} />} />
          <Row icon={<Icon name="card" />} title={t("To'lov usullari")} onClick={() => nav("/payment-methods")} />
          <Row icon={<Icon name="shield" />} title={t("Xavfsizlik")} onClick={() => nav("/security")} />
          <Row icon={<Icon name="help" />} title={t("Yordam va aloqa")} onClick={() => nav("/help")} />
          <Row icon={<Icon name="doc" />} title={t("Qoidalar va shartlar")} onClick={() => nav("/legal/terms")} />
          {me.is_admin && <Row icon={<Icon name="admin" />} title={<span className="y">{t("Admin panel")}</span>} onClick={() => nav("/admin")} />}
        </div>
        <div className="mut xs center">VAYNEXO · v1.1</div>
      </div>
      <LangSheet open={langOpen} current={me.lang} onClose={() => setLangOpen(false)} onPick={(l) => patch({ lang: l })} />
      <BottomNav />
    </>
  );
}

function LangSheet({ open, current, onClose, onPick }: { open: boolean; current: Lang; onClose: () => void; onPick: (l: Lang) => void }) {
  const [v, setV] = useState<Lang>(current);
  useEffect(() => setV(current), [current, open]);
  return (
    <Sheet open={open} onClose={onClose}>
      <div className="row between" style={{ marginBottom: 12 }}>
        <div className="sec-title" style={{ margin: 0 }}>{t("Tilni tanlang")}</div>
        <button className="iconbtn" onClick={onClose} aria-label={t("Yopish")}>✕</button>
      </div>
      <div className="card" style={{ padding: "4px 14px" }}>
        {LANGS.map((l) => (
          <div key={l.v} className="listrow" style={{ cursor: "pointer" }} onClick={() => setV(l.v)}>
            <div className="grow"><div className="b">{l.label}</div><div className="mut xs">{l.sub}</div></div>
            <span className={"radio" + (v === l.v ? " on" : "")} />
          </div>
        ))}
      </div>
      <button className="btn full" style={{ marginTop: 14 }} onClick={() => { onPick(v); onClose(); }}>{t("Tasdiqlash")}</button>
    </Sheet>
  );
}

// ---------------------------------------------------------------- Identifikatsiya
const KYC_STEPS: { key: "selfie" | "front" | "back"; title: string; sub: string }[] = [
  { key: "selfie", title: "Hujjat bilan rasm", sub: "Yuzingiz va hujjat bir kadrda, ikkalasi ham aniq ko'rinsin" },
  { key: "front", title: "Pasport oldi", sub: "Yozuvlar o'qiladigan bo'lsin" },
  { key: "back", title: "Pasport orqasi", sub: "To'liq sahifa ko'rinsin" },
];

export function Kyc() {
  const nav = useNavigate();
  const { me, refreshMe, toast } = useApp();
  const [files, setFiles] = useState<Record<string, File | null>>({ selfie: null, front: null, back: null });
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const { busy, run } = useAction();
  useEffect(() => () => Object.values(previews).forEach((u) => URL.revokeObjectURL(u)), [previews]);
  if (!me) return null;
  const status = me.kyc_status;
  const ready = KYC_STEPS.every((s) => files[s.key]);

  return (
    <>
      <Header title={t("Identifikatsiya")} sub={t("Bir martalik jarayon")} />
      <div className="page withbar">
        <div className="hf bb" style={{ fontSize: 26 }}>{t("Verifikatsiya")}</div>
        {status === "verified" && <div className="card g b">✅ {t("Shaxsingiz tasdiqlangan. Profilingizda «Ishonchli» belgisi ko'rinadi.")}</div>}
        {status === "pending" && <div className="card y">⏳ {t("Rasmlar tekshirilmoqda. Natija haqida bot orqali xabar beramiz.")}</div>}
        {status === "rejected" && <div className="card r">❌ {t("Rad etildi")}: {me.kyc_note ? t(me.kyc_note) : ""}. {t("Rasmlarni qaytadan yuborishingiz mumkin.")}</div>}

        <div className="card col">
          <div className="y b xs mono">🛡 {t("NEGA BU KERAK?")}</div>
          <div className="sm">{t("Platformada har bir sotuvchi haqiqiy inson ekaniga ishonch hosil qilamiz — bu xaridorlarni firibgarlikdan himoya qiladi va e'lonlaringizga ishonchni oshiradi. Bu jarayon atigi bir marta so'raladi.")}</div>
        </div>

        {(status === "none" || status === "rejected") && (
          <>
            <div className="mut xs mono">{t("RASMLARNI YUKLANG")}</div>
            {KYC_STEPS.map((s) => (
              <label key={s.key} className="card click row" style={{ cursor: "pointer" }}>
                <div className="kycthumb">
                  {previews[s.key] ? <img src={previews[s.key]} alt="" /> : <Icon name={s.key === "back" ? "card" : "user"} size={26} />}
                </div>
                <div className="grow">
                  <div className="b">{t(s.title)}</div>
                  <div className="mut xs">{t(s.sub)}</div>
                </div>
                {files[s.key] ? <span className="g"><Icon name="check" /></span> : <span className="mut"><Icon name="upload" /></span>}
                <input type="file" accept="image/*" hidden onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  if (f.size > 5 * 1024 * 1024) return toast(t("Rasm 5 MB dan oshmasin"), "err");
                  setFiles((x) => ({ ...x, [s.key]: f }));
                  setPreviews((x) => ({ ...x, [s.key]: URL.createObjectURL(f) }));
                }} />
              </label>
            ))}
            <div className="mut xs">🔒 {t("Rasmlar faqat adminga Telegram orqali yuboriladi va ilovada saqlanmaydi.")}</div>
          </>
        )}
      </div>
      {(status === "none" || status === "rejected") && (
        <BottomBar>
          <div className="col grow" style={{ gap: 6 }}>
            <button className="btn full" disabled={!ready || busy} onClick={() => run(async () => {
              const fd = new FormData();
              KYC_STEPS.forEach((s) => fd.append(s.key, files[s.key]!));
              await api.form("/me/kyc", fd);
              await refreshMe();
              toast(t("Tekshiruvga yuborildi"), "ok");
              nav(-1);
            })}>{busy ? t("Yuborilmoqda...") : t("Tekshiruvga yuborish")}</button>
            <div className="mut xs center">{t("Natija haqida bot orqali darhol xabar beramiz.")}</div>
          </div>
        </BottomBar>
      )}
    </>
  );
}

// ---------------------------------------------------------------- To'lov usullari
export function PaymentMethods() {
  const cards = useLoad(() => api.get<PayCard[]>("/me/cards"));
  const { toast } = useApp();
  const [add, setAdd] = useState(false);
  const { run } = useAction();
  return (
    <>
      <Header title={t("To'lov usullari")} sub={t("Pul yechish uchun saqlangan kartalar")} />
      <div className="page">
        <Loadable state={cards}>
          {(list) => list.length === 0 ? null : (
            <div className="card" style={{ padding: "4px 14px" }}>
              {list.map((c) => (
                <div key={c.id} className="listrow">
                  <span className="rowico y"><Icon name="card" /></span>
                  <div className="grow" style={{ cursor: c.is_default ? undefined : "pointer" }} onClick={() => !c.is_default && run(async () => {
                    await api.post(`/me/cards/${c.id}/default`);
                    cards.reload();
                  })}>
                    <div className="b mono">{c.brand} •••• {c.last4}</div>
                    <div className="mut xs">{[c.expiry, c.holder].filter(Boolean).join(" · ") || "—"}</div>
                  </div>
                  {c.is_default ? <span className="pill-b y">{t("Asosiy")}</span> : (
                    <button className="iconbtn" aria-label={t("O'chirish")} onClick={() => run(async () => {
                      if (!(await confirmDialog(t("Kartani o'chirasizmi?")))) return;
                      await api.del(`/me/cards/${c.id}`);
                      cards.reload();
                    })}>✕</button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Loadable>
        {cards.data && cards.data.length > 1 && <div className="mut xs">{t("Asosiy qilish uchun kartaga bosing.")}</div>}
        <button className="dashed-btn" onClick={() => setAdd(true)}>+ {t("Yangi karta qo'shish")}</button>
        <div className="mut xs mono" style={{ marginTop: 6 }}>{t("BOSHQA USULLAR")}</div>
        <div className="card" style={{ padding: "4px 14px" }}>
          {["Payme", "Click", "Paynet"].map((n) => (
            <Row key={n} icon={<Icon name="wallet" />} title={n} sub={t("Ulanmagan")} right={<span className="mut xs">{t("Tez kunda")}</span>} />
          ))}
        </div>
        <div className="mut xs">{t("Hamyonni to'ldirish uchun hozir istalgan bank ilovasidan kartaga o'tkazma ishlatiladi (Hamyon → To'ldirish).")}</div>
      </div>
      <AddCardSheet open={add} onClose={() => setAdd(false)} onAdded={() => { setAdd(false); cards.reload(); toast(t("Karta qo'shildi"), "ok"); }} />
    </>
  );
}

function AddCardSheet({ open, onClose, onAdded }: { open: boolean; onClose: () => void; onAdded: () => void }) {
  const [num, setNum] = useState("");
  const [holder, setHolder] = useState("");
  const [exp, setExp] = useState("");
  const { busy, run } = useAction();
  useEffect(() => {
    if (open) { setNum(""); setHolder(""); setExp(""); }
  }, [open]);
  return (
    <Sheet open={open} onClose={onClose}>
      <div className="sec-title" style={{ marginTop: 0 }}>{t("Yangi karta")}</div>
      <div className="col">
        <Field label={t("Karta raqami")}>
          <input className="input mono" inputMode="numeric" placeholder="8600 0000 0000 0000" value={num.replace(/(\d{4})(?=\d)/g, "$1 ")}
            onChange={(e) => setNum(e.target.value.replace(/\D/g, "").slice(0, 16))} />
        </Field>
        <div className="row">
          <div className="grow"><Field label={t("Karta egasi")}><input className="input" placeholder="ISM FAMILIYA" maxLength={64} value={holder} onChange={(e) => setHolder(e.target.value.toUpperCase())} /></Field></div>
          <div style={{ width: 100 }}><Field label={t("Muddati")}><input className="input mono" inputMode="numeric" placeholder="MM/YY" value={exp} onChange={(e) => {
            const d = e.target.value.replace(/\D/g, "").slice(0, 4);
            setExp(d.length > 2 ? d.slice(0, 2) + "/" + d.slice(2) : d);
          }} /></Field></div>
        </div>
        <div className="mut xs">🔒 {t("Karta raqami shifrlangan holda saqlanadi va faqat pul yechishda ishlatiladi.")}</div>
        <button className="btn full" disabled={num.length !== 16 || busy} onClick={() => run(async () => {
          await api.post("/me/cards", { number: num, holder, expiry: exp });
          onAdded();
        })}>{t("Saqlash")}</button>
      </div>
    </Sheet>
  );
}

// ---------------------------------------------------------------- Xavfsizlik
type PinMode = null | "set" | "change" | "remove" | "bio";

export function Security() {
  const { me, setMe, refreshMe, toast, fail } = useApp();
  const [mode, setMode] = useState<PinMode>(null);
  const [bioAvail, setBioAvail] = useState<null | string>(null);
  useEffect(() => {
    bioManager().then((bm) => setBioAvail(bm ? bm.biometricType : null));
  }, []);
  if (!me) return null;
  const patch = async (body: Partial<Me>) => {
    try {
      setMe({ ...me, ...(await api.patch<Me>("/me", body)) });
    } catch (e) {
      fail(e);
    }
  };
  const bioName = bioAvail === "face" ? "Face ID" : t("Barmoq izi");
  return (
    <>
      <Header title={t("Xavfsizlik")} sub={t("Akkaunt himoyasi")} />
      <div className="page">
        <div className="card" style={{ padding: "4px 14px" }}>
          <Row title={t("PIN-kod")} sub={t("Hamyon va to'lovlarni PIN bilan himoyalash")}
            right={<Toggle on={me.pin_set} onChange={(v) => setMode(v ? "set" : "remove")} />} />
          {me.pin_set && <Row title={t("PIN-kodni almashtirish")} onClick={() => setMode("change")} />}
          <Row title={t("Biometrik kirish")}
            sub={bioAvail ? t("{b} orqali tez ochish", { b: bioName }) : t("Bu qurilmada mavjud emas")}
            right={<Toggle on={me.bio_set} onChange={async (v) => {
              if (!me.pin_set) return toast(t("Avval PIN-kod o'rnating"), "info");
              if (!bioAvail && v) return toast(t("Bu qurilmada biometriya mavjud emas"), "info");
              if (v) return setMode("bio");
              try {
                await api.post("/me/pin/bio/off");
                await bioClear();
                await refreshMe();
              } catch (e) {
                fail(e);
              }
            }} />} />
        </div>

        <div className="mut xs mono">{t("KIRISH")}</div>
        <div className="card col">
          <div className="row"><span className="rowico"><Icon name="lock" /></span><div className="grow"><div className="b">{t("Telegram orqali kirish")}</div><div className="mut xs">{t("Shu qurilma · hozir")}</div></div><span className="pill-b g">{t("Faol")}</span></div>
          <div className="mut xs">{t("VAYNEXO'ga faqat Telegram akkauntingiz orqali kiriladi. Qo'shimcha himoya uchun Telegram'da ikki bosqichli tasdiqni yoqing: Sozlamalar → Maxfiylik → Ikki bosqichli tasdiq.")}</div>
        </div>

        <div className="mut xs mono">{t("BILDIRISHNOMALAR")}</div>
        <div className="card" style={{ padding: "4px 14px" }}>
          <Row title={t("Chat xabarlari")} sub={t("Sotuvchi va xaridorlardan yangi xabar")} right={<Toggle on={me.notify_chat} onChange={(v) => patch({ notify_chat: v })} />} />
          <Row title={t("Turnir eslatmalari")} sub={t("Boshlanishidan 30 daqiqa oldin")} right={<Toggle on={me.notify_tour} onChange={(v) => patch({ notify_tour: v })} />} />
        </div>
        <div className="mut xs">{t("To'lov, bitim va buyurtma holati haqidagi muhim xabarlar doim yuboriladi.")}</div>
      </div>
      <PinFlow mode={mode} onClose={() => setMode(null)} onDone={async (msg) => { setMode(null); await refreshMe(); toast(msg, "ok"); }} bioReason={t("VAYNEXO'ni tez ochish uchun")} />
    </>
  );
}

/** PIN o'rnatish / almashtirish / o'chirish / biometriyani yoqish. */
function PinFlow({ mode, onClose, onDone, bioReason }: { mode: PinMode; onClose: () => void; onDone: (msg: string) => void; bioReason: string }) {
  const [step, setStep] = useState<"old" | "new" | "repeat">("new");
  const [oldPin, setOldPin] = useState("");
  const [first, setFirst] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    setStep(mode === "change" || mode === "remove" || mode === "bio" ? "old" : "new");
    setOldPin(""); setFirst(""); setErr("");
  }, [mode]);
  if (!mode) return null;
  const title = step === "old" ? t("Joriy PIN-kodni kiriting") : step === "new" ? t("Yangi PIN-kod (4 raqam)") : t("PIN-kodni takrorlang");
  const submit = async (pin: string) => {
    setErr("");
    try {
      setBusy(true);
      if (step === "old") {
        if (mode === "remove") {
          await api.post("/me/pin/remove", { pin });
          setPinToken(null);
          await bioClear();
          return onDone(t("PIN-kod o'chirildi"));
        }
        if (mode === "bio") {
          const { key } = await api.post<{ key: string }>("/me/pin/bio", { pin });
          const saved = await bioSave(key, bioReason);
          if (!saved) {
            await api.post("/me/pin/bio/off");
            setErr(t("Biometriyaga ruxsat berilmadi"));
            setAttempt((x) => x + 1);
            return;
          }
          return onDone(t("Biometrik kirish yoqildi"));
        }
        setOldPin(pin);
        setStep("new");
        return;
      }
      if (step === "new") {
        setFirst(pin);
        setStep("repeat");
        return;
      }
      if (pin !== first) {
        setErr(t("PIN-kodlar mos kelmadi"));
        setAttempt((x) => x + 1);
        setStep("new");
        return;
      }
      const r = await api.post<{ token: string }>("/me/pin", { pin, old_pin: oldPin || undefined });
      setPinToken(r.token);
      await bioClear();
      onDone(mode === "change" ? t("PIN-kod almashtirildi") : t("PIN-kod o'rnatildi"));
    } catch (e) {
      setErr(errorText(e));
      setAttempt((x) => x + 1);
      if (e instanceof ApiError && (e.code === "weak_pin" || e.code === "bad_pin")) setStep("new");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet open onClose={onClose}>
      <PinPad title={title} error={err} busy={busy} onComplete={submit} key={step + mode + attempt} />
    </Sheet>
  );
}

/** 4 xonali PIN klaviaturasi. */
export function PinPad({ title, error, busy, onComplete, extra }: { title: string; error?: string; busy?: boolean; onComplete: (pin: string) => void; extra?: ReactNode }) {
  const [pin, setPin] = useState("");
  const done = useRef(false);
  useEffect(() => {
    if (error) { setPin(""); done.current = false; haptic("error"); }
  }, [error]);
  const press = (d: string) => {
    if (busy || done.current) return;
    haptic();
    const next = (pin + d).slice(0, 4);
    setPin(next);
    if (next.length === 4) {
      done.current = true;
      setTimeout(() => { onComplete(next); }, 120);
    }
  };
  return (
    <div className="pinpad">
      <div className="b center" style={{ fontSize: 18 }}>{title}</div>
      <div className="pindots">{[0, 1, 2, 3].map((i) => <span key={i} className={i < pin.length ? "on" : ""} />)}</div>
      <div className="r sm center" style={{ minHeight: 18 }}>{error}</div>
      <div className="pinkeys">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => <button key={d} onClick={() => press(d)}>{d}</button>)}
        <div>{extra}</div>
        <button onClick={() => press("0")}>0</button>
        <button className="mut" aria-label={t("O'chirish")} onClick={() => { done.current = false; setPin((p) => p.slice(0, -1)); }}>⌫</button>
      </div>
    </div>
  );
}

/** Ilova ochilganda PIN so'raydigan ekran. */
export function PinLock({ bio, onUnlock }: { bio: boolean; onUnlock: () => void }) {
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [n, setN] = useState(0);
  const tryBio = async () => {
    const key = await bioRead(t("VAYNEXO'ni ochish"));
    if (!key) return;
    try {
      const r = await api.post<{ token: string }>("/me/pin/bio/verify", { key });
      setPinToken(r.token);
      onUnlock();
    } catch (e) {
      setErr(errorText(e));
    }
  };
  useEffect(() => {
    if (bio) tryBio();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="pinlock">
      <div className="hd-ico" style={{ width: 56, height: 56, borderRadius: 16, margin: "0 auto 8px" }}><Icon name="lock" size={28} /></div>
      <PinPad key={n} title={t("PIN-kodni kiriting")} error={err} busy={busy}
        extra={bio ? <button className="y" onClick={tryBio} aria-label={t("Biometrik kirish")}><Icon name="user" /></button> : null}
        onComplete={async (pin) => {
          setBusy(true);
          setErr("");
          try {
            const r = await api.post<{ token: string }>("/me/pin/verify", { pin });
            setPinToken(r.token);
            onUnlock();
          } catch (e) {
            setErr(errorText(e));
            setN((x) => x + 1);
          } finally {
            setBusy(false);
          }
        }} />
      <div className="mut xs center" style={{ marginTop: 16 }}>{t("PIN-kodni unutdingizmi? @vaynexo_support ga yozing.")}</div>
    </div>
  );
}

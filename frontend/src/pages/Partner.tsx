import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { t } from "../i18n";
import { copyText } from "../tg";
import { BottomNav, Empty, Header, Icon, Loadable, som, useAction, useApp, useLoad } from "../ui";

interface Tier { tier: number; views: number; reward: string; done: boolean }
interface Video { id: number; platform: string; url: string; status: string; views: number; likes: number; tier: number; reward: string; note: string | null; created_at: string }
interface Overview {
  tiers: Tier[];
  videos: Video[];
  stats: { sent: number; views: number; pending: number; to_official: number };
  rules: { min_views: number; count_days: number; interval_days: number; like_ratio: number };
  code: { code: string; uses: number; max_uses: number; bonus: number; active: boolean } | null;
  code_terms: { bonus: number; points: number; need_videos: number; approved: number };
  leaderboard: { place: number; name: string; views: number; official: boolean }[];
  ideas: { title: string; text: string }[];
  hashtags: string;
}

const fmtN = (n: number) => n.toLocaleString("ru-RU").replace(/,/g, " ");
const TIER_ICON = ["", "doc", "trophy", "gift", "admin"];
const PLATFORMS = [
  { v: "tiktok", label: "TikTok", ph: "https://www.tiktok.com/@nik/video/..." },
  { v: "instagram", label: "Instagram", ph: "https://www.instagram.com/reel/..." },
  { v: "youtube", label: "YouTube", ph: "https://youtube.com/shorts/..." },
];

export default function Partner() {
  const nav = useNavigate();
  const st = useLoad(() => api.get<Overview>("/partner"));
  const [tab, setTab] = useState<"rewards" | "code" | "send" | "ideas" | "top" | "rules">("rewards");
  return (
    <>
      <Header title={t("Hamkor")} sub={t("Video joylang — mukofot oling")} back={false} icon="play" />
      <div className="page">
        <Loadable state={st}>
          {(d) => (
            <>
              <div className="hero col" style={{ gap: 8, borderColor: "rgba(255,214,10,.45)" }}>
                <div className="hf bb" style={{ fontSize: 20 }}>{t("Video qil — mukofot ol")}</div>
                <div className="sm" style={{ color: "#d6dbe8" }}>{t("VAYNEXO haqida video joylang — ko'rishlar uchun mukofot oling.")}</div>
                <span className="pill-y">{t("Eng kami: {v} ko'rish · {d} kun ichida", { v: fmtN(d.rules.min_views), d: d.rules.count_days })}</span>
              </div>
              <div className="card col">
                <div className="row between">
                  <div className="row" style={{ gap: 18 }}>
                    <div><div className="hf bb" style={{ fontSize: 20 }}>{d.stats.sent}</div><div className="mut xs">{t("yuborilgan")}</div></div>
                    <div><div className="hf bb" style={{ fontSize: 20 }}>{fmtN(d.stats.views)}</div><div className="mut xs">{t("jami ko'rish")}</div></div>
                    <div><div className="hf bb" style={{ fontSize: 20 }}>{d.stats.pending}</div><div className="mut xs">{t("tekshiruvda")}</div></div>
                  </div>
                  <span className="pill-b y">{t("Hamkor")}</span>
                </div>
                <div className="progress"><i style={{ width: Math.min(100, Math.round((d.stats.views / (d.tiers[3]?.views || 1)) * 100)) + "%", background: "var(--g)" }} /></div>
                <div className="mut xs">{d.stats.to_official > 0 ? t("«Rasmiy hamkor»gacha {n} ko'rish qoldi", { n: fmtN(d.stats.to_official) }) : t("Siz «Rasmiy hamkor»siz!")}</div>
              </div>
              <div className="sec-title">💸 {t("Ko'proq daromad")}</div>
              <div className="adm2-list">
                {[
                  ["🎥", t("Striminer paneli"), t("Efirda almaz va pul donati qabul qiling"), "/streamer"],
                  ["🎮", t("Pro bo'lish"), t("O'yin joyingizni auksionda soting"), "/pro/my"],
                  ["🏪", t("O'z do'koningni och"), t("Mijozlar xarididan 3–6% komissiya"), "/shop"],
                ].map(([i, a, b, to]) => (
                  <button key={to} className="adm2-it" onClick={() => nav(to)}>
                    <span style={{ fontSize: 24, width: 34 }}>{i}</span>
                    <div className="grow" style={{ textAlign: "left", minWidth: 0 }}><div className="b">{a}</div><div className="mut xs ell">{b}</div></div>
                    <Icon name="right" size={17} className="mut" />
                  </button>
                ))}
              </div>
              <div className="tabs5">
                {([["rewards", "Mukofotlar"], ["code", "Promo-kod"], ["send", "Yuborish"], ["ideas", "G'oyalar"], ["top", "Reyting"], ["rules", "Shartlar"]] as const).map(([v, l]) => (
                  <button key={v} className={tab === v ? "on" : ""} onClick={() => setTab(v)}>{t(l)}</button>
                ))}
              </div>
              {tab === "rewards" && <Rewards d={d} />}
              {tab === "code" && <Code d={d} onDone={st.reload} />}
              {tab === "ideas" && <Ideas d={d} />}
              {tab === "top" && <PartnerTop d={d} />}
              {tab === "rules" && <Rules d={d} />}
              {tab === "send" && <Send d={d} onSent={st.reload} />}
            </>
          )}
        </Loadable>
      </div>
      <BottomNav />
    </>
  );
}

function Rewards({ d }: { d: Overview }) {
  return (
    <>
      {d.tiers.map((x) => (
        <div key={x.tier} className={"card row" + (x.done ? " tier-done" : "")}>
          <span className="hd-ico" style={{ width: 42, height: 42, background: x.done ? "rgba(29,233,182,.15)" : "rgba(255,214,10,.12)", color: x.done ? "var(--g)" : "var(--y)" }}><Icon name={TIER_ICON[x.tier]} /></span>
          <div className="grow">
            <div className="y mono b sm">{fmtN(x.views)}+ {t("ko'rish")}</div>
            <div className="b">{t(x.reward)}</div>
          </div>
          {x.done ? <span className="g b sm">✓ {t("Olindi")}</span> : <span className="mut">—</span>}
        </div>
      ))}
      <div className="card col" style={{ borderColor: "rgba(255,214,10,.4)" }}>
        <div className="y mono b sm">{fmtN(d.tiers[3]?.views ?? 50000)}+ {t("ko'rishdan yuqori")}</div>
        <div className="b">{t("Shaxsiy shartnoma")}</div>
        <div className="mut xs">{t("Yirik hamkorlar bilan mukofot va shartlar admin tomonidan alohida kelishiladi.")}</div>
      </div>
    </>
  );
}

function Rules({ d }: { d: Overview }) {
  const rules: [string, string][] = [
    ["eye", t("Video joylangandan so'ng {d} kun ichida kamida {v} ko'rish", { d: d.rules.count_days, v: fmtN(d.rules.min_views) })],
    ["star", t("Layklar ko'rishlarning kamida {p} foizi (sun'iy ko'rishlar qabul qilinmaydi)", { p: d.rules.like_ratio })],
    ["doc", t("Videoda VAYNEXO logotipi yoki VAYNEXO haqida ma'lumot bo'lishi, tavsifda #vaynexo va #vaynexobot heshteglari")],
    ["send", t("Post yoki Reels'da @vaynexobot sahifasini belgilash (otmetka)")],
    ["clock", t("Akkaunt kamida 1 oylik bo'lishi; bir kishi {d} kunda 1 ta video yuborishi mumkin", { d: d.rules.interval_days })],
    ["check", t("Ko'rishlar statistikasi skrinshoti talab qilinishi mumkin")],
  ];
  return (
    <div className="card col">
      {rules.map(([ic, txt]) => (
        <div key={txt} className="row sm" style={{ alignItems: "flex-start" }}><span className="y"><Icon name={ic === "eye" ? "search" : ic} size={16} /></span><span>{txt}</span></div>
      ))}
    </div>
  );
}

const STATUS: Record<string, [string, string]> = { pending: ["Tekshirilmoqda", "y"], approved: ["Tasdiqlandi", "g"], rejected: ["Rad etildi", "r"] };

function Send({ d, onSent }: { d: Overview; onSent: () => void }) {
  const { toast } = useApp();
  const [pf, setPf] = useState("tiktok");
  const [url, setUrl] = useState("");
  const { busy, run } = useAction();
  return (
    <>
      <div className="card col">
        <div className="seg3">
          {PLATFORMS.map((p) => (
            <button key={p.v} className={pf === p.v ? "on" : ""} onClick={() => setPf(p.v)}>{p.label}</button>
          ))}
        </div>
        <input className="input" inputMode="url" placeholder={PLATFORMS.find((p) => p.v === pf)!.ph} value={url} onChange={(e) => setUrl(e.target.value)} />
        <button className="btn full" disabled={url.trim().length < 10 || busy} onClick={() => run(async () => {
          await api.post("/partner/videos", { url: url.trim() });
          setUrl("");
          toast(t("Video tekshiruvga yuborildi. Ko'rishlar {d} kundan keyin hisoblanadi.", { d: d.rules.count_days }), "ok");
          onSent();
        })}>{t("Videoni yuborish")}</button>
      </div>
      <div className="sec-title">{t("Mening videolarim")}</div>
      {d.videos.length === 0 ? <Empty icon="🎬" text={t("Hali video yuborilmagan")} /> : d.videos.map((v) => {
        const [lbl, cls] = STATUS[v.status] ?? [v.status, "m"];
        return (
          <div key={v.id} className="card row tight">
            <span className={"pf-ico " + v.platform}>{v.platform === "tiktok" ? "♪" : v.platform === "youtube" ? "▶" : "◎"}</span>
            <div className="grow" style={{ minWidth: 0 }}>
              <div className="b ell sm">{v.url.replace(/^https:\/\//, "")}</div>
              <div className="mut xs ell">
                {v.status === "approved" ? `${fmtN(v.views)} ${t("ko'rish")} · ${t(v.reward)}` : v.status === "rejected" ? (v.note ? t(v.note) : "") : t("Ko'rishlar {d} kundan so'ng hisoblanadi", { d: d.rules.count_days })}
              </div>
            </div>
            <span className={"pill-b " + cls}>{t(lbl)}</span>
          </div>
        );
      })}
    </>
  );
}

function Code({ d, onDone }: { d: Overview; onDone: () => void }) {
  const { toast } = useApp();
  const [code, setCode] = useState("");
  const { busy, run } = useAction();
  const ct = d.code_terms;
  if (d.code) return (
    <div className="card col" style={{ borderColor: "rgba(255,214,10,.45)", gap: 10 }}>
      <div className="mut xs">{t("Shaxsiy promo-kodingiz")}</div>
      <button className="hf bb y" style={{ fontSize: 30, background: "none", border: 0, letterSpacing: ".06em" }} onClick={() => { copyText(d.code!.code); toast(t("Nusxalandi"), "ok"); }}>{d.code.code} ⧉</button>
      <div className="row" style={{ gap: 18 }}>
        <div><div className="hf bb" style={{ fontSize: 20 }}>{d.code.uses}</div><div className="mut xs">{t("foydalanildi")}</div></div>
        <div><div className="hf bb g" style={{ fontSize: 20 }}>+{fmtN(d.code.uses * ct.points)}</div><div className="mut xs">{t("ball oldingiz")}</div></div>
      </div>
      <div className="sm">{t("Tomoshabin kodni Hamyon → Promo-kod bo'limida kiritadi va {b} bonus oladi. Siz har foydalanishda +{p} ball olasiz.", { b: som(ct.bonus), p: ct.points })}</div>
      <button className="btn ghost full" onClick={() => { copyText(`${d.code!.code} — VAYNEXO promo-kodi: hamyonga ${som(ct.bonus)} bonus! @vaynexobot`); toast(t("Nusxalandi"), "ok"); }}>{t("Video tavsifi uchun matnni nusxalash")}</button>
    </div>
  );
  const can = ct.approved >= ct.need_videos;
  return (
    <div className="card col">
      <div className="b">{t("Shaxsiy promo-kod oling")}</div>
      <div className="sm">{t("Videoda kodingizni ayting: tomoshabin {b} bonus oladi, siz esa har foydalanishda +{p} ball.", { b: som(ct.bonus), p: ct.points })}</div>
      {can ? (
        <>
          <input className="input mono" maxLength={16} placeholder="NIKNAME" value={code} onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9_-]/g, ""))} />
          <button className="btn full" disabled={code.length < 4 || busy} onClick={() => run(async () => { await api.post("/partner/code", { code }); toast(t("Promo-kod yaratildi"), "ok"); onDone(); })}>{t("Kod yaratish")}</button>
        </>
      ) : (
        <div className="pill-b y" style={{ alignSelf: "flex-start" }}>{t("Kamida {n} ta tasdiqlangan video kerak ({h}/{n})", { n: ct.need_videos, h: ct.approved })}</div>
      )}
    </div>
  );
}

function Ideas({ d }: { d: Overview }) {
  const { toast } = useApp();
  return (
    <>
      <div className="card row" style={{ borderColor: "rgba(255,214,10,.4)" }}>
        <div className="grow"><div className="b sm">{t("Heshteglar")}</div><div className="mut xs mono">{d.hashtags}</div></div>
        <button className="btn small ghost" onClick={() => { copyText(d.hashtags); toast(t("Nusxalandi"), "ok"); }}>{t("Nusxa")}</button>
      </div>
      {d.ideas.map((x, i) => (
        <div key={x.title} className="card row" style={{ alignItems: "flex-start" }}>
          <span className="mono y bb" style={{ width: 22 }}>{i + 1}</span>
          <div className="grow"><div className="b">{t(x.title)}</div><div className="mut sm">{t(x.text)}</div></div>
        </div>
      ))}
    </>
  );
}

function PartnerTop({ d }: { d: Overview }) {
  return d.leaderboard.length === 0 ? <Empty icon="🏆" text={t("Bu oy hali tasdiqlangan videolar yo'q")} /> : (
    <div className="card" style={{ padding: "4px 14px" }}>
      <div className="mut xs" style={{ padding: "8px 0" }}>{t("Oxirgi 30 kun · tasdiqlangan ko'rishlar")}</div>
      {d.leaderboard.map((r) => (
        <div key={r.place} className="listrow">
          <span className="mono b" style={{ width: 28 }}>{["🥇", "🥈", "🥉"][r.place - 1] ?? r.place}</span>
          <span className="grow b ell">{r.name} {r.official && <span className="pill-b y" style={{ fontSize: 10 }}>{t("Rasmiy hamkor")}</span>}</span>
          <span className="y mono b">{fmtN(r.views)}</span>
        </div>
      ))}
    </div>
  );
}

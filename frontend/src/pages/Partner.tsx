import { useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import { BottomNav, Empty, Header, Icon, Loadable, Seg, useAction, useApp, useLoad } from "../ui";

interface Tier { tier: number; views: number; reward: string; done: boolean }
interface Video { id: number; platform: string; url: string; status: string; views: number; likes: number; tier: number; reward: string; note: string | null; created_at: string }
interface Overview {
  tiers: Tier[];
  videos: Video[];
  stats: { sent: number; views: number; pending: number; to_official: number };
  rules: { min_views: number; count_days: number; interval_days: number; like_ratio: number };
}

const fmtN = (n: number) => n.toLocaleString("ru-RU").replace(/,/g, " ");
const TIER_ICON = ["", "doc", "trophy", "gift", "admin"];
const PLATFORMS = [
  { v: "tiktok", label: "TikTok", ph: "https://www.tiktok.com/@nik/video/..." },
  { v: "instagram", label: "Instagram", ph: "https://www.instagram.com/reel/..." },
  { v: "youtube", label: "YouTube", ph: "https://youtube.com/shorts/..." },
];

export default function Partner() {
  const st = useLoad(() => api.get<Overview>("/partner"));
  const [tab, setTab] = useState<"rewards" | "rules" | "send">("rewards");
  return (
    <>
      <Header title={t("Hamkor")} sub={t("Video joylang — mukofot oling")} back={false} icon="play" />
      <div className="page">
        <Loadable state={st}>
          {(d) => (
            <>
              <div className="hero col" style={{ gap: 8, borderColor: "rgba(255,214,10,.45)" }}>
                <div className="hf bb" style={{ fontSize: 21 }}>{t("Video qil — mukofot ol")}</div>
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
              <Seg value={tab} onChange={setTab} options={[{ v: "rewards", label: t("Mukofotlar") }, { v: "rules", label: t("Shartlar") }, { v: "send", label: t("Yuborish") }]} />
              {tab === "rewards" && <Rewards d={d} />}
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

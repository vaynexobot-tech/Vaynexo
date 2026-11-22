// Draft simulyatori: ko'k va qizil jamoa uchun ban/pick (20 qadam), har qadamda tavsiya va oxirida jamoalar taqqoslanishi.
// Ma'lumot: Rone Arena rank statistikasi (WR, pick, ban, sheriklar) + counter (raqib tanlaganda).
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import { HERO_BY_ID, HEROES, HeroAva, HeroPicker, laneLabel, MlIcon } from "../mlbb";
import { Icon, Loadable, Seg, useLoad } from "../ui";
import { STAT_RANKS, type Stat } from "./Heroes";

type Side = "blue" | "red";
type Act = "ban" | "pick";
type Step = [Side, Act];
type Mode = "mpl" | "rank";

const B: Side = "blue", R: Side = "red";
const ORDER: Record<Mode, Step[]> = {
  // Turnir (MPL): 6 ban → 6 pick → 4 ban → 4 pick
  mpl: [[B, "ban"], [R, "ban"], [B, "ban"], [R, "ban"], [B, "ban"], [R, "ban"],
    [B, "pick"], [R, "pick"], [R, "pick"], [B, "pick"], [B, "pick"], [R, "pick"],
    [R, "ban"], [B, "ban"], [R, "ban"], [B, "ban"],
    [R, "pick"], [B, "pick"], [B, "pick"], [R, "pick"]],
  // Rank (Mythic, 10 ban): 10 ban navbat bilan → pick 1-2-2-2-2-1
  rank: [[B, "ban"], [R, "ban"], [B, "ban"], [R, "ban"], [B, "ban"], [R, "ban"], [B, "ban"], [R, "ban"], [B, "ban"], [R, "ban"],
    [B, "pick"], [R, "pick"], [R, "pick"], [B, "pick"], [B, "pick"], [R, "pick"], [R, "pick"], [B, "pick"], [B, "pick"], [R, "pick"]],
};
const SIDE_LABEL: Record<Side, string> = { blue: "Ko'k jamoa", red: "Qizil jamoa" };
const SHORT: Record<Side, string> = { blue: "Ko'k", red: "Qizil" };
const LANES_ALL = ["exp", "jungle", "mid", "gold", "roam"];

interface Rec { id: number; score: number; why: string }
interface Counter { hero: number; counters: { hero: number; win: number; inc: number }[] }

export default function Draft() {
  const [mode, setMode] = useState<Mode>(() => (localStorage.getItem("vx_draft_mode") as Mode) || "rank");
  const [rank, setRank] = useState("mythic");
  const [moves, setMoves] = useState<number[]>([]);
  const [picker, setPicker] = useState(false);
  const counters = useRef<Record<number, Counter>>({});
  const [, bump] = useState(0);
  const st = useLoad(() => api.get<{ items: Stat[] }>(`/mlbb/stats?rank=${rank}&days=7`), [rank]);
  useEffect(() => { try { localStorage.setItem("vx_draft_mode", mode); } catch { /* yo'q */ } }, [mode]);

  const order = ORDER[mode];
  const step = order[moves.length] as Step | undefined;
  const team = (side: Side, act: Act) => moves.filter((_, i) => order[i][0] === side && order[i][1] === act);
  const used = new Set(moves);
  // Raqib tanlagan qahramonlarga counter ma'lumoti (har biriga bir marta so'rov, serverda 6 soat kesh)
  useEffect(() => {
    moves.forEach((id, i) => {
      if (order[i][1] !== "pick" || counters.current[id]) return;
      counters.current[id] = { hero: id, counters: [] };
      api.get<Counter>(`/mlbb/counters/${id}?rank=${rank}`).then((c) => { counters.current[id] = c; bump((x) => x + 1); }).catch(() => undefined);
    });
  }, [moves, order, rank]);

  const stats = useMemo(() => Object.fromEntries((st.data?.items ?? []).map((s) => [s.hero, s])) as Record<number, Stat>, [st.data]);
  const recs = useMemo<Rec[]>(() => {
    if (!step || !st.data) return [];
    const [side, act] = step;
    const other: Side = side === "blue" ? "red" : "blue";
    const mine = team(side, "pick"), theirs = team(other, "pick");
    const myLanes = new Set(mine.map((h) => HERO_BY_ID[h]?.lane));
    const out: Rec[] = [];
    for (const h of HEROES) {
      if (used.has(h.id)) continue;
      const s = stats[h.id];
      if (!s) continue;
      let score = s.win - 50 + s.pick * 0.12;
      const why: string[] = [`${laneLabel(h.lane)} ${t("yo'lak")}`, `WR ${s.win.toFixed(1)}%`];
      if (act === "ban") {
        score += s.ban * 0.08;
        why.push(`ban ${s.ban.toFixed(1)}%`);
        const threat = mine.map((m) => counters.current[m]?.counters.find((c) => c.hero === h.id)).filter(Boolean);
        if (threat.length) { score += threat.reduce((a, c) => a + Math.max(1, c!.inc), 0) * 1.5; why.push(t("jamoangizga xavfli")); }
        const enemyMate = theirs.some((e) => stats[e]?.mates.some((m) => m.hero === h.id));
        if (enemyMate) { score += 1.5; why.push(t("raqibga juft")); }
      } else {
        const beats = theirs.filter((e) => counters.current[e]?.counters.some((c) => c.hero === h.id));
        if (beats.length) { score += beats.length * 3; why.push(`${t("kontr")}: ${beats.map((e) => HERO_BY_ID[e]?.name).join(", ")}`); }
        const pair = mine.find((m) => stats[m]?.mates.some((x) => x.hero === h.id));
        if (pair) { score += 2; why.push(`${t("juft")}: ${HERO_BY_ID[pair]?.name}`); }
        if (mine.length) score += myLanes.has(h.lane) ? -4 : 2.5;
      }
      out.push({ id: h.id, score, why: why.join(", ") });
    }
    return out.sort((a, b) => b.score - a.score).slice(0, 8);
  }, [step, st.data, moves, stats]); // eslint-disable-line react-hooks/exhaustive-deps

  const choose = (id: number) => { if (step && !used.has(id)) setMoves([...moves, id]); };
  const done = moves.length >= order.length;

  return (
    <>
      <div className="draft-hd">
        <div><div className="hf bb" style={{ fontSize: 20 }}>{t("Draft simulyatori")}</div><div className="mut xs">{t("Ikkala jamoa uchun ban va pick qiling — har qadamda tavsiya")}</div></div>
      </div>
      <Seg value={mode} onChange={(v) => { setMode(v); setMoves([]); }} options={[{ v: "mpl", label: t("Turnir (MPL)") }, { v: "rank", label: t("Rank (Mythic)") }]} />
      <div className="chips-scroll">
        {STAT_RANKS.map((r) => (
          <button key={r.v} className={"chip row" + (rank === r.v ? " on" : "")} style={{ gap: 4 }} onClick={() => setRank(r.v)}>
            {r.icon && <MlIcon kind="rank" k={r.icon} size={18} />}{t(r.label)}
          </button>
        ))}
      </div>

      <TeamBox side="blue" bans={team("blue", "ban")} picks={team("blue", "pick")} active={step?.[0] === "blue" ? step[1] : null} />
      <div className="draft-step">{done ? t("Draft tugadi") : `${moves.length + 1}/${order.length}: ${t(SHORT[step![0]])} — ${step![1] === "ban" ? "ban" : "pick"}`}</div>
      <TeamBox side="red" bans={team("red", "ban")} picks={team("red", "pick")} active={step?.[0] === "red" ? step[1] : null} />

      <div className="row" style={{ gap: 8 }}>
        <button className="btn grow" disabled={done} onClick={() => setPicker(true)}><Icon name="search" size={17} /> {t("Qahramon tanlash")}</button>
        <button className="btn ghost" disabled={!moves.length} onClick={() => setMoves(moves.slice(0, -1))} aria-label={t("Orqaga")}><Icon name="back" size={18} /></button>
        <button className="btn ghost" disabled={!moves.length} onClick={() => setMoves([])} aria-label={t("Qaytadan")}><Icon name="refresh" size={18} /></button>
      </div>

      {done ? <Summary blue={team("blue", "pick")} red={team("red", "pick")} stats={stats} counters={counters.current} /> : (
        <Loadable state={st}>
          {() => (
            <>
              <div className={"sec-title draft-q " + step![0]}>{t(SIDE_LABEL[step![0]])} {step![1] === "ban" ? t("kimni bansin?") : t("kimni olsin?")}</div>
              {recs.length === 0 ? <div className="mut sm">{t("Statistika hozircha yo'q — qahramonni o'zingiz tanlang")}</div> : recs.map((r, i) => (
                <button key={r.id} className="card row draft-rec" onClick={() => choose(r.id)}>
                  <span className="y bb" style={{ width: 18 }}>{i + 1}</span>
                  <HeroAva id={r.id} size={52} radius={12} />
                  <div className="grow" style={{ minWidth: 0, textAlign: "left" }}>
                    <div className="b">{HERO_BY_ID[r.id]?.name}</div>
                    <div className="mut xs">{r.why}</div>
                  </div>
                  <span className={"bb mono " + (r.score >= 0 ? "g" : "r")} style={{ fontSize: 17 }}>{r.score >= 0 ? "+" : ""}{r.score.toFixed(1)}</span>
                </button>
              ))}
            </>
          )}
        </Loadable>
      )}
      <HeroPicker open={picker} value={[]} max={1} disabled={moves} onClose={() => setPicker(false)} onChange={(v) => v[0] && choose(v[0])} />
    </>
  );
}

function TeamBox({ side, bans, picks, active }: { side: Side; bans: number[]; picks: number[]; active: Act | null }) {
  return (
    <div className={"draft-team " + side + (active ? " act" : "")}>
      <div className="row between">
        <span className="bb">{t(SIDE_LABEL[side])}</span>
        <div className="row" style={{ gap: 5 }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <span key={i} className={"draft-ban" + (active === "ban" && i === bans.length ? " next" : "")}>
              {bans[i] ? <HeroAva id={bans[i]} size={30} radius={8} /> : <Icon name="x" size={14} />}
            </span>
          ))}
        </div>
      </div>
      <div className="draft-picks">
        {Array.from({ length: 5 }).map((_, i) => (
          <span key={i} className={"draft-pick" + (active === "pick" && i === picks.length ? " next" : "")}>
            {picks[i] ? <><HeroAva id={picks[i]} size={56} radius={12} /><span className="xs ell">{HERO_BY_ID[picks[i]]?.name}</span></> : null}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Draft yakuni: jamoalar taqqoslanishi (o'rtacha WR, counterlar, liniyalar) va taxminiy ustunlik. */
function Summary({ blue, red, stats, counters }: { blue: number[]; red: number[]; stats: Record<number, Stat>; counters: Record<number, Counter> }) {
  const calc = (mine: number[], theirs: number[]) => {
    const wr = mine.reduce((a, h) => a + (stats[h]?.win ?? 50), 0) / Math.max(1, mine.length);
    const kontr = mine.reduce((a, h) => a + theirs.filter((e) => counters[e]?.counters.some((c) => c.hero === h)).length, 0);
    const lanes = new Set(mine.map((h) => HERO_BY_ID[h]?.lane)).size;
    return { wr, kontr, lanes, score: (wr - 50) * 2 + kontr * 3 + (lanes - 5) * 2 };
  };
  const b = calc(blue, red), r = calc(red, blue);
  const diff = b.score - r.score;
  const blueChance = Math.round(Math.min(80, Math.max(20, 50 + diff * 2.5)));
  return (
    <div className="card col" style={{ gap: 12 }}>
      <div className="bb" style={{ fontSize: 16 }}>{t("Jamoalarni solishtirish")}</div>
      <div className="draft-bar"><i className="blue" style={{ width: `${blueChance}%` }}>{blueChance}%</i><i className="red" style={{ width: `${100 - blueChance}%` }}>{100 - blueChance}%</i></div>
      <div className="mut xs">{t("Taxminiy g'alaba ehtimoli (statistika asosida, o'yinchi mahorati hisobga olinmaydi)")}</div>
      {([["O'rtacha WR", `${b.wr.toFixed(1)}%`, `${r.wr.toFixed(1)}%`], ["Kontr-pick", String(b.kontr), String(r.kontr)],
        ["Liniyalar to'liq", `${b.lanes}/5`, `${r.lanes}/5`]] as const).map(([l, x, y]) => (
        <div key={l} className="row between sm"><span className="b" style={{ color: "#4da3ff" }}>{x}</span><span className="mut">{t(l)}</span><span className="b" style={{ color: "#ff5a6e" }}>{y}</span></div>
      ))}
      {[...new Set(LANES_ALL)].some((l) => !blue.some((h) => HERO_BY_ID[h]?.lane === l)) && (
        <div className="mut xs">{t("Ko'k jamoada yo'q liniya")}: {LANES_ALL.filter((l) => !blue.some((h) => HERO_BY_ID[h]?.lane === l)).map(laneLabel).join(", ")}</div>
      )}
    </div>
  );
}

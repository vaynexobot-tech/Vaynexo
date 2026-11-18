import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Tournament } from "../api";
import { t } from "../i18n";
import { BottomBar, BottomNav, Chips, dateTime, Empty, Field, GameLogo, Header, Icon, Loadable, money, Seg, Sheet, som, useAction, useApp, useLoad } from "../ui";
import { Risers } from "./Heroes";
import { HERO_BY_ID, HeroAva, HeroPicker, HeroSlots, LANES, LanePicker, laneKey, laneLabel, MlIcon, RankPicker, rankKey, rankLabel, roleLabel } from "../mlbb";

interface Summary {
  points: number; passes: number; vip_credit_days: number; boost_coupon_percent: number;
  prediction: { id: number; title: string; team_a: string; team_b: string; starts_at: string; my_pick: string | null; points: number } | null;
  points_rules: Record<string, number>;
}

export function Arena() {
  const [tab, setTab] = useState<"tours" | "games" | "team" | "rating" | "missions">(() => (sessionStorage.getItem("vx_arena_tab") as never) || "tours");
  const sum = useLoad(() => api.get<Summary>("/arena/summary"));
  const pick = (v: typeof tab) => { setTab(v); try { sessionStorage.setItem("vx_arena_tab", v); } catch { /* yo'q */ } };
  return (
    <>
      <Header title={t("Arena")} sub={t("Turnir, viktorina, jamoa, reyting")} back={false} icon="arena"
        right={<span className="pts-pill">🏅 {money(sum.data?.points ?? 0)}</span>} />
      <div className="page">
        <MlCard />
        <div className="tabs5">
          {([["tours", "Turnirlar"], ["games", "O'yinlar"], ["team", "Jamoa"], ["rating", "Reyting"], ["missions", "Vazifalar"]] as const).map(([v, l]) => (
            <button key={v} className={tab === v ? "on" : ""} onClick={() => pick(v)}>{t(l)}</button>
          ))}
        </div>
        {tab === "tours" && <Tours sum={sum.data} reload={sum.reload} />}
        {tab === "games" && <Games onPoints={sum.reload} />}
        {tab === "team" && <Team />}
        {tab === "rating" && <Rating rules={sum.data?.points_rules} />}
        {tab === "missions" && <Missions onChange={sum.reload} />}
      </div>
      <BottomNav />
    </>
  );
}

function Tours({ sum, reload }: { sum: Summary | null; reload: () => void }) {
  const nav = useNavigate();
  const [status, setStatus] = useState<"open" | "soon" | "finished">("open");
  const st = useLoad(() => api.get<Tournament[]>(`/tournaments?status=${status}`), [status]);
  const { run } = useAction();
  const p = sum?.prediction;
  return (
    <>
      <Chips value={status} onChange={setStatus} options={[{ v: "open", label: t("Faol") }, { v: "soon", label: t("Tez kunda") }, { v: "finished", label: t("Tugagan") }]} />
      <Loadable state={st}>
        {(list) => list.length === 0 ? <Empty icon="🏆" text={t("Hozircha turnirlar yo'q")} /> : (
          <>
            {list.map((x) => <TourCard key={x.id} x={x} onClick={() => nav(`/arena/${x.id}`)} />)}
          </>
        )}
      </Loadable>
      {p && (
        <div className="card col">
          <div className="row between"><span className="b">🎯 {t("Bepul prognoz")}</span><span className="pill-b g">+{p.points} {t("ball")}</span></div>
          <div className="mut xs">{p.title} · {dateTime(p.starts_at)}</div>
          <div className="vs-row">
            <button className={p.my_pick === "a" ? "on" : ""} disabled={!!p.my_pick} onClick={() => run(async () => { await api.post(`/arena/predictions/${p.id}`, { pick: "a" }); reload(); })}>{p.team_a}</button>
            <span className="mut b">VS</span>
            <button className={p.my_pick === "b" ? "on" : ""} disabled={!!p.my_pick} onClick={() => run(async () => { await api.post(`/arena/predictions/${p.id}`, { pick: "b" }); reload(); })}>{p.team_b}</button>
          </div>
          <div className="mut xs">{p.my_pick ? t("Tanlovingiz qabul qilindi. Natija chiqqach ball beriladi.") : t("G'olibni tanlang. To'g'ri topsangiz ball olasiz — pul tikilmaydi.")}</div>
        </div>
      )}
    </>
  );
}

function TourCard({ x, onClick }: { x: Tournament; onClick: () => void }) {
  const pct = Math.round((x.players_count / x.max_players) * 100);
  const badge = x.status === "finished" ? ["Tugagan", "m"] : x.status === "soon" ? ["Tez kunda", "b"] : ["Faol", "g"];
  return (
    <div className="card col" style={{ gap: 10 }}>
      <div className="row">
        <GameLogo game={x.game} size={46} />
        <div className="grow" style={{ minWidth: 0 }}>
          <div className="b ell">{x.title}</div>
          <div className="mut xs">{x.game === "ML" ? "Mobile Legends" : "Magic Chess"} · {dateTime(x.starts_at)}</div>
        </div>
        <span className={"pill-b " + badge[1]}>● {t(badge[0])}</span>
      </div>
      {x.status === "open" && (
        <>
          <div className="row between xs"><span className="mut">{t("Ishtirokchilar")}</span><span className="mono b">{x.players_count} / {x.max_players}</span></div>
          <div className="progress"><i style={{ width: pct + "%", background: "var(--g)" }} /></div>
        </>
      )}
      <div className="row between">
        <div><div className="y mono bb" style={{ fontSize: 18 }}>{money(x.prize_fund)} UZS</div><div className="mut xs">{t("sovrin")}</div></div>
        <button className={"btn small" + (x.status === "open" ? "" : " ghost")} onClick={onClick}>
          {x.joined ? "✓ " + t("Qatnashyapsiz") : x.status === "open" ? t("Qatnashish") : t("Batafsil")}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- MLBB kartasi
interface MlProfile { nick: string; lane: string; rank: string; heroes: number[]; ml_id: string; server: string; verified: boolean }

function MlCard() {
  const st = useLoad(() => api.get<MlProfile>("/arena/profile"));
  const [edit, setEdit] = useState(false);
  const p = st.data;
  const empty = !p || (!p.rank && !p.lane && !(p.heroes ?? []).length);
  return (
    <>
      <div className="card click mlcard" onClick={() => setEdit(true)} style={{ borderColor: "rgba(255,214,10,.35)" }}>
        {p?.rank ? <MlIcon kind="rank" k={p.rank} size={52} /> : <span className="rowico" style={{ width: 52, height: 52, borderRadius: 14, fontSize: 22 }}>🎮</span>}
        <div className="grow" style={{ minWidth: 0 }}>
          <div className="row" style={{ gap: 6 }}>
            <span className="b ell">{p?.nick || t("Mening MLBB kartam")}</span>
            {p?.lane && <MlIcon kind="lane" k={p.lane} size={20} />}
            {p?.verified && <span className="g xs b" title={t("Tasdiqlangan")}>✓</span>}
          </div>
          <div className="mut xs ell">{empty ? t("Rank, liniya va sevimli qahramonlaringizni qo'shing") : [p?.rank && rankLabel(p.rank), p?.lane && laneLabel(p.lane)].filter(Boolean).join(" · ")}</div>
        </div>
        <div className="heroes" style={{ display: "flex" }}>
          {(p?.heroes ?? []).map((id) => <HeroAva key={id} id={id} size={38} radius={19} />)}
        </div>
        <span className="mut"><Icon name="right" size={18} /></span>
      </div>
      {edit && p && <MlCardSheet p={p} onClose={() => setEdit(false)} onSaved={(x) => { st.setData(x); setEdit(false); }} onLinked={(x) => st.setData(x)} />}
    </>
  );
}

function LinkBox({ p, onLinked }: { p: MlProfile; onLinked: (p: MlProfile) => void }) {
  const [id, setId] = useState(p.ml_id);
  const [srv, setSrv] = useState(p.server);
  const { busy, run } = useAction();
  const { toast } = useApp();
  return (
    <div className="card col" style={{ borderColor: p.verified ? "rgba(29,233,182,.45)" : "rgba(255,214,10,.4)" }}>
      <div className="row between"><span className="b">🔗 {t("MLBB akkauntni ulash")}</span>{p.verified && <span className="pill-b g">✓ {t("Tasdiqlangan")}</span>}</div>
      <div className="mut xs">{t("O'yinda profil rasmingizga bosing: nik ostida ID va qavs ichida server, masalan 123456789 (2463).")}</div>
      <div className="row">
        <input className="input mono grow" inputMode="numeric" placeholder="Game ID" value={id} onChange={(e) => setId(e.target.value.replace(/\D/g, "").slice(0, 20))} />
        <input className="input mono" style={{ width: 100 }} inputMode="numeric" placeholder="Server" value={srv} onChange={(e) => setSrv(e.target.value.replace(/\D/g, "").slice(0, 10))} />
      </div>
      <button className="btn full" disabled={busy || id.length < 5 || !srv} onClick={() => run(async () => {
        const r = await api.post<MlProfile>("/arena/link", { ml_id: id, server: srv });
        onLinked(r);
        toast(r.verified ? t("Ulandi: {n}", { n: r.nick }) : t("Saqlandi (o'yinda tekshirib bo'lmadi)"), "ok");
      })}>🛡 {t("Tekshirish va ulash")}</button>
    </div>
  );
}

function MlCardSheet({ p, onClose, onSaved, onLinked }: { p: MlProfile; onClose: () => void; onSaved: (p: MlProfile) => void; onLinked: (p: MlProfile) => void }) {
  const [f, setF] = useState({ nick: p.nick, lane: p.lane, rank: p.rank, heroes: p.heroes ?? [] });
  const { busy, run } = useAction();
  const { toast } = useApp();
  return (
    <Sheet open onClose={onClose}>
      <div className="sec-title" style={{ marginTop: 0 }}>{t("Mening MLBB kartam")}</div>
      <div className="col">
        <LinkBox p={p} onLinked={(x) => { setF((y) => ({ ...y, nick: x.nick || y.nick })); onLinked(x); }} />
        <Field label={t("O'yindagi nik")}><input className="input" maxLength={32} value={f.nick} onChange={(e) => setF({ ...f, nick: e.target.value })} /></Field>
        <Field label={t("Rank")}><RankPicker value={f.rank} onChange={(v) => setF({ ...f, rank: v })} /></Field>
        <Field label={t("Asosiy liniya")}><LanePicker value={f.lane} onChange={(v) => setF({ ...f, lane: v })} /></Field>
        <Field label={t("Sevimli qahramonlar (3 tagacha)")}><HeroSlots value={f.heroes} onChange={(v) => setF({ ...f, heroes: v })} /></Field>
        <div className="mut xs">{t("Karta reytingda, jamoa e'lonlarida va turnirlarda ko'rinadi.")}</div>
        <button className="btn full" disabled={busy} onClick={() => run(async () => {
          onSaved(await api.put<MlProfile>("/arena/profile", f));
          toast(t("Saqlandi"), "ok");
        })}>{t("Saqlash")}</button>
      </div>
    </Sheet>
  );
}

// ---------------------------------------------------------------- O'yinlar: viktorina va haftaning qahramoni
interface QuizQ { n: number; type: "who" | "role"; options: string[]; image: string | null; answered: boolean; correct: boolean | null; answer?: string; hero?: number; name?: string }
interface QuizT { day: string; points_each: number; questions: QuizQ[]; score: number; done: boolean; roles: Record<string, string> }

function Games({ onPoints }: { onPoints: () => void }) {
  const nav = useNavigate();
  return (
    <>
      <button className="card row click" style={{ textAlign: "left", borderColor: "rgba(29,233,182,.4)" }} onClick={() => nav("/heroes")}>
        <span className="row" style={{ gap: 0 }}>{[109, 4, 9].map((id, i) => <span key={id} style={{ marginLeft: i ? -12 : 0 }}><HeroAva id={id} size={36} radius={18} /></span>)}</span>
        <div className="grow"><div className="b">📖 {t("Qahramonlar ensiklopediyasi")}</div><div className="mut xs">{t("Skillar, buyumlar, counter-pick — rasmiy ma'lumot")}</div></div>
        <Icon name="right" size={18} />
      </button>
      <Risers onOpen={(id) => nav(`/heroes/${id}`)} />
      <Quiz onPoints={onPoints} />
      <HeroVoteCard onPoints={onPoints} />
    </>
  );
}

function Quiz({ onPoints }: { onPoints: () => void }) {
  const st = useLoad(() => api.get<QuizT>("/arena/quiz"));
  const [res, setRes] = useState<Record<number, { correct: boolean; answer: string; pick: string }>>({});
  const { busy, run } = useAction();
  const { toast } = useApp();
  return (
    <Loadable state={st}>
      {(d) => {
        const cur = d.questions.find((q) => !q.answered && !res[q.n]);
        const shown = cur ?? null;
        const score = d.score + Object.values(res).filter((r) => r.correct).length;
        const dot = (q: QuizQ) => {
          const r = res[q.n];
          const ok = r ? r.correct : q.correct;
          return q.answered || r ? (ok ? "ok" : "no") : cur?.n === q.n ? "cur" : "";
        };
        return (
          <div className="card col" style={{ gap: 12 }}>
            <div className="row between">
              <span className="b">🧠 {t("Qahramonni top")}</span>
              <span className="pill-b g">+{d.points_each} {t("ball")} / {t("javob")}</span>
            </div>
            <div className="quiz-dots">{d.questions.map((q) => <i key={q.n} className={dot(q)} />)}</div>
            {shown ? (
              <>
                {shown.image && <img className="quiz-img" src={shown.image} alt="" />}
                <div className="center b">{shown.type === "who" ? t("Bu qaysi qahramon?") : t("{n} qaysi rolda?", { n: shown.name ?? "" })}</div>
                <div className="quiz-opts">
                  {shown.options.map((o) => (
                    <button key={o} disabled={busy} onClick={() => run(async () => {
                      const r = await api.post<{ correct: boolean; answer: string; points: number }>(`/arena/quiz/${shown.n}`, { answer: o });
                      setRes((x) => ({ ...x, [shown.n]: { correct: r.correct, answer: r.answer, pick: o } }));
                      toast(r.correct ? t("To'g'ri! +{n} ball", { n: r.points }) : t("Noto'g'ri. Javob: {a}", { a: shown.type === "role" ? roleLabel(r.answer) : r.answer }), r.correct ? "ok" : "err");
                      if (r.correct) onPoints();
                      if (d.questions.filter((q) => !q.answered).length <= Object.keys(res).length + 1) st.reload();
                    })}>
                      {shown.type === "role" && <MlIcon kind="role" k={o} size={22} />}
                      {shown.type === "role" ? roleLabel(o) : o}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <div className="col center" style={{ alignItems: "center", gap: 6 }}>
                <div className="hf bb" style={{ fontSize: 28 }}>{score}/{d.questions.length}</div>
                <div className="mut sm">{t("Bugungi viktorina tugadi. Ertaga yangi savollar!")}</div>
                <div className="row" style={{ gap: 6, flexWrap: "wrap", justifyContent: "center" }}>
                  {d.questions.map((q) => {
                    const hid = q.hero;
                    return hid ? <HeroAva key={q.n} id={hid} size={40} radius={10} ring={(res[q.n]?.correct ?? q.correct) === true} /> : null;
                  })}
                </div>
              </div>
            )}
          </div>
        );
      }}
    </Loadable>
  );
}

interface VoteT { week: string; total: number; my: number | null; points: number; top: { hero: number; votes: number; pct: number }[]; last_winner: number | null }

function HeroVoteCard({ onPoints }: { onPoints: () => void }) {
  const st = useLoad(() => api.get<VoteT>("/arena/hero-vote"));
  const [pick, setPick] = useState(false);
  const { run } = useAction();
  const { toast } = useApp();
  return (
    <Loadable state={st}>
      {(d) => (
        <div className="card col">
          <div className="row between">
            <span className="b">👑 {t("Haftaning eng kuchli qahramoni")}</span>
            {!d.my && <span className="pill-b g">+{d.points} {t("ball")}</span>}
          </div>
          <div className="mut xs">{t("Har hafta ovoz bering — jamoatchilik meta reytingi. Jami ovoz: {n}", { n: d.total })}</div>
          {d.last_winner && (
            <div className="row" style={{ gap: 8 }}>
              <HeroAva id={d.last_winner} size={32} radius={16} ring />
              <span className="sm">{t("O'tgan hafta g'olibi")}: <b className="y">{HERO_BY_ID[d.last_winner]?.name}</b></span>
            </div>
          )}
          {d.top.length === 0 ? <div className="mut sm">{t("Bu hafta hali ovoz yo'q — birinchi bo'ling!")}</div> : d.top.map((x, i) => (
            <div key={x.hero} className="vote-bar">
              <i style={{ width: x.pct + "%" }} />
              <span className="mono b" style={{ width: 18, textAlign: "center" }}>{i + 1}</span>
              <HeroAva id={x.hero} size={34} radius={10} ring={d.my === x.hero} />
              <span className="grow b ell">{HERO_BY_ID[x.hero]?.name}</span>
              <span className="mono sm">{x.pct}%</span>
            </div>
          ))}
          {d.my ? (
            <div className="row sm" style={{ gap: 8 }}><HeroAva id={d.my} size={28} radius={14} /><span>{t("Sizning ovozingiz")}: <b>{HERO_BY_ID[d.my]?.name}</b></span></div>
          ) : (
            <button className="btn full" onClick={() => setPick(true)}>{t("Ovoz berish")}</button>
          )}
          <HeroPicker open={pick} value={[]} max={1} onClose={() => setPick(false)} onChange={(v) => v[0] && run(async () => {
            const r = await api.post<VoteT & { earned: number }>("/arena/hero-vote", { hero_id: v[0] });
            st.setData(r);
            toast(t("Ovozingiz qabul qilindi! +{n} ball", { n: r.earned }), "ok");
            onPoints();
          })} />
        </div>
      )}
    </Loadable>
  );
}

// ---------------------------------------------------------------- Jamoa topish
interface Post { id: number; kind: "player" | "team"; name: string; lane: string; rank: string; online: string; note: string; mine: boolean; heroes: number[]; author_rank: string }

function Team() {
  const { toast } = useApp();
  const [lane, setLane] = useState("");
  const apiLane = LANES.find((l) => l.v === lane)?.label ?? "";
  const st = useLoad(() => api.get<Post[]>(`/arena/team-posts?lane=${apiLane}`), [apiLane]);
  const [open, setOpen] = useState(false);
  const { run } = useAction();
  return (
    <>
      <div className="card row" style={{ borderColor: "rgba(255,214,10,.4)" }}>
        <div className="grow"><div className="b">{t("Jamoa yoki o'yinchi qidiryapsizmi?")}</div><div className="mut xs">{t("Rolingiz, rankingiz va onlayn vaqtingizni yozing")}</div></div>
        <button className="btn small" onClick={() => setOpen(true)}>{t("E'lon berish")}</button>
      </div>
      <LanePicker value={lane} onChange={setLane} />
      <Loadable state={st}>
        {(list) => list.length === 0 ? <Empty icon="🤝" text={t("Hozircha e'lonlar yo'q")} /> : list.map((p) => {
          const rk = rankKey(p.rank) || p.author_rank;
          return (
            <div key={p.id} className="card col tight" style={{ gap: 8 }}>
              <div className="row">
                {rk ? <MlIcon kind="rank" k={rk} size={42} /> : <span className="avatar-l" style={{ background: "#ffd60a" }}>{p.name[0]?.toUpperCase()}</span>}
                <div className="grow" style={{ minWidth: 0 }}>
                  <div className="row" style={{ gap: 6 }}>
                    <span className="b ell">{p.name}</span>
                    {p.lane && <MlIcon kind="lane" k={laneKey(p.lane)} size={18} />}
                    <span className={"pill-b " + (p.kind === "team" ? "b" : "y")} style={{ fontSize: 10, padding: "1px 7px" }}>{p.kind === "team" ? t("jamoa") : t("o'yinchi")}</span>
                  </div>
                  <div className="mut xs ell">{[rk ? rankLabel(rk) : p.rank, p.lane && laneLabel(p.lane), p.online].filter(Boolean).join(" · ")}</div>
                </div>
                {p.mine ? (
                  <button className="btn small ghost" onClick={() => run(async () => { await api.post(`/arena/team-posts/${p.id}/close`); st.reload(); })}>{t("Yopish")}</button>
                ) : (
                  <button className="btn small ghost" onClick={() => run(async () => { await api.post(`/arena/team-posts/${p.id}/contact`); toast(t("Xabaringiz botda yuborildi"), "ok"); })}>{t("Yozish")}</button>
                )}
              </div>
              {(p.heroes.length > 0 || p.note) && (
                <div className="row" style={{ gap: 6 }}>
                  {p.heroes.map((id) => <HeroAva key={id} id={id} size={30} radius={8} />)}
                  {p.note && <span className="xs ell grow" style={{ color: "#d6dbe8" }}>{p.note}</span>}
                </div>
              )}
            </div>
          );
        })}
      </Loadable>
      {open && <PostSheet onClose={() => setOpen(false)} onDone={() => { setOpen(false); st.reload(); }} />}
    </>
  );
}

function PostSheet({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const prof = useLoad(() => api.get<MlProfile>("/arena/profile"));
  const [f, setF] = useState({ kind: "player", name: "", lane: "", rank: "", online: "", note: "", heroes: [] as number[] });
  const [filled, setFilled] = useState(false);
  if (prof.data && !filled) {
    setFilled(true);
    setF((x) => ({ ...x, name: prof.data!.nick || x.name, lane: prof.data!.lane, rank: prof.data!.rank, heroes: prof.data!.heroes ?? [] }));
  }
  const { busy, run } = useAction();
  return (
    <Sheet open onClose={onClose}>
      <div className="sec-title" style={{ marginTop: 0 }}>{t("Jamoa topish e'loni")}</div>
      <div className="col">
        <Seg value={f.kind} onChange={(v) => setF({ ...f, kind: v })} options={[{ v: "player", label: t("Men o'yinchiman") }, { v: "team", label: t("Bizga o'yinchi kerak") }]} />
        <Field label={f.kind === "team" ? t("Jamoa nomi") : t("Nik")}><input className="input" maxLength={64} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label={f.kind === "team" ? t("Qaysi liniya kerak") : t("Liniya")}><LanePicker value={f.lane} onChange={(v) => setF({ ...f, lane: v })} /></Field>
        <Field label={t("Rank")}><RankPicker value={f.rank} onChange={(v) => setF({ ...f, rank: v })} only={["epic", "legend", "mythic", "honor", "glory", "immortal"]} /></Field>
        <Field label={t("Qahramonlar (3 tagacha)")}><HeroSlots value={f.heroes} onChange={(v) => setF({ ...f, heroes: v })} /></Field>
        <Field label={t("Onlayn vaqt")}><input className="input" maxLength={32} placeholder="20:00–24:00" value={f.online} onChange={(e) => setF({ ...f, online: e.target.value })} /></Field>
        <Field label={t("Izoh")}><input className="input" maxLength={300} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
        <div className="mut xs">{t("E'lon 7 kun turadi. «Yozish» bosilganda bot sizga xabar yuboradi.")}</div>
        <button className="btn full" disabled={f.name.trim().length < 2 || busy} onClick={() => run(async () => {
          await api.post("/arena/team-posts", { ...f, lane: LANES.find((l) => l.v === f.lane)?.label ?? "", rank: f.rank ? rankLabel(f.rank) : "" });
          onDone();
        })}>{t("Joylash")}</button>
      </div>
    </Sheet>
  );
}

interface LbRow { place: number; user_id: number; name: string; points: number; hero?: number | null; rank?: string; lane?: string }

function Rating({ rules }: { rules?: Record<string, number> }) {
  const st = useLoad(() => api.get<{ season: { number: number; days_left: number }; items: LbRow[]; me: LbRow & { place: number | null }; week: number }>("/arena/leaderboard"));
  return (
    <Loadable state={st}>
      {(d) => (
        <>
          <div className="hero col" style={{ gap: 10 }}>
            <div className="row between"><span className="pill-y">{t("{n}-SEZON", { n: d.season.number })}</span><span className="mut xs">{t("{d} kun qoldi", { d: d.season.days_left })}</span></div>
            <div className="row" style={{ gap: 22 }}>
              <div><div className="y hf bb" style={{ fontSize: 26 }}>#{d.me.place ?? "—"}</div><div className="mut xs">{t("o'rningiz")}</div></div>
              <div><div className="hf bb" style={{ fontSize: 26 }}>{money(d.me.points)}</div><div className="mut xs">{t("ball")}</div></div>
              <div><div className="g hf bb" style={{ fontSize: 26 }}>+{money(d.week)}</div><div className="mut xs">{t("bu hafta")}</div></div>
            </div>
            <div className="mut xs">{t("Sezon mukofotlari: 1-o'rin — olmos paketi, Top 10 — «Sezon chempioni» nishoni, Top 100 — VIP e'lon 3 kun.")}</div>
          </div>
          <div className="card col">
            <div className="b">{t("Ball qanday yig'iladi")}</div>
            <div className="sm">🏆 {t("Turnirda g'alaba")} — <b className="y">+{rules?.pts_tournament_win ?? 100}</b></div>
            <div className="sm">⚔️ {t("Turnirda ishtirok")} — <b className="y">+{rules?.pts_tournament_join ?? 20}</b></div>
            <div className="sm">🎯 {t("To'g'ri prognoz")} — <b className="y">+{rules?.pts_prediction ?? 50}</b></div>
            <div className="sm">🧠 {t("Viktorinada to'g'ri javob")} — <b className="y">+{rules?.pts_quiz ?? 10}</b></div>
            <div className="sm">👑 {t("Haftaning qahramoniga ovoz")} — <b className="y">+{rules?.pts_vote ?? 5}</b></div>
            <div className="sm">✅ {t("Kunlik va haftalik vazifalar")} — <b className="y">+10…100</b></div>
          </div>
          <div className="sec-title">Top 100</div>
          {d.items.length === 0 ? <Empty icon="🏅" text={t("Bu sezonda hali ball yo'q")} /> : (
            <div className="card" style={{ padding: "4px 14px" }}>
              {d.items.map((r) => (
                <div key={r.user_id} className="listrow">
                  <span className="mono b" style={{ width: 28 }}>{["🥇", "🥈", "🥉"][r.place - 1] ?? r.place}</span>
                  {r.hero ? <HeroAva id={r.hero} size={34} radius={17} /> : <span className="avatar-l" style={{ width: 34, height: 34, background: "var(--card2)", color: "var(--mut)" }}>{r.name[0]?.toUpperCase()}</span>}
                  <span className="grow b ell">{r.name}</span>
                  {r.rank && <MlIcon kind="rank" k={r.rank} size={26} />}
                  <span className="y mono b">{money(r.points)}</span>
                </div>
              ))}
            </div>
          )}
          {d.me.place && <div className="mebar"><span className="y mono bb">#{d.me.place}</span><span className="grow b">{t("Siz")}</span><span className="y mono bb">{money(d.me.points)}</span></div>}
        </>
      )}
    </Loadable>
  );
}

interface Mission { key: string; title: string; goal: number; progress: number; claimed: boolean; reward: number }
interface Ex { key: string; title: string; cost: number }
const MICON: Record<string, string> = { login: "calendar", join_tournament: "arena", invite: "user", play_3: "trophy", partner_video: "play", any_service: "bag", quiz: "help", hero_vote: "star" };

function Missions({ onChange }: { onChange: () => void }) {
  const { toast } = useApp();
  const st = useLoad(() => api.get<{ daily: Mission[]; weekly: Mission[]; exchange: Ex[]; points: number }>("/arena/missions"));
  const { busy, run } = useAction();
  const row = (m: Mission) => (
    <div key={m.key} className="card row mission">
      <span className="rowico y"><Icon name={MICON[m.key] ?? "check"} /></span>
      <div className="grow">
        <div className="b sm">{t(m.title)}</div>
        <div className="mut xs">{m.progress}/{m.goal} · +{m.reward} {t("ball")}</div>
        <div className="progress"><i style={{ width: Math.round((m.progress / m.goal) * 100) + "%", background: "var(--g)" }} /></div>
      </div>
      {m.claimed ? <span className="g b sm">✓</span> : m.progress >= m.goal ? (
        <button className="btn small" disabled={busy} onClick={() => run(async () => {
          const r = await api.post<{ reward: number }>(`/arena/missions/${m.key}/claim`);
          toast(t("+{n} ball", { n: r.reward }), "ok");
          st.reload(); onChange();
        })}>{t("Olish")}</button>
      ) : <span className="mut mono sm">{m.progress}/{m.goal}</span>}
    </div>
  );
  return (
    <Loadable state={st}>
      {(d) => (
        <>
          <div className="sec-title">{t("Kunlik")}</div>
          {d.daily.map(row)}
          <div className="sec-title">{t("Haftalik")}</div>
          {d.weekly.map(row)}
          <div className="sec-title">{t("Ballni almashtirish")}</div>
          {d.exchange.map((x) => (
            <div key={x.key} className="card row">
              <div className="grow"><div className="b sm">{t(x.title)}</div><div className="mut xs">{money(x.cost)} {t("ball")}</div></div>
              <button className="btn small" disabled={busy || d.points < x.cost} onClick={() => run(async () => {
                await api.post(`/arena/exchange/${x.key}`);
                toast(t("Almashtirildi"), "ok");
                st.reload(); onChange();
              })}>{t("Almashtirish")}</button>
            </div>
          ))}
          <div className="mut xs">{t("Ball pulga almashtirilmaydi. Boost chegirmasi keyingi buyurtmada, VIP kunlari keyingi VIP xaridida, bepul kirish turnirga yozilishda ishlatiladi.")}</div>
        </>
      )}
    </Loadable>
  );
}

export function TournamentPage() {
  const id = useParams().id;
  const nav = useNavigate();
  const { me, refreshMe, toast } = useApp();
  const st = useLoad(() => api.get<Tournament>(`/tournaments/${id}`), [id]);
  const [nick, setNick] = useState("");
  const [gameId, setGameId] = useState(me?.ml_id ?? "");
  const [server, setServer] = useState("");
  const [tgUser, setTgUser] = useState(me?.username ? "@" + me.username : "");
  const [agree, setAgree] = useState(false);
  const [usePass, setUsePass] = useState(false);
  const [done, setDone] = useState(false);
  const { busy, run } = useAction();
  return (
    <>
      <Header title={done ? t("Ro'yxatdan o'tdingiz") : t("Ro'yxatdan o'tish")} sub={t("Turnirga qatnashish")} />
      <Loadable state={st}>
        {(x) => {
          const canJoin = x.status === "open" && !x.joined && x.players_count < x.max_players;
          const enough = (me?.balance ?? 0) >= x.entry_fee || (usePass && (me?.tournament_passes ?? 0) > 0);
          if (done) return (
            <>
              <div className="page center" style={{ alignItems: "center", paddingTop: 60 }}>
                <div className="okcircle"><Icon name="check" size={40} /></div>
                <div className="hf bb" style={{ fontSize: 26 }}>{t("Ro'yxatdan o'tdingiz")}</div>
                <div className="mut sm">{t("Siz turnirga qo'shildingiz. Boshlanishidan oldin Telegram orqali eslatma yuboramiz.")}</div>
                <div className="card" style={{ width: "100%", textAlign: "left" }}>
                  <div className="kv"><span>{t("Turnir")}</span><span className="b">{x.title}</span></div>
                  <div className="kv"><span>{t("Boshlanish")}</span><span>{dateTime(x.starts_at)}</span></div>
                  <div className="kv"><span>{t("Kirish to'lovi")}</span><span className="y mono">{x.entry_fee ? money(x.entry_fee) : t("Bepul")}</span></div>
                </div>
              </div>
              <BottomBar>
                <button className="btn full" onClick={() => nav("/arena")}>{t("Arenaga qaytish")}</button>
              </BottomBar>
            </>
          );
          return (
            <>
              <div className="page withbar">
                <div className="hero col" style={{ gap: 8 }}>
                  <div className="row between"><span className="badge g">● {t("KONKURS")}</span><span className="mut xs">{x.game === "ML" ? "Mobile Legends" : "Magic Chess"}</span></div>
                  <div className="hf bb" style={{ fontSize: 20 }}>{x.title}</div>
                  <div className="kv"><span>{t("Sovrin fondi")}</span><span className="y mono bb">{money(x.prize_fund)} UZS</span></div>
                  <div className="kv"><span>{t("Ishtirokchilar")}</span><span className="mono b">{x.players_count} / {x.max_players}</span></div>
                  <div className="kv"><span>{t("Boshlanish")}</span><span className="mono b">{dateTime(x.starts_at)}</span></div>
                </div>
                {x.rules && <div className="card"><div className="b" style={{ marginBottom: 6 }}>{t("Qoidalar")}</div><div className="pre sm mut">{x.rules}</div></div>}
                {x.joined && <div className="card tight g sm">✅ {t("Siz ro'yxatdan o'tgansiz. Boshlanishidan oldin Telegram orqali eslatma yuboramiz.")}</div>}
                {canJoin && (
                  <>
                    <div className="b">{t("Ishtirokchi ma'lumotlari")}</div>
                    <Field label={t("O'yindagi nik")}><input className="input" maxLength={64} placeholder={t("Nik")} value={nick} onChange={(e) => setNick(e.target.value)} /></Field>
                    <div className="row">
                      <div className="grow"><Field label={t("O'yin ID")}><input className="input mono" inputMode="numeric" maxLength={32} placeholder="123456789" value={gameId} onChange={(e) => setGameId(e.target.value.replace(/\D/g, ""))} /></Field></div>
                      <div style={{ width: 120 }}><Field label="Server"><input className="input mono" inputMode="numeric" maxLength={16} placeholder="1234" value={server} onChange={(e) => setServer(e.target.value)} /></Field></div>
                    </div>
                    <Field label={t("Telegram username")}><input className="input" maxLength={64} placeholder="@username" value={tgUser} onChange={(e) => setTgUser(e.target.value)} /></Field>
                    <div className="card row" style={{ borderColor: "rgba(255,214,10,.45)" }}>
                      <div className="grow"><div className="b">{t("Qatnashish narxi")}</div><div className="mut xs">{t("Hamyon balansidan yechiladi")}</div></div>
                      <div className="y mono bb" style={{ fontSize: 18 }}>{x.entry_fee ? som(x.entry_fee) : t("Bepul")}</div>
                    </div>
                    {x.entry_fee > 0 && (me?.tournament_passes ?? 0) > 0 && (
                      <label className="row sm" style={{ cursor: "pointer" }}>
                        <input type="checkbox" className="cbox" checked={usePass} onChange={(e) => setUsePass(e.target.checked)} />
                        <span>🎟 {t("Bepul kirishdan foydalanish (sizda {n} ta)", { n: me?.tournament_passes ?? 0 })}</span>
                      </label>
                    )}
                    {!enough && <div className="r sm">{t("Balans yetarli emas")}</div>}
                    <label className="row sm" style={{ cursor: "pointer" }}>
                      <input type="checkbox" className="cbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
                      <span>{t("Turnir qoidalari bilan tanishdim, roziman.")}</span>
                    </label>
                  </>
                )}
              </div>
              {canJoin && (
                <BottomBar>
                  {enough ? (
                    <button className="btn full" disabled={!nick.trim() || !gameId || !agree || busy} onClick={() => run(async () => {
                      st.setData(await api.post<Tournament>(`/tournaments/${x.id}/join`, { nick, game_id: gameId, server, tg_username: tgUser.trim(), use_pass: usePass }));
                      toast(t("Siz turnirga qo'shildingiz"), "ok");
                      refreshMe();
                      setDone(true);
                    })}>{t("Ro'yxatdan o'tish")}</button>
                  ) : (
                    <button className="btn full" onClick={() => nav("/wallet")}>+ {t("Balansni to'ldirish")}</button>
                  )}
                </BottomBar>
              )}
            </>
          );
        }}
      </Loadable>
    </>
  );
}

interface TopRow { place: number; user_id: number; name: string; total: number }

export function Top() {
  const [period, setPeriod] = useState<"week" | "month" | "all">("week");
  const st = useLoad(() => api.get<{ items: TopRow[]; me: TopRow | null }>(`/top?period=${period}`), [period]);
  return (
    <>
      <Header title="Top 100" sub={t("Botda eng ko'p xarid qilganlar")} />
      <div className="page">
        <Seg value={period} onChange={setPeriod} options={[{ v: "week", label: t("Haftalik") }, { v: "month", label: t("Oylik") }, { v: "all", label: t("Hammasi") }]} />
        <Loadable state={st}>
          {(d) => d.items.length === 0 ? <Empty icon="🏅" text={t("Hali reyting yo'q")} /> : (
            <>
              <div className="podium">
                {[1, 0, 2].map((i) => {
                  const r = d.items[i];
                  if (!r) return <div key={i} className="pcol" />;
                  return (
                    <div key={i} className={"pcol p" + r.place}>
                      <div className="pava"><Icon name="user" /></div>
                      <div className="b sm ell" style={{ maxWidth: "100%" }}>{r.name}</div>
                      <div className="y mono xs b">{money(r.total)}</div>
                      <div className="pbox hf">{r.place}</div>
                    </div>
                  );
                })}
              </div>
              {d.items.length > 3 && (
                <div className="card" style={{ padding: "4px 14px" }}>
                  {d.items.slice(3).map((r) => (
                    <div key={r.user_id} className="listrow">
                      <span className="mono mut" style={{ width: 26 }}>{r.place}</span>
                      <div className="iconbtn y" style={{ width: 34, height: 34, borderRadius: 17 }}><Icon name="user" size={16} /></div>
                      <span className="grow b ell">{r.name}</span>
                      <span className="y mono b">{money(r.total)}</span>
                    </div>
                  ))}
                </div>
              )}
              {d.me && (
                <div className="mebar">
                  <span className="y mono bb">#{d.me.place}</span>
                  <span className="grow b">{t("Siz")}</span>
                  <span className="y mono bb">{money(d.me.total)}</span>
                </div>
              )}
            </>
          )}
        </Loadable>
      </div>
    </>
  );
}

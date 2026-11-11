import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Tournament } from "../api";
import { t } from "../i18n";
import { BottomBar, BottomNav, Chips, dateTime, Empty, Field, GameLogo, Header, Icon, Loadable, money, Seg, Sheet, som, useAction, useApp, useLoad } from "../ui";

interface Summary {
  points: number; passes: number; vip_credit_days: number; boost_coupon_percent: number;
  prediction: { id: number; title: string; team_a: string; team_b: string; starts_at: string; my_pick: string | null; points: number } | null;
  points_rules: Record<string, number>;
}

export function Arena() {
  const [tab, setTab] = useState<"tours" | "team" | "rating" | "missions">(() => (sessionStorage.getItem("vx_arena_tab") as never) || "tours");
  const sum = useLoad(() => api.get<Summary>("/arena/summary"));
  const pick = (v: typeof tab) => { setTab(v); try { sessionStorage.setItem("vx_arena_tab", v); } catch { /* yo'q */ } };
  return (
    <>
      <Header title={t("Arena")} sub={t("Turnir, jamoa, reyting, vazifalar")} back={false} icon="arena"
        right={<span className="pts-pill">🏅 {money(sum.data?.points ?? 0)}</span>} />
      <div className="page">
        <div className="tabs4">
          {([["tours", "Turnirlar"], ["team", "Jamoa"], ["rating", "Reyting"], ["missions", "Vazifalar"]] as const).map(([v, l]) => (
            <button key={v} className={tab === v ? "on" : ""} onClick={() => pick(v)}>{t(l)}</button>
          ))}
        </div>
        {tab === "tours" && <Tours sum={sum.data} reload={sum.reload} />}
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
        <div><div className="y mono bb" style={{ fontSize: 17 }}>{money(x.prize_fund)} UZS</div><div className="mut xs">{t("sovrin")}</div></div>
        <button className={"btn small" + (x.status === "open" ? "" : " ghost")} onClick={onClick}>
          {x.joined ? "✓ " + t("Qatnashyapsiz") : x.status === "open" ? t("Qatnashish") : t("Batafsil")}
        </button>
      </div>
    </div>
  );
}

interface Post { id: number; kind: "player" | "team"; name: string; lane: string; rank: string; online: string; note: string; mine: boolean }
const LANES = ["Gold", "Mid", "EXP", "Jungle", "Roam"];
const AVA = ["#ffd60a", "#1de9b6", "#a78bfa", "#ff9f43", "#4da3ff"];

function Team() {
  const { toast } = useApp();
  const [lane, setLane] = useState("");
  const st = useLoad(() => api.get<Post[]>(`/arena/team-posts?lane=${lane}`), [lane]);
  const [open, setOpen] = useState(false);
  const { run } = useAction();
  return (
    <>
      <div className="card row" style={{ borderColor: "rgba(255,214,10,.4)" }}>
        <div className="grow"><div className="b">{t("Jamoa yoki o'yinchi qidiryapsizmi?")}</div><div className="mut xs">{t("Rolingiz, rankingiz va onlayn vaqtingizni yozing")}</div></div>
        <button className="btn small" onClick={() => setOpen(true)}>{t("E'lon berish")}</button>
      </div>
      <Chips value={lane} onChange={setLane} options={[{ v: "", label: t("Hammasi") }, ...LANES.map((l) => ({ v: l, label: l }))]} />
      <Loadable state={st}>
        {(list) => list.length === 0 ? <Empty icon="🤝" text={t("Hozircha e'lonlar yo'q")} /> : list.map((p, i) => (
          <div key={p.id} className="card row tight">
            <span className="avatar-l" style={{ background: AVA[i % AVA.length] }}>{p.name[0]?.toUpperCase()}</span>
            <div className="grow" style={{ minWidth: 0 }}>
              <div className="row" style={{ gap: 6 }}><span className="b ell">{p.name}</span>{p.lane && <span className="pill-b y" style={{ fontSize: 10, padding: "1px 7px" }}>{p.lane}</span>}</div>
              <div className="mut xs ell">{[p.rank, p.online, p.kind === "team" ? t("jamoa") : t("o'yinchi")].filter(Boolean).join(" · ")}</div>
              {p.note && <div className="xs ell" style={{ color: "#d6dbe8" }}>{p.note}</div>}
            </div>
            {p.mine ? (
              <button className="btn small ghost" onClick={() => run(async () => { await api.post(`/arena/team-posts/${p.id}/close`); st.reload(); })}>{t("Yopish")}</button>
            ) : (
              <button className="btn small ghost" onClick={() => run(async () => { await api.post(`/arena/team-posts/${p.id}/contact`); toast(t("Xabaringiz botda yuborildi"), "ok"); })}>{t("Yozish")}</button>
            )}
          </div>
        ))}
      </Loadable>
      <PostSheet open={open} onClose={() => setOpen(false)} onDone={() => { setOpen(false); st.reload(); }} />
    </>
  );
}

function PostSheet({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ kind: "player", name: "", lane: "", rank: "", online: "", note: "" });
  const { busy, run } = useAction();
  return (
    <Sheet open={open} onClose={onClose}>
      <div className="sec-title" style={{ marginTop: 0 }}>{t("Jamoa topish e'loni")}</div>
      <div className="col">
        <Seg value={f.kind} onChange={(v) => setF({ ...f, kind: v })} options={[{ v: "player", label: t("Men o'yinchiman") }, { v: "team", label: t("Bizga o'yinchi kerak") }]} />
        <Field label={f.kind === "team" ? t("Jamoa nomi") : t("Nik")}><input className="input" maxLength={64} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label={t("Liniya")}><Chips wrap value={f.lane} onChange={(v) => setF({ ...f, lane: f.lane === v ? "" : v })} options={LANES.map((l) => ({ v: l, label: l }))} /></Field>
        <div className="row">
          <div className="grow"><Field label={t("Rank")}><input className="input" maxLength={32} placeholder="Mythic 34★" value={f.rank} onChange={(e) => setF({ ...f, rank: e.target.value })} /></Field></div>
          <div className="grow"><Field label={t("Onlayn vaqt")}><input className="input" maxLength={32} placeholder="20:00–24:00" value={f.online} onChange={(e) => setF({ ...f, online: e.target.value })} /></Field></div>
        </div>
        <Field label={t("Izoh")}><input className="input" maxLength={300} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
        <div className="mut xs">{t("E'lon 7 kun turadi. «Yozish» bosilganda bot sizga xabar yuboradi.")}</div>
        <button className="btn full" disabled={f.name.trim().length < 2 || busy} onClick={() => run(async () => { await api.post("/arena/team-posts", f); onDone(); })}>{t("Joylash")}</button>
      </div>
    </Sheet>
  );
}

interface LbRow { place: number; user_id: number; name: string; points: number }

function Rating({ rules }: { rules?: Record<string, number> }) {
  const st = useLoad(() => api.get<{ season: { number: number; days_left: number }; items: LbRow[]; me: LbRow & { place: number | null }; week: number }>("/arena/leaderboard"));
  return (
    <Loadable state={st}>
      {(d) => (
        <>
          <div className="hero col" style={{ gap: 10 }}>
            <div className="row between"><span className="pill-y">{t("{n}-SEZON", { n: d.season.number })}</span><span className="mut xs">{t("{d} kun qoldi", { d: d.season.days_left })}</span></div>
            <div className="row" style={{ gap: 22 }}>
              <div><div className="y hf bb" style={{ fontSize: 24 }}>#{d.me.place ?? "—"}</div><div className="mut xs">{t("o'rningiz")}</div></div>
              <div><div className="hf bb" style={{ fontSize: 24 }}>{money(d.me.points)}</div><div className="mut xs">{t("ball")}</div></div>
              <div><div className="g hf bb" style={{ fontSize: 24 }}>+{money(d.week)}</div><div className="mut xs">{t("bu hafta")}</div></div>
            </div>
            <div className="mut xs">{t("Sezon mukofotlari: 1-o'rin — olmos paketi, Top 10 — «Sezon chempioni» nishoni, Top 100 — VIP e'lon 3 kun.")}</div>
          </div>
          <div className="card col">
            <div className="b">{t("Ball qanday yig'iladi")}</div>
            <div className="sm">🏆 {t("Turnirda g'alaba")} — <b className="y">+{rules?.pts_tournament_win ?? 100}</b></div>
            <div className="sm">⚔️ {t("Turnirda ishtirok")} — <b className="y">+{rules?.pts_tournament_join ?? 20}</b></div>
            <div className="sm">🎯 {t("To'g'ri prognoz")} — <b className="y">+{rules?.pts_prediction ?? 50}</b></div>
            <div className="sm">✅ {t("Kunlik va haftalik vazifalar")} — <b className="y">+10…100</b></div>
          </div>
          <div className="sec-title">Top 100</div>
          {d.items.length === 0 ? <Empty icon="🏅" text={t("Bu sezonda hali ball yo'q")} /> : (
            <div className="card" style={{ padding: "4px 14px" }}>
              {d.items.map((r) => (
                <div key={r.user_id} className="listrow">
                  <span className="mono b" style={{ width: 28 }}>{["🥇", "🥈", "🥉"][r.place - 1] ?? r.place}</span>
                  <span className="grow b ell">{r.name}</span>
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
const MICON: Record<string, string> = { login: "calendar", join_tournament: "arena", invite: "user", play_3: "trophy", partner_video: "play", any_service: "bag" };

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
                <div className="hf bb" style={{ fontSize: 24 }}>{t("Ro'yxatdan o'tdingiz")}</div>
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

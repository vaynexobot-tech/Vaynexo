import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Tournament } from "../api";
import { t } from "../i18n";
import { BottomBar, BottomNav, dateTime, Empty, Field, GameLogo, Header, Loadable, money, Seg, som, Status, useAction, useApp, useLoad } from "../ui";

export function Arena() {
  const nav = useNavigate();
  const [status, setStatus] = useState<"open" | "running">("open");
  const st = useLoad(() => api.get<Tournament[]>(`/tournaments?status=${status}`), [status]);
  return (
    <>
      <Header title={t("Arena")} sub={t("Turnirlar va konkurslar")} back={false} />
      <div className="page">
        <Seg value={status} onChange={setStatus} options={[{ v: "open", label: t("Faol") }, { v: "running", label: t("Davom etmoqda") }]} />
        <Loadable state={st}>
          {(list) => list.length === 0 ? <Empty icon="🏆" text={t("Hozircha turnirlar yo'q")} /> : list.map((x) => <TourCard key={x.id} x={x} onClick={() => nav(`/arena/${x.id}`)} />)}
        </Loadable>
        <div className="card click row between" onClick={() => nav("/top")}>
          <div><div className="b">🏅 Top 100</div><div className="mut xs">{t("Botda eng ko'p xarid qilganlar reytingi")}</div></div>
          <span className="y">›</span>
        </div>
      </div>
      <BottomNav />
    </>
  );
}

function TourCard({ x, onClick }: { x: Tournament; onClick: () => void }) {
  const pct = Math.round((x.players_count / x.max_players) * 100);
  return (
    <div className="hero click" style={{ cursor: "pointer" }} onClick={onClick}>
      <div className="row between"><span className="badge g">{x.game === "ML" ? "Mobile Legends" : "Magic Chess"}</span>{x.joined ? <span className="badge y">✓ {t("Qatnashyapsiz")}</span> : <Status s={x.status} />}</div>
      <div className="hf bb" style={{ fontSize: 19, margin: "10px 0 2px" }}>{x.title}</div>
      <div className="y mono bb">{money(x.prize_fund)} UZS <span className="mut xs">{t("sovrin fondi")}</span></div>
      <div style={{ height: 6, borderRadius: 3, background: "rgba(255,255,255,.08)", margin: "10px 0 6px" }}><div style={{ width: pct + "%", height: "100%", borderRadius: 3, background: "var(--g)" }} /></div>
      <div className="row between mut xs"><span>{t("Ishtirokchilar")} {x.players_count} / {x.max_players}</span><span>{t("Boshlanish")}: {dateTime(x.starts_at)}</span></div>
    </div>
  );
}

export function TournamentPage() {
  const id = useParams().id;
  const { me, refreshMe, toast } = useApp();
  const st = useLoad(() => api.get<Tournament>(`/tournaments/${id}`), [id]);
  const [nick, setNick] = useState("");
  const [gameId, setGameId] = useState(me?.ml_id ?? "");
  const [server, setServer] = useState("");
  const { busy, run } = useAction();
  return (
    <>
      <Header title={t("Turnir")} />
      <Loadable state={st}>
        {(x) => {
          const canJoin = x.status === "open" && !x.joined && x.players_count < x.max_players;
          const enough = (me?.balance ?? 0) >= x.entry_fee;
          return (
            <>
              <div className="page">
                <TourCard x={x} onClick={() => undefined} />
                <div className="card">
                  <div className="kv"><span>{t("Kirish to'lovi")}</span><span>{x.entry_fee ? som(x.entry_fee) : t("Bepul")}</span></div>
                  <div className="kv"><span>{t("Boshlanish")}</span><span>{dateTime(x.starts_at)}</span></div>
                </div>
                {x.rules && <div className="card"><div className="b" style={{ marginBottom: 6 }}>{t("Qoidalar")}</div><div className="pre sm mut">{x.rules}</div></div>}
                {x.joined && <div className="card tight g sm">✅ {t("Siz ro'yxatdan o'tgansiz. Boshlanishidan oldin Telegram orqali eslatma yuboramiz.")}</div>}
                {canJoin && (
                  <div className="card col">
                    <div className="b">{t("Ishtirokchi ma'lumotlari")}</div>
                    <Field label={t("O'yindagi nik")}><input className="input" maxLength={64} value={nick} onChange={(e) => setNick(e.target.value)} /></Field>
                    <div className="row">
                      <div className="grow"><Field label={t("O'yin ID")}><input className="input mono" inputMode="numeric" maxLength={32} value={gameId} onChange={(e) => setGameId(e.target.value.replace(/\D/g, ""))} /></Field></div>
                      <div style={{ width: 110 }}><Field label="Server"><input className="input mono" inputMode="numeric" maxLength={16} value={server} onChange={(e) => setServer(e.target.value)} /></Field></div>
                    </div>
                  </div>
                )}
              </div>
              {canJoin && (
                <BottomBar>
                  <div className="grow"><div className="mut xs">{t("Qatnashish narxi")}</div><div className="y bb mono">{x.entry_fee ? som(x.entry_fee) : t("Bepul")}</div></div>
                  <button className="btn" disabled={!nick.trim() || !gameId || busy || !enough} onClick={() => run(async () => {
                    st.setData(await api.post<Tournament>(`/tournaments/${x.id}/join`, { nick, game_id: gameId, server, tg_username: me?.username ? "@" + me.username : "" }));
                    toast(t("Siz turnirga qo'shildingiz"), "ok");
                    refreshMe();
                  })}>{enough ? t("Qatnashish") : t("Balans yetarli emas")}</button>
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
  const medal = ["🥇", "🥈", "🥉"];
  return (
    <>
      <Header title="Top 100" sub={t("Almaz, xizmatlar va akkauntlarga sarflangan summa bo'yicha")} />
      <div className="page">
        <Seg value={period} onChange={setPeriod} options={[{ v: "week", label: t("Haftalik") }, { v: "month", label: t("Oylik") }, { v: "all", label: t("Hammasi") }]} />
        <Loadable state={st}>
          {(d) => d.items.length === 0 ? <Empty icon="🏅" text={t("Hali reyting yo'q")} /> : (
            <>
              {d.me && <div className="card tight row between" style={{ borderColor: "rgba(255,214,10,.4)" }}><span className="b">#{d.me.place} · {t("Siz")}</span><span className="y mono b">{money(d.me.total)}</span></div>}
              <div className="card">
                {d.items.map((r) => (
                  <div key={r.user_id} className="listrow">
                    <span className="mono b" style={{ width: 34, fontSize: r.place <= 3 ? 20 : 13 }}>{medal[r.place - 1] ?? "#" + r.place}</span>
                    <GameLogo game="UZS" size={32} />
                    <span className="grow b ell">{r.name}</span>
                    <span className="y mono b">{money(r.total)}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </Loadable>
      </div>
    </>
  );
}

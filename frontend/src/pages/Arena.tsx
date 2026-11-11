import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Tournament } from "../api";
import { t } from "../i18n";
import { BottomBar, BottomNav, dateTime, Empty, Field, GameLogo, Header, Icon, Loadable, money, Seg, som, useAction, useApp, useLoad } from "../ui";

export function Arena() {
  const nav = useNavigate();
  const [status, setStatus] = useState<"open" | "running">("open");
  const st = useLoad(() => api.get<Tournament[]>(`/tournaments?status=${status}`), [status]);
  const myPlace = useLoad(() => api.get<{ items: TopRow[]; me: TopRow | null }>("/top?period=all"));
  return (
    <>
      <Header title={t("Arena")} sub={t("Turnirlar va konkurslar")} back={false} icon="arena" />
      <div className="page">
        <Seg value={status} onChange={setStatus} options={[{ v: "open", label: t("Faol") }, { v: "running", label: t("Davom etmoqda") }]} />
        <Loadable state={st}>
          {(list) => list.length === 0 ? <Empty icon="🏆" text={t("Hozircha turnirlar yo'q")} /> : (
            <>
              <FeaturedTour x={list[0]} onClick={() => nav(`/arena/${list[0].id}`)} />
              {list.slice(1).map((x) => (
                <div key={x.id} className="card click row" onClick={() => nav(`/arena/${x.id}`)}>
                  <GameLogo game={x.game} size={46} />
                  <div className="grow" style={{ minWidth: 0 }}>
                    <div className="b ell">{x.title}</div>
                    <div className="mut xs">{x.game === "ML" ? "Mobile Legends" : "Magic Chess"} · {dateTime(x.starts_at)}</div>
                  </div>
                  <div style={{ textAlign: "right" }}><div className="y mono bb">{money(x.prize_fund)}</div><div className="mut xs">UZS</div></div>
                  <span className="mut"><Icon name="right" size={16} /></span>
                </div>
              ))}
            </>
          )}
        </Loadable>
        <div className="card click row between" onClick={() => nav("/top")}>
          <div className="row">
            <div className="iconbtn y" style={{ width: 44, height: 44, background: "rgba(255,214,10,.08)" }}><Icon name="trophy" /></div>
            <div><div className="b">{t("Mening o'rnim")}</div><div className="mut xs">{t("Top 100 reytingida")}</div></div>
          </div>
          <div className="row"><div style={{ textAlign: "right" }}><div className="y mono bb">#{myPlace.data?.me?.place ?? "—"}</div><div className="mut xs">{t("o'rin")}</div></div><span className="mut"><Icon name="right" size={16} /></span></div>
        </div>
      </div>
      <BottomNav />
    </>
  );
}

function FeaturedTour({ x, onClick }: { x: Tournament; onClick: () => void }) {
  const pct = Math.round((x.players_count / x.max_players) * 100);
  return (
    <div className="hero col" style={{ gap: 8 }}>
      <div className="row between"><span className="badge g">● {t("KONKURS")}</span><span className="mut xs">{x.game === "ML" ? "Mobile Legends" : "Magic Chess"}</span></div>
      <div className="hf bb" style={{ fontSize: 22 }}>{x.title}</div>
      <div className="y mono bb" style={{ fontSize: 20 }}>{money(x.prize_fund)} UZS <span className="mut xs">{t("sovrin fondi")}</span></div>
      <div className="row between xs"><span className="mut">{t("Ishtirokchilar")}</span><span className="mono b">{x.players_count} / {x.max_players}</span></div>
      <div className="progress"><i style={{ width: pct + "%", background: "var(--g)" }} /></div>
      <div className="divider" />
      <div className="row between">
        <span className="mut xs">{t("Boshlanish")}: {dateTime(x.starts_at)}</span>
        <button className="btn small" onClick={onClick}>{x.joined ? "✓ " + t("Qatnashyapsiz") : t("Qatnashish")}</button>
      </div>
    </div>
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
  const [done, setDone] = useState(false);
  const { busy, run } = useAction();
  return (
    <>
      <Header title={done ? t("Ro'yxatdan o'tdingiz") : t("Ro'yxatdan o'tish")} sub={t("Turnirga qatnashish")} />
      <Loadable state={st}>
        {(x) => {
          const canJoin = x.status === "open" && !x.joined && x.players_count < x.max_players;
          const enough = (me?.balance ?? 0) >= x.entry_fee;
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
                      st.setData(await api.post<Tournament>(`/tournaments/${x.id}/join`, { nick, game_id: gameId, server, tg_username: tgUser.trim() }));
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

// Yangi admin panel: Bosh (bugungi holat + bajariladigan ishlar), Buyurtmalar (yagona ro'yxat), Katalog (o'yinlar, API'lar, narx),
// O'yin sahifasi (paketlar, foyda, API taqqoslash/almashtirish) va Ko'proq menyusi. Eski bo'limlar `go(...)` orqali ochiladi.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api";
import { confirmDialog, copyText } from "../tg";
import { dateTime, Empty, Field, GameTile, Icon, Loadable, money, MoneyInput, Seg, Sheet, Toggle, useAction, useApp, useLoad } from "../ui";

type Act = [string, string, string];
export interface QItem { kind: string; id: number; title: string; sub: string; amount: number; at: string | null; actions: Act[]; copy?: string; error?: string | null; game?: string | null }
export interface Dash {
  today: { sales: number; yesterday: number; profit: number; orders: number; new_users: number; users: number };
  providers: { id: number; name: string; kind: string; is_active: boolean; balance_usd: string | null; low: boolean; error: string | null }[];
  bot: { open: boolean; guests: number; inline: boolean | null };
  queue: QItem[];
  links: { section: string; label: string; count: number }[];
  top_games: { game: string; name: string; share: number }[];
}
type Go = (to: string) => void;

const KIND_ICON: Record<string, [string, string]> = { topup: ["in", "g"], withdraw: ["out", "y"], tg: ["send", "b"], donate: ["gem", "v"] };
const ago = (iso: string | null) => (iso ? dateTime(iso) : "");

function Ibox({ name, c }: { name: string; c: string }) {
  return <span className={"adm2-ibox " + c}><Icon name={name} size={19} /></span>;
}

function ActionBtns({ item, onDone }: { item: { kind: string; id: number; actions: Act[]; copy?: string }; onDone: () => void }) {
  const { toast } = useApp();
  const { busy, run } = useAction();
  const act = (a: Act) => run(async () => {
    if (["refund", "reject"].includes(a[0]) && !(await confirmDialog(`«${a[1]}» — ishonchingiz komilmi?`))) return;
    let note = "";
    if (a[0] === "reject" && item.kind === "withdraw") note = window.prompt("Rad etish sababi (foydalanuvchiga ko'rinadi):") ?? "";
    await api.post(`/admin/queue/${item.kind}/${item.id}`, { action: a[0], note });
    toast("Bajarildi", "ok");
    onDone();
  });
  return (
    <div className="row adm2-acts">
      {item.actions.map((a) => (
        <button key={a[0]} className={"btn small grow adm2-" + a[2]} disabled={busy} onClick={() => act(a)}>
          {a[0] === "retry" && <Icon name="refresh" size={15} />}{a[0] === "confirm" || a[0] === "paid" || a[0] === "done" ? <Icon name="check" size={15} /> : null}{a[1]}
        </button>
      ))}
      {item.copy && <button className="btn small ghost" onClick={() => { copyText(item.copy!); toast("Karta nusxalandi", "ok"); }}>Karta nusxa</button>}
    </div>
  );
}

// ---------------------------------------------------------------- BOSH
export function Dashboard({ st, go }: { st: { data: Dash | null; error: string | null; loading: boolean; reload: () => void }; go: Go }) {
  const { busy, run } = useAction();
  return (
    <Loadable state={st}>
      {(d) => {
        const t = d.today;
        const pct = t.yesterday ? Math.round(((t.sales - t.yesterday) / t.yesterday) * 100) : null;
        return (
          <>
            <div className="card adm2-kpi">
              <div className="row between"><span className="mut sm b">Bugungi savdo</span>
                {pct !== null && <span className={"badge " + (pct >= 0 ? "g" : "r")}>{pct >= 0 ? "+" : ""}{pct}% kechagidan</span>}</div>
              <div className="adm2-big mono">{money(t.sales)} <span className="mut sm b">so'm</span></div>
              <div className="row" style={{ gap: 0, marginTop: 10 }}>
                <div className="grow"><div className="mut xs">Donat foydasi</div><div className="bb mono g" style={{ fontSize: 16 }}>+{money(t.profit)}</div></div>
                <div className="grow"><div className="mut xs">Buyurtmalar</div><div className="bb mono" style={{ fontSize: 16 }}>{t.orders}</div></div>
                <div className="grow"><div className="mut xs">Yangi odamlar</div><div className="bb mono" style={{ fontSize: 16 }}>+{t.new_users}</div></div>
              </div>
            </div>

            {d.providers.length > 0 && (
              <div className="adm2-provs">
                {d.providers.map((p) => (
                  <button key={p.id} className={"card adm2-prov" + (p.low || p.error ? " bad" : "")} onClick={() => go("apis")}>
                    <div className="row" style={{ gap: 7 }}><span className={"adm2-dot " + (!p.is_active ? "m" : p.low || p.error ? "r" : "g")} /><span className="sm b ell">{p.name}</span></div>
                    <div className={"bb mono" + (p.low ? " r" : "")} style={{ fontSize: 18, marginTop: 5 }}>{p.balance_usd != null ? `$${Number(p.balance_usd).toFixed(2)}` : "—"}</div>
                    <div className={"xs " + (p.low || p.error ? "r" : "mut")}>{!p.is_active ? "o'chiq" : p.error ? "xato bor" : p.low ? "kam qoldi — to'ldiring" : "yetarli"}</div>
                  </button>
                ))}
              </div>
            )}

            {d.bot.inline === false && (
              <div className="card row adm2-warn"><Icon name="alert" size={18} /><div className="grow sm">Inline qidiruv o'chiq. <b>@BotFather</b> → /setinline → botni tanlang → «Paket qidirish…» deb yozing.</div></div>
            )}

            <div className="row between"><div className="sec-title">Hozir bajarish kerak</div><span className={"badge " + (d.queue.length ? "y" : "g")}>{d.queue.length ? `${d.queue.length} ta` : "Hammasi bajarilgan ✓"}</span></div>
            {d.queue.map((q) => {
              const [ic, c] = KIND_ICON[q.kind] ?? ["list", "m"];
              return (
                <div key={q.kind + q.id} className="card col" style={{ gap: 10 }}>
                  <div className="row">
                    {q.game ? <GameTile name={q.game} slug={q.game} size={38} radius={12} /> : <Ibox name={ic} c={c} />}
                    <div className="grow" style={{ minWidth: 0 }}><div className="b ell">{q.title}</div><div className="mut xs ell">{q.sub} · {ago(q.at)}</div></div>
                  </div>
                  {q.error && <div className="xs r">⚠ {q.error}</div>}
                  <ActionBtns item={q} onDone={st.reload} />
                </div>
              );
            })}
            {d.links.length > 0 && (
              <div className="adm2-list">
                {d.links.map((l) => (
                  <button key={l.label} className="adm2-it" onClick={() => go(l.section)}>
                    <span className="grow b">{l.label}</span><span className="badge y">{l.count}</span><Icon name="right" size={17} className="mut" />
                  </button>
                ))}
              </div>
            )}

            <div className="sec-title">Tezkor amallar</div>
            <div className="adm2-quick">
              <button className="card" onClick={() => go("broadcast")}><Ibox name="mega" c="y" /><span>Xabar</span></button>
              <button className="card" onClick={() => go("promo")}><Ibox name="ticket" c="g" /><span>Promo</span></button>
              <button className="card" onClick={() => go("bot")}><Ibox name="userplus" c="b" /><span>Ruxsat</span></button>
              <button className="card" disabled={busy} onClick={() => run(async () => {
                if (!(await confirmDialog(d.bot.open ? "Botni yopasizmi? Faqat adminlar va mehmonlar kira oladi." : "Botni hamma uchun ochasizmi?"))) return;
                await api.post("/admin/bot/open", { open: !d.bot.open }); st.reload();
              })}><Ibox name="lock" c={d.bot.open ? "g" : "r"} /><span>{d.bot.open ? "Yopish" : "Ochish"}</span></button>
            </div>

            {d.top_games.length > 0 && (
              <div className="card col" style={{ gap: 10 }}>
                <div className="b">Eng ko'p sotilgan (7 kun)</div>
                {d.top_games.map((g) => (
                  <div key={g.game} className="row">
                    <GameTile name={g.name} slug={g.game} size={28} radius={8} />
                    <span className="grow sm b ell">{g.name}</span>
                    <span className="adm2-bar"><i style={{ width: `${g.share}%` }} /></span>
                    <span className="mut xs mono" style={{ width: 34, textAlign: "right" }}>{g.share}%</span>
                  </div>
                ))}
              </div>
            )}
          </>
        );
      }}
    </Loadable>
  );
}

// ---------------------------------------------------------------- BUYURTMALAR
interface OItem { kind: string; id: number; ref: string; title: string; game: string | null; price: number; sub: string; status: string; label: string; color: string; error: string | null; provider: string | null; at: string | null; actions: Act[] }
interface ORes { items: OItem[]; counts: { attention: number; processing: number } }
type OState = "attention" | "processing" | "done" | "refunded";

export function OrdersTab({ go }: { go: Go }) {
  const [kind, setKind] = useState("all");
  const [state, setState] = useState<OState>("attention");
  const [q, setQ] = useState("");
  const [qq, setQq] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { const id = setTimeout(() => setQq(q.trim()), 350); return () => clearTimeout(id); }, [q]);
  const st = useLoad(() => api.get<ORes>(`/admin/orders?kind=${kind}&state=${state}&q=${encodeURIComponent(qq)}`), [kind, state, qq]);
  const legacy: [string, string][] = [["incoming", "Kirim"], ["withdraw", "Yechish"], ["boost", "Boost"], ["rent", "Ijara"], ["disputes", "Nizo"]];
  const c = st.data?.counts;
  return (
    <>
      <div className="adm2-search"><Icon name="search" size={17} /><input placeholder="ID, @username yoki VX-D123" value={q} onChange={(e) => setQ(e.target.value)} /></div>
      <div className="chips-scroll">
        {[["all", "Hammasi"], ["donate", "Donat"], ["tg", "Telegram"]].map(([v, l]) => (
          <button key={v} className={"chip" + (kind === v ? " on" : "")} onClick={() => setKind(v)}>{l}</button>
        ))}
        {legacy.map(([v, l]) => <button key={v} className="chip" onClick={() => go(v)}>{l} ›</button>)}
      </div>
      {!qq && <Seg value={state} onChange={setState} options={[
        { v: "attention", label: `Diqqat${c ? ` ${c.attention}` : ""}` }, { v: "processing", label: `Jarayonda${c ? ` ${c.processing}` : ""}` },
        { v: "done", label: "Bajarildi" }, { v: "refunded", label: "Qaytarildi" }]} />}
      <Loadable state={st}>
        {(r) => r.items.length === 0 ? <Empty icon="✅" text={state === "attention" && !qq ? "Diqqat talab qiladigan buyurtma yo'q" : "Buyurtma topilmadi"} /> : (
          <div className="adm2-list">
            {r.items.map((o) => {
              const key = o.kind + o.id;
              return (
                <div key={key} className="adm2-it col" style={{ alignItems: "stretch", gap: 8 }} onClick={() => setOpen(open === key ? null : key)}>
                  <div className="row">
                    {o.game ? <GameTile name={o.game} slug={o.game} size={40} radius={11} /> : <Ibox name="send" c="b" />}
                    <div className="grow" style={{ minWidth: 0 }}>
                      <div className="row between"><span className="b ell">{o.title}</span><span className="b mono">{money(o.price)}</span></div>
                      <div className="row between" style={{ marginTop: 2 }}><span className="mut xs ell">{o.ref} · {o.sub} · {ago(o.at)}</span><span className={"badge " + o.color}>{o.label}</span></div>
                    </div>
                  </div>
                  {open === key && (
                    <div className="col" style={{ gap: 8 }} onClick={(e) => e.stopPropagation()}>
                      {o.provider && <div className="mut xs">API: {o.provider}</div>}
                      {o.error && <div className="xs r">⚠ {o.error}</div>}
                      {o.actions.length > 0 ? <ActionBtns item={o} onDone={st.reload} /> : <div className="mut xs">Amal yo'q — buyurtma yakunlangan</div>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Loadable>
    </>
  );
}

// ---------------------------------------------------------------- KATALOG
interface Cheaper { provider_id: number; provider: string; pct: number | null; linked: boolean; slug: string; name?: string; pairs?: number; ref?: { name: string; cur: string; alt: string } | null; current?: boolean }
interface CGame { slug: string; name: string; logo: string | null; is_active: boolean; sort: number; featured_slot: number | null; popular: boolean; provider_id: number | null; provider: string | null; packages: number; warning: string | null; cheaper: Cheaper | null; providers: number }
interface CRes { items: CGame[]; counts: { active: number; hidden: number; cheaper: number }; rate: number; markup: number }

export function CatalogTab({ apis, go }: { apis: ReactNode; go: Go }) {
  const [view, setView] = useState<"games" | "apis" | "price">("games");
  const [game, setGame] = useState<string | null>(null);
  if (game) return <GameDetail slug={game} onBack={() => setGame(null)} go={go} />;
  return (
    <>
      <Seg value={view} onChange={setView} options={[{ v: "games", label: "O'yinlar" }, { v: "apis", label: "API'lar" }, { v: "price", label: "Narx qoidasi" }]} />
      {view === "games" && <GamesList open={setGame} onPrice={() => setView("price")} />}
      {view === "apis" && apis}
      {view === "price" && <PriceRule />}
    </>
  );
}

function GamesList({ open, onPrice }: { open: (s: string) => void; onPrice: () => void }) {
  const [state, setState] = useState<"active" | "hidden" | "cheaper">("active");
  const [q, setQ] = useState("");
  const [qq, setQq] = useState("");
  useEffect(() => { const id = setTimeout(() => setQq(q.trim()), 350); return () => clearTimeout(id); }, [q]);
  const st = useLoad(() => api.get<CRes>(`/admin/catalog/games?state=${state}&q=${encodeURIComponent(qq)}`), [state, qq]);
  const { busy, run } = useAction();
  const toggle = (g: CGame, v: boolean) => run(async () => { await api.put(`/admin/donate/games/${encodeURIComponent(g.slug)}`, { is_active: v }); st.reload(); });
  const move = (list: CGame[], i: number, d: number) => run(async () => {
    const arr = [...list];
    const [x] = arr.splice(i, 1);
    arr.splice(i + d, 0, x);
    await api.put("/admin/catalog/order", { slugs: arr.map((g) => g.slug) });
    st.reload();
  });
  return (
    <Loadable state={st}>
      {(r) => (
        <>
          <button className="card row adm2-rule" onClick={onPrice}>
            <Ibox name="wallet" c="y" />
            <div className="grow" style={{ textAlign: "left" }}><div className="sm b">1$ = {money(r.rate)} so'm · ustama {r.markup}%</div><div className="mut xs">Narxlar API tannarxidan avtomatik hisoblanadi</div></div>
            <span className="y sm b">O'zgartirish</span>
          </button>
          <div className="adm2-search"><Icon name="search" size={17} /><input placeholder="O'yin qidirish…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <div className="chips-scroll">
            <button className={"chip" + (state === "active" ? " on" : "")} onClick={() => setState("active")}>Bosh sahifada {r.counts.active}</button>
            <button className={"chip" + (state === "hidden" ? " on" : "")} onClick={() => setState("hidden")}>Yashirin {money(r.counts.hidden)}</button>
            <button className={"chip" + (state === "cheaper" ? " on" : "")} onClick={() => setState("cheaper")}>Arzonroq topildi {r.counts.cheaper}</button>
          </div>
          {r.items.length === 0 ? <Empty icon="🎮" text="O'yin topilmadi" /> : (
            <div className="adm2-list">
              {r.items.map((g, i) => (
                <div key={g.slug} className="adm2-it">
                  {state === "active" && !qq && (
                    <div className="col" style={{ gap: 0 }}>
                      <button className="adm2-arrow" disabled={busy || i === 0} onClick={() => move(r.items, i, -1)} aria-label="Yuqoriga"><Icon name="up" size={16} /></button>
                      <button className="adm2-arrow" disabled={busy || i === r.items.length - 1} onClick={() => move(r.items, i, 1)} aria-label="Pastga"><Icon name="down" size={16} /></button>
                    </div>
                  )}
                  <button className="row grow adm2-plain" onClick={() => open(g.slug)}>
                    <GameTile name={g.name} logo={g.logo} slug={g.slug} size={44} radius={12} />
                    <div className="grow" style={{ minWidth: 0, textAlign: "left" }}>
                      <div className="b ell">{g.name}</div>
                      <div className="mut xs ell">{g.packages} paket · {g.provider ?? "qo'lda"}{g.providers > 1 ? ` · ${g.providers} API` : ""}{g.featured_slot ? ` · asosiy #${g.featured_slot}` : ""}</div>
                      {g.cheaper && <span className="badge g adm2-tag"><Icon name="bolt" size={11} /> {g.cheaper.provider}'da ~{Math.abs(g.cheaper.pct ?? 0)}% arzon</span>}
                      {g.warning && <span className="badge y adm2-tag"><Icon name="alert" size={11} /> {g.warning}</span>}
                    </div>
                  </button>
                  <Toggle on={g.is_active} onChange={(v) => toggle(g, v)} />
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </Loadable>
  );
}

function PriceRule() {
  const { toast } = useApp();
  const st = useLoad(() => api.get<{ usd_rate: number; markup: number }>("/admin/donate/providers"));
  const [rate, setRate] = useState<number | "">("");
  const [markup, setMarkup] = useState<number | "">("");
  const { busy, run } = useAction();
  return (
    <Loadable state={st}>
      {(d) => (
        <div className="card col">
          <div className="b">💱 Narx qoidasi</div>
          <div className="mut xs">So'm narx = API tannarxi × kurs × (1 + ustama), 100 so'mga yaxlitlanadi. Hozir: 1$ = {money(d.usd_rate)} so'm, ustama {d.markup}%.</div>
          <div className="row">
            <div className="grow"><Field label="Dollar kursi (so'm)"><MoneyInput value={rate === "" ? d.usd_rate : rate} onChange={(v) => setRate(v)} /></Field></div>
            <div style={{ width: 100 }}><Field label="Ustama %"><input className="input mono" inputMode="numeric" value={markup === "" ? d.markup : markup} onChange={(e) => setMarkup(e.target.value === "" ? "" : Math.min(300, Number(e.target.value.replace(/\D/g, ""))))} /></Field></div>
          </div>
          <button className="btn" disabled={busy || (rate === "" && markup === "")} onClick={() => run(async () => {
            if (rate !== "") await api.put("/admin/settings", { key: "donate_usd_rate", value: Number(rate) });
            if (markup !== "") await api.put("/admin/settings", { key: "donate_markup_percent", value: Number(markup) });
            const r = await api.post<{ changed: number }>("/admin/donate/reprice");
            toast(`${r.changed} ta paket narxi yangilandi`, "ok"); setRate(""); setMarkup(""); st.reload();
          })}>Saqlash va narxlarni yangilash</button>
        </div>
      )}
    </Loadable>
  );
}

// ---------------------------------------------------------------- O'YIN SAHIFASI
interface DPkg { id: number; name: string; diamonds: number; bonus: number; price: number; cost_usd: string | null; profit: number | null; is_active: boolean; is_hot: boolean; source: string; delivery: string; group: string; provider_id: number | null }
interface DGame { game: CGame; fields: unknown[]; view_provider_id: number | null; providers: Cheaper[]; packages: DPkg[]; rate: number }

function GameDetail({ slug, onBack, go }: { slug: string; onBack: () => void; go: Go }) {
  const { toast } = useApp();
  const [view, setView] = useState<number | null>(null);
  const [grp, setGrp] = useState("amount");
  const [pick, setPick] = useState(false);
  const st = useLoad(() => api.get<DGame>(`/admin/catalog/games/${encodeURIComponent(slug)}${view ? `?provider_id=${view}` : ""}`), [slug, view]);
  const { busy, run } = useAction();
  const enc = encodeURIComponent(slug);
  const updGame = (body: Record<string, unknown>) => run(async () => { await api.put(`/admin/donate/games/${enc}`, body); st.reload(); });
  const pkg = (p: DPkg, body: Record<string, unknown>) => run(async () => { await api.patch(`/admin/catalog/packages/${p.id}`, body); st.reload(); });
  const link = (from: string) => run(async () => {
    await api.post(`/admin/catalog/games/${enc}/link`, { from_slug: from });
    toast("Bog'landi: paketlar shu o'yinga qo'shildi. Sotuv hali eski API'da — kerak bo'lsa almashtiring", "ok");
    setPick(false); st.reload();
  });
  const sw = (pid: number, name: string) => run(async () => {
    if (!(await confirmDialog(`Endi «${name}» orqali sotilsinmi? Foydalanuvchilar shu API paketlarini ko'radi.`))) return;
    await api.post(`/admin/catalog/games/${enc}/provider`, { provider_id: pid });
    toast(`${name} ga o'tkazildi`, "ok"); setView(null); st.reload();
  });
  return (
    <>
      <button className="btn small ghost" style={{ alignSelf: "flex-start" }} onClick={onBack}>‹ Katalog</button>
      <Loadable state={st}>
        {(d) => {
          const g = d.game;
          const groups = groupsOf(d.packages);
          const list = d.packages.filter((p) => (groups.length > 1 ? p.group === grp : true));
          const viewing = d.view_provider_id;
          return (
            <>
              <div className="card row">
                <GameTile name={g.name} logo={g.logo} slug={g.slug} size={56} radius={16} />
                <div className="grow" style={{ minWidth: 0 }}><div className="bb ell" style={{ fontSize: 18 }}>{g.name}</div><div className="mut xs">{g.packages} faol paket · {g.provider ?? "qo'lda"}</div></div>
                <div className="col" style={{ alignItems: "flex-end", gap: 3 }}><span className="mut xs">Ko'rinadi</span><Toggle on={g.is_active} onChange={(v) => updGame({ is_active: v })} /></div>
              </div>

              <div className="sec-title">Yetkazib beruvchi (API)</div>
              <div className="adm2-list">
                {d.providers.map((p) => (
                  <div key={`${p.provider_id}-${p.slug}`} className="adm2-it">
                    <span className={"adm2-dot " + (p.current ? "g" : "m")} />
                    <div className="grow" style={{ minWidth: 0 }}>
                      <div className="b">{p.provider}{p.current && <span className="badge g" style={{ marginLeft: 6 }}>sotilmoqda</span>}</div>
                      <div className="mut xs ell">
                        {p.current ? "Foydalanuvchilar shu API paketlarini ko'radi" : !p.linked ? `Bog'lanmagan: «${p.name}»` : "Bog'langan, hozir sotilmayapti"}
                        {!p.current && p.pct != null && <> · <b className={p.pct < 0 ? "g" : "r"}>{p.pct > 0 ? "+" : ""}{p.pct}%</b> ({p.pairs} paket)</>}
                      </div>
                      {!p.current && p.ref && <div className="mut xs">{p.ref.name}: ${p.ref.cur} → ${p.ref.alt}</div>}
                    </div>
                    {!p.current && p.linked && (
                      <div className="col" style={{ gap: 6 }}>
                        <button className="btn small" disabled={busy} onClick={() => sw(p.provider_id, p.provider)}>O'tkazish</button>
                        <button className={"btn small ghost" + (viewing === p.provider_id ? " on" : "")} onClick={() => setView(viewing === p.provider_id ? null : p.provider_id)}>{viewing === p.provider_id ? "Joriy" : "Paketlar"}</button>
                      </div>
                    )}
                    {!p.current && !p.linked && <button className="btn small" disabled={busy} onClick={() => link(p.slug)}><Icon name="link" size={14} /> Bog'lash</button>}
                  </div>
                ))}
                <button className="adm2-it y sm b" onClick={() => setPick(true)}><Icon name="plus" size={16} /> Boshqa API'dagi variantni bog'lash</button>
              </div>
              {viewing && viewing !== g.provider_id && <div className="card adm2-warn sm">Siz boshqa API paketlarini ko'ryapsiz (hozir sotilmayapti).</div>}

              <div className="row between"><div className="sec-title">Paketlar</div><span className="mut xs">foyda = narx − tannarx × {money(d.rate)}</span></div>
              {groups.length > 1 && <Seg value={grp} onChange={setGrp} options={groups} />}
              {list.length === 0 ? <Empty icon="📦" text="Paket yo'q" /> : (
                <div className="adm2-list">
                  {list.map((p) => (
                    <div key={p.id} className="adm2-it" style={{ opacity: p.is_active ? 1 : 0.55 }}>
                      <div className="grow" style={{ minWidth: 0 }}>
                        <div className="row" style={{ gap: 6 }}><span className="b ell">{p.name}</span>{p.delivery === "voucher" && <span className="badge b">kod</span>}{p.source === "manual" && <span className="badge m">qo'lda</span>}</div>
                        <div className="mut xs mono">{p.cost_usd ? `tannarx $${Number(p.cost_usd).toFixed(2)}` : "tannarx —"}{p.profit != null && <> · <span className={p.profit >= 0 ? "g" : "r"}>foyda {p.profit >= 0 ? "+" : ""}{money(p.profit)}</span></>}</div>
                      </div>
                      <button className={"adm2-star" + (p.is_hot ? " on" : "")} disabled={busy} onClick={() => pkg(p, { is_hot: !p.is_hot })} aria-label="Mashhur"><Icon name="star" size={17} /></button>
                      <span className="b mono" style={{ minWidth: 64, textAlign: "right" }}>{money(p.price)}</span>
                      <Toggle on={p.is_active} onChange={(v) => pkg(p, { is_active: v })} />
                    </div>
                  ))}
                </div>
              )}
              <div className="row" style={{ gap: 8 }}>
                <button className="btn small ghost grow" onClick={() => go("packages")}><Icon name="plus" size={15} /> Qo'lda paket</button>
                <button className="btn small ghost grow" onClick={() => go("apis")}><Icon name="refresh" size={15} /> API'dan yangilash</button>
              </div>

              <div className="sec-title">Bosh sahifada</div>
              <div className="card col">
                <div className="row between"><span className="sm">Asosiy (katta karta)</span>
                  <div className="row" style={{ gap: 4 }}>{[0, 1, 2, 3].map((n) => <button key={n} className={"chip" + ((g.featured_slot ?? 0) === n ? " on" : "")} disabled={busy} onClick={() => updGame({ featured_slot: n })}>{n === 0 ? "—" : n}</button>)}</div></div>
                {!g.featured_slot && <div className="row between"><span className="sm">Mashhur o'yinlar qatorida</span><Toggle on={g.popular} onChange={(v) => updGame({ popular: v })} /></div>}
                <label className="btn small ghost" style={{ cursor: "pointer" }}>
                  🖼 Rasm yuklash
                  <input type="file" accept="image/*" hidden disabled={busy} onChange={(e) => {
                    const file = e.target.files?.[0];
                    e.target.value = "";
                    if (!file) return;
                    const fd = new FormData();
                    fd.append("file", file);
                    run(async () => { await api.form(`/admin/donate/games/${enc}/image`, fd); toast("Rasm saqlandi", "ok"); st.reload(); });
                  }} />
                </label>
              </div>
              {pick && <CandidatePicker slug={slug} onPick={link} onClose={() => setPick(false)} />}
            </>
          );
        }}
      </Loadable>
    </>
  );
}

const GROUP_LABEL: Record<string, string> = { amount: "Miqdor", pass: "Pass / obuna", other: "Boshqa" };
function groupsOf(pk: DPkg[]) {
  // hook emas (Loadable ichida chaqiriladi) — oddiy hisob
  const counts: Record<string, number> = {};
  pk.forEach((p) => { counts[p.group] = (counts[p.group] ?? 0) + 1; });
  return ["amount", "pass", "other"].filter((k) => counts[k]).map((k) => ({ v: k, label: `${GROUP_LABEL[k]} · ${counts[k]}` }));
}

function CandidatePicker({ slug, onPick, onClose }: { slug: string; onPick: (s: string) => void; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [qq, setQq] = useState("");
  useEffect(() => { const id = setTimeout(() => setQq(q.trim()), 350); return () => clearTimeout(id); }, [q]);
  const st = useLoad(() => api.get<{ slug: string; name: string; provider: string }[]>(`/admin/catalog/games/${encodeURIComponent(slug)}/candidates?q=${encodeURIComponent(qq)}`), [qq]);
  return (
    <Sheet open onClose={onClose}>
      <div className="col">
        <div className="sec-title">Boshqa API'dagi variant</div>
        <div className="mut xs">Tanlangan o'yinning paketlari shu o'yinga qo'shiladi. Mintaqasi to'g'ri (Global / Uzbekistan) variantni tanlang.</div>
        <div className="adm2-search"><Icon name="search" size={17} /><input placeholder="Nomi bo'yicha…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <Loadable state={st}>
          {(list) => list.length === 0 ? <Empty icon="🔎" text="Topilmadi" /> : (
            <div className="adm2-list">
              {list.map((x) => (
                <button key={x.slug} className="adm2-it" onClick={() => onPick(x.slug)}>
                  <div className="grow" style={{ textAlign: "left" }}><div className="b">{x.name}</div><div className="mut xs">{x.provider}</div></div>
                  <Icon name="link" size={16} />
                </button>
              ))}
            </div>
          )}
        </Loadable>
      </div>
    </Sheet>
  );
}

// ---------------------------------------------------------------- BOT (ochish/yopish, mehmonlar)
export function BotAdmin({ onChange }: { onChange?: () => void }) {
  const { toast } = useApp();
  const dash = useLoad(() => api.get<Dash>("/admin/dashboard"));
  const st = useLoad(() => api.get<{ id: number; name: string; known: boolean }[]>("/admin/bot/guests"));
  const [id, setId] = useState("");
  const { busy, run } = useAction();
  const open = dash.data?.bot.open;
  return (
    <>
      <div className="card row">
        <Ibox name="lock" c={open ? "g" : "r"} />
        <div className="grow"><div className="b">{open ? "Bot hamma uchun ochiq" : "Bot yopiq"}</div><div className="mut xs">{open ? "Hamma foydalana oladi" : "Faqat adminlar va mehmonlar kira oladi, qolganlarga «Tez kunda»"}</div></div>
        {open !== undefined && <Toggle on={!!open} onChange={(v) => run(async () => {
          if (!(await confirmDialog(v ? "Botni hamma uchun ochasizmi?" : "Botni yopasizmi?"))) return;
          await api.post("/admin/bot/open", { open: v }); dash.reload(); onChange?.();
        })} />}
      </div>
      {dash.data?.bot.inline === false && <div className="card adm2-warn sm">Inline qidiruv (@bot 86) o'chiq: @BotFather → /setinline.</div>}
      {dash.data?.bot.inline === true && <div className="card sm"><span className="g b">✓</span> Inline qidiruv ishlayapti: istalgan chatda bot nomini yozib, paket qidirish mumkin.</div>}
      <div className="sec-title">Mehmonlar (yopiq paytda ham kira oladi)</div>
      <div className="row">
        <input className="input mono grow" inputMode="numeric" placeholder="Telegram ID, masalan 123456789" value={id} onChange={(e) => setId(e.target.value.replace(/\D/g, ""))} />
        <button className="btn" disabled={busy || id.length < 5} onClick={() => run(async () => { await api.post("/admin/bot/guests", { id: Number(id) }); setId(""); toast("Ruxsat berildi", "ok"); st.reload(); })}>Qo'shish</button>
      </div>
      <div className="mut xs">ID'ni odam @userinfobot orqali bilib oladi. Botda ham: /ruxsat ID.</div>
      <Loadable state={st}>
        {(list) => list.length === 0 ? <Empty icon="👥" text="Mehmon yo'q" /> : (
          <div className="adm2-list">
            {list.map((g) => (
              <div key={g.id} className="adm2-it">
                <Ibox name="user" c="b" />
                <div className="grow"><div className="b mono">{g.id}</div><div className="mut xs">{g.known ? g.name : "hali /start bosmagan"}</div></div>
                <button className="btn small danger" disabled={busy} onClick={() => run(async () => { await api.post("/admin/bot/guests", { id: g.id, add: false }); st.reload(); })}>Olib tashlash</button>
              </div>
            ))}
          </div>
        )}
      </Loadable>
    </>
  );
}

// ---------------------------------------------------------------- BO'LIMLAR (ochish / «Tez kunda»)
interface SRow { key: string; value: number | string; label: string; group: string }
const SECTION_HINT: Record<string, string> = {
  feature_market: "Akkaunt sotish va sotib olish (garant bilan)", feature_rent: "Akkauntni ijaraga berish va olish",
  feature_boost: "Rank boost buyurtmalari", feature_tg: "Premium, Stars, sovg'alar", feature_arena: "Turnir, viktorina, reyting",
  feature_partner: "Videolar va mukofot", feature_top: "Top xaridorlar reytingi", feature_ai: "AI yordamchi",
};

export function SectionsAdmin() {
  const { toast } = useApp();
  const st = useLoad(() => api.get<SRow[]>("/admin/settings"));
  const { busy, run } = useAction();
  const set = (key: string, on: boolean) => run(async () => {
    st.setData(await api.put<SRow[]>("/admin/settings", { key, value: on ? "on" : "off" }));
    toast(on ? "Bo'lim ochildi" : "Bo'lim «Tez kunda» holatiga o'tdi", "ok");
  });
  return (
    <Loadable state={st}>
      {(rows) => {
        const feats = rows.filter((r) => r.key.startsWith("feature_"));
        return (
          <>
            <div className="mut xs">Yopilgan bo'lim foydalanuvchilarga «Tez kunda» bo'lib ko'rinadi. Siz (admin) yopiq bo'limga baribir kira olasiz.</div>
            <div className="adm2-list">
              {feats.map((r) => (
                <div key={r.key} className="adm2-it">
                  <span className={"adm2-dot " + (r.value === "on" ? "g" : "m")} />
                  <div className="grow" style={{ minWidth: 0 }}>
                    <div className="b">{r.label}</div>
                    <div className="mut xs ell">{SECTION_HINT[r.key] ?? ""}</div>
                  </div>
                  <span className={"badge " + (r.value === "on" ? "g" : "y")}>{r.value === "on" ? "Ochiq" : "Tez kunda"}</span>
                  <Toggle on={r.value === "on"} onChange={(v) => !busy && set(r.key, v)} />
                </div>
              ))}
            </div>
          </>
        );
      }}
    </Loadable>
  );
}

// ---------------------------------------------------------------- KO'PROQ
export type MenuItem = { v: string; icon: string; c: string; label: string; sub: string };
export const MORE: { title: string; items: MenuItem[] }[] = [
  { title: "Bot", items: [
    { v: "bot", icon: "lock", c: "r", label: "Botni ochish va mehmonlar", sub: "Yopiq/ochiq, ruxsat berilgan ID'lar, inline qidiruv" },
    { v: "sections", icon: "rocket", c: "y", label: "Bo'limlar: ochish / Tez kunda", sub: "Akkaunt savdo, ijara, boost, Telegram, Arena..." },
    { v: "broadcast", icon: "mega", c: "y", label: "Ommaviy xabar", sub: "Barcha yoki tanlangan foydalanuvchilarga" },
  ] },
  { title: "Pul", items: [
    { v: "incoming", icon: "card", c: "g", label: "Kirimlar va to'lov kartalari", sub: "P2P kartalar, SMS, bank bot, tekshiruvdagi to'lovlar" },
    { v: "withdraw", icon: "out", c: "y", label: "Pul yechish", sub: "Foydalanuvchi so'rovlari" },
    { v: "analytics", icon: "chart", c: "b", label: "Daromad va hisobot", sub: "Kunlik, oylik grafik" },
    { v: "promo", icon: "ticket", c: "v", label: "Promo-kodlar", sub: "Chegirma va bonus kodlar" },
  ] },
  { title: "Xizmatlar", items: [
    { v: "donate", icon: "gem", c: "v", label: "Donat (tekshiruv)", sub: "Eski ko'rinish: tekshiruvdagi buyurtmalar" },
    { v: "tg", icon: "send", c: "b", label: "Telegram xizmatlar", sub: "Premium, Stars, gift — avtomatik va qo'lda" },
    { v: "boost", icon: "rocket", c: "y", label: "Boost", sub: "Rank boost buyurtmalari" },
    { v: "rent", icon: "bag", c: "g", label: "Ijara", sub: "E'lonlar va nizolar" },
    { v: "moderation", icon: "doc", c: "y", label: "E'lonlar tekshiruvi", sub: "Akkaunt savdosi" },
    { v: "packages", icon: "box", c: "m", label: "Qo'lda paketlar", sub: "API'siz paket qo'shish" },
  ] },
  { title: "Arena", items: [
    { v: "tournaments", icon: "trophy", c: "y", label: "Turnirlar va setka", sub: "Ro'yxat, setka, g'olib" },
    { v: "matches", icon: "flag", c: "b", label: "Prognozlar", sub: "O'yinlar va natijalar" },
    { v: "arena", icon: "brain", c: "v", label: "Viktorina, ovoz, statistika", sub: "Rone Arena statistikasi" },
    { v: "partner", icon: "play", c: "g", label: "Hamkorlar", sub: "Videolar va kodlar" },
  ] },
  { title: "Premium", items: [
    { v: "signals", icon: "bell", c: "y", label: "Ikki barobar almaz signali", sub: "Obunachilarga darhol xabar" },
    { v: "pro", icon: "trophy", c: "v", label: "Pro auksion", sub: "Pro arizalar va nizolar" },
  ] },
  { title: "Xavfsizlik", items: [
    { v: "kyc", icon: "shield", c: "b", label: "Identifikatsiya (KYC)", sub: "Hujjat tekshiruvi" },
    { v: "disputes", icon: "flag", c: "r", label: "Nizolar", sub: "Savdo bitimlari bo'yicha" },
    { v: "audit", icon: "doc", c: "y", label: "Admin jurnali", sub: "Kim, qachon, nima qildi" },
    { v: "settings", icon: "settings", c: "v", label: "Sozlamalar", sub: "Narx, foiz, limitlar, bo'limlar" },
  ] },
];
export const MORE_BY_V: Record<string, MenuItem> = Object.fromEntries(MORE.flatMap((g) => g.items).map((x) => [x.v, x]));

export function MoreMenu({ go, counts }: { go: Go; counts?: Record<string, number> }) {
  return (
    <>
      {MORE.map((grp) => (
        <div key={grp.title} className="col" style={{ gap: 8 }}>
          <div className="sec-title">{grp.title}</div>
          <div className="adm2-list">
            {grp.items.map((x) => (
              <button key={x.v} className="adm2-it" onClick={() => go(x.v)}>
                <Ibox name={x.icon} c={x.c} />
                <div className="grow" style={{ textAlign: "left", minWidth: 0 }}><div className="b">{x.label}</div><div className="mut xs ell">{x.sub}</div></div>
                {counts?.[x.v] ? <span className="badge y">{counts[x.v]}</span> : null}
                <Icon name="right" size={17} className="mut" />
              </button>
            ))}
          </div>
        </div>
      ))}
    </>
  );
}

export function useLinkCounts(d: Dash | null) {
  return useMemo(() => {
    const out: Record<string, number> = {};
    d?.links.forEach((l) => { out[l.section] = (out[l.section] ?? 0) + l.count; });
    d?.queue.forEach((q) => { const k = q.kind === "topup" ? "incoming" : q.kind; out[k] = (out[k] ?? 0) + 1; });
    return out;
  }, [d]);
}

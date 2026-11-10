/* DEMO rejimi: server o'rniga brauzer ichidagi soxta API (VITE_DEMO=1 bilan yig'ilganda).
   Barcha ma'lumotlar namuna; haqiqiy to'lov, almaz yoki xabar yuborilmaydi. */

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any

class MockError extends Error {
  constructor(public code: string, message: string, public status = 400) {
    super(message);
  }
}

const now = () => new Date().toISOString();
const ago = (min: number) => new Date(Date.now() - min * 60000).toISOString();
let seq = 100;
const nid = () => ++seq;
const ME = 1001;

const PKGS = [
  ["ML", "11 almaz", 11, 0, 2_500], ["ML", "56 almaz", 56, 0, 12_000], ["ML", "86 almaz", 78, 8, 18_500],
  ["ML", "172 almaz", 156, 16, 37_000], ["ML", "257 almaz", 234, 23, 55_000], ["ML", "344 almaz", 312, 32, 73_000],
  ["ML", "514 almaz", 468, 46, 109_000], ["ML", "706 almaz", 625, 81, 145_000], ["ML", "1412 almaz", 1250, 162, 289_000],
  ["ML", "Haftalik propusk", 0, 0, 22_000], ["MC", "56 almaz", 56, 0, 12_500], ["MC", "172 almaz", 156, 16, 38_000],
  ["MC", "344 almaz", 312, 32, 74_000], ["MC", "706 almaz", 625, 81, 147_000],
].map(([game, name, diamonds, bonus, price], i) => ({
  id: i + 1, game, name, diamonds, bonus, price, is_hot: String(name).startsWith("172"), is_active: true, sku: `${game}_${i + 1}`, sort: i,
}));

const sellers: Record<number, Json> = {
  2001: { id: 2001, name: "Sardor", username: "sardor_ml", rating: 4.9, rating_count: 41 },
  2002: { id: 2002, name: "Jasur", username: "jasur_pro", rating: 4.7, rating_count: 18 },
  [ME]: { id: ME, name: "Aziz", username: "aziz_demo", rating: 4.8, rating_count: 12 },
};

const state: Json = {
  me: {
    id: ME, name: "Aziz", username: "aziz_demo", rating: 4.8, rating_count: 12, balance: 145_000, tickets: 3, lang: "uz",
    phone: null, ml_id: "84512937", bio: null, is_admin: true, sales: 2, positive_percent: 97, active_listings: 1,
    referral_bonus: 1234, referral_min_topup: 10_000, ref_link: "https://t.me/VaynexoBot?startapp=ref_1001", ref_invited: 3, ref_paid: 1, ref_earned: 1234,
    commission_percent: 5,
  },
  settings: { referral_bonus: 1234, referral_min_topup: 10_000, vip_price_per_day: 5_000 } as Record<string, number>,
  favs: new Set<number>([12]),
  ledger: [
    { id: 3, amount: -37_000, balance_after: 145_000, kind: "donate", note: null, created_at: ago(90) },
    { id: 2, amount: 1_234, balance_after: 182_000, kind: "referral", note: null, created_at: ago(300) },
    { id: 1, amount: 180_766, balance_after: 180_766, kind: "topup", note: null, created_at: ago(600) },
  ],
  topups: [] as Json[],
  withdrawals: [] as Json[],
  orders: [{ id: 41, ref: "VX-D41", game: "ML", title: "172 almaz", player_id: "84512937", zone_id: "2104", price: 37_000, status: "done", error: null, created_at: ago(90), finished_at: ago(89) }],
  listings: [
    { id: 10, seller_id: 2001, game: "ML", title: "Mythic Glory · 210 skin", rank: "Mythic Glory", server: "Asia", collection_level: "World Collector", skins: 210, heroes: 118, price: 2_900_000, description: "Eng kuchli akkaunt: 210 skin, 12 ta Collector skin, barcha qahramonlar ochiq.", media: [], status: "active", views: 512, created_at: ago(3000), vip_until: new Date(Date.now() + 3 * 86400000).toISOString() },
    { id: 11, seller_id: 2001, game: "ML", title: "Mythic akkaunt · 120 skin", rank: "Mythic", server: "Asia", collection_level: "Mega Collector", skins: 120, heroes: 85, price: 1_250_000, description: "Moonton bog'langan, 120 skin, 6 ta Legend skin. Pochta va parol to'liq beriladi.", media: [], status: "active", views: 214, created_at: ago(30) },
    { id: 12, seller_id: 2002, game: "ML", title: "Legend akkaunt · 41 skin", rank: "Legend", server: "Asia", collection_level: "Exalted Collector", skins: 41, heroes: 60, price: 540_000, description: "Toza akkaunt, hech qachon bloklanmagan.", media: [], status: "active", views: 88, created_at: ago(120) },
    { id: 13, seller_id: 2001, game: "ML", title: "Epic akkaunt · 18 skin", rank: "Epic", server: "Asia", collection_level: "Senior Collector", skins: 18, heroes: 32, price: 150_000, description: "Boshlash uchun arzon akkaunt.", media: [], status: "active", views: 45, created_at: ago(400) },
    { id: 14, seller_id: 2002, game: "MC", title: "Magic Chess · Master", rank: "Mythic", server: "Asia", collection_level: "", skins: 25, heroes: 0, price: 320_000, description: "Magic Chess Master darajasi.", media: [], status: "active", views: 23, created_at: ago(600) },
    { id: 15, seller_id: ME, game: "ML", title: "Mythic akkaunt · 98 skin", rank: "Mythic", server: "Asia", collection_level: "Mega Collector", skins: 98, heroes: 80, price: 980_000, description: "Mening akkauntim.", media: [], status: "active", views: 214, created_at: ago(2000) },
    { id: 16, seller_id: 2001, game: "ML", title: "Legend akkaunt · 60 skin", rank: "Legend", server: "Asia", collection_level: "Exalted Collector", skins: 60, heroes: 70, price: 620_000, description: "Moderatsiyadagi e'lon (admin panelda ko'rinadi).", media: [], status: "moderation", views: 0, created_at: ago(10) },
  ] as Json[],
  chats: [] as Json[],
  messages: [] as Json[],
  deals: [] as Json[],
  reviews: new Set<number>(),
  tg: [] as Json[],
  boosts: [] as Json[],
  tournaments: [
    { id: 1, title: "Mobile Legends Noyabr kubogi", game: "ML", prize_fund: 1_000_000, entry_fee: 10_000, max_players: 256, players_count: 128, starts_at: new Date(Date.now() + 20 * 86400000).toISOString(), rules: "5v5, Draft pick. Har bir jamoada 5 o'yinchi.", status: "open", joined: false },
    { id: 2, title: "Haftalik Magic Chess turniri", game: "MC", prize_fund: 300_000, entry_fee: 0, max_players: 64, players_count: 37, starts_at: new Date(Date.now() + 5 * 86400000).toISOString(), rules: "Shveytsariya tizimi, 5 tur.", status: "open", joined: false },
  ] as Json[],
  incoming: [{ id: 7, amount: 51_212, source: "sms", raw_text: "HUMOCARD *5276: Popolnenie 51 212.00 UZS", status: "unmatched", topup_id: null, created_at: ago(15) }] as Json[],
  users: [] as Json[],
};
state.users = [
  { ...state.me, is_banned: false, created_at: ago(5000) },
  { ...sellers[2001], balance: 320_000, tickets: 1, lang: "uz", phone: null, ml_id: null, bio: null, is_admin: false, is_banned: false, created_at: ago(9000) },
  { ...sellers[2002], balance: 15_000, tickets: 0, lang: "ru", phone: null, ml_id: null, bio: null, is_admin: false, is_banned: false, created_at: ago(7000) },
];
state.withdrawals.push({ id: 5, user_id: 2001, amount: 300_000, card: "8600123456789012", card_holder: "SARDOR K", status: "pending", admin_note: null, created_at: ago(40) });
state.tg.push({ id: 9, ref: "VX-T9", kind: "premium", title: "Telegram Premium · 3 oy", target_username: "@jasur_pro", details: { months: 3 }, price: 189_000, status: "processing", admin_note: null, user_id: 2002, created_at: ago(25) });

// ---------------------------------------------------------------- yordamchilar
const fmt = (n: number) => n.toLocaleString("ru-RU").replace(/,/g, " ");
function money(amount: number, kind: string, note: string | null = null) {
  if (state.me.balance + amount < 0) throw new MockError("insufficient_funds", "Balansda mablag' yetarli emas", 402);
  state.me.balance += amount;
  state.ledger.unshift({ id: nid(), amount, balance_after: state.me.balance, kind, note, created_at: now() });
  const u = state.users.find((x: Json) => x.id === ME);
  if (u) u.balance = state.me.balance;
}
const card = (l: Json) => ({
  id: l.id, game: l.game, title: l.title, rank: l.rank, server: l.server, collection_level: l.collection_level, skins: l.skins,
  heroes: l.heroes, price: l.price, cover: l.media.find((m: Json) => m.type === "image")?.url ?? null, status: l.status,
  created_at: l.created_at, views: l.views, reject_reason: l.reject_reason ?? null,
  vip: !!l.vip_until && Date.parse(l.vip_until) > Date.now(), vip_until: l.vip_until ?? null, is_fav: state.favs.has(l.id),
  seller_rating: sellers[l.seller_id]?.rating ?? null,
});
const full = (l: Json) => ({ ...card(l), description: l.description, media: l.media, views: l.views, reject_reason: null, seller: sellers[l.seller_id] });
const listing = (id: number) => {
  const l = state.listings.find((x: Json) => x.id === id);
  if (!l) throw new MockError("not_found", "E'lon topilmadi", 404);
  return l;
};
const chatView = (c: Json) => ({ id: c.id, listing: card(listing(c.listing_id)), role: c.buyer_id === ME ? "buyer" : "seller", buyer_id: c.buyer_id, seller_id: c.seller_id, last_message_at: c.last_message_at });
const dealView = (d: Json) => ({
  ...d, listing: card(listing(d.listing_id)), role: d.buyer_id === ME ? "buyer" : "seller",
  credentials: ["delivered", "completed", "disputed"].includes(d.status) && d.buyer_id === ME ? d.creds : null,
  reviewed: state.reviews.has(d.id), seller_deliver_hours: 12,
});
const sys = (chatId: number, text: string) => state.messages.push({ id: nid(), chat_id: chatId, sender_id: null, text, created_at: now() });
const later = (ms: number, fn: () => void) => setTimeout(fn, ms);

function openChat(listingId: number) {
  const l = listing(listingId);
  let c = state.chats.find((x: Json) => x.listing_id === listingId && x.buyer_id === ME);
  if (!c) {
    c = { id: nid(), listing_id: listingId, buyer_id: ME, seller_id: l.seller_id, last_message_at: now() };
    state.chats.unshift(c);
  }
  return c;
}

const STAR = [[0, 4000], [25, 5000], [50, 7000], [75, 8000], [100, 10000]];
const DIV = ["V", "IV", "III", "II", "I"];
function quote(b: Json) {
  const pos = b.current_rank === "Epic" ? DIV.indexOf(b.current_division) * 5 : b.current_rank === "Legend" ? 25 + DIV.indexOf(b.current_division) * 5 : 50 + (b.current_stars || 0);
  const end = b.target_rank === "Legend" ? 45 : b.target_rank === "Mythic" ? 50 + Math.max(1, b.target_stars || 0) : 50 + Math.max(50, b.target_stars || 0);
  if (end <= pos) throw new MockError("bad_rank", "Maqsad rank hozirgisidan yuqori bo'lishi kerak");
  let price = 0;
  for (let p = pos; p < end; p++) price += STAR.filter(([s]) => p >= s).pop()![1];
  const days = Math.max(1, Math.round((end - pos) / 15));
  return { price, stars: end - pos, days: `${days}–${days + 1}` };
}

const CATALOG = {
  premium: [{ months: 1, price: 69_000 }, { months: 3, price: 189_000 }, { months: 6, price: 349_000 }, { months: 12, price: 599_000 }],
  stars: { presets: [50, 100, 250, 500, 1000, 2500, 5000, 10000], rate: 220, min: 50, max: 100000 },
  gifts: [["heart", "Yurak", 15000], ["bear", "Ayiqcha", 15000], ["box", "Sovg'a qutisi", 25000], ["rose", "Gul", 25000], ["cup", "Kubok", 50000], ["diamond", "Brilliant", 100000]].map(([code, name, price]) => ({ code, name, price })),
  nft: [["gift", "NFT sovg'a", 350000], ["username", "Username", 120000], ["number", "Anonim raqam", 90000]].map(([code, name, price]) => ({ code, name, price })),
};

// ---------------------------------------------------------------- marshrutlar
type H = (m: RegExpMatchArray, body: Json, q: URLSearchParams) => Json | Promise<Json>;
const routes: [string, RegExp, H][] = [];
const on = (method: string, path: string, h: H) => routes.push([method, new RegExp("^" + path.replace(/:\w+/g, "([^/]+)") + "$"), h]);

on("GET", "/me", () => ({ ...state.me, referral_bonus: state.settings.referral_bonus, referral_min_topup: state.settings.referral_min_topup }));
on("PATCH", "/me", (_m, b) => {
  for (const k of ["first_name", "phone", "ml_id", "bio", "lang"]) if (k in b) state.me[k === "first_name" ? "name" : k] = b[k];
  return state.me;
});
on("GET", "/home", () => ({ balance: state.me.balance, tickets: state.me.tickets, tournament: state.tournaments[0] }));
on("GET", "/top", (_m, _b, q) => {
  const names = ["Shoxrux", "Akbar_K", "Umid_7", "Sardor_pro", "Jasur ML", "Dilshod_17", "Aziz Mythic", "Bekzod_x", "Omadbek"];
  const items = names.map((n, i) => ({ place: i + 1, user_id: 3000 + i, name: n, total: 3_480_000 - i * 120_000 - (q.get("period") === "week" ? 2_000_000 : 0) }));
  items.push({ place: 47, user_id: ME, name: "aziz_demo", total: 37_000 });
  return { period: q.get("period"), items, me: items[items.length - 1] };
});
on("GET", "/history", (_m, _b, q) => {
  const t = q.get("type") || "all";
  const items: Json[] = [];
  if (["all", "donate"].includes(t)) state.orders.forEach((o: Json) => items.push({ type: "donate", id: o.id, game: o.game, title: o.title, sub: `ID ${o.player_id} (${o.zone_id})`, amount: -o.price, status: o.status, created_at: o.created_at }));
  if (["all", "account"].includes(t)) state.deals.forEach((d: Json) => items.push({ type: "account", id: d.id, game: "ML", title: listing(d.listing_id).title, sub: "Garantli bitim", amount: -d.price, status: d.status, created_at: d.created_at }));
  if (["all", "boost"].includes(t)) state.boosts.forEach((b: Json) => items.push({ type: "boost", id: b.id, game: b.game, title: `${b.current_rank} → ${b.target_rank}`, sub: "Rank boost", amount: -b.price, status: b.status, created_at: b.created_at }));
  if (["all", "telegram"].includes(t)) state.tg.filter((o: Json) => o.user_id === ME).forEach((o: Json) => items.push({ type: "telegram", id: o.id, game: "TG", title: o.title, sub: o.target_username, amount: -o.price, status: o.status, created_at: o.created_at }));
  if (["all", "wallet"].includes(t)) state.topups.filter((x: Json) => x.status === "paid").forEach((x: Json) => items.push({ type: "topup", id: x.id, game: "UZS", title: "Hamyon to'ldirish", sub: "P2P karta", amount: x.pay_amount, status: "done", created_at: x.paid_at }));
  items.sort((a, b) => (b.created_at > a.created_at ? 1 : -1));
  return { items, spent: items.filter((i) => i.amount < 0 && ["done", "completed"].includes(i.status)).reduce((s, i) => s - i.amount, 0), count: items.length };
});

// hamyon
const topupView = (t: Json) => {
  if (t.status === "pending" && Date.now() - Date.parse(t.created_at) > 8000) {
    t.status = "paid";
    t.paid_at = now();
    money(t.pay_amount, "topup", "P2P (demo: avtomatik tasdiqlandi)");
  }
  return { ...t, card_number: "5614 6822 0915 5276", card_holder: "BOTIRALIYEV AZIZBEK", balance: state.me.balance };
};
on("GET", "/wallet", () => ({
  balance: state.me.balance, entries: state.ledger,
  pending_topup: state.topups.find((t: Json) => t.status === "pending") ? topupView(state.topups.find((t: Json) => t.status === "pending")) : null,
  limits: { topup_min: 1000, topup_max: 20_000_000, withdraw_min: 10_000, ttl_minutes: 30 },
}));
on("POST", "/wallet/topup", (_m, b) => {
  if (!(b.amount >= 1000)) throw new MockError("bad_amount", "Summa 1 000 so'mdan kam bo'lmasin");
  state.topups.forEach((t: Json) => t.status === "pending" && (t.status = "cancelled"));
  const t = { id: nid(), requested_amount: b.amount, pay_amount: b.amount + 1 + Math.floor(Math.random() * 999), status: "pending", created_at: now(), expires_at: new Date(Date.now() + 30 * 60000).toISOString(), paid_at: null };
  state.topups.unshift(t);
  return topupView(t);
});
on("GET", "/wallet/topup/:id", (m) => topupView(state.topups.find((t: Json) => t.id === +m[1])));
on("POST", "/wallet/topup/:id/cancel", (m) => {
  const t = state.topups.find((x: Json) => x.id === +m[1]);
  if (t?.status === "pending") t.status = "cancelled";
  return { ok: true };
});
on("POST", "/wallet/withdraw", (_m, b) => {
  if (state.withdrawals.some((w: Json) => w.user_id === ME && w.status === "pending")) throw new MockError("bad_state", "Oldingi so'rovingiz hali ko'rib chiqilmoqda", 409);
  money(-b.amount, "withdraw");
  const w = { id: nid(), user_id: ME, amount: b.amount, card: b.card_number, card_holder: b.card_holder, status: "pending", admin_note: null, created_at: now() };
  state.withdrawals.unshift(w);
  return { ...w, card: "•••• " + w.card.slice(-4) };
});
on("GET", "/wallet/withdrawals", () => state.withdrawals.filter((w: Json) => w.user_id === ME).map((w: Json) => ({ ...w, card: "•••• " + w.card.slice(-4) })));

// donat
on("GET", "/donate/packages", (_m, _b, q) => PKGS.filter((p) => p.game === (q.get("game") || "ML") && p.is_active));
on("POST", "/donate/check-player", (_m, b) => ({ found: /^\d{5,}$/.test(b.player_id), nickname: `Player_${String(b.player_id).slice(-4)}` }));
on("POST", "/donate/orders", (_m, b) => {
  const p = PKGS.find((x) => x.id === b.package_id)!;
  const o: Json = { id: nid(), ref: "", game: p.game, title: p.name, player_id: b.player_id, zone_id: b.zone_id, price: p.price, status: "processing", error: null, created_at: now(), finished_at: null };
  o.ref = "VX-D" + o.id;
  money(-p.price, "donate");
  state.orders.unshift(o);
  later(3000, () => {
    if (String(o.player_id).startsWith("0")) {
      o.status = "refunded";
      o.error = "Player not found";
      money(o.price, "donate_refund");
    } else {
      o.status = "done";
      state.me.tickets += 1;
    }
    o.finished_at = now();
  });
  return o;
});
on("GET", "/donate/orders/:id", (m) => state.orders.find((o: Json) => o.id === +m[1]));

// savdo
on("GET", "/listings", (_m, _b, q) => {
  let ls = state.listings.filter((l: Json) => l.status === "active");
  const s = (q.get("q") || "").toLowerCase();
  if (s) ls = ls.filter((l: Json) => (l.title + l.rank + l.description).toLowerCase().includes(s));
  if (q.get("game")) ls = ls.filter((l: Json) => l.game === q.get("game"));
  if (q.get("rank")) ls = ls.filter((l: Json) => l.rank.startsWith(q.get("rank")!));
  if (q.get("level")) ls = ls.filter((l: Json) => l.collection_level.startsWith(q.get("level")!));
  if (q.get("min_price")) ls = ls.filter((l: Json) => l.price >= +q.get("min_price")!);
  if (q.get("max_price")) ls = ls.filter((l: Json) => l.price <= +q.get("max_price")!);
  if (q.get("min_skins")) ls = ls.filter((l: Json) => l.skins >= +q.get("min_skins")!);
  if (q.get("favorites") === "true") ls = ls.filter((l: Json) => state.favs.has(l.id));
  const sort = q.get("sort");
  const vip = (l: Json) => (l.vip_until && Date.parse(l.vip_until) > Date.now() ? 0 : 1);
  ls = [...ls].sort((a: Json, b: Json) => vip(a) - vip(b) || (sort === "cheap" ? a.price - b.price : sort === "expensive" ? b.price - a.price : sort === "skins" ? b.skins - a.skins : b.id - a.id));
  return { items: ls.map(card), has_more: false, total: ls.length };
});
on("POST", "/listings/:id/favorite", (m) => {
  const id = +m[1];
  if (state.favs.has(id)) state.favs.delete(id);
  else state.favs.add(id);
  return { is_fav: state.favs.has(id) };
});
on("GET", "/vip/price", () => ({ price_per_day: state.settings.vip_price_per_day }));
on("POST", "/listings/:id/vip", (m, b) => {
  const l = listing(+m[1]);
  if (l.seller_id !== ME) throw new MockError("not_found", "E'lon topilmadi", 404);
  if (l.status !== "active") throw new MockError("bad_state", "VIP faqat faol (tasdiqlangan) e'longa qo'yiladi", 409);
  money(-state.settings.vip_price_per_day * b.days, "vip", `VIP ${b.days} kun`);
  const start = l.vip_until && Date.parse(l.vip_until) > Date.now() ? Date.parse(l.vip_until) : Date.now();
  l.vip_until = new Date(start + b.days * 86400000).toISOString();
  return card(l);
});
on("GET", "/listings/:id", (m) => {
  const l = listing(+m[1]);
  return { ...full(l), seller_stats: { sales: 12, positive_percent: 97 }, seller_verified: l.seller_id === 2001, chat_id: state.chats.find((c: Json) => c.listing_id === l.id && c.buyer_id === ME)?.id ?? null, is_mine: l.seller_id === ME };
});
on("POST", "/listings", (_m, b) => {
  const l = { id: nid(), seller_id: ME, ...b, status: "moderation", views: 0, created_at: now() };
  state.listings.unshift(l);
  return card(l);
});
on("PUT", "/listings/:id", (m, b) => {
  const l = listing(+m[1]);
  Object.assign(l, b, { status: "moderation" });
  return card(l);
});
on("POST", "/listings/:id/close", (m) => {
  const l = listing(+m[1]);
  l.status = "closed";
  return card(l);
});
on("GET", "/my/listings", () => state.listings.filter((l: Json) => l.seller_id === ME).map((l: Json) => ({ ...card(l), views: l.views, chats: 2 })));
on("POST", "/media", async (_m, b) => {
  const f: File = b.get("file");
  if (!f?.type.startsWith("image/")) throw new MockError("bad_type", "Demo rejimida faqat rasm yuklanadi");
  const url = await new Promise<string>((res) => { const r = new FileReader(); r.onload = () => res(String(r.result)); r.readAsDataURL(f); });
  return { type: "image", url };
});
on("POST", "/listings/:id/chat", (m) => chatView(openChat(+m[1])));
on("GET", "/chats", () => state.chats.map(chatView));
on("GET", "/chats/:id", (m, _b, q) => {
  const c = state.chats.find((x: Json) => x.id === +m[1]);
  if (!c) throw new MockError("not_found", "Chat topilmadi", 404);
  const after = +(q.get("after") || 0);
  const d = state.deals.find((x: Json) => x.chat_id === c.id);
  return { chat: chatView(c), messages: state.messages.filter((x: Json) => x.chat_id === c.id && x.id > after), deal: d ? { id: d.id, status: d.status } : null };
});
on("POST", "/chats/:id/messages", (m, b) => {
  const c = state.chats.find((x: Json) => x.id === +m[1]);
  const msg = { id: nid(), chat_id: c.id, sender_id: ME, text: b.text, created_at: now() };
  state.messages.push(msg);
  c.last_message_at = now();
  later(2000, () => state.messages.push({ id: nid(), chat_id: c.id, sender_id: c.seller_id, text: "Assalomu alaykum! Ha, akkaunt sotuvda. Garant orqali olsangiz bo'ladi 👍", created_at: now() }));
  return msg;
});
on("POST", "/listings/:id/buy", (m) => {
  const l = listing(+m[1]);
  if (l.seller_id === ME) throw new MockError("own_listing", "O'z akkauntingizni sotib ololmaysiz");
  if (l.status !== "active") throw new MockError("bad_state", "Bu akkaunt allaqachon sotilgan yoki band", 409);
  const c = openChat(l.id);
  const d: Json = { id: nid(), listing_id: l.id, buyer_id: ME, seller_id: l.seller_id, chat_id: c.id, price: l.price, commission: Math.floor(l.price * 0.05), status: "paid", creds: null, delivered_at: null, auto_release_at: null, dispute_reason: null, resolution: null, created_at: now() };
  money(-l.price, "deal_pay");
  l.status = "reserved";
  state.deals.unshift(d);
  sys(c.id, `🔒 Xaridor ${fmt(d.price)} so'm to'ladi. Pul VAYNEXO garantida. Sotuvchi akkaunt ma'lumotlarini yuborsin.`);
  later(5000, () => {
    if (d.status !== "paid") return;
    d.status = "delivered";
    d.creds = "Moonton: sardor.ml.acc@gmail.com\nParol: Demo-Parol-2026\n(namuna ma'lumot)";
    d.delivered_at = now();
    d.auto_release_at = new Date(Date.now() + 48 * 3600000).toISOString();
    sys(c.id, "📦 Sotuvchi akkaunt ma'lumotlarini yubordi. Tekshirib, tasdiqlang.");
  });
  return dealView(d);
});
on("GET", "/deals", (_m, _b, q) => state.deals.filter((d: Json) => (q.get("role") === "seller" ? d.seller_id : d.buyer_id) === ME).map(dealView));
on("GET", "/deals/:id", (m) => dealView(state.deals.find((d: Json) => d.id === +m[1])));
on("POST", "/deals/:id/:action", (m, b) => {
  const d = state.deals.find((x: Json) => x.id === +m[1]);
  const l = listing(d.listing_id);
  const a = m[2];
  if (a === "confirm" && d.status === "delivered") {
    d.status = "completed";
    l.status = "sold";
    sys(d.chat_id, "✅ Bitim yakunlandi (xaridor tasdiqladi).");
  } else if (a === "cancel" && d.status === "paid") {
    throw new MockError("bad_state", "Sotuvchiga 12 soat beriladi. Undan keyin bekor qilishingiz mumkin", 409);
  } else if (a === "dispute" && ["paid", "delivered"].includes(d.status)) {
    d.status = "disputed";
    d.dispute_reason = b.reason;
    sys(d.chat_id, "⚖️ Nizo ochildi. Pul muzlatildi, admin ikkala tomonni ko'rib chiqadi.");
  } else if (a === "review") {
    state.reviews.add(d.id);
  } else throw new MockError("bad_state", "Bu amalni hozir bajarib bo'lmaydi", 409);
  return dealView(d);
});

// TG, boost, arena
on("GET", "/tg/catalog", () => CATALOG);
on("POST", "/tg/orders", (_m, b) => {
  const target = b.for_self ? "@" + state.me.username : "@" + String(b.target_username).replace(/^@/, "");
  if (!/^@[A-Za-z][A-Za-z0-9_]{3,31}$/.test(target)) throw new MockError("bad_username", "Telegram username noto'g'ri (masalan: @username)");
  let title = "", price = 0;
  if (b.kind === "premium") { price = CATALOG.premium.find((p) => p.months === b.months)!.price; title = `Telegram Premium · ${b.months} oy`; }
  if (b.kind === "stars") { if (!(b.stars >= 50)) throw new MockError("bad_stars", "Stars soni 50 dan kam bo'lmasin"); price = b.stars * 220; title = `Telegram Stars · ${fmt(b.stars)}`; }
  if (b.kind === "gift") { const g = CATALOG.gifts.find((x) => x.code === b.gift)!; price = +g.price; title = `Telegram Gift · ${g.name}`; }
  if (b.kind === "nft") { const n = CATALOG.nft.find((x) => x.code === b.nft)!; price = +n.price; title = `Telegram NFT · ${n.name}`; }
  money(-price, "tg_service");
  const o = { id: nid(), ref: "", kind: b.kind, title, target_username: target, details: {}, price, status: "processing", admin_note: null, user_id: ME, created_at: now() };
  o.ref = "VX-T" + o.id;
  state.tg.unshift(o);
  return o;
});
on("POST", "/boost/quote", (_m, b) => quote(b));
on("POST", "/boost/orders", (_m, b) => {
  const q = quote(b);
  money(-q.price, "boost");
  const o: Json = {
    id: nid(), ref: "", game: b.game, current_rank: b.current_rank === "Mythic" ? `Mythic ${b.current_stars}★` : `${b.current_rank} ${b.current_division}`,
    target_rank: b.target_rank === "Legend" ? "Legend I" : `${b.target_rank} ${b.target_stars}★`, stars: q.stars, lane: b.lane, note: b.note,
    login_method: b.login_method, price: q.price, status: "searching", booster_name: null, user_id: ME, created_at: now(), finished_at: null,
  };
  o.ref = "VX-B" + o.id;
  state.boosts.unshift(o);
  later(4000, () => { if (o.status === "searching") { o.status = "accepted"; o.booster_name = "Booster #7"; } });
  later(9000, () => { if (o.status === "accepted") o.status = "in_progress"; });
  later(15000, () => { if (o.status === "in_progress") { o.status = "finished"; o.finished_at = now(); } });
  return o;
});
on("GET", "/boost/orders", () => state.boosts);
on("GET", "/boost/orders/:id", (m) => state.boosts.find((o: Json) => o.id === +m[1]));
on("POST", "/boost/orders/:id/:action", (m) => {
  const o = state.boosts.find((x: Json) => x.id === +m[1]);
  if (m[2] === "confirm" && o.status === "finished") o.status = "done";
  else if (m[2] === "cancel" && o.status === "searching") { o.status = "refunded"; money(o.price, "boost_refund"); }
  else if (m[2] === "dispute") o.status = "disputed";
  else throw new MockError("bad_state", "Bu amalni hozir bajarib bo'lmaydi", 409);
  return o;
});
on("GET", "/tournaments", (_m, _b, q) => state.tournaments.filter((t: Json) => t.status === (q.get("status") || "open")));
on("GET", "/tournaments/:id", (m) => state.tournaments.find((t: Json) => t.id === +m[1]));
on("POST", "/tournaments/:id/join", (m) => {
  const t = state.tournaments.find((x: Json) => x.id === +m[1]);
  if (t.joined) throw new MockError("bad_state", "Siz allaqachon ro'yxatdasiz", 409);
  if (t.entry_fee) money(-t.entry_fee, "tournament_fee");
  t.joined = true;
  t.players_count += 1;
  return t;
});

// admin
on("GET", "/admin/stats", () => ({
  users: 1248, users_today: 37, moderation: state.listings.filter((l: Json) => l.status === "moderation").length,
  withdrawals: state.withdrawals.filter((w: Json) => w.status === "pending").length, unmatched: state.incoming.filter((i: Json) => i.status === "unmatched").length,
  disputes: state.deals.filter((d: Json) => d.status === "disputed").length, donate_review: 0, tg_pending: state.tg.filter((o: Json) => o.status === "processing").length,
  boost_open: state.boosts.filter((b: Json) => ["searching", "disputed"].includes(b.status)).length, topups_today: 4_250_000, donate_today: 1_870_000, balances_total: 18_640_000,
}));
const settingsRows = () => [
  { key: "vip_price_per_day", value: state.settings.vip_price_per_day, min: 0, max: 10_000_000, label: "VIP e'lon narxi (so'm / kun): e'lon ro'yxat tepasida turadi" },
  { key: "referral_bonus", value: state.settings.referral_bonus, min: 0, max: 10_000_000, label: "Taklif bonusi (so'm): do'st birinchi marta to'ldirganda. 0 — o'chiq" },
  { key: "referral_min_topup", value: state.settings.referral_min_topup, min: 1_000, max: 100_000_000, label: "Bonus uchun do'stning eng kam to'ldirishi (so'm)" },
];
on("GET", "/admin/settings", settingsRows);
on("PUT", "/admin/settings", (_m, b) => {
  if (!(b.value >= 0)) throw new MockError("bad_setting", "Qiymat 0 dan kam bo'lmasin");
  state.settings[b.key] = b.value;
  return settingsRows();
});
on("GET", "/admin/listings", () => state.listings.filter((l: Json) => l.status === "moderation").map(full));
on("POST", "/admin/listings/:id/moderate", (m, b) => {
  const l = listing(+m[1]);
  l.status = b.approve ? "active" : "rejected";
  l.reject_reason = b.approve ? null : b.reason;
  return card(l);
});
on("GET", "/admin/withdrawals", (_m, _b, q) => state.withdrawals.filter((w: Json) => w.status === (q.get("status") || "pending")));
on("POST", "/admin/withdrawals/:id", (m, b) => {
  const w = state.withdrawals.find((x: Json) => x.id === +m[1]);
  w.status = b.action === "paid" ? "paid" : "rejected";
  w.admin_note = b.note || null;
  return w;
});
on("GET", "/admin/incoming", (_m, _b, q) => state.incoming.filter((i: Json) => i.status === (q.get("status") || "unmatched")));
on("POST", "/admin/incoming", (_m, b) => {
  const amount = b.amount || +String(b.text || "").replace(/[^\d.,\s]/g, "").replace(/[.,]\d{2}\b/, "").replace(/\D/g, "");
  const inc = { id: nid(), amount, source: "admin", raw_text: b.text, status: "unmatched", topup_id: null, created_at: now() };
  state.incoming.unshift(inc);
  return inc;
});
on("GET", "/admin/topups", () => [{ id: 77, user_id: 2002, requested_amount: 50_000, pay_amount: 51_212, status: "expired", expires_at: ago(5), paid_at: null, created_at: ago(35), card_number: "", card_holder: "" }]);
on("POST", "/admin/incoming/:id/assign", (m) => {
  const i = state.incoming.find((x: Json) => x.id === +m[1]);
  i.status = "matched";
  return { ok: true };
});
on("POST", "/admin/incoming/:id/ignore", (m) => {
  state.incoming.find((x: Json) => x.id === +m[1]).status = "ignored";
  return { ok: true };
});
on("GET", "/admin/deals", () => state.deals.filter((d: Json) => d.status === "disputed").map((d: Json) => ({ ...dealView(d), credentials: d.creds })));
on("POST", "/admin/deals/:id/resolve", (m, b) => {
  const d = state.deals.find((x: Json) => x.id === +m[1]);
  d.status = b.winner === "buyer" ? "refunded" : "completed";
  d.resolution = b.note;
  if (b.winner === "buyer") money(d.price, "deal_refund");
  return dealView(d);
});
on("GET", "/admin/donate", (_m, _b, q) => state.orders.filter((o: Json) => o.status === (q.get("status") || "review")).map((o: Json) => ({ ...o, user_id: ME, attempts: 1, provider_ref: null })));
on("POST", "/admin/donate/:id", () => ({ ok: true }));
on("GET", "/admin/tg", (_m, _b, q) => state.tg.filter((o: Json) => o.status === (q.get("status") || "processing")));
on("POST", "/admin/tg/:id", (m, b) => {
  const o = state.tg.find((x: Json) => x.id === +m[1]);
  o.status = b.action === "done" ? "done" : "refunded";
  return o;
});
on("GET", "/admin/boost", (_m, _b, q) => state.boosts.filter((o: Json) => o.status === (q.get("status") || "searching")));
on("POST", "/admin/boost/:id", (m, b) => {
  const o = state.boosts.find((x: Json) => x.id === +m[1]);
  o.status = b.action === "done" ? "done" : "refunded";
  return o;
});
on("GET", "/admin/users", (_m, _b, q) => {
  const s = (q.get("q") || "").toLowerCase().replace("@", "");
  return state.users.filter((u: Json) => !s || String(u.id).includes(s) || (u.username || "").includes(s) || u.name.toLowerCase().includes(s));
});
on("POST", "/admin/users/:id/ban", (m, b) => {
  const u = state.users.find((x: Json) => x.id === +m[1]);
  if (u.id === ME) throw new MockError("bad_state", "O'zingizni bloklay olmaysiz", 409);
  u.is_banned = b.banned;
  return { ok: true };
});
on("POST", "/admin/users/:id/balance", (m, b) => {
  const u = state.users.find((x: Json) => x.id === +m[1]);
  if (u.id === ME) money(b.amount, "admin_adjust", b.note);
  else u.balance += b.amount;
  return { ok: true, applied: true };
});
on("GET", "/admin/packages", () => PKGS);
on("POST", "/admin/packages", (_m, b) => { const p = { id: nid(), ...b, sku: b.provider_sku }; PKGS.push(p); return p; });
on("PUT", "/admin/packages/:id", (m, b) => { const p = PKGS.find((x) => x.id === +m[1])!; Object.assign(p, b, { sku: b.provider_sku }); return p; });
on("POST", "/admin/tournaments", (_m, b) => { const t = { id: nid(), ...b, players_count: 0, joined: false }; state.tournaments.push(t); return t; });
on("PUT", "/admin/tournaments/:id", (m, b) => { const t = state.tournaments.find((x: Json) => x.id === +m[1]); Object.assign(t, b); return t; });
on("GET", "/admin/tournaments/:id/entries", () => [{ user_id: ME, nick: "Aziz", game_id: "84512937", server: "2104", tg_username: "@aziz_demo" }]);

export async function mockRequest(method: string, url: string, body: unknown): Promise<unknown> {
  await new Promise((r) => setTimeout(r, 180)); // tarmoq kechikishi taqlidi
  const [path, qs] = url.split("?");
  const q = new URLSearchParams(qs || "");
  for (const [m, re, h] of routes) {
    if (m !== method) continue;
    const match = path.match(re);
    if (match) {
      try {
        return structuredClone(await h(match, body as Json, q));
      } catch (e) {
        if (e instanceof MockError) throw e;
        console.error(e);
        throw new MockError("error", "Demo xatosi");
      }
    }
  }
  throw new MockError("not_found", "Demo rejimida bu amal mavjud emas", 404);
}

export { MockError };

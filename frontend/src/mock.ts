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
    commission_percent: 5, kyc_status: "none", kyc_note: null, pin_set: false, bio_set: false, notify_chat: true, notify_tour: true,
    purchases_count: 7, rent_count: 1, kyc_required: { marketplace: true, rental: true, withdraw: true }, features: { market: false, rent: false, boost: false, tg: true, arena: true, partner: true, ai: false, top: true }, points: 1_240,
    vip_credit_days: 0, tournament_passes: 1, boost_coupon_percent: 0, badge: null, wallet_id: "VX 4821 7730",
  },
  settings: {
    referral_bonus: 1234, referral_min_topup: 10_000, vip_price_per_day: 5_000, rent_deposit_type: "percent", rent_deposit_percent: 100,
    rent_deposit_fixed: 50_000, rent_commission_percent: 10, boost_express_percent: 30, boost_hero_percent: 15, boost_lane_percent: 10,
    tg_price_mode: "fixed", tg_markup_percent: 15, stars_cost: 190, stars_price: 220,
    premium_cost_1: 60_000, premium_cost_3: 165_000, premium_cost_6: 300_000, premium_cost_12: 520_000,
    premium_price_1: 69_000, premium_price_3: 189_000, premium_price_6: 349_000, premium_price_12: 599_000,
    gift_price_heart: 15_000, gift_price_bear: 15_000, gift_price_box: 25_000, gift_price_rose: 25_000, gift_price_cup: 50_000, gift_price_diamond: 100_000,
    nft_price_gift: 350_000, nft_price_username: 120_000, nft_price_number: 90_000,
  } as Record<string, Json>,
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
    { id: 3, title: "Dekabr Grand Cup", game: "ML", prize_fund: 2_000_000, entry_fee: 20_000, max_players: 128, players_count: 0, starts_at: new Date(Date.now() + 30 * 86400000).toISOString(), rules: "5v5", status: "soon", joined: false },
    { id: 4, title: "Oktabr kubogi", game: "ML", prize_fund: 500_000, entry_fee: 0, max_players: 64, players_count: 64, starts_at: new Date(Date.now() - 10 * 86400000).toISOString(), rules: "5v5", status: "finished", joined: true },
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
  const S = state.settings;
  const extras: Json[] = [];
  if (b.express) extras.push({ key: "express", label: "Express", percent: S.boost_express_percent });
  if (b.hero) extras.push({ key: "hero", label: `Qahramon: ${b.hero}`, percent: S.boost_hero_percent });
  if (b.lane) extras.push({ key: "lane", label: `Liniya: ${b.lane}`, percent: S.boost_lane_percent });
  extras.forEach((x) => (x.amount = Math.floor((price * x.percent) / 100)));
  let days = Math.max(1, Math.round((end - pos) / 15));
  if (b.express) days = Math.max(1, Math.floor(days / 2));
  const percents = { boost_express_percent: S.boost_express_percent, boost_hero_percent: S.boost_hero_percent, boost_lane_percent: S.boost_lane_percent };
  return { base: price, extras, price: price + extras.reduce((s, x) => s + x.amount, 0), stars: end - pos, days: `${days}–${days + 1}`, percents };
}

const GIFT_NAMES: [string, string][] = [["heart", "Yurak"], ["bear", "Ayiqcha"], ["box", "Sovg'a qutisi"], ["rose", "Gul"], ["cup", "Kubok"], ["diamond", "Brilliant"]];
const NFT_NAMES: [string, string][] = [["gift", "NFT sovg'a"], ["username", "Username"], ["number", "Anonim raqam"]];
const PRESETS = [50, 100, 250, 500, 1000, 2500];
const SBONUS: Record<number, number> = { 250: 5, 500: 15, 1000: 40, 2500: 120 };
function catalog() {
  const S = state.settings;
  const pct = S.tg_price_mode === "percent";
  const k = 100 + S.tg_markup_percent;
  const rate = pct ? (S.stars_cost * k) / 100 : S.stars_price;
  return {
    premium: [1, 3, 6, 12].map((m) => ({ months: m, price: pct ? Math.ceil((S[`premium_cost_${m}`] * k) / 100) : S[`premium_price_${m}`] })),
    stars: { presets: PRESETS, rate, min: 50, max: 100000, preset_prices: Object.fromEntries(PRESETS.map((n) => [n, Math.ceil(n * rate)])), bonus: SBONUS },
    gifts: GIFT_NAMES.map(([code, name]) => ({ code, name, price: S[`gift_price_${code}`] })),
    nft: NFT_NAMES.map(([code, name]) => ({ code, name, price: S[`nft_price_${code}`] })),
  };
}

// ---------------------------------------------------------------- marshrutlar
type H = (m: RegExpMatchArray, body: Json, q: URLSearchParams) => Json | Promise<Json>;
const routes: [string, RegExp, H][] = [];
const on = (method: string, path: string, h: H) => routes.push([method, new RegExp("^" + path.replace(/:\w+/g, "([^/]+)") + "$"), h]);

on("GET", "/me", () => ({ ...state.me, referral_bonus: state.settings.referral_bonus, referral_min_topup: state.settings.referral_min_topup }));
on("PATCH", "/me", (_m, b) => {
  for (const k of ["first_name", "phone", "ml_id", "bio", "lang", "notify_chat", "notify_tour"]) if (k in b) state.me[k === "first_name" ? "name" : k] = b[k];
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
const DEMO_CARDS = [
  { id: 1, number: "8600 0000 0000 0001", holder: "VAYNEXO KASSA", kind: "Uzcard" },
  { id: 2, number: "9860 0000 0000 0002", holder: "VAYNEXO KASSA", kind: "Humo" },
  { id: 3, number: "4073 0000 0000 0003", holder: "VAYNEXO KASSA", kind: "Visa" },
];
const topupView = (t: Json) => {
  // demo: «To'ladim» bosilgach 8 soniyadan keyin admin tasdiqlagandek bo'ladi
  if (t.status === "checking" && Date.now() - Date.parse(t.claimed_at) > 8000) {
    t.status = "paid";
    t.paid_at = now();
    money(t.pay_amount, "topup", "P2P (demo: tasdiqlandi)");
  }
  return { ...t, card_number: DEMO_CARDS[0].number, card_holder: DEMO_CARDS[0].holder, cards: [DEMO_CARDS[0]], balance: state.me.balance };
};
on("GET", "/wallet", () => ({
  balance: state.me.balance, entries: state.ledger,
  pending_topup: state.topups.find((t: Json) => ["pending", "checking"].includes(t.status)) ? topupView(state.topups.find((t: Json) => ["pending", "checking"].includes(t.status))) : null,
  limits: { topup_min: 1000, topup_max: 20_000_000, withdraw_min: 10_000, ttl_minutes: 10 },
  wallet_id: "VX 4821 7730", withdraw: { earned: 120_000, withdrawn: 0, available: Math.min(state.me.balance, 120_000) },
}));
on("POST", "/wallet/topup", (_m, b) => {
  if (!(b.amount >= 1000)) throw new MockError("bad_amount", "Summa 1 000 so'mdan kam bo'lmasin");
  state.topups.forEach((t: Json) => t.status === "pending" && (t.status = "cancelled"));
  const t = { id: nid(), requested_amount: b.amount, pay_amount: b.amount + 1 + Math.floor(Math.random() * 99), status: "pending", created_at: now(), expires_at: new Date(Date.now() + 10 * 60000).toISOString(), paid_at: null, has_receipt: false, reject_reason: null };
  state.topups.unshift(t);
  return topupView(t);
});
on("POST", "/wallet/topup/:id/paid", (m) => {
  const t = state.topups.find((x: Json) => x.id === +m[1]);
  if (t.status === "pending") { t.status = "checking"; t.claimed_at = now(); }
  return topupView(t);
});
on("GET", "/admin/topups/checking", () => state.topups.filter((t: Json) => t.status === "checking").map((t: Json) => ({ ...t, user_id: ME, user_name: "aziz_demo" })));
on("POST", "/admin/topups/:id/confirm", (m) => { const t = state.topups.find((x: Json) => x.id === +m[1]); t.status = "paid"; money(t.pay_amount, "topup", "P2P"); return t; });
on("POST", "/admin/topups/:id/reject", (m, b) => { const t = state.topups.find((x: Json) => x.id === +m[1]); t.status = "rejected"; t.reject_reason = b.reason; return t; });
const tgBank = { api_ready: true, logged_in: true, account: "@vaynexo_kassa", connected: true, error: null, bots: ["HUMOcardbot", "CardXabarBot"], seen: { HUMOcardbot: { at: now(), amount: 50000 } }, login_step: null };
on("GET", "/admin/tg-bank", () => tgBank);
on("PUT", "/admin/tg-bank/bots", (_m, b) => { tgBank.bots = (b.bots as string[]).map((x) => x.replace(/^@/, "")); return tgBank; });
on("GET", "/admin/donate/providers", () => ({ providers: [{ id: 1, name: "API 1", kind: "yupay", kind_label: "Donat API", base_url: "", host: null, key_set: true, is_active: true, config: {}, last_ok_at: now(), last_error: null, synced_at: now(), balance_usd: "42.10", webhook_url: "https://vaynexo.example/api/yupay/webhook/1" }], legacy_env: false, usd_rate: 12_800, markup: 10 }));
on("GET", "/admin/donate/games", () => GAMES.map((g, i) => ({ slug: g.slug, name: g.name, logo: null, category: "", is_active: true, featured_slot: g.slot, popular: !g.slot, sort: i, packages: PKGS.filter((p) => p.game === g.slug).length, provider_id: null })));
on("PUT", "/admin/donate/games/:slug", () => ({ ok: true }));
on("POST", "/admin/donate/providers/:id/test", () => ({ ok: true, ms: 180, balance_usd: "42.10", title: "VAYNEXO" }));
on("POST", "/admin/donate/providers/:id/sync", () => ({ games: 12, packages: 140, new_games: [] }));
on("POST", "/admin/donate/reprice", () => ({ changed: 0 }));
on("GET", "/admin/donate/provider", () => ({ mode: "manual", live: false, yupay: false, url_set: false, host: null, key_set: false, webhook_url: "https://vaynexo.example/api/yupay/webhook", low_balance_usd: 20 }));
on("POST", "/admin/donate/provider/test", () => ({ ok: false, error: "Provayder ulanmagan (demo)" }));
on("GET", "/admin/donate/yupay/skus", () => []);
on("GET", "/admin/p2p/sms-setup", () => ({ url: "https://vaynexo.example/api/p2p/incoming", url_with_key: "https://vaynexo.example/api/p2p/incoming?key=DEMO-KEY", secret: "DEMO-KEY", header: "X-P2P-Secret", ready: true, body_template: '{"text": "%text%", "from": "%from%", "id": "%sentStamp%"}', last_sms_at: null, last_sms_amount: null, last_24h: {} }));
const adminCards: Json[] = DEMO_CARDS.map((c) => ({ ...c, active: true, sort: 0 }));
on("GET", "/admin/p2p-cards", () => adminCards);
on("POST", "/admin/p2p-cards", (_m, b) => { const n = String(b.number).replace(/(\d{4})(?=\d)/g, "$1 "); const c = { id: nid(), number: n, holder: b.holder, kind: n.startsWith("9860") ? "Humo" : "Uzcard", active: true, sort: 0 }; adminCards.push(c); return c; });
on("PUT", "/admin/p2p-cards/:id", (m, b) => { const c = adminCards.find((x) => x.id === +m[1])!; c.active = b.active; return c; });
on("DELETE", "/admin/p2p-cards/:id", (m) => { adminCards.splice(adminCards.findIndex((x) => x.id === +m[1]), 1); return {}; });
on("GET", "/wallet/topup/:id", (m) => topupView(state.topups.find((t: Json) => t.id === +m[1])));
on("POST", "/wallet/topup/:id/cancel", (m) => {
  const t = state.topups.find((x: Json) => x.id === +m[1]);
  if (t?.status === "pending") t.status = "cancelled";
  return { ok: true };
});
on("POST", "/wallet/withdraw", (_m, b) => {
  if (state.withdrawals.some((w: Json) => w.user_id === ME && w.status === "pending")) throw new MockError("bad_state", "Oldingi so'rovingiz hali ko'rib chiqilmoqda", 409);
  money(-b.amount, "withdraw");
  const saved = b.card_id ? cards.find((c) => c.id === b.card_id) : null;
  const w = { id: nid(), user_id: ME, amount: b.amount, card: saved ? "000000000000" + saved.last4 : b.card_number, card_holder: saved ? saved.holder : b.card_holder, status: "pending", admin_note: null, created_at: now() };
  state.withdrawals.unshift(w);
  return { ...w, card: "•••• " + w.card.slice(-4) };
});
on("GET", "/wallet/withdrawals", () => state.withdrawals.filter((w: Json) => w.user_id === ME).map((w: Json) => ({ ...w, card: "•••• " + w.card.slice(-4) })));

// donat
const ML_FIELDS = [{ key: "player_id", label: "User ID", placeholder: "12345678", pattern: "^\\d{5,20}$" }, { key: "server_id", label: "Zone ID", placeholder: "1234", pattern: "^\\d{1,10}$" }];
const GAMES: Json[] = [
  { slug: "ML", name: "Mobile Legends", logo: null, hero: null, category: "", fields: ML_FIELDS, available: true, slot: 1 },
  { slug: "pubg-mobile", name: "PUBG Mobile", logo: null, hero: null, category: "", fields: [], available: true, slot: 2 },
  { slug: "steam", name: "Steam", logo: null, hero: null, category: "", fields: [{ key: "login", label: "Steam login", placeholder: "login", pattern: "" }], available: false, slot: 3 },
  ...["Free Fire", "Standoff 2", "Delta Force", "Genshin Impact", "Roblox", "Honor of Kings", "Blood Strike", "Arena Breakout"].map((n) => ({ slug: n.toLowerCase().replace(/ /g, "-"), name: n, logo: null, hero: null, category: "", fields: [], available: n === "Free Fire", slot: null })),
];
PKGS.push(
  { id: 9001, game: "pubg-mobile", name: "60 UC", diamonds: 0, bonus: 0, price: 12_900, is_hot: false, is_active: true, sku: "u60", sort: 0 },
  { id: 9002, game: "pubg-mobile", name: "325 UC", diamonds: 0, bonus: 0, price: 64_900, is_hot: true, is_active: true, sku: "u325", sort: 1 },
  { id: 9003, game: "free-fire", name: "110 Diamonds", diamonds: 0, bonus: 0, price: 12_900, is_hot: false, is_active: true, sku: "f110", sort: 0 },
);
on("GET", "/donate/games", () => ({ featured: GAMES.filter((g) => g.slot), popular: GAMES.filter((g) => !g.slot), all: GAMES }));
on("GET", "/donate/games/:slug", (m) => GAMES.find((g) => g.slug === decodeURIComponent(m[1])) ?? (() => { throw new MockError("not_found", "O'yin topilmadi", 404); })());
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
on("GET", "/tg/catalog", catalog);
on("GET", "/tg/orders", () => state.tg.filter((o: Json) => o.user_id === ME));
on("GET", "/tg/orders/:id", (m) => state.tg.find((o: Json) => o.id === +m[1]));
on("POST", "/tg/orders", (_m, b) => {
  const target = b.for_self ? "@" + state.me.username : "@" + String(b.target_username).replace(/^@/, "");
  if (!/^@[A-Za-z][A-Za-z0-9_]{3,31}$/.test(target)) throw new MockError("bad_username", "Telegram username noto'g'ri (masalan: @username)");
  let title = "", price = 0;
  const C = catalog();
  if (b.kind === "premium") { price = C.premium.find((p) => p.months === b.months)!.price; title = `Telegram Premium · ${b.months} oy`; }
  if (b.kind === "stars") { if (!(b.stars >= 50)) throw new MockError("bad_stars", "Stars soni 50 dan kam bo'lmasin"); price = Math.ceil(b.stars * C.stars.rate); title = `Telegram Stars · ${fmt(b.stars)}`; }
  if (b.kind === "gift") { const g = C.gifts.find((x) => x.code === b.gift)!; price = +g.price; title = `Telegram Gift · ${g.name}`; }
  if (b.kind === "nft") { const n = C.nft.find((x) => x.code === b.nft)!; price = +n.price; title = `Telegram NFT · ${n.name}`; }
  money(-price, "tg_service");
  const o = { id: nid(), ref: "", kind: b.kind, title, target_username: target, details: {}, price, status: "processing", admin_note: null, user_id: ME, created_at: now() };
  o.ref = "VX-T" + o.id;
  state.tg.unshift(o);
  later(8000, () => { if (o.status === "processing") o.status = "done"; });
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
// yangi admin panel (demo)
const demoBot = { open: false, guests: [6440744232, 8475521896] };
on("GET", "/admin/dashboard", () => ({
  today: { sales: 1_870_000, yesterday: 1_670_000, profit: 172_400, orders: 24, new_users: 37, users: 1248 },
  providers: [{ id: 1, name: "API 1", kind: "yupay", is_active: true, balance_usd: "142.30", low: false, error: null },
    { id: 2, name: "API 2", kind: "fazercards", is_active: true, balance_usd: "8.20", low: true, error: null }],
  bot: { open: demoBot.open, guests: demoBot.guests.length, inline: true },
  queue: [
    ...state.withdrawals.filter((w: Json) => w.status === "pending").map((w: Json) => ({ kind: "withdraw", id: w.id, title: `Pul yechish · ${w.amount.toLocaleString("ru-RU").replace(/,/g, " ")} so'm`, amount: w.amount, sub: `Sardor · ${w.card.slice(0, 4)} •• ${w.card.slice(-4)}`, copy: w.card, at: w.created_at, actions: [["paid", "To'landi", "ok"], ["reject", "Rad etish", "no"]] })),
    ...state.tg.filter((o: Json) => o.status === "processing").map((o: Json) => ({ kind: "tg", id: o.id, title: `${o.title} → @${o.target_username.replace("@", "")}`, amount: o.price, sub: "aziz_demo · qo'lda bajariladi", at: o.created_at, actions: [["done", "Bajarildi", "ok"], ["refund", "Pulni qaytarish", "no"]] })),
    { kind: "donate", id: 901, title: "86 almaz · Mobile Legends", amount: 18_100, game: "ML", sub: "ID 84512937 (2051) · aziz_demo", error: "insufficient_deposit: API balansi yetmadi", at: ago(4), actions: [["retry", "Qayta", "y"], ["done", "Qo'lda bajarildi", "ok"], ["refund", "Qaytarish", "no"]] },
  ],
  links: [{ section: "moderation", label: "E'lonlar tekshiruvi", count: state.listings.filter((l: Json) => l.status === "moderation").length || 1 }],
  top_games: [{ game: "ML", name: "Mobile Legends", share: 64 }, { game: "pubg-mobile", name: "PUBG Mobile", share: 18 }, { game: "free-fire", name: "Free Fire", share: 9 }],
}));
on("POST", "/admin/queue/:kind/:id", (m, b) => {
  if (m[1] === "withdraw") { const w = state.withdrawals.find((x: Json) => x.id === +m[2]); if (w) w.status = b.action === "paid" ? "paid" : "rejected"; }
  if (m[1] === "tg") { const o = state.tg.find((x: Json) => x.id === +m[2]); if (o) o.status = b.action === "done" ? "done" : "refunded"; }
  return { ok: true };
});
on("POST", "/admin/bot/open", (_m, b) => { demoBot.open = !!b.open; return { open: demoBot.open }; });
on("GET", "/admin/bot/guests", () => demoBot.guests.map((id) => ({ id, name: id === 6440744232 ? "@aziz_demo" : "—", known: id === 6440744232 })));
on("POST", "/admin/bot/guests", (_m, b) => { demoBot.guests = b.add === false ? demoBot.guests.filter((x) => x !== b.id) : [...new Set([...demoBot.guests, b.id])]; return { ok: true, count: demoBot.guests.length }; });
const DEMO_ORDERS = [
  { kind: "donate", id: 901, ref: "VX-D901", title: "86 almaz · Mobile Legends", game: "ML", price: 18_100, sub: "ID 84512937 (2051) · user 1001", status: "review", label: "Tekshiruv", color: "r", error: "insufficient_deposit: API balansi yetmadi", provider: "API 1", at: ago(4), actions: [["retry", "Qayta", "y"], ["done", "Qo'lda bajarildi", "ok"], ["refund", "Qaytarish", "no"]] },
  { kind: "tg", id: 77, ref: "VX-T77", title: "Premium 1 oy → @dilshod_07", game: null, price: 54_000, sub: "user 1001 · API'da 1 oy yo'q", status: "processing", label: "Qo'lda", color: "r", error: null, provider: null, at: ago(25), actions: [["done", "Bajarildi", "ok"], ["refund", "Qaytarish", "no"]] },
  { kind: "donate", id: 900, ref: "VX-D900", title: "660 UC · PUBG Mobile", game: "pubg-mobile", price: 124_700, sub: "ID 5123986641 · user 1002", status: "done", label: "Yetkazildi", color: "g", error: null, provider: "API 2", at: ago(50), actions: [] },
];
on("GET", "/admin/orders", (_m, _b, q) => {
  const st = q.get("state") || "attention";
  const kind = q.get("kind") || "all";
  const pick = (o: Json) => (kind === "all" || o.kind === kind) && (q.get("q") ? true : st === "attention" ? ["review", "processing"].includes(o.status) : st === "processing" ? o.status === "processing" : o.status === st);
  return { items: DEMO_ORDERS.filter(pick), counts: { attention: 2, processing: 1 } };
});
const CAT = GAMES.map((g: Json, i: number) => ({ slug: g.slug, name: g.name, logo: null, is_active: true, sort: i * 10, featured_slot: g.slot, popular: !g.slot, provider_id: 1, provider: "API 1",
  packages: PKGS.filter((p) => p.game === g.slug).length || 6 + i, warning: g.slug === "standoff-2" ? "Faqat 1 paket" : null, providers: ["ML", "pubg-mobile"].includes(g.slug) ? 2 : 1,
  cheaper: g.slug === "ML" ? { provider_id: 2, provider: "API 2", pct: -20, linked: true, slug: "ML", pairs: 14 } : g.slug === "pubg-mobile" ? { provider_id: 2, provider: "API 2", pct: -14, linked: false, slug: "fz-pubg-mobile-auto", name: "PUBG Mobile (Auto)", pairs: 6 } : null }));
on("GET", "/admin/catalog/games", (_m, _b, q) => {
  const st = q.get("state") || "active";
  const items = st === "hidden" ? [{ ...CAT[0], slug: "fz-mobile-legends-ru", name: "Mobile Legends (RU)", is_active: false, provider: "API 2", cheaper: null, providers: 1 }] : st === "cheaper" ? CAT.filter((g) => g.cheaper) : CAT;
  return { items, counts: { active: CAT.length, hidden: 1152, cheaper: 2 }, rate: 12_800, markup: 10 };
});
on("PUT", "/admin/catalog/order", () => ({ ok: true }));
on("GET", "/admin/catalog/games/:slug", (m) => {
  const g = CAT.find((x) => x.slug === decodeURIComponent(m[1])) ?? CAT[0];
  const pk = PKGS.filter((p) => p.game === g.slug).map((p, i) => ({ id: p.id, name: p.name, diamonds: p.diamonds, bonus: p.bonus, price: p.price, cost_usd: (Number(p.price) / 14080).toFixed(2), profit: Math.round(Number(p.price) * 0.09), is_active: i !== 8, is_hot: p.is_hot, source: "api", delivery: "topup", group: p.diamonds ? "amount" : "pass", provider_id: 1 }));
  return { game: g, fields: [], view_provider_id: 1, rate: 12_800, packages: pk,
    providers: [{ provider_id: 1, provider: "API 1", current: true, linked: true, pct: 0, slug: g.slug }, ...(g.cheaper ? [{ ...g.cheaper, ref: { name: "86 Diamonds (78 + 8)", cur: "1.28", alt: "1.02" } }] : [])] };
});
on("GET", "/admin/catalog/games/:slug/candidates", () => [{ slug: "fz-mobile-legends-global", name: "Mobile Legends (Global)", provider: "API 2" }, { slug: "fz-mobile-legends-ru", name: "Mobile Legends (RU)", provider: "API 2" }]);
on("POST", "/admin/catalog/games/:slug/link", () => ({ ok: true }));
on("POST", "/admin/catalog/games/:slug/provider", () => ({ ok: true }));
on("PATCH", "/admin/catalog/packages/:id", () => ({ ok: true }));
const SPEC: [string, string, string, string, number, number, Json?][] = [
  ["referral_bonus", "money", "Taklif bonusi (so'm). 0 — o'chiq", "Referal", 0, 10_000_000],
  ["referral_min_topup", "money", "Bonus uchun do'stning eng kam to'ldirishi (so'm)", "Referal", 1000, 100_000_000],
  ["vip_price_per_day", "money", "VIP e'lon narxi (so'm / kun)", "Account savdo", 0, 10_000_000],
  ["rent_deposit_type", "choice", "Ijara depoziti turi", "Account ijara", 0, 0, [{ v: "percent", label: "Ijara narxidan foiz" }, { v: "fixed", label: "Aniq summa" }]],
  ["rent_deposit_percent", "percent", "Depozit: ijara narxining necha foizi (%)", "Account ijara", 0, 1000],
  ["rent_deposit_fixed", "money", "Depozit: aniq summa (so'm)", "Account ijara", 0, 100_000_000],
  ["rent_commission_percent", "percent", "Ijaradan platforma ulushi (%)", "Account ijara", 0, 90],
  ["boost_express_percent", "percent", "Express boost ustamasi (%)", "Boost", 0, 500],
  ["boost_hero_percent", "percent", "Qahramon tanlash ustamasi (%)", "Boost", 0, 500],
  ["boost_lane_percent", "percent", "Liniya tanlash ustamasi (%)", "Boost", 0, 500],
];
const TGG = "Telegram: Premium va Stars", PCT = { key: "tg_price_mode", value: "percent" }, FIX = { key: "tg_price_mode", value: "fixed" };
const SHOW: Record<string, Json> = { rent_deposit_percent: { key: "rent_deposit_type", value: "percent" }, rent_deposit_fixed: { key: "rent_deposit_type", value: "fixed" },
  tg_markup_percent: PCT, stars_cost: PCT, stars_price: FIX };
SPEC.push(["tg_price_mode", "choice", "Premium va Stars narxi qanday belgilanadi", TGG, 0, 0, [{ v: "fixed", label: "Aniq narx" }, { v: "percent", label: "Fragment tannarxi + foiz" }]]);
SPEC.push(["tg_markup_percent", "percent", "Ustama: Fragment tannarxiga necha foiz qo'shiladi (%)", TGG, 0, 500]);
SPEC.push(["stars_cost", "money", "Fragment tannarxi: 1 Star (so'm)", TGG, 1, 100000]);
SPEC.push(["stars_price", "money", "Sotuv narxi: 1 Star (so'm)", TGG, 1, 100000]);
for (const m of [1, 3, 6, 12]) {
  SPEC.push([`premium_cost_${m}`, "money", `Fragment tannarxi: Premium ${m} oy (so'm)`, TGG, 1, 1e8]); SHOW[`premium_cost_${m}`] = PCT;
  SPEC.push([`premium_price_${m}`, "money", `Sotuv narxi: Premium ${m} oy (so'm)`, TGG, 1, 1e8]); SHOW[`premium_price_${m}`] = FIX;
}
for (const [c, n] of GIFT_NAMES) SPEC.push([`gift_price_${c}`, "money", `Gift: ${n} (so'm)`, "Telegram: Gift va NFT", 1, 1e8]);
for (const [c, n] of NFT_NAMES) SPEC.push([`nft_price_${c}`, "money", `NFT: ${n} (so'm)`, "Telegram: Gift va NFT", 1, 1e8]);
const FEATS: [string, string][] = [["market", "Account savdo"], ["rent", "Account ijara"], ["boost", "Boost xizmati"], ["tg", "Telegram xizmatlar (Premium/Stars)"], ["arena", "Arena (turnir, reyting)"], ["partner", "Hamkor dasturi"], ["ai", "AI yordamchi"], ["top", "Top xaridorlar"]];
for (const [k, n] of FEATS) { SPEC.push([`feature_${k}`, "choice", n, "Bo'limlar (ilovada ko'rinishi)", 0, 0, [{ v: "on", label: "Yoqilgan" }, { v: "off", label: "O'chirilgan" }]]); state.settings[`feature_${k}`] = state.me.features[k] ? "on" : "off"; }
const settingsRows = () => SPEC.map(([key, kind, label, group, min, max, choices]) => ({ key, kind, label, group, min, max, choices: choices ?? [], value: state.settings[key], show_if: SHOW[key] ?? null }));
on("GET", "/admin/settings", settingsRows);
on("PUT", "/admin/settings", (_m, b) => {
  if (typeof b.value === "number" && !(b.value >= 0)) throw new MockError("bad_setting", "Qiymat 0 dan kam bo'lmasin");
  state.settings[b.key] = b.value;
  if (String(b.key).startsWith("feature_")) state.me.features[String(b.key).slice(8)] = b.value === "on";
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

// ---------------------------------------------------------------- ijara
const HOURS: Record<number, string> = { 12: "12 soat", 24: "24 soat", 72: "3 kun", 168: "1 hafta" };
const rentListings: Json[] = [
  { id: 201, collection_level: "World Collector", owner_id: 2001, game: "ML", title: "Mythic Glory · 210 skin", rank: "Mythic Glory", server: "Asia", skins: 210, heroes: 118, price_per_hour: 8000, description: "Kuchli akkaunt, reytingli o'yinlar uchun.", media: [], status: "active", busy_until: null, created_at: ago(500) },
  { id: 202, collection_level: "Mega Collector", owner_id: 2002, game: "ML", title: "Mythic · 120 skin", rank: "Mythic", server: "Asia", skins: 120, heroes: 85, price_per_hour: 5000, description: "Toza akkaunt.", media: [], status: "active", busy_until: null, created_at: ago(900) },
  { id: 203, collection_level: "Exalted Collector", owner_id: 2001, game: "MC", title: "Magic Chess · Master", rank: "Mythic", server: "Asia", skins: 25, heroes: 0, price_per_hour: 3000, description: "", media: [], status: "active", busy_until: new Date(Date.now() + 42 * 60000).toISOString(), created_at: ago(1500) },
  { id: 204, collection_level: "Renowned Collector", owner_id: 2002, game: "ML", title: "Legend · 41 skin", rank: "Legend", server: "Asia", skins: 41, heroes: 60, price_per_hour: 3500, description: "", media: [], status: "active", busy_until: null, created_at: ago(2000) },
  { id: 205, collection_level: "Mega Collector", owner_id: ME, game: "ML", title: "Mening Mythic akkauntim", rank: "Mythic", server: "Asia", skins: 98, heroes: 80, price_per_hour: 6000, description: "", media: [], status: "active", busy_until: null, created_at: ago(3000) },
];
const rentals: Json[] = [
  { id: 301, listing_id: 205, renter_id: 2002, owner_id: ME, hours: 12, price: 72_000, deposit: 72_000, commission: 7_200, status: "ended",
    starts_at: ago(13 * 60), ends_at: ago(60), review_until: new Date(Date.now() + 23 * 3600000).toISOString(), dispute_by: null, dispute_reason: null, resolution: null },
];
const rl = (id: number) => { const x = rentListings.find((l) => l.id === id); if (!x) throw new MockError("not_found", "E'lon topilmadi", 404); return x; };
const rcard = (x: Json) => ({ ...x, cover: null, reject_reason: null, owner_rating: sellers[x.owner_id]?.rating ?? null,
  busy_until: x.busy_until && Date.parse(x.busy_until) > Date.now() ? x.busy_until : null });
const rview = (r: Json) => ({ ...r, listing: rcard(rl(r.listing_id)), duration: HOURS[r.hours], role: r.renter_id === ME ? "renter" : "owner",
  credentials: r.renter_id === ME && r.status === "active" ? "Moonton: rent.demo@gmail.com\nParol: Ijara-Demo-2026\n(namuna)" : null });
const RDISC: Record<number, number> = { 12: 0, 24: 10, 72: 20, 168: 30 };
const rentCfg = () => ({ durations: Object.entries(HOURS).map(([h, label]) => ({ hours: +h, label, discount: RDISC[+h] ?? 0 })), ...Object.fromEntries(
  ["rent_deposit_type", "rent_deposit_percent", "rent_deposit_fixed", "rent_commission_percent"].map((k) => [k, state.settings[k]])) });
on("GET", "/rent/config", rentCfg);
on("GET", "/rent/listings", (_m, _b, q) => {
  const lvl = q.get("level");
  const isFree = (x: Json) => !x.busy_until || Date.parse(x.busy_until) <= Date.now();
  let ls = rentListings.filter((x) => x.status === "active");
  const all = ls;
  if (q.get("free")) ls = ls.filter(isFree);
  if (q.get("rank")) ls = ls.filter((x) => x.rank.startsWith(q.get("rank")!));
  if (q.get("max_price")) ls = ls.filter((x) => x.price_per_hour <= +q.get("max_price")!);
  if (lvl) ls = ls.filter((x) => (x.collection_level || "").startsWith(lvl));
  const sort = q.get("sort");
  ls = [...ls].sort((a, b) => (isFree(a) ? 0 : 1) - (isFree(b) ? 0 : 1) || (sort === "expensive" ? b.price_per_hour - a.price_per_hour : sort === "new" ? b.id - a.id : sort === "skins" ? b.skins - a.skins : a.price_per_hour - b.price_per_hour));
  return { items: ls.map(rcard), has_more: false, total: ls.length, free: all.filter(isFree).length };
});
on("GET", "/rent/listings/:id", (m) => { const x = rl(+m[1]); return { ...rcard(x), owner: sellers[x.owner_id], is_mine: x.owner_id === ME }; });
on("POST", "/rent/listings", (_m, b) => { const x = { id: nid(), owner_id: ME, ...b, status: "moderation", busy_until: null, created_at: now() }; delete x.credentials; rentListings.unshift(x); return rcard(x); });
on("PUT", "/rent/listings/:id", (m, b) => { const x = rl(+m[1]); Object.assign(x, b, { status: "moderation" }); delete x.credentials; return rcard(x); });
on("POST", "/rent/listings/:id/close", (m) => { const x = rl(+m[1]); x.status = "closed"; return rcard(x); });
on("GET", "/my/rent-listings", () => rentListings.filter((x) => x.owner_id === ME).map(rcard));
on("POST", "/rent/listings/:id/rent", (m, b) => {
  const x = rl(+m[1]);
  if (x.owner_id === ME) throw new MockError("own_listing", "O'z akkauntingizni ijaraga ololmaysiz");
  if (x.busy_until && Date.parse(x.busy_until) > Date.now()) throw new MockError("bad_state", "Akkaunt hozir band", 409);
  const S = state.settings;
  const price = x.price_per_hour * b.hours;
  const deposit = S.rent_deposit_type === "fixed" ? S.rent_deposit_fixed : Math.floor((price * S.rent_deposit_percent) / 100);
  money(-(price + deposit), "rent_pay", `Ijara ${HOURS[b.hours]} + depozit`);
  const r = { id: nid(), listing_id: x.id, renter_id: ME, owner_id: x.owner_id, hours: b.hours, price, deposit, commission: Math.floor((price * S.rent_commission_percent) / 100),
    status: "active", starts_at: now(), ends_at: new Date(Date.now() + b.hours * 3600000).toISOString(), review_until: null, dispute_by: null, dispute_reason: null, resolution: null };
  x.busy_until = r.ends_at;
  rentals.unshift(r);
  return rview(r);
});
on("GET", "/rentals", (_m, _b, q) => rentals.filter((r) => (q.get("role") === "owner" ? r.owner_id : r.renter_id) === ME).map(rview));
on("GET", "/rentals/:id", (m) => rview(rentals.find((r) => r.id === +m[1])));
on("POST", "/rentals/:id/confirm", (m) => {
  const r = rentals.find((x) => x.id === +m[1]);
  if (r.status !== "ended") throw new MockError("bad_state", "Ijara muddati hali tugamagan", 409);
  r.status = "completed";
  money(r.price - r.commission, "rent_payout");
  rl(r.listing_id).busy_until = null;
  return rview(r);
});
on("POST", "/rentals/:id/dispute", (m, b) => {
  const r = rentals.find((x) => x.id === +m[1]);
  r.status = "disputed"; r.dispute_by = r.owner_id === ME ? "owner" : "renter"; r.dispute_reason = b.reason;
  return rview(r);
});
on("GET", "/admin/rent/listings", () => rentListings.filter((x) => x.status === "moderation").map((x) => ({ ...rcard(x), owner: sellers[x.owner_id] })));
on("POST", "/admin/rent/listings/:id/moderate", (m, b) => { const x = rl(+m[1]); x.status = b.approve ? "active" : "rejected"; return rcard(x); });
on("GET", "/admin/rentals", () => rentals.filter((r) => r.status === "disputed").map((r) => ({ ...rview(r), credentials: "Moonton: rent.demo@gmail.com" })));
on("POST", "/admin/rentals/:id/resolve", (m, b) => { const r = rentals.find((x) => x.id === +m[1]); r.status = b.decision === "renter" ? "refunded" : "completed"; r.resolution = b.note; return rview(r); });

// ---------------------------------------------------------------- sozlamalar: KYC, PIN, kartalar, yordam
const cards: Json[] = [{ id: 1, last4: "4821", brand: "Humo", holder: "AZIZ DEMO", expiry: "12/27", is_default: true }];
let demoPin: string | null = null;
on("POST", "/me/kyc", () => { state.me.kyc_status = "pending"; setTimeout(() => { state.me.kyc_status = "verified"; }, 8000); return { kyc_status: "pending" }; });
on("POST", "/me/pin", (_m, b) => {
  if (!/^\d{4}$/.test(b.pin)) throw new MockError("bad_pin", "PIN 4 ta raqamdan iborat bo'lsin");
  if (new Set(b.pin).size === 1 || b.pin === "1234") throw new MockError("weak_pin", "Juda oson PIN. Boshqa raqamlar tanlang");
  if (demoPin && b.old_pin !== demoPin) throw new MockError("wrong_pin", "Joriy PIN noto'g'ri", 403);
  demoPin = b.pin; state.me.pin_set = true; state.me.bio_set = false;
  return { pin_set: true, token: `${ME}.1.${Math.floor(Date.now() / 1000) + 43200}.demo` };
});
const checkPin = (pin: string) => { if (pin !== demoPin) throw new MockError("wrong_pin", "PIN noto'g'ri", 403); };
on("POST", "/me/pin/verify", (_m, b) => { checkPin(b.pin); return { token: `${ME}.1.${Math.floor(Date.now() / 1000) + 43200}.demo` }; });
on("POST", "/me/pin/remove", (_m, b) => { checkPin(b.pin); demoPin = null; state.me.pin_set = false; state.me.bio_set = false; return {}; });
on("POST", "/me/pin/bio", (_m, b) => { checkPin(b.pin); state.me.bio_set = true; return { key: "demo" }; });
on("POST", "/me/pin/bio/off", () => { state.me.bio_set = false; return {}; });
on("GET", "/me/cards", () => cards);
on("POST", "/me/cards", (_m, b) => {
  const n = String(b.number);
  const brand = n.startsWith("9860") ? "Humo" : n.startsWith("4") ? "Visa" : n.startsWith("5") && !n.startsWith("5614") ? "Mastercard" : "Uzcard";
  const c = { id: nid(), last4: n.slice(-4), brand, holder: b.holder || "", expiry: b.expiry || "", is_default: cards.length === 0 };
  cards.push(c);
  return c;
});
on("POST", "/me/cards/:id/default", (m) => { cards.forEach((c) => (c.is_default = c.id === +m[1])); return {}; });
on("DELETE", "/me/cards/:id", (m) => {
  const i = cards.findIndex((c) => c.id === +m[1]);
  const wasDef = cards[i]?.is_default;
  cards.splice(i, 1);
  if (wasDef && cards[0]) cards[0].is_default = true;
  return {};
});
on("POST", "/support", () => ({ ok: true }));
// ---------------------------------------------------------------- Arena va Hamkor (demo)
const arenaMatch: Json = { id: 1, title: "Noyabr kubogi · yarim final", team_a: "Samarqand Lions", team_b: "Tashkent Wolves",
  starts_at: new Date(Date.now() + 2 * 3600000).toISOString(), status: "open", result: null, my_pick: null, points: 50 };
const missionsState: Json = {
  daily: [
    { key: "login", title: "Ilovaga kirish", goal: 1, progress: 1, claimed: false, reward: 10 },
    { key: "join_tournament", title: "1 ta turnirga yozilish", goal: 1, progress: 0, claimed: false, reward: 20 },
    { key: "invite", title: "Do'stni taklif qilish", goal: 1, progress: 0, claimed: false, reward: 50 },
  ],
  weekly: [
    { key: "play_3", title: "3 ta turnirda qatnashish", goal: 3, progress: 1, claimed: false, reward: 100 },
    { key: "partner_video", title: "Hamkor videosi yuborish", goal: 1, progress: 0, claimed: false, reward: 50 },
    { key: "any_service", title: "Istalgan xizmatdan foydalanish", goal: 1, progress: 1, claimed: false, reward: 30 },
  ],
};
const EXCH = [{ key: "boost_discount", title: "Boost'ga 5% chegirma", cost: 500 }, { key: "vip_3d", title: "VIP e'lon · 3 kun", cost: 1000 }, { key: "free_tournament", title: "Turnirga bepul kirish", cost: 1500 }];
const teamPosts: Json[] = [
  { id: 1, kind: "player", name: "aziz_gg", lane: "Gold", rank: "Mythic 34★", online: "20:00–24:00", note: "Kechqurun onlayn", mine: false },
  { id: 2, kind: "player", name: "dilshod_jg", lane: "Jungle", rank: "Mythic Glory", online: "kun bo'yi", note: "", mine: false },
  { id: 3, kind: "team", name: "Team Nova", lane: "Roam", rank: "Mythic 4/5", online: "", note: "Roam kerak", mine: false },
  { id: 4, kind: "player", name: "sardor_ml", lane: "Mid", rank: "Legend I", online: "dam olish kunlari", note: "", mine: false },
];
const ptsRules = { pts_tournament_win: 100, pts_tournament_join: 20, pts_prediction: 50 };
on("GET", "/arena/summary", () => ({ points: state.me.points, passes: state.me.tournament_passes, vip_credit_days: state.me.vip_credit_days,
  boost_coupon_percent: state.me.boost_coupon_percent, prediction: arenaMatch, points_rules: ptsRules }));
on("GET", "/arena/missions", () => ({ ...missionsState, exchange: EXCH, points: state.me.points }));
on("POST", "/arena/missions/:key/claim", (m) => {
  const x = [...missionsState.daily, ...missionsState.weekly].find((i: Json) => i.key === m[1]);
  if (!x || x.progress < x.goal) throw new MockError("bad_state", "Vazifa hali bajarilmagan", 409);
  x.claimed = true; state.me.points += x.reward;
  return { reward: x.reward, points: state.me.points };
});
on("POST", "/arena/exchange/:key", (m) => {
  const x = EXCH.find((e) => e.key === m[1])!;
  if (state.me.points < x.cost) throw new MockError("no_points", "Ball yetarli emas");
  state.me.points -= x.cost;
  if (x.key === "free_tournament") state.me.tournament_passes += 1;
  if (x.key === "vip_3d") state.me.vip_credit_days += 3;
  if (x.key === "boost_discount") state.me.boost_coupon_percent = 5;
  return { points: state.me.points, passes: state.me.tournament_passes, vip_credit_days: state.me.vip_credit_days, boost_coupon_percent: state.me.boost_coupon_percent };
});
on("GET", "/arena/leaderboard", () => {
  const names = ["Team Phoenix", "dilshod_jg", "Samarqand Lions", "aziz_gold", "Team Nova", "sardor_ml", "Umid_7"];
  const items = names.map((n, i) => ({ place: i + 1, user_id: 4000 + i, name: n, points: 4_820 - i * 420 }));
  return { season: { number: 1, days_left: 19 }, items, me: { place: 47, user_id: ME, name: "", points: state.me.points }, week: 180 };
});
on("POST", "/arena/predictions/:id", (_m, b) => { arenaMatch.my_pick = b.pick; return arenaMatch; });
on("GET", "/arena/team-posts", (_m, _b, q) => teamPosts.filter((p) => !q.get("lane") || p.lane === q.get("lane")));
on("POST", "/arena/team-posts", (_m, b) => { const p = { id: nid(), ...b, mine: true }; teamPosts.unshift(p); return p; });
on("POST", "/arena/team-posts/:id/close", (m) => { const i = teamPosts.findIndex((p) => p.id === +m[1]); teamPosts.splice(i, 1); return {}; });
on("POST", "/arena/team-posts/:id/contact", () => ({ ok: true }));
const mlProfile: Json = { nick: "", lane: "", rank: "", heroes: [], ml_id: "" };
on("GET", "/arena/profile", () => mlProfile);
on("PUT", "/arena/profile", (_m, b) => Object.assign(mlProfile, b));
const QUIZ = [[109, "Aamon", ["Aamon", "Alucard", "Fanny", "Gusion"]], [4, "Alice", ["Lunox", "Alice", "Eudora", "Aurora"]], [9, "Akai", ["Akai", "Tigreal", "Franco", "Minotaur"]]] as const;
const quizAns: Record<number, boolean> = {};
on("GET", "/arena/quiz", () => ({ day: "demo", points_each: 10, score: Object.values(quizAns).filter(Boolean).length, done: Object.keys(quizAns).length === 4, roles: {},
  questions: [...QUIZ.map(([h, a, o], n) => ({ n, type: "who", options: o, image: `/mlbb/heroes/${h}.webp`, answered: n in quizAns, correct: quizAns[n] ?? null, ...(n in quizAns ? { answer: a, hero: h } : {}) })),
    { n: 3, type: "role", name: "Miya", options: ["tank", "fighter", "assassin", "mage", "marksman", "support"], image: "/mlbb/heroes/1.webp", answered: 3 in quizAns, correct: quizAns[3] ?? null }] }));
on("POST", "/arena/quiz/:n", (m, b) => {
  const n = +m[1]; const a = n < 3 ? QUIZ[n][1] : "marksman"; quizAns[n] = String(b.answer).toLowerCase() === a.toLowerCase();
  if (quizAns[n]) state.me.points += 10;
  return { correct: quizAns[n], answer: a, hero: n < 3 ? QUIZ[n][0] : 1, points: quizAns[n] ? 10 : 0 };
});
const votes: Json = { week: "demo", total: 41, my: null, points: 5, last_winner: 106, top: [{ hero: 109, votes: 14, pct: 34 }, { hero: 106, votes: 11, pct: 27 }, { hero: 4, votes: 9, pct: 22 }, { hero: 9, votes: 7, pct: 17 }] };
on("GET", "/arena/hero-vote", () => votes);
on("POST", "/arena/hero-vote", (_m, b) => { votes.my = b.hero_id; votes.total += 1; state.me.points += 5; return { ...votes, earned: 5 }; });
const REGIONS = ["Toshkent sh.", "Toshkent vil.", "Andijon", "Buxoro", "Farg'ona", "Jizzax", "Xorazm", "Namangan", "Navoiy", "Qashqadaryo", "Qoraqalpog'iston", "Samarqand", "Sirdaryo", "Surxondaryo"];
const demoTeams: Json[] = [
  { id: 1, name: "Xorazm guch", tag: "XRZ", region: "Xorazm", about: "", is_open: true, captain: "dilshod_jg", captain_id: 4001, members: 6, max: 7, free: 1, avg_rank: "glory" },
  { id: 2, name: "ORCA eSports", tag: "ORC", region: "Toshkent sh.", about: "", is_open: true, captain: "Hirota", captain_id: 4002, members: 6, max: 7, free: 1, avg_rank: "mythic" },
];
const mkAuthor = (n: string, rank: string, lane: string) => ({ user_id: 4100, nick: n, rank, lane, heroes: [109, 4], region: "Samarqand", verified: true });
const searchPosts: Json[] = [
  { id: 1, kind: "duo", name: "aziz_gold", lane: "Gold", rank: "mythic", online: "21:00–01:00", note: "Mythic push, mikrofon bor", heroes: [109, 4], region: "Samarqand", mine: false, author: mkAuthor("aziz_gold", "mythic", "gold"), respect: { good: 9, bad: 1, pct: 90, toxic: false } },
  { id: 2, kind: "team", name: "Xorazm guch", lane: "Roam", rank: "glory", online: "20:00–24:00", note: "Roam kerak", heroes: [], region: "Xorazm", mine: false, author: mkAuthor("dilshod_jg", "glory", "jungle"), respect: null, team: demoTeams[0] },
  { id: 3, kind: "scrim", name: "ORCA eSports", lane: "", rank: "mythic", online: "Shanba 20:00", note: "BO3", heroes: [], region: "Toshkent sh.", mine: false, author: mkAuthor("Hirota", "mythic", "exp"), respect: null, team: demoTeams[1] },
];
on("GET", "/arena/search/meta", () => ({ regions: REGIONS, signal: false, my_rank: mlProfile.rank, my_region: "", team_max: 7 }));
on("GET", "/arena/posts", (_m, _b, q) => searchPosts.filter((p) => p.kind === q.get("kind")));
on("POST", "/arena/posts", (_m, b) => { const p = { id: nid(), ...b, name: "Siz", rank: mlProfile.rank, heroes: b.heroes ?? [], mine: true, author: null, respect: null }; searchPosts.unshift(p); return p; });
on("POST", "/arena/posts/:id/respond", () => ({ ok: true, text: "Xabar yuborildi" }));
on("POST", "/arena/posts/:id/close", (m) => { const i = searchPosts.findIndex((p) => p.id === +m[1]); searchPosts.splice(i, 1); return { ok: true }; });
on("GET", "/arena/teams", () => demoTeams);
on("GET", "/arena/teams/my", () => ({ team: null, requests: [], invites: [] }));
on("GET", "/arena/teams/:id", (m) => ({ ...demoTeams.find((t) => t.id === +m[1]), roster: [{ ...mkAuthor("dilshod_jg", "glory", "jungle"), role: "captain", respect: null }], is_member: false, is_captain: false, my_request: null }));
on("POST", "/arena/teams/:id/join", () => ({ ok: true }));
on("GET", "/arena/contacts", () => []);
on("POST", "/arena/signal", (_m, b) => ({ signal: b.enabled }));
const partnerVideos: Json[] = [
  { id: 1, platform: "tiktok", url: "https://tiktok.com/@aziz_edits/video/7431", status: "approved", views: 12_400, likes: 900, tier: 2, reward: "Turnirlarga bepul kirish · 1 oy", note: null, created_at: ago(20000) },
  { id: 2, platform: "instagram", url: "https://instagram.com/reel/C9xQ", status: "pending", views: 0, likes: 0, tier: 0, reward: "", note: null, created_at: ago(3000) },
];
const PTIERS = [[3000, "VIP e'lon · 3 kun"], [10000, "Turnirlarga bepul kirish · 1 oy"], [25000, "Olmos paketi"], [50000, "«Rasmiy hamkor» nishoni + 1 oy xizmat haqisiz"]] as const;
on("GET", "/partner", () => {
  const views = partnerVideos.filter((v) => v.status === "approved").reduce((a, v) => a + v.views, 0);
  const best = Math.max(0, ...partnerVideos.filter((v) => v.status === "approved").map((v) => v.tier));
  return { tiers: PTIERS.map(([v, r], i) => ({ tier: i + 1, views: v, reward: r, done: i + 1 <= best })), videos: partnerVideos,
    stats: { sent: partnerVideos.length, views, pending: partnerVideos.filter((v) => v.status === "pending").length, to_official: Math.max(0, 50000 - views) },
    rules: { min_views: 3000, count_days: 10, interval_days: 2, like_ratio: 3 },
    code: null, code_terms: { bonus: 3000, points: 50, need_videos: 1, approved: 1 },
    leaderboard: [{ place: 1, name: "aziz_edits", views: 48_200, official: false }, { place: 2, name: "ml_uz_clips", views: 21_900, official: false }],
    ideas: [{ title: "Donat 1 daqiqada", text: "Ekranni yozib, VAYNEXO'da ML almaz olishni boshidan oxirigacha ko'rsating." }], hashtags: "#vaynexo #vaynexobot #mlbb #mobilelegends" };
});
on("POST", "/partner/videos", (_m, b) => {
  const url = String(b.url);
  const platform = /tiktok/.test(url) ? "tiktok" : /instagram/.test(url) ? "instagram" : /youtu/.test(url) ? "youtube" : null;
  if (!platform) throw new MockError("bad_url", "Faqat TikTok, Instagram yoki YouTube havolasi qabul qilinadi");
  if (partnerVideos.some((v) => Date.now() - Date.parse(v.created_at) < 2 * 86400000)) throw new MockError("bad_state", "2 kunda 1 ta video yuborish mumkin", 409);
  const v = { id: nid(), platform, url, status: "pending", views: 0, likes: 0, tier: 0, reward: "", note: null, created_at: now() };
  partnerVideos.unshift(v);
  return v;
});
on("GET", "/admin/partner/videos", () => partnerVideos.filter((v) => v.status === "pending").map((v) => ({ ...v, user_id: ME })));
on("POST", "/admin/partner/videos/:id", (m, b) => { const v = partnerVideos.find((x) => x.id === +m[1])!; v.status = b.approve ? "approved" : "rejected"; v.views = b.views; v.tier = b.views >= 10000 ? 2 : 1; return v; });
on("GET", "/admin/arena/matches", () => [arenaMatch]);
on("POST", "/admin/arena/matches", (_m, b) => ({ id: nid(), ...b, status: "open", result: null }));
on("POST", "/admin/arena/matches/:id/settle", (_m, b) => { arenaMatch.status = "settled"; arenaMatch.result = b.result; return { winners: 12 }; });
on("GET", "/admin/kyc", () => []);
let aiLeft = 15;
on("GET", "/ai/status", () => ({ enabled: true, limit: 15, left: aiLeft }));
on("POST", "/ai/ask", (_m, b) => {
  aiLeft = Math.max(0, aiLeft - 1);
  const q = String(b.text).toLowerCase();
  if (/mythic|legend|epic|skin|akkaunt|аккаунт|account/.test(q)) {
    const items = state.listings.filter((x: Json) => x.status === "active").sort((a: Json, c: Json) => c.skins - a.skins).slice(0, 3);
    return { reply: "Talablaringizga mos e'lonlar topdim. Eng yaxshisi birinchi o'rinda:", listings: items.map(card), left: aiLeft };
  }
  if (/to'ldir|пополн|top up/.test(q)) return { reply: "Hamyon → To'ldirish. Summani kiriting, tizim bergan ANIQ summani kartaga o'tkazing — 1–3 daqiqada balansga tushadi.", listings: [], left: aiLeft };
  return { reply: "Demo rejimda AI cheklangan. Haqiqiy botda Claude savolingizga to'liq javob beradi.", listings: [], left: aiLeft };
});
on("POST", "/ai/describe", (_m, b) => ({ title: `${b.rank || "Mythic"} akkaunt · ${b.skins || 0} skin`, description: `${b.rank || "Mythic"} rankdagi akkaunt, ${b.skins || 0} ta skin va ${b.heroes || 0} ta qahramon. Akkaunt toza, faqat bitta egada bo'lgan.`, left: --aiLeft }));

// ---------------------------------------------------------------- Premium bo'limlar (demo)
const LV4 = [["🥉", "Bronza", 3, 0], ["🥈", "Kumush", 4, 5_000_000], ["🥇", "Oltin", 5, 20_000_000], ["💎", "Brilliant", 6, 50_000_000]] as const;
state.me.plus = false; state.me.vay = { xp: 620, name: "Jangchi", icon: "⚔️", level: 2 };
const DEMO_QR = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 29 29" shape-rendering="crispEdges"><rect width="29" height="29" fill="#fff"/><path fill="#111" d="M2 2h7v7H2zM20 2h7v7h-7zM2 20h7v7H2zM11 2h2v2h-2zM14 5h3v2h-3zM11 9h4v2h-4zM17 11h3v3h-3zM11 14h2v3h-2zM15 16h3v2h-3zM20 14h5v2h-5zM12 20h3v3h-3zM17 21h4v2h-4zM22 19h3v3h-3zM11 25h5v2h-5zM22 25h3v2h-3z"/></svg>`;
const demo: Json = {
  shop: null as Json, plus: null as Json, savings: [] as Json[], streamer: null as Json, proProfile: null as Json,
  plusAuto: null as Json,
  slots: [
    { id: 1, title: "Men bilan 1 ta ranked o'yin (Mythic)", details: "Ovozli chat, efirda ko'rsataman", play_at: new Date(Date.now() + 2 * 86400000).toISOString(), ends_at: new Date(Date.now() + 5 * 3600000).toISOString(), min_bid: 50_000, step: 5_000, price: 85_000, bids: 6, status: "open", next_bid: 90_000, pro: { id: 3001, name: "Aziz Pro", rank: "Mythical Immortal 180★", bio: "MPL UZ ishtirokchisi, Gold lane", link: "https://t.me/azizpro" }, mine: false, winner: false, leading: false },
    { id: 2, title: "Duo: Mythic Glory yo'lida", details: "", play_at: new Date(Date.now() + 3 * 86400000).toISOString(), ends_at: new Date(Date.now() + 26 * 3600000).toISOString(), min_bid: 30_000, step: 5_000, price: 0, bids: 0, status: "open", next_bid: 30_000, pro: { id: 3002, name: "Dilshod TV", rank: "Mythic Glory", bio: "Striminer, 12K obunachi", link: "" }, mine: false, winner: false, leading: false },
  ] as Json[],
};
const plusView = () => {
  const p = demo.plus;
  return { enabled: true, price: 39_000, cashback: 3, active: !!p, until: p?.until ?? null, days_left: p ? 30 : 0, months: p ? 1 : 0, auto_renew: true, cashback_total: p ? 1_110 : 0,
    auto: demo.plusAuto };
};
const savingsView = () => ({ enabled: true, bonus_pct: 3, min_days: 14, items: demo.savings, total_saved: demo.savings.filter((x: Json) => x.status === "active").reduce((a: number, x: Json) => a + x.saved, 0) });
const shopView = () => {
  const sh = demo.shop;
  const lv = { level: 1, key: "bronze", name: "Bronza", icon: "🥉", pct: 3, from: 0, next: { name: "Kumush", icon: "🥈", pct: 4, need: 3_800_000, at: 5_000_000 } };
  return { enabled: true, levels: LV4.map(([icon, name, pct, from]) => ({ icon, name, pct, from })), shop: sh ? { ...sh, active: true, link: `https://t.me/VaynexoBot?start=shop_${sh.slug}`, qr: "data:image/svg+xml;utf8," + encodeURIComponent(DEMO_QR) } : null,
    ...(sh ? { level: lv, sales_total: 1_200_000, rank: 3, stats: { customers: 14, buyers: 6, orders: 9, earned: 36_000, week: { orders: 3, earned: 11_000 }, today: { orders: 1, earned: 4_000 } } } : {}) };
};
on("GET", "/shop/my", () => shopView());
on("POST", "/shop", (_m, b) => { demo.shop = { slug: b.slug, name: b.name, tagline: b.tagline }; return shopView(); });
on("POST", "/shop/card", () => ({ ok: true }));
on("PUT", "/shop", (_m, b) => { Object.assign(demo.shop, { name: b.name ?? demo.shop.name, tagline: b.tagline ?? demo.shop.tagline }); return shopView(); });
on("GET", "/shop/top", () => ({ items: [
  { place: 1, name: "Sardor Gaming", slug: "sardor", icon: "🥇", level: "Oltin", orders: 61, sales: 24_300_000 },
  { place: 2, name: "ML Uz Kanal", slug: "mluz", icon: "🥈", level: "Kumush", orders: 33, sales: 9_800_000 },
  { place: 3, name: "Dilshod TV", slug: "dilshod", icon: "🥉", level: "Bronza", orders: 14, sales: 3_100_000 }] }));
on("GET", "/vay", () => ({ enabled: true, xp: 620, per: 1000, level: 2, name: "Jangchi", icon: "⚔️", cashback: 1, from: 500,
  next: { name: "Usta", icon: "🎖", need: 2_380, at: 3_000, cashback: 1 },
  levels: [["Rekrut", "🪖", 0, 0], ["Jangchi", "⚔️", 500, 1], ["Usta", "🎖", 3_000, 1], ["Legenda", "👑", 10_000, 2]].map(([name, icon, from, cashback]) => ({ name, icon, from, cashback })) }));
on("GET", "/plus", () => plusView());
on("POST", "/plus/buy", () => { money(-39_000, "plus"); demo.plus = { until: new Date(Date.now() + 30 * 86400000).toISOString() }; state.me.plus = true; return plusView(); });
on("PUT", "/plus", (_m, b) => {
  if (b.clear_auto) demo.plusAuto = null;
  else if (b.package_id) { const pk = PKGS.find((x) => x.id === b.package_id)! as Json; demo.plusAuto = { package_id: pk.id, title: pk.name, price: pk.price, game: pk.game, player_id: b.player_id, zone_id: b.zone_id, next_at: now() }; }
  return plusView();
});
on("GET", "/savings", () => savingsView());
on("POST", "/savings", (_m, b) => {
  const pk = PKGS.find((x) => x.id === b.package_id)! as Json;
  const first = Math.min(b.first || 0, pk.price);
  if (first) money(-first, "saving_in");
  demo.savings.unshift({ id: nid(), title: pk.name, package_id: pk.id, target: pk.price, saved: first, weekly: b.weekly || 0, status: "active", pct: Math.round((first * 100) / pk.price),
    next_at: null, buy_at: b.buy_at, bonus_pct: 3, bonus_ready: false, bonus_amount: 0, bonus_in_days: null, bonus: 0, order_id: null });
  return savingsView();
});
on("POST", "/savings/:id/deposit", (m, b) => {
  const x = demo.savings.find((y: Json) => y.id === Number(m[1])); const add = Math.min(b.amount, x.target - x.saved);
  money(-add, "saving_in"); x.saved += add; x.pct = Math.round((x.saved * 100) / x.target); return savingsView();
});
on("POST", "/savings/:id/cancel", (m) => { const x = demo.savings.find((y: Json) => y.id === Number(m[1])); money(x.saved, "saving_out"); x.status = "cancelled"; return savingsView(); });
on("POST", "/savings/:id/buy", (m) => { const x = demo.savings.find((y: Json) => y.id === Number(m[1])); x.status = "done"; return { order_id: 41, ...savingsView() }; });
on("GET", "/signals", () => ({ double: !!demo.signal }));
on("PUT", "/signals/:kind", (_m, b) => { demo.signal = b.on; return { double: b.on }; });
const streamerView = () => ({ enabled: true, fee: 10, min_money: 5_000, streamer: demo.streamer ? { ...demo.streamer, link: `https://t.me/VaynexoBot?start=stream_${demo.streamer.slug}`,
  widget: "https://vaynexo.example/api/stream/w/DEMO-TOKEN", total_count: 5, total_packs: 90_000, total_money: 27_000, today: { money: 9_000, count: 2 },
  items: [{ id: 3, name: "Jasur", kind: "money", title: "10 000 so'm", amount: 10_000, payout: 9_000, message: "Zo'r o'yin! 🔥", at: ago(20), hidden: false },
    { id: 2, name: "Anonim", kind: "pack", title: "86 almaz", amount: 18_500, payout: 0, message: "", at: ago(240), hidden: false }] } : null });
on("GET", "/stream/me", () => streamerView());
on("POST", "/stream/me", (_m, b) => { demo.streamer = { slug: b.slug || demo.streamer?.slug, name: b.name, about: b.about, player_id: b.player_id, zone_id: b.zone_id }; return streamerView(); });
on("POST", "/stream/me/test", () => ({ ok: true }));
on("POST", "/stream/me/rotate", () => streamerView());
on("POST", "/stream/me/hide/:id", () => ({ ok: true }));
on("GET", "/stream/s/:slug", (m) => ({ slug: m[1], name: m[1] === "aziz_live" ? "Aziz Live" : "Striminer", about: "Har kuni 20:00 da Mythic rank", count: 5, enabled: true, min_money: 5_000,
  top: [{ name: "Jasur", total: 38_000 }, { name: "Sardor", total: 20_000 }],
  recent: [{ id: 3, name: "Jasur", kind: "money", title: "10 000 so'm", amount: 10_000, message: "Zo'r o'yin! 🔥", at: ago(20) }] }));
on("POST", "/stream/s/:slug/donate", (_m, b) => { if (b.kind === "money") money(-b.amount, "stream_donate"); else money(-(PKGS.find((x) => x.id === b.package_id)?.price ?? 0), "stream_donate"); return { ok: true, order_id: null }; });
const slotView = (x: Json) => ({ ...x, history: [{ amount: x.price || x.min_bid, at: ago(30), me: x.leading }].filter(() => x.bids > 0) });
on("GET", "/pro", () => ({ items: demo.slots.filter((x: Json) => x.status === "open") }));
on("GET", "/pro/my", () => ({ enabled: true, fee: 15, min_bid: 20_000, earned: 0, profile: demo.proProfile, own: [], won: demo.slots.filter((x: Json) => x.winner) }));
on("POST", "/pro/apply", (_m, b) => { demo.proProfile = { ...b, status: "pending", note: "" }; return { enabled: true, fee: 15, min_bid: 20_000, earned: 0, profile: demo.proProfile, own: [], won: [] }; });
on("GET", "/pro/:id", (m) => slotView(demo.slots.find((x: Json) => x.id === Number(m[1]))));
on("POST", "/pro/:id/bid", (m, b) => {
  const x = demo.slots.find((y: Json) => y.id === Number(m[1]));
  if (b.amount < x.next_bid) throw new MockError("low_bid", `Stavka kamida ${fmt(x.next_bid)}`);
  money(-b.amount, "pro_bid"); x.price = b.amount; x.bids += 1; x.next_bid = b.amount + x.step; x.leading = true; return slotView(x);
});

// ---------------------------------------------------------------- Birgalikda, Draft Jang, seriya, meta (demo)
const HEROES_DEMO = [[109, "Aamon", "assassin", "jungle"], [4, "Alucard", "fighter", "exp"], [9, "Akai", "tank", "roam"], [5, "Alice", "mage", "mid"], [8, "Bruno", "marksman", "gold"]] as const;
demo.splits = [{ code: "demo1234", mode: "wish", title: "706 almaz", message: "Tug'ilgan kunim! 🎂", status: "open", target: 145_000, collected: 62_000,
  expires_at: new Date(Date.now() + 15 * 3600000).toISOString(), order_id: null, creator: { id: ME, name: "Aziz" }, mine: 0, is_creator: true,
  parts: [{ name: "Jasur", amount: 40_000 }, { name: "Sardor", amount: 22_000 }], game_id: "84512937", link: "https://t.me/VaynexoBot?start=split_demo1234", min: 1_000 }] as Json[];
const splitRow = (x: Json) => ({ code: x.code, mode: x.mode, title: x.title, status: x.status, target: x.target, collected: x.collected, expires_at: x.expires_at });
on("GET", "/split/my", () => ({ enabled: true, made: demo.splits.map(splitRow), joined: [] }));
on("POST", "/split", (_m, b) => {
  const pk = PKGS.find((x) => x.id === b.package_id)! as Json;
  const x = { code: "c" + nid(), mode: b.mode, title: pk.name, message: b.message, status: "open", target: pk.price, collected: 0, expires_at: new Date(Date.now() + 24 * 3600000).toISOString(),
    order_id: null, creator: { id: ME, name: "Aziz" }, mine: 0, is_creator: true, parts: [], game_id: b.player_id, link: "https://t.me/VaynexoBot?start=split_demo", min: 1_000 };
  demo.splits.unshift(x); return x;
});
on("GET", "/split/:code", (m) => demo.splits.find((x: Json) => x.code === m[1]) ?? demo.splits[0]);
on("POST", "/split/:code/pay", (m, b) => {
  const x = demo.splits.find((y: Json) => y.code === m[1]) ?? demo.splits[0]; const a = Math.min(b.amount, x.target - x.collected);
  money(-a, "split_in"); x.collected += a; x.mine += a; x.parts.unshift({ name: "Aziz", amount: a }); x.remaining = x.target - x.collected;
  if (x.collected >= x.target) x.status = "done"; return x;
});
on("POST", "/split/:code/cancel", (m) => { const x = demo.splits.find((y: Json) => y.code === m[1]); x.status = "cancelled"; return x; });
Object.values(demo.splits).forEach((x: Json) => { x.remaining = x.target - x.collected; });
const slotsD = [["gold", "Gold"], ["exp", "EXP"], ["mid", "Mid"], ["jungle", "Jungle"], ["roam", "Roam"]].map(([key, label]) => ({ key, label }));
const heroD = (id: number) => { const h = HEROES_DEMO.find((x) => x[0] === id) ?? HEROES_DEMO[0]; return { id: h[0], name: h[1], role: h[2], lane: h[3] }; };
demo.duel = { status: "picking", my: null as Json };
on("GET", "/duel/top", () => ({ items: [{ place: 1, name: "Sardor", elo: 1048, id: 2001 }, { place: 2, name: "Jasur", elo: 1021, id: 2002 }, { place: 3, name: "Aziz", elo: 1012, id: ME }], me: { elo: 1012 } }));
on("POST", "/duel", () => ({ code: "demo5678" }));
on("GET", "/duel/:code", () => ({ code: "demo5678", status: demo.duel.status, side: "a", opponent: { id: 2001, name: "Sardor", elo: 1048 }, me: { id: ME, name: "Aziz", elo: 1012 },
  expires_at: new Date(Date.now() + 40 * 3600000).toISOString(), link: "https://t.me/VaynexoBot?start=duel_demo5678", slots: slotsD,
  my_picks: demo.duel.my ? Object.fromEntries(Object.entries(demo.duel.my).map(([k, v]) => [k, heroD(v as number)])) : null,
  their_picks: demo.duel.status === "done" ? Object.fromEntries(slotsD.map((s, i) => [s.key, heroD(HEROES_DEMO[(i + 1) % 5][0])])) : null, opponent_ready: true,
  result: demo.duel.status === "done" ? { a_score: 78, b_score: 64, winner_id: ME, a_delta: 12, b_delta: -12, a: { id: ME, name: "Aziz" }, b: { id: 2001, name: "Sardor" },
    detail: { a: { lane: 32, front: 12, marksman: 12, mage: 12, mixed: 10 }, b: { lane: 24, front: 12, marksman: 12, mixed: 10, spread: 6 }, live_counters: false } } : null }));
on("POST", "/duel/:code/join", () => ({ code: "demo5678", status: "picking" }));
on("POST", "/duel/:code/picks", (_m, b) => { demo.duel.my = b.picks; demo.duel.status = "done"; return { ok: true }; });
demo.habit = { streak: 3, done: false };
on("GET", "/habit", () => ({ streak: demo.habit.streak, done_today: demo.habit.done, points: 5, hero: { id: 109, name: "Aamon", role: "assassin", lane: "jungle" }, next: { days: 7, points: 30, left: 7 - demo.habit.streak } }));
on("POST", "/habit/checkin", () => { demo.habit.streak += 1; demo.habit.done = true; state.me.points = (state.me.points ?? 0) + 5; return { earned: 5, bonus: 0 }; });
demo.meta = { pick: null as number | null };
on("GET", "/meta", () => ({ week: "2026W48", available: true, points: 50, my_pick: demo.meta.pick, candidates: HEROES_DEMO.map((h) => ({ id: h[0], name: h[1], role: h[2], win: 50 })),
  last: { winner: { id: 5, name: "Alice", delta: 2.4 }, my_hero: 109, correct: false } }));
on("POST", "/meta/pick", (_m, b) => { demo.meta.pick = b.hero_id; return { ok: true }; });
on("POST", "/arena/card", () => ({ ok: true }));

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

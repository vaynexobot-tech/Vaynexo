import { tg } from "./tg";

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) {
    super(message);
  }
}

/** Brauzerda sinash uchun: ?dev=12345 (backend DEV_MODE=true bo'lishi kerak). */
const devUser = new URLSearchParams(location.search).get("dev") || localStorageGet("devUser");
if (devUser) localStorageSet("devUser", devUser);

function localStorageGet(k: string) {
  try {
    return localStorage.getItem(k);
  } catch {
    return null;
  }
}
function localStorageSet(k: string, v: string) {
  try {
    localStorage.setItem(k, v);
  } catch {
    /* yo'q */
  }
}

function headers(json = true): Record<string, string> {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  if (tg?.initData) h["Authorization"] = "tma " + tg.initData;
  else if (devUser) h["X-Dev-User"] = devUser;
  return h;
}

export const DEMO = import.meta.env.VITE_DEMO === "1";

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  if (DEMO) {
    const { mockRequest, MockError } = await import("./mock");
    try {
      return (await mockRequest(method, url, body)) as T;
    } catch (e) {
      if (e instanceof MockError) throw new ApiError(e.code, e.message, e.status);
      throw e;
    }
  }
  let res: Response;
  try {
    res = await fetch("/api" + url, {
      method,
      headers: headers(!(body instanceof FormData)),
      body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("network", "Internet aloqasini tekshiring", 0);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(data.error || "error", data.message || "Xatolik yuz berdi", res.status);
  return data as T;
}

export const api = {
  get: <T>(url: string) => request<T>("GET", url),
  post: <T>(url: string, body: unknown = {}) => request<T>("POST", url, body),
  put: <T>(url: string, body: unknown) => request<T>("PUT", url, body),
  patch: <T>(url: string, body: unknown) => request<T>("PATCH", url, body),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{ type: "image" | "video"; url: string }>("POST", "/media", fd);
  },
};

// ---------------------------------------------------------------- turlar
export type Game = "ML" | "MC";
export interface Me {
  id: number;
  name: string;
  username: string | null;
  rating: number | null;
  rating_count: number;
  balance: number;
  tickets: number;
  lang: "uz" | "ru";
  phone: string | null;
  ml_id: string | null;
  bio: string | null;
  is_admin: boolean;
  sales: number;
  positive_percent: number | null;
  active_listings: number;
  referral_bonus: number;
  ref_link: string | null;
  ref_invited: number;
  ref_paid: number;
  ref_earned: number;
  commission_percent: number;
}
export interface Pkg { id: number; game: Game; name: string; diamonds: number; bonus: number; price: number; is_hot: boolean; is_active?: boolean; sku?: string; sort?: number }
export interface DonateOrder { id: number; ref: string; game: Game; title: string; player_id: string; zone_id: string; price: number; status: string; error: string | null; created_at: string; user_id?: number; attempts?: number; provider_ref?: string }
export interface ListingCard {
  id: number; game: Game; title: string; rank: string; server: string; collection_level: string; skins: number; heroes: number;
  price: number; cover: string | null; status: string; created_at: string; views?: number; chats?: number; reject_reason?: string | null;
}
export interface Media { type: "image" | "video"; url: string }
export interface UserPublic { id: number; name: string; username: string | null; rating: number | null; rating_count: number }
export interface ListingFull extends ListingCard {
  description: string; media: Media[]; views: number; reject_reason: string | null; seller: UserPublic;
  seller_stats?: { sales: number; positive_percent: number | null }; chat_id?: number | null; is_mine?: boolean;
}
export interface Deal {
  id: number; listing: ListingCard; price: number; commission: number; status: string; role: "buyer" | "seller" | "admin";
  chat_id: number; buyer_id: number; seller_id: number; credentials: string | null; delivered_at: string | null;
  auto_release_at: string | null; dispute_reason: string | null; resolution: string | null; created_at: string;
  reviewed?: boolean; seller_deliver_hours?: number;
}
export interface Chat { id: number; listing: ListingCard; role: "buyer" | "seller"; buyer_id: number; seller_id: number; last_message_at: string }
export interface Msg { id: number; sender_id: number | null; text: string; created_at: string }
export interface Topup { id: number; requested_amount: number; pay_amount: number; status: string; expires_at: string; paid_at: string | null; card_number: string; card_holder: string; created_at: string; balance?: number; user_id?: number }
export interface Ledger { id: number; amount: number; balance_after: number; kind: string; note: string | null; created_at: string }
export interface Withdrawal { id: number; user_id: number; amount: number; card: string; card_holder: string; status: string; admin_note: string | null; created_at: string }
export interface TgOrder { id: number; ref: string; kind: string; title: string; target_username: string; details: Record<string, unknown>; price: number; status: string; admin_note: string | null; user_id: number; created_at: string }
export interface Boost { id: number; ref: string; game: Game; current_rank: string; target_rank: string; stars: number; lane: string; note: string; login_method: string; price: number; status: string; booster_name: string | null; user_id: number; created_at: string; finished_at: string | null }
export interface Tournament { id: number; title: string; game: Game; prize_fund: number; entry_fee: number; max_players: number; players_count: number; starts_at: string; rules: string; status: string; joined: boolean }
export interface Catalog {
  premium: { months: number; price: number }[];
  stars: { presets: number[]; rate: number; min: number; max: number };
  gifts: { code: string; name: string; price: number }[];
  nft: { code: string; name: string; price: number }[];
}
export interface HistoryItem { type: string; id: number; game: string; title: string; sub: string; amount: number; status: string; created_at: string }

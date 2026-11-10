/* Telegram WebApp yordamchilari. Brauzerda (Telegramsiz) ochilganda ham ishlaydi. */

type Haptic = "light" | "medium" | "heavy";
interface TgWebApp {
  initData: string;
  initDataUnsafe: { user?: { id: number; first_name?: string; username?: string; photo_url?: string }; start_param?: string };
  ready(): void;
  expand(): void;
  setHeaderColor?(c: string): void;
  setBackgroundColor?(c: string): void;
  disableVerticalSwipes?(): void;
  BackButton: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void };
  HapticFeedback?: { impactOccurred(s: Haptic): void; notificationOccurred(t: "success" | "error" | "warning"): void };
  openTelegramLink(url: string): void;
  openLink(url: string): void;
  showConfirm?(msg: string, cb: (ok: boolean) => void): void;
  version: string;
  isVersionAtLeast?(v: string): boolean;
  BiometricManager?: BioManager;
}

interface BioManager {
  isInited: boolean;
  isBiometricAvailable: boolean;
  biometricType: "finger" | "face" | "unknown";
  isAccessGranted: boolean;
  isBiometricTokenSaved: boolean;
  init(cb?: () => void): void;
  requestAccess(p: { reason?: string }, cb?: (granted: boolean) => void): void;
  authenticate(p: { reason?: string }, cb?: (ok: boolean, token?: string) => void): void;
  updateBiometricToken(token: string, cb?: (ok: boolean) => void): void;
}

declare global {
  interface Window {
    Telegram?: { WebApp: TgWebApp };
  }
}

export const tg: TgWebApp | undefined = window.Telegram?.WebApp?.initData ? window.Telegram.WebApp : undefined;

export function initTelegram() {
  if (!tg) return;
  tg.ready();
  tg.expand();
  try {
    tg.setHeaderColor?.("#0d0e13");
    tg.setBackgroundColor?.("#0d0e13");
    if (tg.isVersionAtLeast?.("7.7")) tg.disableVerticalSwipes?.();
  } catch {
    /* eski versiyalar */
  }
}

export function haptic(kind: Haptic | "success" | "error" = "light") {
  const h = tg?.HapticFeedback;
  if (!h) return;
  if (kind === "success" || kind === "error") h.notificationOccurred(kind);
  else h.impactOccurred(kind);
}

export function confirmDialog(msg: string): Promise<boolean> {
  return new Promise((resolve) => {
    if (tg?.showConfirm && tg.isVersionAtLeast?.("6.2")) tg.showConfirm(msg, resolve);
    else if (import.meta.env.VITE_DEMO === "1") resolve(true); // artifact ichida confirm() ishlamaydi
    else resolve(window.confirm(msg));
  });
}

export function openTg(url: string) {
  if (tg) tg.openTelegramLink(url);
  else window.open(url, "_blank");
}

export const startParam = (): string | undefined =>
  tg?.initDataUnsafe.start_param || new URLSearchParams(location.search).get("tgWebAppStartParam") || undefined;

export const tgPhoto = (): string | undefined => tg?.initDataUnsafe.user?.photo_url;

/** Telegram biometrik menejeri (Face ID / barmoq izi). Mavjud bo'lmasa null. */
export function bioManager(): Promise<BioManager | null> {
  const bm = tg?.isVersionAtLeast?.("7.2") ? tg.BiometricManager : undefined;
  if (!bm) return Promise.resolve(null);
  if (bm.isInited) return Promise.resolve(bm.isBiometricAvailable ? bm : null);
  return new Promise((resolve) => bm.init(() => resolve(bm.isBiometricAvailable ? bm : null)));
}

/** Biometrik kalitni qurilmaga yozadi (avval ruxsat so'raydi). */
export async function bioSave(key: string, reason: string): Promise<boolean> {
  const bm = await bioManager();
  if (!bm) return false;
  if (!bm.isAccessGranted) {
    const granted = await new Promise<boolean>((r) => bm.requestAccess({ reason }, r));
    if (!granted) return false;
  }
  return new Promise((r) => bm.updateBiometricToken(key, r));
}

/** Biometriya orqali saqlangan kalitni oladi. */
export async function bioRead(reason: string): Promise<string | null> {
  const bm = await bioManager();
  if (!bm || !bm.isBiometricTokenSaved) return null;
  return new Promise((r) => bm.authenticate({ reason }, (ok, token) => r(ok && token ? token : null)));
}

export async function bioClear(): Promise<void> {
  const bm = await bioManager();
  if (bm?.isBiometricTokenSaved) await new Promise((r) => bm.updateBiometricToken("", r));
}

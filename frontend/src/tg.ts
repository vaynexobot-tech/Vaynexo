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

import { ru } from "./ru";

let lang: "uz" | "ru" = "uz";

export function setLang(l: "uz" | "ru") {
  lang = l;
  document.documentElement.lang = l;
}

export const getLang = () => lang;

/** Kalit — o'zbekcha matnning o'zi. Ruscha tarjima bo'lmasa, o'zbekchasi ko'rsatiladi. */
export function t(uz: string, vars?: Record<string, string | number>): string {
  let s = lang === "ru" ? ru[uz] ?? uz : uz;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
  return s;
}

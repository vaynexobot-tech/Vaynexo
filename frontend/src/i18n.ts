import { en } from "./en";
import { ru } from "./ru";

export type Lang = "uz" | "ru" | "en";
let lang: Lang = "uz";

export function setLang(l: Lang) {
  lang = l;
  document.documentElement.lang = l;
}

export const getLang = () => lang;

export const LANGS: { v: Lang; label: string; sub: string }[] = [
  { v: "uz", label: "O'zbekcha", sub: "O'zbek tili" },
  { v: "ru", label: "Русский", sub: "Русский язык" },
  { v: "en", label: "English", sub: "English" },
];

/** Kalit — o'zbekcha matnning o'zi. Tarjima bo'lmasa, o'zbekchasi ko'rsatiladi. */
export function t(uz: string, vars?: Record<string, string | number>): string {
  let s = lang === "ru" ? ru[uz] ?? uz : lang === "en" ? en[uz] ?? uz : uz;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
  return s;
}

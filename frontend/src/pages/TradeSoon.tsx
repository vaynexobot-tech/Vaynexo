// «Savdo va xizmatlar»: yopiq bo'limlar «Tez kunda» bilan ko'rinadi, ochiqlari bosiladi. Admin Ko'proq → Bo'limlar orqali ochadi.
import { useNavigate } from "react-router-dom";
import { t } from "../i18n";
import { Art, Header, Icon, useApp } from "../ui";

const ITEMS = [
  { f: "market", to: "/market", icon: "market", title: "Account savdo", sub: "Garant bilan akkaunt sotib oling yoki soting" },
  { f: "rent", to: "/rent", icon: "rent", title: "Account ijara", sub: "Akkauntni soatbay ijaraga oling yoki bering" },
  { f: "boost", to: "/boost", icon: "boost", title: "Boost xizmati", sub: "Rankni professional boosterlar bilan ko'taring" },
  { f: "tg", to: "/tg", icon: "tg", title: "Telegram xizmatlar", sub: "Premium, Stars va sovg'alar" },
];

export default function TradeSoon() {
  const nav = useNavigate();
  const { me } = useApp();
  const open = (f: string) => !!me?.features?.[f];
  const anyClosed = ITEMS.some((i) => !open(i.f));
  return (
    <>
      <Header title={t("Savdo va xizmatlar")} sub={t("Tez orada ishga tushadi")} />
      <div className="page">
        {anyClosed && (
          <div className="hero center" style={{ alignItems: "center", gap: 6 }}>
            <div style={{ fontSize: 34 }}>🚀</div>
            <div className="hf bb" style={{ fontSize: 18 }}>{t("Tez kunda ochilamiz!")}</div>
            <div className="mut sm" style={{ textAlign: "center", maxWidth: 300 }}>{t("Bu bo'limlar ustida ishlayapmiz. Donat va hamyon hozir ishlaydi.")}</div>
          </div>
        )}
        {ITEMS.map((i) => {
          const on = open(i.f);
          return (
            <button key={i.f} className="card click row" style={{ textAlign: "left", opacity: on ? 1 : 0.7 }} disabled={!on && !me?.is_admin} onClick={() => nav(i.to)}>
              <Art name={i.icon} size={44} />
              <div className="grow" style={{ minWidth: 0 }}>
                <div className="b">{t(i.title)}</div>
                <div className="mut xs">{t(i.sub)}</div>
              </div>
              {on ? <Icon name="right" size={18} className="mut" /> : <span className="badge y">{t("Tez kunda")}</span>}
            </button>
          );
        })}
      </div>
    </>
  );
}

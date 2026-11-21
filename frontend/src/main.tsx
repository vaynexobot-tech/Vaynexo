import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, MemoryRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, ApiError, DEMO, isWebAdmin, pinToken, type Me } from "./api";
import { setLang, t } from "./i18n";
import Admin from "./pages/Admin";
import Partner from "./pages/Partner";
import { Arena, TournamentPage, Top } from "./pages/Arena";
import { Boost, BoostOrderPage, BoostOrders } from "./pages/Boost";
import { ChatPage, Chats } from "./pages/Chat";
import { DealPage, Deals } from "./pages/Deal";
import Donate, { DonateOrderPage } from "./pages/Donate";
import Home from "./pages/Home";
import { HeroPage, Heroes } from "./pages/Heroes";
import { ListingDetail, Market, PayListing } from "./pages/Market";
import { MyRentals, Rent, RentalPage, RentDetail, RentSell } from "./pages/Rent";
import { MyListings, Sell } from "./pages/Sell";
import { Help, History, Legal, ProfileEdit, Referral } from "./pages/Settings";
import { Kyc, PaymentMethods, PinLock, Security, Settings } from "./pages/Account";
import TgServices, { TgOrderPage, TgOrders } from "./pages/TgServices";
import Wallet from "./pages/Wallet";
import "./styles.css";
import { initTelegram, startParam, tg } from "./tg";
import { AppCtx, Empty, errorText, Spinner, useApp, useToastHost } from "./ui";

initTelegram();
if (DEMO) window.prompt = () => "Demo izoh"; // artifact ichida prompt() ishlamaydi

/** t.me/bot?startapp=listing_15 kabi havolalar bilan to'g'ridan-to'g'ri sahifaga o'tish. */
function DeepLink() {
  const nav = useNavigate();
  useEffect(() => {
    const p = startParam();
    if (!p) return;
    const [kind, id] = p.split("_");
    const map: Record<string, string> = { listing: `/listing/${id}`, deal: `/deal/${id}`, chat: `/chat/${id}`, boost: `/boost/${id}`, tour: `/arena/${id}`, arena: `/arena/${id}`, rental: `/rental/${id}` };
    if (kind === "donate" && /^donate_[A-Za-z0-9-]{1,60}$/.test(p)) nav(`/donate/${p.slice(7)}`); // inline qidiruvdan
    else if (map[kind] && /^\d+$/.test(id)) nav(map[kind], { replace: false }); // yopiq bo'lim bo'lsa Gate bosh sahifaga qaytaradi
    else if (["admin", "wallet", "booster", "rent", "partner", "arena"].includes(kind) && !id) nav("/" + kind); // kanal tugmalari
  }, [nav]);
  return null;
}

/** Admin Sozlamalarida o'chirilgan bo'lim sahifasi ochilmaydi (admin o'zi kira oladi). */
function Gate({ f, children }: { f: string; children: JSX.Element }) {
  const { me } = useApp();
  return me?.is_admin || me?.features?.[f] ? children : <Navigate to="/" replace />;
}

function App() {
  const [me, setMeState] = useState<Me | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);
  const [comingSoon, setComingSoon] = useState(false);
  const { show, node } = useToastHost();

  const setMe = useCallback((m: Me) => {
    setLang(m.lang);
    setMeState(m);
  }, []);
  const refreshMe = useCallback(async () => {
    setMe(await api.get<Me>("/me"));
  }, [setMe]);
  const fail = useCallback((e: unknown) => show(errorText(e), "err"), [show]);
  const [locked, setLocked] = useState(false);
  useEffect(() => {
    const onReq = () => setLocked(true);
    window.addEventListener("vx:pin-required", onReq);
    return () => window.removeEventListener("vx:pin-required", onReq);
  }, []);
  useEffect(() => {
    if (me?.pin_set && !pinToken()) setLocked(true);
  }, [me?.pin_set]);

  useEffect(() => {
    refreshMe().catch((e) => (e instanceof ApiError && e.code === "coming_soon" ? setComingSoon(true) : setFatal(errorText(e))));
  }, [refreshMe]);

  if (comingSoon)
    return (
      <div className="app">
        <Empty icon="🚀" text={t("Tez kunda ochilamiz!")}>
          <div className="mut sm" style={{ textAlign: "center", maxWidth: 280 }}>{t("Yana biroz sabr qiling — VAYNEXO tez orada hammaga ochiladi.")}</div>
        </Empty>
      </div>
    );
  if (fatal)
    return (
      <div className="app">
        <Empty icon="🔒" text={fatal}>
          {!tg && <div className="mut sm">{t("Ilova Telegram ichida ochilishi kerak.")}</div>}
        </Empty>
      </div>
    );
  if (!me) return <Spinner />;
  if (locked && me.pin_set)
    return (
      <div className="app">
        {node}
        <PinLock bio={me.bio_set} onUnlock={() => setLocked(false)} />
      </div>
    );

  return (
    <AppCtx.Provider value={{ me, setMe, refreshMe, toast: show, fail }}>
      <div className={"app" + (isWebAdmin ? " web" : "")} key={me.lang}>
        {node}
        {DEMO && <div className="demo-bar">DEMO · namuna ma'lumotlar · haqiqiy to'lov va yuborish yo'q</div>}
        <DeepLink />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/wallet" element={<Wallet />} />
          <Route path="/partner" element={<Gate f="partner"><Partner /></Gate>} />
          <Route path="/donate/order/:id" element={<DonateOrderPage />} />
          <Route path="/donate/:game" element={<Donate />} />
          <Route path="/market" element={<Gate f="market"><Market /></Gate>} />
          <Route path="/listing/:id" element={<Gate f="market"><ListingDetail /></Gate>} />
          <Route path="/pay/listing/:id" element={<Gate f="market"><PayListing /></Gate>} />
          <Route path="/sell" element={<Gate f="market"><Sell /></Gate>} />
          <Route path="/sell/:id" element={<Gate f="market"><Sell /></Gate>} />
          <Route path="/my-listings" element={<Gate f="market"><MyListings /></Gate>} />
          <Route path="/chats" element={<Gate f="market"><Chats /></Gate>} />
          <Route path="/chat/:id" element={<Gate f="market"><ChatPage /></Gate>} />
          <Route path="/deals" element={<Gate f="market"><Deals /></Gate>} />
          <Route path="/deal/:id" element={<Gate f="market"><DealPage /></Gate>} />
          <Route path="/rent" element={<Gate f="rent"><Rent /></Gate>} />
          <Route path="/rent/new" element={<Gate f="rent"><RentSell /></Gate>} />
          <Route path="/rent/edit/:id" element={<Gate f="rent"><RentSell /></Gate>} />
          <Route path="/rent/:id" element={<Gate f="rent"><RentDetail /></Gate>} />
          <Route path="/rentals" element={<Gate f="rent"><MyRentals /></Gate>} />
          <Route path="/rental/:id" element={<Gate f="rent"><RentalPage /></Gate>} />
          <Route path="/tg" element={<Gate f="tg"><TgServices /></Gate>} />
          <Route path="/tg/orders" element={<Gate f="tg"><TgOrders /></Gate>} />
          <Route path="/tg/order/:id" element={<Gate f="tg"><TgOrderPage /></Gate>} />
          <Route path="/boost" element={<Gate f="boost"><Boost /></Gate>} />
          <Route path="/boosts" element={<Gate f="boost"><BoostOrders /></Gate>} />
          <Route path="/boost/:id" element={<Gate f="boost"><BoostOrderPage /></Gate>} />
          <Route path="/arena" element={<Gate f="arena"><Arena /></Gate>} />
          <Route path="/arena/:id" element={<Gate f="arena"><TournamentPage /></Gate>} />
          <Route path="/heroes" element={<Heroes />} />
          <Route path="/heroes/:id" element={<HeroPage />} />
          <Route path="/top" element={<Gate f="top"><Top /></Gate>} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/profile" element={<ProfileEdit />} />
          <Route path="/referral" element={<Referral />} />
          <Route path="/kyc" element={<Kyc />} />
          <Route path="/payment-methods" element={<PaymentMethods />} />
          <Route path="/security" element={<Security />} />
          <Route path="/history" element={<History />} />
          <Route path="/help" element={<Help />} />
          <Route path="/legal/:doc" element={<Legal />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </AppCtx.Provider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {DEMO ? (
      <MemoryRouter initialEntries={[location.hash.slice(1) || "/"]}>
        <App />
      </MemoryRouter>
    ) : (
      <BrowserRouter>
        <App />
      </BrowserRouter>
    )}
  </StrictMode>,
);

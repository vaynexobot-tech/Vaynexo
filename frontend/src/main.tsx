import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, MemoryRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, DEMO, pinToken, type Me } from "./api";
import { setLang, t } from "./i18n";
import Admin from "./pages/Admin";
import { Arena, TournamentPage, Top } from "./pages/Arena";
import { Boost, BoostOrderPage, BoostOrders } from "./pages/Boost";
import { ChatPage, Chats } from "./pages/Chat";
import { DealPage, Deals } from "./pages/Deal";
import Donate from "./pages/Donate";
import Home from "./pages/Home";
import { ListingDetail, Market } from "./pages/Market";
import { MyRentals, Rent, RentalPage, RentDetail, RentSell } from "./pages/Rent";
import { MyListings, Sell } from "./pages/Sell";
import { Help, History, Legal, ProfileEdit, Referral } from "./pages/Settings";
import { Kyc, PaymentMethods, PinLock, Security, Settings } from "./pages/Account";
import TgServices, { TgOrderPage, TgOrders } from "./pages/TgServices";
import Wallet from "./pages/Wallet";
import "./styles.css";
import { initTelegram, startParam, tg } from "./tg";
import { AppCtx, Empty, errorText, Spinner, useToastHost } from "./ui";

initTelegram();
if (DEMO) window.prompt = () => "Demo izoh"; // artifact ichida prompt() ishlamaydi

/** t.me/bot?startapp=listing_15 kabi havolalar bilan to'g'ridan-to'g'ri sahifaga o'tish. */
function DeepLink() {
  const nav = useNavigate();
  useEffect(() => {
    const p = startParam();
    if (!p) return;
    const [kind, id] = p.split("_");
    const map: Record<string, string> = { listing: `/listing/${id}`, deal: `/deal/${id}`, chat: `/chat/${id}`, boost: `/boost/${id}`, tour: `/arena/${id}` };
    if (map[kind] && /^\d+$/.test(id)) nav(map[kind], { replace: false });
  }, [nav]);
  return null;
}

function App() {
  const [me, setMeState] = useState<Me | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);
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
    refreshMe().catch((e) => setFatal(errorText(e)));
  }, [refreshMe]);

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
      <div className="app" key={me.lang}>
        {node}
        {DEMO && <div className="demo-bar">DEMO · namuna ma'lumotlar · haqiqiy to'lov va yuborish yo'q</div>}
        <DeepLink />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/wallet" element={<Wallet />} />
          <Route path="/donate/:game" element={<Donate />} />
          <Route path="/market" element={<Market />} />
          <Route path="/listing/:id" element={<ListingDetail />} />
          <Route path="/sell" element={<Sell />} />
          <Route path="/sell/:id" element={<Sell />} />
          <Route path="/my-listings" element={<MyListings />} />
          <Route path="/chats" element={<Chats />} />
          <Route path="/chat/:id" element={<ChatPage />} />
          <Route path="/deals" element={<Deals />} />
          <Route path="/deal/:id" element={<DealPage />} />
          <Route path="/rent" element={<Rent />} />
          <Route path="/rent/new" element={<RentSell />} />
          <Route path="/rent/edit/:id" element={<RentSell />} />
          <Route path="/rent/:id" element={<RentDetail />} />
          <Route path="/rentals" element={<MyRentals />} />
          <Route path="/rental/:id" element={<RentalPage />} />
          <Route path="/tg" element={<TgServices />} />
          <Route path="/tg/orders" element={<TgOrders />} />
          <Route path="/tg/order/:id" element={<TgOrderPage />} />
          <Route path="/boost" element={<Boost />} />
          <Route path="/boosts" element={<BoostOrders />} />
          <Route path="/boost/:id" element={<BoostOrderPage />} />
          <Route path="/arena" element={<Arena />} />
          <Route path="/arena/:id" element={<TournamentPage />} />
          <Route path="/top" element={<Top />} />
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

import { Suspense, lazy } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import { useAuth } from "./lib/auth";
import AuthPage from "./pages/AuthPage";
import EventPage from "./pages/EventPage";
import Home from "./pages/Home";
import MyTickets from "./pages/MyTickets";
import PaymentCallback from "./pages/PaymentCallback";
import SimulatePayment from "./pages/SimulatePayment";
import Dashboard from "./pages/organizer/Dashboard";
import EventEditor from "./pages/organizer/EventEditor";
import EventStats from "./pages/organizer/EventStats";

// The QR scanner library is large; only organizers at the door need it.
const CheckIn = lazy(() => import("./pages/organizer/CheckIn"));

function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  return children;
}

const auth = (el) => <RequireAuth>{el}</RequireAuth>;

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="login" element={<AuthPage />} />
        <Route path="events/:slug" element={<EventPage />} />
        <Route path="tickets" element={auth(<MyTickets />)} />
        <Route path="payment/callback" element={auth(<PaymentCallback />)} />
        <Route path="payment/simulate" element={auth(<SimulatePayment />)} />
        <Route path="organize" element={auth(<Dashboard />)} />
        <Route path="organize/new" element={auth(<EventEditor />)} />
        <Route path="organize/:slug" element={auth(<EventStats />)} />
        <Route path="organize/:slug/edit" element={auth(<EventEditor />)} />
        <Route path="organize/:slug/checkin" element={auth(<Suspense fallback={<Spinner />}><CheckIn /></Suspense>)} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";

function NavItem({ to, end, children }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `rounded-lg px-3 py-2 text-sm font-medium transition ${
          isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const next = encodeURIComponent(location.pathname + location.search);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-3">
          <Link to="/" className="mr-2 flex items-center gap-2 text-lg font-bold text-slate-900">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-sm text-white">G</span>
            <span className="hidden sm:inline">Gatepass</span>
          </Link>
          <nav className="flex flex-1 items-center gap-1">
            <NavItem to="/" end>
              Events
            </NavItem>
            {user && <NavItem to="/tickets">My tickets</NavItem>}
            {user && <NavItem to="/organize">Organize</NavItem>}
          </nav>
          {user ? (
            <div className="flex items-center gap-3">
              <span className="hidden text-sm text-slate-500 md:inline">{user.username}</span>
              <button onClick={logout} className="text-sm text-slate-500 hover:text-slate-800">
                Log out
              </button>
            </div>
          ) : (
            <Link to={`/login?next=${next}`} className="btn-primary">
              Sign in
            </Link>
          )}
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 py-6 text-center text-xs text-slate-400">
        Gatepass · Payments by Paystack · Built with Django, Celery & React
      </footer>
    </div>
  );
}

import { Link } from "react-router-dom";
import { dateBadge, formatNaira } from "../lib/format";

export function Spinner({ label = "Loading…" }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-slate-400">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" />
      {label}
    </div>
  );
}

export function Empty({ icon = "🎟️", title, children }) {
  return (
    <div className="card px-6 py-14 text-center">
      <div className="mx-auto mb-3 text-4xl">{icon}</div>
      <h3 className="font-semibold text-slate-700">{title}</h3>
      {children && <div className="mt-2 text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function ErrorNote({ children }) {
  if (!children) return null;
  return <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{children}</p>;
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-600">{label}</span>
      <div className="mt-1">{children}</div>
      {hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </label>
  );
}

export function Badge({ className, children }) {
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}>{children}</span>;
}

export function DateBadge({ iso, size = "md" }) {
  const { day, month } = dateBadge(iso);
  const box = size === "lg" ? "h-16 w-16" : "h-12 w-12";
  return (
    <div className={`${box} flex shrink-0 flex-col items-center justify-center rounded-xl bg-brand-50 text-brand-700`}>
      <span className="text-[10px] font-semibold tracking-wide">{month}</span>
      <span className={size === "lg" ? "text-2xl font-bold leading-none" : "text-lg font-bold leading-none"}>{day}</span>
    </div>
  );
}

// Deterministic gradient per event so cards look distinct without image uploads.
const GRADIENTS = [
  "from-indigo-500 to-violet-500",
  "from-sky-500 to-indigo-500",
  "from-emerald-500 to-teal-500",
  "from-orange-500 to-rose-500",
  "from-fuchsia-500 to-pink-500",
  "from-amber-500 to-orange-500",
];

export function gradientFor(slug) {
  let hash = 0;
  for (const ch of slug) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return GRADIENTS[hash % GRADIENTS.length];
}

export function EventCard({ event }) {
  return (
    <Link to={`/events/${event.slug}`} className="card group overflow-hidden transition hover:-translate-y-0.5 hover:shadow-lg">
      <div className={`relative h-32 bg-gradient-to-br ${gradientFor(event.slug)}`}>
        <span className="absolute bottom-3 left-4 rounded-full bg-white/20 px-2.5 py-0.5 text-xs font-medium text-white backdrop-blur">
          {event.city}
        </span>
        {event.is_sold_out && (
          <span className="absolute right-3 top-3 rounded-full bg-slate-900/70 px-2.5 py-0.5 text-xs font-medium text-white">
            Sold out
          </span>
        )}
      </div>
      <div className="flex gap-4 p-4">
        <DateBadge iso={event.starts_at} />
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-slate-800 group-hover:text-brand-700">{event.title}</h3>
          <p className="truncate text-sm text-slate-500">{event.venue}</p>
          <p className="mt-1 text-sm font-medium text-slate-700">
            {event.min_price === null ? "Tickets soon" : event.min_price === 0 ? "Free" : `From ${formatNaira(event.min_price)}`}
          </p>
        </div>
      </div>
    </Link>
  );
}

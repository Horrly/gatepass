import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { DateBadge, Empty, ErrorNote, Spinner, gradientFor } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDateTime, formatNaira } from "../lib/format";
import { useFetch } from "../lib/useFetch";

const MAX_PER_ORDER = 10;

export default function EventPage() {
  const { slug } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data: event, loading, error } = useFetch(`/events/${slug}/`);

  const [quantities, setQuantities] = useState({});
  const [busy, setBusy] = useState(false);
  const [checkoutError, setCheckoutError] = useState("");

  const selected = useMemo(() => {
    if (!event) return { count: 0, total: 0 };
    return event.ticket_types.reduce(
      (acc, t) => {
        const q = quantities[t.id] || 0;
        return { count: acc.count + q, total: acc.total + q * t.price };
      },
      { count: 0, total: 0 },
    );
  }, [event, quantities]);

  if (loading) return <Spinner />;
  if (error) return <Empty icon="🔎" title="Event not found">It may have been unpublished or removed.</Empty>;

  const onSale = event.is_published && !event.has_ended;

  function change(ticket, delta) {
    setCheckoutError("");
    setQuantities((q) => {
      const current = q[ticket.id] || 0;
      const othersTotal = selected.count - current;
      const next = Math.max(0, Math.min(current + delta, ticket.available, MAX_PER_ORDER - othersTotal));
      return { ...q, [ticket.id]: next };
    });
  }

  async function checkout() {
    if (!user) {
      navigate(`/login?next=${encodeURIComponent(`/events/${slug}`)}`);
      return;
    }
    setBusy(true);
    setCheckoutError("");
    try {
      const order = await api("/orders/", {
        method: "POST",
        body: {
          event: slug,
          items: Object.entries(quantities)
            .filter(([, q]) => q > 0)
            .map(([id, q]) => ({ ticket_type: Number(id), quantity: q })),
        },
      });
      if (order.status === "paid") {
        navigate(`/payment/callback?reference=${order.reference}`);
      } else {
        // Hand over to Paystack's hosted checkout (or the local simulator).
        window.location.assign(order.authorization_url);
      }
    } catch (err) {
      setCheckoutError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_380px]">
      <article>
        <div className={`mb-6 h-48 rounded-3xl bg-gradient-to-br md:h-64 ${gradientFor(event.slug)}`} />
        {!event.is_published && (
          <p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Draft — only you can see this page.{" "}
            <Link className="font-medium underline" to={`/organize/${event.slug}/edit`}>
              Edit & publish
            </Link>
          </p>
        )}
        <div className="flex items-start gap-4">
          <DateBadge iso={event.starts_at} size="lg" />
          <div>
            <h1 className="text-3xl font-bold">{event.title}</h1>
            <p className="mt-1 text-slate-500">by {event.organizer}</p>
          </div>
        </div>

        <dl className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="card p-4">
            <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">When</dt>
            <dd className="mt-1 text-sm font-medium">{formatDateTime(event.starts_at)}</dd>
            {event.ends_at && <dd className="text-sm text-slate-500">until {formatDateTime(event.ends_at)}</dd>}
          </div>
          <div className="card p-4">
            <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">Where</dt>
            <dd className="mt-1 text-sm font-medium">{event.venue}</dd>
            <dd className="text-sm text-slate-500">{event.city}</dd>
          </div>
        </dl>

        {event.description && (
          <p className="mt-6 whitespace-pre-line leading-relaxed text-slate-600">{event.description}</p>
        )}

        {event.is_organizer && (
          <div className="mt-6 flex flex-wrap gap-2">
            <Link to={`/organize/${event.slug}`} className="btn-secondary">
              View sales
            </Link>
            <Link to={`/organize/${event.slug}/checkin`} className="btn-secondary">
              Check in guests
            </Link>
          </div>
        )}
      </article>

      <aside className="lg:sticky lg:top-24 lg:self-start">
        <div className="card p-5">
          <h2 className="font-semibold">Tickets</h2>
          {event.ticket_types.length === 0 && <p className="mt-3 text-sm text-slate-500">No tickets yet.</p>}
          <ul className="mt-3 divide-y divide-slate-100">
            {event.ticket_types.map((t) => {
              const q = quantities[t.id] || 0;
              const soldOut = t.available === 0;
              return (
                <li key={t.id} className="flex items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{t.name}</p>
                    <p className="text-sm text-slate-600">{formatNaira(t.price)}</p>
                    {t.description && <p className="text-xs text-slate-400">{t.description}</p>}
                    {!soldOut && t.available <= 10 && (
                      <p className="text-xs font-medium text-amber-600">Only {t.available} left</p>
                    )}
                  </div>
                  {soldOut ? (
                    <span className="text-sm font-medium text-slate-400">Sold out</span>
                  ) : (
                    <div className="flex items-center gap-2" aria-label={`${t.name} quantity`}>
                      <button className="btn-secondary h-8 w-8 p-0" onClick={() => change(t, -1)} disabled={!onSale || q === 0} aria-label={`Remove ${t.name}`}>
                        −
                      </button>
                      <span className="w-5 text-center text-sm font-semibold" data-testid={`qty-${t.name}`}>{q}</span>
                      <button className="btn-secondary h-8 w-8 p-0" onClick={() => change(t, 1)} disabled={!onSale} aria-label={`Add ${t.name}`}>
                        +
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>

          <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-4">
            <span className="text-sm text-slate-500">
              {selected.count} ticket{selected.count === 1 ? "" : "s"}
            </span>
            <span className="text-lg font-bold">{selected.count ? formatNaira(selected.total) : "—"}</span>
          </div>
          <div className="mt-4 space-y-3">
            <ErrorNote>{checkoutError}</ErrorNote>
            <button className="btn-primary w-full py-3" disabled={!onSale || selected.count === 0 || busy} onClick={checkout}>
              {busy ? "Reserving your tickets…" : !onSale ? "Not on sale" : selected.total === 0 && selected.count ? "Get free tickets" : "Checkout"}
            </button>
            <p className="text-center text-xs text-slate-400">Tickets are held for 15 minutes while you pay. Secured by Paystack.</p>
          </div>
        </div>
      </aside>
    </div>
  );
}

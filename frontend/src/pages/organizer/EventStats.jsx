import { Link, useParams } from "react-router-dom";
import { Empty, Spinner } from "../../components/ui";
import { formatDateTime, formatNaira } from "../../lib/format";
import { useFetch } from "../../lib/useFetch";

function Stat({ label, value, sub }) {
  return (
    <div className="card p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-bold">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

export default function EventStats() {
  const { slug } = useParams();
  const { data: event, loading: loadingEvent } = useFetch(`/events/${slug}/`);
  const { data: stats, loading, error } = useFetch(`/events/${slug}/stats/`);

  if (loading || loadingEvent) return <Spinner />;
  if (error) return <Empty icon="🔒" title="Sales are only visible to the organizer" />;

  const checkinRate = stats.tickets_sold ? Math.round((stats.checked_in / stats.tickets_sold) * 100) : 0;

  return (
    <div>
      <Link to="/organize" className="text-sm text-slate-500 hover:text-slate-800">
        ← Your events
      </Link>
      <div className="mb-6 mt-2 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{event.title}</h1>
          <p className="text-sm text-slate-500">
            {formatDateTime(event.starts_at)} · {event.venue}
          </p>
        </div>
        <div className="flex gap-2">
          <Link to={`/organize/${slug}/edit`} className="btn-secondary">
            Edit
          </Link>
          <Link to={`/organize/${slug}/checkin`} className="btn-primary">
            Check in guests
          </Link>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Revenue" value={formatNaira(stats.revenue) || "₦0"} sub={`${stats.orders} paid orders`} />
        <Stat label="Tickets sold" value={stats.tickets_sold} />
        <Stat label="Checked in" value={stats.checked_in} sub={`${checkinRate}% of tickets sold`} />
        <Stat
          label="Capacity left"
          value={stats.by_ticket_type.reduce((n, t) => n + Math.max(t.quantity - t.sold - t.on_hold, 0), 0)}
        />
      </div>

      <section className="card mt-6 p-6">
        <h2 className="mb-4 font-semibold">By ticket type</h2>
        <div className="space-y-5">
          {stats.by_ticket_type.map((t) => {
            const soldPct = (t.sold / t.quantity) * 100;
            const holdPct = (t.on_hold / t.quantity) * 100;
            return (
              <div key={t.id}>
                <div className="mb-1.5 flex flex-wrap justify-between gap-2 text-sm">
                  <span className="font-medium">
                    {t.name} <span className="font-normal text-slate-400">· {formatNaira(t.price)}</span>
                  </span>
                  <span className="text-slate-500">
                    {t.sold} sold{t.on_hold ? ` · ${t.on_hold} on hold` : ""} of {t.quantity} · {formatNaira(t.revenue) || "₦0"}
                  </span>
                </div>
                <div className="flex h-2.5 overflow-hidden rounded-full bg-slate-100" role="img" aria-label={`${t.sold} of ${t.quantity} sold`}>
                  <div className="bg-brand-600" style={{ width: `${soldPct}%` }} />
                  <div className="bg-amber-300" style={{ width: `${holdPct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
        <p className="mt-4 flex gap-4 text-xs text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-brand-600" /> Sold
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-amber-300" /> Held while buyers pay
          </span>
        </p>
      </section>

      <section className="card mt-6 p-6">
        <h2 className="mb-3 font-semibold">Recent orders</h2>
        {stats.recent_orders.length === 0 ? (
          <p className="text-sm text-slate-500">No sales yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="pb-2 font-medium">Order</th>
                  <th className="pb-2 font-medium">Buyer</th>
                  <th className="pb-2 font-medium">Tickets</th>
                  <th className="pb-2 font-medium">Total</th>
                  <th className="pb-2 font-medium">Paid</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {stats.recent_orders.map((o) => (
                  <tr key={o.reference}>
                    <td className="py-2.5 font-mono text-xs">{o.reference}</td>
                    <td className="py-2.5">{o.buyer}</td>
                    <td className="py-2.5">{o.tickets}</td>
                    <td className="py-2.5">{formatNaira(o.total)}</td>
                    <td className="py-2.5 text-slate-500">{formatDateTime(o.paid_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

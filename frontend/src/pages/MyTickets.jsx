import { QRCodeSVG } from "qrcode.react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, DateBadge, Empty, Spinner } from "../components/ui";
import { ORDER_STATUS, formatDateTime, formatNaira, minutesLeft, orderTotalLabel } from "../lib/format";
import { useFetch } from "../lib/useFetch";

function TicketCard({ ticket, event, onOpen }) {
  const used = Boolean(ticket.checked_in_at);
  return (
    <button
      onClick={() => onOpen(ticket)}
      className={`card flex items-center gap-4 p-3 text-left transition hover:shadow-md ${used ? "opacity-60" : ""}`}
    >
      <div className="rounded-lg border border-slate-100 bg-white p-1.5">
        <QRCodeSVG value={ticket.code} size={72} />
      </div>
      <div className="min-w-0">
        <p className="font-semibold">{ticket.ticket_type}</p>
        <p className="truncate text-xs text-slate-400">{event.title}</p>
        <p className="mt-1 text-xs font-medium text-slate-500">{used ? "✓ Checked in" : "Tap to enlarge"}</p>
      </div>
    </button>
  );
}

function TicketModal({ ticket, event, onClose }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/60 p-4" onClick={onClose}>
      <div className="card w-full max-w-xs p-6 text-center" onClick={(e) => e.stopPropagation()}>
        <p className="text-sm font-medium text-brand-600">{ticket.ticket_type}</p>
        <h3 className="font-semibold">{event.title}</h3>
        <p className="text-xs text-slate-400">{formatDateTime(event.starts_at)}</p>
        <div className="my-5 flex justify-center">
          <QRCodeSVG value={ticket.code} size={220} level="M" includeMargin />
        </div>
        <p className="break-all font-mono text-[10px] text-slate-400">{ticket.code}</p>
        <p className="mt-3 text-sm text-slate-500">Show this at the entrance. Turn your screen brightness up.</p>
        <button className="btn-secondary mt-4 w-full" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}

export default function MyTickets() {
  const { data: orders, loading } = useFetch("/orders/");
  const [open, setOpen] = useState(null);

  if (loading) return <Spinner />;

  const paid = orders.filter((o) => o.status === "paid");
  const pending = orders.filter((o) => o.status === "pending" && minutesLeft(o.expires_at) > 0);
  const history = orders.filter((o) => !paid.includes(o) && !pending.includes(o));

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 text-2xl font-bold">My tickets</h1>

      {pending.map((order) => (
        <div key={order.reference} className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <div>
            <p className="font-medium text-amber-900">
              Finish paying for {orderTotalLabel(order.items)} to {order.event.title}
            </p>
            <p className="text-sm text-amber-700">Held for {minutesLeft(order.expires_at)} more minutes · {formatNaira(order.total)}</p>
          </div>
          <a href={order.authorization_url} className="btn-primary">
            Complete payment
          </a>
        </div>
      ))}

      {paid.length === 0 && pending.length === 0 && (
        <Empty title="No tickets yet">
          <Link to="/" className="font-medium text-brand-600 hover:underline">
            Browse upcoming events
          </Link>
        </Empty>
      )}

      <div className="space-y-8">
        {paid.map((order) => (
          <section key={order.reference}>
            <div className="mb-3 flex items-center gap-3">
              <DateBadge iso={order.event.starts_at} />
              <div className="min-w-0 flex-1">
                <Link to={`/events/${order.event.slug}`} className="font-semibold hover:text-brand-700">
                  {order.event.title}
                </Link>
                <p className="text-sm text-slate-500">
                  {formatDateTime(order.event.starts_at)} · {order.event.venue}
                </p>
              </div>
              <span className="hidden text-xs text-slate-400 sm:block">{order.reference}</span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {order.tickets.map((ticket) => (
                <TicketCard key={ticket.code} ticket={ticket} event={order.event} onOpen={(t) => setOpen({ ticket: t, event: order.event })} />
              ))}
            </div>
          </section>
        ))}
      </div>

      {history.length > 0 && (
        <details className="mt-10">
          <summary className="cursor-pointer text-sm font-medium text-slate-500">Other orders ({history.length})</summary>
          <ul className="card mt-3 divide-y divide-slate-100">
            {history.map((order) => {
              const status = order.status === "pending" ? ORDER_STATUS.expired : ORDER_STATUS[order.status];
              return (
                <li key={order.reference} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                  <span className="min-w-0 truncate">
                    {order.event.title} · {orderTotalLabel(order.items)}
                  </span>
                  <Badge className={status.className}>{status.label}</Badge>
                </li>
              );
            })}
          </ul>
        </details>
      )}

      {open && <TicketModal {...open} onClose={() => setOpen(null)} />}
    </div>
  );
}

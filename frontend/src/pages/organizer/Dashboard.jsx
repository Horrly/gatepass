import { Link } from "react-router-dom";
import { Badge, DateBadge, Empty, Spinner } from "../../components/ui";
import { formatDateTime } from "../../lib/format";
import { useFetch } from "../../lib/useFetch";

function statusOf(event) {
  if (!event.is_published) return { label: "Draft", className: "bg-slate-100 text-slate-600" };
  if (event.has_ended) return { label: "Ended", className: "bg-slate-100 text-slate-500" };
  if (event.is_sold_out) return { label: "Sold out", className: "bg-violet-50 text-violet-700" };
  return { label: "On sale", className: "bg-emerald-50 text-emerald-700" };
}

export default function Dashboard() {
  const { data: events, loading } = useFetch("/events/mine/");

  return (
    <div>
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Your events</h1>
          <p className="text-sm text-slate-500">Create events, track sales and check guests in.</p>
        </div>
        <Link to="/organize/new" className="btn-primary">
          + New event
        </Link>
      </div>

      {loading ? (
        <Spinner />
      ) : events.length === 0 ? (
        <Empty icon="🎪" title="You haven't created any events">
          <Link to="/organize/new" className="font-medium text-brand-600 hover:underline">
            Create your first event
          </Link>
        </Empty>
      ) : (
        <ul className="card divide-y divide-slate-100">
          {events.map((event) => {
            const status = statusOf(event);
            const capacity = event.ticket_types.reduce((n, t) => n + t.quantity, 0);
            const taken = event.ticket_types.reduce((n, t) => n + t.reserved, 0);
            return (
              <li key={event.slug} className="flex flex-wrap items-center gap-4 p-4">
                <DateBadge iso={event.starts_at} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Link to={`/organize/${event.slug}`} className="truncate font-semibold hover:text-brand-700">
                      {event.title}
                    </Link>
                    <Badge className={status.className}>{status.label}</Badge>
                  </div>
                  <p className="text-sm text-slate-500">
                    {formatDateTime(event.starts_at)} · {event.city}
                  </p>
                </div>
                <div className="text-right text-sm">
                  <p className="font-semibold">
                    {taken} / {capacity}
                  </p>
                  <p className="text-xs text-slate-400">tickets taken</p>
                </div>
                <div className="flex gap-2">
                  <Link to={`/organize/${event.slug}/edit`} className="btn-secondary">
                    Edit
                  </Link>
                  <Link to={`/organize/${event.slug}`} className="btn-secondary">
                    Sales
                  </Link>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

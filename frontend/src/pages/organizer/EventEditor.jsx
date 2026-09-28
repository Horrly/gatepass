import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Empty, ErrorNote, Field, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import { formatNaira, fromLocalInput, nairaToKobo, toLocalInput } from "../../lib/format";

const EMPTY = { title: "", description: "", venue: "", city: "", starts_at: "", ends_at: "" };

function TicketRow({ ticket, onChanged }) {
  const [quantity, setQuantity] = useState(ticket.quantity);
  const [error, setError] = useState("");
  const dirty = Number(quantity) !== ticket.quantity;

  async function save() {
    setError("");
    try {
      await api(`/ticket-types/${ticket.id}/`, { method: "PATCH", body: { quantity: Number(quantity) } });
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete "${ticket.name}"?`)) return;
    try {
      await api(`/ticket-types/${ticket.id}/`, { method: "DELETE" });
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <tr className="align-top">
      <td className="py-3 pr-3">
        <p className="font-medium">{ticket.name}</p>
        {ticket.description && <p className="text-xs text-slate-400">{ticket.description}</p>}
        {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
      </td>
      <td className="py-3 pr-3 text-sm">{formatNaira(ticket.price)}</td>
      <td className="py-3 pr-3">
        <div className="flex items-center gap-2">
          <input className="input w-20" type="number" min={ticket.reserved || 1} value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          {dirty && (
            <button className="text-sm font-medium text-brand-600" onClick={save}>
              Save
            </button>
          )}
        </div>
        <p className="mt-1 text-xs text-slate-400">{ticket.reserved} taken</p>
      </td>
      <td className="py-3 text-right">
        {ticket.reserved === 0 && (
          <button className="text-sm text-slate-400 hover:text-rose-600" onClick={remove}>
            Delete
          </button>
        )}
      </td>
    </tr>
  );
}

function AddTicketForm({ slug, onAdded }) {
  const [form, setForm] = useState({ name: "", price: "", quantity: "", description: "" });
  const [error, setError] = useState("");
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    setError("");
    const price = form.price === "" ? 0 : nairaToKobo(form.price);
    if (Number.isNaN(price)) return setError("Enter a valid price.");
    try {
      await api(`/events/${slug}/ticket-types/`, {
        method: "POST",
        body: { name: form.name, description: form.description, price, quantity: Number(form.quantity) },
      });
      setForm({ name: "", price: "", quantity: "", description: "" });
      onAdded();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form onSubmit={submit} className="mt-4 rounded-xl bg-slate-50 p-4">
      <p className="mb-3 text-sm font-medium">Add a ticket type</p>
      <div className="grid gap-3 sm:grid-cols-[1fr_120px_100px]">
        <input className="input" placeholder="Name, e.g. VIP" value={form.name} onChange={set("name")} required />
        <input className="input" placeholder="Price (₦)" inputMode="decimal" value={form.price} onChange={set("price")} />
        <input className="input" placeholder="Quantity" type="number" min="1" value={form.quantity} onChange={set("quantity")} required />
      </div>
      <input className="input mt-3" placeholder="Short description (optional)" value={form.description} onChange={set("description")} />
      <p className="mt-2 text-xs text-slate-400">Leave the price empty for a free ticket. Paid tickets start at ₦100.</p>
      <div className="mt-3 flex items-center gap-3">
        <button className="btn-primary">Add ticket</button>
        {error && <span className="text-sm text-rose-600">{error}</span>}
      </div>
    </form>
  );
}

export default function EventEditor() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [event, setEvent] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [loading, setLoading] = useState(Boolean(slug));
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function load() {
    const data = await api(`/events/${slug}/`);
    setEvent(data);
    setForm({
      title: data.title,
      description: data.description,
      venue: data.venue,
      city: data.city,
      starts_at: toLocalInput(data.starts_at),
      ends_at: toLocalInput(data.ends_at),
    });
  }

  useEffect(() => {
    if (!slug) return;
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  const set = (key) => (e) => {
    setSaved(false);
    setForm((f) => ({ ...f, [key]: e.target.value }));
  };

  async function save(e) {
    e.preventDefault();
    setError("");
    const body = { ...form, starts_at: fromLocalInput(form.starts_at), ends_at: fromLocalInput(form.ends_at) };
    // Don't resend an unchanged start time: it may be in the past for a running event.
    if (event && new Date(body.starts_at).getTime() === new Date(event.starts_at).getTime()) delete body.starts_at;
    try {
      if (event) {
        setEvent(await api(`/events/${event.slug}/`, { method: "PATCH", body }));
        setSaved(true);
      } else {
        const created = await api("/events/", { method: "POST", body });
        navigate(`/organize/${created.slug}/edit`, { replace: true });
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function togglePublish() {
    setError("");
    try {
      setEvent(await api(`/events/${event.slug}/`, { method: "PATCH", body: { is_published: !event.is_published } }));
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) return <Spinner />;
  if (event && !event.is_organizer) return <Empty icon="🔒" title="You can only edit your own events" />;

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/organize" className="text-sm text-slate-500 hover:text-slate-800">
        ← Your events
      </Link>
      <div className="mb-6 mt-2 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{event ? "Edit event" : "New event"}</h1>
        {event && (
          <div className="flex gap-2">
            <Link to={`/events/${event.slug}`} className="btn-secondary">
              Preview
            </Link>
            <button onClick={togglePublish} className={event.is_published ? "btn-secondary" : "btn-primary"}>
              {event.is_published ? "Unpublish" : "Publish"}
            </button>
          </div>
        )}
      </div>

      {event && (
        <p className={`mb-4 rounded-lg px-3 py-2 text-sm ${event.is_published ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>
          {event.is_published ? "Published — tickets are on sale." : "Draft — add tickets, then publish to start selling."}
        </p>
      )}

      <form onSubmit={save} className="card space-y-4 p-6">
        <Field label="Event name">
          <input className="input" value={form.title} onChange={set("title")} required maxLength={120} />
        </Field>
        <Field label="Description">
          <textarea className="input min-h-28" value={form.description} onChange={set("description")} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Venue">
            <input className="input" value={form.venue} onChange={set("venue")} required />
          </Field>
          <Field label="City">
            <input className="input" value={form.city} onChange={set("city")} required />
          </Field>
          <Field label="Starts">
            <input className="input" type="datetime-local" value={form.starts_at} onChange={set("starts_at")} required />
          </Field>
          <Field label="Ends" hint="Optional">
            <input className="input" type="datetime-local" value={form.ends_at} onChange={set("ends_at")} />
          </Field>
        </div>
        <ErrorNote>{error}</ErrorNote>
        <div className="flex items-center gap-3">
          <button className="btn-primary">{event ? "Save changes" : "Create event"}</button>
          {saved && <span className="text-sm text-emerald-600">Saved</span>}
        </div>
      </form>

      {event ? (
        <section className="card mt-6 p-6">
          <h2 className="font-semibold">Tickets</h2>
          {event.ticket_types.length > 0 && (
            <table className="mt-3 w-full text-left">
              <thead className="text-xs uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="pb-2 font-medium">Type</th>
                  <th className="pb-2 font-medium">Price</th>
                  <th className="pb-2 font-medium">Quantity</th>
                  <th />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {event.ticket_types.map((t) => (
                  <TicketRow key={`${t.id}-${t.quantity}`} ticket={t} onChanged={load} />
                ))}
              </tbody>
            </table>
          )}
          <AddTicketForm slug={event.slug} onAdded={load} />
        </section>
      ) : (
        <p className="mt-4 text-sm text-slate-500">You'll add ticket types after creating the event.</p>
      )}
    </div>
  );
}

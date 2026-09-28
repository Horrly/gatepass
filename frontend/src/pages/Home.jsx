import { useEffect, useState } from "react";
import { Empty, EventCard, Spinner } from "../components/ui";
import { useFetch } from "../lib/useFetch";

export default function Home() {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

  const { data: events, loading, error } = useFetch(`/events/${debounced ? `?q=${encodeURIComponent(debounced)}` : ""}`);

  return (
    <>
      <section className="mb-10 overflow-hidden rounded-3xl bg-gradient-to-br from-brand-600 to-violet-600 px-6 py-12 text-white md:px-12">
        <h1 className="max-w-xl text-3xl font-bold leading-tight md:text-4xl">Find your next event. Get in with one scan.</h1>
        <p className="mt-3 max-w-lg text-brand-100">
          Concerts, meetups and hackathons across Nigeria. Pay securely with Paystack and keep your QR tickets on your phone.
        </p>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search events, venues or cities"
          className="mt-6 w-full max-w-md rounded-xl border-0 bg-white px-4 py-3 text-sm text-slate-800 outline-none ring-4 ring-white/20"
        />
      </section>

      <h2 className="mb-4 text-lg font-semibold">Upcoming events</h2>
      {loading && !events ? (
        <Spinner />
      ) : error ? (
        <Empty icon="⚠️" title="Couldn't load events">{error.message}</Empty>
      ) : events.length === 0 ? (
        <Empty title={debounced ? "No events match your search" : "No upcoming events yet"}>
          {debounced ? "Try another city or keyword." : "Check back soon, or create one from the Organize tab."}
        </Empty>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {events.map((event) => (
            <EventCard key={event.slug} event={event} />
          ))}
        </div>
      )}
    </>
  );
}

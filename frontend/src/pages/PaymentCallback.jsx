import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Empty, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { formatNaira, orderTotalLabel } from "../lib/format";

const POLL_MS = 2000;
const MAX_POLLS = 15;

/**
 * Paystack sends the buyer here after checkout (?reference=...). We ask our
 * backend to verify with Paystack; if the result isn't final yet, we poll
 * briefly — the webhook often confirms the payment a moment later.
 */
export default function PaymentCallback() {
  const [params] = useSearchParams();
  const reference = params.get("reference") || params.get("trxref");
  const [order, setOrder] = useState(null);
  const [error, setError] = useState("");
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    if (!reference) return;
    let cancelled = false;
    let polls = 0;
    let timer;

    async function check() {
      try {
        const result = await api("/payments/verify/", { method: "POST", body: { reference } });
        if (cancelled) return;
        setOrder(result);
        if (result.status === "pending") {
          if (++polls < MAX_POLLS) timer = setTimeout(check, POLL_MS);
          else setGaveUp(true);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }
    check();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [reference]);

  if (!reference) return <Empty icon="🤔" title="No payment reference">Open this page from the checkout.</Empty>;
  if (error) return <Empty icon="⚠️" title="We couldn't check your payment">{error}</Empty>;
  if (!order || (order.status === "pending" && !gaveUp)) return <Spinner label="Confirming your payment with Paystack…" />;

  const content = {
    paid: {
      icon: "🎉",
      title: "You're going!",
      body: `${orderTotalLabel(order.items)} for ${order.event.title}. We've emailed them to ${order.email}.`,
    },
    failed: { icon: "❌", title: "Payment didn't go through", body: "No money was taken for these tickets. You can try again." },
    expired: { icon: "⌛", title: "Your reservation expired", body: "The tickets were released. You can start a new order." },
    pending: {
      icon: "⏳",
      title: "Still waiting for confirmation",
      body: "If you completed the payment, your tickets will appear in My tickets shortly.",
    },
  }[order.status];

  return (
    <div className="mx-auto max-w-md text-center">
      <div className="card p-8">
        <div className="text-5xl">{content.icon}</div>
        <h1 className="mt-4 text-2xl font-bold">{content.title}</h1>
        <p className="mt-2 text-slate-500">{content.body}</p>
        <p className="mt-4 text-sm text-slate-400">
          Order {order.reference} · {formatNaira(order.total)}
        </p>
        <div className="mt-6 flex justify-center gap-2">
          {order.status === "paid" || order.status === "pending" ? (
            <Link to="/tickets" className="btn-primary">
              View my tickets
            </Link>
          ) : (
            <Link to={`/events/${order.event.slug}`} className="btn-primary">
              Back to event
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Empty, ErrorNote, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { formatNaira } from "../lib/format";
import { useFetch } from "../lib/useFetch";

/**
 * Stand-in for Paystack's checkout page, used when the server has no Paystack
 * key (local development and the public demo). It is clearly labelled and no
 * real money moves.
 */
export default function SimulatePayment() {
  const [params] = useSearchParams();
  const reference = params.get("reference");
  const navigate = useNavigate();
  const { data: order, loading, error } = useFetch(reference ? `/orders/${reference}/` : null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");

  async function simulate(outcome) {
    setBusy(true);
    try {
      await api("/payments/simulate/", { method: "POST", body: { reference, outcome } });
      navigate(`/payment/callback?reference=${reference}`, { replace: true });
    } catch (err) {
      setFailure(err.message);
      setBusy(false);
    }
  }

  if (loading) return <Spinner />;
  if (error || !order) return <Empty icon="⚠️" title="Order not found" />;

  return (
    <div className="mx-auto max-w-sm">
      <div className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-center text-xs font-medium text-amber-800">
        Test mode · simulated Paystack checkout · no real money is charged
      </div>
      <div className="card overflow-hidden">
        <div className="bg-slate-900 px-6 py-5 text-white">
          <p className="text-xs uppercase tracking-wide text-slate-400">Pay Gatepass</p>
          <p className="mt-1 text-3xl font-bold">{formatNaira(order.total)}</p>
          <p className="mt-1 text-sm text-slate-400">{order.email}</p>
        </div>
        <div className="space-y-2 p-6">
          {order.items.map((item) => (
            <div key={item.ticket_type} className="flex justify-between text-sm">
              <span>
                {item.quantity} × {item.ticket_type}
              </span>
              <span className="text-slate-500">{formatNaira(item.unit_price * item.quantity)}</span>
            </div>
          ))}
          <p className="pt-2 text-xs text-slate-400">{order.event.title} · {order.reference}</p>

          {order.status !== "pending" ? (
            <p className="pt-4 text-sm text-slate-500">This order is already {order.status}.</p>
          ) : (
            <div className="space-y-2 pt-4">
              <ErrorNote>{failure}</ErrorNote>
              <button className="btn w-full bg-emerald-600 py-3 text-white hover:bg-emerald-700" disabled={busy} onClick={() => simulate("success")}>
                Pay {formatNaira(order.total)}
              </button>
              <button className="btn-secondary w-full" disabled={busy} onClick={() => simulate("failed")}>
                Simulate a declined card
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

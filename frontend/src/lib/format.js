// Money is stored in kobo (₦1 = 100 kobo) everywhere; convert only for display.

const naira = new Intl.NumberFormat("en-NG", {
  style: "currency",
  currency: "NGN",
  maximumFractionDigits: 2,
  minimumFractionDigits: 0,
});

export function formatNaira(kobo) {
  if (kobo === null || kobo === undefined) return "";
  if (kobo === 0) return "Free";
  return naira.format(kobo / 100);
}

export function nairaToKobo(value) {
  const n = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(n) ? Math.round(n * 100) : NaN;
}

export function formatDateTime(iso) {
  return new Date(iso).toLocaleString("en-NG", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function dateBadge(iso) {
  const d = new Date(iso);
  return {
    day: d.toLocaleDateString("en-NG", { day: "numeric" }),
    month: d.toLocaleDateString("en-NG", { month: "short" }).toUpperCase(),
  };
}

// <input type="datetime-local"> works in local time without a zone: "2026-10-10T18:00".
export function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fromLocalInput(value) {
  return value ? new Date(value).toISOString() : null;
}

export function minutesLeft(iso, now = Date.now()) {
  return Math.max(0, Math.ceil((new Date(iso) - now) / 60000));
}

export const ORDER_STATUS = {
  paid: { label: "Paid", className: "bg-emerald-50 text-emerald-700" },
  pending: { label: "Awaiting payment", className: "bg-amber-50 text-amber-700" },
  failed: { label: "Payment failed", className: "bg-rose-50 text-rose-700" },
  expired: { label: "Expired", className: "bg-slate-100 text-slate-500" },
};

export function orderTotalLabel(items) {
  const count = items.reduce((n, i) => n + i.quantity, 0);
  return `${count} ticket${count === 1 ? "" : "s"}`;
}

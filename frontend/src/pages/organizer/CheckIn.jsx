import { Html5Qrcode } from "html5-qrcode";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { useFetch } from "../../lib/useFetch";

const RESULT_STYLES = {
  ok: { box: "border-emerald-300 bg-emerald-50", title: "text-emerald-800", icon: "✅", heading: "Admit" },
  already_checked_in: { box: "border-amber-300 bg-amber-50", title: "text-amber-800", icon: "⚠️", heading: "Already used" },
  wrong_event: { box: "border-rose-300 bg-rose-50", title: "text-rose-800", icon: "⛔", heading: "Wrong event" },
  invalid: { box: "border-rose-300 bg-rose-50", title: "text-rose-800", icon: "⛔", heading: "Invalid ticket" },
};

const SCAN_COOLDOWN_MS = 2500;

export default function CheckIn() {
  const { slug } = useParams();
  const { data: event } = useFetch(`/events/${slug}/`);
  const [result, setResult] = useState(null);
  const [manual, setManual] = useState("");
  const [admitted, setAdmitted] = useState(0);
  const [cameraOn, setCameraOn] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const scannerRef = useRef(null);
  const lastScan = useRef({ code: null, at: 0 });

  const submit = useCallback(
    async (code) => {
      code = code.trim();
      if (!code) return;
      // The camera sees the same QR many times per second; ignore repeats briefly.
      const now = Date.now();
      if (code === lastScan.current.code && now - lastScan.current.at < SCAN_COOLDOWN_MS) return;
      lastScan.current = { code, at: now };
      try {
        const res = await api(`/events/${slug}/checkin/`, { method: "POST", body: { code } });
        setResult(res);
        if (res.result === "ok") setAdmitted((n) => n + 1);
        navigator.vibrate?.(res.result === "ok" ? 80 : [60, 60, 60]);
      } catch (err) {
        setResult({ result: "invalid", detail: err.message });
      }
    },
    [slug],
  );

  async function startCamera() {
    setCameraError("");
    try {
      const scanner = new Html5Qrcode("qr-reader");
      scannerRef.current = scanner;
      await scanner.start({ facingMode: "environment" }, { fps: 8, qrbox: { width: 240, height: 240 } }, submit, () => {});
      setCameraOn(true);
    } catch (err) {
      setCameraError("Couldn't open the camera. Allow camera access, or type the code below.");
      scannerRef.current = null;
    }
  }

  async function stopCamera() {
    try {
      await scannerRef.current?.stop();
    } catch {
      /* already stopped */
    }
    scannerRef.current = null;
    setCameraOn(false);
  }

  useEffect(() => () => void stopCamera(), []);

  const style = result && RESULT_STYLES[result.result];

  return (
    <div className="mx-auto max-w-lg">
      <Link to={`/organize/${slug}`} className="text-sm text-slate-500 hover:text-slate-800">
        ← Sales
      </Link>
      <div className="mb-6 mt-2 flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Check in</h1>
          <p className="text-sm text-slate-500">{event?.title}</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-emerald-600">{admitted}</p>
          <p className="text-xs text-slate-400">admitted this session</p>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div id="qr-reader" className={cameraOn ? "" : "hidden"} />
        <div className="p-4">
          {cameraOn ? (
            <button className="btn-secondary w-full" onClick={stopCamera}>
              Stop camera
            </button>
          ) : (
            <button className="btn-primary w-full py-3" onClick={startCamera}>
              📷 Scan tickets with camera
            </button>
          )}
          {cameraError && <p className="mt-2 text-sm text-rose-600">{cameraError}</p>}

          <form
            className="mt-4 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              lastScan.current = { code: null, at: 0 };
              submit(manual);
              setManual("");
            }}
          >
            <input className="input font-mono" placeholder="Or paste a ticket code" value={manual} onChange={(e) => setManual(e.target.value)} />
            <button className="btn-secondary">Check</button>
          </form>
        </div>
      </div>

      {result && style && (
        <div className={`mt-6 rounded-2xl border-2 p-6 text-center ${style.box}`} role="status" data-testid="checkin-result">
          <div className="text-4xl">{style.icon}</div>
          <p className={`mt-2 text-2xl font-bold ${style.title}`}>{style.heading}</p>
          <p className="mt-1 text-sm text-slate-600">{result.detail}</p>
          {result.ticket && (
            <p className="mt-3 text-sm">
              <strong>{result.ticket.ticket_type}</strong> · {result.ticket.holder} · {result.ticket.order}
              {result.result === "already_checked_in" && (
                <span className="block text-xs text-slate-500">First scanned {formatDateTime(result.ticket.checked_in_at)}</span>
              )}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

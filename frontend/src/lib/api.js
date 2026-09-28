// Thin fetch wrapper: attaches the JWT, refreshes it once on 401, and
// signs the user out if the refresh token has expired too.

const ACCESS = "gatepass.access";
const REFRESH = "gatepass.refresh";

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS);
  },
  get refresh() {
    return localStorage.getItem(REFRESH);
  },
  set({ access, refresh }) {
    if (access) localStorage.setItem(ACCESS, access);
    if (refresh) localStorage.setItem(REFRESH, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
  },
};

export class ApiError extends Error {
  constructor(status, data) {
    super(firstErrorMessage(data) || `Request failed (${status})`);
    this.status = status;
    this.data = data;
  }
}

// DRF errors look like {"detail": "..."} or {"field": ["msg", ...]}.
export function firstErrorMessage(data) {
  if (!data || typeof data !== "object") return null;
  if (typeof data.detail === "string") return data.detail;
  for (const [field, value] of Object.entries(data)) {
    const msg = Array.isArray(value) ? value[0] : value;
    if (typeof msg === "string") {
      return field === "non_field_errors" ? msg : `${field}: ${msg}`;
    }
  }
  return null;
}

let refreshing = null;

async function refreshAccessToken() {
  if (!tokens.refresh) return false;
  // Share one in-flight refresh between parallel requests.
  refreshing ??= fetch("/api/auth/refresh/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: tokens.refresh }),
  })
    .then(async (res) => {
      if (!res.ok) return false;
      tokens.set(await res.json());
      return true;
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

export async function api(path, { method = "GET", body, auth = true, retry = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && auth && retry) {
    if (await refreshAccessToken()) return api(path, { method, body, auth, retry: false });
    tokens.clear();
    window.dispatchEvent(new Event("gatepass:logout"));
  }

  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}


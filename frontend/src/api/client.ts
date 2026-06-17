// API base URL is configurable via .env (VITE_API_BASE_URL). In dev the Vite
// proxy maps "/api" -> backend; in production nginx does the same. We never put
// API keys here — those stay server-side only.
export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

const AUTH_TOKEN_KEY = "orchestra_auth_token";

export function getAuthToken(): string {
  return localStorage.getItem(AUTH_TOKEN_KEY) ?? "";
}

export function setAuthToken(token: string): void {
  if (token.trim()) localStorage.setItem(AUTH_TOKEN_KEY, token.trim());
  else localStorage.removeItem(AUTH_TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-Orchestra-Token": token } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(0, "Netzwerkfehler — läuft das Backend?");
  }

  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const data = await res.json();
      const raw = data?.detail;
      if (typeof raw === "string") detail = raw;
      else if (Array.isArray(raw)) {
        detail = raw.map((item) => item?.msg ?? JSON.stringify(item)).join("; ");
      } else if (raw != null) {
        detail = JSON.stringify(raw);
      } else {
        detail = JSON.stringify(data);
      }
    } catch {
      detail = (await res.text().catch(() => "")) || res.statusText;
    }
    if (res.status === 502) {
      detail = "Backend vorübergehend nicht erreichbar (Bad Gateway). Bitte in wenigen Sekunden erneut versuchen.";
    } else if (res.status === 503) {
      detail = "Backend vorübergehend nicht verfügbar. Bitte später erneut versuchen.";
    } else if (res.status === 504) {
      detail = "Zeitüberschreitung beim Backend — die Analyse dauert möglicherweise zu lange.";
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Build the WebSocket URL for a session, honoring API_BASE host if absolute. */
export function sessionSocketUrl(sessionId: string): string {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  // If API_BASE is an absolute URL, derive host from it; else use current host.
  let host = location.host;
  try {
    if (/^https?:\/\//i.test(API_BASE)) {
      host = new URL(API_BASE).host;
    }
  } catch {
    /* keep current host */
  }
  return `${proto}//${host}/ws/sessions/${sessionId}`;
}

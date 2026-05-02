const DEV_DEFAULT_API_ORIGIN = "http://localhost:5000";

// Precedence:
// 1) Explicit override
// 2) Vercel Services auto-injected routePrefix for the `backend` service
// 3) Local dev default
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_BACKEND_URL ??
  DEV_DEFAULT_API_ORIGIN;

export async function apiGet<T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined | null>,
): Promise<T> {
  const base = API_BASE_URL;
  const isAbsolute = /^https?:\/\//i.test(base);
  const origin =
    typeof window !== "undefined" ? window.location.origin : DEV_DEFAULT_API_ORIGIN;

  const normalizedBase = base.endsWith("/") ? base.slice(0, -1) : base;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  const url = isAbsolute
    ? new URL(normalizedPath, normalizedBase)
    : new URL(`${normalizedBase}${normalizedPath}`, origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === "") continue;
      url.searchParams.set(k, String(v));
    }
  }

  const res = await fetch(url.toString(), {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return (await res.json()) as T;
}

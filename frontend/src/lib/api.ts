"use client";

export const API_BASE = "/api";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function cookieValue(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie.split("; ").find((part) => part.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : undefined;
}

function requestHeaders(options: RequestInit): Headers {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && options.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const method = (options.method || "GET").toUpperCase();
  if (!SAFE_METHODS.has(method) && !headers.has("X-CSRF-Token")) {
    const csrf = cookieValue("risklocker_csrf");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  return headers;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = requestHeaders(options);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      credentials: "include",
      cache: "no-store",
    });
  } catch (err) {
    if (process.env.NODE_ENV !== "production") {
      console.error(`[api] network error: ${path}`, err);
    }
    throw new Error("Network error. Check if the backend is running.");
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof payload === "object" ? payload?.error?.message || "Something went wrong." : String(payload);
    if (process.env.NODE_ENV !== "production") {
      console.error(`[api] ${response.status} ${path}: ${message}`);
    }
    throw new Error(message);
  }
  return payload as T;
}

export async function apiRaw(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = requestHeaders(options);
  return fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
    cache: "no-store",
  });
}

export function fileUrl(path: string) {
  return `${API_BASE}${path}`;
}

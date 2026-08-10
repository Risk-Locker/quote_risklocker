"use client";

import { beginRequest, endRequest } from "@/lib/activity";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (typeof window !== "undefined"
    ? `http://${window.location.hostname}:8100`
    : "http://127.0.0.1:8100");

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  beginRequest();
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      credentials: "include",
      cache: "no-store"
    });
  } catch (err) {
    if (process.env.NODE_ENV !== "production") {
      console.error(`[api] network error: ${path}`, err);
    }
    throw new Error("Network error. Check if the backend is running.");
  } finally {
    endRequest();
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
  beginRequest();
  try {
    return await fetch(`${API_BASE}${path}`, {
      ...options,
      credentials: "include",
      cache: "no-store",
    });
  } finally {
    endRequest();
  }
}

export function fileUrl(path: string) {
  return `${API_BASE}${path}`;
}

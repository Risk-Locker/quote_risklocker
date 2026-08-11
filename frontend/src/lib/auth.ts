"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "./api";

export type User = {
  id: string;
  email: string;
  role: string;
  name?: string;
  status?: string;
};

let cachedUser: User | null | undefined;
let cacheTime = 0;
const CACHE_MS = 300_000;

export function clearAuthCache() {
  cachedUser = undefined;
  cacheTime = 0;
}

export function useAuth() {
  const [user, setUser] = useState<User | null | undefined>(
    cacheTime && Date.now() - cacheTime < CACHE_MS ? cachedUser : undefined
  );

  useEffect(() => {
    if (cacheTime && Date.now() - cacheTime < CACHE_MS) {
      setUser(cachedUser);
      return;
    }
    let cancelled = false;
    fetch(`${API_BASE}/auth/me`, { credentials: "include", cache: "no-store" })
      .then(async (response) => {
        if (cancelled) return;
        if (response.ok) {
          const data = await response.json();
          cachedUser = data as User;
          cacheTime = Date.now();
          setUser(cachedUser);
        } else {
          // Never cache a negative (logged-out) result: a fresh login in the
          // same session would otherwise keep bouncing back to /login for the
          // cache window. Only successful responses are cached.
          setUser(null);
        }
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    // Re-validate when a page is restored from the browser back/forward cache
    // (bfcache): a logged-out user could otherwise keep seeing a protected
    // page after pressing Back without any navigation event firing.
    function onPageshow(event: PageTransitionEvent) {
      if (!event.persisted) return;
      clearAuthCache();
      fetch(`${API_BASE}/auth/me`, { credentials: "include", cache: "no-store" })
        .then(async (response) => {
          if (response.ok) {
            const data = await response.json();
            cachedUser = data as User;
            cacheTime = Date.now();
            setUser(cachedUser);
          } else {
            setUser(null);
          }
        })
        .catch(() => setUser(null));
    }
    window.addEventListener("pageshow", onPageshow);
    return () => window.removeEventListener("pageshow", onPageshow);
  }, []);

  return { user, loading: user === undefined };
}

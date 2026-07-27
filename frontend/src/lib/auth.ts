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

export function useAuth() {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/auth/me`, { credentials: "include", cache: "no-store" })
      .then(async (response) => {
        if (cancelled) return;
        if (response.ok) {
          const data = await response.json();
          setUser(data as User);
        } else {
          setUser(null);
        }
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { user, loading: user === undefined };
}

/**
 * Navigation state persistence and retrieval utilities.
 * Allows preserving user's last visited workspace / tab across browser refreshes
 * and managing history state transitions.
 */

export interface BuilderNavigationState {
  companyId?: string;
  productId?: string;
  catalogId?: string;
  screenTab?: "company_benefits" | "catalogs" | "conditions" | "matrix";
  updatedAt?: number;
}

const STORAGE_KEY = "rl_builder_navigation_state";

export function saveBuilderState(state: Partial<BuilderNavigationState>): void {
  if (typeof window === "undefined") return;
  try {
    const existing = loadBuilderState() || {};
    const merged: BuilderNavigationState = {
      ...existing,
      ...state,
      updatedAt: Date.now(),
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
  } catch {
    // Best-effort storage fallback (e.g. storage quota, private browsing mode)
  }
}

export function loadBuilderState(): BuilderNavigationState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as BuilderNavigationState;
  } catch {
    return null;
  }
}

export function clearBuilderState(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Best-effort fallback
  }
}

// Staged Uploads Durable Storage (IndexedDB + localStorage fallback)
// Preserves staged PDFs and in-flight quotation session jobs across tab reloads, crashes, and network reconnects.

export interface StoredStagedItem {
  id: string;
  file: File;
  status: "staged" | "uploading" | "processing" | "completed" | "failed";
  progress: number;
  phase?: string;
  sessionId?: string;
  jobId?: string;
  tenureId?: string;
  plate?: string;
  insurer?: string;
  premium?: string | number;
  ref?: string;
  error?: string;
  updatedAt?: number;
}

const DB_NAME = "rl_staged_uploads_v2_db";
const STORE_NAME = "staged_queue";
const DB_VERSION = 1;
const LS_KEY = "rl_staged_uploads_v2";
const MAX_AGE_MS = 24 * 60 * 60 * 1000; // 24 hours retention

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function openDb(): Promise<IDBDatabase | null> {
  if (!isBrowser() || !("indexedDB" in window)) return Promise.resolve(null);
  return new Promise((resolve) => {
    try {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: "id" });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => {
        console.warn("[staged-storage] Failed to open IndexedDB", request.error);
        resolve(null);
      };
    } catch {
      resolve(null);
    }
  });
}

export async function saveStagedQueue(items: StoredStagedItem[]): Promise<void> {
  if (!isBrowser()) return;

  const now = Date.now();
  // 1. Sync metadata to localStorage for instant synchronous inspection
  try {
    const metaList = items.map((i) => ({
      id: i.id,
      name: i.file?.name || "quotation.pdf",
      size: i.file?.size || 0,
      type: i.file?.type || "application/pdf",
      status: i.status,
      progress: i.progress,
      phase: i.phase,
      sessionId: i.sessionId,
      jobId: i.jobId,
      tenureId: i.tenureId,
      plate: i.plate,
      insurer: i.insurer,
      premium: i.premium,
      ref: i.ref,
      error: i.error,
      updatedAt: now,
    }));
    if (metaList.length === 0) {
      window.localStorage.removeItem(LS_KEY);
    } else {
      window.localStorage.setItem(LS_KEY, JSON.stringify(metaList));
    }
  } catch (err) {
    console.warn("[staged-storage] Failed to write localStorage", err);
  }

  // 2. Persist binary File objects to IndexedDB
  const db = await openDb();
  if (!db) return;

  try {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    store.clear();
    for (const item of items) {
      store.put({
        id: item.id,
        file: item.file,
        name: item.file?.name || "quotation.pdf",
        size: item.file?.size || 0,
        type: item.file?.type || "application/pdf",
        status: item.status,
        progress: item.progress,
        phase: item.phase,
        sessionId: item.sessionId,
        jobId: item.jobId,
        tenureId: item.tenureId,
        plate: item.plate,
        insurer: item.insurer,
        premium: item.premium,
        ref: item.ref,
        error: item.error,
        updatedAt: now,
      });
    }
  } catch (err) {
    console.warn("[staged-storage] Failed to write IndexedDB", err);
  }
}

export async function loadStagedQueue(): Promise<StoredStagedItem[]> {
  if (!isBrowser()) return [];

  const now = Date.now();
  // 1. Try reading from IndexedDB first (contains original binary File)
  const db = await openDb();
  if (db) {
    try {
      const records = await new Promise<any[]>((resolve) => {
        const tx = db.transaction(STORE_NAME, "readonly");
        const store = tx.objectStore(STORE_NAME);
        const req = store.getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => resolve([]);
      });

      if (records && records.length > 0) {
        const valid = records.filter((r) => !r.updatedAt || now - r.updatedAt < MAX_AGE_MS);
        if (valid.length > 0) {
          return valid.map((r) => {
            const fileObj =
              r.file instanceof File
                ? r.file
                : new File([r.file || ""], r.name || "quotation.pdf", {
                    type: r.type || "application/pdf",
                  });
            return {
              id: r.id,
              file: fileObj,
              status: r.status || "staged",
              progress: r.progress || 0,
              phase: r.phase,
              sessionId: r.sessionId,
              jobId: r.jobId,
              tenureId: r.tenureId,
              plate: r.plate,
              insurer: r.insurer,
              premium: r.premium,
              ref: r.ref,
              error: r.error,
              updatedAt: r.updatedAt,
            };
          });
        }
      }
    } catch (err) {
      console.warn("[staged-storage] Error reading IndexedDB", err);
    }
  }

  // 2. Fallback to localStorage metadata
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        const valid = parsed.filter((r: any) => !r.updatedAt || now - r.updatedAt < MAX_AGE_MS);
        return valid.map((r: any) => ({
          id: r.id,
          file: new File([], r.name || "quotation.pdf", { type: r.type || "application/pdf" }),
          status: r.status || "staged",
          progress: r.progress || 0,
          phase: r.phase,
          sessionId: r.sessionId,
          jobId: r.jobId,
          tenureId: r.tenureId,
          plate: r.plate,
          insurer: r.insurer,
          premium: r.premium,
          ref: r.ref,
          error: r.error,
          updatedAt: r.updatedAt,
        }));
      }
    }
  } catch (err) {
    console.warn("[staged-storage] Error reading localStorage", err);
  }

  return [];
}

export async function clearStagedQueue(): Promise<void> {
  if (!isBrowser()) return;
  try {
    window.localStorage.removeItem(LS_KEY);
  } catch {}

  const db = await openDb();
  if (!db) return;
  try {
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).clear();
  } catch {}
}

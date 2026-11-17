# Milestone 5: Marketing Comparison State Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` and `systematic-debugging` to execute this plan cleanly. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the perpetual "analyzing all the time ranking all the time" state in Marketing Comparison by adding a defensive fallback auto-dismiss timeout to `operationStatus`, hardening `isRescanning`/`reranking` state resets, and polishing the card bottom action footer.

**Architecture:**
1. **Defensive Timeout on Loading Toasts (`comparison-matrix.tsx:580`):**
   Replace the indefinite hanging loading state with a 45-second defensive timeout that automatically clears `operationStatus` if an async rescan/rerank promise hangs or fails silently.
2. **Strict Finally Resets:**
   Ensure `setRescanningQuoteId(null)`, `setIsRescanning(false)`, and `setReranking(false)` are always executed inside `finally` blocks, including when user navigates away or when component unmounts.
3. **Card Bottom Action Footer Polish (`UnderwriterQuoteCard.tsx:514`):**
   Cleanly delineate "Re-Analyze Quote" and "Pick as Winner" buttons so their state transitions are crystal-clear and never stuck in spinning state.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS.

---

### Task 1: Harden State Resets & Timeouts in Comparison Matrix

**Files:**
- Modify: `frontend/src/components/comparison/comparison-matrix.tsx:575-600`
- Modify: `frontend/src/components/comparison/comparison-matrix.tsx:895-930`
- Modify: `frontend/src/components/comparison/comparison-matrix.tsx:1085-1110`
- Modify: `frontend/src/components/comparison/components/UnderwriterQuoteCard.tsx:535-555`

- [x] **Step 1: Update `useEffect` for `operationStatus` in `comparison-matrix.tsx`**

```tsx
  useEffect(() => {
    if (!operationStatus) return;
    // Loading toasts auto-dismiss after 45s safety timeout to prevent stuck analyzing/ranking state
    const timeoutMs = operationStatus.type === "loading" ? 45000 : 30000;
    const timer = setTimeout(() => {
      setOperationStatus(null);
    }, timeoutMs);
    return () => clearTimeout(timer);
  }, [operationStatus]);
```

- [x] **Step 2: Guarantee reset in `handleRescanQuotes` and `handleRerank`**
Verify all catch blocks trigger `triggerStatus("error", ...)` and finally blocks reset loading states cleanly.

- [x] **Step 3: Run TypeScript compilation**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS with 0 errors

- [x] **Step 4: Commit Milestone 5 changes**

```bash
git add frontend/src/components/comparison/
git commit -m "fix(comparison): harden toast timeouts and eliminate stuck analyzing/ranking state"
```


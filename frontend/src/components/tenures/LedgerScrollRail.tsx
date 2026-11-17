"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { CaretLeft, CaretRight } from "@phosphor-icons/react";

interface LedgerScrollRailProps {
  scrollTargetRef: React.RefObject<HTMLDivElement | null>;
  recomputeDeps: unknown[];
}

/**
 * Viewport-sticky horizontal pan rail synced two-way with the ledger table scroll container.
 * Renders only when table scrollWidth exceeds clientWidth.
 */
export function LedgerScrollRail({ scrollTargetRef, recomputeDeps }: LedgerScrollRailProps) {
  const railRef = useRef<HTMLDivElement>(null);
  const syncingSourceRef = useRef<"table" | "rail" | null>(null);
  const [metrics, setMetrics] = useState({
    hasOverflow: false,
    scrollWidth: 0,
    canScrollLeft: false,
    canScrollRight: false,
  });

  const measure = useCallback(() => {
    const el = scrollTargetRef.current;
    if (!el) return;
    const hasOverflow = el.scrollWidth - el.clientWidth > 4;
    const canScrollLeft = el.scrollLeft > 4;
    const canScrollRight = el.scrollLeft + el.clientWidth < el.scrollWidth - 4;
    setMetrics((prev) =>
      prev.hasOverflow === hasOverflow &&
      prev.scrollWidth === el.scrollWidth &&
      prev.canScrollLeft === canScrollLeft &&
      prev.canScrollRight === canScrollRight
        ? prev
        : { hasOverflow, scrollWidth: el.scrollWidth, canScrollLeft, canScrollRight }
    );
    if (railRef.current && Math.abs(railRef.current.scrollLeft - el.scrollLeft) > 1) {
      railRef.current.scrollLeft = el.scrollLeft;
    }
  }, [scrollTargetRef]);

  useEffect(() => {
    measure();
    const el = scrollTargetRef.current;
    if (!el) return;

    const handleTableScroll = () => {
      if (syncingSourceRef.current === "rail") return;
      syncingSourceRef.current = "table";
      if (railRef.current) {
        railRef.current.scrollLeft = el.scrollLeft;
      }
      measure();
      requestAnimationFrame(() => {
        syncingSourceRef.current = null;
      });
    };

    el.addEventListener("scroll", handleTableScroll, { passive: true });

    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(measure);
      ro.observe(el);
      if (el.firstElementChild) {
        ro.observe(el.firstElementChild);
      }
    }
    window.addEventListener("resize", measure);

    return () => {
      el.removeEventListener("scroll", handleTableScroll);
      window.removeEventListener("resize", measure);
      ro?.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [measure, scrollTargetRef, ...recomputeDeps]);

  const handleRailScroll = () => {
    const el = scrollTargetRef.current;
    const rail = railRef.current;
    if (!el || !rail || syncingSourceRef.current === "table") return;
    syncingSourceRef.current = "rail";
    el.scrollLeft = rail.scrollLeft;
    measure();
    requestAnimationFrame(() => {
      syncingSourceRef.current = null;
    });
  };

  const panBy = (delta: number) => {
    scrollTargetRef.current?.scrollBy({ left: delta, behavior: "smooth" });
  };

  if (!metrics.hasOverflow) return null;

  return (
    <div
      data-testid="ledger-sticky-scroll-rail"
      className="sticky bottom-0 z-30 flex items-center gap-2 border-t border-[var(--rl-border)] bg-[#f9f9fb]/95 px-3 py-1.5 backdrop-blur-md"
    >
      <button
        type="button"
        onClick={() => panBy(-320)}
        disabled={!metrics.canScrollLeft}
        className="inline-flex shrink-0 items-center gap-1 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white px-2 py-1 text-[11px] font-semibold text-[var(--rl-text-strong)] hover:bg-neutral-100 transition-colors cursor-pointer disabled:opacity-35 disabled:cursor-not-allowed"
        title="Pan columns left"
        aria-label="Pan columns left"
      >
        <CaretLeft size={12} weight="bold" />
        <span>Left</span>
      </button>

      <div
        ref={railRef}
        onScroll={handleRailScroll}
        aria-label="Horizontal ledger column scrollbar"
        className="flex-1 overflow-x-auto scrollbar-thin py-0.5"
      >
        <div style={{ width: `${metrics.scrollWidth}px`, height: "6px" }} />
      </div>

      <button
        type="button"
        onClick={() => panBy(320)}
        disabled={!metrics.canScrollRight}
        className="inline-flex shrink-0 items-center gap-1 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white px-2 py-1 text-[11px] font-semibold text-[var(--rl-text-strong)] hover:bg-neutral-100 transition-colors cursor-pointer disabled:opacity-35 disabled:cursor-not-allowed"
        title="Pan columns right"
        aria-label="Pan columns right"
      >
        <span>Right</span>
        <CaretRight size={12} weight="bold" />
      </button>
    </div>
  );
}

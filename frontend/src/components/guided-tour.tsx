"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CaretLeft, CaretRight, Question, X } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";

export type TourStep = {
    /** CSS selector of the element to highlight (e.g. "#step-1" or ".some-class"). */
    target: string;
    title: string;
    body: string;
    position?: "top" | "bottom" | "left" | "right";
};

type GuidedTourProps = {
    /** localStorage key for "don't show again" (e.g. "tour:builder-benefits"). */
    storageKey: string;
    steps: TourStep[];
    title: string;
    description: string;
    launcherLabel?: string;
};

const TOOLTIP_WIDTH = 320;

function tooltipStyle(rect: DOMRect, position: string): React.CSSProperties {
    const gap = 12;
    switch (position) {
        case "top":
            return { left: rect.left + rect.width / 2 - TOOLTIP_WIDTH / 2, top: rect.top - gap - 120, width: TOOLTIP_WIDTH };
        case "left":
            return { left: rect.left - gap - TOOLTIP_WIDTH, top: rect.top + rect.height / 2 - 60, width: TOOLTIP_WIDTH };
        case "right":
            return { left: rect.right + gap, top: rect.top + rect.height / 2 - 60, width: TOOLTIP_WIDTH };
        default:
            return { left: rect.left + rect.width / 2 - TOOLTIP_WIDTH / 2, top: rect.bottom + gap, width: TOOLTIP_WIDTH };
    }
}

export function GuidedTour({ storageKey, steps, title, description, launcherLabel = "How this page works" }: GuidedTourProps) {
    const [panelOpen, setPanelOpen] = useState(false);
    const [tourActive, setTourActive] = useState(false);
    const [stepIndex, setStepIndex] = useState(0);
    const [rect, setRect] = useState<DOMRect | null>(null);
    const [dismissed, setDismissed] = useState(false);

    useEffect(() => {
        try {
            setDismissed(localStorage.getItem(storageKey) === "1");
        } catch {
            setDismissed(false);
        }
    }, [storageKey]);

    const step = steps[Math.min(stepIndex, steps.length - 1)];

    useEffect(() => {
        if (!tourActive || !step) return;
        const el = document.querySelector(step.target);
        if (!el) {
            setRect(null);
            return;
        }
        el.scrollIntoView({ block: "center", behavior: "smooth" });
        const update = () => setRect(el.getBoundingClientRect());
        update();
        const timer = window.setTimeout(update, 350);
        window.addEventListener("resize", update);
        window.addEventListener("scroll", update, true);
        return () => {
            window.clearTimeout(timer);
            window.removeEventListener("resize", update);
            window.removeEventListener("scroll", update, true);
        };
    }, [tourActive, stepIndex, step]);

    const startTour = useCallback(() => {
        setPanelOpen(false);
        setStepIndex(0);
        setTourActive(true);
    }, []);

    const closeTour = useCallback(() => {
        setTourActive(false);
        setRect(null);
    }, []);

    const next = useCallback(() => {
        if (stepIndex >= steps.length - 1) closeTour();
        else setStepIndex((i) => i + 1);
    }, [stepIndex, steps.length, closeTour]);

    const prev = useCallback(() => setStepIndex((i) => Math.max(0, i - 1)), []);

    const dismissForever = useCallback(() => {
        try {
            localStorage.setItem(storageKey, "1");
        } catch {
            // Best effort
        }
        setDismissed(true);
        closeTour();
    }, [storageKey, closeTour]);

    const tooltipPos = useMemo(() => (rect ? tooltipStyle(rect, step?.position || "bottom") : null), [rect, step]);

    return (
        <>
            {/* Launcher button */}
            <Button
                variant="secondary"
                size="sm"
                onClick={() => setPanelOpen((v) => !v)}
                className="gap-1.5"
                title={title}
            >
                <Question size={14} weight="bold" />
                {launcherLabel}
            </Button>

            {/* "How this page works" panel */}
            {panelOpen ? (
                <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4" onClick={() => setPanelOpen(false)}>
                    <div
                        className="w-full max-w-md rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white p-5 shadow-xl"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-start justify-between gap-2">
                            <div>
                                <h3 className="text-base font-bold text-[var(--rl-text-strong)]">{title}</h3>
                                <p className="mt-1 text-xs text-[var(--rl-text-muted)]">{description}</p>
                            </div>
                            <button type="button" onClick={() => setPanelOpen(false)} className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-gray-100">
                                <X size={16} weight="bold" />
                            </button>
                        </div>
                        <div className="mt-4 grid gap-2">
                            {steps.map((s, idx) => (
                                <div key={idx} className="flex items-start gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-2.5">
                                    <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-[var(--rl-black)] text-[10px] font-bold text-white">
                                        {idx + 1}
                                    </span>
                                    <div className="min-w-0">
                                        <p className="text-xs font-bold text-[var(--rl-text-strong)]">{s.title}</p>
                                        <p className="text-[11px] text-[var(--rl-text-muted)]">{s.body}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div className="mt-4 flex items-center justify-between gap-2">
                            <button
                                type="button"
                                onClick={dismissForever}
                                className="text-[11px] font-semibold text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                            >
                                Don&apos;t show again
                            </button>
                            <Button size="sm" onClick={startTour} className="gap-1.5">
                                <Question size={14} weight="bold" />
                                Start guided tour
                            </Button>
                        </div>
                    </div>
                </div>
            ) : null}

            {/* Guided tour overlay */}
            {tourActive && step ? (
                <div className="fixed inset-0 z-[80]">
                    {/* Dimmed backdrop with a "hole" around the target */}
                    <div className="absolute inset-0 bg-black/50" />
                    {rect ? (
                        <div
                            className="absolute rounded-[var(--rl-radius-sm)] ring-2 ring-[var(--rl-red)]"
                            style={{ left: rect.left - 4, top: rect.top - 4, width: rect.width + 8, height: rect.height + 8 }}
                        />
                    ) : null}
                    {/* Tooltip */}
                    <div
                        className="absolute rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white p-4 shadow-xl"
                        style={tooltipPos || { left: "50%", top: "50%", transform: "translate(-50%, -50%)", width: TOOLTIP_WIDTH }}
                    >
                        <div className="flex items-center justify-between gap-2">
                            <span className="rounded-[4px] bg-[var(--rl-black)] px-2 py-0.5 text-[10px] font-bold text-white">
                                {stepIndex + 1} / {steps.length}
                            </span>
                            <button type="button" onClick={closeTour} className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-gray-100">
                                <X size={15} weight="bold" />
                            </button>
                        </div>
                        <h4 className="mt-2 text-sm font-bold text-[var(--rl-text-strong)]">{step.title}</h4>
                        <p className="mt-1 text-xs leading-relaxed text-[var(--rl-text-muted)]">{step.body}</p>
                        <div className="mt-3 flex items-center justify-between gap-2">
                            <Button variant="secondary" size="sm" onClick={prev} disabled={stepIndex === 0} className="h-7 gap-1 text-xs">
                                <CaretLeft size={13} weight="bold" />
                                Back
                            </Button>
                            <Button size="sm" onClick={next} className="h-7 gap-1 text-xs">
                                {stepIndex >= steps.length - 1 ? "Finish" : "Next"}
                                <CaretRight size={13} weight="bold" />
                            </Button>
                        </div>
                    </div>
                </div>
            ) : null}
        </>
    );
}

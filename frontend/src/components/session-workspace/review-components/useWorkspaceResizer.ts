"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type WorkspacePanelKey = "pdf" | "form" | "preview" | "benefits";

const PANEL_ORDER: WorkspacePanelKey[] = ["pdf", "form", "preview", "benefits"];

const DEFAULT_WEIGHTS: Record<WorkspacePanelKey, number> = {
  pdf: 22,
  form: 29,
  preview: 39,
  benefits: 32,
};

export function useWorkspaceResizer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pdfOpen, setPdfOpen] = useState(false);
  const [formCollapsed, setFormCollapsed] = useState(false);
  const [previewColCollapsed, setPreviewColCollapsed] = useState(false);
  const [benefitsColCollapsed, setBenefitsColCollapsed] = useState(false);
  const [isDesktop, setIsDesktop] = useState(true);

  const [dragPair, setDragPair] = useState<{ left: WorkspacePanelKey; right: WorkspacePanelKey } | null>(null);
  const [weights, setWeights] = useState<Record<WorkspacePanelKey, number>>(DEFAULT_WEIGHTS);

  const visiblePanels = useMemo<WorkspacePanelKey[]>(() => {
    const openMap: Record<WorkspacePanelKey, boolean> = {
      pdf: pdfOpen,
      form: !formCollapsed,
      preview: !previewColCollapsed,
      benefits: !benefitsColCollapsed,
    };
    return PANEL_ORDER.filter((key) => openMap[key]);
  }, [pdfOpen, formCollapsed, previewColCollapsed, benefitsColCollapsed]);

  const panelWidths = useMemo<Record<WorkspacePanelKey, string>>(() => {
    const totalWeight = visiblePanels.reduce((acc, k) => acc + weights[k], 0) || 1;
    const result: Record<WorkspacePanelKey, string> = {
      pdf: "0%",
      form: "0%",
      preview: "0%",
      benefits: "0%",
    };
    for (const key of visiblePanels) {
      result[key] = `${((weights[key] / totalWeight) * 100).toFixed(4)}%`;
    }
    return result;
  }, [visiblePanels, weights]);

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(typeof window !== "undefined" ? window.innerWidth >= 1024 : true);
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const handlePointerDown = useCallback(
    (left: WorkspacePanelKey, right: WorkspacePanelKey) => (e: React.PointerEvent) => {
      e.preventDefault();
      setDragPair({ left, right });
    },
    []
  );

  useEffect(() => {
    if (!dragPair) return;

    const handlePointerMove = (e: PointerEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      if (rect.width <= 0) return;

      const leftIdx = visiblePanels.indexOf(dragPair.left);
      const rightIdx = visiblePanels.indexOf(dragPair.right);
      if (leftIdx === -1 || rightIdx === -1) return;

      const totalWeight = visiblePanels.reduce((acc, k) => acc + weights[k], 0);
      if (totalWeight <= 0) return;

      const leftOffsetWeight = visiblePanels
        .slice(0, leftIdx)
        .reduce((acc, k) => acc + weights[k], 0);

      const pointerRatio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const pointerWeight = pointerRatio * totalWeight;
      const combinedWeight = weights[dragPair.left] + weights[dragPair.right];

      const minWeight = Math.min(totalWeight * 0.14, combinedWeight * 0.4);
      const rawLeftWeight = pointerWeight - leftOffsetWeight;
      const clampedLeft = Math.max(minWeight, Math.min(combinedWeight - minWeight, rawLeftWeight));
      const clampedRight = combinedWeight - clampedLeft;

      setWeights((prev) => ({
        ...prev,
        [dragPair.left]: clampedLeft,
        [dragPair.right]: clampedRight,
      }));
    };

    const handlePointerUp = () => {
      setDragPair(null);
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [dragPair, visiblePanels, weights]);

  return {
    containerRef,
    pdfOpen,
    setPdfOpen,
    formCollapsed,
    setFormCollapsed,
    previewColCollapsed,
    setPreviewColCollapsed,
    benefitsColCollapsed,
    setBenefitsColCollapsed,
    visiblePanels,
    panelWidths,
    isDesktop,
    isDragging: dragPair ? `${dragPair.left}-${dragPair.right}` : null,
    dragPair,
    handlePointerDown,
    pdfWidth: panelWidths.pdf,
    formWidth: panelWidths.form,
    previewWidth: panelWidths.preview,
    benefitsWidth: panelWidths.benefits,
  };
}

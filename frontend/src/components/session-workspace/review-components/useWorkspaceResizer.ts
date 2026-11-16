"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export function useWorkspaceResizer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pdfOpen, setPdfOpen] = useState(false);
  const [formCollapsed, setFormCollapsed] = useState(false);
  const [previewColCollapsed, setPreviewColCollapsed] = useState(false);
  const [isDesktop, setIsDesktop] = useState(true);

  const [isDragging, setIsDragging] = useState<"pdf" | "main" | "pdf-preview" | null>(null);
  const [colSizes, setColSizes] = useState({ pdf: 28, middle: 36, right: 36 });
  const [splitPdfPreview, setSplitPdfPreview] = useState(50);
  const [splitPdfForm, setSplitPdfForm] = useState(40);
  const [split2Col, setSplit2Col] = useState(45);

  const pdfWidth = useMemo(() => {
    if (!pdfOpen) return "0%";
    if (formCollapsed && previewColCollapsed) return "100%";
    if (formCollapsed) return `${splitPdfPreview}%`;
    if (previewColCollapsed) return `${splitPdfForm}%`;
    return `${colSizes.pdf}%`;
  }, [pdfOpen, formCollapsed, previewColCollapsed, splitPdfPreview, splitPdfForm, colSizes.pdf]);

  const formWidth = useMemo(() => {
    if (formCollapsed) return "0%";
    if (!pdfOpen && previewColCollapsed) return "100%";
    if (!pdfOpen) return `${split2Col}%`;
    if (previewColCollapsed) return `${100 - splitPdfForm}%`;
    return `${colSizes.middle}%`;
  }, [formCollapsed, pdfOpen, previewColCollapsed, split2Col, splitPdfForm, colSizes.middle]);

  const previewWidth = useMemo(() => {
    if (previewColCollapsed) return "0%";
    if (!pdfOpen && formCollapsed) return "100%";
    if (!pdfOpen) return `${100 - split2Col}%`;
    if (formCollapsed) return `${100 - splitPdfPreview}%`;
    return `${colSizes.right}%`;
  }, [previewColCollapsed, pdfOpen, formCollapsed, split2Col, splitPdfPreview, colSizes.right]);

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(typeof window !== "undefined" ? window.innerWidth >= 1024 : true);
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const handlePointerDown = useCallback((which: "pdf" | "main" | "pdf-preview") => (e: React.PointerEvent) => {
    e.preventDefault();
    setIsDragging(which);
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handlePointerMove = (e: PointerEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const totalWidth = rect.width;
      if (totalWidth <= 0) return;

      const offsetX = e.clientX - rect.left;
      const percent = Math.max(10, Math.min(90, (offsetX / totalWidth) * 100));

      if (isDragging === "pdf-preview") {
        const newPdf = Math.max(20, Math.min(80, percent));
        setSplitPdfPreview(newPdf);
        return;
      }

      if (pdfOpen && !formCollapsed && !previewColCollapsed) {
        if (isDragging === "pdf") {
          const newPdf = Math.max(15, Math.min(45, percent));
          setColSizes((prev) => {
            const remaining = 100 - newPdf;
            const currentMiddleRight = prev.middle + prev.right || 1;
            const middleRatio = prev.middle / currentMiddleRight;
            const newMiddle = Math.max(20, Math.min(remaining - 20, remaining * middleRatio));
            const newRight = remaining - newMiddle;
            return { pdf: newPdf, middle: newMiddle, right: newRight };
          });
        } else if (isDragging === "main") {
          setColSizes((prev) => {
            const minMiddle = 20;
            const maxMiddle = 100 - prev.pdf - 20;
            const newMiddle = Math.max(minMiddle, Math.min(maxMiddle, percent - prev.pdf));
            const newRight = Math.max(20, 100 - prev.pdf - newMiddle);
            return { ...prev, middle: newMiddle, right: newRight };
          });
        }
        return;
      }

      if (!pdfOpen && !formCollapsed && !previewColCollapsed) {
        if (isDragging === "main") {
          const newForm = Math.max(20, Math.min(80, percent));
          setSplit2Col(newForm);
        }
        return;
      }

      if (pdfOpen && !formCollapsed && previewColCollapsed) {
        if (isDragging === "pdf") {
          const newPdf = Math.max(20, Math.min(80, percent));
          setSplitPdfForm(newPdf);
        }
        return;
      }
    };

    const handlePointerUp = () => {
      setIsDragging(null);
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
  }, [isDragging, pdfOpen, formCollapsed, previewColCollapsed]);

  return {
    containerRef,
    pdfOpen,
    setPdfOpen,
    formCollapsed,
    setFormCollapsed,
    previewColCollapsed,
    setPreviewColCollapsed,
    isDesktop,
    isDragging,
    handlePointerDown,
    pdfWidth,
    formWidth,
    previewWidth,
  };
}

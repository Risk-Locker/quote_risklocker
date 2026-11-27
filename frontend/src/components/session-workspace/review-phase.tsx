"use client";

import React, { useEffect, useRef, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageLoading } from "@/components/ui/page-loading";
import { ArrowSquareOut, DownloadSimple, Flask, X } from "@phosphor-icons/react";
import {
  useWorkspaceActions,
  useWorkspaceData,
  useWorkspaceMutation,
  useWorkspaceRealtime,
} from "@/components/session-workspace/provider";
import { RealtimePresenceBanner } from "@/components/realtime/RealtimePresenceBanner";
import { api, fileUrl } from "@/lib/api";

import { ReviewHeaderCard } from "./review-components/ReviewHeaderCard";
import { useReviewWorkspaceState } from "./review-components/useReviewWorkspaceState";
import { useWorkspaceResizer, type WorkspacePanelKey } from "./review-components/useWorkspaceResizer";
import { useQuotationExports } from "./review-components/useQuotationExports";
import {
  useBenefitOperations,
  GLOBAL_BENEFIT_KEYS,
  type GlobalConcept,
} from "./review-components/useBenefitOperations";
import { useReviewCatalogAndTemplate } from "./review-components/useReviewCatalogAndTemplate";
import { useQuotationConflictAndAi } from "./review-components/useQuotationConflictAndAi";
import { TemplateConfigCard } from "./review-components/TemplateConfigCard";
import { LivePreviewCard } from "./review-components/LivePreviewCard";
import { PolicyFieldsCard } from "./review-components/policy-fields-card";
import { ExtractedBenefitsCard } from "./review-components/extracted-benefits-card";
import { BenefitsManagerPanel } from "./review-components/benefits-manager-panel";
import { ReviewBanners } from "./review-components/review-banners";
import { ReviewAttentionBar } from "./review-components/review-attention-bar";
import { ReviewModals } from "./review-components/review-modals";
import { UnsavedChangesBar } from "./review-components/UnsavedChangesBar";
import { DeepRedetectProgressBanner } from "@/components/redetect/DeepRedetectProgressBanner";
import type { BenefitCardSummary } from "./types";
import { useDeepRedetect } from "@/components/redetect/useDeepRedetect";

export function ReviewPhase({
  id,
  highlightField,
  onNext,
  onBack,
}: {
  id: string;
  highlightField?: string;
  onNext?: () => void;
  onBack?: () => void;
}) {
  const { workspace, loading, loadError, remoteSyncNotice, dismissRemoteSyncNotice } = useWorkspaceData();
  const { queueOperation, reload, save, discard, decideField } = useWorkspaceActions();
  const mutation = useWorkspaceMutation();
  const realtime = useWorkspaceRealtime();

  const [globalConcepts, setGlobalConcepts] = useState<GlobalConcept[]>([]);
  const [templateCollapsed, setTemplateCollapsed] = useState(false);
  const [extractedValuesCollapsed, setExtractedValuesCollapsed] = useState(false);
  const [extractedBenefitsCollapsed, setExtractedBenefitsCollapsed] = useState(false);
  const [previewCollapsed, setPreviewCollapsed] = useState(false);
  const [previewExpanded, setPreviewExpanded] = useState(false);
  const [highlightedFieldKey, setHighlightedFieldKey] = useState<string | null>(null);
  const [highlightedSelectionId, setHighlightedSelectionId] = useState<string | null>(null);
  const highlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const resizer = useWorkspaceResizer();

  const state = useReviewWorkspaceState({
    id,
    pinCatalog: async (compId, prodId, tierId, opts) => {
      await catalog.pinCatalog(compId, prodId, tierId, opts);
    },
  });

  const { formValues, setFormValues, previewFields } = state;

  const benefits = useBenefitOperations({
    workspace,
    formValues,
    queueOperation,
    scheduleSave: state.scheduleSave,
    setToastMessage: state.setToastMessage,
  });

  const catalog = useReviewCatalogAndTemplate({
    id,
    workspace,
    formValues,
    setFormValues,
    currentVehicleCategory: benefits.currentVehicleCategory,
    currentCards: benefits.currentCards,
    addonCards: benefits.addonCards,
    showDesign2Schedule: state.showDesign2Schedule,
    extrasDisplayMode: state.extrasDisplayMode,
    queueOperation,
    save,
    commitFieldDirectly: state.commitFieldDirectly,
    setSyncHighlight: state.setSyncHighlight,
    decideField,
    onQueue: benefits.onQueue,
  });

  const conflictAndAi = useQuotationConflictAndAi({
    id,
    reload,
    setToastMessage: state.setToastMessage,
  });

  const deepRedetect = useDeepRedetect({
    onCompleted: async (completedJob) => {
      const changedCount = (completedJob.result_summary?.changed_fields as string[] | undefined)?.length || 0;
      await reload();
      state.setToastMessage(
        changedCount > 0
          ? `Deep Re-detect finished (${changedCount} field(s) updated).`
          : "Deep Re-detect completed and verified."
      );
    },
    onCancelled: () => {
      state.setToastMessage("Re-detection cancelled safely.");
    },
    onFailed: (msg) => {
      state.setActionError(msg);
    },
  });

  const exports = useQuotationExports({
    id,
    workspace,
    mutation,
    save,
    formValues,
    previewFields,
    previewTemplate: catalog.previewTemplate,
    canvasH: catalog.canvasH,
    ownershipConflict: conflictAndAi.ownershipConflict,
    setConflictModalOpen: conflictAndAi.setConflictModalOpen,
    setToastMessage: state.setToastMessage,
    setActionError: state.setActionError,
  });

  useEffect(() => {
    let cancelled = false;
    api<{ benefit_concepts: { items: GlobalConcept[] } }>("/business/benefit-concepts?page=1&page_size=100")
      .then((res) => { if (!cancelled) setGlobalConcepts(res.benefit_concepts?.items || []); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!remoteSyncNotice) return;
    state.setToastMessage(remoteSyncNotice);
    dismissRemoteSyncNotice();
  }, [remoteSyncNotice, dismissRemoteSyncNotice, state]);

  useEffect(() => {
    if (highlightField && !loading) {
      setHighlightedFieldKey(highlightField);
      if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
      highlightTimerRef.current = setTimeout(() => setHighlightedFieldKey(null), 4500);
    }
  }, [highlightField, loading]);

  useEffect(() => {
    return () => {
      if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
    };
  }, []);

  const approveFieldAndPersist = (fieldName: string, val: string) => {
    decideField(fieldName, "confirm", val);
    void save().catch((err) => {
      state.setActionError(err instanceof Error ? err.message : "Could not approve field");
    });
  };

  const approveBenefitAndPersist = (card: BenefitCardSummary) => {
    const selId = card.selection_id || card.card_key;
    if (!selId) return;
    if (card.cost_status === "unknown") {
      const hasPrice = Boolean(card.price?.amount && Number(card.price.amount) > 0);
      queueOperation(
        {
          op: "benefit_update",
          selection_id: selId,
          cost_status: hasPrice ? "paid" : "included",
          confirm_plan_tier: true,
        },
        `benefits.${selId}.approve`
      );
    } else {
      queueOperation(
        { op: "benefit_update", selection_id: selId, confirm_plan_tier: true },
        `benefits.${selId}.plan_tier`
      );
    }
    void save().catch((err) => {
      state.setActionError(err instanceof Error ? err.message : "Could not approve benefit");
    });
  };

  if (loading) return <PageLoading />;
  if (loadError || !workspace) {
    return (
      <Card className="grid gap-3 p-6 m-4" role="alert">
        <h1 className="text-xl font-bold text-[var(--rl-text-strong)]">Could not load quotation</h1>
        <p className="text-sm text-[var(--rl-text)]">{loadError || "The quotation workspace is unavailable."}</p>
        <Button className="w-fit" onClick={() => reload().catch(() => undefined)}>Retry</Button>
      </Card>
    );
  }

  const companyName = workspace.pinned_names?.company_name;
  const visibleCols = resizer.visiblePanels;

  const renderPanel = (panelKey: WorkspacePanelKey) => {
    if (panelKey === "pdf") {
      return (
        <div
          style={{ width: resizer.isDesktop ? resizer.panelWidths.pdf : "100%" }}
          className="w-full lg:w-auto min-w-0 flex-shrink-0 lg:h-full lg:overflow-hidden"
        >
          <Card className="h-[520px] lg:h-full p-2 flex flex-col">
            <div className="flex items-center justify-between px-1 pb-1.5 border-b border-[var(--rl-border)] mb-1 shrink-0">
              <span className="text-xs font-bold text-[var(--rl-text-strong)]">Source Quotation PDF</span>
              <div className="flex items-center gap-1">
                <a
                  href={fileUrl(`/uploaded-files/${workspace.uploaded_file_id}/content`)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 h-6 px-2 text-[11px] font-semibold rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white text-[var(--rl-text-strong)] hover:bg-neutral-50 hover:border-neutral-400 shadow-2xs transition-colors cursor-pointer"
                  title="Open uploaded PDF in full browser tab"
                >
                  <ArrowSquareOut size={12} weight="bold" />
                  <span>Open Tab</span>
                </a>
                <Button
                  size="sm"
                  variant="secondary"
                  className="h-6 px-2 text-[11px] gap-1 cursor-pointer"
                  onClick={() => {
                    const srcUrl = fileUrl(`/uploaded-files/${workspace.uploaded_file_id}/content?download=true`);
                    exports.triggerDownload(srcUrl, `source_quotation_${formValues.vehicle_no || id}.pdf`);
                  }}
                  title="Download original uploaded PDF"
                >
                  <DownloadSimple size={12} weight="bold" /> Download
                </Button>
                <button
                  type="button"
                  onClick={() => resizer.setPdfOpen(false)}
                  className="p-1 text-gray-400 hover:text-gray-900 rounded cursor-pointer"
                  title="Close PDF panel"
                  aria-label="Close PDF panel"
                >
                  <X size={14} weight="bold" />
                </button>
              </div>
            </div>
            <iframe
              title="Source quotation PDF"
              src={fileUrl(`/uploaded-files/${workspace.uploaded_file_id}/content`)}
              className={`flex-1 min-h-0 w-full rounded border bg-white ${resizer.isDragging ? "pointer-events-none" : ""}`}
            />
          </Card>
        </div>
      );
    }

    if (panelKey === "form") {
      return (
        <div
          style={{ width: resizer.isDesktop ? resizer.panelWidths.form : "100%" }}
          className="w-full lg:w-auto min-w-0 flex-shrink-0 lg:h-full lg:overflow-y-auto pr-0 lg:pr-0.5"
        >
          <section aria-label="Template configuration and extracted values" className="grid grid-cols-1 gap-3 content-start pb-6">
            {/* Compact Context Overview Bar */}
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2.5 py-1.5 text-xs shadow-xs">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11px] text-[var(--rl-text-muted)]">Insurer: <strong className="rounded bg-gray-100 px-1.5 py-0.5 font-bold text-gray-900 border">{companyName || "Standard"}</strong></span>
                <span className="text-[11px] text-[var(--rl-text-muted)]">Vehicle: <strong className="rounded bg-blue-50 px-1.5 py-0.5 font-bold text-blue-700 border">{formValues.vehicle_type || "Car"}</strong></span>
                <span className="text-[11px] text-[var(--rl-text-muted)]">Model: <strong className="truncate font-bold text-gray-900 max-w-[140px]">{formValues.car_model || "—"}</strong></span>
              </div>
              <button
                type="button"
                onClick={() => resizer.setFormCollapsed(true)}
                className="hidden lg:flex p-1 text-gray-400 hover:text-gray-900 cursor-pointer"
                title="Close Form panel"
                aria-label="Close Form panel"
              >
                <X size={14} weight="bold" />
              </button>
            </div>

            <TemplateConfigCard
              workspace={workspace}
              templateCollapsed={templateCollapsed}
              setTemplateCollapsed={setTemplateCollapsed}
              publishedTemplates={catalog.publishedTemplates}
              selectedRevisionId={catalog.selectedRevisionId}
              templatesLoading={catalog.templatesLoading}
              selectTemplateDirectly={catalog.selectTemplateDirectly}
              templateError={catalog.templateError}
              templateImpact={catalog.templateImpact}
              confirmTemplateSelection={() => {
                if (catalog.templateImpact) catalog.selectTemplateDirectly(catalog.templateImpact.target.template_revision_id);
              }}
              setTemplateImpact={catalog.setTemplateImpact}
              companyName={companyName}
              companies={catalog.companies}
              pinLoading={catalog.pinLoading}
              pinCatalog={catalog.pinCatalog}
              productOptions={catalog.productOptions}
              categorizedProducts={catalog.categorizedProducts}
              handlePackageSelect={catalog.handlePackageSelect}
              syncHighlight={state.syncHighlight}
              formatProductLabel={(name) => name}
              pinPackageTier={catalog.pinPackageTier}
              allBenefitPresets={catalog.allBenefitPresets}
              selectedBenefitPreset={catalog.selectedBenefitPreset}
              handleSelectBenefitPreset={catalog.handleSelectBenefitPreset}
              extrasDisplayMode={state.extrasDisplayMode}
              handleExtrasDisplayModeChange={state.handleExtrasDisplayModeChange}
              isDesign2={catalog.isDesign2}
              showDesign2Schedule={state.showDesign2Schedule}
              toggleDesign2Schedule={state.toggleDesign2Schedule}
            />

            <PolicyFieldsCard
              workspace={workspace}
              formValues={formValues}
              setFormValues={setFormValues}
              previousValuesRef={state.previousValuesRef}
              extractedValuesCollapsed={extractedValuesCollapsed}
              setExtractedValuesCollapsed={setExtractedValuesCollapsed}
              copiedInfo={exports.copiedInfo}
              handleCopyExtractedInfo={exports.handleCopyExtractedInfo}
              geminiQuotaInfo={conflictAndAi.geminiQuotaInfo}
              previewFields={previewFields}
              savingDiscount={state.savingDiscount}
              onApplyMotorDiscountPct={state.handleApplyMotorDiscountPct}
              companies={catalog.companies}
              roundTotal={state.roundTotal}
              toggleRoundTotal={state.toggleRoundTotal}
              isFieldModified={state.isFieldModified}
              getDetectedValue={state.getDetectedValue}
              handleResetField={state.handleResetField}
              commitField={state.commitField}
              commitFieldDirectly={state.commitFieldDirectly}
              syncHighlight={state.syncHighlight}
              setSyncHighlight={state.setSyncHighlight}
              companyWorkspace={catalog.companyWorkspace}
              categorizedProducts={catalog.categorizedProducts}
              pinCatalog={catalog.pinCatalog}
              highlightedFieldKey={highlightedFieldKey}
              onConfirmField={approveFieldAndPersist}
            />

            <ExtractedBenefitsCard
              workspace={workspace}
              extractedBenefitsCollapsed={extractedBenefitsCollapsed}
              setExtractedBenefitsCollapsed={setExtractedBenefitsCollapsed}
              pinLoading={catalog.pinLoading}
              pinPackageTier={catalog.pinPackageTier}
              globalConcepts={globalConcepts}
              addConceptAsBenefit={benefits.addConceptAsBenefit}
              onQueue={benefits.onQueue}
              queueOperation={queueOperation}
              scheduleSave={state.scheduleSave}
              setToastMessage={state.setToastMessage}
            />
          </section>
        </div>
      );
    }

    if (panelKey === "preview") {
      return (
        <div
          style={{ width: resizer.isDesktop ? resizer.panelWidths.preview : "100%" }}
          className="w-full lg:w-auto min-w-0 flex-shrink-0 lg:h-full lg:overflow-hidden"
        >
          <LivePreviewCard
            previewCollapsed={previewCollapsed}
            setPreviewCollapsed={setPreviewCollapsed}
            previewExpanded={previewExpanded}
            setPreviewExpanded={setPreviewExpanded}
            setPreviewColCollapsed={resizer.setPreviewColCollapsed}
            previewZoom={catalog.previewZoom}
            setPreviewZoom={catalog.setPreviewZoom}
            isDesign2={catalog.isDesign2}
            showDesign2Schedule={state.showDesign2Schedule}
            toggleDesign2Schedule={state.toggleDesign2Schedule}
            design2CardCount={catalog.design2CardCount}
            selectedBenefitPreset={catalog.selectedBenefitPreset}
            handleSelectBenefitPreset={catalog.handleSelectBenefitPreset}
            allBenefitPresets={catalog.allBenefitPresets}
            previewScrollRef={catalog.previewScrollRef}
            previewLoading={catalog.previewLoading}
            previewTemplate={catalog.previewTemplate}
            canvasH={catalog.canvasH}
            previewFields={previewFields}
            currentCards={benefits.currentCards}
            addonCards={benefits.addonCards}
            companyName={companyName}
            previewTemplateAssets={catalog.previewTemplateAssets}
            companyWorkspace={catalog.companyWorkspace}
            companies={catalog.companies}
            workspace={workspace}
            balancedElements={catalog.balancedElements}
            displayOptions={workspace.display_options}
            conceptAssets={{}}
            handleOpenNewQuotationTab={exports.handleOpenNewQuotationTab}
            openingPreviewTab={exports.openingPreviewTab}
          />
        </div>
      );
    }

    return (
      <div
        style={{ width: resizer.isDesktop ? resizer.panelWidths.benefits : "100%" }}
        className="w-full lg:w-auto min-w-0 flex-shrink-0 lg:h-full lg:overflow-y-auto pl-0 lg:pl-0.5"
      >
        <div className="pb-6">
          <BenefitsManagerPanel
            companyName={companyName}
            vehicleType={formValues.vehicle_type}
            onClosePanel={() => resizer.setBenefitsColCollapsed(true)}
            benefitsCollapsed={benefits.benefitsCollapsed}
            setBenefitsCollapsed={benefits.setBenefitsCollapsed}
            benefitsViewMode={benefits.benefitsViewMode}
            setBenefitsViewMode={benefits.setBenefitsViewMode}
            currentCards={benefits.currentCards}
            addonCards={benefits.addonCards}
            focCards={benefits.focCards}
            purchasedAddonCards={benefits.purchasedAddonCards}
            handleReset={benefits.handleReset}
            handleUndo={benefits.handleUndo}
            handleRedo={benefits.handleRedo}
            undoStack={benefits.undoStack}
            redoStack={benefits.redoStack}
            setModalTarget={benefits.setModalTarget}
            setShowGlobalModal={benefits.setShowGlobalModal}
            workspace={workspace}
            globalConcepts={globalConcepts}
            conceptAssets={{}}
            onQueue={benefits.onQueue}
            packPlanSelections={benefits.packPlanSelections}
            setPackPlanSelections={benefits.setPackPlanSelections}
            removePack={benefits.removePack}
            addPack={benefits.addPack}
            customLabel={benefits.customLabel}
            setCustomLabel={benefits.setCustomLabel}
            customValue={benefits.customValue}
            setCustomValue={benefits.setCustomValue}
            customPrice={benefits.customPrice}
            setCustomPrice={benefits.setCustomPrice}
            addCustomBenefit={benefits.addCustomBenefit}
            highlightedSelectionId={highlightedSelectionId}
            onApproveBenefit={approveBenefitAndPersist}
          />
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col lg:h-[calc(100dvh-45px)] lg:overflow-hidden">
      {workspace.is_test ? (
        <div
          role="status"
          className="shrink-0 flex flex-wrap items-center justify-between gap-2 bg-amber-50 border-b border-amber-300 px-3 py-1.5 text-xs font-semibold text-amber-950"
        >
          <span className="inline-flex items-center gap-1.5">
            <Flask size={14} weight="bold" className="text-amber-700 shrink-0" />
            <span>SANDBOX TEST SESSION — Isolated from live Client Records, Tenures &amp; Hit/Miss Tracking</span>
          </span>
          <span className="rounded bg-amber-200/70 px-1.5 py-0.5 font-mono text-[10px] font-bold text-amber-950">
            /sessions/sandbox/{workspace.session_id}
          </span>
        </div>
      ) : null}
      <ReviewHeaderCard
        workspace={workspace}
        companyName={companyName}
        mutation={mutation}
        formValues={formValues}
        previewFields={previewFields}
        onBack={onBack}
        pdfOpen={resizer.pdfOpen}
        setPdfOpen={resizer.setPdfOpen}
        formCollapsed={resizer.formCollapsed}
        setFormCollapsed={resizer.setFormCollapsed}
        previewColCollapsed={resizer.previewColCollapsed}
        setPreviewColCollapsed={resizer.setPreviewColCollapsed}
        benefitsColCollapsed={resizer.benefitsColCollapsed}
        setBenefitsColCollapsed={resizer.setBenefitsColCollapsed}
        saveAndCheckLearning={state.saveAndCheckLearning}
        copiedPng={exports.copiedPng}
        copyingPng={exports.copyingPng}
        handleCopyPng={exports.handleCopyPng}
        downloadingPng={exports.downloadingPng}
        handleDownloadPng={exports.handleDownloadPng}
        ownershipConflict={conflictAndAi.ownershipConflict}
        handleDownloadPdf={exports.handleDownloadPdf}
        pdfLoading={exports.pdfLoading}
        handleCopySummary={exports.handleCopyExtractedInfo}
        copiedSummary={exports.copiedInfo}
        redetecting={deepRedetect.isRunning}
        onStartRedetect={() => void deepRedetect.startSessionRedetect(workspace.session_id)}
      />

      <section className="flex flex-col flex-1 min-h-0 gap-1 w-full px-1.5 py-1">
        <div className="shrink-0 flex flex-col gap-1.5 empty:hidden">
          <DeepRedetectProgressBanner
            job={deepRedetect.job}
            elapsedSeconds={deepRedetect.elapsedSeconds}
            cancelling={deepRedetect.cancelling}
            onCancel={() => void deepRedetect.cancelRedetect()}
            onDismiss={deepRedetect.dismissBanner}
          />
          {realtime && (
            <RealtimePresenceBanner
              connected={realtime.connected}
              otherEditors={realtime.otherEditors}
              primaryEditor={realtime.primaryEditor}
              isPrimaryEditor={realtime.isPrimaryEditor}
              pendingUpdate={realtime.pendingUpdate}
              onRefreshNow={() => void realtime.refreshNow()}
              onDismissPending={realtime.dismissPendingUpdate}
            />
          )}
          {state.actionError || mutation.saveError ? (
            <div role="alert" className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] p-2.5 text-xs font-semibold text-[var(--rl-red)]">
              {state.actionError || mutation.saveError}
            </div>
          ) : null}

          <ReviewBanners
            ownershipConflict={conflictAndAi.ownershipConflict}
            setConflictModalOpen={conflictAndAi.setConflictModalOpen}
            formValues={formValues}
            workspace={workspace}
            onRefresh={() => reload({ silent: true })}
            onDismissOwnerChangeAlert={async () => {
              queueOperation(
                { op: "update_display_options", options: { owner_change_alert: null } },
                "display_options.owner_change_alert"
              );
              await save();
            }}
          />

          <ReviewAttentionBar
            workspace={workspace}
            currentCards={benefits.currentCards}
            addonCards={benefits.addonCards}
            formValues={formValues}
            onConfirmField={approveFieldAndPersist}
            onConfirmBundleTier={(selectionId) => {
              queueOperation(
                { op: "benefit_update", selection_id: selectionId, confirm_plan_tier: true },
                `benefits.${selectionId}.plan_tier`
              );
              void save().catch((err) => {
                state.setActionError(err instanceof Error ? err.message : "Could not approve benefit");
              });
            }}
            onApproveBenefit={approveBenefitAndPersist}
            onJumpToItem={(item) => {
              // Auto-open Source PDF on the left so staff can verify immediately
              resizer.setPdfOpen(true);
              if (item.kind === "field" && item.fieldKey) {
                resizer.setFormCollapsed(false);
                setExtractedValuesCollapsed(false);
                setHighlightedFieldKey(item.fieldKey);
                setHighlightedSelectionId(null);
                if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
                highlightTimerRef.current = setTimeout(() => setHighlightedFieldKey(null), 2500);
                const fieldKey = item.fieldKey;
                requestAnimationFrame(() => {
                  setTimeout(() => {
                    const el =
                      document.querySelector(`[data-field-key="${fieldKey}"]`) ||
                      document.getElementById(`workspace-field-${fieldKey}`);
                    if (el instanceof HTMLElement) {
                      el.scrollIntoView({ behavior: "smooth", block: "center" });
                      const input = el.querySelector("input, select, textarea");
                      if (input instanceof HTMLElement) {
                        input.focus({ preventScroll: true });
                      }
                    }
                  }, 60);
                });
                return;
              }
              if (item.kind === "bundle" && item.selectionId) {
                resizer.setBenefitsColCollapsed(false);
                benefits.setBenefitsCollapsed(false);
                setHighlightedSelectionId(item.selectionId);
                setHighlightedFieldKey(null);
                if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
                highlightTimerRef.current = setTimeout(() => setHighlightedSelectionId(null), 2500);
                const selId = item.selectionId;
                requestAnimationFrame(() => {
                  setTimeout(() => {
                    const el =
                      document.querySelector(`[data-selection-id="${selId}"]`) ||
                      document.getElementById(`workspace-benefit-${selId}`);
                    if (el instanceof HTMLElement) {
                      el.scrollIntoView({ behavior: "smooth", block: "center" });
                    }
                  }, 60);
                });
              }
            }}
          />
        </div>

        {/* 4-Column Horizontal Workspace: Source PDF | Form | Preview | Benefit Edit */}
        <div
          ref={resizer.containerRef}
          className={`flex flex-col lg:flex-row items-stretch flex-1 min-h-0 w-full gap-2 lg:gap-0 relative ${resizer.isDragging ? "select-none" : ""}`}
        >
          {visibleCols.length === 0 ? (
            <Card className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
              <p className="text-sm font-semibold text-[var(--rl-text-strong)]">All workspace panels are closed.</p>
              <div className="flex flex-wrap items-center justify-center gap-2">
                <Button size="sm" variant="secondary" onClick={() => resizer.setPdfOpen(true)}>Show Source PDF</Button>
                <Button size="sm" variant="secondary" onClick={() => resizer.setFormCollapsed(false)}>Show Form</Button>
                <Button size="sm" variant="secondary" onClick={() => resizer.setPreviewColCollapsed(false)}>Show Preview</Button>
                <Button size="sm" variant="primary" onClick={() => resizer.setBenefitsColCollapsed(false)}>Show Benefit Edit</Button>
              </div>
            </Card>
          ) : (
            visibleCols.map((panelKey, idx) => {
              const prevKey = idx > 0 ? visibleCols[idx - 1] : null;
              const dragId = prevKey ? `${prevKey}-${panelKey}` : "";
              return (
                <React.Fragment key={panelKey}>
                  {prevKey ? (
                    <div
                      onPointerDown={resizer.handlePointerDown(prevKey, panelKey)}
                      role="separator"
                      aria-orientation="vertical"
                      aria-label={`Resize ${prevKey} and ${panelKey} panels`}
                      className="group w-2.5 mx-0.5 flex items-center justify-center cursor-col-resize self-stretch z-10 shrink-0 hidden lg:flex"
                    >
                      <div
                        className={`w-1 h-full rounded-full transition-colors ${
                          resizer.isDragging === dragId ? "bg-[var(--rl-red)]" : "bg-[var(--rl-border)] group-hover:bg-[var(--rl-red)]"
                        }`}
                      />
                    </div>
                  ) : null}
                  {renderPanel(panelKey)}
                </React.Fragment>
              );
            })
          )}
        </div>

        <ReviewModals
          showGlobalModal={benefits.showGlobalModal}
          setShowGlobalModal={benefits.setShowGlobalModal}
          modalTarget={benefits.modalTarget}
          globalSearch={benefits.globalSearch}
          setGlobalSearch={benefits.setGlobalSearch}
          modalFilter={benefits.modalFilter}
          setModalFilter={benefits.setModalFilter}
          companyName={companyName}
          globalConcepts={globalConcepts}
          isExcludedForVehicle={benefits.isExcludedForVehicle}
          insurerConceptKeys={benefits.insurerConceptKeys}
          GLOBAL_BENEFIT_KEYS={GLOBAL_BENEFIT_KEYS}
          filteredConcepts={globalConcepts.filter((c) => {
            if (benefits.isExcludedForVehicle(c)) return false;
            if (benefits.modalFilter === "insurer") {
              if (!benefits.insurerConceptKeys.has(c.concept_key) && !benefits.insurerConceptKeys.has(c.id)) return false;
            } else if (benefits.modalFilter === "global") {
              if (!GLOBAL_BENEFIT_KEYS.has(c.concept_key)) return false;
            } else if (benefits.modalFilter === "addons") {
              if (GLOBAL_BENEFIT_KEYS.has(c.concept_key)) return false;
            }
            const q = benefits.globalSearch.trim().toLowerCase();
            if (!q) return true;
            return (
              c.label.toLowerCase().includes(q) ||
              c.concept_key.toLowerCase().includes(q) ||
              (c.description || "").toLowerCase().includes(q)
            );
          })}
          fileUrl={fileUrl}
          addConceptAsBenefit={benefits.addConceptAsBenefit}
          conflictModalOpen={conflictAndAi.conflictModalOpen}
          setConflictModalOpen={conflictAndAi.setConflictModalOpen}
          ownershipConflict={conflictAndAi.ownershipConflict}
          selectedResolution={conflictAndAi.selectedResolution}
          setSelectedResolution={conflictAndAi.setSelectedResolution}
          resolutionNotes={conflictAndAi.resolutionNotes}
          setResolutionNotes={conflictAndAi.setResolutionNotes}
          resolvingConflict={conflictAndAi.resolvingConflict}
          handleResolveConflict={conflictAndAi.handleResolveConflict}
          toastMessage={state.toastMessage}
          onDismissToast={() => state.setToastMessage(null)}
          pendingExportAction={exports.pendingExportAction}
          setPendingExportAction={exports.setPendingExportAction}
          confirmAndExecuteExport={exports.confirmAndExecuteExport}
        />

        <UnsavedChangesBar
          mutation={mutation}
          onSave={state.saveAndCheckLearning}
          onDiscard={discard}
        />
      </section>
    </div>
  );
}

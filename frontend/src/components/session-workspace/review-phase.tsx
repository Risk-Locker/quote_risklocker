"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageLoading } from "@/components/ui/page-loading";
import { ArrowSquareOut, DownloadSimple, X } from "@phosphor-icons/react";
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
import { useWorkspaceResizer } from "./review-components/useWorkspaceResizer";
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
import { ReviewModals } from "./review-components/review-modals";
import { UnsavedChangesBar } from "./review-components/UnsavedChangesBar";

export function ReviewPhase({ id, onNext, onBack }: { id: string; onNext?: () => void; onBack?: () => void }) {
  const { workspace, loading, loadError } = useWorkspaceData();
  const { queueOperation, reload, save, discard, decideField } = useWorkspaceActions();
  const mutation = useWorkspaceMutation();
  const realtime = useWorkspaceRealtime();

  const [globalConcepts, setGlobalConcepts] = useState<GlobalConcept[]>([]);
  const [templateCollapsed, setTemplateCollapsed] = useState(false);
  const [extractedValuesCollapsed, setExtractedValuesCollapsed] = useState(false);
  const [extractedBenefitsCollapsed, setExtractedBenefitsCollapsed] = useState(false);
  const [previewCollapsed, setPreviewCollapsed] = useState(false);
  const [previewExpanded, setPreviewExpanded] = useState(false);

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

  if (loading) return <PageLoading />;
  if (loadError || !workspace) {
    return (
      <Card className="grid gap-3 p-6" role="alert">
        <h1 className="text-xl font-bold text-[var(--rl-text-strong)]">Could not load quotation</h1>
        <p className="text-sm text-[var(--rl-text)]">{loadError || "The quotation workspace is unavailable."}</p>
        <Button className="w-fit" onClick={() => reload().catch(() => undefined)}>Retry</Button>
      </Card>
    );
  }

  const companyName = workspace.pinned_names?.company_name;

  return (
    <>
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
      />

      <section className="grid gap-4 w-full max-w-[1800px] mx-auto pb-12 pt-6 px-4 sm:px-6">
        {realtime && (
          <RealtimePresenceBanner
            connected={realtime.connected}
            otherEditors={realtime.otherEditors}
            pendingUpdate={realtime.pendingUpdate}
            onRefreshNow={() => void realtime.refreshNow()}
            onDismissPending={realtime.dismissPendingUpdate}
          />
        )}
        {state.actionError || mutation.saveError ? (
          <div role="alert" className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] p-3 text-sm font-semibold text-[var(--rl-red)]">
            {state.actionError || mutation.saveError}
          </div>
        ) : null}

        <ReviewBanners
          ownershipConflict={conflictAndAi.ownershipConflict}
          setConflictModalOpen={conflictAndAi.setConflictModalOpen}
          formValues={formValues}
          workspace={workspace}
          learnPrompt={state.learnPrompt}
          learnValue={state.learnValue}
          setLearnPrompt={state.setLearnPrompt}
        />

        <div ref={resizer.containerRef} className={`flex flex-col lg:flex-row items-stretch min-h-[580px] w-full gap-0 relative ${resizer.isDragging ? "select-none" : ""}`}>
          {/* Column 1: Source PDF */}
          {resizer.pdfOpen ? (
            <>
              <div style={{ width: resizer.isDesktop ? resizer.pdfWidth : "100%" }} className="w-full lg:w-auto min-w-0 flex-shrink-0 relative overflow-hidden pr-0 lg:pr-1">
                <Card className="sticky top-[140px] h-[calc(100vh-180px)] p-2">
                  <div className="flex items-center justify-between px-1 pb-1.5 border-b border-[var(--rl-border)] mb-1">
                    <span className="text-xs font-bold text-[var(--rl-text-strong)]">Source Quotation PDF</span>
                    <div className="flex items-center gap-1">
                      <a
                        href={fileUrl(`/uploaded-files/${workspace.uploaded_file_id}/content`)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 h-6 px-2 text-[11px] font-semibold rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white text-[var(--rl-text-strong)] hover:bg-neutral-50 hover:border-neutral-400 shadow-2xs transition-colors cursor-pointer"
                        title="Open uploaded PDF in full Acrobat / Foxit browser tab"
                      >
                        <ArrowSquareOut size={12} weight="bold" />
                        <span>Open in New Tab</span>
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
                  <iframe title="Source quotation PDF" src={fileUrl(`/uploaded-files/${workspace.uploaded_file_id}/content`)} className={`h-[calc(100%-32px)] w-full rounded border bg-white ${resizer.isDragging ? "pointer-events-none" : ""}`} />
                </Card>
              </div>
              <div onPointerDown={resizer.handlePointerDown("pdf")} role="separator" aria-orientation="vertical" className="group w-3.5 -mx-1 flex items-center justify-center cursor-col-resize self-stretch z-10 shrink-0 hidden lg:flex">
                <div className={`w-1 h-full rounded-full ${resizer.isDragging === "pdf" ? "bg-[var(--rl-red)]" : "bg-[var(--rl-border)] group-hover:bg-[var(--rl-red)]"}`} />
              </div>
            </>
          ) : null}

          {/* Column 2: Template Selection & Extracted Values */}
          <div style={{ width: resizer.isDesktop ? resizer.formWidth : "100%", opacity: resizer.isDesktop && resizer.formCollapsed ? 0 : 1 }} className={`w-full lg:w-auto min-w-0 flex-shrink-0 ${resizer.formCollapsed ? "overflow-hidden px-0" : "px-0 lg:px-2"}`}>
            <section aria-label="Template configuration and extracted values" className="grid grid-cols-1 gap-4 content-start">
              {/* Context Overview Bar */}
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-2.5 text-xs shadow-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[11px] text-[var(--rl-text-muted)]">Insurer: <strong className="rounded bg-gray-100 px-1.5 py-0.5 font-bold text-gray-900 border">{companyName || "Standard"}</strong></span>
                  <span className="text-[11px] text-[var(--rl-text-muted)]">Vehicle: <strong className="rounded bg-blue-50 px-1.5 py-0.5 font-bold text-blue-700 border">{formValues.vehicle_type || "Car"}</strong></span>
                  <span className="text-[11px] text-[var(--rl-text-muted)]">Model: <strong className="truncate font-bold text-gray-900 max-w-[140px]">{formValues.car_model || "—"}</strong></span>
                </div>
                <button type="button" onClick={() => resizer.setFormCollapsed(true)} className="hidden lg:flex p-1 text-gray-400 hover:text-gray-900 cursor-pointer"><X size={14} weight="bold" /></button>
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
                geminiExtracting={conflictAndAi.geminiExtracting}
                triggerGeminiExtraction={conflictAndAi.triggerGeminiExtraction}
                geminiQuotaInfo={conflictAndAi.geminiQuotaInfo}
                previewFields={previewFields}
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

          <div onPointerDown={resizer.handlePointerDown("main")} role="separator" aria-orientation="vertical" className="group w-3.5 -mx-1 flex items-center justify-center cursor-col-resize self-stretch z-10 shrink-0 hidden lg:flex">
            <div className={`w-1 h-full rounded-full ${resizer.isDragging === "main" ? "bg-[var(--rl-red)]" : "bg-[var(--rl-border)] group-hover:bg-[var(--rl-red)]"}`} />
          </div>

          {/* Column 3: Live Preview & Benefits Manager */}
          <div style={{ width: resizer.isDesktop ? resizer.previewWidth : "100%", opacity: resizer.isDesktop && resizer.previewColCollapsed ? 0 : 1 }} className={`w-full lg:w-auto min-w-0 flex-1 ${resizer.previewColCollapsed ? "overflow-hidden px-0" : "pl-0 lg:pl-2"}`}>
            <section aria-label="Live preview and benefits manager" className="grid grid-cols-1 gap-4 content-start">
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

              <BenefitsManagerPanel
                companyName={companyName}
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
              />
            </section>
          </div>
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
          insurerConceptKeys={new Set()}
          GLOBAL_BENEFIT_KEYS={GLOBAL_BENEFIT_KEYS}
          filteredConcepts={globalConcepts}
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
    </>
  );
}

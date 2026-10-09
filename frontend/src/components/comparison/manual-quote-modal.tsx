"use client";

import { useState, useEffect, useRef } from "react";
import {
  X,
  FloppyDisk,
  FilePdf,
  CloudArrowUp,
  Spinner,
  CheckCircle,
  WarningCircle,
  FileText,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { extractDateFromFilename } from "@/components/upload/upload-workspace";

interface ManualQuoteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (payload: any) => Promise<void>;
  initialData?: any;
  tenureId?: string;
  tenureStartDate?: string;
  onUploadSuccess?: () => void;
}

const COMMON_INSURERS = [
  "AmAssurance",
  "Berjaya Sompo",
  "Etiqa Insurance",
  "Lonpac Insurance",
  "QBE Insurance",
  "STMB Insurance",
  "Tune Protect",
  "Liberty Insurance",
  "Allianz General",
];

export function ManualQuoteModal({
  isOpen,
  onClose,
  onSave,
  initialData,
  tenureId,
  tenureStartDate,
  onUploadSuccess,
}: ManualQuoteModalProps) {
  const [activeTab, setActiveTab] = useState<"upload" | "manual">("upload");

  // Manual Form States
  const [companyName, setCompanyName] = useState("AmAssurance");
  const [customCompany, setCustomCompany] = useState("");
  const [sumInsured, setSumInsured] = useState("");
  const [valuationType, setValuationType] = useState("agreed_value");
  const [motorPremium, setMotorPremium] = useState("");
  const [towingLimit, setTowingLimit] = useState("Unlimited");
  const [agreedValue, setAgreedValue] = useState(true);
  const [waiverBetterment, setWaiverBetterment] = useState(true);
  const [excess, setExcess] = useState("0");
  const [windscreen, setWindscreen] = useState("");
  const [specialPerils, setSpecialPerils] = useState("");
  const [llpLlop, setLlpLlop] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  // Advanced Breakdown & Rating States
  const [isAdvancedExpanded, setIsAdvancedExpanded] = useState(false);
  const [basicFigureAmount, setBasicFigureAmount] = useState("");
  const [basicFigureName, setBasicFigureName] = useState("Basic Premium");
  const [netRateFactor, setNetRateFactor] = useState("");
  const [sourceQuotationNo, setSourceQuotationNo] = useState("");

  // Upload States
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string>("");
  const [uploadError, setUploadError] = useState<string>("");
  const [isTestUpload, setIsTestUpload] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (initialData) {
      setActiveTab("manual");
      setCompanyName(initialData.company_name || "AmAssurance");
      const siStr = initialData.sum_insured !== undefined && initialData.sum_insured !== null ? String(initialData.sum_insured) : "0";
      setSumInsured(siStr);
      setValuationType(initialData.valuation_type || "agreed_value");
      setMotorPremium(initialData.motor_premium !== undefined && initialData.motor_premium !== null ? String(initialData.motor_premium) : "0");
      setTowingLimit(initialData.towing_limit || "Unlimited");
      setAgreedValue(initialData.agreed_value ?? true);
      setWaiverBetterment(initialData.waiver_betterment ?? true);
      setExcess(initialData.excess !== undefined && initialData.excess !== null ? String(initialData.excess) : "0");
      setWindscreen(initialData.windscreen_sum_insured ? String(initialData.windscreen_sum_insured) : "");
      setSpecialPerils(initialData.special_perils || "");
      setLlpLlop(initialData.llp_llop || "");
      setNotes(initialData.notes || "");

      // Breakdown & Rating fields
      const bfVal = initialData.basic_figure_amount != null ? String(initialData.basic_figure_amount) : "";
      setBasicFigureAmount(bfVal);
      setBasicFigureName(initialData.basic_figure_name || (initialData.is_takaful ? "Basic Contribution" : "Basic Premium"));
      if (initialData.rate_factor != null) {
        setNetRateFactor(Number(initialData.rate_factor).toFixed(6));
      } else if (initialData.sum_insured > 0 && initialData.basic_figure_amount != null) {
        setNetRateFactor((Number(initialData.basic_figure_amount) / Number(initialData.sum_insured)).toFixed(6));
      } else {
        setNetRateFactor("");
      }
      setSourceQuotationNo(initialData.source_quotation_no || initialData.quotation_ref || "");
    } else {
      setActiveTab(tenureId ? "upload" : "manual");
      setCompanyName("AmAssurance");
      setCustomCompany("");
      setSumInsured("");
      setValuationType("agreed_value");
      setMotorPremium("");
      setTowingLimit("Unlimited");
      setAgreedValue(true);
      setWaiverBetterment(true);
      setExcess("0");
      setWindscreen("");
      setSpecialPerils("");
      setLlpLlop("");
      setNotes("");
      setBasicFigureAmount("");
      setBasicFigureName("Basic Premium");
      setNetRateFactor("");
      setSourceQuotationNo("");
      setIsAdvancedExpanded(false);
      setUploadFile(null);
      setUploadError("");
      setUploadProgress("");
    }
  }, [initialData, isOpen, tenureId]);

  // Dynamic Mathematical Rate & Sum Insured Coupling
  const handleSumInsuredChange = (newSiStr: string) => {
    setSumInsured(newSiStr);
    const newSi = parseFloat(newSiStr);
    const currentBf = parseFloat(basicFigureAmount);
    if (!isNaN(newSi) && newSi > 0 && !isNaN(currentBf) && currentBf > 0) {
      setNetRateFactor((currentBf / newSi).toFixed(6));
    }
  };

  const handleRateFactorChange = (newRateStr: string) => {
    setNetRateFactor(newRateStr);
    const newRate = parseFloat(newRateStr);
    const currentSi = parseFloat(sumInsured);
    // When rate changes, sum insured remains constant, and basic figure dynamically updates
    if (!isNaN(newRate) && newRate > 0 && !isNaN(currentSi) && currentSi > 0) {
      setBasicFigureAmount((currentSi * newRate).toFixed(2));
    }
  };

  const handleBasicFigureChange = (newBfStr: string) => {
    setBasicFigureAmount(newBfStr);
    const newBf = parseFloat(newBfStr);
    const currentSi = parseFloat(sumInsured);
    if (!isNaN(newBf) && newBf > 0 && !isNaN(currentSi) && currentSi > 0) {
      setNetRateFactor((newBf / currentSi).toFixed(6));
    }
  };

  const handleReset = async () => {
    if (!tenureId || !initialData?.id || initialData.is_manual) return;
    try {
      setSaving(true);
      await api(`/comparison/${tenureId}/entry/${initialData.id}/reset`, { method: "POST" });
      onClose();
      if (onUploadSuccess) onUploadSuccess();
    } catch (err: any) {
      alert("Failed to reset entry: " + err.message);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const finalCompany = companyName === "Other" ? (customCompany.trim() || "Other Insurer") : companyName;
      await onSave({
        id: initialData?.id,
        company_name: finalCompany,
        sum_insured: parseFloat(sumInsured) || 0,
        valuation_type: valuationType,
        motor_premium: parseFloat(motorPremium) || 0,
        towing_limit: towingLimit,
        agreed_value: agreedValue,
        waiver_betterment: waiverBetterment,
        excess: parseFloat(excess) || 0,
        windscreen_sum_insured: windscreen ? parseFloat(windscreen) : null,
        special_perils: specialPerils || null,
        llp_llop: llpLlop || null,
        notes: notes || null,
        basic_figure_amount: basicFigureAmount ? parseFloat(basicFigureAmount) : undefined,
        source_quotation_no: sourceQuotationNo ? sourceQuotationNo.trim() : undefined,
        is_manual: true,
      });
      onClose();
    } catch (err) {
      console.error("Failed to save manual quote:", err);
    } finally {
      setSaving(false);
    }
  };

  function validateDateMatch(pdf: File): boolean {
    if (!tenureStartDate) return true;
    const fileDate = extractDateFromFilename(pdf.name);
    if (!fileDate) return true; // No date in filename, allowed through

    let targetYear: number | null = null;
    const targetDate = extractDateFromFilename(tenureStartDate);
    if (targetDate?.year) {
      targetYear = targetDate.year;
    } else {
      const yearMatch = tenureStartDate.match(/(20\d{2})/);
      if (yearMatch) targetYear = parseInt(yearMatch[1], 10);
    }

    if (fileDate.year && targetYear && fileDate.year !== targetYear) {
      setUploadError(
        `Cannot upload: quotation year (${fileDate.year}) does not match comparison year (${targetYear}).`
      );
      setUploadFile(null);
      return false;
    }
    return true;
  }

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (uploading) return;
    const files = Array.from(e.dataTransfer.files || []);
    const pdf = files.find((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (pdf) {
      if (validateDateMatch(pdf)) {
        setUploadFile(pdf);
        setUploadError("");
      }
    } else {
      setUploadError("Please drop a valid underwriter PDF file.");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setUploadError("Please select a PDF file.");
        return;
      }
      if (validateDateMatch(file)) {
        setUploadFile(file);
        setUploadError("");
      }
    }
  };

  const handleUploadSubmit = async () => {
    if (!uploadFile || !tenureId || uploading) return;
    setUploading(true);
    setUploadError("");
    setUploadProgress("Uploading underwriter PDF...");

    try {
      const form = new FormData();
      form.append("file", uploadFile);
      form.append("is_test", String(isTestUpload));

      const data = await api<{
        status: string;
        session_id: string | null;
        job_id: string | null;
        uploaded_file_id: string | null;
      }>(`/comparison/${tenureId}/upload-quote`, {
        method: "POST",
        body: form,
      });

      setUploadProgress("Scanning document & extracting quotation terms...");

      // Poll extraction job if returned
      if (data?.job_id) {
        let attempts = 0;
        const maxAttempts = 35; // 35 * 800ms = 28s
        while (attempts < maxAttempts) {
          attempts++;
          await new Promise((r) => setTimeout(r, 800));
          try {
            const jobData = await api<{
              job: {
                state: string;
                progress?: number;
                error?: { message: string };
              };
            }>(`/jobs/${data.job_id}`);
            const state = jobData?.job?.state;

            if (state === "completed") {
              setUploadProgress("Finalizing comparison matrix column...");
              break;
            }
            if (state === "failed" || state === "cancelled") {
              throw new Error(jobData?.job?.error?.message || "Quotation extraction failed");
            }
          } catch (pollErr: any) {
            if (pollErr?.message?.includes("failed") || pollErr?.message?.includes("cancelled")) {
              throw pollErr;
            }
          }
        }
      }

      if (onUploadSuccess) {
        onUploadSuccess();
      }
      onClose();
    } catch (err: any) {
      setUploadError(err.message || "Failed to process quote PDF");
    } finally {
      setUploading(false);
      setUploadProgress("");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
      <div className="relative w-full max-w-lg rounded-2xl bg-white border border-[#e5e5ea] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#e5e5ea] px-6 py-4 bg-[#f5f5f7]">
          <div>
            <h3 className="text-base font-bold text-[#1b1717]">
              {initialData ? "Edit Underwriter Quote" : "Add Insurer Quote"}
            </h3>
            <p className="text-xs text-[#6e6e73] mt-0.5">
              {initialData
                ? "Adjust quote figures directly in the comparison matrix"
                : "Upload an underwriter quote PDF or key in portal numbers manually"}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-[#6e6e73] hover:text-[#1b1717] hover:bg-neutral-200 transition-colors cursor-pointer"
          >
            <X size={18} weight="bold" />
          </button>
        </div>

        {/* Tab Switcher (Only when adding a new quote) */}
        {!initialData && (
          <div className="flex border-b border-[#e5e5ea] bg-white px-6 pt-3">
            <button
              type="button"
              onClick={() => setActiveTab("upload")}
              className={`pb-2.5 px-3 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 cursor-pointer ${
                activeTab === "upload"
                  ? "border-[#1b1717] text-[#1b1717]"
                  : "border-transparent text-[#6e6e73] hover:text-[#1b1717]"
              }`}
            >
              <FilePdf size={16} weight="bold" className={activeTab === "upload" ? "text-[#ed1c24]" : ""} />
              <span>Upload Quotation PDF</span>
              <span className="ml-1 rounded-full bg-emerald-50 text-emerald-700 px-1.5 py-0.2 text-[10px] font-semibold border border-emerald-200">
                Recommended
              </span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("manual")}
              className={`pb-2.5 px-3 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 cursor-pointer ${
                activeTab === "manual"
                  ? "border-[#1b1717] text-[#1b1717]"
                  : "border-transparent text-[#6e6e73] hover:text-[#1b1717]"
              }`}
            >
              <FileText size={16} weight="bold" />
              <span>Manual Portal Entry</span>
            </button>
          </div>
        )}

        {/* Tab 1: Upload Quotation PDF */}
        {activeTab === "upload" && !initialData && (
          <div className="p-6 space-y-4">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleFileDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-2xl p-6 text-center transition-all cursor-pointer ${
                isDragging
                  ? "border-[#1b1717] bg-[#f5f5f7] scale-[1.01]"
                  : uploadFile
                  ? "border-emerald-300 bg-emerald-50/40"
                  : "border-[#e5e5ea] hover:border-neutral-400 bg-white"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={handleFileChange}
              />

              {uploadFile ? (
                <div className="flex flex-col items-center gap-2">
                  <div className="size-12 rounded-xl bg-white border border-emerald-200 flex items-center justify-center text-emerald-600 shadow-xs">
                    <FilePdf size={28} weight="bold" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-[#1b1717]">{uploadFile.name}</p>
                    <p className="text-xs text-[#6e6e73]">
                      {(uploadFile.size / 1024 / 1024).toFixed(2)} MB · Ready for extraction
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setUploadFile(null);
                    }}
                    className="mt-1 text-xs text-rose-600 hover:text-rose-800 font-semibold underline cursor-pointer"
                  >
                    Choose different file
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <div className="size-12 rounded-xl bg-[#f5f5f7] flex items-center justify-center text-[#454545]">
                    <CloudArrowUp size={28} weight="bold" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-[#1b1717]">
                      Drop underwriter quote PDF here
                    </p>
                    <p className="text-xs text-[#6e6e73] mt-0.5">
                      or click to browse from your computer
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center justify-center gap-1.5 mt-2 max-w-sm">
                    {COMMON_INSURERS.slice(0, 6).map((ins) => (
                      <span
                        key={ins}
                        className="rounded-md bg-[#f5f5f7] px-2 py-0.5 text-[10px] font-medium text-[#454545]"
                      >
                        {ins}
                      </span>
                    ))}
                  </div>
                  <p className="text-[11px] text-[#6e6e73] mt-1 italic">
                    Supports multiple peril variants of the same insurer (e.g. Basic vs Plus)
                  </p>
                </div>
              )}
            </div>

            {uploadError && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 flex items-start gap-2.5 text-xs text-rose-800">
                <WarningCircle size={16} weight="bold" className="shrink-0 mt-0.5 text-rose-600" />
                <span>{uploadError}</span>
              </div>
            )}

            {uploadProgress && (
              <div className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900 space-y-2">
                <div className="flex items-center gap-2">
                  <Spinner size={16} className="animate-spin text-blue-600 shrink-0" weight="bold" />
                  <span className="font-semibold">{uploadProgress}</span>
                </div>
                <div className="h-1.5 w-full bg-blue-200 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-600 rounded-full animate-pulse w-3/4" />
                </div>
              </div>
            )}

            {/* Test Sandbox Option */}
            <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-3 flex items-center justify-between gap-3">
              <label className="flex items-center gap-2.5 cursor-pointer flex-1 min-w-0">
                <input
                  type="checkbox"
                  checked={isTestUpload}
                  onChange={(e) => setIsTestUpload(e.target.checked)}
                  disabled={uploading}
                  className="h-4 w-4 accent-amber-600 rounded shrink-0 cursor-pointer"
                />
                <div>
                  <span className="text-xs font-bold text-amber-900 block">
                    Test Upload Mode (Sandbox)
                  </span>
                  <span className="text-[11px] text-amber-700 block">
                    Saves quote for comparison testing only; will not record to client records or analytics.
                  </span>
                </div>
              </label>
              <span className="rounded bg-amber-200 text-amber-900 text-[10px] font-bold px-2 py-0.5 shrink-0 uppercase tracking-wider">
                Sandbox
              </span>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#e5e5ea]">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={onClose}
                disabled={uploading}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handleUploadSubmit}
                disabled={!uploadFile || uploading}
                className="bg-[#1b1717] hover:bg-black text-white"
                icon={
                  uploading ? (
                    <Spinner size={14} className="animate-spin" />
                  ) : (
                    <CloudArrowUp size={14} weight="bold" />
                  )
                }
              >
                {uploading ? "Extracting..." : "Upload & Extract Quote"}
              </Button>
            </div>
          </div>
        )}

        {/* Tab 2: Manual Portal Entry Form */}
        {(activeTab === "manual" || initialData) && (
          <form onSubmit={handleManualSubmit} className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
            {/* Insurer Selection */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                Underwriter Company
              </label>
              <select
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-sm font-medium text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
              >
                {companyName && !COMMON_INSURERS.includes(companyName) && companyName !== "Other" && (
                  <option value={companyName}>{companyName}</option>
                )}
                {COMMON_INSURERS.map((ins) => (
                  <option key={ins} value={ins}>
                    {ins}
                  </option>
                ))}
                <option value="Other">Other / Custom Insurer</option>
              </select>
            </div>

            {companyName === "Other" && (
              <div>
                <label className="block text-xs font-semibold text-[#454545] mb-1">
                  Custom Insurer Name
                </label>
                <input
                  type="text"
                  value={customCompany}
                  onChange={(e) => setCustomCompany(e.target.value)}
                  placeholder="e.g. MSIG, Pacific & Orient"
                  className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-sm text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
                />
              </div>
            )}

            {/* Sum Insured & Valuation Type */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                  Sum Insured (RM)
                </label>
                <input
                  type="text"
                  step="0.01"
                  placeholder="e.g. 85000"
                  value={sumInsured}
                  onChange={(e) => handleSumInsuredChange(e.target.value)}
                  className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-sm font-mono text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                  Valuation Type
                </label>
                <select
                  value={valuationType}
                  onChange={(e) => {
                    setValuationType(e.target.value);
                    setAgreedValue(e.target.value === "agreed_value");
                  }}
                  className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-sm text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
                >
                  <option value="agreed_value">Agreed Value (约定价值)</option>
                  <option value="market_value">Market Value (市场价值)</option>
                </select>
              </div>
            </div>

            {/* Motor Premium */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                Gross Motor Premium (RM)
              </label>
              <input
                type="text"
                step="0.01"
                placeholder="e.g. 1850.50"
                value={motorPremium}
                onChange={(e) => setMotorPremium(e.target.value)}
                className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-sm font-mono text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
              />
              <span className="text-[11px] text-[#6e6e73] mt-1 block">
                Total payable will automatically include tenure Road Tax and Runner Fee
              </span>
            </div>

            {/* Perils & Endorsements */}
            <div className="grid grid-cols-2 gap-3 pt-1">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                  Towing Limit
                </label>
                <input
                  type="text"
                  placeholder="e.g. Unlimited or 300 KM"
                  value={towingLimit}
                  onChange={(e) => setTowingLimit(e.target.value)}
                  className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-sm text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                  Excess (RM)
                </label>
                <input
                  type="text"
                  step="0.01"
                  placeholder="0.00"
                  value={excess}
                  onChange={(e) => setExcess(e.target.value)}
                  className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-sm font-mono text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
                />
              </div>
            </div>

            {/* Windscreen & Special Perils */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                  Windscreen Coverage (RM)
                </label>
                <input
                  type="text"
                  step="0.01"
                  placeholder="e.g. 1500"
                  value={windscreen}
                  onChange={(e) => setWindscreen(e.target.value)}
                  className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-sm font-mono text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                  Special Perils / Flood
                </label>
                <input
                  type="text"
                  placeholder="e.g. Included or 0.20%"
                  value={specialPerils}
                  onChange={(e) => setSpecialPerils(e.target.value)}
                  className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-sm text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
                />
              </div>
            </div>

            {/* Legal Liability & Notes */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                  LLP / LLOP (Passenger)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Included or RM 30.00"
                  value={llpLlop}
                  onChange={(e) => setLlpLlop(e.target.value)}
                  className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-sm text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                  Notes / Endorsements
                </label>
                <input
                  type="text"
                  placeholder="e.g. Workshop panel only"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-sm text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
                />
              </div>
            </div>

            {/* Checkbox Features */}
            <div className="grid grid-cols-2 gap-3 pt-2">
              <label className="flex items-center gap-2 text-xs font-medium text-[#1b1717] cursor-pointer">
                <input
                  type="checkbox"
                  checked={agreedValue}
                  onChange={(e) => setAgreedValue(e.target.checked)}
                  className="rounded border-[#e5e5ea] text-[#1b1717] focus:ring-[#1b1717]"
                />
                <span>Agreed Value (约定价值)</span>
              </label>

              <label className="flex items-center gap-2 text-xs font-medium text-[#1b1717] cursor-pointer">
                <input
                  type="checkbox"
                  checked={waiverBetterment}
                  onChange={(e) => setWaiverBetterment(e.target.checked)}
                  className="rounded border-[#e5e5ea] text-[#1b1717] focus:ring-[#1b1717]"
                />
                <span>Waiver of Betterment</span>
              </label>
            </div>

            {/* Expandable Advanced Breakdown, Rating & PDF Detection Audit */}
            <div className="pt-2 border-t border-[#e5e5ea]">
              <button
                type="button"
                onClick={() => setIsAdvancedExpanded(!isAdvancedExpanded)}
                className="w-full flex items-center justify-between py-2 px-3 rounded-lg bg-[#f5f5f7] hover:bg-neutral-200 text-xs font-bold text-[#1b1717] transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <FileText size={16} weight="bold" className="text-[#6e6e73]" />
                  <span>Advanced Breakdown, Rating &amp; Detection Audit</span>
                </div>
                <span className="text-xs text-[#6e6e73] font-mono">
                  {isAdvancedExpanded ? "▲ Collapse" : "▼ Expand to View & Edit"}
                </span>
              </button>

              {isAdvancedExpanded && (
                <div className="mt-3 p-3.5 rounded-xl bg-neutral-50 border border-[#e5e5ea] space-y-4 text-xs">
                  {/* 1. Dynamic Rating & Tariff Math */}
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between border-b border-[#e5e5ea] pb-1">
                      <span className="font-bold text-[#1b1717] uppercase tracking-wider text-[11px]">
                        Dynamic Rating &amp; Tariff Math
                      </span>
                      <span className="text-[10px] text-[#6e6e73]">
                        Auto-calculates rate factor and basic premium
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-2.5">
                      <div>
                        <label className="block text-[10px] font-bold text-[#6e6e73] uppercase mb-1">
                          {basicFigureName || "Basic Premium"} (RM)
                        </label>
                        <input
                          type="text"
                          step="0.01"
                          value={basicFigureAmount}
                          onChange={(e) => handleBasicFigureChange(e.target.value)}
                          placeholder="e.g. 5436.88"
                          className="w-full rounded-md border border-[#e5e5ea] bg-white px-2 py-1.5 text-xs font-mono font-bold text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                        />
                      </div>

                      <div>
                        <label className="block text-[10px] font-bold text-[#6e6e73] uppercase mb-1">
                          Sum Insured (RM)
                        </label>
                        <input
                          type="text"
                          step="0.01"
                          value={sumInsured}
                          onChange={(e) => handleSumInsuredChange(e.target.value)}
                          placeholder="e.g. 199000"
                          className="w-full rounded-md border border-[#e5e5ea] bg-white px-2 py-1.5 text-xs font-mono font-bold text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                        />
                      </div>

                      <div>
                        <label className="block text-[10px] font-bold text-[#6e6e73] uppercase mb-1">
                          Net Rate Factor (6 dec)
                        </label>
                        <input
                          type="text"
                          step="0.000001"
                          value={netRateFactor}
                          onChange={(e) => handleRateFactorChange(e.target.value)}
                          placeholder="e.g. 0.027321"
                          className="w-full rounded-md border border-[#e5e5ea] bg-white px-2 py-1.5 text-xs font-mono font-bold text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                        />
                        {netRateFactor && parseFloat(netRateFactor) > 0 && (
                          <span className="text-[10px] text-[#6e6e73] block mt-0.5 font-mono">
                            Rate: {(parseFloat(netRateFactor) * 100).toFixed(4)}%
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* 2. Underwriting & Betterment Attributes */}
                  <div className="space-y-2 pt-1 border-t border-[#e5e5ea]">
                    <div className="flex items-center justify-between border-b border-[#e5e5ea] pb-1">
                      <span className="font-bold text-[#1b1717] uppercase tracking-wider text-[11px]">
                        Underwriting &amp; Betterment Rules
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div className="p-2 rounded-lg bg-white border border-[#e5e5ea]">
                        <span className="text-[10px] text-[#6e6e73] block">Vehicle Age</span>
                        <span className="font-bold text-[#1b1717]">
                          {initialData?.vehicle_age != null ? `${initialData.vehicle_age} Years` : "—"}
                        </span>
                      </div>

                      <div className="p-2 rounded-lg bg-white border border-[#e5e5ea]">
                        <span className="text-[10px] text-[#6e6e73] block">Betterment Scale</span>
                        <span className="font-bold text-[#1b1717]">
                          {initialData?.betterment_rate != null ? `${initialData.betterment_rate}%` : (initialData?.betterment_display || "0%")}
                        </span>
                      </div>

                      <div className="p-2 rounded-lg bg-white border border-[#e5e5ea]">
                        <span className="text-[10px] text-[#6e6e73] block">Waiver Status</span>
                        <span className={`font-bold ${waiverBetterment ? "text-emerald-700" : "text-amber-700"}`}>
                          {waiverBetterment ? "Waived (0% Co-pay)" : "Standard Tariff Co-pay"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* 3. Quotation Reference & Raw PDF Detection Audit */}
                  <div className="space-y-2 pt-1 border-t border-[#e5e5ea]">
                    <div className="flex items-center justify-between border-b border-[#e5e5ea] pb-1">
                      <span className="font-bold text-[#1b1717] uppercase tracking-wider text-[11px]">
                        Insurer Quotation Ref &amp; Detection Audit
                      </span>
                      <span className="text-[10px] text-[#6e6e73]">
                        Verified from uploaded insurer schedule
                      </span>
                    </div>

                    {/* Quotation Reference Input */}
                    <div>
                      <label className="block text-[10px] font-bold text-[#6e6e73] uppercase mb-1">
                        Insurer Quotation Reference No.
                      </label>
                      <input
                        type="text"
                        value={sourceQuotationNo}
                        onChange={(e) => setSourceQuotationNo(e.target.value)}
                        placeholder="e.g. QM12390133, FL22026M-00867209-001, QC590226-001"
                        className="w-full rounded-md border border-[#e5e5ea] bg-white px-2.5 py-1.5 text-xs font-mono font-bold text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
                      />
                    </div>

                    {/* Customer & Policyholder Info */}
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="p-2 rounded-lg bg-white border border-[#e5e5ea]">
                        <span className="text-[10px] text-[#6e6e73] block">Customer Name</span>
                        <span className="font-semibold text-[#1b1717] truncate block" title={initialData?.customer_name || "—"}>
                          {initialData?.customer_name || "—"}
                        </span>
                      </div>

                      <div className="p-2 rounded-lg bg-white border border-[#e5e5ea]">
                        <span className="text-[10px] text-[#6e6e73] block">IC / Business Reg No.</span>
                        <span className="font-semibold text-[#1b1717]">
                          {initialData?.ic_or_brn || "—"}
                        </span>
                      </div>
                    </div>

                    {/* Customer Address */}
                    {initialData?.customer_address && (
                      <div className="p-2 rounded-lg bg-white border border-[#e5e5ea]">
                        <span className="text-[10px] text-[#6e6e73] block">Customer Address</span>
                        <span className="text-[11px] text-[#1b1717] whitespace-pre-line">
                          {initialData.customer_address}
                        </span>
                      </div>
                    )}

                    {/* Detected Perils & Benefits List */}
                    {initialData?.detailed_perils && initialData.detailed_perils.length > 0 && (
                      <div className="p-2 rounded-lg bg-white border border-[#e5e5ea] space-y-1">
                        <span className="text-[10px] text-[#6e6e73] font-bold uppercase block">
                          Detected Riders &amp; Perils ({initialData.detailed_perils.length})
                        </span>
                        <div className="space-y-1 max-h-36 overflow-y-auto">
                          {initialData.detailed_perils.map((dp: any, idx: number) => (
                            <div key={idx} className="flex items-center justify-between text-[11px] py-0.5 border-b border-neutral-100 last:border-0">
                              <span className="text-[#1b1717] font-medium">{dp.name}</span>
                              <div className="flex items-center gap-2">
                                {dp.coverage_limit && (
                                  <span className="text-[10px] text-[#6e6e73] font-mono">
                                    {String(dp.coverage_limit)}
                                  </span>
                                )}
                                <span className="font-mono text-[#1b1717]">
                                  {dp.premium_cost ? `RM ${Number(dp.premium_cost).toFixed(2)}` : "Included"}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Auxiliary Vehicle Specs */}
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div className="p-1.5 rounded bg-white border border-[#e5e5ea]">
                        <span className="text-[10px] text-[#6e6e73] block">Chassis No.</span>
                        <span className="font-mono text-[11px] font-semibold text-[#1b1717] truncate block" title={initialData?.chassis_no || "—"}>
                          {initialData?.chassis_no || "—"}
                        </span>
                      </div>
                      <div className="p-1.5 rounded bg-white border border-[#e5e5ea]">
                        <span className="text-[10px] text-[#6e6e73] block">Engine No.</span>
                        <span className="font-mono text-[11px] font-semibold text-[#1b1717] truncate block" title={initialData?.engine_no || "—"}>
                          {initialData?.engine_no || "—"}
                        </span>
                      </div>
                      <div className="p-1.5 rounded bg-white border border-[#e5e5ea]">
                        <span className="text-[10px] text-[#6e6e73] block">Capacity / Unit</span>
                        <span className="font-mono text-[11px] font-semibold text-[#1b1717]">
                          {initialData?.engine_cc || "—"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-2 pt-4 border-t border-[#e5e5ea]">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={onClose}
                disabled={saving}
              >
                Cancel
              </Button>
              {initialData && !initialData.is_manual && tenureId && (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleReset}
                  disabled={saving}
                  className="text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                >
                  Reset to Detected
                </Button>
              )}
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={saving}
                className="bg-[#1b1717] hover:bg-black text-white"
                icon={<FloppyDisk size={14} weight="bold" />}
              >
                {saving ? "Saving..." : initialData ? "Save Changes" : "Add to Comparison"}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

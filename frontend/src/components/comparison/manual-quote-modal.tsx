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

interface ManualQuoteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (payload: any) => Promise<void>;
  initialData?: any;
  tenureId?: string;
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
  const [saving, setSaving] = useState(false);

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
      setSumInsured(initialData.sum_insured ? String(initialData.sum_insured) : "");
      setValuationType(initialData.valuation_type || "agreed_value");
      setMotorPremium(initialData.motor_premium ? String(initialData.motor_premium) : "");
      setTowingLimit(initialData.towing_limit || "Unlimited");
      setAgreedValue(initialData.agreed_value ?? true);
      setWaiverBetterment(initialData.waiver_betterment ?? true);
      setExcess(initialData.excess !== undefined && initialData.excess !== null ? String(initialData.excess) : "0");
      setWindscreen(initialData.windscreen_sum_insured ? String(initialData.windscreen_sum_insured) : "");
      setSpecialPerils(initialData.special_perils || "");
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
      setUploadFile(null);
      setUploadError("");
      setUploadProgress("");
    }
  }, [initialData, isOpen, tenureId]);

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
        is_manual: true,
      });
      onClose();
    } catch (err) {
      console.error("Failed to save manual quote:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (uploading) return;
    const files = Array.from(e.dataTransfer.files || []);
    const pdf = files.find((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (pdf) {
      setUploadFile(pdf);
      setUploadError("");
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
      setUploadFile(file);
      setUploadError("");
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

      const res = await fetch(`/api/comparison/${tenureId}/upload-quote`, {
        method: "POST",
        body: form,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Upload failed");
      }

      setUploadProgress("Scanning document & extracting quotation terms...");

      // Poll extraction job if returned
      if (data.job_id) {
        let attempts = 0;
        const maxAttempts = 35; // 35 * 800ms = 28s
        while (attempts < maxAttempts) {
          attempts++;
          await new Promise((r) => setTimeout(r, 800));
          const jobRes = await fetch(`/api/jobs/${data.job_id}`);
          if (!jobRes.ok) continue;
          const jobData = await jobRes.json();
          const state = jobData.job?.state;

          if (state === "completed") {
            setUploadProgress("Finalizing comparison matrix column...");
            break;
          }
          if (state === "failed" || state === "cancelled") {
            throw new Error(jobData.job?.error?.message || "Quotation extraction failed");
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
                  type="number"
                  step="0.01"
                  required
                  placeholder="e.g. 85000"
                  value={sumInsured}
                  onChange={(e) => setSumInsured(e.target.value)}
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
                type="number"
                step="0.01"
                required
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
                  type="number"
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
                  type="number"
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

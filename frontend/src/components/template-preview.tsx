"use client";

type PackageConfig = { name: string; included?: string[]; add_ons?: string[] };
type TemplateConfig = {
  fixed_fields?: {
    payment?: { method?: string; bank?: string; account?: string; account_name?: string };
    driver_box?: { label?: string };
    summary_fields?: Array<{ field: string; label: string; prefix?: string; suffix?: string }>;
    packages?: PackageConfig[];
  };
};

const demoValues: Record<string, string> = {
  coverage_type: "Comprehensive",
  cover_period: "09/07/2026 - 08/07/2027",
  valuation_type: "Market Value",
  car_model: "PROTON WAJA ENHANCED",
  ncd_percent: "45.00%",
  coverage_amount: "RM 10,000.00",
  premium: "RM 654.65",
  roadtax: "RM 0.00",
  service_fee: "RM 20.00",
  total_amount: "RM 717.02"
};

export function TemplatePreview({ template, packageName }: { template: TemplateConfig; packageName?: string }) {
  const config = template.fixed_fields || {};
  const packages = config.packages || [];
  const selectedPackage = packages.find((item) => item.name === packageName) || packages[0] || { name: "Base", included: [], add_ons: [] };
  const payment = config.payment || {};
  const summaryFields = config.summary_fields || [
    { field: "coverage_type", label: "Coverage Type" },
    { field: "cover_period", label: "Cover of Period" },
    { field: "valuation_type", label: "Valuation Type 估价方式" },
    { field: "car_model", label: "Car Model 车款" },
    { field: "ncd_percent", label: "NCD" },
    { field: "coverage_amount", label: "Coverage 保额" },
    { field: "premium", label: "Insurance Premium 车险" },
    { field: "roadtax", label: "Roadtax" },
    { field: "service_fee", label: "Runner Fee" },
    { field: "total_amount", label: "Total Premium 总额" }
  ];

  return (
    <div className="aspect-[210/297] w-full max-w-[560px] overflow-hidden border border-rl-line bg-gradient-to-br from-red-50 via-white to-blue-50 p-4 text-[10px] text-rl-textStrong shadow-sm">
      <div className="grid grid-cols-[110px_1fr_150px] items-start gap-3 border-b-2 border-rl-black pb-2">
        <div>
          <div className="text-xl font-black text-rl-red">RISK LOCKER</div>
          <div className="text-[8px]">MANAGEMENT<br />Business Insurance Agency</div>
        </div>
        <div className="flex min-h-14 items-center justify-center text-2xl font-black">{templateName(template)}</div>
        <div className="text-right text-base font-black text-rl-red">
          Motor Insurance Quotation
          <div className="mt-1 text-sm text-rl-textStrong">{selectedPackage.name}</div>
          <div className="text-sm text-rl-textStrong">JJC9250</div>
        </div>
      </div>
      <div className="grid grid-cols-[1fr_160px] gap-3 border-b-2 border-rl-black py-3">
        <div className="grid gap-1">
          {summaryFields.map((field) => (
            <div key={field.field} className={`grid grid-cols-[130px_12px_1fr] ${field.field === "total_amount" ? "border-y border-rl-black font-black" : ""}`}>
              <span>{field.label}</span>
              <span>:</span>
              <span>{demoValues[field.field] || "0"}</span>
            </div>
          ))}
        </div>
        <div className="grid gap-3">
          <div className="border-2 border-rl-black p-2 text-right">
            <strong>{payment.method || "Payment Method"}</strong>
            <div>Bank details</div>
            <div>{payment.account || "12300318500"}</div>
            <div>{payment.account_name || "Risklocker Sdn. Bhd."}</div>
            <div>{payment.bank || "Hong Leong Bank"}</div>
          </div>
          <div className="border-2 border-rl-black p-2 text-center font-bold">{config.driver_box?.label || "All Driver"}</div>
        </div>
      </div>
      <h3 className="my-3 text-center font-serif text-2xl font-black underline">Our Specials</h3>
      <div className="grid grid-cols-2 gap-2">
        {(selectedPackage.included || []).slice(0, 8).map((item) => <PreviewCard key={item} label={item} />)}
      </div>
      <h3 className="my-3 text-center font-serif text-xl font-black underline">You May Add On (With Additional Charges)</h3>
      <div className="grid grid-cols-2 gap-2">
        {(selectedPackage.add_ons || []).slice(0, 6).map((item) => <PreviewCard key={item} label={item} />)}
      </div>
      <div className="mt-8">*Terms and Condition Applied</div>
    </div>
  );
}

function PreviewCard({ label }: { label: string }) {
  return (
    <div className="grid min-h-9 grid-cols-[34px_1fr] border border-rl-black bg-white/70">
      <div className="flex items-center justify-center border-r border-rl-black text-[9px] font-black">IC</div>
      <div className="p-1 leading-snug">{label}</div>
    </div>
  );
}

function templateName(template: TemplateConfig) {
  const name = (template as { name?: string }).name || "Insurance";
  return name.replace("Risklocker ", "").replace(" Motor", "");
}

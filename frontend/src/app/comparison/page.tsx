"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { ComparisonMatrix } from "@/components/comparison/comparison-matrix";
import type { Route } from "next";
import { Columns, Plus, Car, MagnifyingGlass, X, Sparkle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

function ComparisonContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const initialTenureId = searchParams.get("tenure_id");

  const [tenureId, setTenureId] = useState<string | null>(initialTenureId);
  const [tenuresList, setTenuresList] = useState<any[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const [searchFilter, setSearchFilter] = useState("");

  // New Blank Deal Modal State
  const [isNewDealOpen, setIsNewDealOpen] = useState(false);
  const [newCustomerName, setNewCustomerName] = useState("");
  const [newVehiclePlate, setNewVehiclePlate] = useState("");
  const [newStartDate, setNewStartDate] = useState(() => {
    return new Date().toISOString().split("T")[0];
  });
  const [newEndDate, setNewEndDate] = useState(() => {
    const dt = new Date();
    dt.setFullYear(dt.getFullYear() + 1);
    dt.setDate(dt.getDate() - 1);
    return dt.toISOString().split("T")[0];
  });
  const [creatingDeal, setCreatingDeal] = useState(false);

  useEffect(() => {
    if (initialTenureId) {
      setTenureId(initialTenureId);
    }
  }, [initialTenureId]);

  // Load tenures list for switching
  const loadTenures = async () => {
    try {
      setLoadingList(true);
      const data = await api<any>("/tenures?page_size=60");
      const items = data?.items || [];
      setTenuresList(items);
    } catch (err) {
      console.error("Failed to load tenures list:", err);
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    loadTenures();
  }, []);

  const handleSelectTenure = (selectedId: string) => {
    setTenureId(selectedId);
    router.push(`/comparison?tenure_id=${selectedId}` as Route);
  };

  const handleStartDateChange = (newStart: string) => {
    setNewStartDate(newStart);
    if (!newStart) return;
    try {
      const parts = newStart.split("-");
      if (parts.length === 3) {
        const y = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10);
        const d = parseInt(parts[2], 10);
        if (!isNaN(y) && !isNaN(m) && !isNaN(d)) {
          const dt = new Date(Date.UTC(y, m - 1, d));
          dt.setUTCFullYear(dt.getUTCFullYear() + 1);
          dt.setUTCDate(dt.getUTCDate() - 1);
          setNewEndDate(dt.toISOString().split("T")[0]);
        }
      }
    } catch {
      // ignore
    }
  };

  const handleCreateNewDeal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newVehiclePlate.trim() || !newCustomerName.trim()) {
      alert("Please provide both Customer Name and Vehicle Plate Number.");
      return;
    }

    setCreatingDeal(true);
    try {
      const res = await api<{ id: string; vehicle_no: string; customer_name: string }>("/tenures", {
        method: "POST",
        body: JSON.stringify({
          vehicle_no: newVehiclePlate.trim().toUpperCase(),
          customer_name: newCustomerName.trim(),
          coverage_start_date: newStartDate,
          coverage_end_date: newEndDate,
        }),
      });

      setIsNewDealOpen(false);
      setNewCustomerName("");
      setNewVehiclePlate("");
      setTenureId(res.id);
      await loadTenures();
      router.push(`/comparison?tenure_id=${res.id}` as Route);
    } catch (err: any) {
      alert("Error creating new comparison deal: " + err.message);
    } finally {
      setCreatingDeal(false);
    }
  };

  // Filter tenures by customer name or vehicle plate
  const filteredTenures = tenuresList.filter((t) => {
    if (!searchFilter.trim()) return true;
    const q = searchFilter.toLowerCase();
    return (
      (t.vehicle_no && t.vehicle_no.toLowerCase().includes(q)) ||
      (t.customer_name && t.customer_name.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6">
      {/* Quick Customer & Tenure Switcher & Header Bar */}
      <div className="rounded-2xl border border-[#e5e5ea] bg-white p-4 shadow-sm flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-xl bg-[#f5f5f7] flex items-center justify-center text-[#1b1717] border border-[#e5e5ea]">
            <Columns size={20} weight="bold" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[#1b1717]">
              Marketing Comparison Workspace
            </h2>
            <p className="text-xs text-[#6e6e73]">
              Side-by-side underwriter quote comparison before issuing the final quotation
            </p>
          </div>
        </div>

        {/* Search, Tenure Selector & New Actions */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Search Filter */}
          <div className="relative w-44 sm:w-52">
            <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6e6e73]" />
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Search customer / plate..."
              className="w-full rounded-xl border border-[#e5e5ea] bg-[#f5f5f7] pl-8 pr-3 py-1.5 text-xs text-[#1b1717] placeholder:text-[#6e6e73] focus:outline-none focus:ring-1 focus:ring-[#1b1717]"
            />
          </div>

          {/* Tenure Combobox */}
          <div className="relative w-56 sm:w-64">
            <select
              value={tenureId || ""}
              onChange={(e) => handleSelectTenure(e.target.value)}
              className="w-full appearance-none rounded-xl border border-[#e5e5ea] bg-[#f5f5f7] px-3 py-1.5 text-xs font-semibold text-[#1b1717] focus:outline-none focus:ring-1 focus:ring-[#1b1717] transition-colors"
            >
              <option value="" disabled>
                -- Select a Client Deal --
              </option>
              {filteredTenures.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.vehicle_no} — {t.customer_name} ({t.expiry_month})
                </option>
              ))}
              {filteredTenures.length === 0 && (
                <option value="" disabled>No tenures found</option>
              )}
            </select>
          </div>

          {/* Start Blank Deal Action */}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsNewDealOpen(true)}
            icon={<Sparkle weight="bold" size={14} />}
            className="text-xs font-semibold text-[#1b1717] border-[#e5e5ea] hover:bg-neutral-50"
          >
            Start Blank Deal
          </Button>

          {/* Upload Comparison Deal */}
          <Button
            variant="primary"
            size="sm"
            onClick={() => router.push("/upload?mode=comparison" as Route)}
            icon={<Plus weight="bold" size={14} />}
            className="bg-[#1b1717] hover:bg-black text-white font-semibold text-xs whitespace-nowrap"
          >
            New Comparison Deal
          </Button>
        </div>
      </div>

      {/* Main Matrix Content */}
      {tenureId ? (
        <ComparisonMatrix tenureId={tenureId} />
      ) : (
        <div className="space-y-6">
          <div className="rounded-2xl border border-[#e5e5ea] bg-white p-8 text-center space-y-4 shadow-sm">
            <div className="size-12 rounded-full bg-[#f5f5f7] mx-auto flex items-center justify-center text-[#1b1717]">
              <Car size={24} weight="bold" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[#1b1717]">Marketing Comparison Workspace</h3>
              <p className="text-xs text-[#6e6e73] mt-1 max-w-md mx-auto">
                Select an existing customer deal below, start a blank ledger, or upload quotes to compare underwriters.
              </p>
            </div>
            <div className="flex items-center justify-center gap-3 pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setIsNewDealOpen(true)}
                icon={<Sparkle weight="bold" size={14} />}
                className="text-xs font-semibold text-[#1b1717]"
              >
                Start Blank Ledger
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => router.push("/upload?mode=comparison" as Route)}
                icon={<Plus weight="bold" size={14} />}
                className="bg-[#1b1717] hover:bg-black text-white text-xs font-semibold"
              >
                Upload Quotations
              </Button>
            </div>
          </div>

          {/* Recent Active Client Deals Grid */}
          {tenuresList.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[#6e6e73]">
                  Active Customer Deals ({tenuresList.length})
                </h4>
                <span className="text-[11px] text-[#6e6e73]">Click a deal to view comparison matrix</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {filteredTenures.slice(0, 12).map((t) => (
                  <div
                    key={t.id}
                    onClick={() => handleSelectTenure(t.id)}
                    className="p-4 rounded-xl border border-[#e5e5ea] bg-white hover:border-[#1b1717] hover:shadow-md transition-all cursor-pointer space-y-2 group"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-[#1b1717] bg-[#f5f5f7] px-2 py-0.5 rounded border border-[#e5e5ea] group-hover:bg-[#1b1717] group-hover:text-white transition-colors">
                        {t.vehicle_no}
                      </span>
                      <span className="text-[10px] font-semibold text-[#6e6e73]">
                        Exp: {t.expiry_month}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-[#1b1717] truncate">{t.customer_name}</p>
                      <p className="text-[11px] text-[#6e6e73] truncate">
                        {t.vehicle_model || "Motor Vehicle"} {t.engine_cc ? `(${t.engine_cc})` : ""}
                      </p>
                    </div>
                    <div className="flex items-center justify-between pt-1 border-t border-neutral-100 text-[10px]">
                      <span className="text-neutral-500 font-medium">Status: {t.status || "draft"}</span>
                      <span className="font-bold text-[#1b1717] group-hover:translate-x-0.5 transition-transform inline-flex items-center gap-0.5">
                        Open Matrix →
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modal: Start Blank Comparison Deal */}
      {isNewDealOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <div className="relative w-full max-w-md rounded-2xl bg-white border border-[#e5e5ea] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-[#e5e5ea] px-6 py-4 bg-[#f5f5f7]">
              <div>
                <h3 className="text-base font-bold text-[#1b1717]">
                  Start Blank Comparison Deal
                </h3>
                <p className="text-xs text-[#6e6e73] mt-0.5">
                  Open an empty ledger with just customer name and vehicle plate
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsNewDealOpen(false)}
                className="rounded-lg p-1.5 text-[#6e6e73] hover:text-[#1b1717] hover:bg-neutral-200 transition-colors"
              >
                <X size={18} weight="bold" />
              </button>
            </div>

            <form onSubmit={handleCreateNewDeal} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                  Customer / Policyholder Name
                </label>
                <input
                  type="text"
                  required
                  value={newCustomerName}
                  onChange={(e) => setNewCustomerName(e.target.value)}
                  placeholder="e.g. TAN AH KOW"
                  className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-sm text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                  Vehicle Registration Plate
                </label>
                <input
                  type="text"
                  required
                  value={newVehiclePlate}
                  onChange={(e) => setNewVehiclePlate(e.target.value.toUpperCase())}
                  placeholder="e.g. WX 8888"
                  className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-sm font-mono font-bold text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                    Start Date
                  </label>
                  <input
                    type="date"
                    required
                    value={newStartDate}
                    onChange={(e) => handleStartDateChange(e.target.value)}
                    className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-xs font-mono text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[#6e6e73] mb-1.5">
                    End Date (+1yr -1d)
                  </label>
                  <input
                    type="date"
                    required
                    value={newEndDate}
                    onChange={(e) => setNewEndDate(e.target.value)}
                    className="w-full rounded-lg border border-[#e5e5ea] bg-white px-3 py-2 text-xs font-mono text-[#1b1717] focus:outline-none focus:ring-2 focus:ring-[#1b1717]"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-4 border-t border-[#e5e5ea]">
                <Button type="button" variant="secondary" size="sm" onClick={() => setIsNewDealOpen(false)}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  loading={creatingDeal}
                  icon={<Sparkle size={15} weight="bold" />}
                  className="bg-[#1b1717] hover:bg-black text-white font-bold"
                >
                  Create Ledger
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ComparisonPage() {
  return (
    <AppShell>
      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <div className="size-8 animate-spin rounded-full border-2 border-[#1b1717] border-t-transparent" />
          </div>
        }
      >
        <ComparisonContent />
      </Suspense>
    </AppShell>
  );
}

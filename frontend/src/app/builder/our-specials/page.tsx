"use client";

import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { BuilderNav } from "@/components/builder-nav";
import { AppShell } from "@/components/app-shell";
import { api } from "@/lib/api";

type Benefit = { id: string; label: string; section: string; default_selected: boolean; status: string };

export default function BuilderOurSpecialsPage() {
  const [benefits, setBenefits] = useState<Benefit[]>([]);
  const [label, setLabel] = useState("");
  const [section, setSection] = useState("Motor Benefits");
  const [error, setError] = useState("");

  async function load() {
    const result = await api<{ benefits: Benefit[] }>("/admin/benefits");
    setBenefits(result.benefits);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load our specials."));
  }, []);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    await api("/admin/benefits", { method: "POST", body: JSON.stringify({ label, section, default_selected: false }) });
    setLabel("");
    await load();
  }

  return (
    <AppShell>
      <section className="grid gap-5">
        <div>
          <h1 className="text-3xl font-bold text-rl-textStrong">Our Specials</h1>
          <p className="mt-2">Manage our specials and add-on labels used by templates and review choices.</p>
        </div>
        <BuilderNav />
        {error ? <p className="rounded-md border border-rl-red bg-red-50 p-3 font-bold text-rl-red">{error}</p> : null}
        <form className="rl-panel grid gap-3 p-4" onSubmit={save}>
          <input className="rl-input" placeholder="Special label" value={label} onChange={(event) => setLabel(event.target.value)} required />
          <input className="rl-input" placeholder="Section" value={section} onChange={(event) => setSection(event.target.value)} required />
          <button className="rl-button w-fit" type="submit"><Save aria-hidden="true" size={18} />Save special</button>
        </form>
        <div className="grid gap-2">
          {benefits.map((benefit) => (
            <div key={benefit.id} className="rl-panel p-4">
              <div className="font-bold text-rl-textStrong">{benefit.label}</div>
              <div className="text-sm">{benefit.section} · {benefit.status}</div>
            </div>
          ))}
        </div>
      </section>
    </AppShell>
  );
}

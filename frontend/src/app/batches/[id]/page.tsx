"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { FilePenLine, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { api } from "@/lib/api";

type Batch = {
  id: string;
  name: string;
  status: string;
  files: Array<{ id: string; draft_id: string | null; filename: string; status: string; simple_issue?: string | null }>;
};

export default function BatchPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ batch: Batch }>(`/batches/${id}`)
      .then((result) => setBatch(result.batch))
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load batch."));
  }, [id]);

  return (
    <AppShell>
      <section className="grid gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold text-rl-textStrong">Preparing quotations</h1>
            <p className="mt-2 text-rl-text">Check values, edit if needed, then generate PDFs.</p>
          </div>
        </div>
        {error ? <p className="rounded-md border border-rl-red bg-red-50 p-3 font-bold text-rl-red">{error}</p> : null}
        <div className="rl-panel overflow-x-auto">
          <table className="rl-table min-w-[760px]">
            <thead>
              <tr>
                <th>Status</th>
                <th>File</th>
                <th>Check</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {batch?.files.map((file) => (
                <tr key={file.id}>
                  <td><StatusBadge status={file.status} /></td>
                  <td className="font-bold text-rl-textStrong">{file.filename}</td>
                  <td className="text-sm font-bold text-rl-warning">{file.simple_issue || ""}</td>
                  <td>
                    {file.draft_id ? (
                      <Link className="rl-button rl-button-secondary" href={`/review/${file.draft_id}`}>
                        <FilePenLine aria-hidden="true" size={18} />
                        Review / Edit
                      </Link>
                    ) : (
                      <button className="rl-button rl-button-secondary" disabled type="button">
                        <RefreshCw aria-hidden="true" size={18} />
                        Preparing
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}

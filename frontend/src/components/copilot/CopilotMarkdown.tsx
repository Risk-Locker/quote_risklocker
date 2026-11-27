"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import { Check, Copy, MagnifyingGlass } from "@phosphor-icons/react";

function renderInline(text: string, onNavigateDeepLink?: () => void): React.ReactNode[] {
  const tokens: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\((\/[^)\s]+)\)|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let keyIdx = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push(text.slice(lastIndex, match.index));
    }
    const raw = match[0];
    if (raw.startsWith("**") && raw.endsWith("**")) {
      tokens.push(
        <strong key={`b-${keyIdx++}`} className="font-semibold text-[var(--rl-text-strong)]">
          {raw.slice(2, -2)}
        </strong>
      );
    } else if (raw.startsWith("`") && raw.endsWith("`")) {
      tokens.push(
        <code
          key={`c-${keyIdx++}`}
          className="rounded bg-neutral-100 px-1.5 py-0.5 font-mono text-[12px] text-[var(--rl-text-strong)] border border-neutral-200"
        >
          {raw.slice(1, -1)}
        </code>
      );
    } else if (raw.startsWith("[") && match[2]) {
      const label = raw.slice(1, raw.indexOf("]("));
      const href = match[2];
      tokens.push(
        <Link
          key={`l-${keyIdx++}`}
          href={href as Route}
          onClick={() => onNavigateDeepLink?.()}
          className="font-semibold text-blue-700 underline decoration-blue-300 underline-offset-2 hover:text-blue-900"
        >
          {label}
        </Link>
      );
    } else if (raw.startsWith("*") && raw.endsWith("*")) {
      tokens.push(
        <em key={`i-${keyIdx++}`} className="italic">
          {raw.slice(1, -1)}
        </em>
      );
    } else {
      tokens.push(raw);
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    tokens.push(text.slice(lastIndex));
  }
  return tokens;
}

function stripMarkdownToPlain(cell: string): string {
  return (cell || "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}

const KNOWN_STATUS_VALUES = ["In Ledger", "Other Record Only", "Not Found"] as const;

function MarkdownTable({
  rows,
  onNavigateDeepLink,
}: {
  rows: string[][];
  onNavigateDeepLink?: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("All");
  const [pageSize, setPageSize] = useState<number>(50);
  const [page, setPage] = useState<number>(1);

  const header = rows[0] || [];
  const body = useMemo(() => (rows.length >= 2 ? rows.slice(2) : []), [rows]);
  const isLarge = body.length > 25;

  const statusMeta = useMemo(() => {
    if (!isLarge) return null;
    for (let colIdx = 0; colIdx < header.length; colIdx++) {
      const counts: Record<string, number> = {
        "In Ledger": 0,
        "Other Record Only": 0,
        "Not Found": 0,
      };
      let matchedAny = 0;
      for (const r of body) {
        const val = stripMarkdownToPlain(r[colIdx] || "");
        for (const known of KNOWN_STATUS_VALUES) {
          if (val === known) {
            counts[known] += 1;
            matchedAny += 1;
          }
        }
      }
      if (matchedAny > 0) {
        return { colIdx, counts };
      }
    }
    return null;
  }, [isLarge, header, body]);

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return body.filter((r) => {
      if (statusMeta && statusFilter !== "All") {
        const cellVal = stripMarkdownToPlain(r[statusMeta.colIdx] || "");
        if (cellVal !== statusFilter) return false;
      }
      if (q) {
        const joined = r.map((c) => stripMarkdownToPlain(c).toLowerCase()).join(" ");
        if (!joined.includes(q)) return false;
      }
      return true;
    });
  }, [body, search, statusFilter, statusMeta]);

  const effectivePageSize = pageSize === 0 ? Math.max(1, filteredRows.length) : pageSize;
  const totalPages = Math.max(1, Math.ceil(filteredRows.length / effectivePageSize));

  useEffect(() => {
    if (page > totalPages) {
      setPage(1);
    }
  }, [page, totalPages]);

  if (rows.length < 2) return null;

  const displayedRows = isLarge
    ? filteredRows.slice((page - 1) * effectivePageSize, page * effectivePageSize)
    : body;

  function handleCopyTable() {
    const rowsToCopy = isLarge ? filteredRows : body;
    const tsv = [header.map(stripMarkdownToPlain), ...rowsToCopy.map((r) => r.map(stripMarkdownToPlain))]
      .map((r) => r.join("\t"))
      .join("\n");
    navigator.clipboard.writeText(tsv).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  return (
    <div className="my-2.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 bg-neutral-50 border-b border-[var(--rl-border)]">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--rl-text-muted)]">
          Table ({isLarge && filteredRows.length !== body.length ? `${filteredRows.length.toLocaleString()} of ` : ""}
          {body.length.toLocaleString()} row{body.length === 1 ? "" : "s"})
        </span>
        <button
          type="button"
          onClick={handleCopyTable}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] cursor-pointer"
        >
          {copied ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
          {copied ? "Copied" : isLarge ? `Copy (${filteredRows.length})` : "Copy"}
        </button>
      </div>

      {isLarge && (
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 bg-white border-b border-neutral-100">
          <div className="relative flex-1 min-w-[180px] max-w-xs">
            <MagnifyingGlass
              size={13}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Filter plate, customer, status..."
              className="w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-neutral-50/70 pl-7 pr-2.5 py-1 text-xs text-[var(--rl-text-strong)] placeholder:text-[var(--rl-text-muted)] focus:outline-none focus:border-[var(--rl-black)] focus:bg-white"
            />
          </div>

          {statusMeta && (
            <div className="flex flex-wrap items-center gap-1">
              {(["All", "In Ledger", "Other Record Only", "Not Found"] as const).map((st) => {
                const count = st === "All" ? body.length : statusMeta.counts[st] || 0;
                if (st !== "All" && count === 0) return null;
                const active = statusFilter === st;
                return (
                  <button
                    key={st}
                    type="button"
                    onClick={() => {
                      setStatusFilter(st);
                      setPage(1);
                    }}
                    className={`rounded-full border px-2 py-0.5 text-[11px] font-medium transition-colors cursor-pointer ${
                      active
                        ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white"
                        : "border-neutral-200 bg-neutral-50 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    }`}
                  >
                    {st} ({count.toLocaleString()})
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div className={isLarge ? "max-h-[480px] overflow-auto" : "overflow-x-auto"}>
        <table className="w-full text-left border-collapse text-xs">
          <thead
            className={`${
              isLarge ? "sticky top-0 z-10 bg-neutral-50 shadow-[0_1px_0_0_rgba(0,0,0,0.08)]" : "bg-neutral-50/70 border-b border-[var(--rl-border)]"
            }`}
          >
            <tr>
              {header.map((cell, idx) => (
                <th key={idx} className="px-3 py-2 font-semibold text-[var(--rl-text-strong)] whitespace-nowrap">
                  {renderInline(cell, onNavigateDeepLink)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {displayedRows.map((r, rIdx) => (
              <tr key={rIdx} className="hover:bg-neutral-50/60">
                {r.map((cell, cIdx) => (
                  <td key={cIdx} className="px-3 py-1.5 text-[var(--rl-text)] whitespace-nowrap">
                    {renderInline(cell, onNavigateDeepLink)}
                  </td>
                ))}
              </tr>
            ))}
            {displayedRows.length === 0 && (
              <tr>
                <td colSpan={Math.max(1, header.length)} className="px-3 py-6 text-center text-xs text-[var(--rl-text-muted)]">
                  No matching rows found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {isLarge && (
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 bg-neutral-50 border-t border-[var(--rl-border)] text-[11px] text-[var(--rl-text-muted)]">
          <div className="flex items-center gap-1.5">
            <span>Rows/page:</span>
            {([50, 100] as const).map((sz) => (
              <button
                key={sz}
                type="button"
                onClick={() => {
                  setPageSize(sz);
                  setPage(1);
                }}
                className={`rounded px-1.5 py-0.5 cursor-pointer ${
                  pageSize === sz ? "bg-[var(--rl-black)] text-white font-semibold" : "hover:bg-neutral-200"
                }`}
              >
                {sz}
              </button>
            ))}
            {filteredRows.length <= 500 && (
              <button
                type="button"
                onClick={() => {
                  setPageSize(0);
                  setPage(1);
                }}
                className={`rounded px-1.5 py-0.5 cursor-pointer ${
                  pageSize === 0 ? "bg-[var(--rl-black)] text-white font-semibold" : "hover:bg-neutral-200"
                }`}
              >
                Show All
              </button>
            )}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded border border-neutral-200 bg-white px-2 py-0.5 hover:bg-neutral-100 disabled:opacity-40 cursor-pointer disabled:cursor-default"
              >
                Prev
              </button>
              <span className="font-mono">
                {page} / {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="rounded border border-neutral-200 bg-white px-2 py-0.5 hover:bg-neutral-100 disabled:opacity-40 cursor-pointer disabled:cursor-default"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function parseMarkdownTableRow(rawLine: string): string[] {
  const placeholder = "\u0000PIPE\u0000";
  return rawLine
    .trim()
    .replace(/\\\|/g, placeholder)
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim().replaceAll(placeholder, "|"));
}

export function CopilotMarkdown({
  content,
  onNavigateDeepLink,
}: {
  content: string;
  onNavigateDeepLink?: () => void;
}) {
  const lines = (content || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    if (line.trim().startsWith("```")) {
      const codeLines: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i += 1;
      }
      i += 1;
      blocks.push(
        <pre
          key={`pre-${i}`}
          className="my-2 overflow-x-auto rounded-[var(--rl-radius-sm)] bg-neutral-900 p-3 font-mono text-xs text-neutral-100"
        >
          {codeLines.join("\n")}
        </pre>
      );
      continue;
    }

    // Markdown table
    if (
      line.trim().startsWith("|") &&
      i + 1 < lines.length &&
      /^\s*\|?[\s:-]+\|/.test(lines[i + 1])
    ) {
      const tableRows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tableRows.push(parseMarkdownTableRow(lines[i]));
        i += 1;
      }
      blocks.push(<MarkdownTable key={`tbl-${i}`} rows={tableRows} onNavigateDeepLink={onNavigateDeepLink} />);
      continue;
    }

    // Headings
    const hMatch = line.match(/^(#{1,3})\s+(.+)$/);
    if (hMatch) {
      const level = hMatch[1].length;
      const cls =
        level === 1
          ? "text-base font-bold text-[var(--rl-text-strong)] mt-3 mb-1"
          : level === 2
          ? "text-sm font-bold text-[var(--rl-text-strong)] mt-2.5 mb-1"
          : "text-sm font-semibold text-[var(--rl-text-strong)] mt-2 mb-0.5";
      blocks.push(
        <div key={`h-${i}`} className={cls}>
          {renderInline(hMatch[2], onNavigateDeepLink)}
        </div>
      );
      i += 1;
      continue;
    }

    // Bullet list
    if (/^\s*[-*•]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*•]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*•]\s+/, ""));
        i += 1;
      }
      blocks.push(
        <ul key={`ul-${i}`} className="my-1.5 ml-4 list-disc flex flex-col gap-1 text-sm leading-relaxed text-[var(--rl-text)]">
          {items.map((it, idx) => (
            <li key={idx}>{renderInline(it, onNavigateDeepLink)}</li>
          ))}
        </ul>
      );
      continue;
    }

    // Numbered list
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i += 1;
      }
      blocks.push(
        <ol key={`ol-${i}`} className="my-1.5 ml-4 list-decimal flex flex-col gap-1 text-sm leading-relaxed text-[var(--rl-text)]">
          {items.map((it, idx) => (
            <li key={idx}>{renderInline(it, onNavigateDeepLink)}</li>
          ))}
        </ol>
      );
      continue;
    }

    // Blockquote
    if (line.trim().startsWith("> ")) {
      blocks.push(
        <blockquote
          key={`bq-${i}`}
          className="my-1.5 border-l-2 border-neutral-300 pl-3 text-sm text-[var(--rl-text-muted)] italic"
        >
          {renderInline(line.trim().slice(2), onNavigateDeepLink)}
        </blockquote>
      );
      i += 1;
      continue;
    }

    if (!line.trim()) {
      blocks.push(<div key={`sp-${i}`} className="h-1.5" />);
      i += 1;
      continue;
    }

    blocks.push(
      <p key={`p-${i}`} className="text-sm leading-relaxed text-[var(--rl-text)]">
        {renderInline(line, onNavigateDeepLink)}
      </p>
    );
    i += 1;
  }

  return <div className="flex flex-col gap-1">{blocks}</div>;
}

"use client";

import React, { useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import { Check, Copy } from "@phosphor-icons/react";

function renderInline(text: string): React.ReactNode[] {
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
          className="rounded bg-neutral-100 px-1 py-0.5 font-mono text-[11px] text-[var(--rl-text-strong)] border border-neutral-200"
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

function MarkdownTable({ rows }: { rows: string[][] }) {
  const [copied, setCopied] = useState(false);
  if (rows.length < 2) return null;
  const header = rows[0];
  const body = rows.slice(2);

  function handleCopyTable() {
    const tsv = [header, ...body].map((r) => r.join("\t")).join("\n");
    navigator.clipboard.writeText(tsv).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  return (
    <div className="my-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white overflow-hidden">
      <div className="flex items-center justify-between px-2.5 py-1 bg-neutral-50 border-b border-[var(--rl-border)]">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--rl-text-muted)]">
          Table ({body.length} row{body.length === 1 ? "" : "s"})
        </span>
        <button
          type="button"
          onClick={handleCopyTable}
          className="inline-flex items-center gap-1 text-[10px] font-medium text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] cursor-pointer"
        >
          {copied ? <Check size={11} className="text-emerald-600" /> : <Copy size={11} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-[11px]">
          <thead className="bg-neutral-50/70 border-b border-[var(--rl-border)]">
            <tr>
              {header.map((cell, idx) => (
                <th key={idx} className="px-2.5 py-1.5 font-semibold text-[var(--rl-text-strong)] whitespace-nowrap">
                  {renderInline(cell)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {body.map((r, rIdx) => (
              <tr key={rIdx} className="hover:bg-neutral-50/60">
                {r.map((cell, cIdx) => (
                  <td key={cIdx} className="px-2.5 py-1.5 text-[var(--rl-text)] whitespace-nowrap">
                    {renderInline(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function CopilotMarkdown({ content }: { content: string }) {
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
          className="my-2 overflow-x-auto rounded-[var(--rl-radius-sm)] bg-neutral-900 p-2.5 font-mono text-[11px] text-neutral-100"
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
        const parsed = lines[i]
          .trim()
          .replace(/^\|/, "")
          .replace(/\|$/, "")
          .split("|")
          .map((c) => c.trim());
        tableRows.push(parsed);
        i += 1;
      }
      blocks.push(<MarkdownTable key={`tbl-${i}`} rows={tableRows} />);
      continue;
    }

    // Headings
    const hMatch = line.match(/^(#{1,3})\s+(.+)$/);
    if (hMatch) {
      const level = hMatch[1].length;
      const cls =
        level === 1
          ? "text-sm font-bold text-[var(--rl-text-strong)] mt-2 mb-1"
          : level === 2
          ? "text-xs font-bold text-[var(--rl-text-strong)] mt-2 mb-1"
          : "text-xs font-semibold text-[var(--rl-text-strong)] mt-1.5 mb-0.5";
      blocks.push(
        <div key={`h-${i}`} className={cls}>
          {renderInline(hMatch[2])}
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
        <ul key={`ul-${i}`} className="my-1.5 ml-4 list-disc space-y-1 text-xs text-[var(--rl-text)]">
          {items.map((it, idx) => (
            <li key={idx}>{renderInline(it)}</li>
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
        <ol key={`ol-${i}`} className="my-1.5 ml-4 list-decimal space-y-1 text-xs text-[var(--rl-text)]">
          {items.map((it, idx) => (
            <li key={idx}>{renderInline(it)}</li>
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
          className="my-1.5 border-l-2 border-neutral-300 pl-2.5 text-xs text-[var(--rl-text-muted)] italic"
        >
          {renderInline(line.trim().slice(2))}
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
      <p key={`p-${i}`} className="text-xs leading-relaxed text-[var(--rl-text)]">
        {renderInline(line)}
      </p>
    );
    i += 1;
  }

  return <div className="space-y-0.5">{blocks}</div>;
}

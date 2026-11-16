"use client";

import React from "react";

export interface HighlightTextProps {
  text: string | null | undefined;
  query: string | null | undefined;
  className?: string;
}

/**
 * Clean, safe text highlighter for table cells and search results.
 * Highlights matching substrings with a readable amber badge while preserving
 * exact casing of the original text.
 */
export function HighlightText({ text, query, className }: HighlightTextProps) {
  if (!text) return null;
  if (!query || !query.trim()) {
    return <span className={className}>{text}</span>;
  }

  const trimmed = query.trim();
  // Escape special regex characters
  const escaped = trimmed.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex = new RegExp(`(${escaped})`, "gi");
  const parts = text.split(regex);

  if (parts.length <= 1) {
    return <span className={className}>{text}</span>;
  }

  return (
    <span className={className}>
      {parts.map((part, index) =>
        regex.test(part) ? (
          <mark
            key={index}
            className="bg-amber-200/90 text-neutral-950 font-bold px-0.5 rounded-[2px]"
          >
            {part}
          </mark>
        ) : (
          <React.Fragment key={index}>{part}</React.Fragment>
        )
      )}
    </span>
  );
}

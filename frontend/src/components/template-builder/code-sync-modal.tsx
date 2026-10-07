"use client";

import { useState } from "react";
import { Check, ClipboardText, CodeSimple, X } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { BlockTree } from "@/lib/template-block-engine";

interface CodeSyncModalProps {
  tree: BlockTree;
  isOpen: boolean;
  onClose: () => void;
  onApplyCode: (updatedTree: BlockTree) => void;
}

export function CodeSyncModal({ tree, isOpen, onClose, onApplyCode }: CodeSyncModalProps) {
  const [codeText, setCodeText] = useState(() => JSON.stringify(tree, null, 2));
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  function handleCopy() {
    navigator.clipboard.writeText(codeText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleApply() {
    setError(null);
    try {
      const parsed = JSON.parse(codeText);
      if (!parsed.sections || !Array.isArray(parsed.sections)) {
        throw new Error("Invalid structure: missing 'sections' array.");
      }
      onApplyCode(parsed);
      onClose();
    } catch (e: any) {
      setError(`JSON Syntax Error: ${e.message}`);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="bg-white rounded-lg shadow-2xl border border-slate-200 w-full max-w-4xl h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2">
            <CodeSimple size={20} weight="bold" className="text-red-600" />
            <div>
              <h2 className="text-sm font-bold text-slate-900">Template JSON Declarative Code</h2>
              <p className="text-xs text-slate-500">
                Directly edit the template DOM hierarchy. Changes update the visual canvas instantly.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-slate-400 hover:text-slate-800 hover:bg-slate-200 transition-all cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Code Editor Body */}
        <div className="flex-1 p-4 flex flex-col min-h-0 bg-slate-950">
          <Textarea
            value={codeText}
            onChange={(e) => setCodeText(e.target.value)}
            className="w-full flex-1 font-mono text-xs text-emerald-400 bg-slate-950 border border-slate-800 rounded p-3 resize-none focus:outline-none focus:border-red-500"
            spellCheck={false}
          />
          {error && (
            <div className="mt-2 text-xs font-semibold text-red-400 bg-red-950/40 p-2 rounded border border-red-800">
              {error}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-300 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-100 transition-all cursor-pointer"
          >
            {copied ? <Check size={14} className="text-emerald-600" /> : <ClipboardText size={14} />}
            {copied ? "Copied to Clipboard" : "Copy Code"}
          </button>

          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button size="sm" onClick={handleApply}>
              Apply Code to Canvas
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

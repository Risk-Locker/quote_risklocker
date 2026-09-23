"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  X,
  Lightning,
  ArrowsClockwise,
  CheckCircle,
  WarningCircle,
  ShieldCheck,
  Check,
  Tag,
  Car,
  PencilSimple,
  Plus,
  Trash,
  GitBranch,
  ArrowsOutSimple,
  ArrowsInSimple,
  Info,
  PaperPlaneRight,
  ChatCircleText,
  MagnifyingGlass,
  ArrowCounterClockwise,
  Robot,
  StopCircle,
} from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { NeuralCubeIcon } from "@/components/ui/neural-cube-icon";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type OperationPreviewItem = {
  catalog_id: string;
  catalog_name: string;
  action: "update_plan_item" | "add_offering" | "remove_offering" | "update_description";
  concept_key: string;
  concept_label: string;
  current_value?: string | null;
  new_value?: string | null;
  current_description?: string | null;
  new_description?: string | null;
  details?: string | null;
};

type PreviewResponse = {
  summary: string;
  parsed_intent: {
    intent: string;
    operations: Record<string, unknown>[];
  };
  company_id: string;
  target_company_name?: string;
  matched_catalogs: Array<{
    id: string;
    name: string;
    vehicle_category?: string | null;
    engine_type?: string | null;
  }>;
  operations_preview: OperationPreviewItem[];
  mutations: Array<Record<string, unknown>>;
  active_profile_id?: string | null;
  active_profile_name?: string | null;
  active_profile_version?: string | null;
  suggested_next_version?: string | null;
  is_active_profile?: boolean;
};

type DuplicateGroup = {
  group_type: string;
  sha: string;
  car_plate: string;
  filename: string;
  company: string;
  roadtax: string;
  gross_premium: string;
  total_instances: number;
  keep_session: {
    session_id: string;
    quotation_ref?: string;
    filename: string;
    created_at: string;
    roadtax: string;
    gross_premium: string;
  };
  trash_sessions: Array<{
    session_id: string;
    quotation_ref?: string;
    filename: string;
    created_at: string;
    plate?: string;
    company?: string;
    roadtax?: string;
    gross_premium?: string;
    sha?: string;
  }>;
};

type ChatAction =
  | {
      type: "catalog_diff";
      title?: string;
      company_id?: string;
      preview: PreviewResponse;
    }
  | {
      type: "session_cleanup";
      title?: string;
      redundant_count: number;
      groups: DuplicateGroup[];
      session_ids_to_trash: string[];
    }
  | {
      type: "profile_cleanup";
      title?: string;
      profiles: Array<{ id: string; name: string; version: string; is_active: boolean }>;
    };

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions?: ChatAction[];
  timestamp: Date;
};

type Company = {
  id: string;
  name: string;
  code?: string;
};

const QUICK_PROMPTS = [
  {
    label: "Engine CC Breakdown",
    prompt: "What is the list of CCs of types of cars you found across all quotations?",
  },
  {
    label: "Insurer Quote Ranking",
    prompt: "Which insurance companies had more quotes and what is their market share?",
  },
  {
    label: "Cars & Models Mostly Found",
    prompt: "What types of cars, makes, and models are mostly found?",
  },
  {
    label: "Most Popular Benefits",
    prompt: "What benefits and optional covers are mostly used?",
  },
  {
    label: "AmAssurance Status & Towing",
    prompt: "Check if AmAssurance got how many catalogs and whats the situation",
  },
  {
    label: "Check Session Duplicates",
    prompt: "Check if there are duplicate sessions in the database and show cleanable uploads",
  },
];

export function GlobalAiCopilot() {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [drawerSize, setDrawerSize] = useState<"normal" | "wide" | "maximized">("normal");
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>("all");
  const [scope, setScope] = useState<"all" | "catalogs" | "sessions">("all");
  const [inputQuery, setInputQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Chat message thread
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastSentQueryRef = useRef<string>("");

  function handleSelectPrompt(promptText: string) {
    setInputQuery(promptText);
    setTimeout(() => {
      inputRef.current?.focus();
    }, 50);
  }

  function handleAbortRequest() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setLoading(false);
    if (lastSentQueryRef.current) {
      setInputQuery(lastSentQueryRef.current);
    }
    setMessages((prev) => {
      if (!prev.length) return prev;
      const last = prev[prev.length - 1];
      if (last.role === "user") {
        return [
          ...prev.slice(0, -1),
          { ...last, content: `${last.content} (stopped)` },
          {
            id: Math.random().toString(36).substring(2, 9),
            role: "assistant",
            content: "⏹ Request stopped. Your query has been restored to the input box so you can adjust and send again.",
            timestamp: new Date(),
          },
        ];
      }
      return prev;
    });
  }

  // Catalog mutation state
  const [selectedMutationIndices, setSelectedMutationIndices] = useState<Record<string, Set<number>>>({});
  const [applyingCatalog, setApplyingCatalog] = useState(false);
  const [forkNewVersion, setForkNewVersion] = useState(false);
  const [catalogSuccessMsg, setCatalogSuccessMsg] = useState<string | null>(null);

  // Session hygiene action state
  const [cleaningDuplicates, setCleaningDuplicates] = useState(false);
  const [sessionCleanupMsg, setSessionCleanupMsg] = useState<string | null>(null);

  // Interactive Duplicate Audit State
  const [inspectingDuplicateGroups, setInspectingDuplicateGroups] = useState<DuplicateGroup[] | null>(null);
  const [selectedTrashSessionIds, setSelectedTrashSessionIds] = useState<Set<string>>(new Set());
  const [duplicateSearchQuery, setDuplicateSearchQuery] = useState("");

  const filteredDuplicateGroups = useMemo(() => {
    if (!inspectingDuplicateGroups) return [];
    if (!duplicateSearchQuery.trim()) return inspectingDuplicateGroups;
    const q = duplicateSearchQuery.toLowerCase();
    return inspectingDuplicateGroups.filter((grp) => {
      const matchPlate = (grp.car_plate || "").toLowerCase().includes(q);
      const matchCompany = (grp.company || "").toLowerCase().includes(q);
      const matchFile = (grp.filename || "").toLowerCase().includes(q);
      const matchRef = (grp.keep_session?.quotation_ref || "").toLowerCase().includes(q);
      const matchTrash = grp.trash_sessions.some(
        (t) => (t.quotation_ref || "").toLowerCase().includes(q) || (t.filename || "").toLowerCase().includes(q)
      );
      return matchPlate || matchCompany || matchFile || matchRef || matchTrash;
    });
  }, [inspectingDuplicateGroups, duplicateSearchQuery]);

  // Profile cleanup action state
  const [cleaningProfiles, setCleaningProfiles] = useState(false);
  const [profileCleanupMsg, setProfileCleanupMsg] = useState<string | null>(null);

  // Action card dismissal state (Cancel button on proposals)
  const [dismissedActions, setDismissedActions] = useState<Record<string, boolean>>({});

  function handleDismissAction(actionKey: string) {
    setDismissedActions((prev) => ({ ...prev, [actionKey]: true }));
  }

  function handleResetChat() {
    setMessages([]);
    setSelectedMutationIndices({});
    setDismissedActions({});
    setCatalogSuccessMsg(null);
    setSessionCleanupMsg(null);
    setProfileCleanupMsg(null);
    setError(null);
  }

  // Load companies on mount
  useEffect(() => {
    async function fetchCompanies() {
      try {
        const res = await api<{ companies: { items: Company[] } }>(
          "/business/companies?page=1&page_size=100"
        );
        const list = res?.companies?.items || [];
        if (list.length) {
          setCompanies(list);
        }
      } catch {
        // Fallback
      }
    }
    fetchCompanies();
  }, []);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Submit chat message
  async function handleSendMessage(overrideText?: string) {
    const textToSend = (overrideText ?? inputQuery).trim();
    if (!textToSend || loading) return;

    setError(null);
    setInputQuery("");

    // Detect mentioned company in query
    const lower = textToSend.toLowerCase();
    const mentionedCompany = companies.find(
      (c) =>
        lower.includes(c.name.toLowerCase()) ||
        (c.code && lower.includes(c.code.toLowerCase()))
    );
    if (mentionedCompany && mentionedCompany.id !== selectedCompanyId) {
      setSelectedCompanyId(mentionedCompany.id);
    }

    const userMsg: ChatMessage = {
      id: Math.random().toString(36).substring(2, 9),
      role: "user",
      content: textToSend,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;
    lastSentQueryRef.current = textToSend;

    try {
      const historyPayload = messages.slice(-8).map((m) => {
        let content = m.content;
        if (m.role === "assistant" && m.actions && m.actions.length > 0) {
          const actionSummaries = m.actions
            .map((act) => {
              if (act.type === "catalog_diff" && act.preview?.operations_preview) {
                const ops = act.preview.operations_preview
                  .map(
                    (op, idx) =>
                      `[Item ${idx + 1}] ${op.action}: ${op.concept_label || op.concept_key} -> ${op.new_value || op.new_description || "updated"}`
                  )
                  .join("; ");
                return `[Active Proposed Changes for ${act.company_id || "selected company"}: ${ops}]`;
              }
              if (act.type === "session_cleanup") {
                return `[Active Proposed Session Cleanup: ${act.redundant_count} duplicate sessions ready to clean]`;
              }
              if (act.type === "profile_cleanup") {
                return `[Active Proposed Profile Cleanup: ${act.profiles?.length || 0} unused profiles]`;
              }
              return "";
            })
            .filter(Boolean)
            .join("\n");
          if (actionSummaries) {
            content += `\n\n${actionSummaries}`;
          }
        }
        return {
          role: m.role,
          content,
        };
      });

      const companyParam = mentionedCompany
        ? mentionedCompany.id
        : (selectedCompanyId === "all" ? undefined : selectedCompanyId);

      const res = await api<{
        reply: string;
        actions: ChatAction[];
        facts_summary: Record<string, unknown>;
      }>("/copilot/chat", {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          message: textToSend,
          company_id: companyParam,
          history: historyPayload,
          scope,
        }),
      });

      const assistantMsg: ChatMessage = {
        id: Math.random().toString(36).substring(2, 9),
        role: "assistant",
        content: res.reply,
        actions: res.actions,
        timestamp: new Date(),
      };

      // If catalog diff action present, pre-select all mutation indices
      if (res.actions) {
        res.actions.forEach((act, actIdx) => {
          if (act.type === "catalog_diff" && act.preview?.mutations) {
            setSelectedMutationIndices((prev) => ({
              ...prev,
              [`${assistantMsg.id}_${actIdx}`]: new Set(act.preview.mutations.map((_, i) => i)),
            }));
          }
        });
      }

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      if (err?.name === "AbortError") {
        return; // User intentionally stopped the request
      }
      setError(apiErrorMessage(err));
      const errorMsg: ChatMessage = {
        id: Math.random().toString(36).substring(2, 9),
        role: "assistant",
        content: "Sorry, I encountered an issue analyzing your request. Please try again or refine your query.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  }

  // Execute session duplicate cleanup
  async function handleCleanDuplicates(sessionIds: string[]) {
    if (!sessionIds.length || cleaningDuplicates) return;
    setCleaningDuplicates(true);
    setSessionCleanupMsg(null);
    try {
      const res = await api<{ cleaned_count: number; message: string }>(
        "/copilot/sessions/cleanup-duplicates",
        {
          method: "POST",
          body: JSON.stringify({ session_ids: sessionIds }),
        }
      );
      setSessionCleanupMsg(res.message || `Successfully moved ${res.cleaned_count} duplicate sessions to Trash!`);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setCleaningDuplicates(false);
    }
  }

  // Execute catalog mutations
  async function handleApplyCatalogMutations(
    preview: PreviewResponse,
    companyId: string,
    actionKey: string
  ) {
    if (!preview || applyingCatalog) return;
    setApplyingCatalog(true);
    setCatalogSuccessMsg(null);
    try {
      const selectedIndices = selectedMutationIndices[actionKey] || new Set();
      const mutationsToApply = (preview.mutations || []).map((m, idx) => ({
        ...m,
        is_selected: selectedIndices.has(idx),
      }));

      const payload = {
        mutations: mutationsToApply,
        operations: preview.parsed_intent?.operations || [],
        target_profile_action: forkNewVersion ? "clone_new" : "in_place",
        create_new_profile_version: forkNewVersion,
        activate_profile: true,
      };

      const res = await api<{ applied_count: number; message: string }>(
        `/business/companies/${companyId}/catalog-operations/apply`,
        {
          method: "POST",
          body: JSON.stringify(payload),
        }
      );
      setCatalogSuccessMsg(res.message || `Successfully applied ${res.applied_count} catalog changes!`);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setApplyingCatalog(false);
    }
  }

  // Execute profile cleanup
  async function handleCleanProfiles(profileIds: string[]) {
    if (!profileIds.length || cleaningProfiles) return;
    setCleaningProfiles(true);
    setProfileCleanupMsg(null);
    try {
      const res = await api<{ cleaned_count: number; message: string }>(
        "/copilot/profiles/cleanup-dummy",
        {
          method: "POST",
          body: JSON.stringify({ profile_ids: profileIds }),
        }
      );
      setProfileCleanupMsg(res.message || `Cleaned ${res.cleaned_count} unused profile(s)!`);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setCleaningProfiles(false);
    }
  }

  const activeCompany = companies.find((c) => c.id === selectedCompanyId);

  return (
    <>
      {/* Floating Launcher Button */}
      {!isOpen && (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="group fixed bottom-6 right-6 z-40 flex items-center h-14 w-14 hover:w-36 rounded-full bg-[var(--rl-black)] hover:bg-[#111111] text-white shadow-2xl transition-all duration-300 ease-out border border-white/10 hover:shadow-[0_8px_32px_rgba(0,0,0,0.35)] overflow-hidden cursor-pointer justify-center hover:justify-start hover:px-3.5"
          aria-label="Open AI Copilot"
        >
          <div className="w-8 h-8 rounded-full bg-white/15 flex items-center justify-center text-white shrink-0 group-hover:scale-105 transition-transform duration-200">
            <Robot size={20} weight="fill" />
          </div>
          <span className="max-w-0 overflow-hidden group-hover:max-w-xs transition-all duration-300 ease-out whitespace-nowrap text-xs font-bold tracking-wide pl-0 group-hover:pl-2.5 opacity-0 group-hover:opacity-100 text-white">
            Start Chat
          </span>
        </button>
      )}

      {/* Slide-out Copilot Drawer */}
      {isOpen && (
        <aside
          aria-label="RiskLocker AI Copilot Drawer"
          className={`fixed top-0 right-0 z-50 h-screen bg-white text-[var(--rl-text-strong)] shadow-2xl border-l border-[var(--rl-border)] flex flex-col transition-all duration-300 ease-in-out ${
            drawerSize === "maximized"
              ? "w-[96vw] max-w-[1550px]"
              : drawerSize === "wide" || isExpanded
              ? "w-[840px] max-w-[95vw]"
              : "w-[480px] max-w-[95vw]"
          }`}
        >
          {/* Header */}
          <div className="p-4 border-b border-[var(--rl-border)] bg-white flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-[var(--rl-black)] flex items-center justify-center text-white shrink-0">
                <Robot size={18} weight="fill" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">AI Copilot</h3>
                  <Badge variant="default" className="text-[10px] px-1.5 py-0 font-medium">
                    Intelligence & Operator
                  </Badge>
                </div>
                <p className="text-[11px] text-[var(--rl-text-muted)]">
                  Dataset analytics, towing audits & duplicate hygiene
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleResetChat}
                className="p-1.5 rounded-[var(--rl-radius-sm)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-[var(--rl-surface-muted)] transition-colors"
                title="Reset conversation"
              >
                <ArrowCounterClockwise size={16} />
              </button>
              <button
                type="button"
                onClick={() => {
                  setDrawerSize((prev) => {
                    const next = prev === "normal" ? "wide" : prev === "wide" ? "maximized" : "normal";
                    setIsExpanded(next !== "normal");
                    return next;
                  });
                }}
                className={`px-2 py-1 rounded-[var(--rl-radius-sm)] transition-colors flex items-center gap-1 cursor-pointer ${
                  drawerSize === "maximized"
                    ? "bg-[var(--rl-black)] text-white font-semibold shadow-xs"
                    : drawerSize === "wide"
                    ? "bg-blue-100 text-blue-900 font-semibold border border-blue-300"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-[var(--rl-surface-muted)] border border-transparent"
                }`}
                title={
                  drawerSize === "normal"
                    ? "Widen drawer to 840px"
                    : drawerSize === "wide"
                    ? "Maximize drawer (Fullscreen)"
                    : "Restore standard width (480px)"
                }
              >
                {drawerSize === "maximized" ? (
                  <>
                    <ArrowsInSimple size={14} weight="bold" />
                    <span className="text-[11px]">Standard</span>
                  </>
                ) : drawerSize === "wide" ? (
                  <>
                    <ArrowsOutSimple size={14} weight="bold" />
                    <span className="text-[11px]">Maximize</span>
                  </>
                ) : (
                  <>
                    <ArrowsOutSimple size={14} />
                    <span className="text-[11px]">Expand</span>
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="p-1.5 rounded-[var(--rl-radius-sm)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] hover:bg-[var(--rl-surface-muted)] transition-colors"
                title="Close drawer"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Context Control Bar */}
          <div className="px-4 py-2.5 border-b border-[var(--rl-border)] bg-[var(--rl-surface-muted)] flex items-center justify-between gap-3 text-xs shrink-0">
            <div className="flex items-center gap-2 w-1/2">
              <span className="text-[11px] font-medium text-[var(--rl-text-muted)] whitespace-nowrap">Insurer:</span>
              <Select
                value={selectedCompanyId}
                onChange={(e) => setSelectedCompanyId(e.target.value)}
                className="text-xs h-7 py-0 bg-white"
              >
                <option value="all">All Companies (Comparative)</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </div>

            <div className="flex items-center gap-2 w-1/2 justify-end">
              <span className="text-[11px] font-medium text-[var(--rl-text-muted)] whitespace-nowrap">Scope:</span>
              <Select
                value={scope}
                onChange={(e) => setScope(e.target.value as any)}
                className="text-xs h-7 py-0 bg-white w-32"
              >
                <option value="all">All Systems</option>
                <option value="catalogs">Catalogs Only</option>
                <option value="sessions">Sessions & Quotes</option>
              </Select>
            </div>
          </div>

          {/* Chat Messages Container */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center text-center p-6 mt-4 space-y-3">
                <div className="w-12 h-12 rounded-[var(--rl-radius-md)] bg-[var(--rl-surface-muted)] border border-[var(--rl-border)] flex items-center justify-center text-[var(--rl-text-strong)]">
                  <ChatCircleText size={24} weight="regular" />
                </div>
                <div className="space-y-1 max-w-sm">
                  <h4 className="text-xs font-bold text-[var(--rl-text-strong)]">How can I help you today?</h4>
                  <p className="text-[11px] text-[var(--rl-text-muted)]">
                    Ask questions about insurer catalogs, check towing descriptions and upgrade conditions, or run a 1-click duplicate upload cleanup.
                  </p>
                </div>

                {/* Prompt Suggestions */}
                <div className="w-full pt-2 text-left space-y-1.5">
                  <p className="text-[10px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">
                    Suggested Questions & Operations
                  </p>
                  <div className="flex flex-col gap-1.5">
                    {QUICK_PROMPTS.map((qp, i) => (
                      <button
                        key={i}
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleSelectPrompt(qp.prompt);
                        }}
                        className="w-full text-left p-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white hover:bg-[var(--rl-surface-muted)] text-[11px] transition-colors flex items-center justify-between group"
                      >
                        <span className="font-medium text-[var(--rl-text-strong)]">{qp.label}</span>
                        <span className="text-[10px] text-[var(--rl-text-muted)] group-hover:text-[var(--rl-text-strong)]">
                          Use ↵
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Render Messages */}
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
              >
                {/* Message Bubble */}
                <div
                  className={`max-w-[90%] p-3 rounded-[var(--rl-radius-md)] text-xs leading-relaxed ${
                    m.role === "user"
                      ? "bg-[var(--rl-black)] text-white shadow-sm"
                      : "bg-white text-[var(--rl-text-strong)] border border-[var(--rl-border)] shadow-sm"
                  }`}
                >
                  <div className="whitespace-pre-wrap font-sans text-xs">{m.content}</div>
                </div>

                {/* Attached Interactive Action Cards */}
                {m.actions && m.actions.length > 0 && (
                  <div className="w-full mt-3 space-y-3">
                    {m.actions.map((act, actIdx) => {
                      const actionKey = `${m.id}_${actIdx}`;

                      if (dismissedActions[actionKey]) {
                        return (
                          <div
                            key={actIdx}
                            className="p-2.5 rounded-[var(--rl-radius-sm)] border border-dashed border-[var(--rl-border)] bg-[var(--rl-surface-muted)] text-[11px] text-[var(--rl-text-muted)] flex items-center justify-between"
                          >
                            <div className="flex items-center gap-2">
                              <X size={12} className="text-neutral-400" />
                              <span className="italic">Proposal dismissed by user</span>
                            </div>
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-200 text-neutral-600 font-medium">
                              Dismissed
                            </span>
                          </div>
                        );
                      }

                      // 1. Session Cleanup Action Card
                      if (act.type === "session_cleanup") {
                        return (
                          <Card
                            key={actIdx}
                            className="p-3.5 border border-[var(--rl-border)] bg-[var(--rl-surface-muted)] space-y-3 rounded-[var(--rl-radius-md)]"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <div className="w-6 h-6 rounded-[var(--rl-radius-sm)] bg-[var(--rl-black)] text-white flex items-center justify-center">
                                  <ShieldCheck size={14} weight="fill" />
                                </div>
                                <div>
                                  <h4 className="text-xs font-bold text-[var(--rl-text-strong)]">
                                    {act.title || `Clean ${act.redundant_count} Duplicate Uploads`}
                                  </h4>
                                  <p className="text-[11px] text-[var(--rl-text-muted)]">
                                    Identical file hash uploads. Edited quotes (e.g. roadtax adjustments) are safely kept.
                                  </p>
                                </div>
                              </div>
                              <Badge variant="default" className="text-[10px]">
                                {act.redundant_count} Redundant
                              </Badge>
                            </div>

                            {/* Preview list of duplicate sets */}
                            <div className="max-h-48 overflow-y-auto space-y-2 pr-1">
                              {act.groups.map((grp, gIdx) => (
                                <div
                                  key={gIdx}
                                  className="p-2.5 rounded-[var(--rl-radius-sm)] bg-white border border-[var(--rl-border)] text-[11px] space-y-1"
                                >
                                  <div className="flex items-center justify-between font-semibold">
                                    <span className="font-mono text-[var(--rl-text-strong)]">
                                      Plate: {grp.car_plate}
                                    </span>
                                    <span className="text-[var(--rl-text-muted)] text-[10px]">
                                      {grp.total_instances} uploads · {grp.company}
                                    </span>
                                  </div>
                                  <div className="text-[10px] text-[var(--rl-text-muted)] flex items-center gap-2">
                                    <span>File: {grp.filename}</span>
                                    {grp.roadtax && <span>· RT: RM {grp.roadtax}</span>}
                                    {grp.gross_premium && <span>· Gross: RM {grp.gross_premium}</span>}
                                  </div>
                                  <div className="pt-1 flex items-center gap-2 text-[10px]">
                                    <span className="px-1.5 py-0.5 rounded-[var(--rl-radius-sm)] bg-emerald-100 text-emerald-800 font-semibold">
                                      KEEP: Session #{grp.keep_session.session_id.substring(0, 8)}
                                    </span>
                                    <span className="px-1.5 py-0.5 rounded-[var(--rl-radius-sm)] bg-rose-100 text-rose-800 font-medium">
                                      TO TRASH: {grp.trash_sessions.length} copy(s)
                                    </span>
                                  </div>
                                </div>
                              ))}
                            </div>

                            {/* Action execution */}
                            {sessionCleanupMsg ? (
                              <div className="p-2.5 rounded-[var(--rl-radius-sm)] bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
                                <CheckCircle size={15} weight="fill" />
                                <span>{sessionCleanupMsg}</span>
                              </div>
                            ) : (
                              <div className="flex flex-col gap-2">
                                <Button
                                  type="button"
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => {
                                    setInspectingDuplicateGroups(act.groups);
                                    setSelectedTrashSessionIds(new Set(act.session_ids_to_trash));
                                  }}
                                  className="w-full h-8 text-xs px-3 border border-[var(--rl-border)] bg-white text-[var(--rl-text-strong)] hover:bg-neutral-50 flex items-center justify-center gap-1.5 font-semibold cursor-pointer shadow-2xs"
                                >
                                  <MagnifyingGlass size={14} weight="bold" />
                                  <span>Inspect & Audit Duplicates ({act.groups.length} Sets)</span>
                                </Button>
                                <div className="flex items-center gap-2">
                                  <Button
                                    type="button"
                                    variant="secondary"
                                    size="sm"
                                    onClick={() => handleDismissAction(actionKey)}
                                    disabled={cleaningDuplicates}
                                    className="h-8 text-xs px-3 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] border border-[var(--rl-border)] bg-white cursor-pointer"
                                  >
                                    Cancel
                                  </Button>
                                  <Button
                                    size="sm"
                                    onClick={() => handleCleanDuplicates(act.session_ids_to_trash)}
                                    disabled={cleaningDuplicates}
                                    className="flex-1 h-8 text-xs bg-[var(--rl-black)] hover:bg-[var(--rl-text-strong)] text-white gap-2 font-medium cursor-pointer"
                                  >
                                    {cleaningDuplicates ? (
                                      <>
                                        <ArrowsClockwise size={13} className="animate-spin" />
                                        Moving duplicates to Trash...
                                      </>
                                    ) : (
                                      <>
                                        <Trash size={13} />
                                        Confirm & Clean {act.redundant_count} Redundant Duplicates
                                      </>
                                    )}
                                  </Button>
                                </div>
                              </div>
                            )}
                          </Card>
                        );
                      }

                      // 2. Catalog Diff Action Card
                      if (act.type === "catalog_diff") {
                        const selectedIndices = selectedMutationIndices[actionKey] || new Set();
                        return (
                          <Card
                            key={actIdx}
                            className="p-3.5 border border-[var(--rl-border)] bg-white space-y-3 rounded-[var(--rl-radius-md)]"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <div className="w-6 h-6 rounded-[var(--rl-radius-sm)] bg-[var(--rl-black)] text-white flex items-center justify-center">
                                  <PencilSimple size={14} />
                                </div>
                                <h4 className="text-xs font-bold text-[var(--rl-text-strong)]">
                                  {act.title || "Proposed Catalog Changes"}
                                </h4>
                              </div>
                              <Badge variant="default" className="text-[10px]">
                                {act.preview.operations_preview.length} Items
                              </Badge>
                            </div>

                            {/* Diff items preview */}
                            <div className="max-h-56 overflow-y-auto border border-[var(--rl-border)] rounded-[var(--rl-radius-sm)] divide-y divide-[var(--rl-border)]">
                              {act.preview.operations_preview.map((op, opIdx) => {
                                const isChecked = selectedIndices.has(opIdx);
                                return (
                                  <div
                                    key={opIdx}
                                    onClick={() => {
                                      const next = new Set(selectedIndices);
                                      if (next.has(opIdx)) next.delete(opIdx);
                                      else next.add(opIdx);
                                      setSelectedMutationIndices((prev) => ({
                                        ...prev,
                                        [actionKey]: next,
                                      }));
                                    }}
                                    className={`p-2.5 text-xs flex items-start gap-2.5 cursor-pointer transition-colors ${
                                      isChecked ? "bg-white" : "bg-[var(--rl-surface-muted)] opacity-60"
                                    }`}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={isChecked}
                                      onChange={() => {}}
                                      className="mt-0.5 rounded border-[var(--rl-border)] text-[var(--rl-black)] focus:ring-0"
                                    />
                                    <div className="flex-1 space-y-1">
                                      <div className="flex items-center justify-between">
                                        <span className="font-semibold text-[var(--rl-text-strong)]">
                                          {op.concept_label}
                                        </span>
                                        <span className="text-[10px] text-[var(--rl-text-muted)]">
                                          {op.catalog_name}
                                        </span>
                                      </div>

                                      {op.action === "update_plan_item" && (
                                        <div className="flex items-center gap-2 text-[11px]">
                                          <span className="line-through text-rose-600">
                                            {op.current_value || "None"}
                                          </span>
                                          <span className="text-[var(--rl-text-muted)]">→</span>
                                          <span className="font-semibold text-emerald-600">
                                            {op.new_value}
                                          </span>
                                        </div>
                                      )}

                                      {op.action === "update_description" && (
                                        <div className="text-[10px] space-y-0.5">
                                          <p className="line-through text-rose-600 truncate max-w-sm">
                                            {op.current_description || "None"}
                                          </p>
                                          <p className="font-medium text-emerald-600 truncate max-w-sm">
                                            {op.new_description}
                                          </p>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>

                            {/* Versioning toggle */}
                            <div className="flex items-center justify-between pt-1 border-t border-[var(--rl-border)] text-xs">
                              <label className="flex items-center gap-2 cursor-pointer text-[11px] text-[var(--rl-text-muted)]">
                                <input
                                  type="checkbox"
                                  checked={forkNewVersion}
                                  onChange={(e) => setForkNewVersion(e.target.checked)}
                                  className="rounded border-[var(--rl-border)]"
                                />
                                <span>Create new profile version (Default: In-place update)</span>
                              </label>
                            </div>

                            {/* Apply execution */}
                            {catalogSuccessMsg ? (
                              <div className="p-2.5 rounded-[var(--rl-radius-sm)] bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
                                <CheckCircle size={15} weight="fill" />
                                <span>{catalogSuccessMsg}</span>
                              </div>
                            ) : (
                              <div className="flex items-center gap-2">
                                <Button
                                  type="button"
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => handleDismissAction(actionKey)}
                                  disabled={applyingCatalog}
                                  className="h-8 text-xs px-3 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] border border-[var(--rl-border)] bg-white"
                                >
                                  Cancel
                                </Button>
                                <Button
                                  size="sm"
                                  onClick={() =>
                                    handleApplyCatalogMutations(
                                      act.preview,
                                      act.company_id || selectedCompanyId,
                                      actionKey
                                    )
                                  }
                                  disabled={applyingCatalog || selectedIndices.size === 0}
                                  className="flex-1 h-8 text-xs bg-[var(--rl-black)] hover:bg-[var(--rl-text-strong)] text-white gap-2 font-medium"
                                >
                                  {applyingCatalog ? (
                                    <>
                                      <ArrowsClockwise size={13} className="animate-spin" />
                                      Applying Changes...
                                    </>
                                  ) : (
                                    <>
                                      <Check size={13} />
                                      Confirm & Apply {selectedIndices.size} Changes
                                    </>
                                  )}
                                </Button>
                              </div>
                            )}
                          </Card>
                        );
                      }

                      // 3. Profile Cleanup Card
                      if (act.type === "profile_cleanup") {
                        return (
                          <Card
                            key={actIdx}
                            className="p-3 border border-[var(--rl-border)] bg-[var(--rl-surface-muted)] space-y-2.5 rounded-[var(--rl-radius-md)]"
                          >
                            <div className="flex items-center justify-between">
                              <h4 className="text-xs font-bold text-[var(--rl-text-strong)]">
                                {act.title || "Unused Profile Cleanup"}
                              </h4>
                              <Badge variant="default" className="text-[10px]">
                                {act.profiles.length} Profiles
                              </Badge>
                            </div>
                            <div className="text-[11px] space-y-1">
                              {act.profiles.map((p) => (
                                <div
                                  key={p.id}
                                  className="p-2 bg-white rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] flex items-center justify-between"
                                >
                                  <span>{p.name} ({p.version})</span>
                                  <span className="text-[10px] text-amber-700 font-medium">Inactive</span>
                                </div>
                              ))}
                            </div>
                            {profileCleanupMsg ? (
                              <div className="p-2 text-xs bg-emerald-50 text-emerald-800 rounded">
                                {profileCleanupMsg}
                              </div>
                            ) : (
                              <div className="flex items-center gap-2">
                                <Button
                                  type="button"
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => handleDismissAction(actionKey)}
                                  disabled={cleaningProfiles}
                                  className="h-7 text-xs px-3 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] border border-[var(--rl-border)] bg-white"
                                >
                                  Cancel
                                </Button>
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  onClick={() => handleCleanProfiles(act.profiles.map((p) => p.id))}
                                  disabled={cleaningProfiles}
                                  className="flex-1 h-7 text-xs bg-white hover:bg-neutral-100"
                                >
                                  {cleaningProfiles ? "Cleaning..." : "Deactivate Unused Profiles"}
                                </Button>
                              </div>
                            )}
                          </Card>
                        );
                      }

                      return null;
                    })}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex items-center justify-between p-2.5 rounded-[var(--rl-radius-sm)] bg-[var(--rl-surface-muted)] border border-[var(--rl-border)] text-xs text-[var(--rl-text-muted)] animate-pulse">
                <div className="flex items-center gap-2">
                  <ArrowsClockwise size={14} className="animate-spin text-[var(--rl-black)] shrink-0" />
                  <span className="font-medium text-[var(--rl-text-strong)]">Thinking & querying live database...</span>
                </div>
                <button
                  type="button"
                  onClick={handleAbortRequest}
                  className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-[var(--rl-red)] bg-white hover:bg-[var(--rl-red-light)] border border-[var(--rl-red)]/30 rounded-[var(--rl-radius-sm)] transition-colors shadow-xs"
                >
                  <StopCircle size={14} weight="bold" />
                  <span>Cancel / Stop</span>
                </button>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Chat Input & Scope Anchors */}
          <div className="p-3 border-t border-[var(--rl-border)] bg-white space-y-2.5 shrink-0">
            {/* Quick scope anchor buttons */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-[11px]">
              <span className="text-[10px] text-[var(--rl-text-muted)] font-medium shrink-0">Anchors:</span>
              <button
                type="button"
                onClick={() => handleSelectPrompt(`For ${activeCompany?.name || "AmAssurance"} all EV catalogs: `)}
                className="px-2 py-0.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface-muted)] hover:bg-white text-[10px] whitespace-nowrap"
              >
                ⚡ EV Scope
              </button>
              <button
                type="button"
                onClick={() => handleSelectPrompt(`For ${activeCompany?.name || "AmAssurance"} Private Car ICE: `)}
                className="px-2 py-0.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface-muted)] hover:bg-white text-[10px] whitespace-nowrap"
              >
                🚗 ICE Scope
              </button>
              <button
                type="button"
                onClick={() => handleSelectPrompt("Check if there are duplicate sessions in the database")}
                className="px-2 py-0.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface-muted)] hover:bg-white text-[10px] whitespace-nowrap"
              >
                🔍 Check Duplicates
              </button>
            </div>

            {/* Input Box */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex items-center gap-2"
            >
              <Input
                ref={inputRef}
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                placeholder={`Ask Copilot or instruct changes (e.g. 'How many catalogs for ${activeCompany?.name || "AmAssurance"}?', 'Check duplicate sessions')...`}
                className="text-xs h-9 bg-white border-[var(--rl-border)] rounded-[var(--rl-radius-sm)]"
                disabled={loading}
              />
              {loading ? (
                <Button
                  type="button"
                  onClick={handleAbortRequest}
                  className="h-9 px-3 bg-[var(--rl-red)] hover:bg-[var(--rl-red)]/90 text-white shrink-0 rounded-[var(--rl-radius-sm)] flex items-center gap-1.5"
                  title="Stop query"
                >
                  <StopCircle size={15} weight="bold" />
                  <span className="text-xs font-semibold">Stop</span>
                </Button>
              ) : (
                <Button
                  type="submit"
                  disabled={!inputQuery.trim()}
                  className="h-9 px-3 bg-[var(--rl-black)] hover:bg-[var(--rl-text-strong)] text-white shrink-0 rounded-[var(--rl-radius-sm)]"
                >
                  <PaperPlaneRight size={15} weight="bold" />
                </Button>
              )}
            </form>
          </div>
        </aside>
      )}

      {/* Interactive Duplicate Audit & Inspection Modal */}
      {inspectingDuplicateGroups && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in">
          <Card className="w-full max-w-6xl bg-white shadow-2xl rounded-[var(--rl-radius-lg)] border border-[var(--rl-border)] overflow-hidden flex flex-col max-h-[92vh]">
            {/* Modal Header */}
            <div className="p-4 border-b border-[var(--rl-border)] bg-[var(--rl-surface-muted)] flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-[var(--rl-black)] text-white flex items-center justify-center shrink-0">
                  <ShieldCheck size={20} weight="fill" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-[var(--rl-text-strong)]">
                      Duplicate Sessions Audit & Inspection
                    </h3>
                    <Badge variant="default" className="text-xs">
                      {inspectingDuplicateGroups.length} Duplicate Sets
                    </Badge>
                  </div>
                  <p className="text-xs text-[var(--rl-text-muted)]">
                    Review duplicate uploads, verify exact timestamps and quotation references, and choose sessions to clean.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setInspectingDuplicateGroups(null)}
                className="text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] p-1.5 rounded cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            {/* Filter and Bulk Action Controls */}
            <div className="p-3 border-b border-[var(--rl-border)] bg-gray-50 flex flex-wrap items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2 flex-1 min-w-[240px] max-w-md">
                <MagnifyingGlass size={14} className="text-[var(--rl-text-muted)]" />
                <Input
                  type="text"
                  placeholder="Filter by plate, insurer, filename, or ref..."
                  value={duplicateSearchQuery}
                  onChange={(e) => setDuplicateSearchQuery(e.target.value)}
                  className="h-8 text-xs bg-white"
                />
              </div>

              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    const allTrash = new Set<string>();
                    for (const grp of inspectingDuplicateGroups) {
                      for (const s of grp.trash_sessions) allTrash.add(s.session_id);
                    }
                    setSelectedTrashSessionIds(allTrash);
                  }}
                  className="h-7 text-[11px] px-2.5 bg-white border border-[var(--rl-border)] cursor-pointer"
                >
                  Select All Duplicates
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setSelectedTrashSessionIds(new Set())}
                  className="h-7 text-[11px] px-2.5 bg-white border border-[var(--rl-border)] cursor-pointer"
                >
                  Deselect All
                </Button>
                <span className="text-xs font-semibold px-2.5 py-1 rounded bg-amber-100 text-amber-900 border border-amber-200">
                  {selectedTrashSessionIds.size} selected for Trash
                </span>
              </div>
            </div>

            {/* Detailed Table */}
            <div className="flex-1 overflow-y-auto p-4">
              <div className="border border-[var(--rl-border)] rounded-[var(--rl-radius-md)] overflow-hidden">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-neutral-100 border-b border-[var(--rl-border)] text-[var(--rl-text-strong)] font-semibold text-[11px]">
                      <th className="p-2.5 w-12 text-center">Trash?</th>
                      <th className="p-2.5">Vehicle Plate & Insurer</th>
                      <th className="p-2.5">Quotation Ref & ID</th>
                      <th className="p-2.5">Upload Timestamp</th>
                      <th className="p-2.5">File Name & Hash</th>
                      <th className="p-2.5">Extracted Roadtax / Gross</th>
                      <th className="p-2.5">Survivorship Status</th>
                      <th className="p-2.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--rl-border)]">
                    {filteredDuplicateGroups.map((grp, grpIdx) => {
                      const allInGroup = [
                        { ...grp.keep_session, is_keep: true, plate: grp.car_plate, company: grp.company, sha: grp.sha },
                        ...grp.trash_sessions.map((t) => ({ ...t, is_keep: false, plate: grp.car_plate, company: grp.company, sha: grp.sha })),
                      ];

                      return allInGroup.map((item) => {
                        const isTrash = !item.is_keep;
                        const isChecked = selectedTrashSessionIds.has(item.session_id);
                        const formattedDate = item.created_at
                          ? new Date(item.created_at).toLocaleString("en-MY", {
                              year: "numeric",
                              month: "short",
                              day: "2-digit",
                              hour: "2-digit",
                              minute: "2-digit",
                              second: "2-digit",
                            })
                          : "Unknown Date";

                        return (
                          <tr
                            key={`${grpIdx}_${item.session_id}`}
                            className={`transition-colors ${
                              item.is_keep
                                ? "bg-emerald-50/50 hover:bg-emerald-50"
                                : isChecked
                                ? "bg-rose-50/40 hover:bg-rose-50/70"
                                : "bg-white hover:bg-neutral-50"
                            }`}
                          >
                            <td className="p-2.5 text-center">
                              {isTrash ? (
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={() => {
                                    const next = new Set(selectedTrashSessionIds);
                                    if (next.has(item.session_id)) next.delete(item.session_id);
                                    else next.add(item.session_id);
                                    setSelectedTrashSessionIds(next);
                                  }}
                                  className="rounded text-[var(--rl-black)] focus:ring-0 cursor-pointer"
                                />
                              ) : (
                                <span className="text-xs text-emerald-700 font-bold" title="Keep this quotation">
                                  ✓
                                </span>
                              )}
                            </td>
                            <td className="p-2.5 font-medium">
                              <span className="font-mono font-bold text-[var(--rl-text-strong)] mr-2">
                                {grp.car_plate || "UNREGISTERED"}
                              </span>
                              <Badge variant="default" className="text-[10px] py-0 px-1.5 font-normal">
                                {grp.company}
                              </Badge>
                            </td>
                            <td className="p-2.5 font-mono text-[11px]">
                              <span className="font-semibold text-[var(--rl-text-strong)]">
                                {item.quotation_ref || `RL-${item.session_id.substring(0, 8).toUpperCase()}`}
                              </span>
                              <div className="text-[10px] text-[var(--rl-text-muted)] font-mono">
                                #{item.session_id.substring(0, 8)}
                              </div>
                            </td>
                            <td className="p-2.5 font-mono text-[11px] text-[var(--rl-text-strong)] whitespace-nowrap">
                              {formattedDate}
                            </td>
                            <td className="p-2.5 max-w-[200px]">
                              <div className="truncate font-medium text-[var(--rl-text-strong)] text-[11px]" title={item.filename}>
                                {item.filename}
                              </div>
                              <div className="text-[10px] font-mono text-[var(--rl-text-muted)] truncate" title={item.sha}>
                                SHA: {item.sha ? item.sha.substring(0, 10) : "N/A"}
                              </div>
                            </td>
                            <td className="p-2.5 text-[11px]">
                              {grp.roadtax && (
                                <div className="text-[var(--rl-text-muted)]">
                                  RT: <span className="font-semibold text-[var(--rl-text-strong)]">RM {grp.roadtax}</span>
                                </div>
                              )}
                              {grp.gross_premium && (
                                <div className="text-[var(--rl-text-muted)]">
                                  Gross: <span className="font-semibold text-[var(--rl-text-strong)]">RM {grp.gross_premium}</span>
                                </div>
                              )}
                              {!grp.roadtax && !grp.gross_premium && <span className="text-[var(--rl-text-muted)]">-</span>}
                            </td>
                            <td className="p-2.5">
                              {item.is_keep ? (
                                <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-900 border border-emerald-300">
                                  <CheckCircle size={12} weight="fill" />
                                  KEEP (Survivor)
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-900 border border-rose-300">
                                  <Trash size={11} />
                                  DUPLICATE
                                </span>
                              )}
                            </td>
                            <td className="p-2.5 text-right whitespace-nowrap">
                              <a
                                href={`/sessions/${item.session_id}/review`}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-600 hover:text-blue-800 hover:underline"
                              >
                                View Quote ↗
                              </a>
                            </td>
                          </tr>
                        );
                      });
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-[var(--rl-border)] bg-[var(--rl-surface-muted)] flex items-center justify-between">
              <span className="text-xs text-[var(--rl-text-muted)]">
                Soft-delete: sessions moved to Trash can be restored anytime from the Sessions list.
              </span>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setInspectingDuplicateGroups(null)}
                  disabled={cleaningDuplicates}
                >
                  Close
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  onClick={async () => {
                    await handleCleanDuplicates(Array.from(selectedTrashSessionIds));
                    setInspectingDuplicateGroups(null);
                  }}
                  disabled={cleaningDuplicates || selectedTrashSessionIds.size === 0}
                  className="bg-rose-600 hover:bg-rose-700 text-white font-semibold flex items-center gap-1.5 cursor-pointer"
                >
                  {cleaningDuplicates ? (
                    <>
                      <ArrowsClockwise size={14} className="animate-spin" />
                      Moving to Trash...
                    </>
                  ) : (
                    <>
                      <Trash size={14} weight="bold" />
                      Clean {selectedTrashSessionIds.size} Selected Duplicates
                    </>
                  )}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}

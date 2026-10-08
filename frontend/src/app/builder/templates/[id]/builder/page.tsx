"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle,
  CopySimple,
  FloppyDisk,
  Sparkle,
  Star,
  WarningCircle,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

import {
  type BlockTree,
  type BlockSection,
  type BlockContainer,
  type TemplateBlock,
  type BlockType,
  type SelectionTarget,
  type CustomerSessionPreview,
} from "@/components/template-builder/clean-studio/types";
import {
  createDefaultBlockTree,
  compileBlockTreeToCanvasElements,
} from "@/lib/template-block-engine";
import { PalettePanel } from "@/components/template-builder/clean-studio/palette-panel";
import { InteractiveCanvas } from "@/components/template-builder/clean-studio/interactive-canvas";
import { LiveA4Preview } from "@/components/template-builder/clean-studio/live-a4-preview";
import { InspectorPanel } from "@/components/template-builder/clean-studio/inspector-panel";

interface TemplateRecord {
  id: string;
  revision: number;
  name: string;
  insurance_type: string;
  status: string;
  locked: boolean;
  fixed_fields: any;
}

export default function TemplateBuilderPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { toast } = useToast();

  const [template, setTemplate] = useState<TemplateRecord | null>(null);
  const [tree, setTree] = useState<BlockTree>(() => createDefaultBlockTree());
  const [selection, setSelection] = useState<SelectionTarget | null>(null);
  const [sessions, setSessions] = useState<CustomerSessionPreview[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number>(Date.now());
  const [savedFingerprint, setSavedFingerprint] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [isBenefitEditorOpen, setIsBenefitEditorOpen] = useState(false);

  const dirty = useMemo(() => {
    return JSON.stringify(tree) !== savedFingerprint;
  }, [tree, savedFingerprint]);

  const load = useCallback(async () => {
    try {
      const [templateRes, sessionsRes] = await Promise.all([
        api<{ template: TemplateRecord }>(`/admin/templates/${id}`),
        api<{ sessions: any[] }>("/sessions?page=1&page_size=20").catch(() => ({ sessions: [] })),
      ]);

      const loaded = templateRes.template;
      setTemplate(loaded);

      if (loaded.fixed_fields?.block_tree) {
        setTree(loaded.fixed_fields.block_tree);
        setSavedFingerprint(JSON.stringify(loaded.fixed_fields.block_tree));
      } else {
        const def = createDefaultBlockTree();
        setTree(def);
        setSavedFingerprint(JSON.stringify(def));
      }

      if (sessionsRes.sessions?.length) {
        const mapped: CustomerSessionPreview[] = sessionsRes.sessions.map((s) => ({
          id: s.id,
          quotation_reference: s.quotation_ref || "RL260000313",
          customer_name: s.insured_name || "CHENG TECK KIONG",
          vehicle_no: s.vehicle_plate || "ANY 368",
          car_model: s.vehicle_model || "Tesla Model 3 Performance",
          insurance_company: s.detected_company || "BERJAYA SOMPO INSURANCE BERHAD",
          coverage_type: "Comprehensive",
          cover_period: s.coverage_start_date
            ? `${s.coverage_start_date} to ${s.coverage_end_date || ""}`
            : "04-06-2026 to 03-06-2027",
          engine_cc: "9.4 kW",
          ncd_percent: "25.00%",
          valuation_type: "Market Value",
          authorized_driver: "All Driver",
          excess_amount: "RM 0.00",
          coverage_amount: "RM 199,000.00",
          premium: s.total_premium || "3,758.21",
          roadtax: "20.00",
          runner_fee: "10.00",
          total_amount: s.total_premium || "4,073.21",
          valid_until: "14 Days",
        }));
        setSessions(mapped);
        setActiveSessionId(null);
      }
    } catch (err: any) {
      toast(`Failed to load template: ${err.message}`, "error");
    }
  }, [id, toast]);

  useEffect(() => {
    if (authLoading || !user) return;
    load();
  }, [authLoading, user, load]);

  // Helper to commit tree change and trigger lastUpdated
  function commitTree(newTree: BlockTree) {
    setTree(newTree);
    setLastUpdated(Date.now());
  }

  // --- ACTIONS ---

  function handleAddSection() {
    const newSection: BlockSection = {
      id: `sec_${Date.now()}`,
      name: "New Custom Section",
      sectionType: "body",
      containers: [
        {
          id: `cnt_${Date.now()}`,
          direction: "column",
          width: "100%",
          blocks: [],
        },
      ],
    };
    commitTree({
      ...tree,
      sections: [...tree.sections, newSection],
    });
    setSelection({ type: "section", id: newSection.id });
    toast("Added new section", "success");
  }

  function handleAddContainer(preset: "1-col" | "2-col-equal" | "2-col-wide-narrow" | "3-col") {
    // Find target section (selected section or default to last section)
    let targetSectionId = "";
    if (selection?.type === "section") {
      targetSectionId = selection.id;
    } else if (selection?.sectionId) {
      targetSectionId = selection.sectionId;
    } else if (tree.sections.length > 0) {
      targetSectionId = tree.sections[tree.sections.length - 1].id;
    }

    if (!targetSectionId) return;

    let newContainers: BlockContainer[] = [];
    const t = Date.now();
    switch (preset) {
      case "1-col":
        newContainers = [{ id: `cnt_${t}_1`, direction: "column", width: "100%", blocks: [] }];
        break;
      case "2-col-equal":
        newContainers = [
          { id: `cnt_${t}_1`, direction: "column", width: "50%", blocks: [] },
          { id: `cnt_${t}_2`, direction: "column", width: "50%", blocks: [] },
        ];
        break;
      case "2-col-wide-narrow":
        newContainers = [
          { id: `cnt_${t}_1`, direction: "column", width: "68%", blocks: [] },
          { id: `cnt_${t}_2`, direction: "column", width: "32%", blocks: [] },
        ];
        break;
      case "3-col":
        newContainers = [
          { id: `cnt_${t}_1`, direction: "column", width: "33%", blocks: [] },
          { id: `cnt_${t}_2`, direction: "column", width: "33%", blocks: [] },
          { id: `cnt_${t}_3`, direction: "column", width: "33%", blocks: [] },
        ];
        break;
    }

    commitTree({
      ...tree,
      sections: tree.sections.map((sec) =>
        sec.id === targetSectionId
          ? { ...sec, containers: [...sec.containers, ...newContainers] }
          : sec
      ),
    });
    setSelection({ type: "container", id: newContainers[0].id, sectionId: targetSectionId });
    toast("Added container layout", "success");
  }

  function handleAddElement(type: BlockType, specificContainerId?: string) {
    let targetContainerId = specificContainerId;
    if (!targetContainerId) {
      if (selection?.type === "container") {
        targetContainerId = selection.id;
      } else if (selection?.containerId) {
        targetContainerId = selection.containerId;
      } else {
        // Fallback to first container of first section
        targetContainerId = tree.sections[0]?.containers[0]?.id;
      }
    }

    if (!targetContainerId) {
      toast("Select or add a container first to insert this element.", "warning");
      return;
    }

    const newId = `blk_${Date.now()}`;
    let newBlock: TemplateBlock;

    switch (type) {
      case "variable_with_title":
        newBlock = {
          id: newId,
          type: "variable_with_title",
          title: "Vehicle No: ",
          variableId: "vehicle_no",
          align: "between",
        };
        break;
      case "variable":
        newBlock = {
          id: newId,
          type: "variable",
          variableId: "insurance_company",
        };
        break;
      case "text":
        newBlock = {
          id: newId,
          type: "text",
          text: "Motor Insurance Quotation",
          fontSize: 14,
          fontWeight: "800",
        };
        break;
      case "image":
        newBlock = {
          id: newId,
          type: "image",
          assetSlot: "risklocker_logo",
          width: 80,
          height: 30,
          objectFit: "contain",
        };
        break;
      case "specs_table":
        newBlock = {
          id: newId,
          type: "specs_table",
          rows: [
            { id: `r_${Date.now()}_1`, label: "Customer Name", variableId: "customer_name" },
            { id: `r_${Date.now()}_2`, label: "Vehicle No", variableId: "vehicle_no" },
            { id: `r_${Date.now()}_3`, label: "Car Model", variableId: "car_model" },
            { id: `r_${Date.now()}_4`, label: "Authorised Driver", variableId: "authorized_driver" },
            { id: `r_${Date.now()}_5`, label: "Policy Excess", variableId: "excess_amount" },
          ],
        };
        break;
      case "premium_block":
        newBlock = {
          id: newId,
          type: "premium_block",
          premiumLabel: "Insurance Premium",
          roadtaxLabel: "Roadtax and Runner Fee",
          totalLabel: "Total Payable",
        };
        break;
      case "benefits_grid":
        newBlock = {
          id: newId,
          type: "benefits_grid",
          kind: "current_benefits",
          titleEn: "Comprehensive Benefits",
          columns: 3,
        };
        break;
      default:
        newBlock = {
          id: newId,
          type: "text",
          text: "Text block",
        };
    }

    commitTree({
      ...tree,
      sections: tree.sections.map((sec) => ({
        ...sec,
        containers: sec.containers.map((cnt) =>
          cnt.id === targetContainerId ? { ...cnt, blocks: [...cnt.blocks, newBlock] } : cnt
        ),
      })),
    });
    setSelection({ type: "block", id: newId, containerId: targetContainerId });
    toast(`Added ${type.replace(/_/g, " ")}`, "success");
  }

  function handleAddSubContainer(parentContainerId: string) {
    const newSub: BlockContainer = {
      id: `cnt_sub_${Date.now()}`,
      direction: "column",
      width: "100%",
      blocks: [],
    };

    function addSubRecursive(list: BlockContainer[]): BlockContainer[] {
      return list.map((c) => {
        if (c.id === parentContainerId) {
          return {
            ...c,
            containers: [...(c.containers || []), newSub],
          };
        }
        if (c.containers?.length) {
          return {
            ...c,
            containers: addSubRecursive(c.containers),
          };
        }
        return c;
      });
    }

    commitTree({
      ...tree,
      sections: tree.sections.map((sec) => ({
        ...sec,
        containers: addSubRecursive(sec.containers),
      })),
    });
    setSelection({ type: "container", id: newSub.id, containerId: parentContainerId });
    toast("Added sub-container", "success");
  }

  function handleUpdateContainerWidth(containerId: string, deltaPercent: number) {
    function updateWidthRecursive(list: BlockContainer[]): BlockContainer[] {
      return list.map((cnt) => {
        if (cnt.id === containerId) {
          let cur = 100;
          if (typeof cnt.width === "string" && cnt.width.endsWith("%")) {
            cur = parseFloat(cnt.width) || 100;
          } else if (typeof cnt.width === "number") {
            cur = Math.round((cnt.width / 794) * 100);
          }
          const next = Math.max(10, Math.min(100, cur + deltaPercent));
          return { ...cnt, width: `${next}%` };
        }
        if (cnt.containers?.length) {
          return { ...cnt, containers: updateWidthRecursive(cnt.containers) };
        }
        return cnt;
      });
    }

    commitTree({
      ...tree,
      sections: tree.sections.map((sec) => ({
        ...sec,
        containers: updateWidthRecursive(sec.containers),
      })),
    });
  }

  function handleUpdateContainerAlign(
    containerId: string,
    align: "start" | "center" | "end" | "between"
  ) {
    function updateAlignRecursive(list: BlockContainer[]): BlockContainer[] {
      return list.map((cnt) => {
        if (cnt.id === containerId) {
          return { ...cnt, justifyContent: align };
        }
        if (cnt.containers?.length) {
          return { ...cnt, containers: updateAlignRecursive(cnt.containers) };
        }
        return cnt;
      });
    }

    commitTree({
      ...tree,
      sections: tree.sections.map((sec) => ({
        ...sec,
        containers: updateAlignRecursive(sec.containers),
      })),
    });
  }

  function handleUpdateContainer(containerId: string, updates: Partial<BlockContainer>) {
    function updateContainerRecursive(list: BlockContainer[]): BlockContainer[] {
      return list.map((cnt) => {
        if (cnt.id === containerId) {
          return { ...cnt, ...updates };
        }
        if (cnt.containers?.length) {
          return { ...cnt, containers: updateContainerRecursive(cnt.containers) };
        }
        return cnt;
      });
    }

    commitTree({
      ...tree,
      sections: tree.sections.map((sec) => ({
        ...sec,
        containers: updateContainerRecursive(sec.containers),
      })),
    });
  }

  function handleUpdateBlock(blockId: string, updates: Partial<TemplateBlock>) {
    function updateBlockRecursive(list: BlockContainer[]): BlockContainer[] {
      return list.map((cnt) => ({
        ...cnt,
        blocks: cnt.blocks.map((b) =>
          b.id === blockId ? ({ ...b, ...updates } as TemplateBlock) : b
        ),
        containers: cnt.containers?.length ? updateBlockRecursive(cnt.containers) : cnt.containers,
      }));
    }

    commitTree({
      ...tree,
      sections: tree.sections.map((sec) => ({
        ...sec,
        containers: updateBlockRecursive(sec.containers),
      })),
    });
  }

  function handleUpdateSection(sectionId: string, updates: Partial<BlockSection>) {
    commitTree({
      ...tree,
      sections: tree.sections.map((sec) =>
        sec.id === sectionId ? { ...sec, ...updates } : sec
      ),
    });
  }

  function handleDeleteBlock(blockId: string) {
    function deleteBlockRecursive(list: BlockContainer[]): BlockContainer[] {
      return list.map((cnt) => ({
        ...cnt,
        blocks: cnt.blocks.filter((b) => b.id !== blockId),
        containers: cnt.containers?.length ? deleteBlockRecursive(cnt.containers) : cnt.containers,
      }));
    }

    commitTree({
      ...tree,
      sections: tree.sections.map((sec) => ({
        ...sec,
        containers: deleteBlockRecursive(sec.containers),
      })),
    });
    if (selection?.id === blockId) setSelection(null);
  }

  function handleDeleteContainer(containerId: string) {
    function deleteContainerRecursive(list: BlockContainer[]): BlockContainer[] {
      return list
        .filter((c) => c.id !== containerId)
        .map((c) => ({
          ...c,
          containers: c.containers?.length ? deleteContainerRecursive(c.containers) : c.containers,
        }));
    }

    commitTree({
      ...tree,
      sections: tree.sections.map((sec) => ({
        ...sec,
        containers: deleteContainerRecursive(sec.containers),
      })),
    });
    if (selection?.id === containerId) setSelection(null);
  }

  function handleDeleteSection(sectionId: string) {
    commitTree({
      ...tree,
      sections: tree.sections.filter((s) => s.id !== sectionId),
    });
    if (selection?.id === sectionId) setSelection(null);
  }

  // --- PERSISTENCE ---

  async function handleSaveDraft() {
    if (!template) return;
    setSaving(true);
    try {
      const compiled = compileBlockTreeToCanvasElements(tree);
      const cleanConfig = {
        ...template.fixed_fields,
        block_tree: tree,
        canvas: {
          ...template.fixed_fields.canvas,
          elements: compiled,
        },
      };

      const res = await api<{ template: TemplateRecord }>(`/admin/templates/${template.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          base_revision: template.revision,
          name: template.name,
          insurance_type: template.insurance_type,
          fixed_fields: cleanConfig,
        }),
      });

      setTemplate(res.template);
      setSavedFingerprint(JSON.stringify(tree));
      toast("Template draft saved successfully.", "success");
    } catch (err: any) {
      toast(`Failed to save draft: ${err.message}`, "error");
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish() {
    if (!template) return;
    setPublishing(true);
    try {
      // First save latest draft
      const compiled = compileBlockTreeToCanvasElements(tree);
      const cleanConfig = {
        ...template.fixed_fields,
        block_tree: tree,
        canvas: {
          ...template.fixed_fields.canvas,
          elements: compiled,
        },
      };
      const saveRes = await api<{ template: TemplateRecord }>(`/admin/templates/${template.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          base_revision: template.revision,
          name: template.name,
          insurance_type: template.insurance_type,
          fixed_fields: cleanConfig,
        }),
      });

      // Publish
      const currentRev = saveRes.template?.revision ?? template.revision;
      const pubRes = await api<{ template_revision: { revision_number: number } }>(
        `/business/templates/${template.id}/publish`,
        { method: "POST", body: JSON.stringify({ base_revision: currentRev }) }
      );

      toast(
        `Published revision ${pubRes.template_revision.revision_number} successfully!`,
        "success"
      );
      await load();
    } catch (err: any) {
      toast(`Failed to publish: ${err.message}`, "error");
    } finally {
      setPublishing(false);
    }
  }

  const selectedContainerId =
    selection?.type === "container"
      ? selection.id
      : selection?.containerId || null;

  return (
    <main className="flex h-dvh flex-col overflow-hidden bg-slate-100 text-slate-900">
      {/* 1. TOP HEADER TOOLBAR (Clean, Uncluttered) */}
      <header className="z-30 shrink-0 flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-2.5 shadow-2xs">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            icon={<ArrowLeft size={15} weight="bold" />}
            onClick={() => router.push("/builder/templates")}
          >
            Templates
          </Button>

          <Input
            className="w-72 font-bold text-sm bg-slate-50 border-slate-200"
            value={template?.name || ""}
            onChange={(e) =>
              setTemplate((cur) => (cur ? { ...cur, name: e.target.value } : cur))
            }
          />

          {(template as any)?.is_default || (template?.fixed_fields as any)?.is_default ? (
            <Badge variant="warning" className="gap-1">
              <Star size={11} weight="fill" />
              Default Master
            </Badge>
          ) : null}
        </div>

        <div className="flex items-center gap-3">
          {/* Status Indicator */}
          <div className="flex items-center gap-1.5 text-xs">
            {dirty ? (
              <span className="flex items-center gap-1 text-amber-600 font-medium">
                <WarningCircle size={14} weight="bold" />
                Unsaved changes
              </span>
            ) : (
              <span className="flex items-center gap-1 text-emerald-600 font-medium">
                <CheckCircle size={14} weight="bold" />
                All changes saved
              </span>
            )}
          </div>
          <Button
            variant="secondary"
            size="sm"
            icon={<Sparkle size={14} weight="bold" className="text-amber-500" />}
            onClick={() => setIsBenefitEditorOpen(true)}
          >
            Benefit Templates
          </Button>

          <Button
            variant="secondary"
            size="sm"
            icon={<FloppyDisk size={14} weight="bold" />}
            loading={saving}
            onClick={handleSaveDraft}
          >
            Save Draft
          </Button>

          <Button
            variant="primary"
            size="sm"
            loading={publishing}
            onClick={handlePublish}
          >
            Publish Revision
          </Button>
        </div>
      </header>

      {/* 2. THE 4-COLUMN STUDIO WORKSPACE */}
      <div className="flex-1 min-h-0 flex overflow-hidden">
        {/* COLUMN 1: Elements & Containers Palette (240px) */}
        <PalettePanel
          onAddSection={handleAddSection}
          onAddContainer={handleAddContainer}
          onAddElement={handleAddElement}
          selectedContainerId={selectedContainerId}
        />

        {/* COLUMN 2: Visual Editable Working Canvas (Flex 1) */}
        <InteractiveCanvas
          tree={tree}
          selection={selection}
          onSelect={setSelection}
          onUpdateContainerWidth={handleUpdateContainerWidth}
          onUpdateContainerAlign={handleUpdateContainerAlign}
          onDeleteBlock={handleDeleteBlock}
          onDeleteContainer={handleDeleteContainer}
          onDeleteSection={handleDeleteSection}
          onAddElementToContainer={(cntId) => handleAddElement("variable_with_title", cntId)}
        />

        {/* COLUMN 3: Real A4 Live Quotation Preview with Customer Dropdown (480px) */}
        <LiveA4Preview
          tree={tree}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={setActiveSessionId}
          lastUpdated={lastUpdated}
        />

        {/* COLUMN 4: Hierarchy Tree & Properties Inspector with 1-Click Upload (320px) */}
        <InspectorPanel
          tree={tree}
          selection={selection}
          onSelect={setSelection}
          onUpdateContainer={handleUpdateContainer}
          onUpdateBlock={handleUpdateBlock}
          onUpdateSection={handleUpdateSection}
          onAddContainerToSection={(secId) => {
            setSelection({ type: "section", id: secId });
            handleAddContainer("1-col");
          }}
          onAddSubContainerToContainer={handleAddSubContainer}
          onAddElementToContainer={(cntId) => handleAddElement("variable_with_title", cntId)}
          onDeleteBlock={handleDeleteBlock}
          onDeleteContainer={handleDeleteContainer}
          onDeleteSection={handleDeleteSection}
        />
      </div>

      {/* Docked Benefit Editor Drawer */}
      {isBenefitEditorOpen && (
        <div className="fixed inset-y-0 right-0 w-[90vw] max-w-[1400px] bg-slate-50 shadow-2xl z-50 border-l border-slate-200 flex flex-col transform transition-transform duration-300">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-white">
            <h2 className="font-bold text-slate-800 flex items-center gap-2">
              <Sparkle className="text-amber-500" size={18} weight="fill" /> 
              Benefit Templates Designer
            </h2>
            <Button variant="ghost" size="sm" onClick={() => setIsBenefitEditorOpen(false)}>
              Close & Return to Quotation Builder
            </Button>
          </div>
          <div className="flex-1 overflow-hidden bg-slate-100 relative">
            <iframe 
              src="/builder/templates/benefit-templates?docked=true" 
              className="absolute inset-0 w-full h-full border-0"
              title="Benefit Templates Editor"
            />
          </div>
        </div>
      )}
    </main>
  );
}

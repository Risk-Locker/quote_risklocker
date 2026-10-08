/**
 * WordPress / Elementor-Style Container Block Engine
 * 
 * Replaces brittle absolute (x, y) drag coordinates with a structured DOM box model:
 * Section > Container (Row/Column) > Blocks.
 * 
 * Flow rule: When content expands (e.g. extras or specs rows), it naturally pushes
 * downstream containers down. Header never touches Body, Body never touches Footer.
 */

import type { CanvasElement } from "@/components/template-canvas/shared";

export type BlockType =
  | "image"
  | "text"
  | "variable"
  | "variable_with_title"
  | "specs_table"
  | "premium_block"
  | "benefits_grid";

export interface BaseBlock {
  id: string;
  type: BlockType;
  locked?: boolean;
}

export interface ImageBlock extends BaseBlock {
  type: "image";
  assetSlot?: string;
  url?: string;
  width: number;
  height: number;
  objectFit?: "contain" | "cover";
  align?: "left" | "center" | "right";
}

export interface TextBlock extends BaseBlock {
  type: "text";
  text: string;
  fontSize?: number;
  fontWeight?: string;
  color?: string;
  align?: "left" | "center" | "right";
}

export interface VariableBlock extends BaseBlock {
  type: "variable";
  variableId: string;
  prefix?: string;
  suffix?: string;
  fontSize?: number;
  fontWeight?: string;
  color?: string;
  align?: "left" | "center" | "right";
  transform?: "none" | "uppercase" | "capitalize";
}

export interface VariableWithTitleBlock extends BaseBlock {
  type: "variable_with_title";
  title: string;
  variableId: string;
  prefix?: string;
  suffix?: string;
  titleFontSize?: number;
  titleColor?: string;
  valueFontSize?: number;
  valueColor?: string;
  align?: "left" | "right" | "between";
}

export interface SpecRowItem {
  id: string;
  label: string;
  variableId: string;
  prefix?: string;
  suffix?: string;
}

export interface SpecsTableBlock extends BaseBlock {
  type: "specs_table";
  titleEn?: string;
  titleZh?: string;
  rows: SpecRowItem[];
  rowHeight?: number;
  borderColor?: string;
  borderRadius?: number;
}

export interface PremiumBreakdownBlock extends BaseBlock {
  type: "premium_block";
  premiumLabel?: string;
  roadtaxLabel?: string;
  totalLabel?: string;
  extrasLabel?: string;
}

export interface BenefitsGridBlock extends BaseBlock {
  type: "benefits_grid";
  kind: "current_benefits" | "available_addons";
  titleEn: string;
  titleZh?: string;
  columns?: number;
  autoDensity?: boolean;
}

export type TemplateBlock =
  | ImageBlock
  | TextBlock
  | VariableBlock
  | VariableWithTitleBlock
  | SpecsTableBlock
  | PremiumBreakdownBlock
  | BenefitsGridBlock;

export interface BlockContainer {
  id: string;
  direction: "row" | "column";
  flex?: number | string; // e.g. 1, "70%", "30%"
  width?: number | string;
  height?: number | string;
  alignItems?: "start" | "center" | "end" | "stretch";
  justifyContent?: "start" | "center" | "end" | "between" | "around";
  padding?: number;
  gap?: number;
  background?: string;
  borderWidth?: number;
  borderColor?: string;
  blocks: TemplateBlock[];
  containers?: BlockContainer[];
}

export interface BlockSection {
  id: string;
  name: string;
  sectionType: "header" | "body" | "benefits" | "footer";
  paddingY?: number;
  containers: BlockContainer[];
}

export interface BlockTree {
  version: 1;
  pageWidth: number;
  pageHeight: number;
  sections: BlockSection[];
}

/**
 * Creates the standard default Block Tree corresponding to Bilingual Agency Motor v3.
 */
export function createDefaultBlockTree(): BlockTree {
  return {
    version: 1,
    pageWidth: 794,
    pageHeight: 1123,
    sections: [
      {
        id: "sec_header",
        name: "Header Section",
        sectionType: "header",
        containers: [
          {
            id: "hdr_left_col",
            direction: "row",
            width: "50%",
            alignItems: "center",
            gap: 8,
            blocks: [
              {
                id: "blk_logo",
                type: "image",
                assetSlot: "risklocker_logo",
                width: 26,
                height: 26,
                align: "left",
              },
              {
                id: "blk_title_motor",
                type: "text",
                text: "Motor Insurance Quotation",
                fontSize: 16,
                fontWeight: "800",
                color: "#0F172A",
              },
            ],
          },
          {
            id: "hdr_right_col",
            direction: "column",
            width: "50%",
            alignItems: "end",
            justifyContent: "center",
            gap: 2,
            blocks: [
              {
                id: "blk_ref",
                type: "variable_with_title",
                title: "Quotation Ref: ",
                variableId: "quotation_reference",
                titleFontSize: 9.5,
                valueFontSize: 9.5,
                valueColor: "#ED1C24",
                align: "right",
              },
              {
                id: "blk_vehicle_no",
                type: "variable_with_title",
                title: "Vehicle No: ",
                variableId: "vehicle_no",
                titleFontSize: 9.5,
                valueFontSize: 9.5,
                valueColor: "#ED1C24",
                align: "right",
              },
              {
                id: "blk_insurer",
                type: "variable_with_title",
                title: "Insurer: ",
                variableId: "insurance_company",
                titleFontSize: 9.5,
                valueFontSize: 10,
                valueColor: "#ED1C24",
                align: "right",
              },
            ],
          },
        ],
      },
      {
        id: "sec_body",
        name: "Coverage & Payment Section",
        sectionType: "body",
        containers: [
          {
            id: "body_coverage_col",
            direction: "column",
            width: "72%",
            blocks: [
              {
                id: "blk_specs_table",
                type: "specs_table",
                titleEn: "Coverage & Vehicle Information",
                titleZh: "车辆及保单资料",
                rowHeight: 14,
                borderColor: "#E2E8F0",
                borderRadius: 4,
                rows: [
                  { id: "r_cust", label: "Customer / 客户姓名", variableId: "customer_name" },
                  { id: "r_type", label: "Coverage Type / 保单种类", variableId: "coverage_type" },
                  { id: "r_model", label: "Car Model / 车型", variableId: "car_model" },
                  { id: "r_cc", label: "Engine Capacity / 发动机排量", variableId: "engine_cc" },
                  { id: "r_ncd", label: "NCD", variableId: "ncd_percent", suffix: "%" },
                  { id: "r_period", label: "Cover of Period / 保单期限", variableId: "cover_period" },
                  { id: "r_val", label: "Valuation Type / 估价方式", variableId: "valuation_type" },
                  { id: "r_driver", label: "Authorised Driver / 授权驾驶人", variableId: "authorized_driver" },
                  { id: "r_excess", label: "Policy Excess / 自负额", variableId: "excess_amount", prefix: "RM " },
                  { id: "r_sum", label: "Vehicle Sum Insured / 车辆保额", variableId: "coverage_amount", prefix: "RM " },
                ],
              },
              {
                id: "blk_premium_block",
                type: "premium_block",
                premiumLabel: "Insurance Premium / 保费",
                roadtaxLabel: "Roadtax and Runner Fee / 路税及服务费",
                totalLabel: "TOTAL PAYABLE",
                extrasLabel: "Extras / 附加项目",
              },
            ],
          },
          {
            id: "body_payment_col",
            direction: "column",
            width: "28%",
            alignItems: "stretch",
            blocks: [
              {
                id: "blk_bank_img",
                type: "image",
                assetSlot: "bank_qr_layout_dark",
                width: 170,
                height: 284,
                objectFit: "contain",
                align: "right",
              },
            ],
          },
        ],
      },
      {
        id: "sec_benefits",
        name: "Insurer Benefits & Add-Ons",
        sectionType: "benefits",
        containers: [
          {
            id: "benefits_container",
            direction: "column",
            width: "100%",
            gap: 12,
            blocks: [
              {
                id: "blk_current_benefits",
                type: "benefits_grid",
                kind: "current_benefits",
                titleEn: "Our Specials",
                titleZh: "特别优惠",
                columns: 3,
                autoDensity: true,
              },
              {
                id: "blk_available_addons",
                type: "benefits_grid",
                kind: "available_addons",
                titleEn: "You May Add On (With Additional Charges)",
                titleZh: "可添加项目 (额外收费)",
                columns: 3,
                autoDensity: true,
              },
            ],
          },
        ],
      },
      {
        id: "sec_footer",
        name: "Footer Section",
        sectionType: "footer",
        containers: [
          {
            id: "footer_container",
            direction: "row",
            width: "100%",
            justifyContent: "center",
            blocks: [
              {
                id: "blk_footer_terms",
                type: "text",
                text: "*Terms & Conditions Apply | Quotation Validity: {valid_until}",
                fontSize: 8.5,
                fontWeight: "500",
                color: "#64748B",
                align: "center",
              },
            ],
          },
        ],
      },
    ],
  };
}

/**
 * Compiles a structured Block Tree into standard flat CanvasElements
 * for deterministic browser canvas rendering and PDF export.
 */
export function compileBlockTreeToCanvasElements(tree: BlockTree): CanvasElement[] {
  const elements: CanvasElement[] = [];

  // 1. Page Background
  elements.push({
    id: "page_bg",
    type: "rectangle",
    x: 0,
    y: 0,
    w: tree.pageWidth || 794,
    h: tree.pageHeight || 1123,
    z: 1,
    style: { background: "#FFFFFF", borderWidth: 0, borderColor: "transparent", borderRadius: 0 },
  });

  const headerSec = tree.sections.find((s) => s.sectionType === "header");
  const bodySec = tree.sections.find((s) => s.sectionType === "body");
  const benefitsSec = tree.sections.find((s) => s.sectionType === "benefits");
  const footerSec = tree.sections.find((s) => s.sectionType === "footer");

  // 2. Header
  if (headerSec) {
    // Left container (Logo + Title)
    const leftCol = headerSec.containers[0];
    const logoBlk = leftCol?.blocks.find((b) => b.type === "image") as ImageBlock | undefined;
    const titleBlk = leftCol?.blocks.find((b) => b.type === "text") as TextBlock | undefined;

    if (logoBlk) {
      elements.push({
        id: "risklocker_logo",
        type: "image",
        assetSlot: logoBlk.assetSlot || "risklocker_logo",
        x: 40,
        y: 22,
        w: logoBlk.width || 26,
        h: logoBlk.height || 26,
        z: 5,
        style: { borderWidth: 0 },
      });
    }

    if (titleBlk) {
      elements.push({
        id: "title_motor",
        type: "text",
        text: "Motor Insurance ",
        x: 72,
        y: 23,
        w: 140,
        h: 26,
        z: 5,
        locked: true,
        style: { fontSize: titleBlk.fontSize || 16, fontWeight: "800", color: "#0F172A", textAlign: "left" },
      });
      elements.push({
        id: "title_quotation",
        type: "text",
        text: "Quotation",
        x: 212,
        y: 23,
        w: 90,
        h: 26,
        z: 5,
        locked: true,
        style: { fontSize: titleBlk.fontSize || 16, fontWeight: "800", color: "#ED1C24", textAlign: "left" },
      });
    }

    // Right container (Metadata items)
    const rightCol = headerSec.containers[1];
    const rightVars = (rightCol?.blocks || []).filter((b) => b.type === "variable_with_title") as VariableWithTitleBlock[];

    let metaY = 16;
    for (const v of rightVars) {
      const eid = v.variableId === "quotation_reference" ? "ref_val" : v.variableId === "vehicle_no" ? "vehicle_no_val" : "header_insurer_name";
      elements.push({
        id: eid,
        type: "variable",
        variableId: v.variableId,
        prefix: v.title,
        x: 354,
        y: metaY,
        w: 400,
        h: 15,
        z: 5,
        style: {
          fontSize: v.valueFontSize || 9.5,
          fontWeight: v.variableId === "insurance_company" ? "800" : "700",
          color: v.valueColor || "#ED1C24",
          textAlign: "right",
          textTransform: v.variableId === "insurance_company" ? "uppercase" : "none",
        },
      });
      metaY += 15;
    }

    // Header dividing rule
    elements.push({
      id: "header_rule",
      type: "line",
      x: 40,
      y: 70,
      w: 714,
      h: 1,
      z: 2,
      style: { color: "#E2E8F0", borderWidth: 1 },
    });
  }

  // 3. Body Section (Coverage Table + Bank Image)
  let bodyY = 86;
  if (bodySec) {
    const covCol = bodySec.containers[0];
    const payCol = bodySec.containers[1];

    const tableBlk = covCol?.blocks.find((b) => b.type === "specs_table") as SpecsTableBlock | undefined;
    const premBlk = covCol?.blocks.find((b) => b.type === "premium_block") as PremiumBreakdownBlock | undefined;
    const bankImgBlk = payCol?.blocks.find((b) => b.type === "image") as ImageBlock | undefined;

    // Coverage Header Pill
    elements.push({
      id: "cov_header_bg",
      type: "rectangle",
      x: 40,
      y: bodyY,
      w: 530,
      h: 26,
      z: 2,
      locked: true,
      style: { background: "#1E293B", borderWidth: 0, borderColor: "transparent", borderRadius: 4 },
    });
    elements.push({
      id: "cov_header_txt",
      type: "text",
      text: `${tableBlk?.titleEn || "Coverage & Vehicle Information"} / ${tableBlk?.titleZh || "车辆及保单资料"}`,
      x: 52,
      y: bodyY + 5,
      w: 506,
      h: 16,
      z: 5,
      locked: true,
      style: { fontSize: 10, fontWeight: "700", color: "#FFFFFF", textAlign: "left" },
    });

    const rowsCount = tableBlk?.rows.length || 10;
    const tableTop = bodyY + 26;
    const tableBaseHeight = rowsCount * 14 + 132;

    // Single unified card border covering specs rows + premium block
    elements.push({
      id: "cov_table_bg",
      type: "rectangle",
      x: 40,
      y: tableTop,
      w: 530,
      h: tableBaseHeight,
      z: 2,
      locked: true,
      style: { background: "#FFFFFF", borderWidth: 1, borderColor: "#E2E8F0", borderRadius: 4 },
    });

    // Render Specs Rows
    let rowY = tableTop + 4;
    for (const r of tableBlk?.rows || []) {
      elements.push({
        id: `lbl_${r.id}`,
        type: "text",
        text: r.label,
        x: 52,
        y: rowY,
        w: 180,
        h: 14,
        z: 5,
        locked: true,
        style: { fontSize: 8.5, fontWeight: "600", color: "#334155", textAlign: "left" },
      });
      elements.push({
        id: `val_${r.id}`,
        type: "variable",
        variableId: r.variableId,
        prefix: r.prefix || "",
        suffix: r.suffix || "",
        x: 236,
        y: rowY,
        w: 320,
        h: 14,
        z: 5,
        locked: true,
        style: { fontSize: 9.5, fontWeight: "700", color: "#0F172A", textAlign: "left", textTransform: "none" },
      });
      rowY += 14;
    }

    // Dynamic Premium Block
    elements.push({
      id: "premium_info_block",
      type: "premium-info-block",
      x: 52,
      y: rowY,
      w: 506,
      h: 126,
      z: 5,
      locked: true,
      rowHeight: 14,
      labels: {
        premium: premBlk?.premiumLabel || "Insurance Premium / 保费",
        roadtax: premBlk?.roadtaxLabel || "Roadtax and Runner Fee / 路税及服务费",
        runner: "Runner Fee / 服务费",
        total: premBlk?.totalLabel || "TOTAL PAYABLE",
        extras: premBlk?.extrasLabel || "Extras / 附加项目",
      },
    } as any);

    // Right Column: Bank QR Image (Flush right w=170, h=tableBaseHeight + 26)
    if (bankImgBlk) {
      elements.push({
        id: "payment_account_details_img",
        type: "image",
        assetSlot: bankImgBlk.assetSlot || "bank_qr_layout_dark",
        x: 584,
        y: bodyY,
        w: bankImgBlk.width || 170,
        h: tableBaseHeight + 26,
        z: 5,
        style: { borderWidth: 0 },
      });
    }

    bodyY = tableTop + tableBaseHeight + 16;
  }

  // 4. Benefits Section
  if (benefitsSec) {
    const curGrid = benefitsSec.containers[0]?.blocks.find((b) => (b as BenefitsGridBlock).kind === "current_benefits") as BenefitsGridBlock | undefined;
    const addGrid = benefitsSec.containers[0]?.blocks.find((b) => (b as BenefitsGridBlock).kind === "available_addons") as BenefitsGridBlock | undefined;

    if (curGrid) {
      elements.push({
        id: "specials_header_bg",
        type: "rectangle",
        x: 40,
        y: bodyY,
        w: 714,
        h: 26,
        z: 2,
        locked: true,
        style: { background: "#1E293B", borderWidth: 0, borderColor: "transparent", borderRadius: 4 },
      });
      elements.push({
        id: "specials_header_txt",
        type: "text",
        text: `${curGrid.titleEn} / ${curGrid.titleZh || "特别优惠"}`,
        x: 52,
        y: bodyY + 5,
        w: 690,
        h: 16,
        z: 5,
        locked: true,
        style: { fontSize: 10.5, fontWeight: "700", color: "#FFFFFF", textAlign: "left" },
      });
      elements.push({
        id: "current_benefits_grid",
        type: "benefit-grid",
        gridKind: "current_benefits",
        x: 40,
        y: bodyY + 30,
        w: 714,
        h: 324,
        z: 4,
        columns: curGrid.columns || 3,
        locked: true,
      } as any);

      bodyY += 360;
    }

    if (addGrid) {
      elements.push({
        id: "addons_header_bg",
        type: "rectangle",
        x: 40,
        y: bodyY,
        w: 714,
        h: 26,
        z: 2,
        locked: true,
        style: { background: "#1E293B", borderWidth: 0, borderColor: "transparent", borderRadius: 4 },
      });
      elements.push({
        id: "addons_header_txt",
        type: "text",
        text: `${addGrid.titleEn} / ${addGrid.titleZh || "可添加项目 (额外收费)"}`,
        x: 52,
        y: bodyY + 5,
        w: 690,
        h: 16,
        z: 5,
        locked: true,
        style: { fontSize: 10.5, fontWeight: "700", color: "#FFFFFF", textAlign: "left" },
      });
      elements.push({
        id: "available_addons_grid",
        type: "benefit-grid",
        gridKind: "available_addons",
        x: 40,
        y: bodyY + 30,
        w: 714,
        h: 268,
        z: 4,
        columns: addGrid.columns || 3,
        autoFourCol: true,
        adaptiveColumns: true,
        locked: true,
      } as any);
    }
  }

  // 5. Footer Section
  if (footerSec) {
    const footerTxt = footerSec.containers[0]?.blocks.find((b) => b.type === "text") as TextBlock | undefined;
    elements.push({
      id: "footer_terms",
      type: "text",
      text: footerTxt?.text || "*Terms & Conditions Apply | Quotation Validity: {valid_until}",
      x: 40,
      y: 1072,
      w: 714,
      h: 16,
      z: 5,
      style: { fontSize: 8.5, fontWeight: "500", color: "#64748B", textAlign: "center" },
    });
  }

  return elements;
}

export const blockTreeToCanvasElements = compileBlockTreeToCanvasElements;

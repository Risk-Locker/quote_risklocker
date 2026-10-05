/**
 * Template Section Compiler
 *
 * Provides bidirectional compilation between high-level structured section definitions
 * (Section 1: Vehicle & Policy specs, Section 5: Footer & Payment) and canonical
 * CanvasElement[] nodes used by the template renderer, review workspace, and WeasyPrint PDF generator.
 */

import type { CanvasElement } from "@/components/template-canvas/shared";

export interface VehicleSpecFieldSlot {
  id: string;
  variableId?: string;
  labelEn: string;
  labelZh?: string;
  fixedValue?: string;
  prefix?: string;
  suffix?: string;
  fontSize?: number;
  fontWeight?: string;
  color?: string;
  visible: boolean;
  rowOrder: number;
}

export type GenericBlockType = "image" | "text" | "variable" | "divider";

export interface GenericBlockConfig {
  id: string;
  type: GenericBlockType;
  visible?: boolean;
  order?: number;

  // Image block properties
  assetSlot?: string;
  assetId?: string;
  imageUrl?: string;
  imageWidth?: number;
  imageHeight?: number;
  imageFit?: "contain" | "cover";

  // Text block properties
  text?: string;

  // Variable block properties
  variableId?: string;
  prefix?: string;
  suffix?: string;

  // Typography & Styling
  fontSize?: number;
  fontWeight?: string;
  color?: string;
  textAlign?: "left" | "center" | "right";
  lineHeight?: number;

  // Divider properties
  dividerColor?: string;
  dividerHeight?: number;
}

export interface ContainerBlockConfig {
  id: string;
  title?: string;
  layout?: "column" | "row" | "payment_grid";
  boxX?: number;
  boxY?: number;
  boxW?: number;
  boxH?: number;
  background?: string;
  borderWidth?: number;
  borderColor?: string;
  borderRadius?: number;
  padding?: number;
  gap?: number;
  blocks: GenericBlockConfig[];
}

export interface Section1Config {
  vehicleFields: VehicleSpecFieldSlot[];
  headerTitleEn?: string;
  headerTitleZh?: string;
  boxX?: number;
  boxY?: number;
  boxW?: number;
  rowHeight?: number;
  extrasDisplayMode?: "itemized" | "lump_sum";
}

export interface SectionHeaderConfig {
  layout?: "right_3_rows" | "split_logo_insurer";
  rowsOrder?: Array<"ref" | "vehicle" | "insurer">;
  insurerPosition?: "row1" | "row2" | "row3" | "top_left";
  refLabel?: string;
  vehicleLabel?: string;
  insurerLabel?: string;
  fontSize?: number;
  logoX?: number;
  logoY?: number;
  logoW?: number;
  logoH?: number;
}

export interface SectionFooterConfig {
  bankName?: string;
  accountNo?: string;
  accountHolder?: string;
  paymentNotice?: string;
  termsNotice?: string;
}

export interface StructuredSections {
  version: 1;
  header?: SectionHeaderConfig;
  section1: Section1Config;
  rightContainers?: ContainerBlockConfig[];
  footer: SectionFooterConfig;
}

export function defaultHeaderConfig(): SectionHeaderConfig {
  return {
    layout: "right_3_rows",
    rowsOrder: ["ref", "vehicle", "insurer"],
    insurerPosition: "row3",
    refLabel: "Quotation Ref: ",
    vehicleLabel: "Vehicle No: ",
    insurerLabel: "Insurer: ",
    fontSize: 10.0,
    logoX: 40,
    logoY: 8,
    logoW: 72,
    logoH: 74,
  };
}

export const CANONICAL_VARIABLE_LABELS: Record<string, [string, string]> = {
  customer_name: ["Customer", "客户姓名"],
  coverage_type: ["Coverage Type", "保单种类"],
  car_model: ["Car Model", "车型"],
  engine_cc: ["Engine Capacity", "发动机排量 :"],
  ncd_percent: ["NCD", ""],
  cover_period: ["Cover of Period", "保单期限"],
  valuation_type: ["Valuation Type", "估价方式"],
  coverage_amount: ["Vehicle Sum Insured", "车辆保额"],
};

export interface VariableDescriptor {
  variableId: string;
  labelEn: string;
  labelZh: string;
  category: "vehicle" | "policy" | "pricing" | "custom";
  defaultPrefix?: string;
  defaultSuffix?: string;
  description?: string;
}

export const AVAILABLE_VARIABLES: VariableDescriptor[] = [
  { variableId: "vehicle_no", labelEn: "Vehicle No. (Car Plate)", labelZh: "车牌号码", category: "vehicle" },
  { variableId: "car_model", labelEn: "Car Model", labelZh: "车辆型号", category: "vehicle" },
  { variableId: "engine_cc", labelEn: "Engine CC / Capacity", labelZh: "发动机排量", category: "vehicle" },
  { variableId: "vehicle_year", labelEn: "Year of Make", labelZh: "制造年份", category: "vehicle" },
  { variableId: "seating_capacity", labelEn: "Seating Capacity", labelZh: "座位数", category: "vehicle" },
  { variableId: "engine_no", labelEn: "Engine Number", labelZh: "发动机编号", category: "vehicle" },
  { variableId: "chassis_no", labelEn: "Chassis Number", labelZh: "底盘编号", category: "vehicle" },

  { variableId: "customer_name", labelEn: "Customer", labelZh: "客户姓名", category: "policy" },
  { variableId: "quotation_reference", labelEn: "Quotation Ref", labelZh: "报价单号", category: "policy" },
  { variableId: "insurance_company", labelEn: "Insurer Name", labelZh: "保险公司", category: "policy" },
  { variableId: "coverage_type", labelEn: "Coverage Type", labelZh: "保单种类", category: "policy" },
  { variableId: "cover_period", labelEn: "Cover of Period", labelZh: "保单期限", category: "policy" },
  { variableId: "valuation_type", labelEn: "Valuation Type", labelZh: "估价方式", category: "policy" },
  { variableId: "valid_until", labelEn: "Validity Date", labelZh: "报价有效期", category: "policy" },

  { variableId: "coverage_amount", labelEn: "Vehicle Sum Insured", labelZh: "车辆保额", category: "pricing", defaultPrefix: "RM " },
  { variableId: "ncd_percent", labelEn: "NCD", labelZh: "", category: "pricing", defaultSuffix: "%" },
  { variableId: "excess_amount", labelEn: "Policy Excess", labelZh: "自负额", category: "pricing", defaultPrefix: "RM " },
  { variableId: "compulsory_excess", labelEn: "Compulsory Excess", labelZh: "强制自负额", category: "pricing", defaultPrefix: "RM " },
  { variableId: "premium", labelEn: "Insurance Premium", labelZh: "基本保费", category: "pricing", defaultPrefix: "RM " },
  { variableId: "roadtax", labelEn: "Roadtax", labelZh: "路税", category: "pricing", defaultPrefix: "RM " },
  { variableId: "service_fee", labelEn: "Runner Fee", labelZh: "跑腿服务费", category: "pricing", defaultPrefix: "RM " },
  { variableId: "total_amount", labelEn: "Total Premium", labelZh: "总保费", category: "pricing", defaultPrefix: "RM " },
];

export const DEFAULT_VEHICLE_FIELDS: VehicleSpecFieldSlot[] = [
  { id: "customer", variableId: "customer_name", labelEn: "Customer", labelZh: "客户姓名", visible: true, rowOrder: 0 },
  { id: "coverage_type", variableId: "coverage_type", labelEn: "Coverage Type", labelZh: "保单种类", visible: true, rowOrder: 1 },
  { id: "car_model", variableId: "car_model", labelEn: "Car Model", labelZh: "车型", visible: true, rowOrder: 2 },
  { id: "engine_cc", variableId: "engine_cc", labelEn: "Engine Capacity", labelZh: "发动机排量 :", visible: true, rowOrder: 3 },
  { id: "ncd_percent", variableId: "ncd_percent", labelEn: "NCD", labelZh: "", suffix: "%", visible: true, rowOrder: 4 },
  { id: "cover_period", variableId: "cover_period", labelEn: "Cover of Period", labelZh: "保单期限", visible: true, rowOrder: 5 },
  { id: "valuation_type", variableId: "valuation_type", labelEn: "Valuation Type", labelZh: "估价方式", visible: true, rowOrder: 6 },
  { id: "coverage_amount", variableId: "coverage_amount", labelEn: "Vehicle Sum Insured", labelZh: "车辆保额", prefix: "RM ", visible: true, rowOrder: 7 },
];

export function defaultRightContainers(): ContainerBlockConfig[] {
  return [
    {
      id: "rc_container_payment",
      title: "Payment Method Card",
      layout: "payment_grid",
      boxX: 508,
      boxY: 134,
      boxW: 246,
      boxH: 68,
      background: "#FFFFFF",
      borderWidth: 1,
      borderColor: "#E2E8F0",
      borderRadius: 6,
      padding: 9,
      gap: 3,
      blocks: [
        {
          id: "rc_b_pay_title",
          type: "text",
          text: "Payment Methods :",
          fontSize: 9.5,
          fontWeight: "700",
          color: "#334155",
          textAlign: "left",
          order: 0,
        },
        {
          id: "rc_b_pay_details",
          type: "text",
          text: "Bank Details : 12300318500\nRiskLocker Sdn. Bhd.",
          fontSize: 8.5,
          fontWeight: "600",
          color: "#475569",
          textAlign: "left",
          order: 1,
        },
        {
          id: "rc_b_bank_logo",
          type: "image",
          assetSlot: "bank_logo",
          assetId: "2168eaee-3e56-4903-8c4f-841f01ff2407",
          imageWidth: 72,
          imageHeight: 28,
          imageFit: "contain",
          order: 2,
        },
      ],
    },
    {
      id: "rc_container_qr",
      title: "DuitNow QR Card",
      layout: "row",
      boxX: 508,
      boxY: 210,
      boxW: 246,
      boxH: 78,
      background: "#FFFFFF",
      borderWidth: 1,
      borderColor: "#E2E8F0",
      borderRadius: 6,
      padding: 8,
      gap: 8,
      blocks: [
        {
          id: "rc_b_qr_code",
          type: "image",
          assetSlot: "qr_code",
          assetId: "c2003185-0000-4000-8000-000000000001",
          imageWidth: 70,
          imageHeight: 70,
          imageFit: "contain",
          order: 0,
        },
        {
          id: "rc_b_qr_text",
          type: "text",
          text: "DuitNow QR\nScan to Pay / 扫码付款\nInstant Verification",
          fontSize: 8.5,
          fontWeight: "700",
          color: "#0F172A",
          textAlign: "left",
          order: 1,
        },
      ],
    },
    {
      id: "rc_container_drivers",
      title: "All Drivers & Excess Card",
      layout: "column",
      boxX: 508,
      boxY: 296,
      boxW: 246,
      boxH: 74,
      background: "#F8FAFC",
      borderWidth: 1,
      borderColor: "#E2E8F0",
      borderRadius: 6,
      padding: 9,
      gap: 4,
      blocks: [
        {
          id: "rc_b_driver_title",
          type: "text",
          text: "All Driver Included",
          fontSize: 9.5,
          fontWeight: "700",
          color: "#0F172A",
          textAlign: "left",
          order: 0,
        },
        {
          id: "rc_b_driver_sub",
          type: "text",
          text: "Authorised Drivers Covered",
          fontSize: 8,
          fontWeight: "500",
          color: "#64748B",
          textAlign: "left",
          order: 1,
        },
        {
          id: "rc_b_driver_divider",
          type: "divider",
          dividerColor: "#E2E8F0",
          dividerHeight: 1,
          order: 2,
        },
        {
          id: "rc_b_excess_val",
          type: "variable",
          variableId: "excess_amount",
          prefix: "Policy Excess / 自负额 : RM ",
          fontSize: 9.5,
          fontWeight: "700",
          color: "#0F172A",
          textAlign: "left",
          order: 3,
        },
      ],
    },
  ];
}

/**
 * Parses existing canvas elements into structured section metadata.
 * If savedSections are already present in template configuration, they are merged or preserved.
 */
export function extractSectionsFromCanvas(
  elements: CanvasElement[],
  savedSections?: StructuredSections | null
): StructuredSections {
  if (savedSections && savedSections.version === 1 && savedSections.section1?.vehicleFields?.length > 0) {
    const sanitizedFields: VehicleSpecFieldSlot[] = [];
    savedSections.section1.vehicleFields.forEach((f) => {
      const varId = f.variableId || "";
      const fid = f.id || "";
      const lblEn = f.labelEn || "";
      if (
        varId === "insurance_company" ||
        varId === "quotation_reference" ||
        varId === "vehicle_no" ||
        fid === "header_insurer_name" ||
        fid === "top_insurer_name" ||
        fid === "insurer_name"
      ) {
        return;
      }
      let finalEn = lblEn;
      let finalZh = f.labelZh || "";
      if (varId && CANONICAL_VARIABLE_LABELS[varId]) {
        const [cEn, cZh] = CANONICAL_VARIABLE_LABELS[varId];
        if (
          !finalZh ||
          finalEn.startsWith("val_") ||
          finalEn.startsWith("value_") ||
          finalEn.startsWith("field_") ||
          finalEn.startsWith("label_") ||
          finalEn.startsWith("header_insurer") ||
          finalEn === fid
        ) {
          finalEn = cEn;
          finalZh = cZh;
        }
      }
      sanitizedFields.push({
        ...f,
        labelEn: finalEn,
        labelZh: finalZh,
        rowOrder: sanitizedFields.length,
      });
    });

    return {
      version: 1,
      header: savedSections.header || defaultHeaderConfig(),
      section1: {
        ...savedSections.section1,
        vehicleFields: sanitizedFields.length > 0 ? sanitizedFields : [...DEFAULT_VEHICLE_FIELDS],
      },
      rightContainers: savedSections.rightContainers && savedSections.rightContainers.length > 0
        ? savedSections.rightContainers
        : defaultRightContainers(),
      footer: savedSections.footer || {},
    };
  }

  // Detect vehicle spec rows from canvas elements matching value_*, val_*, and label_*, lbl_*
  const valueElements = elements.filter(
    (e) => e.type === "variable" && (e.id.startsWith("value_") || e.id.startsWith("val_") || e.variableId)
  );

  const detectedFields: VehicleSpecFieldSlot[] = [];
  const seenIds = new Set<string>();

  // Sort candidate elements by their vertical Y position
  const sortedValues = [...valueElements].sort((a, b) => (a.y || 0) - (b.y || 0));

  for (let i = 0; i < sortedValues.length; i++) {
    const valElem = sortedValues[i];
    const eid = valElem.id;
    let rawKey = eid;
    if (eid.startsWith("value_")) rawKey = eid.replace(/^value_/, "");
    else if (eid.startsWith("val_")) rawKey = eid.replace(/^val_/, "");
    else rawKey = eid || valElem.variableId || `field_${i}`;

    if (seenIds.has(rawKey)) continue;

    // Filter out header elements, validity tags, and insurer labels that do not belong to the left spec table
    if (
      valElem.id === "quote_vehicle" ||
      valElem.id === "validity" ||
      valElem.id === "header_insurer_name" ||
      valElem.id === "top_insurer_name" ||
      valElem.id === "ref_val" ||
      valElem.id === "vehicle_no_val" ||
      valElem.id === "insurer_name" ||
      valElem.variableId === "insurance_company" ||
      valElem.variableId === "quotation_reference" ||
      valElem.variableId === "vehicle_no" ||
      (valElem.y || 0) < 130 ||
      (valElem.x || 0) > 400
    ) {
      continue;
    }

    seenIds.add(rawKey);

    // Find corresponding label element
    const labelElem = elements.find((e) => e.id === `label_${rawKey}` || e.id === `lbl_${rawKey}`);
    const rawLabel = labelElem?.text || rawKey;

    // Split bilingual label if separated by slash
    let labelEn = rawLabel;
    let labelZh = "";
    if (rawLabel.includes("/")) {
      const parts = rawLabel.split("/");
      labelEn = parts[0].trim();
      labelZh = parts.slice(1).join("/").trim();
    }

    // Sanitize with canonical labels if needed
    const varId = valElem.variableId || "";
    if (varId && CANONICAL_VARIABLE_LABELS[varId]) {
      const [cEn, cZh] = CANONICAL_VARIABLE_LABELS[varId];
      if (
        !labelZh ||
        labelEn.startsWith("val_") ||
        labelEn.startsWith("value_") ||
        labelEn.startsWith("field_") ||
        labelEn.startsWith("label_") ||
        labelEn.startsWith("header_insurer") ||
        labelEn === rawKey ||
        !rawLabel.includes("/")
      ) {
        labelEn = cEn;
        labelZh = cZh;
      }
    }

    detectedFields.push({
      id: rawKey,
      variableId: valElem.variableId || rawKey,
      labelEn: labelEn || rawKey,
      labelZh: labelZh,
      prefix: valElem.prefix,
      suffix: valElem.suffix,
      fontSize: valElem.style?.fontSize,
      fontWeight: valElem.style?.fontWeight ? String(valElem.style.fontWeight) : undefined,
      color: valElem.style?.color,
      visible: valElem.visible !== false,
      rowOrder: detectedFields.length,
    });
  }

  // Fallback to default fields if none could be extracted
  const finalFields = detectedFields.length > 0 ? detectedFields : [...DEFAULT_VEHICLE_FIELDS];

  // Extract footer details
  const paymentTextElem = elements.find((e) => e.id === "payment_text" || e.id === "text_3yr0mvi");
  const termsElem = elements.find((e) => e.id === "terms");

  let bankName = "Hong Leong Bank";
  let accountNo = "12300318500";
  let accountHolder = "Risklocker Sdn. Bhd.";

  if (paymentTextElem?.text) {
    const lines = paymentTextElem.text.split("\n");
    if (lines.length >= 3) {
      accountNo = lines[2].trim() || accountNo;
    }
  }

  return {
    version: 1,
    header: savedSections?.header || defaultHeaderConfig(),
    section1: {
      vehicleFields: finalFields,
      headerTitleEn: "Coverage & Vehicle Information",
      headerTitleZh: "保障与车辆信息",
    },
    rightContainers: defaultRightContainers(),
    footer: {
      bankName,
      accountNo,
      accountHolder,
      termsNotice: termsElem?.text || "*Terms and Condition Applied",
    },
  };
}

export interface SimulatedExtra {
  id: string;
  labelEn: string;
  labelZh?: string;
  price: string;
}

export const SAMPLE_SIMULATED_EXTRAS: SimulatedExtra[] = [
  { id: "sim_extra_1", labelEn: "Driver PA", labelZh: "司机个人意外险", price: "RM 300.00" },
  { id: "sim_extra_2", labelEn: "Windscreen Repair (RM 4,000)", labelZh: "挡风玻璃保障", price: "RM 600.00" },
  { id: "sim_extra_3", labelEn: "Special Perils (Flood) (RM 55,000)", labelZh: "天灾特别风险", price: "RM 110.00" },
  { id: "sim_extra_4", labelEn: "Legal Liability to Passengers", labelZh: "乘客法律责任险", price: "RM 25.00" },
  { id: "sim_extra_5", labelEn: "Key Care & Replacement (RM 1,500)", labelZh: "车钥匙重置保障", price: "RM 35.00" },
  { id: "sim_extra_6", labelEn: "All Authorized Drivers Protection", labelZh: "全司机驾驶保障", price: "RM 50.00" },
  { id: "sim_extra_7", labelEn: "Waiver of Betterment (10 Years)", labelZh: "豁免折旧费用", price: "RM 120.00" },
  { id: "sim_extra_8", labelEn: "24/7 Unlimited Towing & Roadside", labelZh: "无限距离拖车救援", price: "RM 80.00" },
];

export function getLumpSumExtrasPrice(count?: number): string {
  const numItems = count && count > 0 ? Math.min(count, SAMPLE_SIMULATED_EXTRAS.length) : 1;
  let total = 0;
  for (let i = 0; i < numItems; i++) {
    const val = parseFloat(SAMPLE_SIMULATED_EXTRAS[i].price.replace(/[^0-9.]/g, "")) || 0;
    total += val;
  }
  return `RM ${total.toFixed(2)}`;
}

export interface CompileOptions {
  simulatedExtrasCount?: number;
}

/**
 * Pure compiler: Takes high-level structured sections and outputs valid, canonical CanvasElement[]
 * ensuring 100% compatibility with the template renderer, review workspace, and WeasyPrint PDF generator.
 */
export function compileSectionsToCanvas(
  sections: StructuredSections,
  baseElements: CanvasElement[],
  options?: CompileOptions
): CanvasElement[] {
  const fields = (sections.section1.vehicleFields || [])
    .slice()
    .sort((a, b) => a.rowOrder - b.rowOrder);

  const visibleFields = fields.filter((f) => f.visible);

  const extrasMode = sections.section1.extrasDisplayMode ?? "itemized";
  const simulatedCount = Math.max(0, Math.min(options?.simulatedExtrasCount ?? 0, SAMPLE_SIMULATED_EXTRAS.length));
  const itemizedItemCount = Math.max(1, simulatedCount);
  const extraRowsCount = extrasMode === "lump_sum" ? 1 : (1 + itemizedItemCount);
  const totalRows = visibleFields.length + extraRowsCount;

  const firstLabel = baseElements.find((e) => (e.id.startsWith("label_") || e.id.startsWith("lbl_")) && !e.id.includes("sim_extra"));
  const firstColon = baseElements.find((e) => (e.id.startsWith("colon_") || e.id.startsWith("col_")) && !e.id.includes("sim_extra"));
  const firstValue = baseElements.find((e) => (e.id.startsWith("value_") || e.id.startsWith("val_")) && !e.id.includes("sim_extra"));

  const hasDenseLayout = firstLabel !== undefined && ((firstLabel.h ?? 24) <= 16 || (firstLabel.x ?? 16) >= 40);

  const labelX = firstLabel?.x ?? (hasDenseLayout ? 52 : 16);
  const colonX = firstColon?.x ?? 207;
  const valueX = firstValue?.x ?? (hasDenseLayout ? 216 : 231);
  const startY = firstLabel?.y ?? 164;
  const labelW = firstLabel?.w ?? (hasDenseLayout ? 160 : 190);
  const valueW = firstValue?.w ?? (hasDenseLayout ? 266 : 215);
  const elementH = firstLabel?.h ?? (hasDenseLayout ? 14 : 24);

  const rowH = sections.section1.rowHeight ?? (hasDenseLayout ? 14 : 28);

  // IDs of legacy or previous right-side elements to replace when rightContainers is compiled
  const rightContainerIds = new Set([
    "pay_card_bg",
    "pay_title",
    "bank_logo",
    "pay_bank_logo",
    "pay_details_lbl",
    "pay_acc_no",
    "pay_holder",
    "qr_card_bg",
    "qr_code_img",
    "qr_title",
    "qr_sub",
    "qr_hint",
    "qr_badge",
    "all_driver_bg",
    "all_driver_title",
    "all_driver_sub",
    "divider_driver_excess",
    "excess_label",
    "excess_val",
    "compulsory_excess_label",
    "compulsory_excess_val",
    "excess_note",
    "payment_box",
    "payment_text",
    "pay_bank_sub",
    "driver_box",
    "driver_icon",
    "driver_text",
    "rc_container_main",
    "rc_container_payment",
    "rc_container_qr",
    "rc_container_drivers",
    "grp_payment_card",
    "grp_qr_card",
    "grp_excess_card",
  ]);

  const hasCustomRightContainers = Boolean(
    sections.rightContainers && sections.rightContainers.length > 0
  );

  // Filter out previously compiled spec rows, right-box elements, and legacy ghost nodes
  const GHOST_IDS = new Set([
    "group_4pysxhb", "group_4pysxhb--rectangle", "text_3yr0mvi",
    "text_ltaa394", "text_ul2w5ka", "group_90j9e0t",
    "group_4b1q6op", "group_ovsuz2u", "group_ovsuz2u--rectangle",
  ]);

  const remainingElements = baseElements.filter((e) => {
    if (
      e.id.startsWith("label_") ||
      e.id.startsWith("colon_") ||
      e.id.startsWith("value_") ||
      e.id.startsWith("lbl_") ||
      e.id.startsWith("col_") ||
      e.id.startsWith("val_") ||
      e.id.includes("sim_extra") ||
      e.id === "label_sim_extras_header" ||
      e.id === "premium_info_block" ||
      GHOST_IDS.has(e.id) ||
      e.type === "special"
    ) {
      return false;
    }
    if (hasCustomRightContainers) {
      if (
        rightContainerIds.has(e.id) ||
        e.id.startsWith("rc_") ||
        e.id.startsWith("rc_b_") ||
        ((e.x || 0) >= 480 && (e.y || 0) >= 110 && (e.y || 0) <= 430 && e.id !== "quote_vehicle" && e.id !== "validity")
      ) {
        return false;
      }
    }
    return true;
  });

  // Generate compiled CanvasElement rows
  const compiledRows: CanvasElement[] = [];

  // Find insertion index for extras (immediately below premium)
  const premiumIdx = visibleFields.findIndex(
    (f) => f.variableId === "premium" || f.id === "premium" || f.id === "insurance_premium"
  );
  const insertExtrasAfterIdx = premiumIdx !== -1 ? premiumIdx : visibleFields.length - 1;

  let currentRenderRow = 0;

  visibleFields.forEach((field, index) => {
    const currentY = startY + currentRenderRow * rowH;
    const combinedLabel = field.labelZh ? `${field.labelEn} / ${field.labelZh}` : field.labelEn;
    const fontSize = field.fontSize ?? (hasDenseLayout ? 9.0 : 12);
    const fontWeight = (field.fontWeight ?? (hasDenseLayout ? "600" : "700")) as any;
    const color = field.color ?? (hasDenseLayout ? "#64748B" : "#111111");

    // 1. Label
    compiledRows.push({
      id: `label_${field.id}`,
      type: "text",
      x: labelX,
      y: currentY,
      w: labelW,
      h: elementH,
      z: 2,
      text: combinedLabel,
      style: {
        fontSize,
        fontWeight,
        color,
        textAlign: "left",
      },
    });

    // 2. Colon
    compiledRows.push({
      id: `colon_${field.id}`,
      type: "text",
      x: colonX,
      y: currentY,
      w: 12,
      h: elementH,
      z: 2,
      text: ":",
      style: {
        fontSize,
        fontWeight: "400",
        color,
        textAlign: "left",
      },
    });

    // 3. Value variable or fixed text
    const valFontSize = field.fontSize ?? (hasDenseLayout ? 9.5 : 12);
    const valFontWeight = (field.fontWeight ?? "700") as any;
    const valColor = field.color ?? (hasDenseLayout ? "#0F172A" : "#111111");
    compiledRows.push({
      id: `value_${field.id}`,
      type: field.variableId ? "variable" : "text",
      variableId: field.variableId,
      text: field.fixedValue,
      prefix: field.prefix,
      suffix: field.suffix,
      x: valueX,
      y: currentY,
      w: valueW,
      h: elementH,
      z: 2,
      style: {
        fontSize: valFontSize,
        fontWeight: valFontWeight,
        color: valColor,
        textAlign: "left",
      },
    });

    currentRenderRow++;

    // Inject extras immediately below premium
    if (index === insertExtrasAfterIdx) {
      if (extrasMode === "lump_sum") {
        const lumpY = startY + currentRenderRow * rowH;
        compiledRows.push({
          id: "label_extras_lump",
          type: "text",
          x: labelX,
          y: lumpY,
          w: labelW,
          h: elementH,
          z: 2,
          text: "Extras / 附加项目",
          style: {
            fontSize: 12,
            fontWeight: "700",
            color: "#111111",
            textAlign: "left",
          },
        });

        compiledRows.push({
          id: "colon_extras_lump",
          type: "text",
          x: colonX,
          y: lumpY,
          w: 12,
          h: elementH,
          z: 2,
          text: ":",
          style: {
            fontSize: 12,
            fontWeight: "400",
            color: "#111111",
            textAlign: "left",
          },
        });

        compiledRows.push({
          id: "value_extras_lump",
          type: "variable",
          variableId: "total_optional_cover_amount",
          text: getLumpSumExtrasPrice(simulatedCount),
          prefix: "RM ",
          x: valueX,
          y: lumpY,
          w: valueW,
          h: elementH,
          z: 2,
          style: {
            fontSize: 12,
            fontWeight: "700",
            color: "#111111",
            textAlign: "left",
          },
        });
        currentRenderRow++;
      } else {
        // Itemized Mode
        // Extras Section Header
        const headerY = startY + currentRenderRow * rowH;
        compiledRows.push({
          id: "label_sim_extras_header",
          type: "text",
          x: labelX,
          y: headerY,
          w: labelW + colonX + valueW,
          h: elementH,
          z: 2,
          text: "Extras / 附加项目 :",
          style: {
            fontSize: 10,
            fontWeight: "800",
            color: "#0F172A",
            textAlign: "left",
            letterSpacing: 0.5,
          },
        });
        currentRenderRow++;

        // Extras items (at least 1 item is shown so Extras is never missing)
        for (let i = 0; i < itemizedItemCount; i++) {
          const extra = SAMPLE_SIMULATED_EXTRAS[i];
          const extraY = startY + currentRenderRow * rowH;
          const extraLabel = extra.labelZh ? `${extra.labelEn} / ${extra.labelZh}` : extra.labelEn;

          compiledRows.push({
            id: `label_sim_extra_${i}`,
            type: "text",
            x: labelX,
            y: extraY,
            w: labelW,
            h: elementH,
            z: 2,
            text: extraLabel,
            style: {
              fontSize: 10.5,
              fontWeight: "600",
              color: "#334155",
              textAlign: "left",
            },
          });

          compiledRows.push({
            id: `colon_sim_extra_${i}`,
            type: "text",
            x: colonX,
            y: extraY,
            w: 12,
            h: elementH,
            z: 2,
            text: ":",
            style: {
              fontSize: 10.5,
              fontWeight: "400",
              color: "#334155",
              textAlign: "left",
            },
          });

          compiledRows.push({
            id: `value_sim_extra_${i}`,
            type: "text",
            text: extra.price,
            x: valueX,
            y: extraY,
            w: valueW,
            h: elementH,
            z: 2,
            style: {
              fontSize: 11,
              fontWeight: "700",
              color: "#0F172A",
              textAlign: "left",
            },
          });

          currentRenderRow++;
        }
      }
    }
  });

  // In production mode (when simulated extras are not requested), append canonical premium_info_block
  if (simulatedCount === 0 && extrasMode !== "lump_sum" && hasDenseLayout) {
    const premiumY = startY + visibleFields.length * rowH;
    compiledRows.push({
      id: "premium_info_block",
      type: "premium-info-block" as any,
      x: 52,
      y: premiumY,
      w: 430,
      h: 130,
      z: 4,
      rowHeight: rowH,
      labels: {
        extras: "EXTRAS / 附加项目",
        premium: "Insurance Premium / 保费",
        roadtax: "Roadtax / 路税",
        runner: "Runner Fee / 服务费",
        total: "TOTAL PAYABLE",
      },
      locked: true,
    } as any);
  }

  // Calculate dynamic vertical expansion based on row count
  const deltaY = hasDenseLayout
    ? Math.max(0, (visibleFields.length - 8) * rowH)
    : Math.max(0, (totalRows - 9) * rowH);

  // Compile Right Containers
  const compiledRightBlocks: CanvasElement[] = [];
  if (hasCustomRightContainers && sections.rightContainers) {
    const rightContainers = sections.rightContainers;
    const isMultiBox = rightContainers.length > 1;
    rightContainers.forEach((container, cIdx) => {
      const isLastOrBottom = !isMultiBox || cIdx === rightContainers.length - 1 || container.id === "rc_container_drivers" || (container.boxY ?? 0) >= 300;
      const boxX = container.boxX ?? 508;
      const boxY = container.boxY ?? 134;
      const boxW = container.boxW ?? 246;
      const baseH = container.boxH ?? (isMultiBox ? 80 : 272);
      const boxH = isLastOrBottom ? baseH + deltaY : baseH;
      const padding = container.padding ?? 10;
      const gap = container.gap ?? 6;

      // Container background rectangle / div
      compiledRightBlocks.push({
        id: container.id,
        type: "rectangle",
        x: boxX,
        y: boxY,
        w: boxW,
        h: boxH,
        z: 2,
        style: {
          background: container.background ?? "#FFFFFF",
          borderWidth: container.borderWidth ?? 1,
          borderColor: container.borderColor ?? "#E2E8F0",
          borderRadius: container.borderRadius ?? 6,
        },
      });

      const blocks = (container.blocks || [])
        .slice()
        .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
        .filter((b) => b.visible !== false);

      if (container.id === "rc_container_payment" || container.layout === "payment_grid") {
        let currentY = boxY + padding;
        const blockW = boxW - padding * 2;
        const blockX = boxX + padding;
        const payTitle = blocks.find((b) => String(b.id).includes("title")) || blocks[0];
        const payDetails = blocks.find((b) => String(b.id).includes("details"));
        const bankLogo = blocks.find((b) => b.type === "image" || String(b.id).includes("bank"));

        if (payTitle) {
          const fontSize = payTitle.fontSize ?? 9.5;
          compiledRightBlocks.push({
            id: payTitle.id,
            type: "text",
            x: blockX,
            y: currentY,
            w: blockW,
            h: 14,
            z: 3,
            text: payTitle.text || "Payment Methods :",
            style: {
              fontSize,
              fontWeight: (payTitle.fontWeight ?? "700") as any,
              color: payTitle.color ?? "#334155",
              textAlign: payTitle.textAlign ?? "left",
            },
          });
          currentY += 14 + gap;
        }

        const subY = currentY;
        const leftW = 150;
        const rightW = 72;
        const subH = 28;

        if (payDetails) {
          const fontSize = payDetails.fontSize ?? 8.5;
          compiledRightBlocks.push({
            id: payDetails.id,
            type: "text",
            x: blockX,
            y: subY,
            w: leftW,
            h: subH,
            z: 3,
            text: payDetails.text || "Bank Details : 12300318500\nRiskLocker Sdn. Bhd.",
            style: {
              fontSize,
              fontWeight: (payDetails.fontWeight ?? "600") as any,
              color: payDetails.color ?? "#475569",
              textAlign: payDetails.textAlign ?? "left",
            },
          });
        }

        if (bankLogo) {
          const logoX = boxX + boxW - padding - rightW;
          compiledRightBlocks.push({
            id: bankLogo.id,
            type: "image",
            x: logoX,
            y: subY,
            w: rightW,
            h: subH,
            z: 3,
            assetSlot: bankLogo.assetSlot ?? "bank_logo",
            assetId: bankLogo.assetId ?? "2168eaee-3e56-4903-8c4f-841f01ff2407",
          });
        }
      } else if (container.layout === "row") {
        let currentX = boxX + padding;
        const blockY = boxY + padding;
        const availableH = boxH - padding * 2;

        blocks.forEach((block) => {
          if (block.type === "image") {
            const blockW = block.imageWidth ?? 64;
            const blockH = Math.min(availableH, block.imageHeight ?? availableH);
            compiledRightBlocks.push({
              id: block.id,
              type: "image",
              x: currentX,
              y: blockY + (availableH - blockH) / 2,
              w: blockW,
              h: blockH,
              z: 3,
              assetSlot: block.assetSlot,
              assetId: block.assetId,
            });
            currentX += blockW + gap;
          } else if (block.type === "text") {
            const blockW = Math.max(60, boxX + boxW - padding - currentX);
            compiledRightBlocks.push({
              id: block.id,
              type: "text",
              x: currentX,
              y: blockY,
              w: blockW,
              h: availableH,
              z: 3,
              text: block.text || "",
              style: {
                fontSize: block.fontSize ?? 9,
                fontWeight: (block.fontWeight ?? "500") as any,
                color: block.color ?? "#0F172A",
                textAlign: block.textAlign ?? "left",
              },
            });
            currentX += blockW + gap;
          }
        });
      } else {
        // Default "column" stack
        let currentY = boxY + padding;
        const blockW = boxW - padding * 2;
        const blockX = boxX + padding;

        blocks.forEach((block) => {
          if (block.type === "image") {
            const h = block.imageHeight ?? 24;
            const w = Math.min(blockW, block.imageWidth ?? 100);
            compiledRightBlocks.push({
              id: block.id,
              type: "image",
              x: blockX,
              y: currentY,
              w,
              h,
              z: 3,
              assetSlot: block.assetSlot,
              assetId: block.assetId,
            });
            currentY += h + gap;
          } else if (block.type === "text") {
            const lines = (block.text || "").split("\n");
            const fontSize = block.fontSize ?? 9.5;
            const h = Math.max(14, Math.ceil(lines.length * fontSize * 1.35));
            compiledRightBlocks.push({
              id: block.id,
              type: "text",
              x: blockX,
              y: currentY,
              w: blockW,
              h,
              z: 3,
              text: block.text || "",
              style: {
                fontSize,
                fontWeight: (block.fontWeight ?? "500") as any,
                color: block.color ?? "#0F172A",
                textAlign: block.textAlign ?? "left",
              },
            });
            currentY += h + gap;
          } else if (block.type === "variable") {
            const fontSize = block.fontSize ?? 9.5;
            const h = Math.max(14, Math.ceil(fontSize * 1.4));
            compiledRightBlocks.push({
              id: block.id,
              type: "variable",
              variableId: block.variableId,
              prefix: block.prefix,
              suffix: block.suffix,
              x: blockX,
              y: currentY,
              w: blockW,
              h,
              z: 3,
              style: {
                fontSize,
                fontWeight: (block.fontWeight ?? "700") as any,
                color: block.color ?? "#0F172A",
                textAlign: block.textAlign ?? "left",
              },
            });
            currentY += h + gap;
          } else if (block.type === "divider") {
            const h = block.dividerHeight ?? 1;
            compiledRightBlocks.push({
              id: block.id,
              type: "line",
              x: blockX,
              y: currentY,
              w: blockW,
              h: 2,
              z: 3,
              style: {
                borderWidth: h,
                borderColor: block.dividerColor ?? "#E2E8F0",
              },
            });
            currentY += h + gap;
          }
        });
      }
    });
  }

  const BASELINE_Y_MAP: Record<string, number> = {
    specials_title: hasDenseLayout ? 380 : 404,
    current_benefits_grid: hasDenseLayout ? 404 : 428,
    extras_title: hasDenseLayout ? 609 : 633,
    purchased_extras_grid: hasDenseLayout ? 633 : 657,
    addons_title: hasDenseLayout ? 838 : 862,
    available_addons_grid: hasDenseLayout ? 862 : 886,
    terms: 1090,
  };

  // Update Section 1 bounding box if present, and push all lower elements down by deltaY
  const updatedElements = remainingElements.map((elem) => {
    let nextElem = { ...elem };
    if (nextElem.id === "cov_table_bg" || nextElem.id === "group_specs_box") {
      const baseH = hasDenseLayout ? 210 : Number((nextElem as any).baseline_h ?? nextElem.h ?? 246);
      (nextElem as any).baseline_h = baseH;
      nextElem.h = baseH + deltaY;
    }

    if (BASELINE_Y_MAP[nextElem.id] !== undefined) {
      nextElem.y = BASELINE_Y_MAP[nextElem.id] + deltaY;
    } else if ((nextElem.y || 0) >= (hasDenseLayout ? 380 : 400)) {
      const base = (nextElem as any).baseline_y ?? nextElem.y;
      (nextElem as any).baseline_y = base;
      nextElem.y = base + deltaY;
    }

    // Update section titles as requested
    if (nextElem.id === "specials_title") {
      nextElem.text = "QBE Free Added Coverage";
    }
    if (nextElem.id === "extras_title") {
      nextElem.text = "Included Optional Add-On";
    }
    if (nextElem.id === "addons_title") {
      nextElem.text = "Recommended Add-On Upgrades :";
    }

    // Top Header Realignment: Motor Insurance Quotation, Validity Until, Insurer Full Name
    if (nextElem.id === "title") {
      nextElem.x = 480;
      nextElem.y = 16;
      nextElem.w = 296;
      nextElem.h = 24;
      nextElem.style = { ...(nextElem.style || {}), textAlign: "right", fontSize: 16, fontWeight: "800", color: "#ed1c24" };
    }
    if (nextElem.id === "validity") {
      nextElem.x = 480;
      nextElem.y = 40;
      nextElem.w = 296;
      nextElem.h = 20;
      nextElem.style = { ...(nextElem.style || {}), textAlign: "right", fontSize: 11, fontWeight: "600", color: "#475569" };
    }
    if (nextElem.id === "quote_vehicle") {
      nextElem.x = 480;
      nextElem.y = 96;
      nextElem.w = 296;
      nextElem.h = 28;
      nextElem.style = { ...(nextElem.style || {}), textAlign: "right", fontSize: 16, fontWeight: "800" };
    }
    // Clean redundant center placeholder insurer_logo
    if (nextElem.id === "insurer_logo" && (nextElem.x || 0) > 180 && (nextElem.x || 0) < 450) {
      nextElem.visible = false;
    }
    const header = sections.header || defaultHeaderConfig();
    const rowsOrder = header.rowsOrder || ["ref", "vehicle", "insurer"];
    const headerFontSize = header.fontSize ?? 10.5;
    const isTopLeftInsurer = header.insurerPosition === "top_left";

    const rightRowSlots: Array<"ref" | "vehicle" | "insurer"> = isTopLeftInsurer
      ? rowsOrder.filter((r) => r !== "insurer")
      : rowsOrder;

    const rowSlotYMap: Record<string, number> = {};
    rightRowSlots.forEach((slot, idx) => {
      rowSlotYMap[slot] = 20 + idx * 18;
    });

    if (nextElem.id === "risklocker_logo") {
      nextElem.x = header.logoX ?? 40;
      nextElem.y = header.logoY ?? 12;
      nextElem.w = header.logoW ?? 88;
      nextElem.h = header.logoH ?? 70;
    }
    if (nextElem.id === "ref_label") {
      const slotY = rowSlotYMap["ref"] ?? 20;
      nextElem.visible = false;
      nextElem.x = 354;
      nextElem.y = slotY;
      nextElem.w = 400;
      nextElem.h = 16;
      if (header.refLabel) nextElem.text = header.refLabel;
      nextElem.style = { ...(nextElem.style || {}), textAlign: "right", fontSize: headerFontSize, fontWeight: "500", color: "#64748B" };
    }
    if (nextElem.id === "ref_val") {
      const slotY = rowSlotYMap["ref"] ?? 20;
      nextElem.x = 354;
      nextElem.y = slotY;
      nextElem.w = 400;
      nextElem.h = 16;
      nextElem.prefix = header.refLabel || "Quotation Ref: ";
      nextElem.style = { ...(nextElem.style || {}), textAlign: "right", fontSize: headerFontSize, fontWeight: "700", color: "#ED1C24" };
    }
    if (nextElem.id === "vehicle_no_label") {
      const slotY = rowSlotYMap["vehicle"] ?? 38;
      nextElem.visible = false;
      nextElem.x = 354;
      nextElem.y = slotY;
      nextElem.w = 400;
      nextElem.h = 16;
      if (header.vehicleLabel) nextElem.text = header.vehicleLabel;
      nextElem.style = { ...(nextElem.style || {}), textAlign: "right", fontSize: headerFontSize, fontWeight: "500", color: "#64748B" };
    }
    if (nextElem.id === "vehicle_no_val") {
      const slotY = rowSlotYMap["vehicle"] ?? 38;
      nextElem.x = 354;
      nextElem.y = slotY;
      nextElem.w = 400;
      nextElem.h = 16;
      nextElem.prefix = header.vehicleLabel || "Vehicle No: ";
      nextElem.style = { ...(nextElem.style || {}), textAlign: "right", fontSize: headerFontSize, fontWeight: "700", color: "#ED1C24" };
    }
    if (nextElem.id === "header_insurer_label") {
      if (isTopLeftInsurer) {
        nextElem.visible = true;
        nextElem.x = 40;
        nextElem.y = (header.logoY ?? 12) + (header.logoH ?? 70) + 6;
        nextElem.w = 60;
        nextElem.h = 16;
        if (header.insurerLabel) nextElem.text = header.insurerLabel;
        nextElem.style = { ...(nextElem.style || {}), textAlign: "left", fontSize: headerFontSize, fontWeight: "600", color: "#64748B" };
      } else {
        const slotY = rowSlotYMap["insurer"] ?? 56;
        nextElem.visible = false;
        nextElem.x = 354;
        nextElem.y = slotY;
        nextElem.w = 400;
        nextElem.h = 16;
        if (header.insurerLabel) nextElem.text = header.insurerLabel;
        nextElem.style = { ...(nextElem.style || {}), textAlign: "right", fontSize: headerFontSize, fontWeight: "500", color: "#64748B" };
      }
    }
    if (nextElem.id === "header_insurer_name") {
      if (isTopLeftInsurer) {
        nextElem.x = 105;
        nextElem.y = (header.logoY ?? 12) + (header.logoH ?? 70) + 6;
        nextElem.w = 280;
        nextElem.h = 16;
        nextElem.prefix = "";
        nextElem.style = { ...(nextElem.style || {}), textAlign: "left", fontSize: headerFontSize, fontWeight: "800", color: "#ED1C24", textTransform: "uppercase" };
      } else {
        const slotY = rowSlotYMap["insurer"] ?? 56;
        nextElem.x = 354;
        nextElem.y = slotY;
        nextElem.w = 400;
        nextElem.h = 16;
        nextElem.prefix = header.insurerLabel || "Insurer: ";
        nextElem.style = { ...(nextElem.style || {}), textAlign: "right", fontSize: headerFontSize, fontWeight: "800", color: "#ED1C24", textTransform: "uppercase" };
      }
    }

    // Update footer terms if edited
    if (nextElem.id === "terms" && sections.footer.termsNotice) {
      nextElem.text = sections.footer.termsNotice;
    }

    return nextElem;
  });

  // Ensure official Insurer Name sits right below Vehicle No on top right if not present
  const hasTopInsurer = updatedElements.some(
    (e) => e.id === "top_insurer_name" || e.id === "header_insurer_name" || (e.variableId === "insurance_company" && (e.y || 0) < 130 && e.visible !== false)
  );
  const topInsurerElem: CanvasElement[] = [];
  if (!hasTopInsurer) {
    const header = sections.header || defaultHeaderConfig();
    const rowsOrder = header.rowsOrder || ["ref", "vehicle", "insurer"];
    const headerFontSize = header.fontSize ?? 10.5;
    const isTopLeftInsurer = header.insurerPosition === "top_left";
    const rightRowSlots = isTopLeftInsurer ? rowsOrder.filter((r) => r !== "insurer") : rowsOrder;
    const rowSlotYMap: Record<string, number> = {};
    rightRowSlots.forEach((slot, idx) => {
      rowSlotYMap[slot] = 20 + idx * 18;
    });

    const slotY = isTopLeftInsurer ? ((header.logoY ?? 18) + (header.logoH ?? 58) + 6) : (rowSlotYMap["insurer"] ?? 56);
    const posX = isTopLeftInsurer ? 105 : 555;
    const posW = isTopLeftInsurer ? 280 : 200;

    topInsurerElem.push({
      id: "top_insurer_name",
      type: "variable",
      variableId: "insurance_company",
      text: "AmGeneral Insurance Berhad",
      x: posX,
      y: slotY,
      w: posW,
      h: 16,
      z: 3,
      style: {
        fontSize: headerFontSize,
        fontWeight: "800",
        color: "#ED1C24",
        textAlign: "left",
        textTransform: "uppercase",
      },
    });
  }

  // Append compiled rows and right blocks
  return [...updatedElements, ...topInsurerElem, ...compiledRows, ...compiledRightBlocks];
}

/**
 * Returns pre-built template preset configurations for full English, full Mandarin, or mixed Bilingual.
 */
export function getPresetSections(preset: "bilingual" | "english" | "mandarin"): StructuredSections {
  if (preset === "english") {
    return {
      version: 1,
      section1: {
        vehicleFields: [
          { id: "coverage_type", variableId: "coverage_type", labelEn: "Coverage Type", visible: true, rowOrder: 0 },
          { id: "cover_period", variableId: "cover_period", labelEn: "Cover Period", visible: true, rowOrder: 1 },
          { id: "car_model", variableId: "car_model", labelEn: "Car Model", visible: true, rowOrder: 2 },
          { id: "engine_cc", variableId: "engine_cc", labelEn: "Engine Capacity", visible: true, rowOrder: 3 },
          { id: "ncd_percent", variableId: "ncd_percent", labelEn: "NCD", suffix: "%", visible: true, rowOrder: 4 },
          { id: "coverage_amount", variableId: "coverage_amount", labelEn: "Sum Insured", prefix: "RM ", visible: true, rowOrder: 5 },
          { id: "premium", variableId: "premium", labelEn: "Basic Premium", prefix: "RM ", visible: true, rowOrder: 6 },
          { id: "roadtax", variableId: "roadtax", labelEn: "Roadtax", prefix: "RM ", visible: true, rowOrder: 7 },
          { id: "service_fee", variableId: "service_fee", labelEn: "Runner Fee", prefix: "RM ", visible: true, rowOrder: 8 },
          { id: "total_amount", variableId: "total_amount", labelEn: "Total Premium", prefix: "RM ", visible: true, rowOrder: 9 },
        ],
        headerTitleEn: "Coverage & Vehicle Details",
      },
      rightContainers: defaultRightContainers(),
      footer: {
        bankName: "Hong Leong Bank",
        accountNo: "12300318500",
        accountHolder: "RiskLocker Sdn. Bhd.",
        termsNotice: "*Terms and Conditions Apply",
      },
    };
  }

  if (preset === "mandarin") {
    return {
      version: 1,
      section1: {
        vehicleFields: [
          { id: "coverage_type", variableId: "coverage_type", labelEn: "保单种类", visible: true, rowOrder: 0 },
          { id: "cover_period", variableId: "cover_period", labelEn: "保单期限", visible: true, rowOrder: 1 },
          { id: "car_model", variableId: "car_model", labelEn: "车型", visible: true, rowOrder: 2 },
          { id: "engine_cc", variableId: "engine_cc", labelEn: "发动机排量", visible: true, rowOrder: 3 },
          { id: "ncd_percent", variableId: "ncd_percent", labelEn: "无索偿折扣", suffix: "%", visible: true, rowOrder: 4 },
          { id: "coverage_amount", variableId: "coverage_amount", labelEn: "车辆保额", prefix: "RM ", visible: true, rowOrder: 5 },
          { id: "premium", variableId: "premium", labelEn: "基本保费", prefix: "RM ", visible: true, rowOrder: 6 },
          { id: "roadtax", variableId: "roadtax", labelEn: "路税", prefix: "RM ", visible: true, rowOrder: 7 },
          { id: "service_fee", variableId: "service_fee", labelEn: "跑腿服务费", prefix: "RM ", visible: true, rowOrder: 8 },
          { id: "total_amount", variableId: "total_amount", labelEn: "总保费", prefix: "RM ", visible: true, rowOrder: 9 },
        ],
        headerTitleEn: "车辆及保单资料",
        headerTitleZh: "车辆及保单资料",
      },
      rightContainers: defaultRightContainers(),
      footer: {
        bankName: "Hong Leong Bank",
        accountNo: "12300318500",
        accountHolder: "RiskLocker Sdn. Bhd.",
        termsNotice: "*适用条款及细则",
      },
    };
  }

  // Default: Bilingual
  return {
    version: 1,
    section1: {
      vehicleFields: [...DEFAULT_VEHICLE_FIELDS],
      headerTitleEn: "Coverage & Vehicle Information",
      headerTitleZh: "车辆及保单资料",
    },
    rightContainers: defaultRightContainers(),
    footer: {
      bankName: "Hong Leong Bank",
      accountNo: "12300318500",
      accountHolder: "RiskLocker Sdn. Bhd.",
      termsNotice: "*Terms & Conditions Apply",
    },
  };
}

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
  visible: boolean;
  rowOrder: number;
}

export interface Section1Config {
  vehicleFields: VehicleSpecFieldSlot[];
  headerTitleEn?: string;
  headerTitleZh?: string;
  boxX?: number;
  boxY?: number;
  boxW?: number;
  rowHeight?: number;
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
  section1: Section1Config;
  footer: SectionFooterConfig;
}

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

  { variableId: "customer_name", labelEn: "Insured Name", labelZh: "被保人姓名", category: "policy" },
  { variableId: "quotation_reference", labelEn: "Quotation Ref", labelZh: "报价单号", category: "policy" },
  { variableId: "insurance_company", labelEn: "Insurer Name", labelZh: "保险公司", category: "policy" },
  { variableId: "coverage_type", labelEn: "Coverage Type", labelZh: "保险类型", category: "policy" },
  { variableId: "cover_period", labelEn: "Cover Period", labelZh: "保险期限", category: "policy" },
  { variableId: "valuation_type", labelEn: "Valuation Type", labelZh: "估值方式", category: "policy" },
  { variableId: "valid_until", labelEn: "Validity Date", labelZh: "报价有效期", category: "policy" },

  { variableId: "coverage_amount", labelEn: "Sum Insured / Coverage", labelZh: "保险金额", category: "pricing", defaultPrefix: "RM " },
  { variableId: "ncd_percent", labelEn: "NCD", labelZh: "无索偿折扣", category: "pricing", defaultSuffix: "%" },
  { variableId: "excess_amount", labelEn: "Policy Excess", labelZh: "自负额", category: "pricing", defaultPrefix: "RM " },
  { variableId: "premium", labelEn: "Insurance Premium", labelZh: "基本保费", category: "pricing", defaultPrefix: "RM " },
  { variableId: "roadtax", labelEn: "Roadtax", labelZh: "路税", category: "pricing", defaultPrefix: "RM " },
  { variableId: "service_fee", labelEn: "Runner Fee", labelZh: "跑腿服务费", category: "pricing", defaultPrefix: "RM " },
  { variableId: "total_amount", labelEn: "Total Premium", labelZh: "总保费", category: "pricing", defaultPrefix: "RM " },
];

export const DEFAULT_VEHICLE_FIELDS: VehicleSpecFieldSlot[] = [
  { id: "coverage_type", variableId: "coverage_type", labelEn: "Coverage Type", labelZh: "保险类型", visible: true, rowOrder: 0 },
  { id: "cover_period", variableId: "cover_period", labelEn: "Cover of Period", labelZh: "保险期限", visible: true, rowOrder: 1 },
  { id: "car_model", variableId: "car_model", labelEn: "Car Model", labelZh: "车辆型号", visible: true, rowOrder: 2 },
  { id: "ncd_percent", variableId: "ncd_percent", labelEn: "NCD", labelZh: "无索偿折扣", suffix: "%", visible: true, rowOrder: 3 },
  { id: "coverage_amount", variableId: "coverage_amount", labelEn: "Coverage", labelZh: "保额", prefix: "RM ", visible: true, rowOrder: 4 },
  { id: "premium", variableId: "premium", labelEn: "Insurance Premium", labelZh: "基本保费", prefix: "RM ", visible: true, rowOrder: 5 },
  { id: "roadtax", variableId: "roadtax", labelEn: "Roadtax", labelZh: "路税", prefix: "RM ", visible: true, rowOrder: 6 },
  { id: "service_fee", variableId: "service_fee", labelEn: "Runner Fee", labelZh: "服务费", prefix: "RM ", visible: true, rowOrder: 7 },
  { id: "total_amount", variableId: "total_amount", labelEn: "Total Premium", labelZh: "总保费", prefix: "RM ", visible: true, rowOrder: 8 },
];

/**
 * Parses existing canvas elements into structured section metadata.
 * If savedSections are already present in template configuration, they are merged or preserved.
 */
export function extractSectionsFromCanvas(
  elements: CanvasElement[],
  savedSections?: StructuredSections | null
): StructuredSections {
  if (savedSections && savedSections.version === 1 && savedSections.section1?.vehicleFields?.length > 0) {
    return {
      version: 1,
      section1: {
        ...savedSections.section1,
        vehicleFields: savedSections.section1.vehicleFields.map((f, i) => ({
          ...f,
          rowOrder: f.rowOrder ?? i,
        })),
      },
      footer: savedSections.footer || {},
    };
  }

  // Detect vehicle spec rows from canvas elements matching value_* and label_*
  const valueElements = elements.filter(
    (e) => e.type === "variable" && (e.id.startsWith("value_") || e.variableId)
  );

  const detectedFields: VehicleSpecFieldSlot[] = [];
  const seenIds = new Set<string>();

  // Sort candidate elements by their vertical Y position
  const sortedValues = [...valueElements].sort((a, b) => (a.y || 0) - (b.y || 0));

  for (let i = 0; i < sortedValues.length; i++) {
    const valElem = sortedValues[i];
    const rawKey = valElem.id.replace(/^value_/, "") || valElem.variableId || `field_${i}`;
    if (seenIds.has(rawKey)) continue;

    // Filter out header vehicle elements or validity tags that do not belong to the left spec table
    if (valElem.id === "quote_vehicle" || valElem.id === "validity" || (valElem.x || 0) > 400) {
      continue;
    }

    seenIds.add(rawKey);

    // Find corresponding label element
    const labelElem = elements.find((e) => e.id === `label_${rawKey}`);
    const rawLabel = labelElem?.text || rawKey;

    // Split bilingual label if separated by slash
    let labelEn = rawLabel;
    let labelZh = "";
    if (rawLabel.includes("/")) {
      const parts = rawLabel.split("/");
      labelEn = parts[0].trim();
      labelZh = parts.slice(1).join("/").trim();
    }

    // Match known defaults
    const knownVar = AVAILABLE_VARIABLES.find((v) => v.variableId === valElem.variableId);

    detectedFields.push({
      id: rawKey,
      variableId: valElem.variableId || rawKey,
      labelEn: labelEn || knownVar?.labelEn || rawKey,
      labelZh: labelZh || knownVar?.labelZh || "",
      prefix: valElem.prefix,
      suffix: valElem.suffix,
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
    section1: {
      vehicleFields: finalFields,
      headerTitleEn: "Coverage & Vehicle Information",
      headerTitleZh: "保障与车辆信息",
    },
    footer: {
      bankName,
      accountNo,
      accountHolder,
      termsNotice: termsElem?.text || "*Terms and Condition Applied",
    },
  };
}

/**
 * Pure compiler: Takes high-level structured sections and outputs valid, canonical CanvasElement[]
 * ensuring 100% compatibility with the template renderer, review workspace, and WeasyPrint PDF generator.
 */
export function compileSectionsToCanvas(
  sections: StructuredSections,
  baseElements: CanvasElement[]
): CanvasElement[] {
  const fields = (sections.section1.vehicleFields || [])
    .slice()
    .sort((a, b) => a.rowOrder - b.rowOrder);

  const visibleFields = fields.filter((f) => f.visible);

  // Detect base geometry from existing template elements or use standard defaults
  const firstLabel = baseElements.find((e) => e.id.startsWith("label_"));
  const firstColon = baseElements.find((e) => e.id.startsWith("colon_"));
  const firstValue = baseElements.find((e) => e.id.startsWith("value_"));

  const labelX = firstLabel?.x ?? 16;
  const colonX = firstColon?.x ?? 207;
  const valueX = firstValue?.x ?? 231;
  const startY = firstLabel?.y ?? 164;
  const rowH = sections.section1.rowHeight ?? 28;

  const labelW = firstLabel?.w ?? 190;
  const valueW = firstValue?.w ?? 215;
  const elementH = firstLabel?.h ?? 24;

  // Filter out previously compiled spec rows
  const remainingElements = baseElements.filter(
    (e) => !e.id.startsWith("label_") && !e.id.startsWith("colon_") && !e.id.startsWith("value_")
  );

  // Generate compiled CanvasElement rows
  const compiledRows: CanvasElement[] = [];

  visibleFields.forEach((field, index) => {
    const currentY = startY + index * rowH;
    const combinedLabel = field.labelZh ? `${field.labelEn} / ${field.labelZh}` : field.labelEn;

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
        fontSize: 12,
        fontWeight: "700",
        color: "#111111",
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
        fontSize: 12,
        fontWeight: "400",
        color: "#111111",
        textAlign: "left",
      },
    });

    // 3. Value variable or fixed text
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
        fontSize: 12,
        fontWeight: "700",
        color: "#111111",
        textAlign: "left",
      },
    });
  });

  // Calculate required container box height to avoid border clipping
  const totalFieldsHeight = (visibleFields.length + 1) * rowH;
  const minBoxH = Math.max(280, totalFieldsHeight + 20);

  // Update Section 1 bounding box if present
  const updatedElements = remainingElements.map((elem) => {
    // If this is the background rectangle for vehicle specs (e.g. cov_table_bg or group_specs_box)
    if (elem.id === "cov_table_bg" || elem.id === "group_specs_box") {
      return {
        ...elem,
        h: Math.max(Number(elem.h || 0), minBoxH),
      };
    }

    // Update footer terms if edited
    if (elem.id === "terms" && sections.footer.termsNotice) {
      return {
        ...elem,
        text: sections.footer.termsNotice,
      };
    }

    return elem;
  });

  // Append compiled rows
  return [...updatedElements, ...compiledRows];
}

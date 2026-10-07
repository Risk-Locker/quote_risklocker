import type {
  BlockTree,
  BlockSection,
  BlockContainer,
  TemplateBlock,
  BlockType,
  ImageBlock,
  TextBlock,
  VariableBlock,
  VariableWithTitleBlock,
  SpecsTableBlock,
  PremiumBreakdownBlock,
  BenefitsGridBlock,
  SpecRowItem,
} from "@/lib/template-block-engine";

export type {
  BlockTree,
  BlockSection,
  BlockContainer,
  TemplateBlock,
  BlockType,
  ImageBlock,
  TextBlock,
  VariableBlock,
  VariableWithTitleBlock,
  SpecsTableBlock,
  PremiumBreakdownBlock,
  BenefitsGridBlock,
  SpecRowItem,
};

export interface SelectionTarget {
  type: "section" | "container" | "block";
  id: string;
  sectionId?: string;
  containerId?: string;
}

export interface CustomerSessionPreview {
  id: string;
  quotation_reference: string;
  customer_name: string;
  vehicle_no: string;
  car_model: string;
  insurance_company: string;
  coverage_type: string;
  cover_period: string;
  engine_cc: string;
  ncd_percent: string;
  valuation_type: string;
  authorized_driver: string;
  excess_amount: string;
  coverage_amount: string;
  premium: string;
  roadtax: string;
  runner_fee: string;
  total_amount: string;
  valid_until: string;
  benefits?: Array<{
    id: string;
    label: string;
    value?: string;
    description?: string;
    cost_status?: "standard" | "extra";
    cost_value?: string;
    is_extra?: boolean;
    asset_url?: string;
  }>;
}

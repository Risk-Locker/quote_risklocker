import { type CanvasElement } from "@/components/template-canvas/shared";
import { TourStep } from "@/components/guided-tour";

export type Source = { id: string; title: string; issuer: string; verification_status: string };

export type TemplateRecord = {
  id: string;
  name: string;
  is_default?: boolean;
  status: string;
  fixed_fields: {
    canvas?: { width?: number; height?: number; elements?: CanvasElement[] };
    page_profile?: { name?: string; width?: number; height?: number; unit?: string };
    assets?: Record<string, string>;
  };
};

export const ROLE_FALLBACK: Record<string, string> = {
  base: "included",
  optional: "addon_option",
  package_component: "bundle_component",
  upgrade: "upgrade",
};

export type MatrixOffering = {
  offering_id: string;
  offering_key: string;
  concept_key: string;
  label: string;
  description: string;
  is_custom_description?: boolean;
  description_override?: string | null;
  display_value: string;
  price: number;
  price_text: string;
};

export type MatrixBundleItem = {
  offering_key: string;
  label: string;
  override_value: string;
};

export type MatrixBundlePlan = {
  plan_id: string;
  plan_key: string;
  name: string;
  items: MatrixBundleItem[];
};

export type MatrixBundle = {
  package_id: string;
  package_key: string;
  name: string;
  package_kind: string;
  plans: MatrixBundlePlan[];
};

export type MatrixScenario = {
  catalog_id: string;
  product_id: string | null;
  product_name: string;
  product_key: string;
  scenario_name: string;
  segment_name: string;
  segment_key: string;
  vehicle_category_name: string;
  vehicle_category_key: string;
  coverage_type_name: string;
  coverage_type_key: string;
  system_type: string;
  revision_number: number;
  state: string;
  defaults: MatrixOffering[];
  addons: MatrixOffering[];
  bundles: MatrixBundle[];
};

export type CompanyMatrixData = {
  company: {
    id: string;
    name: string;
    slug: string;
    category: string;
  };
  summary: {
    total_products: number;
    total_scenarios: number;
    total_defaults: number;
    total_addons: number;
    total_bundles: number;
  };
  scenarios: MatrixScenario[];
};

export const BENEFITS_TOUR_STEPS: TourStep[] = [
  {
    target: "header",
    title: "Page purpose",
    body: "This is the Benefits & Add-ons cockpit. It assigns the global benefit library to one insurer's product, builds package tiers (package-system insurers), and configures add-on bundles. Nothing here is hardcoded — everything is saved to the database.",
  },
  {
    target: ".rl-tour-companies",
    title: "1. Insurance companies",
    body: "Select which insurer you want to configure. You can add new companies or edit existing ones at any time.",
  },
  {
    target: ".rl-tour-scenarios",
    title: "2. Scenarios",
    body: "Select the specific segment, vehicle category, and coverage type you want to configure for this company.",
  },
  {
    target: ".rl-tour-catalogs",
    title: "3. Products & Catalogs",
    body: "Each scenario has its own catalog of benefits. You can create different products for the same vehicle/coverage scenario.",
  },
  {
    target: ".rl-tour-tiers",
    title: "4. Package tiers",
    body: "For insurers with tiered packages (e.g. Lite, Plus, Comprehensive), manage tiers and assign specific benefits to each.",
  },
  {
    target: ".rl-tour-offerings",
    title: "5. Benefit offerings",
    body: "Assign benefits from the global library to this catalog. Set whether each benefit is included by default, optional, or part of a package.",
  },
  {
    target: ".rl-tour-publish",
    title: "6. Publication",
    body: "When you're happy with your changes, publish the catalog revision so it becomes active for quotation generation.",
  },
];

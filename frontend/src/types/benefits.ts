/**
 * Canonical benefit and catalog domain type definitions for Risklocker v7.
 */

export type AssetSummary = {
  id: string;
  label: string;
  asset_kind: string;
  status: string;
  url: string;
};

export type CompanySummary = {
  id: string;
  name: string;
  slug?: string | null;
  revision: number;
  status: string;
  logo?: AssetSummary | null;
};

export type ProductSummary = {
  id: string;
  company_id: string;
  product_key: string;
  name: string;
  channel?: string | null;
  revision: number;
  status: string;
};

export type TierSummary = {
  id: string;
  product_id: string;
  tier_key: string;
  name: string;
  sort_order: number;
  revision: number;
  status: string;
};

export type CatalogRevisionSummary = {
  id: string;
  revision_number: number;
  state: string;
  content_hash: string;
  published_at?: string | null;
};

export type PackageSummary = {
  id: string;
  package_key: string;
  name: string;
  package_kind: string;
  sort_order: number;
  revision?: number;
  status?: string;
};

export type CatalogSummary = {
  id: string;
  company_id: string;
  product_id?: string | null;
  tier_id?: string | null;
  package_id?: string | null;
  package?: PackageSummary | null;
  segment_id?: string | null;
  vehicle_category_id?: string | null;
  vehicle_subcategory_id?: string | null;
  coverage_type_id?: string | null;
  name: string;
  revision: number;
  status: string;
  revisions: CatalogRevisionSummary[];
};

export type HierarchyItem = {
  id: string;
  key: string;
  name: string;
  sort_order: number;
  status: string;
};

export type ConceptSummary = {
  id: string;
  concept_key: string;
  label: string;
  category?: "default" | "addon";
  variants?: string[];
  sort_order?: number;
  value_schema: { type?: string; category?: string; variants?: string[] };
  display_template: string;
  required_variables: string[];
  default_asset?: AssetSummary | null;
  status: string;
};

export type OfferingSummary = {
  id: string;
  catalog_revision_id: string;
  offering_key: string;
  concept_id: string;
  offering_kind: string;
  applies_to_type?: string | null;
  applies_to_id?: string | null;
  role?: string | null;
  label_override?: string | null;
  display_value?: string | null;
  source_document_id?: string | null;
  source_citation: Record<string, unknown>;
  source_aliases: string[];
  presentation_facet_ids: string[];
  sort_order: number;
  status: string;
  concept?: ConceptSummary | null;
};

export type PackageEntity = {
  id: string;
  catalog_revision_id: string;
  package_key: string;
  name: string;
  package_kind: string;
  sort_order: number;
  revision: number;
  status: string;
};

export type CompanyWorkspaceData = {
  company: CompanySummary;
  products: ProductSummary[];
  tiers: TierSummary[];
  catalogs: CatalogSummary[];
};

export type CatalogWorkspaceData = {
  catalog: CatalogSummary;
  active_revision: { id: string; revision_number: number; state: string; content_hash: string };
  offerings: OfferingSummary[];
  packages: PackageEntity[];
  relations: Array<Record<string, unknown>>;
  plans: Array<Record<string, unknown>>;
  plan_items: Array<Record<string, unknown>>;
};

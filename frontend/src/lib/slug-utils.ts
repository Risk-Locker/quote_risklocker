/**
 * Slug utilities for human-readable URL parameters.
 *
 * Converts entity names (e.g. "AmAssurance", "Berjaya Sompo")
 * into URL-safe slugs ("amassurance", "berjaya-sompo") and resolves
 * parameters that could be either UUIDs or slugs back to entity IDs.
 */

/** Lowercases and hyphenates a name: "AmAssurance" → "amassurance", "Berjaya Sompo" → "berjaya-sompo" */
export function toSlug(name: string): string {
  if (!name) return "";
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Returns true if the string looks like a UUID v4 */
export function isUuid(value: string): boolean {
  return UUID_RE.test(value);
}

/**
 * Given a list of items and a URL param that could be a UUID or a slug, resolve to the matching item.
 * Supports items with `name`, `package.name`, `product_key`, etc.
 */
export function resolveBySlugOrId<T extends { id: string; name?: string | null; [key: string]: any }>(
  items: T[],
  param: string
): T | undefined {
  if (!param) return undefined;

  // Try exact ID match first (fast path for UUIDs)
  if (isUuid(param)) {
    const byId = items.find((i) => i.id === param);
    if (byId) return byId;
  }

  // Try slug match
  const slugParam = toSlug(param);
  return items.find((i) => {
    if (i.slug && toSlug(i.slug) === slugParam) return true;
    if (i.name && toSlug(i.name) === slugParam) return true;
    if (i.package?.name && toSlug(i.package.name) === slugParam) return true;
    if (i.product_key && toSlug(i.product_key) === slugParam) return true;
    if (i.key && toSlug(i.key) === slugParam) return true;
    return false;
  });
}

/** Given an entity, get its slug for clean URLs */
export function getEntitySlug(
  item?: { id: string; name?: string | null; slug?: string | null; package?: { name: string } | null; [key: string]: any } | null
): string {
  if (!item) return "";
  if (item.slug) return toSlug(item.slug);
  if (item.name) return toSlug(item.name);
  if (item.package?.name) return toSlug(item.package.name);
  return item.id;
}

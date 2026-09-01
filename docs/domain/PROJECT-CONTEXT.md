# Project Context

## Purpose

Risklocker Quotation Converter is a private internal application for converting insurer motor quotations into reviewed, versioned Risklocker PDFs. It is designed for repeated staff use, not public self-service.

## Staff Journey

1. Upload exactly one insurer quotation PDF for a new quotation.
2. Check extracted Risklocker values against the source document.
3. Confirm the company/product catalog, package, current benefits, add-on offers, and quotation-specific values.
4. Preview the quotation with an insurer-independent fixed-page template.
5. Save reviewed values and generate one deterministic, immutable PDF version.

## Scope

- Motor quotation extraction and review.
- Database-driven legal-entity, brand, product, tier, and alias resolution with no fixed company list.
- Revisioned benefit catalogs, packages, typed values, upgrades, presentation facets, and verified source provenance.
- Versioned output PDFs, private source-PDF access, history, and trash management.
- Administrative configuration for users, companies, templates, benefits, dictionaries, storage, and system checks.

## Current Boundaries

- The application processes PDFs; backend validation is the authority for accepted upload formats.
- Customer examples and process references are external private development material, not runtime dependencies.
- No paid API is required for the supported workflow.
- Core workflow support begins at 768px; the full template canvas begins at 1024px and does not promise phone or touch-drag support.
- The v7 core is completed and approved before the login/OTP redesign or Resend integration begins.

For mandatory constraints and staff-facing behavior, read [BUSINESS-RULES.md](BUSINESS-RULES.md).

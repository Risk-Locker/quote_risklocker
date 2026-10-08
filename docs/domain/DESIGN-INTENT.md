# Product Design Intent & User Experience Philosophy

This document defines the core product philosophy, target user personas, and design principles governing the **Risk-Locker** quotation platform. Every architectural and UI decision must align with these human-centered requirements.

---

## 1. Product Vision & Mission

Risk-Locker transforms the chaotic, error-prone process of Malaysian motor insurance quotation generation into a fast, accurate, and professional workflow. 

Quotations are binding financial documents. They directly influence customer purchasing decisions and underwrite legal vehicle liabilities. Therefore:
- **Accuracy takes precedence over convenience.**
- **Visual trust and brand polish take precedence over generic utilitarian forms.**
- **Staff velocity must never be compromised by technical friction.**

---

## 2. Core User Personas

### Persona A: Internal Agency Staff (The Operator)
- **Profile**: Insurance agency clerks, administrators, and runners who process motor renewal quotes daily.
- **Tech Savviness**: Low to Moderate. They are experts in insurance underwriting rules, NCD schedules, and JPJ road tax, but have zero patience for software jargon, developer errors, or cryptic modals.
- **Workflow Tempo**: High speed. Often juggling 10–30 renewal files simultaneously under tight customer WhatsApp deadlines.
- **Non-Negotiable UX Needs**:
  1. **Instant Clarity & Ergonomics**: Actions like "Copy PNG", "Download PDF", "Send via WhatsApp", or "Rescan" must be accessible in 1 click.
  2. **Safe Manual Overrides**: Staff know their underwriting exceptions. When staff manually adjust a premium, towing limit, or road tax amount, the system must **never** silently overwrite their edits upon re-save.
  3. **Zero Cryptic Errors**: Error notifications must clearly state the business cause (e.g., *"Vehicle plate missing from PDF"* instead of *"KeyError: vehicle_registration_number"*).
  4. **Visual Previews**: Live instant preview of the A4 quotation canvas before export eliminates test printing.

### Persona B: External Vehicle Owner (The Decision Maker)
- **Profile**: Private car owners, motorcycle riders, and commercial fleet managers receiving quotations on their smartphones via WhatsApp or email.
- **Reading Environment**: Small mobile displays or printed A4 documents.
- **Core Questions**: 
  1. *What is my total payable amount?*
  2. *What coverage/add-ons do I actually get for this price?*
  3. *Why should I choose Insurer A over Insurer B?*
- **Non-Negotiable Visual Standards**:
  1. **Bilingual Clarity (English / Mandarin)**: Standardized vehicle spec labels and benefit descriptions in both languages for Malaysian market demographics.
  2. **Clean Financial Breakdown**: Transparent row-by-row structure: Basic Premium $\rightarrow$ NCD Discount $\rightarrow$ Net Premium $\rightarrow$ Extras $\rightarrow$ SST $\rightarrow$ Stamp Duty $\rightarrow$ Road Tax $\rightarrow$ Total Payable.
  3. **Visual Benefit Cards**: Purchased add-ons (Windscreen, Special Perils, Towing) must render as distinct, elegant cards with icons—not dense walls of small text.
  4. **High-Trust Aesthetics**: Modern typography, consistent padding, crisp vector brand logos, and zero visual glitches.

---

## 3. Product Invariants & Design Contracts

| Invariant | Principle | Implementation Rule |
| :--- | :--- | :--- |
| **No Silent Guessing** | Never hallucinate uncertain numbers | If PDF extraction confidence is low, leave the field highlighted for staff review rather than silently guessing a wrong value. |
| **Staff Overrides Win** | Human expertise supersedes AI defaults | Any value manually edited by staff is permanently tracked and protected from automated overwrite cascades. |
| **Deterministic Arithmetic** | Math must always balance | Total Payable must strictly equal `(Net Premium + Extras) * (1 + SST) + Stamp Duty + Road Tax + Runner Fee`. Rounding differences must never leak into client documents. |
| **Hermetic Stability** | Software must never regress | Every service feature, calculation rule, and template variant must be guarded by automated hermetic unit tests. |

---

## 4. UI Placement & Layout Guidelines

When adding controls or features:
1. **Primary Actions**: High-frequency actions belong in the page header action bar or sticky bottom action toolbar.
2. **Contextual Settings**: Granular configuration belongs inside tabbed side drawers or inspector panels, keeping the main workspace uncluttered.
3. **Empty States**: Never show blank screens or broken layout shells; always display an informative empty state with a direct call to action.
4. **Desktop First, Mobile Optimized**: The quotation builder and comparison matrix are high-density desktop tools (optimized for 1080p+ screens); exported client assets (PNG snapshots and PDFs) are mobile-first.

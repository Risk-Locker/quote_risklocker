# Risklocker Active Working Memory (STATE.md)

Current high-signal snapshot of active development. Rotate old entries to docs/history/MEMORY-YYYY-MM.md when this file exceeds ~80 lines.

## Active System State (Current Snapshot)
- **Architecture**: Next.js 15.5 frontend (:3000) + FastAPI backend (:8100) + Supabase/PostgreSQL pooler + Private Storage.
Done: Investigated run 33628313695 failure; identified 	est_template_publication.py failing because list_published_templates in 	emplate_revision_service.py:312 skipped checking 
evision.state == 'published' in memory (relying only on SQL where clause which FakeDb does not evaluate in unit tests); added explicit 
evision.state != 'published' check; verified 541/541 pytest tests passing and Next.js build clean.
Pending: Commit and push fix to resolve GitHub Actions CI.

### 2026-09-02 Ã‚Â· Antigravity Ã‚Â· UI Layout Fixes & Benefit Visibility Toggles
Asked: Fix duplicated addons, equalize masonry grid heights, add per-benefit visibility toggles, and clarify revision system.
Done: Filtered current_benefits in shared.tsx, migrated layout to equal-height CSS Grid, added Eye toggle buttons to IncludedCard and AddonCard in 
eview-phase.tsx for real-time live preview updates.
Pending: none.

### 2026-09-02 Ã‚Â· Antigravity (Gemini 3.1 Pro) Ã‚Â· Egress Optimization & Workspace Fixes
Asked: Fix 50MB egress and latency issue for templates API, fix road tax calculation bug, Extra Benefits RM prefix, and production PDF viewer iframe.
Done: Optimized list_published_templates in 	emplate_revision_service.py to use SQL where and defer(config); replaced parseInt with parseFloat in 
eview-phase.tsx, removed forced RM prefix for non-monetary limits, and bypassed CSP for application/pdf in http_security.py.
Pending: none.

### 2026-09-02 Â· Antigravity (Gemini 3.1 Pro) Â· Analysis of Implementation Plan
Asked: Analyze the previous AI's implementation plan, check if issues are true, if fixes would break things, and find hidden issues.
Done: Audited codebase against the claims. Validated that many schema "issues" (string money values, untyped JSON, ephemeral files) are actually intentional and required behavior. Confirmed critical RAG learning loop gap, code duplication, and discovered a new bug (db_packs is missing from extraction context). Wrote analysis report and concrete fix plan in "implementation_plan.md".
Pending: User review of the plan and decision on Admin Approval for the AI learning loop.

### 2026-09-02 · Antigravity (Gemini 3.1 Pro) · Analysis of Egress Issues & Final Plan
Asked: Do a final analysis prioritizing DB egress and memory spikes (e.g. 700 revisions crash) and enforce a strict 200MB/day limit. Start plan with branch v13 creation.
Done: Investigated template_revision_service and admin_service. Found exact cause of the egress spike: querying all TemplateRevisions without deferring the massive JSON config column. Updated the implementation_plan.md with 5 tasks, inserting a new Task 1 to fix all missing config defers. Ensured all new tasks (packs, corrections) use strict DB-level aggregations and limits to minimize payload size.
Pending: User approval to execute the final egress-safe plan.

### 2026-09-02 · Antigravity (Gemini 3.1 Pro) · System-Wide Egress Sweep
Asked: Search for other discrepancies/issues in the system beyond just template revisions.
Done: Swept the codebase for missing defers on heavy JSON columns (GeneratedPdfVersion, OutputTemplateConfig, QuotationDraft). Expanded the implementation plan to patch trash_service, legacy_asset_inventory, and workspace_service to prevent egress spikes across the entire backend.
Pending: User approval to execute the final plan.

2026-09-02 * Antigravity * User requested to finalize extraction logic and verify egress * Fixed missing defers across admin/template/trash services, added total_premium fallback, integrated db_packs and correction memory into Gemini extraction, skipped Task 4 to prevent bugs * Verified build successfully
2026-09-03 · Antigravity · Audited project architecture and fixed upload failure; resolved distributed worker collision via node_host payload/claim filtering in job_service.py:42-133, fixed TypeError/NameError in sandbox.py:31-95 and orchestrator.py:18-75, added pipeline observability logs in extraction_worker.py:168-410, added step failure prefix in upload/page.tsx:160 · 542 pytest passing + Next.js build clean · Pending: none.
2026-09-03 · Antigravity · Fixed Document.new_page typing diagnostic in test_extraction_regression.py:177 with Any annotation; encoded rule to inspect and resolve IDE problem diagnostics after every change into AGENTS.md:38,53 and INSTRUCTIONS.md:25 · All checks green · Pending: none.
2026-09-03 · Antigravity · Fixed NameError 'defer' in workspace_service.py:13,131 by importing defer and removing bad defer on fixed_fields; smoke-tested build_workspace_snapshot on session d59d824a · 26 workspace tests passing · Pending: none.
2026-09-03 · Antigravity · Cleared 8 redundant str() linter warnings in workspace_service.py:1343-1799 · All 24 workspace tests green · Pending: none.
2026-09-03 · Antigravity · Implemented 'valuation_type' field across extraction, master template, and sessions UI; added QBE/addon detection in candidate_finder.py:33,818 and draft_mapper.py:130, inserted Row 7 in master_template_service.py:175, added dropdown in review-phase.tsx:75,2285 · 544 pytest passing + Next.js build clean · Pending: none.
2026-09-03 · Antigravity · Fixed benefit extraction false positives and fragmentation; added table row stitching, section termination, and noise filtering in benefit_lines.py:42-425, catalog_review_service.py:552-570, workspace_service.py:610-660 · 546 pytest passing + Next.js build clean · Pending: none.
2026-09-03 · Antigravity · Restored text copy/selection on review page by removing global select-none and restored Card design token styling on rl-tour-fields in review-phase.tsx:1897,2006,2197,2565 · tsc green · Pending: none.
2026-09-03 · Antigravity · Added 'Copy Info' button copying all extracted policy fields, custom fields, and detected extra benefits; unified Extra Benefits card styling in review-phase.tsx:726,1693,2270,2420 · tsc green · Pending: none.
2026-09-03 · Antigravity · Planned excess amount 0.00 default, validity fallback to cover start date, valuation type 'NO' -> Market Value fix, template element placement, and AI learned memory viewer tab · Created implementation plan artifact · Pending: user approval.
2026-09-03 · Antigravity · Implemented excess default 0.00, validity fallback, valuation type negative check in candidate_finder.py:818, draft_mapper.py:129, published template revisions, added GET /settings/ai-memory and Learned Memory tab in ai-context/page.tsx · 547 pytest passing + tsc clean · Pending: none.
2026-09-03 · Antigravity · Fixed AttributeError 'str' object has no attribute 'get' in build_rag_system_prompt and extraction pipeline by handling string plan lists in gemini_extractor.py:323, routes.py:683,774, orchestrator.py:116 · 15/15 regression tests passing · Pending: none.
2026-09-03 · Antigravity · Formulated plan to resolve IDE type checker diagnostics in gemini_extractor.py:289, draft_mapper.py:159, and test_extraction_regression.py:302 · Created implementation plan artifact · Pending: user approval.
2026-09-03 · Antigravity · Resolved IDE type checker diagnostics in gemini_extractor.py:10,288,416, draft_mapper.py:158; Pyright 0 errors, 15/15 regression tests green · Pending: none.
2026-09-03 · Antigravity · Cleared redundant str() call warnings in gemini_extractor.py:304,317,328; pyright 0 errors and 0 warnings across all files · Pending: none.
2026-09-03 · Antigravity · Confirmed project context, active stack, and recent progress for the user · Reviewed docs/core/START-HERE.md, STATE.md, and PROJECT-CONTEXT.md · Pending: none.
2026-09-03 · Antigravity · Drafted implementation plan for complex fixes (visibility toggles, revisions UI, vehicle deduplication, AI memory, sequential refs) and pushed back on deleting backend revisions to preserve immutability · Created implementation_plan.md · Pending: User review and approval.
2026-09-03 · Antigravity · Committed and pushed v13 to origin/v13 and origin/main; published new branch v14 to origin/v14 and checked out · 548 pytest green, tsc green, build clean · Pending: none.


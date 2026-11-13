# Core Domain Engines: Complete Language-Agnostic Pseudocode Blueprints

> **Textbook Purpose**: Before a civil engineer pours concrete, they check exact mathematical blueprints. Before anyone touches production code in Phase 1–4, this document defines the **exact step-by-step pseudocode** for Risklocker's six critical engines so Python, PostgreSQL, and TypeScript stay 100% deterministic, testable, and free of "magic numbers".

---

## 1. Engine 1: Deterministic Decimal Pricing & Rounding Engine

**What it cures**: Eliminates float rounding errors, prevents [`draft_mapper.py:556`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/extraction/draft_mapper.py#L556) from overwriting calculated totals with stale insurer totals, eliminates silent `except Exception: pass` in [`workspace_patch_service.py:268`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/workspace_patch_service.py#L268), and aligns Preview with PDF totals.

```text
STRUCT MoneyResult:
    base_insurance_net : DECIMAL(12,2)   // Insurer premium AFTER discount/NCD, SST & Stamp Duty (excluding optional addons added separately OR already reconciled)
    addons_total       : DECIMAL(12,2)   // Sum of ONLY active PAID optional add-ons
    road_tax           : DECIMAL(12,2)
    runner_fee         : DECIMAL(12,2)
    agency_discount    : DECIMAL(12,2)   // Defaults to 0.00
    raw_total_payable  : DECIMAL(12,2)
    final_total_payable: DECIMAL(12,2)
    rounding_adjustment: DECIMAL(12,2)   // final_total - raw_total (transparent audit trail!)
    discrepancies      : LIST<TEXT>

FUNCTION parse_money_strict(raw_value, field_name) -> DECIMAL(12,2):
    IF raw_value IS NULL OR trim(string(raw_value)) == "":
        RETURN DECIMAL("0.00")
    cleaned = strip_currency_tokens_and_commas(raw_value) // allows optional leading '-' only where discounts permitted
    IF cleaned does NOT match regex "^-?\d+(\.\d+)?$":
        RAISE ValidationError("Invalid monetary format for " + field_name + ": " + raw_value)
    val = ROUND_HALF_UP(DECIMAL(cleaned), 2)
    IF val < 0 AND field_name != "agency_discount":
        RAISE ValidationError(field_name + " cannot be negative")
    RETURN val

FUNCTION compute_quotation_pricing(draft_fields, active_selections, round_to_ringgit : BOOL) -> MoneyResult:
    base_net  = parse_money_strict(draft_fields.premium, "premium")
    road_tax  = parse_money_strict(draft_fields.roadtax, "roadtax")
    runner    = parse_money_strict(draft_fields.runner_fee, "runner_fee")
    discount  = parse_money_strict(draft_fields.quotation_discount, "agency_discount")

    addons_sum = DECIMAL("0.00")
    FOR EACH sel IN active_selections:
        IF sel.state IN {"current", "available_addon"} AND sel.is_selected AND sel.cost_status == "paid":
            // Raise explicit ValidationError instead of silent try/except swallow!
            addons_sum = addons_sum + parse_money_strict(sel.premium_amount, "addon:" + sel.concept_key)

    raw_total = base_net + addons_sum + road_tax + runner - discount
    IF raw_total < 0:
        RAISE ValidationError("Discount exceeds gross quotation payable")

    IF round_to_ringgit IS TRUE:
        final_total = ROUND_HALF_UP(raw_total, 0).quantize("0.01")
    ELSE:
        final_total = ROUND_HALF_UP(raw_total, 2)

    rounding_adj = final_total - raw_total
    RETURN MoneyResult(base_net, addons_sum, road_tax, runner, discount, raw_total, final_total, rounding_adj, [])
```

---

## 2. Engine 2: Safe AST-Based JPJ Road Tax Engine (Zero `eval()` + Monotonic Brackets)

**What it cures**: Replaces dangerous [`_eval_formula`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/road_tax_engine.py#L21-L29) (`eval()` permitting `9**9**9` CPU/memory DoS) and fixes the `2500cc` RM 880 -> `2501cc` RM 842.50 bracket cliff (`road_tax_engine.py:41-42`, [`provider.tsx:116`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/frontend/src/components/session-workspace/provider.tsx#L116)).

```text
ALLOWED_AST_NODES = {Expression, BinOp, UnaryOp, Constant, Name("cc"), Call(id IN {"ceil", "floor", "min", "max"})}
ALLOWED_OPERATORS = {Add, Sub, Mult, Div} // Deliberately EXCLUDE Pow (**) and Mod/Bitwise!

FUNCTION safe_eval_ast(node, cc : DECIMAL) -> DECIMAL:
    IF node IS Constant AND node.value IS Number:
        RETURN DECIMAL(string(node.value))
    IF node IS Name AND node.id == "cc":
        RETURN cc
    IF node IS UnaryOp AND op IS USub:
        RETURN -safe_eval_ast(node.operand, cc)
    IF node IS BinOp AND op IN ALLOWED_OPERATORS:
        left = safe_eval_ast(node.left, cc)
        right = safe_eval_ast(node.right, cc)
        IF op IS Div AND right == 0:
            RAISE RoadTaxFormulaError("Division by zero in road tax formula")
        RETURN apply_decimal_op(op, left, right)
    IF node IS Call AND node.func.id IN {"ceil", "floor", "min", "max"}:
        args = [safe_eval_ast(a, cc) for a in node.args]
        RETURN apply_safe_math_func(node.func.id, args)
    RAISE RoadTaxFormulaError("Disallowed expression node in road tax formula")

FUNCTION compute_jpj_road_tax(cc_or_watts, raw_vehicle_class, owner_type, jurisdiction, db_rules) -> DECIMAL(12,2):
    // Step 1: Resolve powertrain & normalize units BEFORE rate lookup (cures draft_mapper bug!)
    powertrain, normalized_measure = classify_powertrain_and_measure(cc_or_watts, raw_vehicle_class)
    IF normalized_measure <= 0:
        RETURN DECIMAL("0.00")

    // Step 2: Check active DB rule table first (strict monotonic invariant verified at seed/save time)
    rule = query_matching_db_rule(db_rules, powertrain, raw_vehicle_class, owner_type, jurisdiction, normalized_measure)
    IF rule EXISTS:
        IF rule.formula IS NOT EMPTY:
            ast_tree = parse_ast(rule.formula)
            amount = safe_eval_ast(ast_tree, normalized_measure)
        ELSE:
            amount = rule.base_rate
        RETURN ROUND_HALF_UP(amount, 2)

    // Step 3: Declarative monotonic fallback brackets (Peninsular Private Saloon example):
    // Verify Continuity at boundaries:
    //   2001..2500cc: 380.00 + (cc - 2000)*1.00 => at 2500cc = 880.00
    //   2501..3000cc: 880.00 + (cc - 2500)*2.50 => at 2501cc = 882.50, at 3000cc = 2130.00!
    //   >3000cc:      2130.00 + (cc - 3000)*4.50 => continuous!
    RETURN ROUND_HALF_UP(lookup_bracket_formula(powertrain, raw_vehicle_class, owner_type, jurisdiction, normalized_measure), 2)
```

---

## 3. Engine 3: Unified Benefit, Condition & 24-Slot Design 2 Card Engine

**What it cures**: Eliminates `4+1` conflicting benefit systems, fixes [`generation_service.py:351`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/generation_service.py#L351) (`company_key` -> always `"etiqa"`), and guarantees identical output in Python PDF and React preview via a **single server-computed payload**.

```text
FUNCTION resolve_unified_quotation_benefits(company_slug, vehicle_class, package_slug, draft_selections, catalog_rules, eval_context):
    // 1. Validate insurer identity via InsuranceCompany.slug (NEVER missing getattr(..., "company_key", "etiqa"))
    rules = query_company_rules(catalog_rules, company_slug, vehicle_class, package_slug)

    cards_by_key = ORDERED_MAP()
    // 2. Materialize 24 Canonical Concepts from DB table `benefit_concepts` (seeded once via migration, NOT hardcoded in TS/PY!)
    FOR EACH concept IN load_canonical_concepts_ordered(vehicle_class):
        rule = rules.get(concept.concept_key)
        selection = draft_selections.get(concept.concept_key)

        is_selected = determine_selection_state(rule, selection) // extracted FOC, package included, or staff ticked paid addon
        coverage_txt = format_coverage_limit(rule, selection, eval_context)
        cost_decimal = compute_addon_cost(rule, selection, eval_context)

        cards_by_key[concept.concept_key] = Card(
            concept_key=concept.concept_key,
            title=selection.custom_title OR rule.title_override OR concept.title,
            description=selection.custom_desc OR rule.desc_override OR concept.default_description,
            is_selected=is_selected,
            inclusion_kind=determine_kind(rule, selection), // 'foc' vs 'paid_addon' vs 'unselected_optional'
            display_value=coverage_txt,
            cost_amount=cost_decimal,
            icon_key=concept.icon_key,
        )

    // 3. Apply conditional rules deterministically (e.g. if Motor PA Plus Plan >= 2 selected -> upgrade Towing card)
    apply_conditional_rules(cards_by_key, rules.conditions)

    // 4. Deterministic partition: selected (ticked) cards float to slots 01..N, unselected optional cards follow!
    selected_cards = [c for c in cards_by_key.values() if c.is_selected]
    unselected_cards = [c for c in cards_by_key.values() if NOT c.is_selected]
    ordered = assign_serial_numbers(selected_cards + unselected_cards) // "01", "02", ...

    RETURN SplitPages(page1_cards=ordered[0:24], overflow_cards=ordered[24:])
```

---

## 4. Engine 4: Render Worker, Chromium Pool & Atomic Supabase Upload

**What it cures**: Eliminates [`render_worker.py:195`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/workers/render_worker.py#L195) (`if storage is not None:` bug writing PDFs to local `.qc-tmp/`) and eliminates [`pdf_generator.py:37`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/rendering/pdf_generator.py#L37) launching a new Chromium process per PDF.

```text
FUNCTION process_render_job(db, settings, job, storage_client):
    // 1. Always initialize real storage client; fail fast in production if bucket unreachable!
    IF storage_client IS NULL:
        storage_client = SupabaseStorage(settings)
    IF settings.app_env == "production" AND NOT storage_client.is_configured():
        RAISE FatalConfigError("Supabase storage is mandatory in production")

    // 2. Indexed lookup (NEVER _rows(db, RenderSnapshot)!)
    snapshot = db.query_one(RenderSnapshot WHERE id == job.payload["render_snapshot_id"])
    assert_canonical_hash_matches(snapshot)

    resolved_assets = download_and_verify_sha256_assets(snapshot, storage_client)
    html_document = render_template_html(snapshot.context, resolved_assets, agency_profile=load_agency_profile(db))

    // 3. Acquire warm Chromium BrowserContext from thread/process pool instead of cold browser launch!
    WITH ChromiumContextPool.acquire(timeout_sec=15) AS page:
        pdf_bytes = page.render_pdf_from_html(html_document, viewport=snapshot.page_profile)

    assert_valid_pdf_header_and_eof(pdf_bytes)
    sha256_hex = sha256(pdf_bytes)

    // 4. Atomic Upload -> DB Commit -> Cleanup Compensation
    stored_obj = storage_client.upload_generated_pdf(object_key, pdf_bytes)
    TRY:
        BEGIN TRANSACTION:
            lock_draft_for_version_increment(snapshot.draft_id)
            version_no = max_version_for_draft(snapshot.draft_id) + 1
            insert GeneratedPdfVersion(storage_provider="supabase", storage_bucket=stored_obj.bucket, storage_sha256=sha256_hex, ...)
            mark_job_completed(job, version_no)
        COMMIT
    CATCH DbError:
        storage_client.delete_pdf_safe(stored_obj.object_key) // Compensating cleanup: never leave orphan bucket objects
        RETHROW
```

---

## 5. Engine 5: Deterministic Towing, Customer Identity & Calendar-Exact Renewal Dates

### 5.1 Fixed Towing & Comparison Evaluator
Fixes [`towing_evaluator.py:231`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/marketing_comparison/towing_evaluator.py#L231) and [`ncd_evaluator.py:287`](file:///c:/Users/mahmud/Desktop/Code/risklocker/quote_risklocker/backend/app/services/marketing_comparison/ncd_evaluator.py#L287):

```text
FUNCTION evaluate_stmb_towing(combined_text, extracted_raw) -> (normalized_limit, is_uncertain):
    IF matches_word_boundary(combined_text, r"\b(unlimited|tanpa\s+had)\b"):
        RETURN ("Unlimited", FALSE)
    IF has_pa_plus_addon(combined_text):
        // STRICT word-boundary plan match — NEVER `"4" in text`!
        IF regex_match(combined_text, r"\b(?:plan|pelan)\s*(?:4|iv|d)\b"): RETURN ("Unlimited", FALSE)
        IF regex_match(combined_text, r"\b(?:plan|pelan)\s*(?:3|iii|c)\b"): RETURN ("300 km", FALSE)
        IF regex_match(combined_text, r"\b(?:plan|pelan)\s*(?:2|ii|b)\b"): RETURN ("200 km", FALSE)
        IF regex_match(combined_text, r"\b(?:plan|pelan)\s*(?:1|i|a)\b"):   RETURN ("100 km", FALSE)
        RETURN ("Plan Tier Unspecified (Check PA+)", TRUE) // Human review!
    RETURN ("50 km", FALSE)

FUNCTION fallback_towing(extracted_raw, company_slug) -> (normalized_limit, is_uncertain):
    IF explicit_km_or_rm_found(extracted_raw):
        RETURN (formatted_value, FALSE)
    // NEVER default unknown to "Unlimited"!
    RETURN ("Unspecified (Check Policy)", TRUE)
```

### 5.2 Calendar-Exact Annual Tenure Dates & Safe Customer Match

```text
FUNCTION compute_annual_policy_end(start_date : DATE) -> DATE:
    // Exact 1-year policy period in Malaysia (e.g. 2024-03-01 -> 2025-02-28; 2023-03-01 -> 2024-02-29 leap year!)
    next_year_same_day = add_calendar_years(start_date, 1) // Clamps Feb 29 -> Feb 28 cleanly
    RETURN next_year_same_day - timedelta(days=1)

FUNCTION resolve_customer_strict(db, raw_name, raw_gov_id) -> (CustomerAccount, Discrepancies):
    norm_id, id_kind = normalize_government_id(raw_gov_id)
    IF norm_id EXISTS AND NOT is_placeholder_id(norm_id):
        customer = db.find_by_id_number(norm_id)
        IF customer FOUND: RETURN (customer, check_contact_diffs(customer))
        RETURN create_verified_customer(norm_id, id_kind, raw_name)
    // NEVER blindly auto-merge by canonical_name alone when NRIC/BRN is missing!
    provisional_customer = create_provisional_customer(raw_name)
    possible_matches = db.find_candidates_by_name(raw_name)
    IF possible_matches NOT EMPTY:
        record_duplicate_review_flag(provisional_customer.id, possible_matches)
    RETURN (provisional_customer, [])
```

---

## 6. Engine 6: Double-Entry Ledger Posting Protocol

```text
FUNCTION post_policy_win_journal(db, tenure, invoice, actor_id, idempotency_key):
    // Idempotent posting on policy win: Debtor Receivable Dr, Insurer Payable Cr, Agency Income Cr
    ASSERT invoice.total_receivable == invoice.gross_premium + invoice.service_tax + invoice.stamp_duty + invoice.road_tax + invoice.runner_fee - invoice.discount
    net_to_insurer = compute_net_remittance_to_insurer(invoice)
    agency_revenue = invoice.total_receivable - net_to_insurer

    lines = [
        JournalLine(account="1200-AR-CLIENT",  debit=invoice.total_receivable, credit=0.00),
        JournalLine(account="2100-AP-INSURER", debit=0.00,                     credit=net_to_insurer),
        JournalLine(account="4010-AGENCY-REV", debit=0.00,                     credit=agency_revenue),
    ]
    ASSERT sum(l.debit for l in lines) == sum(l.credit for l in lines)
    insert_atomic_journal_entry(db, tenure.id, invoice.id, lines, idempotency_key, actor_id)
```


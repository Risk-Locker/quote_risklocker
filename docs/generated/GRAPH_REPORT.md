# Graph Report - .qc-tmp  (2026-11-11)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 6348 nodes · 24269 edges · 254 communities (174 shown, 80 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 3500 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f8c410a6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 135
- Community 136
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 142
- Community 143
- Community 144
- Community 145
- Community 146
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- Community 154
- Community 155
- Community 156
- Community 157
- Community 158
- Community 159
- Community 160
- Community 161
- Community 162
- Community 163
- Community 166
- Community 167
- Community 168
- Community 169
- Community 170
- Community 171
- Community 172
- Community 173
- Community 174
- Community 175
- Community 177
- Community 178
- Community 179
- Community 180
- Community 181
- Community 182
- Community 183
- Community 184
- Community 186
- Community 187
- Community 188
- Community 189
- Community 190
- Community 191
- Community 192
- Community 193
- Community 194
- Community 195
- Community 196
- Community 197
- Community 198
- Community 202
- Community 204
- Community 205

## God Nodes (most connected - your core abstractions)
1. `Session` - 735 edges
2. `User` - 474 edges
3. `AppError` - 349 edges
4. `QuotationDraft` - 225 edges
5. `new_id()` - 197 edges
6. `api()` - 164 edges
7. `InsuranceCompany` - 148 edges
8. `Button` - 133 edges
9. `apiErrorMessage()` - 127 edges
10. `BenefitConcept` - 120 edges

## Surprising Connections (you probably didn't know these)
- `test_profile_schemas_validation()` --uses--> `CompanyBenefitConfigsUpdateRequest`  [INFERRED]
  tests/test_company_benefit_profiles.py → backend/app/api/schemas.py
- `test_v7_revision_and_snapshot_columns_are_part_of_the_orm_contract()` --uses--> `Base`  [INFERRED]
  tests/test_v7_domain.py → backend/app/models/tables.py
- `test_v7_schema_is_additive_and_preserves_legacy_tables()` --uses--> `Base`  [INFERRED]
  tests/test_v7_domain.py → backend/app/models/tables.py
- `test_comma_grouped_numeric_values_normalize_exactly_without_rounding()` --uses--> `BenefitValue`  [INFERRED]
  tests/test_render_context.py → backend/app/domain/benefits.py
- `test_typed_values_cover_money_percentage_per_day_formula_and_custom()` --uses--> `BenefitValue`  [INFERRED]
  tests/test_v7_domain.py → backend/app/domain/benefits.py

## Import Cycles
- 2-file cycle: `frontend/src/components/tenures/edit-vehicle-deal-modal.tsx -> frontend/src/components/tenures/tenure-timeline-ledger.tsx -> frontend/src/components/tenures/edit-vehicle-deal-modal.tsx`

## Communities (254 total, 80 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (151): current_user(), settings_dep(), admin_our_special_save(), BackfillConfirmRequest, BenefitAliasSaveRequest, BenefitCardPresetCreateRequest, BenefitCardPresetSaveRequest, BenefitCatalogSaveRequest (+143 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (118): AssetLibraryPage(), handleBulkDelete(), handleBulkMove(), handleDeleteFolder(), handleDeleteSingle(), handleRenameFolder(), handleUpdateAsset(), uploadBatch() (+110 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (95): session_extract_gemini(), detect_is_covernote(), get_correction_memory(), get_db_packs(), RecordStatus, Batch, DraftBenefitSelection, DraftSourceLineDecision (+87 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (98): invalidate_cache(), AuditEvent, BenefitAlias, BenefitPackagePlan, BenefitPackagePlanItem, BusinessAsset, CompanyAlias, CompanyBenefitCondition (+90 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (80): BenefitConcept, BenefitProfile, CatalogOffering, CompanyBenefitConfig, InsuranceCompany, new_id(), utcnow(), activate_benefit_profile() (+72 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (85): ActiveTab, AIContextData, AIMemoryData, AIMemoryItem, ChatMessage, STARTER_PROMPTS, BenefitConditionsTab(), CompanyBenefitsTab() (+77 more)

### Community 6 - "Community 6"
Cohesion: 0.04
Nodes (73): BenefitValue, CostStatus, format_coverage_value(), MoneyAmount, ReviewedBenefitState, SourceLineDisposition, normalize_date(), normalize_money() (+65 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (107): business_activate_global_benefit_profile(), business_auto_assign_global_benefit_profile(), business_benefit_alias_retire(), business_benefit_alias_save(), business_benefit_alias_update(), business_benefit_aliases(), business_benefit_concept_restore(), business_benefit_concept_retire() (+99 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (88): settings_ai_prompt_put(), extraction_detail(), admin_companies(), admin_company_delete(), admin_company_save(), admin_dictionaries(), admin_extraction_settings_save(), admin_field_alias_delete() (+80 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (77): ComparisonContent(), ComparisonPage(), LedgerContent(), LedgerPage(), TabKey, GeminiEndpointItem, GeminiQuota, GeminiQuotaInfoButton() (+69 more)

### Community 10 - "Community 10"
Cohesion: 0.04
Nodes (67): AuthContext, current_auth(), current_auth_optional(), ensure_trusted_origin(), _remaining_session_seconds(), auth_change_password(), auth_login(), auth_logout() (+59 more)

### Community 11 - "Community 11"
Cohesion: 0.06
Nodes (68): BenefitCatalog, BenefitCatalogRevision, BenefitPackage, remove_catalog_offering(), save_catalog_offering(), _validate_assignment_context(), _catalogs_batch(), main() (+60 more)

### Community 12 - "Community 12"
Cohesion: 0.05
Nodes (45): BenefitEvaluationEngine, EvaluatedBenefit, calculate_exact_rate(), detect_runner_fee_from_id(), _extract_exact_basic_figure(), _extract_excess(), _extract_ncd_from_draft(), _extract_source_quotation_no() (+37 more)

### Community 13 - "Community 13"
Cohesion: 0.04
Nodes (43): InsightsPage(), RedirectContent(), ComparisonEntry, ComparisonMatrix(), ComparisonMatrixProps, formatExpiryDateDisplay(), TenureSpec, CustomerVehicleLedgerPane() (+35 more)

### Community 14 - "Community 14"
Cohesion: 0.05
Nodes (46): choose_winner(), ComparisonEntryUpsertRequest, convert_session_document_type(), ConvertDocumentTypeRequest, delete_entry(), FixedCostsUpdateRequest, generate_all_deal_quotes(), generate_single_entry_quote() (+38 more)

### Community 15 - "Community 15"
Cohesion: 0.04
Nodes (62): LoginForm(), submit(), LoginPage(), SettingsAiEnginePage(), handleAddKey(), handleDeleteKey(), loadData(), formatBytes() (+54 more)

### Community 16 - "Community 16"
Cohesion: 0.04
Nodes (37): record_audit_event(), DeliveryState, FieldStatus, InsuranceType, NotificationEventType, AdminSuggestion, Base, BenefitRelation (+29 more)

### Community 17 - "Community 17"
Cohesion: 0.04
Nodes (67): BenefitValueEditor(), handleChange(), BenefitValueEditorProps, parseValueString(), TypedValue, typedValueLabel(), typedValueToString(), AiCatalogSidebar() (+59 more)

### Community 18 - "Community 18"
Cohesion: 0.05
Nodes (16): _apply(), main(), _report(), audit_and_clean(), main(), build_plan(), _get_amassurance_company(), _get_newest_published_revision() (+8 more)

### Community 19 - "Community 19"
Cohesion: 0.06
Nodes (65): TemplateBuilderPage(), commitTree(), handleAddContainer(), handleAddElement(), handleAddSection(), handleAddSubContainer(), addSubRecursive(), handleDeleteBlock() (+57 more)

### Community 20 - "Community 20"
Cohesion: 0.07
Nodes (52): draft_update(), draft_workspace_patch(), admin_template_asset_upload(), admin_template_copy(), admin_template_group_save(), admin_template_make_master(), admin_template_save(), admin_template_set_default() (+44 more)

### Community 21 - "Community 21"
Cohesion: 0.05
Nodes (19): GeminiApiCallLog, GeminiAccount, GeminiAccountManager, get_current_local_date(), persist_call_log(), _do_insert(), _admin_user(), _http_client() (+11 more)

### Community 22 - "Community 22"
Cohesion: 0.05
Nodes (42): TrackedVehicle, format_whatsapp_teaser(), save_comparison_entry(), select_winner_and_generate_draft(), update_tenure_fixed_costs(), test_comparison_api_crud_and_teaser(), test_comparison_handles_whitespace_mismatch_without_unique_violation(), test_comparison_upload_quote_api() (+34 more)

### Community 23 - "Community 23"
Cohesion: 0.07
Nodes (54): BenefitCombobox(), BenefitComboboxProps, BenefitConditionsTabProps, BenefitsDialogs(), BenefitsDialogsProps, BenefitsStepNavigator(), handleSaveTpo(), BenefitsStepNavigatorProps (+46 more)

### Community 24 - "Community 24"
Cohesion: 0.05
Nodes (48): SessionLayout(), SessionWorkspacePage(), SLIDE, PhaseKey, SessionPhaseBar(), SessionPhaseBarProps, STEP_HREFS, STEPS (+40 more)

### Community 25 - "Community 25"
Cohesion: 0.08
Nodes (22): _field(), upsert_from_draft(), _resolve_preview_assets(), generate_pdf(), _version_filename(), purge_expired_pdfs(), create_batch_from_uploads(), _get_shared_client() (+14 more)

### Community 26 - "Community 26"
Cohesion: 0.05
Nodes (53): dependencies, framer-motion@^12.43.0, html-to-image@^1.11.13, jspdf@^4.2.1, lucide-react@^0.468.0, next@^15.1.3, @phosphor-icons/react@^2.1.10, @radix-ui/react-dialog@^1.1.23 (+45 more)

### Community 27 - "Community 27"
Cohesion: 0.05
Nodes (42): Asset, CategoryInfo, kinds, CompaniesPage(), handleLogoUpload(), Asset, AutoAssignMatch, AutoAssignResponse (+34 more)

### Community 28 - "Community 28"
Cohesion: 0.06
Nodes (26): main(), run_check(), check_external_releases(), check_internal_health(), fetch_json(), main(), run_radar(), evaluate_payload() (+18 more)

### Community 29 - "Community 29"
Cohesion: 0.05
Nodes (30): _integrity_message(), register_error_handlers(), integrity_error_handler(), client(), test_catalog_offering_requires_typed_value_and_base_revision(), test_catalog_publish_requires_base_revision_and_returns_published_catalog(), test_company_detection_aliases_live_under_business_api(), test_crud_lifecycle_operations_contract() (+22 more)

### Community 30 - "Community 30"
Cohesion: 0.07
Nodes (27): bulk_confirm_hit(), bulk_delete_tenures(), BulkConfirmHitRequest, BulkDeleteTenuresRequest, create_tenure(), CreateTenureRequest, delete_tenure_endpoint(), generate_tenure_quote() (+19 more)

### Community 31 - "Community 31"
Cohesion: 0.06
Nodes (30): CustomerUpdateRequest, update_customer_endpoint(), update_tenure_ledger_fields(), UpdateTenureLedgerRequest, CustomerAccount, list_customers(), resolve_or_create_customer(), is_corporate_entity() (+22 more)

### Community 32 - "Community 32"
Cohesion: 0.07
Nodes (31): admin_template_preview_render(), _build_preview_profile_data(), _get_benefit_artwork_data_uris(), _extract_field(), _format_price_badge(), get_company_logo_data_uri(), get_design2_asset_uris(), _local_file_data_uri() (+23 more)

### Community 33 - "Community 33"
Cohesion: 0.07
Nodes (25): qc_temp_directory(), resolve_qc_path(), available_engines(), run_enhanced_reading(), _run_ocrmypdf(), _run_tesseract(), _tesseract_page_text(), _defender_command() (+17 more)

### Community 34 - "Community 34"
Cohesion: 0.09
Nodes (40): is_pds_text(), _add(), _add_2d_spatial_candidates(), _add_amgen_profile(), _add_company_detection(), _add_contribution_rows(), row_amount(), _add_line_value() (+32 more)

### Community 35 - "Community 35"
Cohesion: 0.08
Nodes (42): _balance_benefit_grid_elements(), render_quotation_html(), cards(), config(), test_all_dense_cards_have_one_uniform_scale_and_remain_present(), test_available_addons_grid_uses_only_available_context_cards(), test_dense_quotation_auto_fit_zero_scale_and_multiline_title(), test_empty_grid_hides_without_fake_or_legacy_global_cards() (+34 more)

### Community 36 - "Community 36"
Cohesion: 0.06
Nodes (19): resolve_client_ip(), RequestSecurityMiddleware, SecurityHeadersMiddleware, consume_rate_limit(), policy_for_request(), RateLimitMiddleware, RateLimitPolicy, RateLimitResult (+11 more)

### Community 37 - "Community 37"
Cohesion: 0.10
Nodes (33): _dynamic_benefit_grid(), _get_helpers(), _aligned_offset(), _candidate_score(), GridBounds, GridSpec, pack_fixed_grid(), PackedCard (+25 more)

### Community 38 - "Community 38"
Cohesion: 0.05
Nodes (28): compute_quotation_content_hash(), mark_tenure_lapsed(), normalize_tenure_dates(), resolve_or_create_tenure(), shift_tenure_dates(), clean_legacy_sessions(), db_session(), test_compute_quotation_content_hash() (+20 more)

### Community 39 - "Community 39"
Cohesion: 0.06
Nodes (42): _pdf_response(), client_record_saved_view_save(), client_records_bulk_delete(), confirm_insights_backfill(), create_session_activity(), run_insights_backfill(), update_session_status(), batch_detail() (+34 more)

### Community 40 - "Community 40"
Cohesion: 0.12
Nodes (32): apply_workspace_patch(), test_apply_workspace_patch_stamps_session_editor(), _catalog_values(), FakeDb, objects(), test_benefit_update_supports_label_description_and_null_price(), test_build_workspace_snapshot_preserves_existing_draft_and_never_wipes(), test_completely_invalid_selection_id_returns_404() (+24 more)

### Community 41 - "Community 41"
Cohesion: 0.12
Nodes (40): AppError, _alias_duplicate(), _audit(), clone_package(), list_coverage_types(), list_segments(), list_vehicle_categories(), list_vehicle_subcategories() (+32 more)

### Community 42 - "Community 42"
Cohesion: 0.07
Nodes (18): build_rag_system_prompt(), estimate_and_guard_payload(), extract_with_gemini_sync(), get_key_pool(), answer_grounding_query(), _extract_potential_plates(), _field_val(), clean_vehicle_tokens_deterministic() (+10 more)

### Community 43 - "Community 43"
Cohesion: 0.06
Nodes (39): label(), LayerAction, LayerIcon(), LayersPanel(), finishRename(), row(), LayersPanelProps, LiveSimulator() (+31 more)

### Community 44 - "Community 44"
Cohesion: 0.05
Nodes (45): concurrency, cancel-in-progress, group, env, if, name, needs, runs-on (+37 more)

### Community 45 - "Community 45"
Cohesion: 0.08
Nodes (28): resolve_benefit_cards(), test_hierarchical_description_resolution_5_tiers(), row(), test_complete_7_tier_precedence(), test_dynamic_condition_not_triggered_when_inactive(), test_dynamic_condition_triggers_upgrade(), test_hide_target_condition_suppresses_target_card(), test_render_context_available_cards_suppression_and_customer_extra_preservation() (+20 more)

### Community 46 - "Community 46"
Cohesion: 0.08
Nodes (41): app_settings, batches, benefit_options, correction_memory, document_groups, extraction_records, field_aliases, idx_batches_owner_id (+33 more)

### Community 47 - "Community 47"
Cohesion: 0.09
Nodes (21): business_benefit_card_preset_create(), business_benefit_card_preset_reset(), business_benefit_card_preset_set_default(), business_benefit_card_preset_update(), business_benefit_card_presets_list(), _preset_to_dict(), BenefitCardPreset, create_custom_benefit_card_preset() (+13 more)

### Community 48 - "Community 48"
Cohesion: 0.07
Nodes (20): benefit_identity(), build_source_manifest(), slugify(), validate_image_file(), cards(), main(), test_derivative_preserves_aspect_ratio_without_cropping(), test_opaque_derivative_uses_webp_and_never_enlarges() (+12 more)

### Community 49 - "Community 49"
Cohesion: 0.11
Nodes (10): _admin_user(), auth_settings(), FakeDb, _http_client(), _make_special(), _make_variant(), _ScalarResult, _staff_user() (+2 more)

### Community 50 - "Community 50"
Cohesion: 0.13
Nodes (35): trash_delete_forever(), OurSpecial, OurSpecialVariant, delete(), list_trash(), delete_client_record(), delete_special(), delete_special_variant() (+27 more)

### Community 51 - "Community 51"
Cohesion: 0.15
Nodes (33): _agency_bilingual_config(), _agency_bilingual_v2_config(), _agency_bilingual_v3_config(), _agency_bilingual_v3_lump_sum_config(), _agency_bilingual_v3_no_extras_config(), _agency_bilingual_v4_config(), _agency_bilingual_v4_lump_sum_config(), _agency_bilingual_v4_no_extras_config() (+25 more)

### Community 52 - "Community 52"
Cohesion: 0.07
Nodes (32): idx_insurance_tenures_expiry_month, idx_insurance_tenures_status, idx_insurance_tenures_vehicle, idx_insurance_tenures_vehicle_dates, insurance_tenures, idx_tenure_comp_session, idx_tenure_comp_tenure, tenure_comparison_entries (+24 more)

### Community 53 - "Community 53"
Cohesion: 0.11
Nodes (12): delete_company(), _admin_auth(), _admin_user(), auth_settings(), FakeDb, _http_client(), _make_company(), _ScalarResult (+4 more)

### Community 54 - "Community 54"
Cohesion: 0.08
Nodes (19): apply_asset_manifest(), build_asset_import_plan(), _company_identity_keys(), _delete_uploaded_paths(), _extension(), _normalized_alias(), _storage_path(), _upload_asset_payload() (+11 more)

### Community 55 - "Community 55"
Cohesion: 0.10
Nodes (28): _candidate_mappings(), extract_benefit_lines(), _format_display_money(), _heading_scope(), is_spurious_benefit_line(), _looks_like_benefit(), _money(), _normalized() (+20 more)

### Community 56 - "Community 56"
Cohesion: 0.09
Nodes (27): calculate_breakdown(), calculate_ev_car_road_tax(), calculate_ev_motorcycle_road_tax(), calculate_road_tax(), compute_rate(), _eval_formula(), find_matching_rule(), _normalize_jurisdiction() (+19 more)

### Community 57 - "Community 57"
Cohesion: 0.07
Nodes (16): client(), db_session(), admin_user(), client(), db_session(), test_exact_rate_formula_precision_and_takaful(), client(), db_session() (+8 more)

### Community 58 - "Community 58"
Cohesion: 0.10
Nodes (30): client_record_detail(), client_record_saved_views(), client_record_update(), client_records_bulk_action(), client_records_export(), client_records_list(), get_customer_detail(), insights_analytics() (+22 more)

### Community 59 - "Community 59"
Cohesion: 0.13
Nodes (20): job_cancel(), job_detail(), session_delete(), Job, cancel_job(), claim_next_job(), claim_query(), _elapsed_seconds() (+12 more)

### Community 60 - "Community 60"
Cohesion: 0.10
Nodes (13): add_pic(), CreatePicRequest, get_pics(), get_single_pic(), remove_pic(), update_single_pic(), UpdatePicRequest, PersonInCharge (+5 more)

### Community 61 - "Community 61"
Cohesion: 0.10
Nodes (23): build_draft(), normalize_vehicle_model_text(), validate_engine_cc(), validate_ncd(), validate_vehicle_number(), test_draft_mapper_sets_detected_value_and_prefers_realistic_sum_insured(), test_messy_compact_text_maps_model_cc_and_coverage_type(), test_messy_text_maps_customer_vehicle_and_year() (+15 more)

### Community 62 - "Community 62"
Cohesion: 0.13
Nodes (11): FakeDb, scan(), settings(), Storage, test_database_failure_rolls_back_and_reconciles_uploaded_object(), test_idempotency_key_owned_by_another_user_is_conflict(), test_new_upload_creates_one_queued_session_transaction_and_no_expiry(), test_safe_retry_returns_existing_job_without_reading_or_uploading_file() (+3 more)

### Community 63 - "Community 63"
Cohesion: 0.09
Nodes (21): SessionItem, SessionsPage(), StaffOption, EditVehicleDealModal(), EditVehicleDealModalProps, TenureTimelineDrawer(), formatDateSafe(), formatDateTimeSafe() (+13 more)

### Community 64 - "Community 64"
Cohesion: 0.13
Nodes (29): Design2CanvasProps, Design2CanvasView(), Design2Footer(), FIELD_ALIASES, formatMoney(), getLocalCompanyLogoPath(), getVal(), GreenTickSvg() (+21 more)

### Community 65 - "Community 65"
Cohesion: 0.17
Nodes (19): _fake_db(), FakeDb, _ScalarResult, _settings(), _special(), _template(), test_delete_client_record_soft_deletes(), test_delete_special_soft_deletes_variants_too() (+11 more)

### Community 66 - "Community 66"
Cohesion: 0.13
Nodes (16): hash_password(), hash_session_token(), FakeSession, ScalarRows, settings(), test_change_password_requires_current_password(), test_dev_account_cannot_login_or_keep_a_session_in_production(), test_eight_hour_window_rolls_on_activity_and_then_expires() (+8 more)

### Community 67 - "Community 67"
Cohesion: 0.11
Nodes (11): detect_layout(), words_to_lines(), extract_native(), candidate_values_from_payload(), ExtractionOrchestrator, _apply_process_limits(), extract_with_limits(), _worker() (+3 more)

### Community 68 - "Community 68"
Cohesion: 0.13
Nodes (16): _draft(), FakeDb, plan_fixture_values(), Scalars, test_ai_detected_pack_auto_applies_plan_members(), test_apply_select_package_tier_operation(), test_extras_payload_and_adjusted_total(), test_plan_crud_requires_an_addon_bundle_and_plans_freezes_into_publish_hash() (+8 more)

### Community 69 - "Community 69"
Cohesion: 0.14
Nodes (14): QuotationActivity, backfill_existing_sessions(), bulk_update_quotation_status(), get_calendar_activities(), get_insights_analytics(), log_quotation_activity(), _safe_field_val(), update_quotation_status() (+6 more)

### Community 70 - "Community 70"
Cohesion: 0.15
Nodes (18): build_unified_matrix_cards(), _build_card_dict(), _push_item(), extract_free_coverage_items(), format_addon_value(), _infer_icon_hint(), _is_basic_emergency_towing(), is_item_selected() (+10 more)

### Community 71 - "Community 71"
Cohesion: 0.16
Nodes (20): _app_environment(), _app_network_settings(), _auth_hash_secret(), _bool(), _bounded_int(), _database_provider(), _database_url(), get_settings() (+12 more)

### Community 72 - "Community 72"
Cohesion: 0.26
Nodes (22): AppliedMigration, build_plan(), discover_migrations(), MigrationError, test_already_applied_legacy_rows_are_not_rerun(), test_crlf_migrations_still_require_contiguous_versions(), test_fresh_planning_returns_every_migration(), test_genuine_content_change_still_fails_against_historical_checksum() (+14 more)

### Community 73 - "Community 73"
Cohesion: 0.12
Nodes (22): idx_insurance_companies_category, idx_insurance_companies_name, idx_insurance_companies_status, insurance_companies, template_groups, company_benefit_conditions, company_benefit_configs, idx_company_benefit_conditions_company (+14 more)

### Community 74 - "Community 74"
Cohesion: 0.12
Nodes (11): WindscreenScraper, evaluate_cart_tariff(), evaluate_formula(), extract_evaluation_context(), _field_val(), _safe_eval(), test_evaluate_cart_tariff(), test_extract_evaluation_context() (+3 more)

### Community 75 - "Community 75"
Cohesion: 0.15
Nodes (21): _require_user_management_permission(), test_backend_auth_hash_secret_is_required(), test_backend_database_provider_rejects_unknown_provider(), test_backend_database_url_accepts_supabase_postgres(), test_backend_database_url_is_required(), test_backend_database_url_rejects_sqlite(), test_backend_production_rejects_cross_origin_cors(), test_backend_production_rejects_placeholder_auth_hash_secret() (+13 more)

### Community 76 - "Community 76"
Cohesion: 0.13
Nodes (15): sanitize_folder(), _admin_user(), auth_settings(), FakeDb, _http_client(), test_active_asset_library_never_lists_legacy_local_assets(), test_list_assets_includes_folder(), test_sanitize_folder_defaults_and_cleans() (+7 more)

### Community 77 - "Community 77"
Cohesion: 0.20
Nodes (20): compile_sections_to_canvas(), default_header_config(), default_right_containers(), default_right_containers_v2(), extract_sections_from_canvas(), get_lump_sum_extras_price(), backfill_all_templates(), sample_canvas() (+12 more)

### Community 78 - "Community 78"
Cohesion: 0.11
Nodes (10): csrf_token_for_session(), generate_session_token(), keyed_hash(), verify_password(), csrf_app(), security_settings(), test_csrf_token_is_session_bound_and_required_for_authenticated_mutations(), test_login_is_csrf_exempt_but_still_requires_the_trusted_origin() (+2 more)

### Community 79 - "Community 79"
Cohesion: 0.14
Nodes (12): run_one_job(), extraction_result(), FakeDb, _objects(), Storage, test_source_hash_mismatch_fails_before_extraction(), test_successful_job_persists_initial_extraction_and_completes(), extractor() (+4 more)

### Community 80 - "Community 80"
Cohesion: 0.12
Nodes (23): idx_quotation_activities_session_id, idx_quotation_activities_status, idx_quotation_activities_timestamp, idx_quotation_activities_vehicle_no, idx_sessions_quotation_status, idx_tracked_vehicles_vehicle_no, idx_vehicle_ownerships_current, idx_vehicle_ownerships_vehicle_id (+15 more)

### Community 81 - "Community 81"
Cohesion: 0.10
Nodes (8): bootstrap_primary(), create_admin(), init_db(), main(), _normalize_email(), FakeSessionContext, test_default_data_seed_never_bootstraps_or_resets_primary_admin(), test_web_startup_checks_dependencies_without_mutating_schema_credentials_or_retention()

### Community 82 - "Community 82"
Cohesion: 0.15
Nodes (16): is_corporate_name(), _apply_detected_packs(), _drop_plan_selection(), _field_value(), _norm(), _normalized_value(), pin_catalog_context(), _resolve_coverage_type() (+8 more)

### Community 83 - "Community 83"
Cohesion: 0.18
Nodes (21): benefit_catalog_revision_immutable, benefit_package_immutable, benefit_relation_immutable, business_assets_content_hash_idx, business_assets_kind_status_idx, catalog_offering_immutable, public.benefit_catalog_revisions, public.benefit_concepts (+13 more)

### Community 84 - "Community 84"
Cohesion: 0.15
Nodes (12): classify_client_entity(), classify_vehicle_ev_status(), is_business_registration(), is_malaysian_nric(), is_non_saloon_model(), test_classify_client_entity_with_ev(), test_classify_vehicle_ev_status_canonical(), test_template_renderer_engine_capacity_formatting() (+4 more)

### Community 85 - "Community 85"
Cohesion: 0.14
Nodes (11): VehicleOwnership, assign_or_get_deal_cycle(), check_vehicle_ownership_conflict(), get_upcoming_renewals(), is_valid_malaysian_plate(), normalize_plate(), resolve_vehicle_ownership(), _sequence_label() (+3 more)

### Community 86 - "Community 86"
Cohesion: 0.17
Nodes (10): editable_template(), FakeDb, Scalars, template_config(), test_new_publication_rejects_legacy_manual_benefit_content(), test_non_business_role_cannot_publish_or_list_templates(), test_publish_creates_exact_immutable_revision_and_canonical_page_profile(), test_published_options_return_only_latest_revision_without_company_filtering() (+2 more)

### Community 87 - "Community 87"
Cohesion: 0.14
Nodes (5): Notification, create_notification(), FakeSession, ScalarRows, TestNotificationService

### Community 88 - "Community 88"
Cohesion: 0.12
Nodes (15): ClientDossier, ClientDossierResponse, ClientProfile, ClientTenure, ConnectedClientDossier(), downloadClientZip(), fetchClients(), handleSearchSubmit() (+7 more)

### Community 89 - "Community 89"
Cohesion: 0.15
Nodes (8): FakeDb, objects(), Scalars, test_existing_version_for_key_returns_without_creating_job(), test_request_rejects_stale_revision_and_generation_blockers(), test_request_snapshots_exact_revision_then_enqueues_one_render_job(), test_same_key_is_idempotent_and_different_user_cannot_reuse_it(), user()

### Community 90 - "Community 90"
Cohesion: 0.15
Nodes (8): build_docx_reference(), _document_text(), register_docx_reference(), main(), FakeDb, test_non_docx_or_malformed_container_is_rejected(), test_owner_docx_is_extracted_as_unverified_reference_only(), test_registering_reference_is_idempotent_by_checksum()

### Community 91 - "Community 91"
Cohesion: 0.19
Nodes (17): convert_legacy_template_nodes(), template_config_hash(), config(), grid(), test_compatibility_mode_can_read_legacy_manual_benefits_but_not_publish_them(), test_duplicate_grid_kind_is_rejected(), test_editor_scenario_data_and_new_legacy_manual_benefit_elements_are_rejected(), test_empty_message_requires_customer_facing_copy() (+9 more)

### Community 92 - "Community 92"
Cohesion: 0.16
Nodes (9): _get_val(), main(), run_recalculation(), _set_val(), _to_decimal(), main(), update_template_headers(), main() (+1 more)

### Community 93 - "Community 93"
Cohesion: 0.10
Nodes (4): create_test_app(), test_app_error(), error_client(), SampleModel

### Community 95 - "Community 95"
Cohesion: 0.13
Nodes (16): idx_sessions_created_at, idx_sessions_owner_id, sessions, client_records, idx_client_records_created_at, idx_client_records_customer_name, idx_client_records_insurance_company, idx_client_records_insurer_no (+8 more)

### Community 96 - "Community 96"
Cohesion: 0.17
Nodes (13): apply_migrations(), connect_with_retry(), default_migration_root(), _ensure_ledger(), _history(), main(), Migration, validate_schema_history() (+5 more)

### Community 97 - "Community 97"
Cohesion: 0.17
Nodes (11): complete_job(), FakeDb, make_job(), test_claim_query_uses_skip_locked_and_recovers_expired_leases(), test_claim_sets_lease_heartbeat_and_attempt_atomically(), test_complete_and_cancel_are_terminal_and_serialization_is_safe(), test_enqueue_creates_queued_job_with_bounded_attempts(), test_enqueue_is_idempotent_and_does_not_duplicate_existing_job() (+3 more)

### Community 98 - "Community 98"
Cohesion: 0.15
Nodes (8): format_quotation_reference(), generate_quotation_reference(), get_current_business_time(), FakeDb, test_candidate_finder_does_not_extract_quotation_reference(), test_format_quotation_reference_exact_patterns(), test_generate_quotation_reference_increments_per_year(), test_generate_quotation_reference_uses_current_time_if_none()

### Community 99 - "Community 99"
Cohesion: 0.11
Nodes (5): ScalarResult, stored_record(), test_legacy_expiry_timestamp_does_not_hide_an_available_private_object(), test_legacy_retention_service_is_disabled_and_deletes_nothing(), test_timed_trash_purge_is_disabled_and_never_deletes_storage()

### Community 100 - "Community 100"
Cohesion: 0.19
Nodes (10): adapt_legacy_special(), adapt_legacy_template(), _value(), apply_backfill_plan(), build_backfill_plan(), normalize_key(), stable_key(), stable_uuid() (+2 more)

### Community 101 - "Community 101"
Cohesion: 0.17
Nodes (10): build_reference_inventory(), collect_database_surfaces(), _references(), asset_root(), _local_asset_id(), _local_assets(), _local_label(), main() (+2 more)

### Community 102 - "Community 102"
Cohesion: 0.20
Nodes (10): _filename(), JobProcessingError, process_render_job(), fake_renderer(), objects(), Storage, test_corrupt_snapshot_and_asset_hash_fail_before_render(), test_invalid_or_oversized_pdf_is_not_uploaded() (+2 more)

### Community 103 - "Community 103"
Cohesion: 0.13
Nodes (11): CalendarActivity, CalendarData, CalendarViewMode, MISS_REASONS, TeamsCalendarView(), fetchCalendarActivities(), getActivitiesForSlot(), handleReopenSession() (+3 more)

### Community 104 - "Community 104"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+10 more)

### Community 105 - "Community 105"
Cohesion: 0.22
Nodes (12): _admin_user(), auth_settings(), _http_client(), MemoryDb, _staff_user(), test_admin_upload_limits_endpoints(), test_bulk_upload_limit_default(), test_bulk_upload_limit_minimum_validation() (+4 more)

### Community 106 - "Community 106"
Cohesion: 0.13
Nodes (10): args, consoleErrors, __dirname, __filename, playwrightPath, qcTmpDir, repoRoot, shotsDir (+2 more)

### Community 107 - "Community 107"
Cohesion: 0.21
Nodes (10): QueuedUpload, _client(), FakeDb, _job(), test_job_cancel_changes_a_nonterminal_job(), test_job_status_is_shared_with_authenticated_staff(), test_missing_job_returns_404(), test_upload_accepts_exactly_one_file_and_returns_202() (+2 more)

### Community 108 - "Community 108"
Cohesion: 0.14
Nodes (9): cleanup_junk(), main(), _normalize_phrase(), seed_company_aliases(), seed_global_benefits(), test_matrix_partitioning_and_description_overrides(), make_offering(), test_seed_demo_betterment_configs_private_cars() (+1 more)

### Community 109 - "Community 109"
Cohesion: 0.18
Nodes (12): generated_pdf_draft_idempotency_uq, generated_pdf_render_hash_idx, jobs_claim_idx, jobs_lease_idx, jobs_owner_idx, jobs_session_idx, public.jobs, public.prevent_published_template_mutation() (+4 more)

### Community 110 - "Community 110"
Cohesion: 0.29
Nodes (15): _admin_user(), _fake_db(), test_copy_template_allows_locked_default_and_inherits_group(), test_copy_template_clones_editable_template_as_an_independent_draft(), test_make_template_master_promotes_and_demotes(), test_road_tax_explicit_dates_are_kept(), test_road_tax_missing_dates_default_to_today_and_one_year(), test_runner_fee_default_returns_20_when_unset() (+7 more)

### Community 111 - "Community 111"
Cohesion: 0.12
Nodes (11): normalize_detection(), test_ambiguous_alias_across_companies_is_reported(), test_build_companies_payload_unions_detection_phrases_and_alias_rows(), test_conflict_detector_prefers_database_company_filename_over_conflicting_gemini(), test_empty_value_is_unresolved(), test_normalize_detection_collapses_separators(), test_text_amgeneral_variant_detects_amassurance(), test_unrelated_tokens_never_match() (+3 more)

### Community 112 - "Community 112"
Cohesion: 0.17
Nodes (5): html_to_pdf(), PdfOutputInvalid, PdfRendererUnavailable, test_pdf_generation_smoke(), test_missing_playwright_fails_retryably_without_creating_pdf()

### Community 113 - "Community 113"
Cohesion: 0.20
Nodes (13): idx_users_email, idx_users_role, idx_users_status, users, admin_suggestions, audit_events, idx_notifications_event_type, idx_notifications_recipient_created (+5 more)

### Community 114 - "Community 114"
Cohesion: 0.12
Nodes (7): test_check_has_betterment_peril(), test_condition_1_older_cars_fall_through(), test_condition_1_zero_to_five_years(), test_condition_2_1_qbe_ten_year_rule(), test_condition_2_2_lonpac_stmb_with_peril(), test_condition_2_2_other_insurers_without_peril(), test_condition_2_2_tune_sompo_amassurance_etiqa_with_peril()

### Community 115 - "Community 115"
Cohesion: 0.24
Nodes (8): Db, Rows, staff(), test_evidence_omits_scores_methods_coordinates_and_requires_known_field(), test_source_pages_are_paginated_and_do_not_include_raw_or_engine_details(), test_template_config_requires_published_pinned_revision(), test_template_config_uses_override_only_for_exact_binding(), values()

### Community 116 - "Community 116"
Cohesion: 0.20
Nodes (8): _categorize_vehicle(), get_client_dossiers(), _parse_money(), _resolve_session_client_identity(), _safe_field_val(), test_client_dossier_with_raw_string_fields(), test_categorize_vehicle_types(), test_resolve_session_client_identity_corporate_and_private()

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (6): load_canonical_benefits(), load_company_catalogs(), main(), normalize_phrase(), seed_canonical_benefits(), seed_company_benefit_configs()

### Community 118 - "Community 118"
Cohesion: 0.13
Nodes (14): name, private, scripts, backend, code-map, code-map:check, dev, frontend (+6 more)

### Community 119 - "Community 119"
Cohesion: 0.24
Nodes (7): active_user_and_session(), app_client(), auth_settings(), FakeSession, test_inactive_account_is_rejected_over_http(), test_login_me_logout_and_revoked_session_http_flow(), test_login_with_password_sets_http_only_session_cookie()

### Community 120 - "Community 120"
Cohesion: 0.26
Nodes (9): CaptureDb, company(), Result, special(), template(), test_apply_uses_only_idempotent_inserts_and_ignores_preserve_actions(), test_backfill_plan_is_deterministic_and_never_deletes_or_guesses_special_company(), test_backfill_plan_reports_alias_and_variant_collisions_without_silent_merge() (+1 more)

### Community 121 - "Community 121"
Cohesion: 0.15
Nodes (5): send_login_alert(), dummy_settings(), DummyFakeSession, test_resend_security_alert_dispatches_when_key_present(), test_resend_security_alert_skipped_when_no_api_key()

### Community 122 - "Community 122"
Cohesion: 0.15
Nodes (13): configuredBackendOrigin(), DELETE, dynamic, GET, HEAD, HOP_BY_HOP_HEADERS, OPTIONS, PATCH (+5 more)

### Community 123 - "Community 123"
Cohesion: 0.22
Nodes (8): public.catalog_imports, public.draft_benefit_selections, public.draft_source_line_decisions, public.extraction_benefit_lines, quotation_drafts_catalog_revision_idx, quotation_drafts_company_idx, draft_benefit_selections_plan_idx, quotation_drafts_package_id_idx

### Community 124 - "Community 124"
Cohesion: 0.20
Nodes (7): client(), db_session(), _make_vehicle(), test_api_yoy_stats_and_sync_endpoint(), test_ensure_next_year_renewal_tenures_roll_forward(), test_marketing_comparison_hydrates_previous_policy_baseline(), test_user()

### Community 125 - "Community 125"
Cohesion: 0.21
Nodes (12): generated_pdf_versions, idx_generated_versions_draft_id, idx_generated_versions_uploaded_file_id, idx_generated_pdf_versions_quotation_draft_id, ix_generated_versions_archive_connection_id, ix_generated_versions_storage_expires_at, ix_generated_versions_storage_status, ix_storage_connections_status (+4 more)

### Community 126 - "Community 126"
Cohesion: 0.27
Nodes (8): _admin_user(), FakeDb, _http_client(), _settings(), test_bulk_delete_client_records_calls_service_per_id(), test_bulk_delete_client_records_continues_on_failure(), flaky(), test_bulk_delete_records_moves_each_to_trash()

### Community 127 - "Community 127"
Cohesion: 0.26
Nodes (9): client(), db_session(), make_test_session(), test_covernote_never_in_marketing_comparison(), test_create_custom_vehicle_endpoint(), test_delete_comparison_entry_all_versions(), test_stage_summary_and_tenures_parity(), test_update_fixed_costs_plate_and_brand() (+1 more)

### Community 128 - "Community 128"
Cohesion: 0.28
Nodes (9): client(), db_session(), _make_tenure(), test_bulk_confirm_hit(), test_hit_creates_next_year_empty_renewal(), test_miss_or_discarded_does_not_create_next_year_renewal(), test_record_stage_timestamp_updates_history(), test_revert_hit_deletes_empty_next_year_renewal() (+1 more)

### Community 129 - "Community 129"
Cohesion: 0.21
Nodes (11): DraftField, DraftFieldTable, EvidenceEntry, EvidenceTag, fallbackGroups, FieldEditor, labels, longFields (+3 more)

### Community 131 - "Community 131"
Cohesion: 0.24
Nodes (6): CaptureDb, Rows, test_authenticated_business_roles_share_record_access(), test_session_listing_has_no_owner_predicate_for_staff(), test_staff_trash_listing_has_no_owner_predicate(), user()

### Community 132 - "Community 132"
Cohesion: 0.18
Nodes (11): pipeline, require_approved_plan, require_model_per_phase, trigger, bypass_roles, checks, max_target_seconds, trigger (+3 more)

### Community 133 - "Community 133"
Cohesion: 0.35
Nodes (7): generate(), main(), python_symbols(), rendered_document(), responsibility(), route_symbols(), text_symbols()

### Community 134 - "Community 134"
Cohesion: 0.33
Nodes (9): global_benefit_profile_assets, global_benefit_profiles, idx_business_assets_category, idx_gbpa_asset, idx_gbpa_concept, idx_gbpa_profile, idx_global_benefit_profiles_asset_category, idx_global_benefit_profiles_status (+1 more)

### Community 135 - "Community 135"
Cohesion: 0.29
Nodes (10): benefit_aliases_benefit_idx, benefit_aliases_company_uq, benefit_aliases_global_uq, benefit_aliases_package_uq, benefit_aliases_product_uq, public.benefit_aliases, public.coverage_types, public.segments (+2 more)

### Community 136 - "Community 136"
Cohesion: 0.18
Nodes (8): test_invalid_or_incomplete_typed_values_are_rejected(), test_legacy_special_adapter_preserves_content_without_guessing_company_or_verification(), test_legacy_template_adapter_creates_read_only_revision_without_company_coupling(), test_typed_values_cover_money_percentage_per_day_formula_and_custom(), test_typed_values_preserve_arbitrary_distance_and_unlimited_semantics(), test_v7_revision_and_snapshot_columns_are_part_of_the_orm_contract(), test_v7_schema_is_additive_and_preserves_legacy_tables(), test_v7_schema_migrations_are_additive_and_cover_every_new_table()

### Community 137 - "Community 137"
Cohesion: 0.20
Nodes (9): description, ide_bridges, canonical_agents_dir, canonical_skills_dir, generated_targets, native_auto_discovered, name, portable (+1 more)

### Community 138 - "Community 138"
Cohesion: 0.24
Nodes (3): infer_vehicle_cc_and_type(), load_vehicle_catalog(), seed_vehicle_catalog_to_db()

### Community 139 - "Community 139"
Cohesion: 0.20
Nodes (5): parse_date_safe(), db_session(), test_normalize_plate(), test_parse_date_safe(), test_vehicle_tracking_and_sequential_ownership()

### Community 140 - "Community 140"
Cohesion: 0.47
Nodes (8): cursor_rule_core(), dir_digest(), main(), run_sync(), sync_agents_mirror(), sync_skill_mirror(), sync_text_file(), wrap_cursor_mdc()

### Community 141 - "Community 141"
Cohesion: 0.27
Nodes (7): inter, jetbrainsMono, manrope, metadata, RootLayout(), Providers(), Toaster()

### Community 142 - "Community 142"
Cohesion: 0.36
Nodes (9): auth_login_codes, auth_sessions, idx_auth_login_codes_email_created, idx_auth_login_codes_expires_at, idx_auth_login_codes_user_id, idx_auth_sessions_absolute_expires_at, idx_auth_sessions_idle_expires_at, idx_auth_sessions_revoked_at (+1 more)

### Community 143 - "Community 143"
Cohesion: 0.24
Nodes (9): benefit_catalogs_context_uq, company_aliases_company_idx, insurance_companies_logo_asset_idx, insurance_companies_slug_uq, public.benefit_catalogs, public.company_aliases, public.insurance_product_tiers, public.insurance_products (+1 more)

### Community 145 - "Community 145"
Cohesion: 0.36
Nodes (8): _get_page_source(), test_workspace_has_single_mode_and_package_mode(), test_workspace_is_interactive_flow_without_list_toggle(), test_workspace_manages_packages_bundles_clone_and_revisions(), test_workspace_navigates_the_database_driven_hierarchy(), test_workspace_never_uses_catalog_language_or_hardcodes_business_data(), test_workspace_path_flow_and_segment_tooltip(), test_workspace_uses_the_shared_api_client_only()

### Community 147 - "Community 147"
Cohesion: 0.33
Nodes (4): _norm(), select_all(), select_field(), FieldSelection

### Community 148 - "Community 148"
Cohesion: 0.36
Nodes (6): _default_assets(), default_canvas_elements(), default_template_config(), _element(), test_canvas_renderer_uses_fields(), test_default_template_is_canvas_locked_and_visual()

### Community 149 - "Community 149"
Cohesion: 0.31
Nodes (4): check_markdown_links(), check_registered_docs(), check_state_size(), main()

### Community 150 - "Community 150"
Cohesion: 0.31
Nodes (6): test_company_detection_uses_database_aliases_for_an_arbitrary_new_company(), test_concurrent_requests_use_only_their_own_vehicle_dictionary(), extract(), test_no_company_is_invented_when_database_has_no_matching_alias(), test_vehicle_dictionaries_do_not_leak_between_sequential_requests(), _values()

### Community 151 - "Community 151"
Cohesion: 0.28
Nodes (4): AIContextPage(), loadPrompt(), resetPrompt(), savePrompt()

### Community 152 - "Community 152"
Cohesion: 0.25
Nodes (8): auth_profile_dir, default_workspace, enable_mcp_tools, enable_write_tools, file, recommended_model, veto_scope, 02-falcon-scout

### Community 153 - "Community 153"
Cohesion: 0.25
Nodes (8): default_workspace, enable_mcp_tools, enable_write_tools, escalate_model, file, recommended_model, veto_scope, 09-qa-and-janitor-gate

### Community 154 - "Community 154"
Cohesion: 0.29
Nodes (4): get_or_create_vehicle_tracking(), db_session(), test_plate_assigned_to_previously_unplated_car(), test_unplated_new_car_tracked_by_chassis()

### Community 155 - "Community 155"
Cohesion: 0.29
Nodes (7): default_workspace, enable_subagent_tools, enable_write_tools, file, recommended_model, veto_scope, 01-orchestrator-pm

### Community 156 - "Community 156"
Cohesion: 0.29
Nodes (7): default_workspace, enable_write_tools, file, recommended_model, veto_scope, roles, 05-principal-designer

### Community 157 - "Community 157"
Cohesion: 0.29
Nodes (7): default_workspace, enable_write_tools, escalate_model, file, recommended_model, veto_scope, 07-frontend-ux-lead

### Community 158 - "Community 158"
Cohesion: 0.29
Nodes (7): routing, ast_graph_report, codebase_map, freeze_lock_file, root_contract, startup_index, working_memory

### Community 159 - "Community 159"
Cohesion: 0.57
Nodes (4): WorkerHeartbeat, heartbeat_worker(), _utcnow(), worker_readiness()

### Community 161 - "Community 161"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, start, test:e2e, test:e2e:chromium

### Community 162 - "Community 162"
Cohesion: 0.38
Nodes (6): demoValues, PackageConfig, PreviewCard(), TemplateConfig, templateName(), TemplatePreview()

### Community 163 - "Community 163"
Cohesion: 0.52
Nodes (6): idx_our_special_variants_special_id, idx_our_special_variants_status, idx_our_specials_category, idx_our_specials_status, our_special_variants, our_specials

### Community 166 - "Community 166"
Cohesion: 0.33
Nodes (6): default_workspace, enable_write_tools, file, recommended_model, veto_scope, 03-mentor-architect

### Community 167 - "Community 167"
Cohesion: 0.33
Nodes (6): default_workspace, enable_write_tools, file, recommended_model, veto_scope, 04-security-auditor

### Community 168 - "Community 168"
Cohesion: 0.33
Nodes (6): default_workspace, enable_write_tools, file, recommended_model, veto_scope, 06-backend-ledger-lead

### Community 169 - "Community 169"
Cohesion: 0.33
Nodes (6): default_workspace, enable_write_tools, file, recommended_model, veto_scope, 08-ai-extraction-lead

### Community 173 - "Community 173"
Cohesion: 0.33
Nodes (3): is_same_customer(), _names_match(), test_plate_validation_and_customer_matching()

### Community 174 - "Community 174"
Cohesion: 0.47
Nodes (3): bootstrap(), main(), render_root_agents_stub()

### Community 175 - "Community 175"
Cohesion: 0.33
Nodes (4): BACKEND, FRONTEND, path, PYTHON

### Community 180 - "Community 180"
Cohesion: 0.40
Nodes (3): migration_checksums(), _normalize_line_endings(), test_mixed_cr_crlf_and_lf_line_endings_normalize_identically()

### Community 181 - "Community 181"
Cohesion: 0.60
Nodes (3): main(), new_id(), utcnow()

### Community 182 - "Community 182"
Cohesion: 0.60
Nodes (4): DEBIAN_FRONTEND, log(), setup-vps.sh script, warn()

### Community 183 - "Community 183"
Cohesion: 0.50
Nodes (3): client_records_archived_at_idx, public.record_saved_views, record_saved_views_owner_idx

### Community 184 - "Community 184"
Cohesion: 0.70
Nodes (4): gemini_api_call_logs, ix_gemini_call_logs_acc_date, ix_gemini_call_logs_created_at, ix_gemini_call_logs_local_date

### Community 188 - "Community 188"
Cohesion: 0.83
Nodes (3): idx_road_tax_rules_status, idx_road_tax_rules_vehicle, road_tax_rules

### Community 189 - "Community 189"
Cohesion: 0.67
Nodes (3): public.rate_limit_buckets, rate_limit_buckets_blocked_until_idx, users_single_primary_admin

### Community 190 - "Community 190"
Cohesion: 0.83
Nodes (3): benefit_card_presets, idx_benefit_card_presets_custom, uq_single_default_benefit_card_preset

## Knowledge Gaps
- **1 isolated node(s):** `DEBIAN_FRONTEND`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 1951 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **80 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Session` connect `Community 7` to `Community 0`, `Community 128`, `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 8`, `Community 10`, `Community 138`, `Community 12`, `Community 139`, `Community 14`, `Community 16`, `Community 18`, `Community 20`, `Community 22`, `Community 25`, `Community 154`, `Community 30`, `Community 31`, `Community 32`, `Community 160`, `Community 38`, `Community 39`, `Community 40`, `Community 42`, `Community 47`, `Community 48`, `Community 50`, `Community 53`, `Community 56`, `Community 57`, `Community 58`, `Community 59`, `Community 60`, `Community 68`, `Community 69`, `Community 79`, `Community 82`, `Community 85`, `Community 87`, `Community 89`, `Community 98`, `Community 102`, `Community 115`, `Community 116`, `Community 124`, `Community 127`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Are the 127 inferred relationships involving `Session` (e.g. with `convert_session_document_type()` and `link_tenure_covernote()`) actually correct?**
  _`Session` has 127 INFERRED edges - model-reasoned connections that need verification._
- **What connects `DEBIAN_FRONTEND` to the rest of the system?**
  _1 weakly-connected nodes found - possible missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.062156842432404436 - nodes in this community are weakly interconnected._
- **Why does `User` connect `Community 8` to `Community 0`, `Community 128`, `Community 2`, `Community 4`, `Community 7`, `Community 10`, `Community 11`, `Community 12`, `Community 14`, `Community 16`, `Community 18`, `Community 20`, `Community 21`, `Community 22`, `Community 28`, `Community 29`, `Community 30`, `Community 31`, `Community 32`, `Community 33`, `Community 38`, `Community 39`, `Community 47`, `Community 49`, `Community 50`, `Community 53`, `Community 57`, `Community 58`, `Community 59`, `Community 60`, `Community 66`, `Community 69`, `Community 71`, `Community 75`, `Community 76`, `Community 81`, `Community 82`, `Community 92`, `Community 105`, `Community 119`, `Community 124`, `Community 126`, `Community 127`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Are the 439 inferred relationships involving `User` (e.g. with `AuthContext` and `current_user()`) actually correct?**
  _`User` has 439 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.027901131126937578 - nodes in this community are weakly interconnected._
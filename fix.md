
Now I have all the data I need. Let me compile the comprehensive report.

---

## Comprehensive Bug/Issue Scan Report for Risklocker Codebase

---

### 1. SILENT ERROR SWALLOWING (`except Exception` without logging)

**Severity: Medium to High**

| #    | File                                                                                          | Line    | Issue                                                                                                                                                                                                                                                                                                  |
| ---- | --------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1.1  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\extraction\ocr.py`            | 19-20   | `except Exception: pass` — catches `import paddleocr` failure silently. Should import `logging` and log a warning like "PaddleOCR not available".                                                                                                                                               |
| 1.2  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\extraction\layout.py`         | 49-50   | `except Exception: warnings.append(...)` — catches `import cv2` failure with no logging. Should log the actual exception message.                                                                                                                                                                 |
| 1.3  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\upload_service.py`   | 172-173 | `except Exception: result = _cannot_read_result()` — inside the file processing loop, a broad `except Exception` catches any extraction failure (including genuine runtime errors like `AttributeError`, `KeyError`) with zero logging. Should at minimum log the exception type and message. |
| 1.4  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\upload_service.py`   | 200-207 | `except Exception: upload_failures.append(...)` — catches all remaining upload errors (e.g. `IntegrityError`, `DBAPIError`) with no logging, returning a generic "could not be prepared" message.                                                                                               |
| 1.5  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\upload_service.py`   | 196-197 | `except StorageError: pass` — removes already-uploaded bytes on failure but swallows the deletion error.                                                                                                                                                                                            |
| 1.6  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\pdf_service.py`      | 105-109 | `except Exception: storage.delete_pdf(...)` then `raise` — catches a commit failure, attempts cleanup, then re-raises. The deletion failure is suppressed with `except StorageError: pass`. Should at minimum log the commit failure before re-raising.                                         |
| 1.7  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\review_service.py`   | 281-282 | `except Exception: pass` — deletes PDF from storage during trash purge but swallows all storage deletion errors silently.                                                                                                                                                                           |
| 1.8  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\review_service.py`   | 288-289 | `except Exception: pass` — same as above but for generated version PDFs during purge.                                                                                                                                                                                                               |
| 1.9  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\road_tax_service.py` | 24-25   | `except Exception: return None` — `_eval_formula()` catches all eval errors silently. Should at minimum narrow the except clause to `(ValueError, TypeError, SyntaxError, NameError)`.                                                                                                          |
| 1.10 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\system_checks.py`    | 31-32   | `except Exception: pass` — `playwright_ready()` catches all exceptions from launching Playwright and returns `False` silently.                                                                                                                                                                  |
| 1.11 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\system_checks.py`    | 104-105 | `except Exception:` — DB health check catches all exceptions without logging the actual error.                                                                                                                                                                                                      |
| 1.12 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\api\routes.py`                | 714     | `except Exception as exc: errors.append(...)` — CSV import catches all exceptions but only appends an error message. Does not scale to bulk operations well; a single failed row should not block the transaction but the exception type should be more specific.                                   |

---

### 2. `console.error` / `console.log` LEFT IN PRODUCTION FRONTEND CODE

**Severity: Low**

| #   | File                                                                         | Line | Issue                                                                                                                                                                   |
| --- | ---------------------------------------------------------------------------- | ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2.1 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\lib\api.ts` | 19   | `console.error(`[api] network error: ${path}`, err);` — error logging in the API client. Acceptable for debugging but can leak internal paths in production.       |
| 2.2 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\lib\api.ts` | 27   | `console.error(`[api] ${response.status} ${path}: ${message}`);` — same as above. Both are in the shared `api()` helper, so they log on every frontend API call. |

No `console.log` (without `error`/`warn`) was found in frontend `.ts`/`.tsx` files.

---

### 3. MISSING IMPORTS

**Severity: High**

| #             | File                                                                           | Line          | Issue                                                                                                                                                                                                                                                                                                                                                                                                          |
| ------------- | ------------------------------------------------------------------------------ | ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **3.1** | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\api\routes.py` | **602** | **`Path` is used in `isinstance(resolved, Path)` but is NOT imported in this function's scope.** The only import of `Path` in routes.py is a local import inside `draft_preview_png()` at line 341. The `template_asset_file()` function at line 590 uses `Path` without importing it. **This will raise `NameError: name 'Path' is not defined` at runtime when the route is hit.** |
| 3.2           | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\api\routes.py` | 340           | The local import`from pathlib import Path` inside `draft_preview_png()` is technically fine but inconsistent — it shows that other functions already forget to import it.                                                                                                                                                                                                                                 |

**All other service files checked:** `upload_service.py`, `review_service.py`, `pdf_service.py`, `admin_service.py`, `auth_service.py`, `session_service.py`, `client_record_service.py`, `notification_service.py`, `road_tax_service.py`, `storage_retention.py`, `template_assets.py`, `template_config.py`, `system_checks.py`, `document_security.py`, `file_validation.py` — all have correct `select` imports where needed. No other missing imports found.

---

### 4. `TypeError` RISKS (`.get()` without defaults, unsafe indexing)

**Severity: Medium**

| #   | File                                                                                               | Line  | Issue                                                                                                                                                                                                                                                                             |
| --- | -------------------------------------------------------------------------------------------------- | ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 4.1 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\upload_service.py`        | 115   | `detected = (draft_data.get("fields") or {}).get("insurance_company", {}).get("value")` — If `draft_data.get("fields")` returns a non-dict truthy value (though unlikely here), the chained `.get()` would fail. Low risk but the pattern is fragile.                      |
| 4.2 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\client_record_service.py` | 17-19 | `f = draft_fields.get(key, {})` / `val = f.get("value")` — If `draft_fields.get(key)` returns `None` instead of a missing-key default `{}`, this breaks. However, since the default is `{}`, this is safe.                                                           |
| 4.3 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\admin_service.py`         | 25    | `company = InsuranceCompany(name=payload["name"], ...)` — No `.get()` with default; direct dict key access. Will raise `KeyError` if `"name"` is missing. The Pydantic schema should enforce this, but at the service layer this is unsafe if called without validation. |
| 4.4 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\api\routes.py`                     | 756   | `brand_name = db.get(VehicleBrand, m.brand_id).name if m.brand_id else ""` — If `db.get()` returns `None` (brand_id exists but brand was deleted), calling `.name` on `None` will raise `AttributeError`.                                                            |
| 4.5 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\template_config.py`       | 197   | `max(int(base.get("version") or 1), 2)` — `base.get("version")` returns `None` when missing, but if it returns `int 0` (falsy), it gets replaced by `1`. Minor logic issue, not a crash.                                                                               |

---

### 5. INCONSISTENT API PATHS (Frontend vs Backend route mismatches)

**Severity: Medium**

| #   | Issue                                                    | Details                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| --- | -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 5.1 | **`/admin/` prefix used inconsistently**         | Backend routes use`/admin/` for: companies, templates, template-assets, our-specials, our-special-variants, dictionaries, extraction-settings, road-tax-rules, storage. But frontend pages live at different URL segments: `/builder/`, `/settings/`, `/admin/` (redirects only). The **backend** APIs are consistent with `router` prefixing, but there's no centralized route prefix — each route hardcodes `/admin/`. Not a breakage, but a maintenance risk. |
| 5.2 | **Frontend admin redirect pages vs. actual pages** | `frontend\src\app\admin\` contains only redirect stubs (`admin/page.tsx` -> `/settings/users`, `admin/benefits/page.tsx` -> `/builder/our-specials`, etc.). The actual admin functionality lives under `/builder/` and `/settings/`. This is intentional refactoring but leaves ghost admin routes that could confuse developers.                                                                                                                                     |
| 5.3 | **No actual mismatches found**                     | All frontend`api()` calls with `/admin/` paths match backend route definitions in `routes.py`. No 404-causing mismatches detected.                                                                                                                                                                                                                                                                                                                                            |

---

### 6. `globals.css` CSS CLASS SPECIFICITY ISSUES (`.rl-input` padding vs. Tailwind)

**Severity: Low**

| #   | File                                                                              | Line   | Issue                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| --- | --------------------------------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 6.1 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\globals.css` | 94-102 | `.rl-input` sets `padding: 8px 10px` with a class selector (specificity 0,1,0). Tailwind utility classes like `pl-10` (used on `login\page.tsx` line 73, 89, 90) use single-class selectors (specificity 0,1,0). Since both have identical specificity, **source order determines the winner.** Tailwind utilities appear after `globals.css` in the compiled CSS if `@tailwind utilities` is processed after the custom CSS (it is — line 3 of `globals.css`). So **Tailwind padding utilities (like `pl-10`) WILL override `.rl-input`'s padding correctly.** No actual conflict in practice, but this is a fragile implicit ordering dependency. |
| 6.2 | Same file                                                                         | 57-68  | `.rl-button` with `padding: 9px 14px` — same pattern. Tailwind padding utilities would override if used together.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |

---

### 7. `any` TYPE USAGE IN FRONTEND TYPESCRIPT

**Severity: Low to Medium**

| #   | File                                                                                                             | Line     | Issue                                                                                                                                                                                  |
| --- | ---------------------------------------------------------------------------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 7.1 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\client-records\page.tsx`                    | 239      | `{(record as any)[key] \|\| "-"}` — Casts `record` to `any` to do dynamic key access. Should type `key` as `keyof ClientRecord` and use `record[key]` with proper typing.   |
| 7.2 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\settings\extraction\road-tax\page.tsx`      | 51       | `const payload: Record<string, any> = {...}` — Uses `any` for values. Should be typed with proper interfaces.                                                                     |
| 7.3 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\settings\extraction\field-aliases\page.tsx` | 24       | `vehicle_brands: any[]; vehicle_models: any[]` — API response typed with `any[]` instead of proper Brand/Model types.                                                             |
| 7.4 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\sessions\[id]\preview\page.tsx`             | 227, 236 | `textAlign: (el.style?.textAlign \|\| "left") as any` — Casting to `any` for CSS `textAlign` property. Should use `as React.CSSProperties['textAlign']` or a proper union type. |
| 7.5 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\builder\templates\[id]\builder\page.tsx`    | 660      | `textAlign: (style.textAlign \|\| "left") as React.CSSProperties["textAlign"]` — This one is properly typed (not `any`), included for contrast.                                     |

---

### 8. `as` TYPE ASSERTIONS THAT MIGHT HIDE ERRORS

**Severity: Low**

| #   | File                                                                                               | Line | Issue                                                                                                                                                                          |
| --- | -------------------------------------------------------------------------------------------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 8.1 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\lib\api.ts`                       | 22   | `return undefined as T;` — Returns `undefined` cast as `T`. Callers must handle the possibility of `undefined` return on 204 status, but TypeScript won't enforce it. |
| 8.2 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\lib\api.ts`                       | 30   | `return payload as T;` — Generic cast without runtime validation. The shape of `payload` could differ from `T` if the backend returns unexpected JSON.                  |
| 8.3 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\lib\auth.ts`                      | 34   | `cachedUser = data as User;` — Assumes the cached JSON matches the `User` type shape. No runtime validation.                                                              |
| 8.4 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\components\draft-field-table.tsx` | 109  | `e.target as Node` — Cast used in a `contains()` check. Safe in practice but masks that `Event.target` could theoretically be `null`.                                 |

---

### 9. FRONTEND PAGES MISSING `.catch()` ON API CALLS

**Severity: Medium**

These are API calls that are NOT inside a `try/catch` and do NOT have `.catch()` chained — meaning an unhandled promise rejection could occur:

| #    | File                                                                                                             | Line(s)        | Method/Call                                                                                                        | Risk                                                                                                                                                   |
| ---- | ---------------------------------------------------------------------------------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 9.1  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\inbox\page.tsx`                             | 52             | `markOneRead()` — `api(...)` inside `try` but no `catch` block (only `finally`)                         | If`/notifications/{id}/read` returns non-OK (e.g. 404), the `api()` helper throws. Without `catch`, the error propagates as unhandled rejection. |
| 9.2  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\inbox\page.tsx`                             | 68             | `markAllRead()` — same pattern: `try`/`finally` only, no `catch`                                          | Same risk as above.                                                                                                                                    |
| 9.3  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\review\[id]\page.tsx`                       | 88-101         | `save()` — `api(...)` not wrapped in try/catch, no `.catch()`                                               | Called from button`onClick`; if the PATCH fails, the error is unhandled.                                                                             |
| 9.4  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\review\[id]\page.tsx`                       | 106            | `generate()` — `api(...)` not wrapped in try/catch, no `.catch()`                                           | If generate fails, unhandled rejection.                                                                                                                |
| 9.5  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\batches\[id]\page.tsx`                      | 31-32          | `generateReady()` — two `api()` calls without try/catch                                                       | If either call fails, error goes unhandled.                                                                                                            |
| 9.6  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\settings\users\page.tsx`                    | 29             | `createUser()` — `api(...)` no try/catch                                                                      | If user creation fails, unhandled rejection.                                                                                                           |
| 9.7  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\settings\extraction\vehicles\page.tsx`      | 34, 38, 43, 48 | `createBrand()`, `createModel()`, `removeBrand()`, `removeModel()` — `api(...)` calls without try/catch | Four functions with unguarded API calls.                                                                                                               |
| 9.8  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\settings\extraction\road-tax\page.tsx`      | 58, 63         | `save()`, `remove()` — `api(...)` no try/catch                                                              | Two functions without error handling.                                                                                                                  |
| 9.9  | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\settings\extraction\field-aliases\page.tsx` | 32, 44, 55     | `create()`, `saveEdit()`, `remove()` — `api(...)` no try/catch                                            | Three functions without error handling.                                                                                                                |
| 9.10 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\builder\companies\page.tsx`                 | 57, 74, 95     | `saveEdit()`, `toggleStatus()`, `createCompany()` — `api(...)` no try/catch                               | `deleteCompany()` (line 84-90) DOES have try/catch, but the others don't.                                                                            |
| 9.11 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\builder\our-specials\page.tsx`              | 194, 238       | `createSpecial()`, `saveVariant()` — `api(...)` no try/catch                                                | `deleteSpecial()` and `deleteVariant()` have try/catch (good). The create/save functions don't.                                                    |
| 9.12 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\builder\templates\page.tsx`                 | 47, 62         | `createTemplate()`, `copyTemplate()` — `api(...)` no try/catch                                              | Both functions call API without error handling.                                                                                                        |
| 9.13 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\settings\storage\page.tsx`                  | 45             | `purge()` — `api(...)` no try/catch                                                                           | Purge API call unguarded.                                                                                                                              |

**Good pages** (all have `.catch()`): `trash`, `history`, `client-records`, `system-checks`, `sessions`, `sessions/[id]/review`, `sessions/[id]/preview`, `builder/templates/[id]/builder`.

---

### 10. HARDCODED VALUES THAT SHOULD BE CONFIGURABLE

**Severity: Low to Medium**

| #    | File                                                                                            | Line | Value                                             | Issue                                                                                                                            |
| ---- | ----------------------------------------------------------------------------------------------- | ---- | ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| 10.1 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\services\upload_service.py`     | 130  | `if len(files) > 50`                            | Max upload files (50) is hardcoded. Should come from`Settings`.                                                                |
| 10.2 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\upload\page.tsx`           | 51   | `"Up to 50 files, 1 MB each"`                   | Frontend hardcodes limits that should match backend config. If`max_upload_bytes` changes in settings, this text becomes stale. |
| 10.3 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\trash\page.tsx`            | 33   | `"14 days"`                                     | Trash retention period is hardcoded in UI. Backend uses`settings.trash_retention_days`. These can diverge.                     |
| 10.4 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\frontend\src\app\settings\storage\page.tsx` | 81   | `{status?.supabase.retention_days ?? 30}`       | Fallback value`30` days hardcoded in frontend as default retention. If backend default changes, UI fallback will be wrong.     |
| 10.5 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\core\config.py`                 | 109  | `"http://localhost:3000,http://127.0.0.1:3000"` | Default CORS origins are hardcoded for local dev. No issue in dev, but environment variable should always be set in non-local.   |

---

### 11. `pytest.ini` — DB-DEPENDENT TEST EXCLUSION

**Severity: Low**

| #    | File                                                            | Issue                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ---- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 11.1 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\pytest.ini` | **No markers or exclusions are defined for DB-dependent tests.** The file only has test discovery paths. Looking at the test files (`test_companies_api.py`, `test_auth_http.py`, `test_hardening.py`, etc.), they all appear to rely on a running database. There are no `pytest.mark.skip` or `pytest.mark.skipif` markers to allow running tests without a DB. No `testpaths` exclusion for integration tests. **This means ALL tests will fail if there's no database connection, and there's no way to run only unit tests (`-m "not db"` or similar).** |

---

### 12. REMAINING `benefit_options` / OLD PACKAGE/CARD REFERENCES

**Severity: Low (Migration Artifacts)**

| #    | File                                                                                       | Line | Issue                                                                                                                                                                                                                                                        |
| ---- | ------------------------------------------------------------------------------------------ | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 12.1 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\db\init_db.py`             | 96   | `db.execute(text("UPDATE benefit_options SET insurance_company_id = NULL, template_id = NULL"))` — Still references the old `benefit_options` table. This code should be removed or migrated to clean up after all environments have run migration 013. |
| 12.2 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\migrations\003_full_app_schema.sql`    | 31   | `CREATE TABLE IF NOT EXISTS benefit_options (...)` — Old schema still exists in migration history. This is acceptable for migration tracking but the table definition remains.                                                                            |
| 12.3 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\migrations\013_our_specials.sql`       | 2-5  | Migration file that deprecates`benefit_options` — this is correct (it's the migration itself).                                                                                                                                                            |
| 12.4 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\migrations\007_lock_down_data_api.sql` | 12   | References`'benefit_options'` in RLS policy — now unnecessary since the table is deprecated.                                                                                                                                                              |
| 12.5 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\docs\generated\CODEBASE-MAP.md`        | 115  | Documents`benefit_options` as still present — the code map needs updating.                                                                                                                                                                                |
| 12.6 | `C:\Users\user\Desktop\dev\quote\quote_risklocker\prompts.md`                            | 91   | Documents`benefit_options` migration preserving row — informational, not a bug.                                                                                                                                                                           |

**No frontend references** to `benefit_options`, `package_card`, or `package_options` were found. The old `/admin/benefits/` frontend route is a redirect (`admin/benefits/page.tsx` -> `/builder/our-specials`) — correct.

---

## SUMMARY

| Category                            | Count                                            | Severity         |
| ----------------------------------- | ------------------------------------------------ | ---------------- |
| 1. Silent exception swallowing      | 12                                               | Medium-High      |
| 2. console.error in frontend        | 2                                                | Low              |
| 3. Missing imports                  | **1 critical** (`Path` in routes.py:602) | **High**   |
| 4. TypeError risks                  | 5                                                | Medium           |
| 5. API path inconsistencies         | 0 mismatches, 1 maintenance note                 | Low              |
| 6. CSS specificity conflicts        | 0 actual conflicts, 1 fragility note             | Low              |
| 7.`any` type usage                | 5                                                | Low-Medium       |
| 8.`as` assertions                 | 4                                                | Low              |
| 9. Missing`.catch()` on API calls | **13 functions across 8 pages**            | **Medium** |
| 10. Hardcoded values                | 5                                                | Low-Medium       |
| 11. Pytest DB exclusion             | 1 (no markers)                                   | Low              |
| 12. Old benefit_options references  | 6 (migration artifacts)                          | Low              |

### CRITICAL ISSUE

The **most urgent finding** is **#3.1**: `C:\Users\user\Desktop\dev\quote\quote_risklocker\backend\app\api\routes.py` line 602 uses `Path` (from `pathlib`) without importing it in the `template_asset_file()` function scope. This will cause a `NameError` at runtime when any user hits the `/template-assets/{asset_id}` endpoint and `resolve_template_asset` returns a `Path` object. **Fix: Add `from pathlib import Path` inside the function or at the module level.





**

## Critical flaws found

### 🔴 CRITICAL — Will crash at runtime

**`routes.py:602` — `Path` used without import**

* `template_asset_file()` function uses `Path` but never imports it. When the `/template-assets/{id}` endpoint is hit and `resolve_template_asset` returns a file path, it crashes with `NameError: name 'Path' is not defined`.

### 🟠 HIGH — Unhandled promise rejections (13 functions across 8 pages)

API calls without `.catch()` or `try/catch` — if the backend returns an error, these become silent failures:

| Page                                | Functions without error handling                                           |
| ----------------------------------- | -------------------------------------------------------------------------- |
| `review/[id]/page.tsx`            | `save()`, `generate()`                                                 |
| `inbox/page.tsx`                  | `markOneRead()`, `markAllRead()`                                       |
| `batches/[id]/page.tsx`           | `generateReady()`                                                        |
| `builder/companies/page.tsx`      | `saveEdit()`, `toggleStatus()`, `createCompany()`                    |
| `builder/our-specials/page.tsx`   | `createSpecial()`, `saveVariant()`                                     |
| `builder/templates/page.tsx`      | `createTemplate()`, `copyTemplate()`                                   |
| `settings/field-aliases/page.tsx` | `create()`, `saveEdit()`, `remove()`                                 |
| `settings/vehicles/page.tsx`      | `createBrand()`, `createModel()`, `removeBrand()`, `removeModel()` |
| `settings/road-tax/page.tsx`      | `save()`, `remove()`                                                   |
| `settings/users/page.tsx`         | `createUser()`                                                           |
| `settings/storage/page.tsx`       | `purge()`                                                                |

### 🟡 MEDIUM — Silent error swallowing (12 locations)

`except Exception: pass` or `except Exception` with no logging in:

* `extraction/ocr.py`, `layout.py` — import failures swallowed
* `upload_service.py` — extraction failures swallowed
* `review_service.py` — storage deletion failures in trash purge
* `road_tax_service.py` — formula eval failures returned as None
* `system_checks.py` — Playwright/DB health check failures

---

## Priority fix plan

**Fix 1** (critical — 1 line): Add `from pathlib import Path` to `routes.py`

**Fix 2** (high — ~20 lines): Wrap 13 unhandled API calls in `try/catch` across 8 frontend pages. Each one just needs `try { await api(...) } catch (e) { setError(...) }` pattern.

**Fix 3** (medium — ~10 lines): Replace `except Exception: pass` with `except Exception: print(f"[WARN] ...")` in the 12 service locations.

**Fix 4** (low — CSS): `.rl-input` padding vs Tailwind `pl-10` — confirmed not actually broken but fragile. Can add `!important` to be safe.

**Fix 5** (low — `any` types): 5 frontend files use `any` type assertions — cosmetic cleanup.

Total: ~35 lines across 12 files. Ready for build mode.

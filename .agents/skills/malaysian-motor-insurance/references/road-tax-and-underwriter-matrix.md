# Malaysian Road Tax (ICE + 2026 EV) & Underwriter Decision Matrix

## 1. Progressive JPJ ICE Road Tax Safeguard (`F-06`)
- Always validate continuity across bracket thresholds (`1600 -> 1601`, `1800 -> 1801`, `2000 -> 2001`, `2500 -> 2501`, `3000 -> 3001`): Peninsular Private Saloon at `2501cc` MUST remain monotonic (`>= RM 880`, never dropping to `RM 842.50`).
- Zero `eval()` formula execution (`F-03`): store explicit `(min_cc, max_cc, base_myr, per_cc_myr)` rows or pure Python `Decimal` tables.

## 2. 2026 ZEV (EV) Road Tax Normalization
- Normalize incoming power strings: `"150 kW"`, `"150kW"`, `"150000 W"` -> `Decimal("150")` kW (`if >= 1000 W divide by 1000`).
- Identical Private & Company passenger car EV slab schedule effective 1 Jan 2026 (`RM 20` starting block; `RM 305` for `220 kW`, `RM 335` for `230 kW`, incrementing cleanly by `10 kW` steps), with `50%` East Malaysia / Labuan discount above `100 kW`; EV motorcycles `RM 2`–`RM 42`.

## 3. Underwriter Edge Rules (7+ Insurers)
| Benefit / Rule | Etiqa | STMB / Takaful MY | Lonpac | QBE | AmAssurance | Berjaya Sompo | Tune Protect |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Betterment Waiver** | Add-on (<=15 yr) | Add-on (<=10 yr) | Add-on (<=10 yr) | Default `0 RM` (<=10 yr) | Add-on (<=15 yr) | Add-on (<=15 yr) | Add-on (<=15 yr) |
| **Betterment Scope** | Private Car Comprehensive ONLY (ICE & EV); NEVER motorcycles/commercial | same | same | same | same | same | same |
| **Towing Parser (`F-05`)** | Structured tokens ONLY | NEVER `"4" in text`; exact tokens + preserve overrides | same | same | same | same | same |


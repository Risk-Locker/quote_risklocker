# References and Assets

## Runtime Template Assets

- The owner-provided v7 source set is `assets/benefits/` and `assets/Company logos/`.
- Filenames drive initial concept/brand matching. Intake validates signatures, MIME, dimensions, transparency, decompressed size, and content hashes; visual inspection is reserved for failed or ambiguous files.
- Preserve originals and produce aspect-preserving, non-cropped runtime derivatives. Unused artwork remains unassigned and must not create catalog benefits.
- Logo count is current data, never an application constraint. A logo without verified product information creates an empty/unverified catalog rather than invented defaults.
- Retire legacy artwork from active libraries only after reference analysis. Referenced blobs remain compatibility-only until safe to delete.

The active v7 Asset Library uses authorized `business_assets` records and content-addressed private storage/derivatives. The legacy `backend/app/assets/template_assets/` folder is compatibility-only while referenced historical templates are converted; its contents must not be listed in the active Builder.

- The catalog accepts PNG, JPG, JPEG, and SVG files.
- Keep only accepted runtime formats in this deployed directory. Unsupported authoring files belong in the private reference archive, not alongside runtime assets.
- Assets can represent logos, payment/all-driver boxes, backgrounds, insurer marks, icons, and bilingual benefit cards.
- A published master template is revisioned database configuration, not a customer PDF. Session layout overrides never mutate it.
- The unused `clcik for cover.wdp` and `E-hailing.wdp` files were removed on 2026-07-14 because the asset service intentionally ignores `.wdp` files.

## Private Development References

Customer and process examples are outside this repository at:

`C:\Users\user\Desktop\dev\quote\risklocker-reference-archive\process`

Additional former sample uploads are at:

`C:\Users\user\Desktop\dev\quote\risklocker-reference-archive\samples`

These are private development references only. Runtime code and automated tests must never depend on them. Add only anonymized, deterministic regression fixtures under `tests/fixtures/`.

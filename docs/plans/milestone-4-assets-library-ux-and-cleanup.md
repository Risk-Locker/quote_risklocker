# Milestone 4: Assets Library UX (Sticky Toolbar, Inspector Modal & Cleanup) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` and `systematic-debugging` to execute this plan cleanly. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Assets Library in `/builder/assets` into a polished, S3-style asset manager: make the filter/sort toolbar sticky during scrolling, add a rich Asset Details Modal showing upload timestamps, file size, dimensions, and one-click URL copy, and purge dummy "test logo" debris from `business_assets`.

**Architecture:**
1. **Sticky Header Layout (`page.tsx:860-960`):**
   Wrap the search/filter/sort container in `sticky top-0 z-20 bg-[var(--rl-surface)]/95 backdrop-blur-md border-b border-[var(--rl-border)] p-3.5 shadow-xs` so users never lose context when scrolling through the asset grid.
2. **S3-Style Asset Details Modal (`AssetDetailsModal.tsx`):**
   Clicking any asset card (outside of multi-select mode) opens a full inspector:
   - High-resolution visual preview with transparent checkerboard
   - Metadata grid: Upload Timestamp, File Size, Dimensions, Content-Type, Transparency, Category, and Mapped Concepts
   - Quick action buttons: Copy Image URL (with green copied toast), Download File, Rename/Edit, and Delete
3. **Database Asset Cleanup Script / Migration:**
   Safely remove dummy test assets matching `Test Label` and `Test Insurer Logo%` while preserving all canonical insurer and brand logos.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS, `@phosphor-icons/react`.

---

### Task 1: Sticky Toolbar & Asset Details Modal in Frontend

**Files:**
- Create: frontend/src/app/builder/assets/components/AssetDetailsModal.tsx
- Modify: `frontend/src/app/builder/assets/page.tsx:860-1150`

- [ ] **Step 1: Create `AssetDetailsModal.tsx`**
Build the inspection modal showing:
1. Preview image with zoom-on-hover.
2. Detailed metadata table: ID, Key, Uploaded At, File Size (`formatBytes`), Resolution (`W × H`), MIME Type, Transparency badge.
3. One-click "Copy Image URL" button with clipboard write.
4. "Download" and "Delete" actions.

- [ ] **Step 2: Update `frontend/src/app/builder/assets/page.tsx`**
1. Make search & filter toolbar `sticky top-0 z-20 bg-white/95 backdrop-blur-sm shadow-xs`.
2. Wire `onClick` on asset card to open `AssetDetailsModal` when not in multi-select mode.

- [ ] **Step 3: Run TypeScript compiler**

Run: `cd frontend; npx tsc --noEmit`
Expected: PASS with 0 errors

---

### Task 2: Clean Up Test Asset Debris in Backend

**Files:**
- Create: `scripts/cleanup_dummy_test_assets.py`

- [ ] **Step 4: Write cleanup script**

```python
from app.db.session import SessionLocal
from app.models.tables import BusinessAsset

def cleanup_test_assets():
    db = SessionLocal()
    try:
        test_assets = db.query(BusinessAsset).filter(
            BusinessAsset.label.ilike("Test Label%") | 
            BusinessAsset.label.ilike("Test Insurer Logo%") | 
            BusinessAsset.label.ilike("Test Logo%")
        ).all()
        print(f"Found {len(test_assets)} dummy test assets to clean up.")
        for a in test_assets:
            db.delete(a)
        db.commit()
        print("Cleanup completed successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_test_assets()
```

- [ ] **Step 5: Run cleanup script**

Run: `.\.venv\Scripts\python.exe scripts/cleanup_dummy_test_assets.py`
Expected: Successfully deletes dummy test assets.

- [ ] **Step 6: Commit Milestone 4 changes**

```bash
git add frontend/src/app/builder/assets/ scripts/cleanup_dummy_test_assets.py
git commit -m "feat(assets): add sticky toolbar, S3-style asset inspector modal, and clean test debris"
```

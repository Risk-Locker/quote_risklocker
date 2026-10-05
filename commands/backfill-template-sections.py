"""Backfill Template Sections.

Iterates over all OutputTemplateConfig records in the database.
If fixed_fields lacks 'sections', extracts structured sections and compiles
canonical modular container canvas elements into fixed_fields.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

# Add backend directory to path
backend_path = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(backend_path))

from sqlalchemy.orm.attributes import flag_modified
from app.db.session import SessionLocal
from app.models.tables import OutputTemplateConfig
from app.services.template_section_compiler import (
    compile_sections_to_canvas,
    extract_sections_from_canvas,
)


def backfill_all_templates() -> None:
    db = SessionLocal()
    try:
        templates = db.query(OutputTemplateConfig).all()
        print(f"Found {len(templates)} templates in database.")

        updated_count = 0
        for t in templates:
            ff = dict(t.fixed_fields or {})
            canvas = dict(ff.get("canvas") or {})
            elems = list(canvas.get("elements") or [])

            # If template has elements but lacks sections, or needs compile
            sections = ff.get("sections")
            if not sections:
                sections = extract_sections_from_canvas(elems)
                ff["sections"] = sections

            compiled_elems = compile_sections_to_canvas(sections, elems)
            canvas["elements"] = compiled_elems
            ff["canvas"] = canvas
            t.fixed_fields = copy.deepcopy(ff) if 'copy' in locals() else dict(ff)
            flag_modified(t, "fixed_fields")
            updated_count += 1
            print(f"  [OK] Backfilled '{t.name}' ({t.id}) with {len(compiled_elems)} container elements.")

        db.commit()
        print(f"Successfully backfilled and committed {updated_count} templates.")
    finally:
        db.close()


if __name__ == "__main__":
    backfill_all_templates()

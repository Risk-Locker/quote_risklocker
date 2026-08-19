"""API error helpers."""

from __future__ import annotations

import re
from traceback import format_exc

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette import status


class AppError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# Maps DB constraint name fragments → friendly messages.
_CONSTRAINT_MESSAGES: list[tuple[str, str]] = [
    ("uq_benefit_concept_key", "A Global Benefit with this key already exists."),
    ("benefit_concepts_concept_key", "A Global Benefit with this key already exists."),
    ("uq_benefit_concept_label", "A Global Benefit with this name already exists."),
    ("company_aliases_normalized_alias_uq", "This company alias is already registered."),
    ("uq_company_alias", "This company alias is already registered."),
    ("uq_company_slug", "A company with this slug already exists."),
    ("insurance_companies_slug", "A company with this slug already exists."),
    ("uq_product_company_key", "A product with this key already exists for this company."),
    ("insurance_products_company_id_product_key", "A product with this key already exists for this company."),
    ("uq_benefit_package_key", "A package with this key already exists for this catalog revision."),
    ("benefit_packages_catalog_revision_id_package_key", "A package with this key already exists for this catalog revision."),
    ("uq_catalog_offering_key", "An offering with this key already exists for this catalog revision."),
    ("catalog_offerings_catalog_revision_id_offering_key", "An offering with this key already exists for this catalog revision."),
    ("benefit_aliases_global_uq", "This alias phrase is already registered for this scope."),
    ("benefit_aliases_company_uq", "This alias phrase is already registered for this scope."),
    ("benefit_aliases_product_uq", "This alias phrase is already registered for this scope."),
    ("benefit_aliases_package_uq", "This alias phrase is already registered for this scope."),
    ("uq_benefit_alias_phrase", "This alias phrase is already registered."),
    ("uq_field_alias", "This field alias already exists."),
    ("uq_coverage_type_key", "A coverage type with this key already exists."),
    ("coverage_types_coverage_key", "A coverage type with this key already exists."),
    ("uq_segment_key", "A segment with this key already exists."),
    ("segments_segment_key", "A segment with this key already exists."),
    ("uq_vehicle_category_key", "A vehicle category with this key already exists."),
    ("vehicle_categories_category_key", "A vehicle category with this key already exists."),
    ("uq_vehicle_subcategory_key", "A vehicle subcategory with this key already exists for this category."),
]

_UNIQUE_RE = re.compile(r"unique constraint [\"']?([a-z0-9_]+)[\"']?", re.IGNORECASE)


def _integrity_message(exc: IntegrityError) -> tuple[str, int]:
    orig_text = str(getattr(exc, "orig", exc) or "").lower()
    if "foreign key" in orig_text or "violates foreign key" in orig_text:
        return "This record references a value that does not exist.", status.HTTP_422_UNPROCESSABLE_ENTITY
    if "not-null" in orig_text or "null value" in orig_text:
        return "A required field is missing.", status.HTTP_422_UNPROCESSABLE_ENTITY

    match = _UNIQUE_RE.search(orig_text)
    constraint = match.group(1) if match else orig_text
    for fragment, message in _CONSTRAINT_MESSAGES:
        if fragment in constraint:
            return message, status.HTTP_409_CONFLICT
    if "unique" in orig_text:
        return "A record with this value already exists.", status.HTTP_409_CONFLICT
    return "Database constraint violation.", status.HTTP_409_CONFLICT


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(loc) for loc in err.get("loc", [])), "message": err.get("msg", "Invalid value")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "validation_error", "message": "Request validation failed.", "details": details}},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_: Request, exc: IntegrityError) -> JSONResponse:
        message, status_code = _integrity_message(exc)
        code = "invalid_reference" if status_code == status.HTTP_422_UNPROCESSABLE_ENTITY else "conflict"
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": code, "message": message}},
        )

    @app.exception_handler(Exception)
    async def catch_all_handler(_: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, (SystemExit, KeyboardInterrupt)):
            raise
        msg = "Internal server error"
        print(f"[ERROR] {exc.__class__.__name__}: {exc}\n{format_exc()}", flush=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"message": msg}},
        )

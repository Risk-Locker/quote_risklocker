"""Run PDF extraction outside the API worker with bounded resources."""

from __future__ import annotations

import multiprocessing
from pathlib import Path
from typing import Any


EXTRACTION_TIMEOUT_SECONDS = 120
EXTRACTION_MEMORY_BYTES = 1024 * 1024 * 1024


def _apply_process_limits() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (EXTRACTION_MEMORY_BYTES, EXTRACTION_MEMORY_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (EXTRACTION_TIMEOUT_SECONDS, EXTRACTION_TIMEOUT_SECONDS + 5))
    except (ImportError, OSError, ValueError):
        # Windows relies on the parent-enforced timeout; deployment containers
        # additionally receive operating-system memory limits.
        return


def _worker(connection, path: str, enhanced_reading: bool, source_filename: str, db_aliases: dict | None = None, db_brands: list | None = None, db_models: list | None = None, db_companies: list[dict] | None = None, db_benefit_concepts: list[dict] | None = None, prompt_override: str | None = None) -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(override=True)
        _apply_process_limits()
        from app.extraction.orchestrator import ExtractionOrchestrator

        result = ExtractionOrchestrator().extract_file(
            Path(path),
            enhanced_reading=enhanced_reading,
            source_filename=source_filename,
            db_aliases=db_aliases,
            db_brands=db_brands,
            db_models=db_models,
            db_companies=db_companies,
            db_benefit_concepts=db_benefit_concepts,
            prompt_override=prompt_override,
        )
        connection.send(("ok", result))
    except Exception as exc:
        connection.send(("error", f"{exc.__class__.__name__}: {exc}"))
    finally:
        connection.close()


def extract_with_limits(
    path: Path,
    *,
    enhanced_reading: bool,
    source_filename: str,
    timeout_seconds: int = EXTRACTION_TIMEOUT_SECONDS,
    db_aliases: dict | None = None,
    db_brands: list | None = None,
    db_models: list | None = None,
    db_companies: list[dict] | None = None,
    db_benefit_concepts: list[dict] | None = None,
    prompt_override: str | None = None,
) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker,
        args=(child, str(path), enhanced_reading, source_filename, db_aliases, db_brands, db_models, db_companies, db_benefit_concepts, prompt_override),
        name="risklocker-pdf-extraction",
        daemon=True,
    )
    process.start()
    child.close()
    try:
        if not parent.poll(timeout_seconds):
            process.terminate()
            process.join(timeout=5)
            raise TimeoutError("PDF extraction exceeded the allowed time.")
        status, payload = parent.recv()
        process.join(timeout=5)
        if status != "ok":
            raise RuntimeError(str(payload))
        return payload
    finally:
        parent.close()
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)

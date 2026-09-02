"""Heuristic candidate finder that does not assume fixed pages or coordinates."""

from __future__ import annotations

import re
from collections import defaultdict

from app.extraction.types import CandidateValue
from app.extraction.validators import normalize_date, normalize_money


DRAFT_FIELDS = [
    "insurance_type",
    "insurance_company",
    "source_template_category",
    "product_name",
    "customer_name",
    "issue_date",
    "valid_until",
    "quotation_reference",
    "vehicle_no",
    "vehicle_class",
    "car_brand",
    "car_model",
    "vehicle_year",
    "engine_cc",
    "engine_no",
    "chassis_no",
    "cover_start_date",
    "cover_end_date",
    "cover_period",
    "coverage_type",
    "coverage_amount",
    "sum_insured",
    "market_value",
    "agreed_value",
    "excess_amount",
    "basic_premium_vehicle",
    "basic_premium_trailer",
    "premium",
    "ncd_amount",
    "loading_amount",
    "all_riders_amount",
    "optional_cover_amount",
    "service_tax",
    "stamp_duty",
    "gross_premium",
    "roadtax",
    "service_fee",
    "total_amount",
    "ncd_percent",
    "optional_covers",
    "benefits_selected",
    "add_ons_selected",
    "notes",
]

MONEY_FIELDS = {
    "coverage_amount",
    "sum_insured",
    "market_value",
    "agreed_value",
    "excess_amount",
    "basic_premium_vehicle",
    "basic_premium_trailer",
    "premium",
    "ncd_amount",
    "loading_amount",
    "all_riders_amount",
    "optional_cover_amount",
    "service_tax",
    "stamp_duty",
    "gross_premium",
    "roadtax",
    "service_fee",
    "total_amount",
}

DEFAULT_ALIASES = {
    "customer_name": ["insured name", "the insured", "customer name", "client name", "policyholder", "owner name", "pihak diinsuranskan", "participant"],
    "vehicle_no": ["vehicle no", "registration no", "reg no", "car no", "plate no", "vehicle registration"],
    "cover_start_date": ["cover start", "period from", "from date", "effective date"],
    "cover_end_date": ["cover end", "period to", "to date", "expiry date"],
    "car_brand": ["make", "brand", "car"],
    "car_model": ["model", "vehicle model"],
    "vehicle_year": ["year", "manufacture year", "mfg year"],
    "engine_cc": ["engine cc", "capacity", "cubic capacity", "engine capacity", "keupayaan enjin", "cc"],
    "engine_no": ["engine/motor no", "engine no", "motor no", "no. enjin"],
    "excess_amount": ["excess amount", "excess all claims", "excess", "policy excess", "ekses", "ekses polisi", "compulsory excess", "lebihan"],
    "valid_until": ["quotation validity", "tarikh sah quotation", "tarikh sah", "tempoh sah", "sah laku sehingga", "valid until", "validity period", "validity date", "validity", "this quotation will expire on", "quotation will expire on", "expire on", "expiry date", "tarikh luput", "sah sehingga"],
    "quotation_reference": ["quotation ref no", "quotation ref", "quotation reference", "quotation no", "quote no", "quote ref", "no sebutharga", "no. sebutharga", "no sebut harga", "no. sebut harga", "nombor sebut harga", "ref no", "reference no", "no. quotation"],
    "coverage_amount": ["sum insured", "coverage amount", "insured value", "market value", "agreed value", "sum covered", "jumlah diinsuranskan", "nilai yang dipersetujui"],
    "sum_insured": ["sum insured", "coverage amount", "insured value", "market value", "agreed value", "sum covered", "jumlah diinsuranskan", "nilai yang dipersetujui", "nilai pasaran"],
    "market_value": ["market value", "nilai pasaran", "agreed value", "sum insured", "jumlah diinsuranskan"],
    "agreed_value": ["agreed value", "nilai yang dipersetujui", "sum insured", "jumlah diinsuranskan"],
    "basic_premium": ["basic premium", "premium asas", "basic contribution", "sum covered basic"],
    "gross_premium": ["gross premium", "premium kasar", "gross contribution", "jumlah premium kasar"],
    "service_tax": ["service tax", "cukai perkhidmatan", "sst", "cukai servis"],
    "stamp_duty": ["stamp duty", "duti setem"],
    "premium": ["total premium", "premium payable", "jumlah premium", "total contribution", "jumlah caruman", "net premium", "gross premium", "premium kasar", "premium"],
    "total_amount": ["total payable", "total amount", "amount payable", "gross amount", "jumlah bayaran", "total / jumlah"],
    "optional_cover_amount": ["total optional cover amount", "total optional cover", "extra benefit", "manfaat tambahan", "optional cover amount"],
    "roadtax": ["road tax", "roadtax", "cukai jalan"],
    "service_fee": ["service fee", "runner fee", "runner charge", "upah runner"],
    "ncd_percent": ["ncd", "ncb", "no claim discount", "no claim bonus", "dtt", "diskaun tanpa tuntutan"],
    "windscreen": ["windscreen", "cermin hadapan"],
    }

DEFAULT_VEHICLE_BRANDS = ("PROTON", "PERODUA", "HONDA", "TOYOTA", "NISSAN", "BMW", "MERCEDES", "MERCEDES-BENZ", "MAZDA", "MITSUBISHI", "KIA", "HYUNDAI")
DEFAULT_VEHICLE_MODELS = ("SAGA BLM", "SAGA", "BLM", "WAJA", "MYVI", "AXIA", "ATIVA", "BEZZA", "ALZA", "VIVA", "VIOS", "CITY", "CIVIC", "ACCORD", "CAMRY", "HILUX")
CANONICAL_COVERAGE_TYPES = ["COMPREHENSIVE", "THIRD PARTY", "THIRD PARTY FIRE AND THEFT", "PRIVATE CAR", "MOTOR TAKAFUL"]
DATE_RE = r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b"
MONEY_RE = r"(?:RM\s*)?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?"


def _compact_evidence(text: str, start: int, end: int) -> str:
    return re.sub(r"\s+", " ", text[max(0, start - 80) : min(len(text), end + 80)]).strip()


def _page_for_offset(page_text: list[dict], offset: int) -> int | None:
    cursor = 0
    for page in page_text:
        text = page.get("text", "")
        next_cursor = cursor + len(text) + 1
        if cursor <= offset <= next_cursor:
            return int(page.get("page", 1))
        cursor = next_cursor
    return None


def _add(results: dict[str, list[CandidateValue]], field: str, value: str | None, source: str, score: float, text: str, start: int, end: int, page_text: list[dict]) -> None:
    if value is None:
        return
    cleaned = re.sub(r"\s+", " ", value).strip(" :;.-_/\\")
    if not cleaned:
        return
    if field == "quotation_reference":
        alpha_num = re.sub(r"[^A-Za-z0-9]", "", cleaned)
        if len(alpha_num) < 4 or alpha_num.upper() in {"MOTOR", "INSURANCE", "QUOTATION", "TAKAFUL", "SCHEDULE", "POLICY", "PRIVATE"}:
            return
    if field == "customer_name":
        upper_c = cleaned.upper()
        if any(bad in upper_c for bad in ["NAMA EJEN", "AGENT", "NO. AKAUN", "ACCOUNT NO", "RISKLOCKER", "BROKER", "AGENCY", "INSURANCE", "TAKAFUL", "SUM INSURED"]):
            return
    if field == "vehicle_no":
        cleaned = re.sub(r"\s+", "", cleaned).strip(" .:;-")
        if not cleaned or len(cleaned) < 2 or cleaned.startswith("RM") or "UNREGISTERED" in cleaned.upper():
            return
    if field == "car_brand":
        if len(cleaned) <= 1 or cleaned in {"&", "AND", "-"}:
            return
    if field in MONEY_FIELDS:
        normalized_money = normalize_money(cleaned)
        if normalized_money is None:
            return
        cleaned = normalized_money
    if field == "ncd_percent":
        ncd_match = re.search(r"\d{1,2}(?:\.\d+)?", cleaned)
        cleaned = ncd_match.group(0) if ncd_match else cleaned
    if field == "coverage_type":
        cleaned = cleaned.replace("Cover Type", "").replace("Jenis Perlindungan", "").strip(" :/-")
        matched_cov = None
        for item in CANONICAL_COVERAGE_TYPES:
            if item in cleaned.upper():
                matched_cov = item.title() if item != "COMPREHENSIVE" else "Comprehensive"
                break
        cleaned = matched_cov or ("Comprehensive" if not cleaned or "PERLINDUNGAN" in cleaned.upper() else cleaned)
    if field == "engine_cc":
        cc_match = re.search(r"\d{3,5}", cleaned)
        cleaned = cc_match.group(0) if cc_match else cleaned
    if field in {"cover_start_date", "cover_end_date", "issue_date", "valid_until"}:
        norm_date = normalize_date(cleaned)
        if not norm_date:
            return
        cleaned = norm_date
    results[field].append(
        CandidateValue(
            field=field,
            value=cleaned,
            source_method=source,
            score=score,
            page=_page_for_offset(page_text, start),
            evidence=_compact_evidence(text, start, end),
        )
    )


def _add_static(results: dict[str, list[CandidateValue]], field: str, value: str | None, source: str, score: float, evidence: str, text: str, page_text: list[dict]) -> None:
    start = max(0, text.find(evidence[:40])) if evidence else 0
    end = start + len(evidence)
    _add(results, field, value, source, score, text, start, end, page_text)


def _dates(segment: str) -> list[str]:
    return [match.group(0) for match in re.finditer(DATE_RE, segment)]


def _money(segment: str) -> list[str]:
    return [match.group(0) for match in re.finditer(MONEY_RE, segment)]


def _rm_money(segment: str) -> list[str]:
    return [match.group(0) for match in re.finditer(r"RM\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?", segment, re.IGNORECASE)]


def _clean_model(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" :-")


def _lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


BILINGUAL_SUBTITLE_LABELS = {
    "pihak diinsuranskan", "no pendaftaran kenderaan", "tahun diperbuat", "no enjin",
    "no casis", "no casis treler", "lebihan", "ekses", "ekses polisi", "nilai yang dipersetujui",
    "jumlah diinsuranskan", "jumlah treler diinsuranskan", "kelas kenderaan", "jenis perlindungan",
    "sewa beli", "premium asas", "semua pemandu", "premium treler", "dtt", "tarikh berkuatkuasa dtt",
    "manfaat tambahan", "buatan & jenis badan", "keupayaan enjin", "muatan tempat duduk termasuk pemandu",
    "muatan tempat duduk", "premium kasar", "cukai perkhidmatan", "setem hasil", "pemandu yang diberi kuasa",
    "jumlah", "akta", "tarikh dikeluarkan", "kawasan geografi", "perniagaan/pekerjaan",
    "no k/p baru/no pendaftaran perniagaan", "no k/p", "no perakuan pendaftaran", "no perakuan",
    "no treler", "no quotation", "no. quotation", "no. akaun / nama ejen", "no akaun", "nama ejen",
    "dipersetujui", "nilai yang", "jumlah diinsuranskan nilai yang"
}


def _is_subtitle_label(text: str) -> bool:
    norm = re.sub(r"[^\w\s/&]+", "", text.lower()).strip()
    if norm in BILINGUAL_SUBTITLE_LABELS:
        return True
    return any(norm == l or norm.startswith(l + " ") or norm.endswith(" " + l) or l in norm for l in BILINGUAL_SUBTITLE_LABELS)


def _clean_code_value(value: str) -> str:
    cleaned = re.split(r"(?i)\s+(?:gross premium|premium kasar|service tax|cukai perkhidmatan|stamp duty|setem hasil|total|jumlah)\b", value)[0].strip()
    return cleaned


def _next_value(lines: list[str], index: int) -> str:
    for candidate in lines[index + 1 : index + 8]:
        stripped = candidate.strip()
        if not stripped or stripped in {":", "-", "RM", "-/-"}:
            continue
        if _is_subtitle_label(stripped):
            continue
        return _clean_code_value(stripped)
    return ""


def _line_value(line: str, lines: list[str], index: int) -> str:
    if ":" in line:
        tail = line.split(":", 1)[1].strip()
        if tail and not _is_subtitle_label(tail):
            parts = re.split(r"\s{2,}|(?i:\b(?:car|model|vehicle|chassis|engine|year|reg(?:ist|istration)?|premium|ncd)\b[\s\-:])", tail)
            raw = parts[0].strip() if parts else tail
            return _clean_code_value(raw)
    return _next_value(lines, index)


def _offset(text: str, needle: str) -> int:
    index = text.find(needle)
    return max(0, index)


def _add_line_value(
    results: dict[str, list[CandidateValue]],
    field: str,
    value: str,
    source: str,
    score: float,
    line: str,
    text: str,
    page_text: list[dict],
) -> None:
    start = _offset(text, line)
    _add(results, field, value, source, score, text, start, start + len(line), page_text)


def _semantic_label_map() -> list[tuple[str, str]]:
    return [
        ("applicant", "customer_name"),
        ("insured name", "customer_name"),
        ("the insured", "customer_name"),
        ("the insured / pihak diinsuranskan", "customer_name"),
        ("participant name", "customer_name"),
        ("participant", "customer_name"),
        ("name", "customer_name"),
        ("quotation date", "issue_date"),
        ("issued date", "issue_date"),
        ("date of issue", "issue_date"),
        ("date", "issue_date"),
        ("this quotation will expire on", "valid_until"),
        ("quotation will expire on", "valid_until"),
        ("expire on", "valid_until"),
        ("expiry date", "valid_until"),
        ("tarikh luput", "valid_until"),
        ("valid until", "valid_until"),
        ("validity period", "valid_until"),
        ("validity", "valid_until"),
        ("sah sehingga", "valid_until"),
        ("vehicle registration number", "vehicle_no"),
        ("registration no", "vehicle_no"),
        ("vehicle no", "vehicle_no"),
        ("regist. no", "vehicle_no"),
        ("regist no", "vehicle_no"),
        ("reg. no", "vehicle_no"),
        ("reg no", "vehicle_no"),
        ("vehicle make", "car_brand"),
        ("make", "car_brand"),
        ("make & type of body", "car_model"),
        ("vehicle model", "car_model"),
        ("make & model", "car_model"),
        ("model", "car_model"),
        ("year of manufactured", "vehicle_year"),
        ("year of manufacture", "vehicle_year"),
        ("year of make", "vehicle_year"),
        ("year", "vehicle_year"),
        ("engine capacity", "engine_cc"),
        ("cubic capacity", "engine_cc"),
        ("capacity", "engine_cc"),
        ("chassis number", "chassis_no"),
        ("chassis no", "chassis_no"),
        ("engine/motor no", "engine_no"),
        ("engine no", "engine_no"),
        ("sum covered (rm)", "coverage_amount"),
        ("sum covered", "coverage_amount"),
        ("sum insured (agreed value)", "coverage_amount"),
        ("vehicle sum insured", "coverage_amount"),
        ("sum insured", "coverage_amount"),
        ("cover type", "coverage_type"),
        ("coverage type", "coverage_type"),
        ("class of vehicle", "vehicle_class"),
        ("scope of cover", "coverage_type"),
        ("takaful scheme", "coverage_type"),
        ("product type", "product_name"),
        ("basic contribution", "basic_premium_vehicle"),
        ("basic premium", "basic_premium_vehicle"),
        ("gross contribution", "premium"),
        ("gross premium", "premium"),
        ("total contribution payable", "total_amount"),
        ("total payable", "total_amount"),
        ("total / jumlah", "total_amount"),
        ("total", "total_amount"),
        ("stamp duty", "stamp_duty"),
        ("sst", "service_tax"),
        ("service tax", "service_tax"),
        ("excess all claims", "excess_amount"),
        ("excess amount", "excess_amount"),
        ("policy excess", "excess_amount"),
        ("compulsory excess", "excess_amount"),
        ("excess", "excess_amount"),
        ("lebihan", "excess_amount"),
        ("ekses", "excess_amount"),
        ("ekses polisi", "excess_amount"),
    ]


def _add_period_of_cover(text: str, lines: list[str], page_text: list[dict], results: dict[str, list[CandidateValue]]) -> None:
    patterns = [
        r"(?i)period of cover\s*:?\s*(?P<start>\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*(?:until|to|-)\s*(?P<end>\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"(?i)period of takaful\s*:?\s*(?P<start>\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*(?:until|to|-)\s*(?P<end>\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"(?i)period of insurance\s*:?\s*(?P<start>\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*(?:until|to|-)\s*(?P<end>\d{1,2}[/-]\d{1,2}[/-]\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            _add(results, "cover_start_date", match.group("start"), "semantic_cover_period", 0.97, text, match.start(), match.end(), page_text)
            _add(results, "cover_end_date", match.group("end"), "semantic_cover_period", 0.97, text, match.start(), match.end(), page_text)
            return
    for index, line in enumerate(lines):
        if line.lower() in {"period of cover", "cover period", "period of takaful", "period of insurance"}:
            value = _next_value(lines, index)
            dates = _dates(value)
            if len(dates) >= 2:
                _add_line_value(results, "cover_start_date", dates[0], "semantic_cover_period", 0.96, line, text, page_text)
                _add_line_value(results, "cover_end_date", dates[1], "semantic_cover_period", 0.96, line, text, page_text)


def _add_semantic_label_values(text: str, page_text: list[dict], results: dict[str, list[CandidateValue]]) -> None:
    lines = _lines(text)
    _add_period_of_cover(text, lines, page_text, results)
    label_map = _semantic_label_map()
    for index, line in enumerate(lines):
        normalized = line.lower().strip(" :-")
        has_colon = ":" in line
        head = line.split(":", 1)[0].lower().strip(" :-") if has_colon else ""
        for label, field in label_map:
            matched = False
            if has_colon:
                matched = head == label or head.endswith(label) or head.startswith(label)
            else:
                matched = normalized == label or normalized.startswith(f"{label} ") or normalized.endswith(f" {label}") or normalized.endswith(label) or f" {label} " in normalized or f" {label}:" in normalized
            if matched:
                value = _line_value(line, lines, index)
                if field == "valid_until":
                    dates = _dates(value)
                    value = dates[0] if dates else value.replace("Until", "").strip(" ()")
                if field == "coverage_amount" and "market value" in value.lower():
                    money_values = _money(value)
                    value = money_values[0] if money_values else value
                if field == "vehicle_no":
                    # Ignore values like '-UNREGISTERED-' or currency-like tokens
                    if "unregistered" in value.lower() or value.upper().startswith("RM"):
                        continue
                if value:
                    _add_line_value(results, field, value, "semantic_label_value", 0.94, line, text, page_text)


def _add_contribution_rows(text: str, page_text: list[dict], results: dict[str, list[CandidateValue]]) -> None:
    lines = _lines(text)
    def row_amount(index: int) -> str | None:
        line = lines[index]
        if "www." in line.lower() or "head office" in line.lower():
            return None
        cleaned_line = re.sub(r"\(\d+(?:\.\d+)?\s*%\)", "", line)
        line_money = _money(cleaned_line)
        if line_money:
            return line_money[0]
        for candidate in lines[index + 1 : index + 4]:
            if candidate.strip().upper() == "RM":
                continue
            cand_clean = re.sub(r"\(\d+(?:\.\d+)?\s*%\)", "", candidate)
            values = _money(cand_clean)
            if values:
                return values[0]
        return None

    for index, line in enumerate(lines):
        lower = line.lower().strip(" :-")
        window = " ".join(lines[index : index + 5])
        money_values = _money(re.sub(r"\(\d+(?:\.\d+)?\s*%\)", "", window))
        if "ncd" in lower or "no-claim-discount" in lower or "dtt" in lower or "diskaun tanpa tuntutan" in lower:
            percent = re.search(r"\((?P<ncd>\d{1,2}(?:\.\d+)?)\s*%\)|(?P<ncd2>\d{1,2}(?:\.\d+)?)\s*%", line)
            if percent:
                _add_line_value(results, "ncd_percent", percent.group("ncd") or percent.group("ncd2"), "semantic_contribution_row", 0.96, line, text, page_text)
            if money_values:
                _add_line_value(results, "ncd_amount", money_values[0], "semantic_contribution_row", 0.9, line, text, page_text)
        if lower.startswith("total payable") or lower.startswith("total amount") or lower.startswith("amount payable") or lower.startswith("total contribution payable") or lower.startswith("jumlah bayaran") or lower.startswith("jumlah perlu dibayar"):
            amount = row_amount(index)
            if amount:
                _add_line_value(results, "total_amount", amount, "semantic_contribution_row", 0.99, line, text, page_text)
        elif lower.startswith("total premium") or lower.startswith("jumlah premium") or lower.startswith("total contribution") or lower.startswith("jumlah caruman"):
            amount = row_amount(index)
            if amount:
                _add_line_value(results, "premium", amount, "semantic_contribution_row", 0.99, line, text, page_text)
                _add_line_value(results, "total_amount", amount, "semantic_contribution_row", 0.94, line, text, page_text)
        elif lower.startswith("basic premium") or lower.startswith("premium asas") or (lower.startswith("premium") and not lower.startswith("premium kasar") and not lower.startswith("premium payable")):
            amount = row_amount(index)
            if amount:
                _add_line_value(results, "basic_premium_vehicle", amount, "semantic_contribution_row", 0.95, line, text, page_text)
        if lower.startswith("gross contribution") or lower.startswith("gross premium") or lower.startswith("premium kasar"):
            amount = row_amount(index)
            if amount:
                _add_line_value(results, "gross_premium", amount, "semantic_contribution_row", 0.95, line, text, page_text)
                _add_line_value(results, "premium", amount, "semantic_contribution_row", 0.92, line, text, page_text)
        if lower.startswith("service tax") or lower.startswith("cukai perkhidmatan") or lower.startswith("sst"):
            amount = row_amount(index)
            if amount:
                _add_line_value(results, "service_tax", amount, "semantic_contribution_row", 0.97, line, text, page_text)
        if lower.startswith("stamp duty") or lower.startswith("duti setem"):
            amount = row_amount(index)
            if amount:
                _add_line_value(results, "stamp_duty", amount, "semantic_contribution_row", 0.95, line, text, page_text)
        if "policy excess" in lower or "lebihan" in lower or "ekses" in lower or (lower.startswith("excess") and any(c.isdigit() for c in window)):
            if money_values:
                _add_line_value(results, "excess_amount", money_values[0], "semantic_contribution_row", 0.92, line, text, page_text)
        if "total optional cover" in lower or "extra benefit" in lower or "manfaat tambahan" in lower:
            amount = row_amount(index)
            if amount:
                _add_line_value(results, "optional_cover_amount", amount, "semantic_contribution_row", 0.94, line, text, page_text)
        if lower.startswith("windscreen"):
            money_match = re.search(r"\((RM\s*[\d,]+(?:\.\d{2})?)\)", line, re.IGNORECASE)
            if money_match:
                _add_line_value(results, "optional_cover_amount", money_match.group(1), "semantic_optional_cover", 0.9, line, text, page_text)


def _add_optional_covers(text: str, page_text: list[dict], results: dict[str, list[CandidateValue]]) -> None:
    labels = [
        "Windscreen",
        "Legal Liability to Passenger",
        "Legal Liability of Passengers for Negligent Acts",
        "Legal Liability Of Passengers",
        "Legal Liability To Passengers",
        "Passenger Liability",
        "Inclusion of Special Perils",
        "Special Perils",
        "Drive Less Save More",
    ]
    found: list[str] = []
    lower = text.lower()
    for label in labels:
        if label.lower() in lower and label not in found:
            found.append(label)
    if found:
        evidence = "; ".join(found)
        _add_static(results, "optional_covers", evidence, "semantic_optional_covers", 0.92, evidence, text, page_text)
        _add_static(results, "benefits_selected", evidence, "semantic_optional_covers", 0.85, evidence, text, page_text)


def _add_messy_compact_text(
    text: str,
    page_text: list[dict],
    results: dict[str, list[CandidateValue]],
    vehicle_models: tuple[str, ...],
) -> None:
    compact = re.sub(r"[^A-Za-z0-9.%/-]", "", text.upper())
    for model in sorted(vehicle_models, key=len, reverse=True):
        token = re.sub(r"[^A-Z0-9]", "", model)
        if token and token in compact:
            normalized = "SAGA BLM" if model in {"SAGA BLM", "BLM"} else model
            _add_static(results, "car_model", normalized, "messy_compact_window", 0.82, model, text, page_text)
            break
    for coverage in CANONICAL_COVERAGE_TYPES:
        token = re.sub(r"[^A-Z0-9]", "", coverage)
        if token and token in compact:
            _add_static(results, "coverage_type", coverage.title() if coverage != "COMPREHENSIVE" else "Comprehensive", "messy_compact_window", 0.82, coverage, text, page_text)
            break
    cc_match = re.search(r"(?P<cc>\d{3,5})(?:CC|C\.C|L)", compact)
    if cc_match:
        _add_static(results, "engine_cc", cc_match.group("cc"), "messy_compact_window", 0.78, cc_match.group(0), text, page_text)


def _add_amgen_profile(text: str, page_text: list[dict], results: dict[str, list[CandidateValue]]) -> None:
    upper = text.upper()
    if not any(marker in upper for marker in ["AUTO365", "AMASSURANCE", "AMGENERAL", "KURNIA", "LIBERTY GENERAL INSURANCE BERHAD"]):
        return

    _add_static(results, "source_template_category", "Amgen / AmAssurance / Kurnia-style", "document_profile", 0.95, "AmAssurance / auto365 quotation", text, page_text)

    header = re.search(
        r"Insured Name\s+Issued Date\s+Vehicle Class\s+Capacity\s+Vehicle No\s+Trailer No\s+Named Driver\s+"
        r"(?P<name>[A-Z][A-Z ]{2,80}?)\s+"
        r"(?P<issue>\d{1,2}[/-]\d{1,2}[/-]\d{4})\s+"
        r"(?P<class>.+?)\s+"
        r"(?P<cc>\d{3,5}\s*CC)\s+"
        r"(?P<vehicle>[A-Z]{1,3}\d{1,4}[A-Z]?)\b",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if header:
        evidence = header.group(0)
        _add_static(results, "customer_name", header.group("name"), "profile_header", 0.97, evidence, text, page_text)
        _add_static(results, "issue_date", header.group("issue"), "profile_header", 0.94, evidence, text, page_text)
        _add_static(results, "vehicle_class", header.group("class"), "profile_header", 0.92, evidence, text, page_text)
        _add_static(results, "engine_cc", header.group("cc"), "profile_header", 0.94, evidence, text, page_text)
        _add_static(results, "vehicle_no", header.group("vehicle"), "profile_header", 0.98, evidence, text, page_text)

    valid_until_patterns = [
        r"quotation\s+validity\s*(?:/\s*tarikh\s+sah\s+quotation)?\s*:?\s*(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"tarikh\s+sah\s+quotation\s*:?\s*(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"quotation\s+validity\s*\n\s*(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"(?:this\s+)?quotation\s+(?:will\s+)?expire\s+on\s*:?\s*(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"valid\s+(?:until|to)\s*:?\s*(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"validity\s*(?:period|date)?\s*:?\s*(?:until\s*)?(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"tarikh\s+luput\s*:?\s*(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"expiry\s+date\s*:?\s*(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"sah\s+sehingga\s*:?\s*(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{4})",
    ]
    for v_pat in valid_until_patterns:
        v_match = re.search(v_pat, text, re.IGNORECASE)
        if v_match:
            _add_static(results, "valid_until", v_match.group("date"), "profile_validity", 0.95, v_match.group(0), text, page_text)
            break

    quotation_ref_patterns = [
        r"(?:quotation\s+ref(?:erence)?\s*(?:no\.?)?|quote\s+(?:no|ref)\.?|no\.?\s*sebut\s*harga|no\.?\s*sebutharga)\s*[:.]?\s*(?P<ref>[A-Z0-9\-_/]{4,35})",
        r"Quotation\s+No\.?\s*(?:\n\s*No\.?\s*Quotation\s*)?[:.]?\s*(?P<ref>[A-Z0-9\-_/]{4,35})",
        r"Quotation\s+Ref\s+No\.(?P<ref>[A-Z0-9\-_/]{4,35})",
        r"(?:Quotation|Quote|Ref)\s*#?\s*[:.]\s*(?P<ref>[A-Z0-9\-_/]{4,35})",
    ]
    for qr_pat in quotation_ref_patterns:
        qr_match = re.search(qr_pat, text, re.IGNORECASE)
        if qr_match:
            ref_candidate = qr_match.group("ref").strip()
            if ref_candidate.upper() not in {"MOTOR", "INSURANCE", "QUOTATION", "TAKAFUL", "SCHEDULE", "POLICY", "PRIVATE"}:
                _add_static(results, "quotation_reference", ref_candidate, "profile_quotation_ref", 0.95, qr_match.group(0), text, page_text)
                break


    vehicle = re.search(
        r"Make\s*&\s*Model\s+Year of make\s+Vehicle Sum Insured\s+Trailer Sum Insured\s+"
        r"(?P<model>[A-Z0-9 /&().+-]+?)\s+"
        r"(?P<year>(?:19|20)\d{2})\s+"
        r"(?P<expiry>\d{1,2}[/-]\d{1,2}[/-]\d{4})\s+"
        r"(?P<sum>RM\s*[\d,]+\.\d{2})",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if vehicle:
        model = _clean_model(vehicle.group("model"))
        brand = model.split()[0] if model else ""
        evidence = vehicle.group(0)
        if brand:
            _add_static(results, "car_brand", brand, "profile_vehicle", 0.96, evidence, text, page_text)
        _add_static(results, "car_model", model, "profile_vehicle", 0.96, evidence, text, page_text)
        _add_static(results, "vehicle_year", vehicle.group("year"), "profile_vehicle", 0.96, evidence, text, page_text)
        _add_static(results, "cover_end_date", vehicle.group("expiry"), "profile_vehicle", 0.93, evidence, text, page_text)
        _add_static(results, "coverage_amount", vehicle.group("sum"), "profile_vehicle", 0.95, evidence, text, page_text)

    start_window = re.search(r"Start Date\s+Expiry Date(?P<window>.+?)ISM-ABI Market Value", text, re.IGNORECASE | re.DOTALL)
    if start_window:
        policy_dates = _dates(start_window.group("window"))
        normalized = [normalize_date(item) for item in policy_dates]
        normalized = [item for item in normalized if item]
        if len(normalized) >= 2:
            normalized_sorted = sorted(normalized)
            _add_static(results, "cover_start_date", normalized_sorted[0], "profile_policy_dates", 0.95, start_window.group(0), text, page_text)
            _add_static(results, "cover_end_date", normalized_sorted[-1], "profile_policy_dates", 0.95, start_window.group(0), text, page_text)

    for field, pattern, score in [
        ("market_value", r"ISM-ABI Market Value\s+(?P<money>RM\s*[\d,]+\.\d{2})", 0.92),
        ("engine_no", r"Engine/Motor No\s*:?\s*(?P<value>[A-Z0-9-]+)", 0.92),
        ("chassis_no", r"Chassis No\.?\s*:?\s*(?P<value>[A-Z0-9-]+)", 0.94),
        ("excess_amount", r"(?:\*?Excess(?:\s+Amount)?|Lebihan|Ekses(?:\s+Polisi)?|Policy\s+Excess)\s*:?\s*(?:RM\s*)?(?P<money>[\d,]+\.\d{2})", 0.92),
    ]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            _add_static(results, field, match.groupdict().get("money") or match.groupdict().get("value"), f"profile_{field}", score, match.group(0), text, page_text)

    product = re.search(r"\b(auto365\s+[A-Za-z ]+?)\s+Quotation Ref No", text, re.IGNORECASE)
    if product:
        value = re.sub(r"\s+", " ", product.group(1)).strip()
        _add_static(results, "product_name", value, "profile_product", 0.94, product.group(0), text, page_text)
        _add_static(results, "coverage_type", value, "profile_product", 0.9, product.group(0), text, page_text)
        tier_match = re.search(r"\b(Lite|Plus|Premier|Premium)\b", value, re.IGNORECASE)
        if tier_match:
            tier_val = tier_match.group(1).title()
            if tier_val == "Premium":
                tier_val = "Premier"
            _add_static(results, "product_tier", tier_val, "profile_product", 0.95, product.group(0), text, page_text)
            _add_static(results, "tier_name", tier_val, "profile_product", 0.95, product.group(0), text, page_text)
            _add_static(results, "detected_package_name", f"Auto365 Comprehensive {tier_val}", "profile_product", 0.95, product.group(0), text, page_text)

    premium_window = re.search(r"Quotation Ref No\.[A-Z0-9-]+(?P<window>.+?)Service Tax\s+8%", text, re.IGNORECASE | re.DOTALL)
    if premium_window:
        amounts = _rm_money(premium_window.group("window"))
        # Visual table values appear before their labels in this PDF family.
        if len(amounts) >= 6:
            _add_static(results, "total_amount", amounts[0], "profile_premium_table", 0.88, premium_window.group(0), text, page_text)
            _add_static(results, "basic_premium_vehicle", amounts[1], "profile_premium_table", 0.9, premium_window.group(0), text, page_text)
            _add_static(results, "basic_premium_trailer", amounts[2], "profile_premium_table", 0.86, premium_window.group(0), text, page_text)
            _add_static(results, "loading_amount", amounts[3], "profile_premium_table", 0.86, premium_window.group(0), text, page_text)
            _add_static(results, "all_riders_amount", amounts[4], "profile_premium_table", 0.86, premium_window.group(0), text, page_text)
            _add_static(results, "ncd_amount", amounts[5], "profile_premium_table", 0.9, premium_window.group(0), text, page_text)
        if len(amounts) >= 7:
            _add_static(results, "agreed_value", amounts[6], "profile_premium_table", 0.86, premium_window.group(0), text, page_text)

    totals_window = re.search(r"Total Optional Cover Amount.+?Service Tax\s+8%.+?Total Payable", text, re.IGNORECASE | re.DOTALL)
    if totals_window:
        amounts = _rm_money(totals_window.group(0))
        if len(amounts) >= 4:
            _add_static(results, "service_tax", amounts[-4], "profile_total_table", 0.93, totals_window.group(0), text, page_text)
            _add_static(results, "stamp_duty", amounts[-3], "profile_total_table", 0.93, totals_window.group(0), text, page_text)
            _add_static(results, "gross_premium", amounts[-2], "profile_total_table", 0.93, totals_window.group(0), text, page_text)
            _add_static(results, "premium", amounts[-2], "profile_total_table", 0.94, totals_window.group(0), text, page_text)
            _add_static(results, "total_amount", amounts[-1], "profile_total_table", 0.96, totals_window.group(0), text, page_text)
            _add_static(results, "optional_cover_amount", amounts[-4], "profile_total_table", 0.86, totals_window.group(0), text, page_text)

    ncd = re.search(r"\bNCD\s+(?P<ncd>\d{1,2}(?:\.\d+)?)\s*%", text, re.IGNORECASE)
    if ncd:
        _add_static(results, "ncd_percent", ncd.group("ncd"), "profile_ncd", 0.95, ncd.group(0), text, page_text)

    optional_window = re.search(r"OPTIONAL COVER LIST(?P<window>.+?)(?:One Touch|www\.amassurance|Head Office)", text, re.IGNORECASE | re.DOTALL)
    if optional_window:
        window = optional_window.group("window")
        covers: list[str] = []
        for label in ["Legal Liability Of Passengers", "Legal Liability To Passengers", "Windscreen Damage"]:
            if re.search(re.escape(label), window, re.IGNORECASE):
                covers.append(label)
        if covers:
            value = "; ".join(covers)
            _add_static(results, "optional_covers", value, "profile_optional_covers", 0.94, optional_window.group(0), text, page_text)
            _add_static(results, "benefits_selected", value, "profile_optional_covers", 0.9, optional_window.group(0), text, page_text)


def _normalized_detection_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _add_company_detection(
    source_filename: str,
    text: str,
    page_text: list[dict],
    results: dict[str, list[CandidateValue]],
    companies: list[dict],
) -> None:
    """Resolve companies exclusively from active database records and aliases."""

    from app.extraction.company_resolution import company_alias_matches

    matches: list[tuple[int, str, dict, str]] = []
    for source, method in ((source_filename, "database_company_filename"), (text, "database_company_text")):
        for match in company_alias_matches(source, companies):
            matches.append((match["length"], method, match["company"], str(match["alias"])))

    if not matches:
        return
    # Prefer the most specific alias, then filename evidence. Equal-scoring
    # alternatives remain visible to the conflict detector for human review.
    best_length = max(item[0] for item in matches)
    selected = [item for item in matches if item[0] == best_length]
    seen: set[tuple[str, str]] = set()
    for _length, method, company, alias in selected:
        name = str(company["name"])
        marker = (name, method)
        if marker in seen:
            continue
        seen.add(marker)
        evidence = source_filename if method.endswith("filename") else alias
        _add_static(results, "insurance_company", name, method, 0.99 if method.endswith("filename") else 0.95, evidence, text, page_text)
        category = str(company.get("source_template_category") or "Other / Unknown")
        _add_static(results, "source_template_category", category, method, 0.94, evidence, text, page_text)


def find_candidates(
    raw_text: str,
    page_text: list[dict],
    words: list[dict] | None = None,
    aliases: dict[str, list[str]] | None = None,
    source_filename: str = "",
    db_brands: list[str] | None = None,
    db_models: list[str] | None = None,
    db_companies: list[dict] | None = None,
) -> dict[str, list[CandidateValue]]:
    text = raw_text or ""
    active_aliases = {**DEFAULT_ALIASES, **(aliases or {})}
    results: dict[str, list[CandidateValue]] = defaultdict(list)

    active_brands = tuple(dict.fromkeys([*(" ".join(item.upper().split()) for item in (db_brands or []) if item), *DEFAULT_VEHICLE_BRANDS]))
    active_models = tuple(dict.fromkeys([*(" ".join(item.upper().split()) for item in (db_models or []) if item), *DEFAULT_VEHICLE_MODELS]))

    _add_company_detection(source_filename, text, page_text, results, db_companies or [])
    _add_amgen_profile(text, page_text, results)
    _add_semantic_label_values(text, page_text, results)
    _add_contribution_rows(text, page_text, results)
    _add_optional_covers(text, page_text, results)
    _add_messy_compact_text(text, page_text, results, active_models)

    for field, field_aliases in active_aliases.items():
        for alias in field_aliases:
            pattern = re.compile(rf"(?i)\b{re.escape(alias)}\b\s*[:\-]?\s*(?P<value>[^\n\r]{{1,90}})")
            for match in pattern.finditer(text):
                value = match.group("value")
                value = re.split(r"\s{2,}|(?i:\b(vehicle|model|premium|total|road\s*tax|ncd|sum insured|cover)\b)", value)[0]
                _add(results, field, value, "label_nearby", 0.78, text, match.start(), match.end(), page_text)

    # Filename vehicle number extraction hint (e.g., 20250604_JJC9250_Quotation_STMB.pdf -> JJC9250)
    if source_filename:
        clean_fn = source_filename.upper().replace("_", " ").replace("-", " ")
        for fn_candidate in re.findall(r"\b[A-Z]{1,3}\d{1,4}[A-Z]?\b", clean_fn):
            if not re.fullmatch(r"20\d{2}|19\d{2}|PDF|REF|STMB|AMGEN|QBE|PDS", fn_candidate):
                _add_static(results, "vehicle_no", fn_candidate, "filename_vehicle_no", 0.95, source_filename, text, page_text)

    non_plate_words = {
        "ACT", "THE", "FOR", "NOT", "AND", "ALL", "BUT", "ANY", "CAN", "MAY", "ARE", "SEE",
        "NEW", "OLD", "CAR", "VAN", "BUS", "FAX", "TEL", "PER", "ONE", "TWO", "SUM", "NET",
        "MAX", "MIN", "STD", "TAX", "SST", "PDS", "REF", "NCD", "JPJ", "CC", "RM", "PIDM",
        "BHD", "SDN", "LTD", "INC", "JAN", "FEB", "MAR", "APR", "JUN", "JUL", "AUG", "SEP",
        "OCT", "NOV", "DEC", "YES", "NO", "WEST", "EAST", "IS", "IN", "IF", "IT", "AT", "BY",
        "ON", "TO", "OF", "OR", "SO", "AS", "HE", "WE", "DO", "GO", "UP", "MY", "AN", "AM",
        "ME", "US",
    }
    for match in re.finditer(r"\b[A-Z]{1,3}\s?\d{1,4}[A-Z]?\b", text.upper()):
        value = match.group(0)
        norm_val = re.sub(r"\s+", "", value)
        prefix_match = re.match(r"^[A-Z]+", norm_val)
        prefix = prefix_match.group(0) if prefix_match else ""
        if prefix in non_plate_words or norm_val in non_plate_words:
            continue
        if norm_val.startswith("RM") or re.fullmatch(r"20\d{2}|19\d{2}", norm_val):
            continue
        _add(results, "vehicle_no", value, "pattern_vehicle_no", 0.7, text, match.start(), match.end(), page_text)

    for match in re.finditer(r"\b(?:19|20)\d{2}\b", text):
        year = match.group(0)
        if 1980 <= int(year) <= 2035:
            _add(results, "vehicle_year", year, "pattern_year", 0.67, text, match.start(), match.end(), page_text)

    money_pattern = MONEY_RE
    for label, field in [("total payable", "total_amount"), ("amount payable", "total_amount"), ("gross amount", "total_amount"), ("gross premium", "premium"), ("premium", "premium"), ("sum insured", "coverage_amount"), ("roadtax", "roadtax"), ("road tax", "roadtax"), ("service fee", "service_fee"), ("runner fee", "service_fee")]:
        for match in re.finditer(rf"(?i){re.escape(label)}[^\dRM]{{0,25}}(?P<money>{money_pattern})", text):
            _add(results, field, match.group("money"), "label_money", 0.84, text, match.start(), match.end(), page_text)

    date_pattern = DATE_RE
    dates = list(re.finditer(date_pattern, text))
    for match in dates:
        evidence = _compact_evidence(text, match.start(), match.end()).lower()
        field = "cover_start_date" if any(word in evidence for word in ["from", "start", "effective"]) else "cover_end_date" if any(word in evidence for word in ["to", "end", "expiry"]) else "issue_date"
        _add(results, field, match.group(0), "pattern_date", 0.72, text, match.start(), match.end(), page_text)
    if len(dates) >= 2:
        _add(results, "cover_start_date", dates[0].group(0), "date_order_hint", 0.55, text, dates[0].start(), dates[0].end(), page_text)
        _add(results, "cover_end_date", dates[1].group(0), "date_order_hint", 0.55, text, dates[1].start(), dates[1].end(), page_text)

    upper = text.upper()
    for brand in active_brands:
        match = re.search(rf"\b{re.escape(brand)}\b", upper)
        if match:
            _add(results, "car_brand", brand, "vehicle_dictionary", 0.86, text, match.start(), match.end(), page_text)
            break

    for model in sorted(active_models, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(model)}\b", upper)
        if match:
            normalized = "SAGA BLM" if model in {"SAGA BLM", "BLM"} else model
            _add(results, "car_model", normalized, "vehicle_dictionary", 0.82, text, match.start(), match.end(), page_text)
            break

    messy_name = re.search(r"(?i)\bNAME\s*[:\-]\s*(?P<name>[A-Z0-9 ]{2,60}?)(?=\s+(?:CAR|VEHICLE|MODEL|REG|INSURANCE)\b|$)", text)
    if messy_name:
        _add(results, "customer_name", messy_name.group("name"), "messy_text_window", 0.82, text, messy_name.start(), messy_name.end(), page_text)

    for match in re.finditer(r"(?i)\bNCD\b[^\d]{0,15}(?P<ncd>\d{1,2}(?:\.\d+)?)\s*%?", text):
        _add(results, "ncd_percent", match.group("ncd"), "label_percent", 0.78, text, match.start(), match.end(), page_text)

    return dict(results)

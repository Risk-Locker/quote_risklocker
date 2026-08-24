"""Deterministic fixed-bounds packing for uniformly scaled benefit cards."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt


STRATEGIES = frozenset({"balanced", "square_biased", "staggered"})
ALIGNMENTS = frozenset({"start", "center", "end"})


@dataclass(frozen=True)
class GridBounds:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class GridSpec:
    strategy: str = "balanced"
    alignment: str = "center"
    aspect_ratio: float = 1.45
    reference_width: float = 180.0
    reference_height: float = 124.0
    gap_ratio: float = 0.06
    padding_ratio: float = 0.02
    stagger_ratio: float = 0.5
    empty_state: str = "hide"
    readability_scale: float = 0.22
    max_scale: float = 1.0


@dataclass(frozen=True)
class PackedCard:
    index: int
    row: int
    column: int
    x: float
    y: float
    width: float
    height: float
    scale: float


@dataclass(frozen=True)
class PackedGrid:
    bounds: GridBounds
    rows: int
    columns: int
    scale: float
    cards: tuple[PackedCard, ...]
    empty_state: str | None
    warning: str | None
    evaluated_candidates: int
    page_extension: int = 0
    paginated: bool = False
    clipped: bool = False


def _validate(count: int, bounds: GridBounds, spec: GridSpec) -> None:
    if count < 0:
        raise ValueError("Card count cannot be negative.")
    if bounds.width <= 0 or bounds.height <= 0:
        raise ValueError("Grid width and height must be positive.")
    if spec.strategy not in STRATEGIES:
        raise ValueError("Unsupported grid strategy.")
    if spec.alignment not in ALIGNMENTS:
        raise ValueError("Unsupported grid alignment.")
    if spec.reference_width <= 0 or spec.reference_height <= 0 or spec.aspect_ratio <= 0:
        raise ValueError("Reference card dimensions must be positive.")
    if not 0 <= spec.gap_ratio <= 1 or not 0 <= spec.padding_ratio < 0.5:
        raise ValueError("Grid spacing ratios are invalid.")


def _candidate_score(
    count: int,
    columns: int,
    bounds: GridBounds,
    spec: GridSpec,
) -> tuple[float, float, int, int]:
    rows = ceil(count / columns)
    pad_x = bounds.width * spec.padding_ratio
    pad_y = bounds.height * spec.padding_ratio
    usable_width = max(0.000001, bounds.width - pad_x * 2)
    usable_height = max(0.000001, bounds.height - pad_y * 2)
    gap_x = usable_width * spec.gap_ratio / max(columns, 1)
    gap_y = usable_height * spec.gap_ratio / max(rows, 1)
    stagger_extra = 0.5 if spec.strategy == "staggered" and rows > 1 and columns > 1 else 0.0
    cell_width = (usable_width - gap_x * max(columns - 1, 0)) / (columns + stagger_extra)
    cell_height = (usable_height - gap_y * max(rows - 1, 0)) / rows
    card_width = min(cell_width, cell_height * spec.aspect_ratio)
    card_height = card_width / spec.aspect_ratio
    if card_height > cell_height:
        card_height = cell_height
        card_width = card_height * spec.aspect_ratio
    raw_scale = min(card_width / spec.reference_width, card_height / spec.reference_height)
    scale = min(spec.max_scale, raw_scale)
    density_shape = abs((columns / rows) - (bounds.width / bounds.height))
    square_bias = abs(columns - rows) / max(columns, rows)
    penalty = square_bias if spec.strategy == "square_biased" else density_shape * 0.02
    return scale - penalty * 1e-6, scale, rows, columns


def _aligned_offset(extra: float, alignment: str) -> float:
    if alignment == "start":
        return 0.0
    if alignment == "end":
        return extra
    return extra / 2


def pack_fixed_grid(count: int, bounds: GridBounds, spec: GridSpec | None = None) -> PackedGrid:
    """Fit all cards in one fixed box; card dimensions are always uniform.

    Candidate column counts are evaluated once, then each card is placed once.
    The resulting work and storage are O(N), with no finite slot limit.
    """

    spec = spec or GridSpec()
    _validate(count, bounds, spec)
    if count == 0:
        return PackedGrid(bounds, 0, 0, 0.0, (), spec.empty_state, None, 0)

    # Searching all 1..N columns remains linear and avoids hidden capacity caps.
    candidates = [_candidate_score(count, columns, bounds, spec) for columns in range(1, count + 1)]
    _score, scale, rows, columns = max(candidates, key=lambda item: (item[0], -item[3]))

    pad_x = bounds.width * spec.padding_ratio
    pad_y = bounds.height * spec.padding_ratio
    usable_width = bounds.width - pad_x * 2
    usable_height = bounds.height - pad_y * 2
    gap_x = usable_width * spec.gap_ratio / max(columns, 1)
    gap_y = usable_height * spec.gap_ratio / max(rows, 1)
    stagger_extra = 0.5 if spec.strategy == "staggered" and rows > 1 and columns > 1 else 0.0
    cell_width = (usable_width - gap_x * max(columns - 1, 0)) / (columns + stagger_extra)
    cell_height = (usable_height - gap_y * max(rows - 1, 0)) / rows
    card_width = spec.reference_width * scale
    card_height = spec.reference_height * scale
    grid_width = columns * cell_width + max(columns - 1, 0) * gap_x + stagger_extra * cell_width
    grid_height = rows * cell_height + max(rows - 1, 0) * gap_y
    origin_x = bounds.x + pad_x + _aligned_offset(max(0.0, usable_width - grid_width), spec.alignment)
    origin_y = bounds.y + pad_y + _aligned_offset(max(0.0, usable_height - grid_height), spec.alignment)

    cards: list[PackedCard] = []
    for index in range(count):
        row, column = divmod(index, columns)
        row_count = min(columns, count - row * columns)
        row_width = row_count * cell_width + max(row_count - 1, 0) * gap_x
        stagger = cell_width * spec.stagger_ratio if spec.strategy == "staggered" and row % 2 else 0.0
        maximum_stagger = max(0.0, usable_width - row_width)
        stagger = min(stagger, maximum_stagger)
        row_x = origin_x + _aligned_offset(max(0.0, grid_width - row_width - stagger_extra * cell_width), spec.alignment) + stagger
        cell_x = row_x + column * (cell_width + gap_x)
        cell_y = origin_y + row * (cell_height + gap_y)
        x = cell_x + (cell_width - card_width) / 2
        y = cell_y + (cell_height - card_height) / 2
        # Floating-point safety: bounds are authoritative, never content.
        x = min(max(x, bounds.x), bounds.x + bounds.width - card_width)
        y = min(max(y, bounds.y), bounds.y + bounds.height - card_height)
        cards.append(PackedCard(index, row, column, x, y, card_width, card_height, scale))

    warning = None
    if scale < spec.readability_scale:
        warning = "Benefit cards are extremely dense and may be difficult to read at this fixed page size."
    return PackedGrid(
        bounds=bounds,
        rows=rows,
        columns=columns,
        scale=scale,
        cards=tuple(cards),
        empty_state=None,
        warning=warning,
        evaluated_candidates=len(candidates),
    )

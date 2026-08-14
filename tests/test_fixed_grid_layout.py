"""Fixed-page dynamic benefit-grid packing regression contract."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")

from app.rendering.grid_layout import GridBounds, GridSpec, pack_fixed_grid  # noqa: E402


@pytest.mark.parametrize("count", [0, 1, 2, 7, 24, 100, 1_000])
@pytest.mark.parametrize("strategy", ["balanced", "square_biased", "staggered"])
def test_every_card_stays_inside_the_same_fixed_grid(count: int, strategy: str):
    bounds = GridBounds(x=18, y=448, width=758, height=230)
    layout = pack_fixed_grid(count, bounds, GridSpec(strategy=strategy))

    assert layout.bounds == bounds
    assert len(layout.cards) == count
    assert layout.page_extension == 0
    assert layout.paginated is False
    assert layout.clipped is False
    assert len({round(card.scale, 12) for card in layout.cards}) <= 1
    for card in layout.cards:
        assert card.x >= bounds.x - 1e-8
        assert card.y >= bounds.y - 1e-8
        assert card.x + card.width <= bounds.x + bounds.width + 1e-8
        assert card.y + card.height <= bounds.y + bounds.height + 1e-8


def test_card_scale_uniformly_shrinks_as_density_increases():
    bounds = GridBounds(x=0, y=0, width=760, height=300)
    scales = [pack_fixed_grid(count, bounds, GridSpec()).scale for count in (1, 2, 8, 24, 100, 1_000)]
    assert scales == sorted(scales, reverse=True)
    assert scales[-1] > 0


def test_layout_is_deterministic_and_linear_work_is_bounded():
    bounds = GridBounds(x=10, y=20, width=500, height=180)
    first = pack_fixed_grid(1_000, bounds, GridSpec(strategy="staggered", alignment="center"))
    second = pack_fixed_grid(1_000, bounds, GridSpec(strategy="staggered", alignment="center"))
    assert first == second
    assert first.evaluated_candidates <= 1_000
    assert first.warning is not None


def test_empty_grid_has_explicit_empty_state_without_fake_card():
    layout = pack_fixed_grid(0, GridBounds(0, 0, 400, 200), GridSpec(empty_state="hide"))
    assert layout.cards == ()
    assert layout.empty_state == "hide"
    assert layout.rows == 0
    assert layout.columns == 0


def test_invalid_geometry_and_configuration_fail_closed():
    with pytest.raises(ValueError, match="positive"):
        pack_fixed_grid(2, GridBounds(0, 0, 0, 100), GridSpec())
    with pytest.raises(ValueError, match="count"):
        pack_fixed_grid(-1, GridBounds(0, 0, 100, 100), GridSpec())
    with pytest.raises(ValueError, match="strategy"):
        pack_fixed_grid(2, GridBounds(0, 0, 100, 100), GridSpec(strategy="slots"))

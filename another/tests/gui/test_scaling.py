"""Đặc tả frontend/gui/scaling.py — documents/CONTEXT.md §5.1, §5.8."""

import pytest

from tests._helpers import require_module

scaling = require_module("gui.scaling")
Viewport = scaling.Viewport


def test_logical_size():
    assert scaling.LOGICAL_SIZE == (960, 640)


def test_fit_identity():
    v = Viewport.fit(960, 640)
    assert (v.scale, v.offset_x, v.offset_y, v.width, v.height) == (1.0, 0, 0, 960, 640)


def test_fit_double():
    v = Viewport.fit(1920, 1280)
    assert (v.scale, v.offset_x, v.offset_y, v.width, v.height) == (2.0, 0, 0, 1920, 1280)


def test_fit_wide_window_letterboxes_sides():
    v = Viewport.fit(1920, 1080)
    assert v.scale == pytest.approx(1.6875)
    assert (v.width, v.height, v.offset_x, v.offset_y) == (1620, 1080, 150, 0)


def test_fit_tall_window_letterboxes_top_bottom():
    v = Viewport.fit(800, 800)
    assert v.scale == pytest.approx(800 / 960)
    assert (v.width, v.height, v.offset_x, v.offset_y) == (800, 533, 0, 133)


@pytest.mark.parametrize("size", [(0, 640), (960, 0), (-1, 5)])
def test_fit_rejects_non_positive(size):
    with pytest.raises(ValueError):
        Viewport.fit(*size)


def test_to_logical():
    v = Viewport.fit(1920, 1080)
    assert v.to_logical(150, 0) == pytest.approx((0.0, 0.0))
    assert v.to_logical(150 + 1620 / 2, 540) == pytest.approx((480.0, 320.0))
    assert v.to_logical(100, 10) is None, "click vào viền đen"
    assert v.to_logical(1770, 10) is None, "mép phải nằm ngoài canvas"


def test_roundtrip():
    v = Viewport.fit(1366, 768)
    for x, y in [(0, 0), (123.5, 456.25), (959, 639)]:
        wx, wy = v.to_window(x, y)
        assert v.to_logical(wx, wy) == pytest.approx((x, y))


def test_custom_logical_size():
    v = Viewport.fit(200, 100, logical=(100, 100))
    assert (v.scale, v.width, v.height, v.offset_x, v.offset_y) == (1.0, 100, 100, 50, 0)

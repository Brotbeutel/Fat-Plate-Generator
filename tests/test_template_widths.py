"""Template selection by key width."""
from __future__ import annotations

import json

import pytest

import fat_plate_generator as fpg
from tests.conftest import REPO_ROOT, build_model


def key(label="", w=1.0, h=1.0):
    return {"label": label, "w": w, "h": h}


@pytest.mark.parametrize(("width", "expected"), [
    (2.0, "stabilizer-2u"),
    (2.25, "stabilizer-2u"),
    (2.5, "stabilizer-2u"),
    (2.75, "stabilizer-2u"),
    (3.0, "stabilizer-2u"),
    (6.0, "spacebar-6u"),
    (6.25, "spacebar-6-25u"),
    (6.5, "spacebar-6-25u"),
    (7.0, "spacebar-7u"),
    (8.0, "spacebar-7u"),
])
def test_width_selects_template_kind(width, expected):
    kind = fpg.classify_key(key("label", w=width))
    choice = fpg.template_kind_for_key(key("label", w=width), kind, 2.0)
    assert choice.kind == expected
    assert choice.size == (
        expected.removeprefix("spacebar-") if expected.startswith("spacebar-") else None)


def test_vertical_two_unit_key_uses_the_two_unit_template():
    k = key("+", w=1.0, h=2.0)
    kind = fpg.classify_key(k)
    choice = fpg.template_kind_for_key(k, kind, 2.0)
    assert choice.kind == "stabilizer-2u"
    assert choice.substitution_reason is None


def test_label_does_not_change_spacebar_classification():
    assert fpg.classify_key(key("Space", w=6.25)) == fpg.KIND_SPACEBAR
    assert fpg.classify_key(key("", w=6.25)) == fpg.KIND_SPACEBAR


@pytest.mark.parametrize("width", [3.25, 4.0, 5.0, 6.1, 6.75, 7.25, 9.0])
def test_unsupported_width_is_rejected_when_selecting_template(width):
    k = key("example", w=width)
    with pytest.raises(ValueError, match=r"unsupported key width.*supported widths"):
        fpg.template_kind_for_key(k, fpg.classify_key(k), 2.0)


def test_vertical_spacebar_width_is_rejected():
    k = key("vertical", w=1.0, h=6.0)
    with pytest.raises(ValueError, match=r"unsupported key width"):
        fpg.template_kind_for_key(k, fpg.classify_key(k), 2.0)


def test_three_unit_key_records_substitution(tmp_path):
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps([[{"w": 3}, "Three"]]), encoding="utf-8")
    model = build_model(layout)
    assert len(model.substitutions) == 1
    assert "3u key (1" in model.substitutions[0]
    assert "2u template is used instead" in model.substitutions[0]
    assert model.templates["stabilizer-2u"].path == (
        REPO_ROOT / fpg.DEFAULT_STABILIZER_2U
    )


def test_seven_unit_spacebar_has_no_off_center_template(tmp_path):
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps([[{"w": 7}, "Space"]]), encoding="utf-8")
    with pytest.raises(ValueError, match="no off-centered template for 7u spacebars"):
        build_model(layout, spacebar_position="off-centered-left")

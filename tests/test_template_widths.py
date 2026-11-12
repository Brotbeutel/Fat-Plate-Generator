"""Template selection by key width."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon

import fat_plate_generator as fpg
from tests.conftest import REPO_ROOT, build_model


def key(label="", w=1.0, h=1.0):
    return {"label": label, "w": w, "h": h}


@pytest.mark.parametrize(("width", "expected"), [
    (2.0, "stabilizer-2u"),
    (2.25, "stabilizer-2u"),
    (2.5, "stabilizer-2u"),
    (2.75, "stabilizer-2u"),
    (3.0, "stabilizer-3u"),
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


def test_label_does_not_change_spacebar_classification():
    assert fpg.classify_key(key("Space", w=6.25)) == fpg.KIND_SPACEBAR
    assert fpg.classify_key(key("", w=6.25)) == fpg.KIND_SPACEBAR


@pytest.mark.parametrize("width", [3.25, 4.0, 5.0, 6.1, 6.75, 7.25, 9.0])
def test_unsupported_width_is_rejected_when_selecting_template(width):
    k = key("example", w=width)
    with pytest.raises(ValueError, match=r"unsupported key width.*supported widths"):
        fpg.template_kind_for_key(k, fpg.classify_key(k), 2.0)


@pytest.mark.parametrize("width", [3.25, 4.0])
def test_unsupported_width_error_lists_3u_as_supported(width):
    k = key("example", w=width)
    with pytest.raises(ValueError, match=r"supported widths are .*\b3u\b"):
        fpg.template_kind_for_key(k, fpg.classify_key(k), 2.0)


def test_vertical_spacebar_width_is_rejected():
    k = key("vertical", w=1.0, h=6.0)
    with pytest.raises(ValueError, match=r"unsupported key width"):
        fpg.template_kind_for_key(k, fpg.classify_key(k), 2.0)


# --------------------------------------------------------------------------
# 3u CAD tests
# --------------------------------------------------------------------------
def test_three_unit_key_builds_with_its_own_template(tmp_path):
    """A 3u key uses the stabilizer-3u template, not a substitute."""
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps([["Q", "W"], [{"w": 3}, "Tab3"]]),
                      encoding="utf-8")
    model = build_model(layout)
    assert "stabilizer-3u" in model.templates
    assert model.templates["stabilizer-3u"].path == (
        REPO_ROOT / fpg.DEFAULT_STABILIZER_3U
    )


def test_three_unit_cavity_has_template_width(tmp_path):
    """The cavity of a 3u key matches the cutter width from load_template()."""
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps([["Q", "W"], [{"w": 3}, "Tab3"]]),
                      encoding="utf-8")
    model = build_model(layout)
    template = model.templates["stabilizer-3u"]
    # Build the cutter at identity to get its unrotated bounding box
    cutter = fpg.template_cutter(template, fpg.IDENTITY_MATRIX)
    cutter_bb = cutter.BoundingBox()
    cutter_width = cutter_bb.xmax - cutter_bb.xmin
    # Find the 3u key's cavity
    three_u_index = next(i for i, k in enumerate(model.keys) if k["w"] == 3.0)
    cavity_bb = model.cavities[three_u_index].BoundingBox()
    cavity_width = cavity_bb.xmax - cavity_bb.xmin
    assert abs(cavity_width - cutter_width) < 1e-3


def test_three_unit_cavity_inside_footprint(tmp_path):
    """The cavity of a 3u key lies inside the plate outline."""
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps([["Q", "W"], [{"w": 3}, "Tab3"]]),
                      encoding="utf-8")
    model = build_model(layout)
    three_u_index = next(i for i, k in enumerate(model.keys) if k["w"] == 3.0)
    cavity_bb = model.cavities[three_u_index].BoundingBox()
    cavity_box = Polygon([
        (cavity_bb.xmin, cavity_bb.ymin), (cavity_bb.xmax, cavity_bb.ymin),
        (cavity_bb.xmax, cavity_bb.ymax), (cavity_bb.xmin, cavity_bb.ymax),
    ])
    assert model.footprint.contains(cavity_box)


def test_three_unit_export_passes_stl_check(tmp_path):
    """generate() with a 3u key ends with 'Done.' and no warnings."""
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps([["Q", "W"], [{"w": 3}, "Tab3"]]),
                      encoding="utf-8")
    output = tmp_path / "plate.stl"
    old_stdout, old_stderr = sys.stdout, sys.stderr
    captured_out = io.StringIO()
    captured_err = io.StringIO()
    sys.stdout = captured_out
    sys.stderr = captured_err
    try:
        fpg.generate(layout, fpg.Settings(templates=fpg.TemplateSet.defaults(REPO_ROOT)),
                     output=output)
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
    stdout_text = captured_out.getvalue()
    stderr_text = captured_err.getvalue()
    assert "Done." in stdout_text
    assert "Done, with warnings." not in stdout_text
    assert "stabilizer_3-00u.stl" in stdout_text
    assert "WARNING" not in stderr_text
    mesh, problems = fpg.check_exported_stl(output)
    assert problems == []


def test_vertical_three_unit_key_cavity_runs_along_y(tmp_path):
    """A vertical 3u key (h=3) has its cavity elongated along Y."""
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps([["Q", {"h": 3}, "V3"]]),
                      encoding="utf-8")
    model = build_model(layout)
    v3_index = next(i for i, k in enumerate(model.keys) if k["h"] == 3.0)
    cavity_bb = model.cavities[v3_index].BoundingBox()
    cavity_width = cavity_bb.xmax - cavity_bb.xmin
    cavity_height = cavity_bb.ymax - cavity_bb.ymin
    # The vertical key has its longer axis along Y
    assert cavity_height > cavity_width


def test_seven_unit_spacebar_has_no_off_center_template(tmp_path):
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps([[{"w": 7}, "Space"]]), encoding="utf-8")
    with pytest.raises(ValueError, match="no off-centered template for 7u spacebars"):
        build_model(layout, spacebar_position="off-centered-left")

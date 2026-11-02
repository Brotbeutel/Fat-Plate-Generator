"""Stepped keys (KLE "l": true, for example a stepped Caps Lock)."""
from __future__ import annotations

import json

import pytest
from shapely.affinity import affine_transform, translate
from shapely.geometry import Polygon

import fat_plate_generator as fpg
from fat_plate_generator import OrientationConfig, TemplateError
from tests.conftest import REPO_ROOT, build_model
from tests.test_plate import projected_outline, run_cli
from tests.test_templates import L_OUTLINE, box_mesh, l_shape_mesh, write_mesh

STEPPED_LAYOUT = REPO_ROOT / "tests" / "layouts" / "stepped_capslock.json"
STEPPED_JSON = REPO_ROOT / "KLE-exports" / "keyboard-layout_ISO_105_stepped_capslock.json"


def keys_of(text):
    return fpg.parse_kle(json.loads(text))


@pytest.fixture
def wide_shift_template(tmp_path):
    """An asymmetric stand-in for switch_socket_wide-shift.stl (an L)."""
    return write_mesh(l_shape_mesh(), tmp_path / "wide-shift.stl")


# --------------------------------------------------------------------------
# reading the flag
# --------------------------------------------------------------------------
def test_the_stepped_flag_is_read_and_only_applies_to_its_key():
    keys = keys_of('[[{"w": 1.25, "w2": 1.75, "l": true}, "Caps Lock", {"x": 0.5}, "A", "S"]]')
    assert [k["l"] for k in keys] == [True, False, False]
    caps = keys[0]
    assert (caps["w"], caps["w2"], caps["x2"]) == (1.25, 1.75, 0.0)


def test_keys_without_the_flag_are_not_stepped():
    assert [k["l"] for k in keys_of('[["A", {"w": 2}, "B"], ["C"]]')] == [False, False, False]
    assert keys_of('[[{"l": false}, "A"]]')[0]["l"] is False


def test_the_exported_stepped_caps_lock_json():
    keys = fpg.parse_kle(json.loads(STEPPED_JSON.read_text(encoding="utf-8")))
    stepped = [k for k in keys if k["l"]]
    assert [(k["label"], k["w"], k["w2"]) for k in stepped] == [("Caps Lock", 1.25, 1.75)]
    a = [k for k in keys if k["label"] == "A"][0]
    assert a["x"] == pytest.approx(1.75)                 # the plate outline is 1.75u wide


# --------------------------------------------------------------------------
# classification and position
# --------------------------------------------------------------------------
def key(label="x", **kwargs):
    return {"label": label, "w": 1.0, "h": 1.0, "x2": 0.0, "y2": 0.0, "w2": 1.0, "h2": 1.0, "l": False,
            "r": 0.0, "rx": 0.0, "ry": 0.0, "x": 0.0, "y": 0.0, **kwargs}


@pytest.mark.parametrize("stepped, kind", [
    ("standard", fpg.KIND_NORMAL), ("wide-shift", fpg.KIND_WIDE_SHIFT)])
def test_a_stepped_key_is_classified_by_the_mode(stepped, kind):
    caps = key("Caps Lock", w=1.25, w2=1.75, l=True)
    assert fpg.classify_key(caps, stepped=stepped) == kind


def test_other_keys_are_not_affected_by_the_mode():
    for mode in fpg.STEPPED_MODES:
        assert fpg.classify_key(key("A"), stepped=mode) == fpg.KIND_NORMAL
        assert fpg.classify_key(key("Shift", w=2.25, l=True), stepped=mode) == fpg.KIND_STABILIZED
        assert fpg.classify_key(key("", w=6.25, l=True), stepped=mode) == fpg.KIND_SPACEBAR
    assert fpg.classify_key(key("Caps Lock", w=1.25, w2=1.75, l=True)) == fpg.KIND_NORMAL   # default mode


def test_the_two_switch_centres():
    caps = key("Caps Lock", x=2.0, y=3.0, w=1.25, w2=1.75, l=True)
    assert fpg.switch_center(caps) == pytest.approx((2.625 * fpg.UNIT, 3.5 * fpg.UNIT))             # w
    assert fpg.switch_center(caps, second=True) == pytest.approx((2.875 * fpg.UNIT, 3.5 * fpg.UNIT))  # w2


def test_the_second_centre_follows_the_second_rectangle():
    iso_enter = key("Enter", x=10.0, y=1.0, w=1.25, h=2.0, x2=-0.25, w2=1.5)
    assert fpg.switch_center(iso_enter, second=True) == pytest.approx(
        ((10.0 - 0.25 + 0.75) * fpg.UNIT, (1.0 + 0.5) * fpg.UNIT))


def test_the_rotation_applies_to_the_second_centre_too():
    turned = key("x", x=1.0, w=1.25, w2=1.75, l=True, r=90.0, rx=1.0, ry=0.0)
    cx, cy = fpg.switch_center(turned, second=True)
    assert (cx, cy) == pytest.approx((1.0 * fpg.UNIT - 0.5 * fpg.UNIT, 0.875 * fpg.UNIT), abs=1e-9)


# --------------------------------------------------------------------------
# the plate
# --------------------------------------------------------------------------
def test_standard_mode_keeps_the_normal_socket_at_w(wide_shift_template):
    model = build_model(STEPPED_LAYOUT, stepped_key="standard", wide_shift_socket_path=wide_shift_template)
    assert model.kinds == [fpg.KIND_NORMAL] * 3
    assert "wide-shift" not in model.templates
    outline = projected_outline(model.cavities[0])
    assert outline.centroid.x == pytest.approx(model.centers[0][0], abs=1e-3)      # symmetric socket


def test_wide_shift_mode_moves_the_switch_to_the_centre_of_w2(wide_shift_template):
    standard = build_model(STEPPED_LAYOUT, stepped_key="standard")
    wide = build_model(STEPPED_LAYOUT, stepped_key="wide-shift", wide_shift_socket_path=wide_shift_template)
    assert wide.kinds == [fpg.KIND_WIDE_SHIFT, fpg.KIND_NORMAL, fpg.KIND_NORMAL]
    assert wide.rotations[0] == 180 and wide.rotations[1:] == [None, None]
    assert wide.centers[0][0] - standard.centers[0][0] == pytest.approx(0.25 * fpg.UNIT)   # 1.75u - 1.25u, halved
    assert wide.centers[0][1] == pytest.approx(standard.centers[0][1])
    for other_wide, other_standard in zip(wide.centers[1:], standard.centers[1:]):
        assert other_wide == pytest.approx(other_standard)


def test_the_plate_outline_covers_both_rectangles_in_every_mode(wide_shift_template):
    standard = build_model(STEPPED_LAYOUT, stepped_key="standard")
    wide = build_model(STEPPED_LAYOUT, stepped_key="wide-shift", wide_shift_socket_path=wide_shift_template)
    assert standard.footprint.symmetric_difference(wide.footprint).area < 1e-9
    width = standard.footprint.bounds[2] - standard.footprint.bounds[0]
    assert width == pytest.approx((1.75 + 1.0 + 1.0 + 0.0) * fpg.UNIT + 2 * fpg.DEFAULT_MARGIN)  # 1.75u, A, S


def affine(polygon, matrix):
    a, b, d, e = matrix
    return affine_transform(polygon, [a, b, d, e, 0, 0])


@pytest.mark.parametrize("global_rotation", [0, 180])
@pytest.mark.parametrize("wide_shift_rotation", [0, 90, 180, 270])
def test_the_wide_shift_socket_is_turned_never_mirrored(wide_shift_template, global_rotation, wide_shift_rotation):
    config = OrientationConfig(global_rotation=global_rotation, wide_shift_rotation=wide_shift_rotation)
    model = build_model(STEPPED_LAYOUT, stepped_key="wide-shift",
                        wide_shift_socket_path=wide_shift_template, orientation=config)
    cx, cy = model.centers[0]
    turned = fpg.matrix_multiply(fpg.plate_rotation_matrix(config), fpg.rotation_matrix(wide_shift_rotation))
    expected = translate(affine(Polygon(L_OUTLINE), turned), cx, cy)
    found = projected_outline(model.cavities[0])
    assert found.symmetric_difference(expected).area < 1e-6
    mirrored = translate(affine(Polygon(L_OUTLINE), fpg.matrix_multiply(model.matrix,
                                                                      fpg.rotation_matrix(wide_shift_rotation))), cx, cy)
    assert found.symmetric_difference(mirrored).area > 1.0


def test_by_default_the_wide_shift_template_comes_out_as_designed(wide_shift_template):
    model = build_model(STEPPED_LAYOUT, stepped_key="wide-shift", wide_shift_socket_path=wide_shift_template)
    cx, cy = model.centers[0]
    found = projected_outline(model.cavities[0])
    assert found.symmetric_difference(translate(Polygon(L_OUTLINE), cx, cy)).area < 1e-6


def test_the_wide_shift_template_is_only_needed_when_it_is_used(tmp_path):
    missing = tmp_path / "missing.stl"
    build_model(STEPPED_LAYOUT, stepped_key="standard", wide_shift_socket_path=missing)       # no error
    build_model(REPO_ROOT / "tests" / "layouts" / "stabilizer_orientation.json",
                stepped_key="wide-shift", wide_shift_socket_path=missing)                    # no stepped key
    with pytest.raises(TemplateError, match="not found"):
        build_model(STEPPED_LAYOUT, stepped_key="wide-shift", wide_shift_socket_path=missing)


def test_the_wide_shift_template_is_looked_up_next_to_the_socket(tmp_path, wide_shift_template):
    folder = tmp_path / "templates"
    folder.mkdir()
    (folder / fpg.DEFAULT_SOCKET_WIDE_SHIFT).write_bytes(wide_shift_template.read_bytes())
    (folder / fpg.DEFAULT_SOCKET).write_bytes((REPO_ROOT / fpg.DEFAULT_SOCKET).read_bytes())
    model = fpg.build_plate_model(STEPPED_LAYOUT, folder / fpg.DEFAULT_SOCKET, REPO_ROOT / fpg.DEFAULT_STABILIZER,
                                  {p: REPO_ROOT / fpg.DEFAULT_SPACEBAR_CENTERED for p in fpg.SPACEBAR_POSITIONS},
                                  stepped_key="wide-shift")
    assert model.templates["wide-shift"].path == folder / fpg.DEFAULT_SOCKET_WIDE_SHIFT


def test_an_unknown_stepped_mode_is_refused():
    with pytest.raises(ValueError, match="stepped_key"):
        build_model(STEPPED_LAYOUT, stepped_key="sideways")


# --------------------------------------------------------------------------
# bounding box of the wide-shift template: only the height is fixed so far
# --------------------------------------------------------------------------
def test_the_wide_shift_box_is_not_checked_in_x_and_y(tmp_path):
    path = write_mesh(box_mesh(23.0, 17.0, fpg.PLATE_Z_MIN, fpg.PLATE_Z_MAX), tmp_path / "w.stl")
    assert fpg.load_template(path, "wide-shift").warnings == []


def test_the_wide_shift_height_is_checked(tmp_path):
    path = write_mesh(box_mesh(23.0, 17.0, fpg.PLATE_Z_MIN, fpg.PLATE_Z_MAX + 0.5), tmp_path / "w.stl")
    assert any("bounding box top" in w for w in fpg.load_template(path, "wide-shift").warnings)


# --------------------------------------------------------------------------
# configuration and CLI
# --------------------------------------------------------------------------
def test_the_wide_shift_rotation_default_and_validation():
    assert OrientationConfig().wide_shift_rotation == 180
    with pytest.raises(ValueError):
        OrientationConfig(wide_shift_rotation=45)


def test_cli_standard_mode_needs_no_wide_shift_template(repo_root, tmp_path):
    result = run_cli(repo_root, "--json", str(STEPPED_LAYOUT), "--output", str(tmp_path / "x.stl"))
    assert result.returncode == 0, result.stderr
    assert "Stepped keys:    1, standard socket at the centre of w" in result.stdout


def test_cli_wide_shift_mode(repo_root, tmp_path, wide_shift_template):
    result = run_cli(repo_root, "--json", str(STEPPED_LAYOUT), "--output", str(tmp_path / "x.stl"),
                     "--stepped-key", "wide-shift", "--socket-wide-shift", str(wide_shift_template),
                     "--wide-shift-rotation", "90")
    assert result.returncode == 0, result.stderr
    assert "Stepped keys:    1, wide-shift socket at the centre of w2 (rotation 90 deg)" in result.stdout


def test_cli_wide_shift_mode_without_the_template_says_so(repo_root, tmp_path):
    result = run_cli(repo_root, "--json", str(STEPPED_LAYOUT), "--output", str(tmp_path / "x.stl"),
                     "--stepped-key", "wide-shift", "--socket-wide-shift", str(tmp_path / "missing.stl"))
    assert result.returncode != 0
    assert "template STL not found" in result.stderr

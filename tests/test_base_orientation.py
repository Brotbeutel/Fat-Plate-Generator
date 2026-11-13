"""Fixed base orientation and additional rotations (offsets), WP-17.

The rotation options are offsets on top of a fixed base orientation
(KLE_TO_CAD_MATRIX, CUTOUT_FRAME_ROTATION, TEMPLATE_BASE_ROTATION).  With the
default settings every plate must stay exactly what it was before WP-17, so the
expected matrices below are the literal tuples that were in effect then.
"""
from __future__ import annotations

import pytest
from shapely.affinity import affine_transform, rotate, translate
from shapely.geometry import Polygon

import fat_plate_generator as fpg
from fat_plate_generator import OrientationConfig
from tests.conftest import REPO_ROOT
from tests.test_plate import projected_outline, run_cli
from tests.test_templates import L_OUTLINE, l_shape_mesh, write_mesh

R = fpg.rotation_matrix
mul = fpg.matrix_multiply


def key(label="x", w=1.0, h=1.0, **extra):
    return {"label": label, "w": w, "h": h, **extra}


# class -> (key, kind, total matrix a cutout got on origin/main with the default settings)
BEFORE_WP17 = {
    "horizontal": (key(w=2), fpg.KIND_STABILIZED, (1, 0, 0, 1)),
    "vertical": (key(h=2), fpg.KIND_STABILIZED, (0, 1, -1, 0)),
    "spacebar": (key("", w=6.25), fpg.KIND_SPACEBAR, (1, 0, 0, 1)),
    "wide-caps": (key(l=True), fpg.KIND_WIDE_CAPS, (1, 0, 0, 1)),
    "socket": (key(), fpg.KIND_NORMAL, (-1, 0, 0, -1)),
}
OFFSET_FIELD = {"horizontal": "stab_rotation_horizontal", "vertical": "stab_rotation_vertical",
                "spacebar": "stab_rotation_spacebar", "wide-caps": "wide_caps_rotation"}


def total_matrix(k, kind, config):
    """Matrix a cutout gets in the plate: its class rotation, then the plate rotation."""
    pm = fpg.plate_rotation_matrix(config)
    rotation = fpg.rotation_for_kind(k, kind, config)
    return pm if rotation is None else mul(pm, R(rotation))


# --------------------------------------------------------------------------
# equivalence with the matrices of origin/main (no CAD)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", list(BEFORE_WP17))
def test_default_matrices_equal_the_ones_before_wp17(name):
    k, kind, before = BEFORE_WP17[name]
    assert total_matrix(k, kind, OrientationConfig()) == before


def test_default_plate_matrices_equal_the_ones_before_wp17():
    assert fpg.global_matrix(OrientationConfig()) == (1, 0, 0, -1)
    assert fpg.plate_rotation_matrix(OrientationConfig()) == (-1, 0, 0, -1)


def test_rotation_classes():
    assert [fpg.cutout_rotation_class(k, kind) for k, kind, _ in BEFORE_WP17.values()] == [
        "horizontal", "vertical", "spacebar", "wide-caps", None]
    square = key(w=2, h=2)           # square keys count as vertical, as before
    assert fpg.cutout_rotation_class(square, fpg.KIND_STABILIZED) == "vertical"


# --------------------------------------------------------------------------
# the options are offsets
# --------------------------------------------------------------------------
def test_an_offset_turns_the_cutout_on_top_of_the_base_rotation():
    k, kind, _ = BEFORE_WP17["horizontal"]
    assert total_matrix(k, kind, OrientationConfig(stab_rotation_horizontal=180)) == (-1, 0, 0, -1)
    k, kind, _ = BEFORE_WP17["wide-caps"]
    assert total_matrix(k, kind, OrientationConfig(wide_caps_rotation=90)) == (0, -1, 1, 0)
    k, kind, _ = BEFORE_WP17["vertical"]
    assert total_matrix(k, kind, OrientationConfig(stab_rotation_vertical=180)) == (0, -1, 1, 0)


@pytest.mark.parametrize("name", ["horizontal", "vertical", "spacebar", "wide-caps"])
@pytest.mark.parametrize("offset", [0, 90, 180, 270])
def test_the_effective_rotation_is_base_plus_offset(name, offset):
    k, kind, _ = BEFORE_WP17[name]
    config = OrientationConfig(**{OFFSET_FIELD[name]: offset})
    assert fpg.rotation_for_kind(k, kind, config) == (fpg.TEMPLATE_BASE_ROTATION[name] + offset) % 360


def test_a_normal_socket_has_no_class_rotation_and_gets_only_the_plate_rotation():
    k, kind, _ = BEFORE_WP17["socket"]
    config = OrientationConfig(stab_rotation_horizontal=90, stab_rotation_vertical=90,
                               stab_rotation_spacebar=90, wide_caps_rotation=90)
    assert fpg.rotation_for_kind(k, kind, config) is None
    assert total_matrix(k, kind, config) == fpg.plate_rotation_matrix(config)


def test_global_rotation_turns_the_finished_plate():
    config = OrientationConfig(global_rotation=90)
    assert fpg.global_matrix(config) == (0, 1, 1, 0)
    assert fpg.plate_rotation_matrix(config) == mul(R(90), R(180)) == (0, 1, -1, 0)
    # outline and cutouts get the same rotation on top of what they had by default
    for turn in (0, 90, 180, 270):
        config = OrientationConfig(global_rotation=turn)
        assert fpg.global_matrix(config) == mul(R(turn), fpg.KLE_TO_CAD_MATRIX)
        assert fpg.plate_rotation_matrix(config) == mul(R(turn), R(fpg.CUTOUT_FRAME_ROTATION))


def test_the_mirror_only_reaches_the_outline_and_the_switch_positions():
    config = OrientationConfig(global_mirror_x=True)
    assert fpg.global_matrix(config) == mul(fpg.MIRROR_X_MATRIX, fpg.KLE_TO_CAD_MATRIX) == (-1, 0, 0, -1)
    assert fpg.plate_rotation_matrix(config) == fpg.plate_rotation_matrix(OrientationConfig())


def test_global_transform_off_skips_the_whole_conversion():
    config = OrientationConfig(global_transform=False)
    assert fpg.global_matrix(config) == fpg.IDENTITY_MATRIX
    assert fpg.plate_rotation_matrix(config) == fpg.IDENTITY_MATRIX
    # the class rotations still apply, as before
    k, kind, _ = BEFORE_WP17["horizontal"]
    assert total_matrix(k, kind, config) == R(fpg.TEMPLATE_BASE_ROTATION["horizontal"])
    k, kind, _ = BEFORE_WP17["vertical"]
    assert total_matrix(k, kind, config) == R(fpg.TEMPLATE_BASE_ROTATION["vertical"])


@pytest.mark.parametrize("name", ["horizontal", "vertical", "spacebar", "wide-caps"])
@pytest.mark.parametrize("old_value", [0, 90, 180, 270])
def test_conversion_table_old_value_to_new_value(name, old_value):
    """Old calls gave the class rotation as an absolute value r and the plate rotated by 180
    (pm = R(180)).  The new offset is r minus the base rotation, modulo 360, and gives the
    same matrix.  Horizontal, spacebar, wide-caps: minus 180; vertical: minus 90."""
    k, kind, _ = BEFORE_WP17[name]
    new_value = (old_value - fpg.TEMPLATE_BASE_ROTATION[name]) % 360
    assert new_value == (old_value - {"vertical": 90}.get(name, 180)) % 360
    config = OrientationConfig(**{OFFSET_FIELD[name]: new_value})
    assert total_matrix(k, kind, config) == mul(R(180), R(old_value))


# --------------------------------------------------------------------------
# through the real pipeline (CAD): an asymmetric template, one key per case
# --------------------------------------------------------------------------
LAYOUTS = {
    "horizontal": '[[{"w": 2}, "x"]]',
    "vertical": '[[{"h": 2}, "x"]]',
    "spacebar": '[[{"w": 6.25}, ""]]',
    "wide-caps": '[[{"w": 1.25, "w2": 1.75, "l": true}, "x"]]',
    "socket": '[["x"]]',
}


def l_settings(tmp_path, **kwargs):
    template = write_mesh(l_shape_mesh(), tmp_path / "l.stl")
    templates = fpg.TemplateSet.defaults(REPO_ROOT).replace(
        socket=template, wide_caps=template, stabilizer_2u=template,
        spacebar_6u_centered=template, spacebar_6u_off_centered=template,
        spacebar_6_25u_centered=template, spacebar_6_25u_off_centered=template,
        spacebar_7u_centered=template)
    return fpg.Settings(templates=templates, stepped_key="wide-caps", **kwargs)


def build_l_model(tmp_path, case, orientation=None, layout=None):
    path = tmp_path / "layout.json"
    path.write_text(layout or LAYOUTS[case], encoding="utf-8")
    settings = l_settings(tmp_path, orientation=orientation or OrientationConfig())
    return fpg.build_plate_model(path, settings)


def affine(polygon, matrix):
    a, b, d, e = matrix
    return affine_transform(polygon, [a, b, d, e, 0, 0])


@pytest.mark.parametrize("case", list(BEFORE_WP17))
def test_default_cutouts_are_the_ones_before_wp17(tmp_path, case):
    """The real pipeline with the default settings turns the template by the literal matrix
    of origin/main (the L is asymmetric, so any other turn or a mirror would show)."""
    model = build_l_model(tmp_path, case)
    (cx, cy) = model.centers[0]
    expected = translate(affine(Polygon(L_OUTLINE), BEFORE_WP17[case][2]), cx, cy)
    assert projected_outline(model.cavities[0]).symmetric_difference(expected).area < 1e-6


@pytest.mark.parametrize("offset", [90, 180, 270])
@pytest.mark.parametrize("case", ["horizontal", "vertical", "spacebar", "wide-caps"])
def test_an_offset_turns_the_cutout_about_its_switch_centre(tmp_path, case, offset):
    """Counter-clockwise, seen from above, and about the switch centre."""
    default = build_l_model(tmp_path, case)
    turned = build_l_model(tmp_path, case, OrientationConfig(**{OFFSET_FIELD[case]: offset}))
    assert turned.centers == default.centers
    cx, cy = default.centers[0]
    expected = rotate(projected_outline(default.cavities[0]), offset, origin=(cx, cy))
    assert projected_outline(turned.cavities[0]).symmetric_difference(expected).area < 1e-6
    assert turned.footprint.symmetric_difference(default.footprint).area < 1e-9      # outline unchanged


def test_the_mirror_changes_outline_and_positions_but_never_a_cutout(tmp_path):
    layout = '[["A", {"w": 2}, "x"]]'                      # the stabilizer key is not centred
    plain = build_l_model(tmp_path, "horizontal", layout=layout)
    mirrored = build_l_model(tmp_path, "horizontal", OrientationConfig(global_mirror_x=True), layout)
    width = plain.footprint.bounds[2]
    assert mirrored.footprint.bounds[:2] == pytest.approx((0.0, 0.0), abs=1e-9)
    assert mirrored.footprint.bounds[2] == pytest.approx(width)
    # positions: mirrored along X inside the plate, Y unchanged
    for (px, py), (mx, my) in zip(plain.centers, mirrored.centers):
        assert (mx, my) == pytest.approx((width - px, py), abs=1e-9)
    assert plain.centers[0][0] != pytest.approx(mirrored.centers[0][0])
    # outline: the mirror image of the default outline
    flipped = translate(affine(plain.footprint, fpg.MIRROR_X_MATRIX), width, 0)
    assert mirrored.footprint.symmetric_difference(flipped).area < 1e-6
    # cutouts: only moved, still the unmirrored template
    for model in (plain, mirrored):
        index = 1                                          # the stabilizer key
        cx, cy = model.centers[index]
        expected = translate(affine(Polygon(L_OUTLINE), total_matrix(
            *BEFORE_WP17["horizontal"][:2], OrientationConfig())), cx, cy)
        assert projected_outline(model.cavities[index]).symmetric_difference(expected).area < 1e-6


# --------------------------------------------------------------------------
# header output
# --------------------------------------------------------------------------
def run_header(repo_root, tmp_path, *options):
    layout = tmp_path / "one.json"
    layout.write_text('[["A"]]', encoding="utf-8")
    result = run_cli(repo_root, "--json", str(layout), "--output", str(tmp_path / "one.stl"), *options)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_the_header_shows_the_offsets_and_the_built_in_flip(repo_root, tmp_path):
    out = run_header(repo_root, tmp_path)
    assert "Stab rotation:   horizontal 0 deg, vertical 0 deg, spacebar 0 deg" in out
    assert "Plate transform: rotate 0 deg, mirror X off (KLE y flip built in, matrix (1, 0, 0, -1))" in out


def test_the_header_shows_additional_rotation_and_mirror(repo_root, tmp_path):
    out = run_header(repo_root, tmp_path, "--global-rotation", "90", "--global-mirror-x")
    matrix = fpg.global_matrix(OrientationConfig(global_rotation=90, global_mirror_x=True))
    assert f"Plate transform: rotate 90 deg, mirror X on (KLE y flip built in, matrix {matrix})" in out


def test_the_header_without_the_global_transform(repo_root, tmp_path):
    out = run_header(repo_root, tmp_path, "--no-global-transform")
    assert "Plate transform: none (--no-global-transform)" in out

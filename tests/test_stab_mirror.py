"""Stabilizer mirror (WP-18): stab_mirror_horizontal / stab_mirror_vertical.

The mirror is made in the template's own coordinates along its long axis,
(x, y) -> (x, -y), before the base orientation and the rotations.  All current
stabilizer templates are symmetric left/right, so for them it equals another
rotation of 180 deg of the same class; a synthetic asymmetric template shows
that it is a real mirror and not a rotation.
"""
from __future__ import annotations

import pytest
from shapely.affinity import translate
from shapely.geometry import Polygon

import fat_plate_generator as fpg
from fat_plate_generator import OrientationConfig
from tests.conftest import ORIENTATION_LAYOUT, build_model
from tests.test_base_orientation import affine, build_l_model, key, run_header
from tests.test_plate import projected_outline
from tests.test_templates import L_OUTLINE, cutter_mesh, l_shape_mesh, section_polygon, write_mesh

R = fpg.rotation_matrix
mul = fpg.matrix_multiply

HORIZONTAL = ["2u", "2.25u", "2.75u"]            # KIND_STABILIZED with w > h
VERTICAL = ["2u vertical", "ISO Enter"]          # KIND_STABILIZED with w <= h
NOT_MIRRORED = ["1u", "Caps Lock", ""]           # sockets and the spacebar


# --------------------------------------------------------------------------
# which keys are mirrored
# --------------------------------------------------------------------------
def test_the_mirror_matrix_is_the_y_mirror():
    assert fpg.MIRROR_Y_MATRIX == (1, 0, 0, -1)
    a, b, d, e = fpg.MIRROR_Y_MATRIX
    assert a * e - b * d == -1                    # a mirror, not a rotation


@pytest.mark.parametrize("horizontal, vertical", [(False, False), (True, False), (False, True), (True, True)])
def test_the_decision_per_key_class(horizontal, vertical):
    config = OrientationConfig(stab_mirror_horizontal=horizontal, stab_mirror_vertical=vertical)
    keys = {
        "horizontal 2u": (key(w=2), horizontal),
        "horizontal 3u": (key(w=3), horizontal),
        "vertical 2u": (key(h=2), vertical),
        "vertical 3u": (key(h=3), vertical),
        "square 2x2 counts as vertical": (key(w=2, h=2), vertical),
        "spacebar": (key("", w=6.25), False),
        "wide-caps": (key(l=True), False),
        "socket": (key(), False),
        "caps lock": (key("Caps Lock", w=1.75), False),
    }
    for name, (k, expected) in keys.items():
        kind = fpg.classify_key(k, 1.75, "wide-caps")
        assert fpg.stabilizer_mirror(k, kind, config) is expected, name


@pytest.fixture(scope="module", params=[(False, False), (True, False), (False, True), (True, True)],
                ids=["off", "horizontal", "vertical", "both"])
def mirror_model(request):
    horizontal, vertical = request.param
    model = build_model(ORIENTATION_LAYOUT, orientation=OrientationConfig(
        stab_mirror_horizontal=horizontal, stab_mirror_vertical=vertical))
    return model, request.param


def test_exactly_the_selected_stabilizers_are_mirrored(mirror_model):
    model, (horizontal, vertical) = mirror_model
    labels = [k["label"] for k in model.keys]
    assert sorted(labels) == sorted(HORIZONTAL + VERTICAL + NOT_MIRRORED)
    mirrored = [label for label, flag in zip(labels, model.mirrored) if flag]
    assert sorted(mirrored) == sorted((HORIZONTAL if horizontal else []) + (VERTICAL if vertical else []))
    assert len(model.mirrored) == len(model.keys)


def test_the_mirror_changes_neither_rotations_nor_positions(mirror_model, orientation_model):
    model, _ = mirror_model
    assert model.rotations == orientation_model.rotations
    assert model.centers == orientation_model.centers
    assert model.footprint.symmetric_difference(orientation_model.footprint).area < 1e-9


def test_by_default_nothing_but_the_left_spacebar_is_mirrored(orientation_model):
    assert not any(orientation_model.mirrored)
    left = build_model(ORIENTATION_LAYOUT, spacebar_position="off-centered-left")
    assert left.mirrored == [kind == fpg.KIND_SPACEBAR for kind in left.kinds]


def test_the_left_spacebar_stays_mirrored_when_stabilizers_are_too():
    both = build_model(ORIENTATION_LAYOUT, spacebar_position="off-centered-left", orientation=OrientationConfig(
        stab_mirror_horizontal=True, stab_mirror_vertical=True))
    assert all(both.mirrored[i] for i, kind in enumerate(both.kinds)
               if kind in (fpg.KIND_SPACEBAR, fpg.KIND_STABILIZED))
    assert not any(flag for flag, kind in zip(both.mirrored, both.kinds) if kind == fpg.KIND_NORMAL)


# --------------------------------------------------------------------------
# the current templates: mirror == another 180 deg of the same class
# --------------------------------------------------------------------------
EQUIVALENCE = [
    ("horizontal 2u", '[[{"w": 2}, "x"]]', "stab_rotation_horizontal", "stab_mirror_horizontal", "stabilizer-2u"),
    ("horizontal 3u", '[[{"w": 3}, "x"]]', "stab_rotation_horizontal", "stab_mirror_horizontal", "stabilizer-3u"),
    ("vertical 2u", '[[{"h": 2}, "x"]]', "stab_rotation_vertical", "stab_mirror_vertical", "stabilizer-2u"),
    ("vertical 3u", '[[{"h": 3}, "x"]]', "stab_rotation_vertical", "stab_mirror_vertical", "stabilizer-3u"),
]


@pytest.mark.parametrize("name, layout, rotation_field, mirror_field, template_kind", EQUIVALENCE,
                         ids=[case[0] for case in EQUIVALENCE])
def test_a_mirror_equals_another_180_degrees_for_the_symmetric_templates(
        tmp_path, name, layout, rotation_field, mirror_field, template_kind):
    path = tmp_path / "layout.json"
    path.write_text(layout, encoding="utf-8")
    plain = build_model(path)
    mirrored = build_model(path, orientation=OrientationConfig(**{mirror_field: True}))
    rotated = build_model(path, orientation=OrientationConfig(**{rotation_field: 180}))
    assert mirrored.mirrored == [True] and rotated.mirrored == [False] and plain.mirrored == [False]
    assert mirrored.templates[template_kind].layers
    plain_mesh, mirror_mesh, rotated_mesh = (cutter_mesh(m.cavities[0]) for m in (plain, mirrored, rotated))
    worst_against_rotation, worst_against_plain = 0.0, 0.0
    for layer in mirrored.templates[template_kind].layers:
        for fraction in (0.1, 0.3, 0.5, 0.7, 0.9):
            z = layer.z0 + (layer.z1 - layer.z0) * fraction
            section = section_polygon(mirror_mesh, z)
            worst_against_rotation = max(
                worst_against_rotation, section.symmetric_difference(section_polygon(rotated_mesh, z)).area)
            worst_against_plain = max(
                worst_against_plain, section.symmetric_difference(section_polygon(plain_mesh, z)).area)
    assert worst_against_rotation <= 1e-4, f"{name}: {worst_against_rotation:.6f} mm2 off the +180 deg cutout"
    # not vacuous: the mirror does change the cutout compared with the default
    assert worst_against_plain > 1.0, f"{name}: the mirror changed nothing ({worst_against_plain:.6f} mm2)"


# --------------------------------------------------------------------------
# a real mirror is not a rotation (synthetic template, asymmetric in X and Y)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_a_real_mirror_is_not_a_rotation(tmp_path, rotation):
    template = fpg.load_template(write_mesh(l_shape_mesh(), tmp_path / "l.stl"), "stabilizer-2u")
    plain = fpg.template_cutter(template, R(rotation))
    matrix = mul(R(rotation), fpg.MIRROR_Y_MATRIX)            # the mirror comes BEFORE the rotation
    cutter = fpg.template_cutter(template, matrix)
    assert cutter.isValid() and cutter.Volume() == pytest.approx(plain.Volume(), rel=1e-9)
    found = section_polygon(cutter_mesh(cutter), -2.0)
    assert found.symmetric_difference(affine(Polygon(L_OUTLINE), matrix)).area < 1e-9
    for extra in (0, 90, 180, 270):                          # no rotation of the L gives its mirror image
        assert found.symmetric_difference(affine(Polygon(L_OUTLINE), R(extra))).area > 1.0, extra


@pytest.mark.parametrize("global_rotation", [0, 90, 180])
@pytest.mark.parametrize("case, flag", [("horizontal", "stab_mirror_horizontal"),
                                        ("vertical", "stab_mirror_vertical")])
def test_the_pipeline_mirrors_before_the_rotations(tmp_path, case, flag, global_rotation):
    """With an asymmetric template the cutout is the template mirrored first, then turned by
    the class rotation and the plate rotation, never mirrored afterwards."""
    config = OrientationConfig(global_rotation=global_rotation, **{flag: True})
    model = build_l_model(tmp_path, case, config)
    assert model.mirrored == [True]
    (cx, cy), rotation = model.centers[0], model.rotations[0]
    turn = mul(fpg.plate_rotation_matrix(config), R(rotation))
    found = projected_outline(model.cavities[0])
    expected = translate(affine(Polygon(L_OUTLINE), mul(turn, fpg.MIRROR_Y_MATRIX)), cx, cy)
    assert found.symmetric_difference(expected).area < 1e-6
    if turn[0] == 0:                       # a 90 or 270 deg turn: the order of mirror and turn matters
        after = translate(affine(Polygon(L_OUTLINE), mul(fpg.MIRROR_Y_MATRIX, turn)), cx, cy)
        assert found.symmetric_difference(after).area > 1.0


@pytest.mark.parametrize("case", ["spacebar", "wide-caps", "socket"])
def test_other_cutouts_are_never_mirrored_by_the_stabilizer_options(tmp_path, case):
    config = OrientationConfig(stab_mirror_horizontal=True, stab_mirror_vertical=True)
    model = build_l_model(tmp_path, case, config)
    assert model.mirrored == [False]
    plain = build_l_model(tmp_path, case)
    assert projected_outline(model.cavities[0]).symmetric_difference(
        projected_outline(plain.cavities[0])).area < 1e-9


# --------------------------------------------------------------------------
# validity and export
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name, layout, rotation_field, mirror_field, template_kind", EQUIVALENCE,
                         ids=[case[0] for case in EQUIVALENCE])
def test_a_mirrored_cavity_is_valid_and_as_large_as_the_plain_one(
        tmp_path, name, layout, rotation_field, mirror_field, template_kind):
    path = tmp_path / "layout.json"
    path.write_text(layout, encoding="utf-8")
    plain = build_model(path)
    mirrored = build_model(path, orientation=OrientationConfig(**{mirror_field: True}))
    assert mirrored.cavities[0].isValid()
    assert mirrored.cavities[0].Volume() == pytest.approx(plain.cavities[0].Volume(), rel=1e-6)
    assert mirrored.plate.isValid()


def test_the_exported_stl_with_both_mirrors_passes_the_check(tmp_path, capsys):
    layout = tmp_path / "small.json"
    layout.write_text('[[{"w": 2}, "H"], [{"w": 3}, "T"], [{"h": 2}, "V", {"h": 3}, "V3"]]', encoding="utf-8")
    out = tmp_path / "plate.stl"
    settings = fpg.Settings(orientation=OrientationConfig(stab_mirror_horizontal=True, stab_mirror_vertical=True))
    fpg.generate(layout, settings, output=out)
    captured = capsys.readouterr()
    assert "Done." in captured.out and "with warnings" not in captured.out and captured.err == ""
    assert "Stab mirror:     horizontal on, vertical on" in captured.out
    _, problems = fpg.check_exported_stl(out)
    assert problems == []


# --------------------------------------------------------------------------
# header output
# --------------------------------------------------------------------------
def test_the_header_shows_the_mirror_settings(repo_root, tmp_path):
    assert "Stab mirror:     horizontal off, vertical off" in run_header(repo_root, tmp_path)
    assert "Stab mirror:     horizontal on, vertical off" in run_header(
        repo_root, tmp_path, "--stab-mirror-horizontal")
    assert "Stab mirror:     horizontal off, vertical on" in run_header(
        repo_root, tmp_path, "--stab-mirror-vertical")


def test_the_spacebar_line_does_not_report_a_mirror_made_by_the_stabilizer_options(repo_root, tmp_path):
    layout = tmp_path / "keys.json"
    layout.write_text('[[{"w": 2}, "x"], [{"w": 6.25}, ""]]', encoding="utf-8")
    from tests.test_plate import run_cli
    out = run_cli(repo_root, "--json", str(layout), "--output", str(tmp_path / "keys.stl"),
                  "--stab-mirror-horizontal")
    assert out.returncode == 0, out.stderr
    spacebar_line = next(line for line in out.stdout.splitlines() if line.startswith("Spacebar:"))
    assert "(centered)" in spacebar_line and "mirrored" not in spacebar_line

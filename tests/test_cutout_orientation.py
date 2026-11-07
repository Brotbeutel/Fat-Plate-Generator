"""Cutouts are only turned, never mirrored; the spacebar switch positions."""
from __future__ import annotations

import pytest
from shapely.affinity import affine_transform, translate
from shapely.geometry import Polygon

import fat_plate_generator as fpg
from fat_plate_generator import OrientationConfig
from tests.conftest import ORIENTATION_LAYOUT, REPO_ROOT, build_model
from tests.test_plate import projected_outline, run_cli
from tests.test_templates import L_OUTLINE, l_shape_mesh, write_mesh

# One key per case: a horizontal and a vertical stabilizer key and the spacebar.
LAYOUTS = {
    "horizontal": '[[{"w": 2}, "x"]]',
    "vertical": '[[{"h": 2}, "x"]]',
    "spacebar": '[[{"w": 6.25}, ""]]',
}


def affine(polygon, matrix):
    a, b, d, e = matrix
    return affine_transform(polygon, [a, b, d, e, 0, 0])


@pytest.mark.parametrize("global_rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("case", list(LAYOUTS))
def test_cutouts_are_turned_never_mirrored(tmp_path, case, global_rotation):
    """An asymmetric template (an L) must come out as the L, turned with the plate
    and by its own rotation, and never as its mirror image.  A mirror image would
    be a different part (a left spacebar template turning into a right one)."""
    layout = tmp_path / "layout.json"
    layout.write_text(LAYOUTS[case], encoding="utf-8")
    template = write_mesh(l_shape_mesh(), tmp_path / "l.stl")
    config = OrientationConfig(global_rotation=global_rotation)
    templates = fpg.TemplateSet.defaults(REPO_ROOT).replace(
        stabilizer=template,
        spacebar_centered=template,
        spacebar_off_centered=template,
    )
    settings = fpg.Settings(orientation=config, templates=templates)
    model = fpg.build_plate_model(layout, settings)
    (cx, cy), rotation = model.centers[0], model.rotations[0]
    found = projected_outline(model.cavities[0])

    turned = fpg.matrix_multiply(fpg.plate_rotation_matrix(config), fpg.rotation_matrix(rotation))
    expected = translate(affine(Polygon(L_OUTLINE), turned), cx, cy)
    assert found.symmetric_difference(expected).area < 1e-6

    mirrored = translate(affine(Polygon(L_OUTLINE),
                                fpg.matrix_multiply(model.matrix, fpg.rotation_matrix(rotation))), cx, cy)
    assert found.symmetric_difference(mirrored).area > 1.0


def test_the_plate_rotation_matrix_has_no_mirror():
    for rotation in (0, 90, 180, 270):
        a, b, d, e = fpg.plate_rotation_matrix(OrientationConfig(global_rotation=rotation))
        assert a * e - b * d == 1                      # a rotation: determinant +1
    assert fpg.plate_rotation_matrix(OrientationConfig(global_transform=False)) == fpg.IDENTITY_MATRIX
    a, b, d, e = fpg.global_matrix(OrientationConfig())
    assert a * e - b * d == -1                         # the whole-plate transform itself mirrors


# --------------------------------------------------------------------------
# spacebar switch positions
# --------------------------------------------------------------------------
@pytest.fixture
def spacebar_layout(tmp_path):
    layout = tmp_path / "spacebar.json"
    layout.write_text(LAYOUTS["spacebar"], encoding="utf-8")
    return layout


@pytest.mark.parametrize("position, expected_path, expected_mirrored", [
    ("centered", REPO_ROOT / fpg.DEFAULT_SPACEBAR_CENTERED, False),
    ("off-centered-left", REPO_ROOT / fpg.DEFAULT_SPACEBAR_OFF_CENTERED, False),
    # one off-centered template; the right position is that template mirrored
    ("off-centered-right", REPO_ROOT / fpg.DEFAULT_SPACEBAR_OFF_CENTERED, True),
])
def test_spacebar_position_picks_the_template(spacebar_layout, position, expected_path, expected_mirrored):
    model = build_model(spacebar_layout, spacebar_position=position)
    assert model.spacebar_path == expected_path
    assert model.mirrored == [expected_mirrored]


def test_unknown_spacebar_position_is_refused(spacebar_layout):
    with pytest.raises(ValueError, match="spacebar_position"):
        build_model(spacebar_layout, spacebar_position="sideways")


@pytest.mark.parametrize("position, side", [
    ("centered", 0), ("off-centered-left", -1), ("off-centered-right", 1),
])
def test_off_centered_spacebar_sits_on_its_side(spacebar_layout, position, side):
    """Seen from above with the typist at the bottom (x to the right): the left
    template must end up left of the key centre, the right one to the right."""
    model = build_model(spacebar_layout, spacebar_position=position)
    offset = projected_outline(model.cavities[0]).centroid.x - model.centers[0][0]
    if side == 0:
        assert offset == pytest.approx(0.0, abs=1e-3)
    else:
        assert offset * side > 1.0, offset


# --------------------------------------------------------------------------
# the right off-centered spacebar is the left template, mirrored
# --------------------------------------------------------------------------
OLD_RIGHT_TEMPLATE = REPO_ROOT / "stl-templates" / "stabilzer_spacebar_off-center_right.stl"
HEIGHT_FRACTIONS = (0.1, 0.35, 0.5, 0.65, 0.9)       # five heights per layer
EQUIVALENCE_TOLERANCE = 1e-4                         # mm2 of difference between two sections


@pytest.mark.parametrize("global_rotation", [180, 90])
@pytest.mark.parametrize("spacebar_rotation", fpg.ROTATION_CHOICES)
def test_mirrored_left_template_equals_the_old_right_file(spacebar_layout, spacebar_rotation, global_rotation):
    """The new way (left template, mirrored in its own coordinates before the
    rotation) must give what the old right file gave when it was used unmirrored,
    for every spacebar rotation and whole-plate rotation."""
    if not OLD_RIGHT_TEMPLATE.is_file():
        pytest.skip(f"{OLD_RIGHT_TEMPLATE.name} is not in the repository (anymore)")
    from tests.test_templates import cutter_mesh, section_polygon

    orientation = OrientationConfig(stab_rotation_spacebar=spacebar_rotation, global_rotation=global_rotation)
    new = build_model(spacebar_layout, spacebar_position="off-centered-right", orientation=orientation)
    old = build_model(spacebar_layout, spacebar_position="off-centered-left", orientation=orientation,
                      spacebar_off_centered=OLD_RIGHT_TEMPLATE)
    assert new.mirrored == [True] and old.mirrored == [False]
    assert new.centers == old.centers

    new_mesh, old_mesh = cutter_mesh(new.cavities[0]), cutter_mesh(old.cavities[0])
    for layer in old.templates["spacebar"].layers:
        for fraction in HEIGHT_FRACTIONS:
            z = layer.z0 + (layer.z1 - layer.z0) * fraction
            difference = section_polygon(new_mesh, z).symmetric_difference(section_polygon(old_mesh, z)).area
            assert difference <= EQUIVALENCE_TOLERANCE, (spacebar_rotation, global_rotation, z, difference)


def test_the_right_spacebar_cavity_is_valid_and_as_large_as_the_left_one(spacebar_layout):
    left = build_model(spacebar_layout, spacebar_position="off-centered-left").cavities[0]
    right = build_model(spacebar_layout, spacebar_position="off-centered-right").cavities[0]
    assert right.isValid()
    assert right.Volume() == pytest.approx(left.Volume(), rel=1e-6)


@pytest.fixture(scope="module")
def right_spacebar_model():
    return build_model(ORIENTATION_LAYOUT, spacebar_position="off-centered-right")


def test_the_right_spacebar_plate_passes_the_stl_check(right_spacebar_model, tmp_path):
    import cadquery as cq

    out = tmp_path / "right.stl"
    cq.exporters.export(right_spacebar_model.plate, str(out), exportType="STL",
                        tolerance=0.001, angularTolerance=0.1)
    bb = right_spacebar_model.plate.BoundingBox()
    _, problems = fpg.check_exported_stl(
        out, expected_bounds=((bb.xmin, bb.ymin, bb.zmin), (bb.xmax, bb.ymax, bb.zmax)))
    assert problems == []


def test_only_the_right_off_centered_spacebar_is_mirrored(right_spacebar_model, orientation_model):
    """The layout has stabilizer keys, Caps Lock, a normal key and the spacebar."""
    model = right_spacebar_model
    assert fpg.KIND_STABILIZED in model.kinds and fpg.KIND_NORMAL in model.kinds
    assert model.mirrored == [kind == fpg.KIND_SPACEBAR for kind in model.kinds]
    assert model.mirrored.count(True) == 1
    # centered (the default of this model) and off-centered-left mirror nothing
    assert not any(orientation_model.mirrored)


def test_the_old_left_and_right_options_are_gone(repo_root, tmp_path):
    for option in ("--spacebar-off-centered-left", "--spacebar-off-centered-right"):
        result = run_cli(repo_root, option, "x.stl", "--output", str(tmp_path / "x.stl"))
        assert result.returncode != 0, option
        assert "unrecognized arguments" in result.stderr and option in result.stderr, result.stderr

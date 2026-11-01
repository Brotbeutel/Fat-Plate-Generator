"""Cutouts are only turned, never mirrored; the spacebar switch positions."""
from __future__ import annotations

import pytest
from shapely.affinity import affine_transform, translate
from shapely.geometry import Polygon

import fat_plate_generator as fpg
from fat_plate_generator import OrientationConfig
from tests.conftest import REPO_ROOT, build_model
from tests.test_plate import projected_outline
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
    model = fpg.build_plate_model(layout, REPO_ROOT / fpg.DEFAULT_SOCKET, template,
                                  {position: template for position in fpg.SPACEBAR_POSITIONS},
                                  orientation=config)
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


@pytest.mark.parametrize("position, name", [
    ("centered", fpg.DEFAULT_SPACEBAR_CENTERED),
    ("off-centered-left", fpg.DEFAULT_SPACEBAR_OFF_CENTERED_LEFT),
    ("off-centered-right", fpg.DEFAULT_SPACEBAR_OFF_CENTERED_RIGHT),
])
def test_spacebar_position_picks_the_template(spacebar_layout, position, name):
    assert build_model(spacebar_layout, spacebar_position=position).spacebar_path.name == name


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

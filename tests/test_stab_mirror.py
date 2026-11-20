"""Stabilizer mirror (WP-18): stab_mirror_horizontal / _vertical / _spacebar.

The spacebar is horizontal, so stab_mirror_horizontal mirrors it too; a spacebar turned by
90 deg (stab_rotation_spacebar) follows stab_mirror_vertical; stab_mirror_spacebar REVERSES
that: alone it mirrors the spacebar, together with the switch of its direction the spacebar is
back in its original position.

The mirror is made in the template's own coordinates along its long axis,
(x, y) -> (x, -y), before the base orientation and the rotations.  The 2u and
3u templates and the centered spacebar templates are symmetric left/right, so
for them it equals another rotation of 180 deg of the same class; the
off-centered spacebar templates are not, and a synthetic asymmetric template
shows that it is a real mirror and not a rotation.
"""
from __future__ import annotations

import itertools

import pytest
from shapely.affinity import translate
from shapely.geometry import Polygon

import fat_plate_generator as fpg
from fat_plate_generator import OrientationConfig
from tests.conftest import ORIENTATION_LAYOUT, build_model
from tests.test_base_orientation import LAYOUTS, affine, build_l_model, key, l_settings, run_header
from tests.test_plate import projected_outline, run_cli
from tests.test_templates import L_OUTLINE, cutter_mesh, l_shape_mesh, section_polygon, write_mesh

R = fpg.rotation_matrix
mul = fpg.matrix_multiply

HORIZONTAL = ["2u", "2.25u", "2.75u"]            # KIND_STABILIZED with w > h
VERTICAL = ["2u vertical", "ISO Enter"]          # KIND_STABILIZED with w <= h
SPACEBAR = [""]                                  # the 6.25u spacebar
NOT_MIRRORED = ["1u", "Caps Lock"]               # normal sockets


def sections_at(meshes, z):
    """Sections of several meshes at the SAME height.

    Cutting triangles with a plane can leave two open ends at a height that is within float
    noise of a vertex (the section then does not close and comes out empty).  If one of the
    sections is empty, all of them are taken a hair higher or lower, so that they stay
    comparable with each other; the shift is at most 1e-6 mm.
    """
    for shift in (0.0, 1e-7, -1e-7, 1e-6, -1e-6):
        sections = [section_polygon(mesh, z + shift) for mesh in meshes]
        if all(section.area > 0 for section in sections):
            return sections
    raise AssertionError(f"no closed section at z={z}")


# --------------------------------------------------------------------------
# which keys are mirrored
# --------------------------------------------------------------------------
def test_the_mirror_matrix_is_the_y_mirror():
    assert fpg.MIRROR_Y_MATRIX == (1, 0, 0, -1)
    a, b, d, e = fpg.MIRROR_Y_MATRIX
    assert a * e - b * d == -1                    # a mirror, not a rotation


ALL_FLAGS = list(itertools.product([False, True], repeat=3))


@pytest.mark.parametrize("horizontal, vertical, spacebar", ALL_FLAGS)
def test_the_decision_per_key_class(horizontal, vertical, spacebar):
    config = OrientationConfig(stab_mirror_horizontal=horizontal, stab_mirror_vertical=vertical,
                               stab_mirror_spacebar=spacebar)
    keys = {
        "horizontal 2u": (key(w=2), horizontal),
        "horizontal 3u": (key(w=3), horizontal),
        "vertical 2u": (key(h=2), vertical),
        "vertical 3u": (key(h=3), vertical),
        "square 2x2 counts as vertical": (key(w=2, h=2), vertical),
        # the spacebar is horizontal: stab_mirror_horizontal mirrors it, and its own switch reverses that
        "spacebar 6u": (key("", w=6), horizontal != spacebar),
        "spacebar 6.25u": (key("", w=6.25), horizontal != spacebar),
        "spacebar 7u": (key("", w=7), horizontal != spacebar),
        "wide-caps": (key(l=True), False),
        "socket": (key(), False),
        "caps lock": (key("Caps Lock", w=1.75), False),
    }
    for name, (k, expected) in keys.items():
        kind = fpg.classify_key(k, 1.75, "wide-caps")
        assert fpg.stabilizer_mirror(k, kind, config) is expected, name


@pytest.mark.parametrize("horizontal, vertical, spacebar", ALL_FLAGS)
@pytest.mark.parametrize("rotation, turned", [(0, False), (90, True), (180, False), (270, True)])
def test_a_spacebar_turned_by_90_degrees_follows_the_vertical_switch(
        rotation, turned, horizontal, vertical, spacebar):
    """The rare exception: stab_mirror_horizontal does not reach a spacebar whose cutout is turned
    by 90 or 270 deg; it is vertical then.  Its own switch reverses what the switch of its
    direction does, in every direction."""
    config = OrientationConfig(stab_mirror_horizontal=horizontal, stab_mirror_vertical=vertical,
                               stab_mirror_spacebar=spacebar, stab_rotation_spacebar=rotation)
    k = key("", w=6.25)
    expected = (vertical if turned else horizontal) != spacebar
    assert fpg.stabilizer_mirror(k, fpg.classify_key(k), config) is expected
    # the rotation of the spacebar changes nothing for the stabilizers
    stabilizer = key(w=2)
    assert fpg.stabilizer_mirror(stabilizer, fpg.classify_key(stabilizer), config) is horizontal


@pytest.fixture(scope="module", params=[(False, False, False), (True, False, False), (False, True, False),
                                        (False, False, True), (True, True, True)],
                ids=["off", "horizontal", "vertical", "spacebar", "all"])
def mirror_model(request):
    horizontal, vertical, spacebar = request.param
    model = build_model(ORIENTATION_LAYOUT, single_mesh=False, orientation=OrientationConfig(
        stab_mirror_horizontal=horizontal, stab_mirror_vertical=vertical, stab_mirror_spacebar=spacebar))
    return model, request.param


def test_exactly_the_selected_stabilizers_are_mirrored(mirror_model):
    model, (horizontal, vertical, spacebar) = mirror_model
    labels = [k["label"] for k in model.keys]
    assert sorted(labels) == sorted(HORIZONTAL + VERTICAL + SPACEBAR + NOT_MIRRORED)
    mirrored = [label for label, flag in zip(labels, model.mirrored) if flag]
    # the spacebar is horizontal: stab_mirror_horizontal mirrors it, too, and its own switch reverses that
    assert sorted(mirrored) == sorted((HORIZONTAL if horizontal else []) + (VERTICAL if vertical else [])
                                      + (SPACEBAR if horizontal != spacebar else []))
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
    # the centered spacebar templates are symmetric left/right, too
    ("spacebar 6u", '[[{"w": 6}, ""]]', "stab_rotation_spacebar", "stab_mirror_spacebar", "spacebar-6u"),
    ("spacebar 6.25u", '[[{"w": 6.25}, ""]]', "stab_rotation_spacebar", "stab_mirror_spacebar", "spacebar-6-25u"),
    ("spacebar 7u", '[[{"w": 7}, ""]]', "stab_rotation_spacebar", "stab_mirror_spacebar", "spacebar-7u"),
    # the same cutout through stab_mirror_horizontal, which mirrors a horizontal spacebar, too
    ("spacebar 6.25u by horizontal", '[[{"w": 6.25}, ""]]', "stab_rotation_spacebar",
     "stab_mirror_horizontal", "spacebar-6-25u"),
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
            section, rotated_section, plain_section = sections_at([mirror_mesh, rotated_mesh, plain_mesh], z)
            worst_against_rotation = max(worst_against_rotation,
                                         section.symmetric_difference(rotated_section).area)
            worst_against_plain = max(worst_against_plain, section.symmetric_difference(plain_section).area)
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


@pytest.mark.parametrize("case", ["wide-caps", "socket"])
def test_wide_caps_and_sockets_are_never_mirrored_by_the_mirror_options(tmp_path, case):
    config = OrientationConfig(stab_mirror_horizontal=True, stab_mirror_vertical=True, stab_mirror_spacebar=True)
    model = build_l_model(tmp_path, case, config)
    assert model.mirrored == [False]
    plain = build_l_model(tmp_path, case)
    assert projected_outline(model.cavities[0]).symmetric_difference(
        projected_outline(plain.cavities[0])).area < 1e-9


@pytest.mark.parametrize("flags, rotation, mirrored", [
    ({"stab_mirror_horizontal": True}, 0, True),             # a horizontal spacebar follows the horizontal switch
    ({"stab_mirror_vertical": True}, 0, False),
    ({"stab_mirror_spacebar": True}, 0, True),               # its own switch alone mirrors it
    ({"stab_mirror_horizontal": True, "stab_mirror_spacebar": True}, 0, False),   # reversed: the original position
    ({"stab_mirror_horizontal": True, "stab_mirror_vertical": True, "stab_mirror_spacebar": True}, 0, False),
    ({"stab_mirror_horizontal": True}, 90, False),           # the rare exception: turned by 90 deg
    ({"stab_mirror_vertical": True}, 90, True),
    ({"stab_mirror_horizontal": True}, 270, False),
    ({"stab_mirror_vertical": True}, 270, True),
    ({"stab_mirror_horizontal": True, "stab_mirror_spacebar": True}, 90, True),   # horizontal does not reach it
    ({"stab_mirror_vertical": True, "stab_mirror_spacebar": True}, 90, False),    # reversed
    ({"stab_mirror_horizontal": True}, 180, True),
])
def test_which_switch_mirrors_the_spacebar(tmp_path, flags, rotation, mirrored):
    """Through the real pipeline with an asymmetric template: mirrored with the matrix MIRROR_Y
    before the rotations, or not at all (also when the two switches reverse each other)."""
    config = OrientationConfig(stab_rotation_spacebar=rotation, **flags)
    model = build_l_model(tmp_path, "spacebar", config)
    assert model.mirrored == [mirrored]
    (cx, cy), effective = model.centers[0], model.rotations[0]
    turn = mul(fpg.plate_rotation_matrix(config), R(effective))
    template_mirror = fpg.MIRROR_Y_MATRIX if mirrored else fpg.IDENTITY_MATRIX
    expected = translate(affine(Polygon(L_OUTLINE), mul(turn, template_mirror)), cx, cy)
    assert projected_outline(model.cavities[0]).symmetric_difference(expected).area < 1e-6


def test_both_switches_mirror_the_horizontal_stabilizers_but_leave_the_spacebar_as_it_is(tmp_path):
    """The reversal with the real templates: horizontal + spacebar = the horizontal stabilizers
    are mirrored, the spacebar is back in its original position."""
    layout = tmp_path / "keys.json"
    layout.write_text('[[{"w": 2}, "x"], [{"w": 6.25}, ""]]', encoding="utf-8")
    plain = build_model(layout)
    both = build_model(layout, orientation=OrientationConfig(
        stab_mirror_horizontal=True, stab_mirror_spacebar=True))
    only_horizontal = build_model(layout, orientation=OrientationConfig(stab_mirror_horizontal=True))
    assert both.mirrored == [True, False] and only_horizontal.mirrored == [True, True]
    stabilizer, spacebar = 0, 1
    z = -3.0
    plain_2u, both_2u = sections_at([cutter_mesh(plain.cavities[stabilizer]), cutter_mesh(both.cavities[stabilizer])], z)
    plain_space, both_space, only_space = sections_at(
        [cutter_mesh(plain.cavities[spacebar]), cutter_mesh(both.cavities[spacebar]),
         cutter_mesh(only_horizontal.cavities[spacebar])], z)
    assert both_space.symmetric_difference(plain_space).area < 1e-4          # the spacebar is as it was
    assert only_space.symmetric_difference(plain_space).area > 1.0           # horizontal alone mirrors it
    assert both_2u.symmetric_difference(plain_2u).area > 1.0                 # the 2u stabilizer is mirrored


# --------------------------------------------------------------------------
# the spacebar: mirror option and switch position are two different mirrors
# --------------------------------------------------------------------------
def build_l_spacebar(tmp_path, position, mirror, global_rotation=0):
    path = tmp_path / "layout.json"
    path.write_text(LAYOUTS["spacebar"], encoding="utf-8")
    settings = l_settings(tmp_path, spacebar_position=position, orientation=OrientationConfig(
        stab_mirror_spacebar=mirror, global_rotation=global_rotation))
    return fpg.build_plate_model(path, settings), settings.orientation


@pytest.mark.parametrize("global_rotation", [0, 90])
@pytest.mark.parametrize("position, mirror, template_mirror", [
    ("centered", False, fpg.IDENTITY_MATRIX),
    ("centered", True, fpg.MIRROR_Y_MATRIX),                                   # the option: along the long axis
    ("off-centered-right", True, fpg.MIRROR_Y_MATRIX),
    ("off-centered-left", False, fpg.MIRROR_X_MATRIX),                         # the position: the right one mirrored
    ("off-centered-left", True, mul(fpg.MIRROR_Y_MATRIX, fpg.MIRROR_X_MATRIX)),  # both: a turn by 180 deg
])
def test_the_spacebar_mirror_and_the_switch_position_combine(tmp_path, position, mirror, template_mirror,
                                                              global_rotation):
    """The two mirrors are applied to the template, before the rotations; with an asymmetric template
    the cutout is exactly that matrix applied to it, for every rotation."""
    model, config = build_l_spacebar(tmp_path, position, mirror, global_rotation)
    (cx, cy), rotation = model.centers[0], model.rotations[0]
    turn = mul(fpg.plate_rotation_matrix(config), R(rotation))
    expected = translate(affine(Polygon(L_OUTLINE), mul(turn, template_mirror)), cx, cy)
    assert projected_outline(model.cavities[0]).symmetric_difference(expected).area < 1e-6
    assert model.mirrored == [template_mirror != fpg.IDENTITY_MATRIX]
    assert model.spacebar_left is (position == "off-centered-left")


def test_a_mirror_on_the_left_spacebar_is_the_right_one_turned_by_180_degrees(tmp_path):
    """Both mirrors together are a rotation: the right template, the switch on the left side."""
    left_mirrored, _ = build_l_spacebar(tmp_path, "off-centered-left", True)
    right_turned = build_l_model(tmp_path, "spacebar", OrientationConfig(stab_rotation_spacebar=180))
    assert projected_outline(left_mirrored.cavities[0]).symmetric_difference(
        projected_outline(right_turned.cavities[0])).area < 1e-6


def test_on_an_off_centered_spacebar_the_mirror_is_not_a_rotation_by_180_degrees(tmp_path):
    """The off-centered spacebar templates are not symmetric left/right: the mirror keeps the switch
    where it is and only swaps the notches, which turning the cutout by 180 degrees would not."""
    layout = tmp_path / "space.json"
    layout.write_text('[[{"w": 6.25}, ""]]', encoding="utf-8")
    for position in ("off-centered-right", "off-centered-left"):
        mirrored = build_model(layout, spacebar_position=position,
                               orientation=OrientationConfig(stab_mirror_spacebar=True))
        turned = build_model(layout, spacebar_position=position,
                             orientation=OrientationConfig(stab_rotation_spacebar=180))
        a, b = cutter_mesh(mirrored.cavities[0]), cutter_mesh(turned.cavities[0])
        worst = 0.0
        for layer in mirrored.templates["spacebar-6-25u"].layers:
            for fraction in (0.1, 0.5, 0.9):
                z = layer.z0 + (layer.z1 - layer.z0) * fraction
                section_a, section_b = sections_at([a, b], z)
                worst = max(worst, section_a.symmetric_difference(section_b).area)
        assert worst > 10.0, f"{position}: the mirror equals +180 deg ({worst:.4f} mm2)"


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
    assert "Stab mirror:     horizontal on, vertical on, spacebar off" in captured.out
    _, problems = fpg.check_exported_stl(out)
    assert problems == []


def test_the_exported_stl_with_a_mirrored_spacebar_passes_the_check(tmp_path, capsys):
    """Only the mesh is judged here (a warning about the bounding box of a spacebar template is
    about that template, not about the mirror)."""
    layout = tmp_path / "space.json"
    layout.write_text('[[{"w": 2}, "H"], [{"h": 2}, "V"], [{"y": 1, "w": 6.25}, ""]]', encoding="utf-8")
    out = tmp_path / "plate.stl"
    settings = fpg.Settings(orientation=OrientationConfig(
        stab_mirror_horizontal=False, stab_mirror_vertical=True, stab_mirror_spacebar=True))
    fpg.generate(layout, settings, output=out)
    captured = capsys.readouterr()
    assert "STL check:       passed" in captured.out and "exported STL has problems" not in captured.err
    assert "Stab mirror:     horizontal off, vertical on, spacebar on" in captured.out
    _, problems = fpg.check_exported_stl(out)
    assert problems == []


# --------------------------------------------------------------------------
# header output
# --------------------------------------------------------------------------
def test_the_header_shows_the_mirror_settings(repo_root, tmp_path):
    assert "Stab mirror:     horizontal off, vertical off, spacebar off" in run_header(repo_root, tmp_path)
    assert "Stab mirror:     horizontal on, vertical off, spacebar off" in run_header(
        repo_root, tmp_path, "--stab-mirror-horizontal")
    assert "Stab mirror:     horizontal off, vertical on, spacebar off" in run_header(
        repo_root, tmp_path, "--stab-mirror-vertical")
    assert "Stab mirror:     horizontal off, vertical off, spacebar on" in run_header(
        repo_root, tmp_path, "--stab-mirror-spacebar")


def spacebar_line(repo_root, tmp_path, *options):
    layout = tmp_path / "keys.json"
    layout.write_text('[[{"w": 2}, "x"], [{"w": 6.25}, ""]]', encoding="utf-8")
    result = run_cli(repo_root, "--json", str(layout), "--output", str(tmp_path / "keys.stl"), *options)
    assert result.returncode == 0, result.stderr
    return next(line for line in result.stdout.splitlines() if line.startswith("Spacebar:"))


def test_the_spacebar_line_says_mirrored_only_for_the_switch_position(repo_root, tmp_path):
    """'mirrored' there is the left position (the right template mirrored); the mirror options have
    their own header line."""
    for options in (("--stab-mirror-horizontal",), ("--stab-mirror-spacebar",)):
        line = spacebar_line(repo_root, tmp_path, *options)
        assert "(centered)" in line and "mirrored" not in line, line
    for options in (("--spacebar-position", "off-centered-left"),
                    ("--spacebar-position", "off-centered-left", "--stab-mirror-spacebar")):
        assert "(off-centered-left, mirrored)" in spacebar_line(repo_root, tmp_path, *options)

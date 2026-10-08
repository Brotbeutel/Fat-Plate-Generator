"""Key classification, chosen stabilizer rotation and orientation config."""
from __future__ import annotations

import pytest

import fat_plate_generator as fpg
from fat_plate_generator import OrientationConfig

# label -> (kind, rotation with the default OrientationConfig)
EXPECTED = {
    "1u": (fpg.KIND_NORMAL, None),
    "Caps Lock": (fpg.KIND_NORMAL, None),          # 1.75u, but normal socket
    "2u": (fpg.KIND_STABILIZED, 180),               # horizontal
    "2.25u": (fpg.KIND_STABILIZED, 180),
    "2.75u": (fpg.KIND_STABILIZED, 180),
    "2u vertical": (fpg.KIND_STABILIZED, 270),      # vertical
    "ISO Enter": (fpg.KIND_STABILIZED, 270),        # 1.25 x 2 -> vertical
    "": (fpg.KIND_SPACEBAR, 180),                   # 6.25u spacebar (empty label)
}


def key(label="x", w=1.0, h=1.0):
    return {"label": label, "w": w, "h": h}


def test_orientation_layout_has_all_cases(orientation_model):
    assert [k["label"] for k in orientation_model.keys] == list(EXPECTED)


@pytest.mark.parametrize("label", list(EXPECTED))
def test_default_classification_and_rotation(orientation_model, label):
    index = [k["label"] for k in orientation_model.keys].index(label)
    kind, rotation = EXPECTED[label]
    assert orientation_model.kinds[index] == kind
    assert orientation_model.rotations[index] == rotation


def test_classify_key_rules():
    assert fpg.classify_key(key("A")) == fpg.KIND_NORMAL
    assert fpg.classify_key(key("Shift", w=1.75)) == fpg.KIND_STABILIZED
    assert fpg.classify_key(key("Shift", w=1.5)) == fpg.KIND_NORMAL
    assert fpg.classify_key(key("Shift", w=1.5), min_units=1.5) == fpg.KIND_STABILIZED
    assert fpg.classify_key(key("+", h=2)) == fpg.KIND_STABILIZED
    assert fpg.classify_key(key("Caps Lock", w=1.75)) == fpg.KIND_NORMAL
    assert fpg.classify_key(key("", w=6.25)) == fpg.KIND_SPACEBAR
    # A wide key with a legend is not a spacebar (current behaviour, see WP-02).
    assert fpg.classify_key(key("Space", w=6.25)) == fpg.KIND_STABILIZED


def test_horizontal_vs_vertical_rule():
    cfg = OrientationConfig(stab_rotation_horizontal=0, stab_rotation_vertical=270,
                            stab_rotation_spacebar=90)
    assert fpg.stabilizer_rotation(key("Shift", w=2.25), cfg) == 0
    assert fpg.stabilizer_rotation(key("+", h=2), cfg) == 270
    # Square keys count as vertical (w > h is the horizontal rule); unchanged.
    assert fpg.stabilizer_rotation(key("big", w=2, h=2), cfg) == 270
    assert fpg.stabilizer_rotation(key("", w=6.25), cfg) == 90
    assert fpg.stabilizer_rotation(key("A"), cfg) is None


def test_documented_defaults():
    """The defaults the project owner settled on after checking the exported
    plate (the first version followed TODO.txt: vertical 90, plate 90 + mirror)."""
    cfg = OrientationConfig()
    assert cfg.stab_rotation_horizontal == 180
    assert cfg.stab_rotation_vertical == 270
    assert cfg.stab_rotation_spacebar == 180
    assert cfg.global_transform
    assert cfg.global_rotation == 180
    assert cfg.global_mirror_x


@pytest.mark.parametrize("field", ["stab_rotation_horizontal", "stab_rotation_vertical",
                                   "stab_rotation_spacebar", "global_rotation"])
@pytest.mark.parametrize("value", [45, 360, -90])
def test_invalid_rotation_is_rejected(field, value):
    with pytest.raises(ValueError):
        OrientationConfig(**{field: value})


def test_default_global_matrix_is_the_plain_kle_y_flip():
    """Rotate 180 deg + mirror X is exactly KLE y (down) -> CAD y (up): the
    cause-level fix, with no extra turn of the plate."""
    y_flip = (1, 0, 0, -1)
    assert fpg.global_matrix(OrientationConfig()) == y_flip
    assert fpg.global_matrix(OrientationConfig(global_transform=False)) == fpg.IDENTITY_MATRIX


def test_old_todo_transform_is_still_available():
    """The original TODO.txt transform (rotate 90 deg, mirror X) is a transposition,
    (x, y) -> (y, x), i.e. the y-flip followed by a 90 deg turn."""
    old = fpg.global_matrix(OrientationConfig(global_rotation=90))
    assert old == (0, 1, 1, 0)
    assert fpg.matrix_multiply(fpg.rotation_matrix(90), (1, 0, 0, -1)) == old


def test_preview_uses_the_same_global_matrix():
    from tools import preview

    assert preview.GLOBAL_MATRIX == fpg.global_matrix(OrientationConfig())
    assert preview.IDENTITY_MATRIX == fpg.IDENTITY_MATRIX

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
    "2u vertical": (fpg.KIND_STABILIZED, 90),       # vertical
    "ISO Enter": (fpg.KIND_STABILIZED, 90),         # 1.25 x 2 -> vertical
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


def test_defaults_match_old_todo_corrections():
    """Old generator: horizontal 90, vertical 0, spacebar 0.  TODO.txt asked for
    +90 for all other stabilizers and +180 for the spacebar stabilizer."""
    cfg = OrientationConfig()
    assert cfg.stab_rotation_horizontal == (90 + 90) % 360
    assert cfg.stab_rotation_vertical == (0 + 90) % 360
    assert cfg.stab_rotation_spacebar == (0 + 180) % 360
    assert cfg.global_transform


@pytest.mark.parametrize("field", ["stab_rotation_horizontal", "stab_rotation_vertical",
                                   "stab_rotation_spacebar", "global_rotation"])
@pytest.mark.parametrize("value", [45, 360, -90])
def test_invalid_rotation_is_rejected(field, value):
    with pytest.raises(ValueError):
        OrientationConfig(**{field: value})


def test_global_matrix_is_transposition_and_cause_level_equivalent():
    default = fpg.global_matrix(OrientationConfig())
    # "rotate 90 deg about Z, then mirror X" as in TODO.txt: (x, y) -> (y, x)
    assert default == (0, 1, 1, 0)
    # Same map as "KLE y-flip (y down -> y up), then rotate 90 deg".
    y_flip = (1, 0, 0, -1)
    assert fpg.matrix_multiply(fpg.rotation_matrix(90), y_flip) == default
    assert fpg.global_matrix(OrientationConfig(global_transform=False)) == fpg.IDENTITY_MATRIX


def test_preview_uses_the_same_global_matrix():
    from tools import preview

    assert preview.GLOBAL_MATRIX == fpg.global_matrix(OrientationConfig())
    assert preview.IDENTITY_MATRIX == fpg.IDENTITY_MATRIX

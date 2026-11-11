"""parse_kle() follows the Keyboard Layout Editor (WP-13).  No CAD, fast.

The editor is the reference: ``rx`` / ``ry`` set the position, properties apply
to the next key only, decals are no keys, ``r`` / ``rx`` / ``ry`` belong at the
start of a row.
"""
from __future__ import annotations

import json

import pytest

import fat_plate_generator as fpg
from tests.conftest import REPO_ROOT

KLE_DIR = REPO_ROOT / "kle-jsons"
RK65 = KLE_DIR / "keyboard-layout_065-percent-iso_royal-kludge-rk65.json"
RK65_CLEAN = KLE_DIR / "keyboard-layout_065-percent-iso_royal-kludge-rk65_clean.json"
ERGODOX = KLE_DIR / "keyboard-layout_ergodox_split_ergo_67-keys.json"
SHAPE = ("x", "y", "w", "h", "x2", "y2", "w2", "h2")


def parse(text):
    return fpg.parse_kle(json.loads(text))


def parse_file(path):
    return fpg.parse_kle(json.loads(path.read_text(encoding="utf-8")))


def placed(keys):
    """(label, x, y) of every key."""
    return [(k["label"], k["x"], k["y"]) for k in keys]


def assert_placed(keys, expected):
    assert [k["label"] for k in keys] == [label for label, _, _ in expected]
    for key, (label, x, y) in zip(keys, expected):
        assert (key["x"], key["y"]) == pytest.approx((x, y)), label


# --------------------------------------------------------------------------
# Layouts of the repository
# --------------------------------------------------------------------------
def test_rk65_export_and_clean_file_have_the_same_key_positions():
    """The export puts Del in a row of its own behind ``rx``; the hand-cleaned
    file has the same keyboard.  The labels differ on purpose."""
    exported, clean = parse_file(RK65), parse_file(RK65_CLEAN)
    assert len(exported) == len(clean)
    shapes = lambda keys: sorted(tuple(k[name] for name in SHAPE) for k in keys)
    assert shapes(exported) == shapes(clean)


def test_rk65_del_is_where_the_editor_shows_it():
    for path in (RK65, RK65_CLEAN):
        delete = [k for k in parse_file(path) if k["label"] == "Del"]
        assert len(delete) == 1, path.name
        assert (delete[0]["x"], delete[0]["y"]) == pytest.approx((15, 1)), path.name


def test_ergodox_thumb_cluster_keeps_the_ry_of_its_cluster():
    """Row 23 is ``{"r": -30, "rx": 13, "y": -1, "x": -3}``: ``rx`` without
    ``ry``, so ``y`` restarts at the ``ry`` of the row before (4.25)."""
    keys = [k for k in parse_file(ERGODOX) if k["rx"] == 13]
    assert len(keys) >= 2
    assert all(k["r"] == -30 and k["ry"] == 4.25 for k in keys)
    assert (keys[0]["x"], keys[0]["y"]) == pytest.approx((10, 3.25))
    assert (keys[1]["x"], keys[1]["y"]) == pytest.approx((11, 3.25))


# --------------------------------------------------------------------------
# rx / ry set the position
# --------------------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    # rx sets x and y (to the ry set last, here 0), then x / y are added
    ('[["A"], [{"rx": 2, "y": 1, "x": 1}, "B"]]', [("A", 0, 0), ("B", 3, 1)]),
    # the ry set last is kept when only rx is given
    ('[[{"r": 30, "rx": 1, "ry": 2}, "A"], [{"rx": 4}, "B"]]', [("A", 1, 2), ("B", 4, 2)]),
    # ry alone: x goes back to the rx set last (0)
    ('[["A"], [{"ry": 5}, "B"]]', [("A", 0, 0), ("B", 0, 5)]),
    ('[[{"rx": 3}, "A"], ["B"]]', [("A", 3, 0), ("B", 3, 1)]),         # every row starts at rx
    ('[[{"rx": 3, "ry": 2}, "A", "B"], ["C"]]', [("A", 3, 2), ("B", 4, 2), ("C", 3, 3)]),
    # r alone does not move anything
    ('[["A"], [{"r": 15}, "B"]]', [("A", 0, 0), ("B", 0, 1)]),
    ('[["A", "B"], [{"r": 15, "x": 2}, "C"]]', [("A", 0, 0), ("B", 1, 0), ("C", 2, 1)]),
])
def test_rx_and_ry_set_the_position(text, expected):
    assert_placed(parse(text), expected)


def test_keys_carry_the_rotation_origin_they_were_created_with():
    keys = parse('[[{"r": 10, "rx": 1, "ry": 2}, "A"], [{"rx": 5}, "B"], [{"r": 0}, "C"]]')
    assert [(k["r"], k["rx"], k["ry"]) for k in keys] == [(10, 1, 2), (10, 5, 2), (0, 5, 2)]


def test_a_layout_without_rotation_is_not_moved_by_the_fix():
    keys = parse('[["A", {"x": 1}, "B"], [{"y": 0.5, "x": 0.25}, "C"], ["D"]]')
    assert_placed(keys, [("A", 0, 0), ("B", 2, 0), ("C", 0.25, 1.5), ("D", 0, 2.5)])
    assert all((k["r"], k["rx"], k["ry"]) == (0, 0, 0) for k in keys)


# --------------------------------------------------------------------------
# properties apply to the next key
# --------------------------------------------------------------------------
def test_two_objects_before_a_key_add_up():
    keys = parse('[[{"w": 2}, {"c": "#fff"}, "A", "B"]]')
    assert [k["w"] for k in keys] == [2, 1]
    assert [k["w2"] for k in keys] == [2, 1]
    assert_placed(keys, [("A", 0, 0), ("B", 2, 0)])


def test_properties_of_two_objects_are_combined():
    key, = parse('[[{"w": 2}, {"h": 3}, "A"]]')
    assert (key["w"], key["h"], key["w2"], key["h2"]) == (2, 3, 2, 3)


def test_properties_are_reset_after_the_key():
    first, second = parse('[[{"w": 2, "h": 2, "l": true, "x2": 0.5, "y2": 0.25}, "A", "B"]]')
    assert (first["w"], first["h"], first["w2"], first["h2"], first["l"]) == (2, 2, 2, 2, True)
    assert (first["x2"], first["y2"]) == (0.5, 0.25)
    assert (second["w"], second["h"], second["w2"], second["h2"]) == (1, 1, 1, 1)
    assert (second["x2"], second["y2"], second["l"]) == (0, 0, False)


def test_w_sets_w2_and_h_sets_h2_unless_they_are_given():
    assert [(k["w2"], k["h2"]) for k in parse('[[{"w": 2, "h": 3}, "A"]]')] == [(2, 3)]
    assert [(k["w2"], k["h2"]) for k in parse('[[{"w": 2, "w2": 3, "h": 4, "h2": 1}, "A"]]')] == [(3, 1)]
    # within one object w comes first, so a w2 in an earlier object is overwritten by a later w
    assert parse('[[{"w2": 3}, {"w": 2}, "A"]]')[0]["w2"] == 2
    assert parse('[[{"w": 2}, {"w2": 3}, "A"]]')[0]["w2"] == 3


def test_the_rotation_stays_until_it_is_changed():
    keys = parse('[[{"r": 20, "rx": 1, "ry": 1}, "A"], ["B"], [{"r": 0}, "C"]]')
    assert [k["r"] for k in keys] == [20, 20, 0]


def test_iso_enter_is_unchanged():
    key, = parse('[[{"x": 0.25, "w": 1.25, "h": 2, "w2": 1.5, "h2": 1, "x2": -0.25}, "Enter"]]')
    assert key == {"label": "Enter", "w": 1.25, "h": 2, "x2": -0.25, "y2": 0.0, "w2": 1.5, "h2": 1,
                   "l": False, "r": 0.0, "rx": 0.0, "ry": 0.0, "x": 0.25, "y": 0.0}


def test_stepped_caps_lock_is_unchanged():
    key, = parse('[[{"w": 1.25, "w2": 1.75, "l": true}, "Caps Lock"]]')
    assert (key["w"], key["w2"], key["h"], key["h2"], key["l"]) == (1.25, 1.75, 1, 1, True)


def test_a_key_has_exactly_the_fields_it_had_before():
    key, = parse('[["A"]]')
    assert set(key) == {"label", "x", "y", "w", "h", "x2", "y2", "w2", "h2", "l", "r", "rx", "ry"}


# --------------------------------------------------------------------------
# decals
# --------------------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    ('[[{"d": true, "w": 2}, "deco", "Q"]]', [("Q", 2, 0)]),
    ('[["Q", {"d": true}, "x", "W"]]', [("Q", 0, 0), ("W", 2, 0)]),
    ('[[{"d": false}, "Q"]]', [("Q", 0, 0)]),
    ('[[{"d": true, "w": 3}, "deco"], ["Q"]]', [("Q", 0, 1)]),          # the decal's row still counts
])
def test_decals_are_no_keys_but_take_their_space(text, expected):
    assert_placed(parse(text), expected)


def test_a_decal_uses_up_its_properties():
    keys = parse('[[{"d": true, "w": 2, "h": 2, "l": true}, "deco", "Q"]]')
    assert len(keys) == 1
    assert (keys[0]["w"], keys[0]["h"], keys[0]["l"]) == (1, 1, False)


# --------------------------------------------------------------------------
# r, rx and ry only at the start of a row
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["r", "rx", "ry"])
def test_rotation_options_after_the_first_item_are_an_error(name):
    with pytest.raises(ValueError, match=r"can only be used on the first key of a row") as error:
        parse('[["Q"], ["A", {"%s": 10}, "B"]]' % name)
    assert "row at index 1" in str(error.value) and repr(name) in str(error.value)


def test_a_second_object_at_the_start_of_a_row_is_too_late():
    with pytest.raises(ValueError, match=r"first key of a row.*row at index 0"):
        parse('[[{"x": 1}, {"ry": 2}, "A"]]')


def test_the_first_item_of_a_row_may_be_a_rotation_object():
    keys = parse('[["Q"], [{"r": 10, "rx": 1, "ry": 2, "x": 1}, "A", "B"]]')
    assert_placed(keys, [("Q", 0, 0), ("A", 2, 2), ("B", 3, 2)])


def test_other_options_may_stand_anywhere_in_a_row():
    keys = parse('[["A", {"x": 1, "y": 0.5, "w": 2, "c": "#fff"}, "B", {"d": false}, "C"]]')
    assert_placed(keys, [("A", 0, 0), ("B", 2, 0.5), ("C", 4, 0.5)])

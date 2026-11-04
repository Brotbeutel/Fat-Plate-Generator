"""KLE Raw Data parsing and layout-wide classification regressions."""
from __future__ import annotations

import json

import pytest

import fat_plate_generator as fpg
from tests.conftest import REPO_ROOT


def test_metadata_object_is_ignored_without_shifting_keys():
    rows = [["Q", "W"], ["A"]]
    metadata_variants = [
        {"name": "My board", "author": "Jannik"},
        {"name": "My board", "author": "Jannik", "backcolor": "#eeeeee",
         "css": "color: red;", "radii": 0.5, "notes": "metadata"},
    ]

    expected = fpg.parse_kle(rows)
    for metadata in metadata_variants:
        assert fpg.parse_kle([metadata, *rows]) == expected


@pytest.mark.parametrize("data", [
    {"name": "Not Raw Data", "author": "Someone"},
    ["not a row"],
    [["Q"], {"name": "Misplaced metadata"}],
])
def test_non_raw_data_shapes_are_rejected(data):
    with pytest.raises(ValueError, match="Raw Data"):
        fpg.parse_kle(data)


def test_invalid_row_error_names_its_index():
    with pytest.raises(ValueError, match=r"row at index 1"):
        fpg.parse_kle([["Q"], "not a row"])


@pytest.mark.parametrize("layout_path", sorted((REPO_ROOT / "kle-jsons").glob("*.json")),
                         ids=lambda path: path.name)
def test_every_repository_layout_parses_and_has_no_false_small_stabilizers(layout_path):
    data = json.loads(layout_path.read_text(encoding="utf-8"))
    keys = fpg.parse_kle(data)

    assert keys, layout_path.name
    kinds = [fpg.classify_key(key) for key in keys]
    assert all(
        kind != fpg.KIND_STABILIZED
        for key, kind in zip(keys, kinds)
        if max(float(key["w"]), float(key["h"])) < fpg.DEFAULT_STABILIZER_MIN_UNIT
    )
    if not any(key["label"] in ("name", "author") for key in keys):
        assert not any(key["label"] in ("name", "author") for key in keys)


def test_jd40_enter_and_shift_at_1_75u_are_normal_sockets():
    path = REPO_ROOT / "kle-jsons" / "keyboard-layout_040-percent_jd40.json"
    keys = fpg.parse_kle(json.loads(path.read_text(encoding="utf-8")))

    affected = [key for key in keys
                if key["label"] in ("Enter", "Shift")
                and max(float(key["w"]), float(key["h"])) == 1.75]
    assert {key["label"] for key in affected} == {"Enter", "Shift"}
    assert all(fpg.classify_key(key) == fpg.KIND_NORMAL for key in affected)


def test_main_reports_invalid_raw_data_as_an_error(tmp_path):
    import subprocess
    import sys

    invalid = tmp_path / "not-raw-data.json"
    invalid.write_text('{"name": "wrong export"}', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "fat_plate_generator.py"),
         "--json", str(invalid)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode != 0
    assert "ERROR:" in result.stderr
    assert "Raw Data" in result.stderr

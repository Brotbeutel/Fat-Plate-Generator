"""Option --fuse-f-row: the top row of the layout becomes one strip of plate.

The first half needs no CAD (``parse_kle``, ``top_row_keys`` and
``plate_footprint`` only, shapely geometry).  The second half builds small
plates; the models are built once per module.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from shapely.affinity import affine_transform, scale, translate
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

import fat_plate_generator as fpg
from tests.conftest import REPO_ROOT, build_model
from tests.test_plate import footprint_parts
from tools import preview

KLE_DIR = REPO_ROOT / "kle-jsons"
G80 = KLE_DIR / "keyboard-layout_100-percent-iso-105-keys_g80-3000.json"
ISO105 = KLE_DIR / "keyboard-layout_100-percent-iso-105-keys.json"
TKL = KLE_DIR / "keyboard-layout_080-percent-iso-cherry_g80-3000n-tkl.json"
JD40 = KLE_DIR / "keyboard-layout_040-percent_jd40.json"
ERGODOX = KLE_DIR / "keyboard-layout_ergodox_split_ergo_67-keys.json"

MARGIN = fpg.DEFAULT_MARGIN
MATRICES = {"kle frame": fpg.IDENTITY_MATRIX,
            "default plate transform": fpg.global_matrix(fpg.OrientationConfig())}

# Esc | F1 F2 | F3 in the top row (two gaps), two keys 0.75 u below (a separate part).
SMALL_LAYOUT = ('[["Esc", {"x": 1}, "F1", "F2", {"x": 0.5}, "F3"], '
                '[{"y": 0.75}, "a", "b"]]')


def load(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return raw, fpg.parse_kle(raw)


def first_row_labels(raw):
    """The labels of the first KLE row, read from the raw data (not from the parser).

    A leading metadata object (name, author, ...) is not a row and is skipped.
    """
    first = next(row for row in raw if isinstance(row, list))
    return [item for item in first if isinstance(item, str)]


def labels(keys):
    return [k["label"] for k in keys]


def center(key, matrix):
    return fpg.apply_matrix(matrix, *fpg.switch_center(key))


def parts_containing(footprint, points):
    """Indices of the parts of ``footprint`` that contain one of the points."""
    parts = footprint_parts(footprint)
    found = {i for i, part in enumerate(parts) for p in points if part.contains(Point(p))}
    assert all(any(part.contains(Point(p)) for part in parts) for p in points)
    return found


def old_footprint(keys, matrix, margin):
    """The outline as it was before the option existed (reference for 'unchanged')."""
    a, b, d, e = matrix
    shapes = []
    for k in keys:
        shape = translate(fpg.local_key_shape(k), xoff=k["x"], yoff=k["y"])
        shape = scale(shape, xfact=fpg.UNIT, yfact=fpg.UNIT, origin=(0, 0))
        shapes.append(affine_transform(shape, [a, b, d, e, 0, 0]))
    return unary_union(shapes).buffer(margin, join_style=2)


# --------------------------------------------------------------------------
# top_row_keys()
# --------------------------------------------------------------------------
@pytest.mark.parametrize("path", [G80, ISO105, TKL, JD40], ids=lambda p: p.name)
def test_top_row_is_the_first_kle_row(path):
    raw, keys = load(path)
    assert labels(fpg.top_row_keys(keys)) == first_row_labels(raw)


@pytest.mark.parametrize("path", [G80, ISO105], ids=lambda p: p.name)
def test_top_row_of_a_100_percent_layout_is_esc_f_row_and_the_three_keys(path):
    _, keys = load(path)
    expected = ["Esc", *(f"F{i}" for i in range(1, 13)), "PrtSc", "Scroll Lock", "Pause\nBreak"]
    assert labels(fpg.top_row_keys(keys)) == expected


def test_top_row_of_the_jd40_layout_has_the_twelve_keys_of_the_first_row():
    raw, keys = load(JD40)
    row = fpg.top_row_keys(keys)
    assert len(row) == len(first_row_labels(raw)) == 12


def test_top_row_is_in_kle_order_and_shares_one_y():
    _, keys = load(G80)
    row = fpg.top_row_keys(keys)
    assert [k["x"] for k in row] == sorted(k["x"] for k in row)
    assert len({k["y"] for k in row}) == 1 and row[0]["y"] == min(k["y"] for k in keys)


def test_rotated_keys_are_never_in_the_top_row():
    """The rotated key has the smallest y of all, so a plain 'smallest y' would pick it."""
    keys = fpg.parse_kle(json.loads('[["A", {"x": 2}, "B"], [{"r": 10, "rx": 0, "ry": -2}, "R"]]'))
    assert [k["label"] for k in keys] == ["A", "B", "R"]
    assert min(k["y"] for k in keys) == -2 and keys[2]["r"] == 10
    assert labels(fpg.top_row_keys(keys)) == ["A", "B"]


def test_top_row_of_the_ergodox_layout_has_no_rotated_key():
    _, keys = load(ERGODOX)
    assert any(abs(k["r"]) > 0 for k in keys)                     # the layout does have rotated keys
    row = fpg.top_row_keys(keys)
    assert row and all(abs(k["r"]) < 1e-9 for k in row)
    assert all(k["y"] == min(q["y"] for q in keys if abs(q["r"]) < 1e-9) for k in row)


def test_a_layout_without_an_unrotated_key_has_no_top_row():
    keys = fpg.parse_kle(json.loads('[[{"r": 15, "rx": 0, "ry": 0}, "A", "B"]]'))
    assert fpg.top_row_keys(keys) == []
    plain = fpg.plate_footprint(keys, fpg.IDENTITY_MATRIX, MARGIN)
    assert fpg.plate_footprint(keys, fpg.IDENTITY_MATRIX, MARGIN, fuse_top_row=True).equals(plain)


def test_keys_whose_y_differs_by_less_than_the_tolerance_are_one_row():
    keys = fpg.parse_kle(json.loads('[["A", "B"]]'))
    keys[1]["y"] += fpg.TOP_ROW_TOLERANCE / 2
    assert labels(fpg.top_row_keys(keys)) == ["A", "B"]
    keys[1]["y"] += 0.01
    assert labels(fpg.top_row_keys(keys)) == ["A"]


# --------------------------------------------------------------------------
# plate_footprint() with and without the option (shapely only)
# --------------------------------------------------------------------------
@pytest.fixture(scope="module", params=list(MATRICES))
def g80_footprints(request):
    """(matrix, keys, plain outline, fused outline) of the G80-3000 layout."""
    matrix = MATRICES[request.param]
    _, keys = load(G80)
    return (matrix, keys,
            fpg.plate_footprint(keys, matrix, MARGIN),
            fpg.plate_footprint(keys, matrix, MARGIN, fuse_top_row=True))


def test_all_top_row_keys_lie_in_one_part_with_the_option(g80_footprints):
    matrix, keys, plain, fused = g80_footprints
    centers = [center(k, matrix) for k in fpg.top_row_keys(keys)]
    assert len(parts_containing(plain, centers)) > 1              # separate islands before
    assert len(parts_containing(fused, centers)) == 1


def test_the_part_count_drops_by_the_islands_of_the_top_row_minus_one(g80_footprints):
    matrix, keys, plain, fused = g80_footprints
    centers = [center(k, matrix) for k in fpg.top_row_keys(keys)]
    islands = len(parts_containing(plain, centers))
    assert len(footprint_parts(fused)) == len(footprint_parts(plain)) - (islands - 1)


def test_the_other_parts_stay_exactly_as_they_were(g80_footprints):
    matrix, keys, plain, fused = g80_footprints
    centers = [center(k, matrix) for k in fpg.top_row_keys(keys)]

    def others(footprint):
        skip = parts_containing(footprint, centers)
        return [part for i, part in enumerate(footprint_parts(footprint)) if i not in skip]

    before, after = others(plain), others(fused)
    assert before and len(before) == len(after)
    for part in before:
        assert min(part.symmetric_difference(other).area for other in after) < 1e-9


def test_the_outline_with_the_option_contains_the_outline_without(g80_footprints):
    _, _, plain, fused = g80_footprints
    assert plain.difference(fused).area < 1e-9
    assert fused.area > plain.area + 100.0                         # the gaps were filled


def test_the_added_area_lies_in_the_strip_of_the_top_row(g80_footprints):
    matrix, keys, plain, fused = g80_footprints
    row = fpg.top_row_keys(keys)
    ys = [fpg.apply_matrix(matrix, 0, y * fpg.UNIT)[1]
          for k in row for y in (k["y"], k["y"] + k["h"])]
    low, high = min(ys) - MARGIN, max(ys) + MARGIN
    extra = fused.difference(plain)
    assert extra.area > 0
    x0, y0, x1, y1 = extra.bounds
    assert y0 >= low - 1e-6 and y1 <= high + 1e-6


@pytest.mark.parametrize("matrix_name", list(MATRICES))
@pytest.mark.parametrize("path", [G80, ISO105, TKL, JD40], ids=lambda p: p.name)
def test_without_the_option_the_outline_is_what_it_was(path, matrix_name):
    _, keys = load(path)
    matrix = MATRICES[matrix_name]
    reference = old_footprint(keys, matrix, MARGIN)
    assert fpg.plate_footprint(keys, matrix, MARGIN).equals(reference)
    assert fpg.plate_footprint(keys, matrix, MARGIN, single_mesh=False, fuse_top_row=False).equals(reference)


@pytest.mark.parametrize("path", [G80, ISO105, TKL, JD40], ids=lambda p: p.name)
def test_with_single_mesh_the_option_changes_nothing(path):
    _, keys = load(path)
    matrix = MATRICES["default plate transform"]
    plain = fpg.plate_footprint(keys, matrix, MARGIN, single_mesh=True)
    both = fpg.plate_footprint(keys, matrix, MARGIN, single_mesh=True, fuse_top_row=True)
    assert both.equals(plain)


def test_a_top_row_without_gaps_changes_nothing():
    _, keys = load(JD40)
    matrix = MATRICES["default plate transform"]
    plain = fpg.plate_footprint(keys, matrix, MARGIN)
    fused = fpg.plate_footprint(keys, matrix, MARGIN, fuse_top_row=True)
    assert len(footprint_parts(plain)) == len(footprint_parts(fused)) == 1
    assert fused.equals(plain)


@pytest.mark.parametrize("path", [ISO105, TKL], ids=lambda p: p.name)
def test_the_top_row_of_other_layouts_becomes_one_strip(path):
    _, keys = load(path)
    matrix = MATRICES["default plate transform"]
    centers = [center(k, matrix) for k in fpg.top_row_keys(keys)]
    plain = fpg.plate_footprint(keys, matrix, MARGIN)
    fused = fpg.plate_footprint(keys, matrix, MARGIN, fuse_top_row=True)
    islands = len(parts_containing(plain, centers))
    assert islands > 1
    assert len(parts_containing(fused, centers)) == 1
    assert len(footprint_parts(fused)) == len(footprint_parts(plain)) - (islands - 1)


def test_the_top_row_is_not_joined_with_the_main_block():
    """The F-row of the G80-3000 layout is 0.75 u above the main block: its part must
    not contain a key of the next row."""
    _, keys = load(G80)
    matrix = MATRICES["default plate transform"]
    fused = fpg.plate_footprint(keys, matrix, MARGIN, fuse_top_row=True)
    row_part = parts_containing(fused, [center(k, matrix) for k in fpg.top_row_keys(keys)])
    below = [k for k in keys if k["y"] > fpg.top_row_keys(keys)[0]["y"]]
    assert row_part.isdisjoint(parts_containing(fused, [center(k, matrix) for k in below]))


# --------------------------------------------------------------------------
# the plate (small layout, CAD)
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def small_layout(tmp_path_factory):
    path = tmp_path_factory.mktemp("fuse_f_row") / "small.json"
    path.write_text(SMALL_LAYOUT, encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def small_plain(small_layout):
    return build_model(small_layout)


@pytest.fixture(scope="module")
def small_fused(small_layout):
    return build_model(small_layout, fuse_f_row=True)


@pytest.fixture(scope="module")
def small_fused_mesh(small_fused, tmp_path_factory):
    from tests.test_plate import export_mesh
    return export_mesh(small_fused, tmp_path_factory.mktemp("fuse_f_row_stl") / "fused.stl")


def section_parts_and_holes(mesh):
    material, _ = preview.plate_section(mesh)
    parts = footprint_parts(material)
    return len(parts), sum(len(part.interiors) for part in parts)


def test_the_small_layout_has_the_expected_islands(small_layout, small_plain):
    row = fpg.top_row_keys(small_plain.keys)
    assert labels(row) == ["Esc", "F1", "F2", "F3"]
    islands = parts_containing(small_plain.footprint, small_plain.centers[:len(row)])
    assert len(islands) == 3


def test_the_plate_has_fewer_parts_with_the_option(small_plain, small_fused):
    islands = len(parts_containing(small_plain.footprint, small_plain.centers[:4]))
    assert len(footprint_parts(small_fused.footprint)) == len(footprint_parts(small_plain.footprint)) - (islands - 1)
    assert len(small_fused.cavities) == len(small_fused.keys) == len(small_plain.keys)


def test_the_section_has_fewer_parts_and_one_hole_per_key(small_plain, small_fused, small_fused_mesh, tmp_path):
    from tests.test_plate import export_mesh
    plain_parts, plain_holes = section_parts_and_holes(export_mesh(small_plain, tmp_path / "plain.stl"))
    fused_parts, fused_holes = section_parts_and_holes(small_fused_mesh)
    islands = len(parts_containing(small_plain.footprint, small_plain.centers[:4]))
    assert fused_parts == plain_parts - (islands - 1)
    assert plain_holes == fused_holes == len(small_fused.keys)


def test_the_fused_plate_passes_the_stl_check(small_fused, tmp_path):
    from tests.test_plate import export_mesh
    path = tmp_path / "check.stl"
    export_mesh(small_fused, path)
    bb = small_fused.plate.BoundingBox()
    _, problems = fpg.check_exported_stl(
        path, expected_bounds=((bb.xmin, bb.ymin, bb.zmin), (bb.xmax, bb.ymax, bb.zmax)))
    assert problems == []


# --------------------------------------------------------------------------
# the real G80-3000 layout (CAD, built once)
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def g80_model():
    return build_model(G80, fuse_f_row=True)


@pytest.fixture(scope="module")
def g80_mesh(g80_model, tmp_path_factory):
    from tests.test_plate import export_mesh
    return export_mesh(g80_model, tmp_path_factory.mktemp("fuse_g80") / "g80.stl")


def test_g80_top_row_is_one_part_of_the_plate_with_a_hole_per_key(g80_model, g80_mesh):
    material, _ = preview.plate_section(g80_mesh)
    parts = footprint_parts(material)
    assert len(parts) == len(footprint_parts(g80_model.footprint))
    assert sum(len(part.interiors) for part in parts) == len(g80_model.keys)

    in_row = {id(k) for k in fpg.top_row_keys(g80_model.keys)}
    row = [c for k, c in zip(g80_model.keys, g80_model.centers) if id(k) in in_row]
    assert len(row) == 16
    holders = {i for i, part in enumerate(parts) for c in row if Polygon(part.exterior).contains(Point(c))}
    assert len(holders) == 1


def test_g80_has_fewer_parts_than_without_the_option(g80_model):
    _, keys = load(G80)
    plain = fpg.plate_footprint(keys, fpg.global_matrix(fpg.OrientationConfig()), MARGIN)
    assert len(footprint_parts(plain)) - len(footprint_parts(g80_model.footprint)) > 1


# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------
def run_cli(*args):
    return subprocess.run([sys.executable, str(REPO_ROOT / "fat_plate_generator.py"), *args],
                          capture_output=True, text=True, cwd=REPO_ROOT)


@pytest.fixture(scope="module")
def cli_runs(small_layout, tmp_path_factory):
    folder = tmp_path_factory.mktemp("fuse_f_row_cli")
    jobs = {"plain": [], "fused": ["--fuse-f-row"],
            "single": ["--single-mesh"], "both": ["--fuse-f-row", "--single-mesh"]}
    results = {}
    for name, extra in jobs.items():
        out = folder / f"{name}.stl"
        run = run_cli("--json", str(small_layout), "--output", str(out), *extra)
        assert run.returncode == 0, run.stderr
        results[name] = (out, run)
    return results


def test_cli_header_names_the_fused_row(cli_runs):
    stdout = cli_runs["fused"][1].stdout
    assert "top row fused (4 keys)" in stdout
    assert "part(s)" in stdout and "\nDone." in stdout
    assert "top row fused" not in cli_runs["plain"][1].stdout


def test_cli_the_option_changes_the_plate(cli_runs):
    assert cli_runs["fused"][0].read_bytes() != cli_runs["plain"][0].read_bytes()


def test_cli_with_single_mesh_the_plate_is_the_same_and_a_note_appears(cli_runs):
    assert cli_runs["both"][0].read_bytes() == cli_runs["single"][0].read_bytes()
    both = cli_runs["both"][1]
    assert "--fuse-f-row has no effect with --single-mesh" in both.stdout
    assert both.stderr == ""                                         # a note, not a warning
    assert "no effect" not in cli_runs["single"][1].stdout

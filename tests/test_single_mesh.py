"""Option --single-mesh: the plate as one connected piece without gaps."""
from __future__ import annotations

import pytest
from shapely.geometry import Point, box
from shapely.ops import unary_union

import fat_plate_generator as fpg
from tests.conftest import ORIENTATION_LAYOUT, build_model
from tests.test_plate import export_mesh, footprint_parts, projected_outline, run_cli
from tools import preview


# --------------------------------------------------------------------------
# connect_footprint() on simple shapes
# --------------------------------------------------------------------------
def test_a_single_part_stays_as_it_is():
    one = box(0, 0, 10, 10)
    assert fpg.connect_footprint(one).symmetric_difference(one).area < 1e-9


def test_two_parts_are_joined_and_only_the_gap_is_filled():
    footprint = unary_union([box(0, 0, 10, 10), box(20, 0, 30, 10)])
    joined = fpg.connect_footprint(footprint)
    assert joined.geom_type == "Polygon" and not list(joined.interiors)
    assert joined.area == pytest.approx(300.0, abs=1e-6)         # two boxes and the 10 x 10 gap
    assert joined.buffer(1e-9).contains(footprint)


def test_every_gap_up_to_the_longest_link_is_filled():
    footprint = unary_union([box(0, 0, 10, 10), box(14, 0, 24, 10), box(34, 0, 44, 10)])
    joined = fpg.connect_footprint(footprint)
    assert joined.geom_type == "Polygon"
    assert joined.area == pytest.approx(440.0, abs=1e-6)         # gaps of 4 and 10 are both filled


def test_gaps_that_are_exactly_as_wide_as_the_longest_link_are_all_filled():
    """The F-row of the 100% layout: several gaps of exactly the same width."""
    row = [box(30 * i, 20, 30 * i + 20, 30) for i in range(4)]    # gaps of 10 between them
    footprint = unary_union(row + [box(0, 0, 110, 10)])           # tied to a base by gaps of 10
    joined = fpg.connect_footprint(footprint)
    assert joined.geom_type == "Polygon" and not list(joined.interiors)
    assert joined.area == pytest.approx(110 * 30, abs=1e-6)


def test_a_notch_wider_than_the_longest_link_stays_open():
    footprint = unary_union([box(0, 0, 40, 10), box(0, 15, 10, 25), box(30, 15, 40, 25)])
    joined = fpg.connect_footprint(footprint)
    assert joined.geom_type == "Polygon"
    assert joined.contains(Point(5, 12.5))                       # the link of 5 is filled
    assert not joined.contains(Point(20, 20))                    # the 20 wide notch is not


def test_enclosed_voids_are_filled():
    ring = unary_union([box(0, 20, 30, 30), box(0, 0, 30, 10), box(0, 10, 10, 20), box(20, 10, 30, 20)])
    assert len(ring.interiors) == 1
    filled = fpg.connect_footprint(ring)
    assert not list(filled.interiors)
    assert filled.area == pytest.approx(900.0, abs=1e-6)


# --------------------------------------------------------------------------
# the plate
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def single_model():
    return build_model(ORIENTATION_LAYOUT, single_mesh=True)


def test_the_default_keeps_the_separate_parts(orientation_model):
    assert len(footprint_parts(orientation_model.footprint)) > 1


def test_single_mesh_gives_one_polygon_that_contains_the_default(orientation_model, single_model):
    footprint = single_model.footprint
    assert footprint.geom_type == "Polygon" and not list(footprint.interiors)
    assert footprint.buffer(1e-6).contains(orientation_model.footprint)
    assert footprint.bounds[:2] == pytest.approx((0.0, 0.0), abs=1e-9)


def test_single_mesh_keeps_every_cutout(orientation_model, single_model):
    assert len(single_model.cavities) == len(orientation_model.cavities)
    for key, cavity in zip(single_model.keys, single_model.cavities):
        outside = projected_outline(cavity).difference(single_model.footprint).area
        assert outside < 1e-4, f"cavity of key {key['label']!r} sticks out by {outside:.4f} mm2"


def test_single_mesh_plate_is_one_piece_with_one_hole_per_key(tmp_path, single_model):
    mesh = export_mesh(single_model, tmp_path / "single.stl")
    material, _ = preview.plate_section(mesh)
    assert len(footprint_parts(material)) == 1
    assert sum(len(part.interiors) for part in footprint_parts(material)) == len(single_model.keys)


def test_cli_single_mesh(repo_root, tmp_path):
    out = tmp_path / "single.stl"
    result = run_cli(repo_root, "--json", str(ORIENTATION_LAYOUT), "--output", str(out), "--single-mesh")
    assert result.returncode == 0, result.stderr
    assert "one connected mesh" in result.stdout
    assert out.exists()


def test_cli_default_is_not_single_mesh(repo_root, tmp_path):
    result = run_cli(repo_root, "--json", str(ORIENTATION_LAYOUT), "--output", str(tmp_path / "x.stl"))
    assert result.returncode == 0, result.stderr
    assert "separated where the keys are far apart" in result.stdout

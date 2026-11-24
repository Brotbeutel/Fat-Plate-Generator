"""Templates with outer walls (closed cells) give the same cutter as open shells.

The templates in the repository are open shells.  A closed variant is made in a
temporary folder by adding a closed box around the cell; no template file of the
repository is changed.
"""
from __future__ import annotations

import dataclasses
import functools
from pathlib import Path

import numpy as np
import pytest
import trimesh
from shapely.geometry import box as shapely_box

import fat_plate_generator as fpg
from fat_plate_generator import TemplateError
from tests.conftest import ORIENTATION_LAYOUT
from tests.test_templates import (REAL_TEMPLATES, ROOT, box_mesh, cutter_mesh,
                                  section_polygon, write_mesh)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def close_cell(source: Path, target: Path) -> Path:
    """Write a closed variant of a template: the mesh plus a closed box around it.

    The box has the XY extent of the mesh and the same height, so its walls run
    along the boundary of the cell (the outer wall).
    """
    mesh = trimesh.load(source, force="mesh", process=False)
    rim = trimesh.creation.box(bounds=mesh.bounds)
    target.parent.mkdir(parents=True, exist_ok=True)
    return write_mesh(trimesh.util.concatenate([mesh, rim]), target)


@functools.lru_cache(maxsize=None)
def template_pair(name, kind):
    """Open and closed variant of a repository template, loaded and built once."""
    import tempfile

    closed_path = close_cell(ROOT / name, Path(tempfile.mkdtemp()) / Path(name).name)
    result = {}
    for label, path in (("open", ROOT / name), ("closed", closed_path)):
        template = fpg.load_template(path, kind)
        result[label] = (template, fpg.template_cutter(template, fpg.IDENTITY_MATRIX))
    return result


# --------------------------------------------------------------------------
# every template of the repository: open shell and closed cell agree
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name, kind", REAL_TEMPLATES)
def test_closed_cell_gives_the_same_template(name, kind):
    pair = template_pair(name, kind)
    (opened, _), (closed, _) = pair["open"], pair["closed"]
    assert closed.warnings == [] and opened.warnings == []
    assert closed.vertex_count == opened.vertex_count
    assert len(closed.layers) == len(opened.layers)
    for a, b in zip(opened.layers, closed.layers):
        assert (a.z0, a.z1) == (b.z0, b.z1)
        assert len(a.rings) == len(b.rings)
        for ring_a, ring_b in zip(a.rings, b.rings):
            assert np.array_equal(ring_a.lines, ring_b.lines)      # same corners, same order


@pytest.mark.parametrize("name, kind", REAL_TEMPLATES)
def test_closed_cell_gives_the_same_cutter(name, kind):
    pair = template_pair(name, kind)
    (opened, open_cutter), (closed, closed_cutter) = pair["open"], pair["closed"]
    assert closed_cutter.Volume() == pytest.approx(open_cutter.Volume(), rel=1e-9)
    open_mesh, closed_mesh = cutter_mesh(open_cutter), cutter_mesh(closed_cutter)
    for layer in opened.layers:
        for fraction in (0.1, 0.35, 0.5, 0.65, 0.9):
            z = layer.z0 + (layer.z1 - layer.z0) * fraction
            difference = section_polygon(open_mesh, z).symmetric_difference(
                section_polygon(closed_mesh, z)).area
            assert difference <= 1e-9, f"{name} z={z:.4f}: sections differ by {difference} mm2"


# --------------------------------------------------------------------------
# end to end: same plate from open and closed copies of all templates
# --------------------------------------------------------------------------
def test_plate_from_closed_templates_equals_plate_from_open_templates(tmp_path):
    opened = fpg.Settings()
    closed_set = {}
    for field in dataclasses.fields(fpg.TemplateSet):
        source = Path(getattr(opened.templates, field.name))
        closed_set[field.name] = close_cell(source, tmp_path / "closed" / source.name)
    closed = dataclasses.replace(opened, templates=fpg.TemplateSet(**closed_set))

    outputs = {}
    for label, settings in (("open", opened), ("closed", closed)):
        outputs[label] = tmp_path / f"{label}.stl"
        fpg.generate(ORIENTATION_LAYOUT, settings, output=outputs[label])
    open_bytes, closed_bytes = outputs["open"].read_bytes(), outputs["closed"].read_bytes()
    if open_bytes != closed_bytes:                       # fall back to the geometry, see the report
        meshes = {label: trimesh.load(path, force="mesh") for label, path in outputs.items()}
        assert len(meshes["open"].faces) == len(meshes["closed"].faces)
        assert meshes["closed"].volume == pytest.approx(meshes["open"].volume, rel=1e-12)
        assert np.allclose(meshes["closed"].bounds, meshes["open"].bounds, atol=1e-9)
    assert open_bytes == closed_bytes


# --------------------------------------------------------------------------
# rim detection on synthetic templates
# --------------------------------------------------------------------------
def test_closed_cell_with_two_cutouts_keeps_both_and_drops_the_rim(tmp_path):
    parts = [box_mesh(30, 20, -5, 1.2), box_mesh(6, 6, -5, 1.2, cx=-8), box_mesh(6, 6, -5, 1.2, cx=8)]
    path = write_mesh(trimesh.util.concatenate(parts), tmp_path / "two.stl")
    template = fpg.load_template(path, "socket")
    assert [len(layer.rings) for layer in template.layers] == [2]
    assert not any("dangling" in w for w in template.warnings)
    mesh = cutter_mesh(fpg.template_cutter(template, fpg.IDENTITY_MATRIX))
    assert section_polygon(mesh, -2.0).area == pytest.approx(36 + 36, abs=1e-9)


def test_a_contour_that_fills_the_whole_extent_stays_a_cutout(tmp_path):
    """The rim is only recognised if it encloses something."""
    path = write_mesh(box_mesh(14, 14, -5, 1.2), tmp_path / "full.stl")
    template = fpg.load_template(path, "socket")
    (ring,) = template.layers[0].rings
    points = ring.at(-2.0)
    assert len(points) == 4
    assert points.min(axis=0) == pytest.approx((-7, -7)) and points.max(axis=0) == pytest.approx((7, 7))


def test_nested_contours_inside_a_closed_cell_are_refused(tmp_path):
    """Only the outer wall of the cell is dropped; a contour inside another one stays an error.

    The middle box does not fill the whole extent, so it is no rim."""
    parts = [box_mesh(24, 24, -5, 1.2), box_mesh(14, 10, -5, 1.2), box_mesh(4, 4, -5, 1.2)]
    path = write_mesh(trimesh.util.concatenate(parts), tmp_path / "nested_in_cell.stl")
    with pytest.raises(TemplateError, match="nested"):
        fpg.load_template(path, "socket")


def test_a_hole_in_the_outer_wall_is_still_reported(tmp_path):
    """A defect of a closed cell is reported like any other open mesh: as dangling contour points."""
    rim = trimesh.creation.box(extents=(30, 20, 6.2))
    rim.apply_translation((0, 0, (fpg.PLATE_Z_MIN + fpg.PLATE_Z_MAX) / 2))
    rim.update_faces(np.arange(len(rim.faces)) != 0)                 # one triangle of a wall is missing
    path = write_mesh(trimesh.util.concatenate([rim, box_mesh(6, 6, -5, 1.2)]), tmp_path / "hole.stl")
    template = fpg.load_template(path, "socket")
    assert any("dangling contour point" in w for w in template.warnings), template.warnings
    assert [len(layer.rings) for layer in template.layers] == [1]


# --------------------------------------------------------------------------
# _rim_indices
# --------------------------------------------------------------------------
CELL = np.array([[-10.0, -5.0, -5.0], [10.0, 5.0, 1.2]])             # vertices that give the extent


def rim_of(*boxes):
    return fpg._rim_indices([shapely_box(*b) for b in boxes], CELL)


def test_rim_is_the_contour_that_spans_the_cell_and_encloses_another():
    assert rim_of((-10, -5, 10, 5), (-3, -3, 3, 3)) == [0]
    assert rim_of((-3, -3, 3, 3), (-10, -5, 10, 5)) == [1]             # order does not matter


def test_no_rim_without_an_enclosed_contour():
    assert rim_of((-10, -5, 10, 5)) == []
    assert rim_of((-10, -5, 10, 5), (-3, 0, 12, 3)) == []             # the second one leaves the cell: not enclosed


def test_no_rim_if_a_side_does_not_reach_the_extent():
    assert rim_of((-10, -5, 10, 4), (-3, -3, 3, 3)) == []
    assert rim_of((-9, -5, 10, 5), (-3, -3, 3, 3)) == []


def test_rim_tolerance():
    inside, outside = fpg.RIM_TOLERANCE / 2, fpg.RIM_TOLERANCE * 2
    assert rim_of((-10 + inside, -5, 10, 5), (-3, -3, 3, 3)) == [0]
    assert rim_of((-10 + outside, -5, 10, 5), (-3, -3, 3, 3)) == []

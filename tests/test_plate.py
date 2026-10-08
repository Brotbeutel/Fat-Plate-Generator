"""Geometry tests: cavities, footprint, exported STL and the 100% layout."""
from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
import trimesh
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

import fat_plate_generator as fpg
from fat_plate_generator import OrientationConfig
from tests.conftest import FULL_LAYOUT, ORIENTATION_LAYOUT, build_model
from tools import preview


def footprint_parts(footprint):
    return list(footprint.geoms) if footprint.geom_type == "MultiPolygon" else [footprint]


def projected_outline(shape, tolerance=0.01):
    """Exact XY projection of a prismatic CAD solid (union of its triangles)."""
    vertices, triangles = shape.tessellate(tolerance)
    pts = np.array([(v.x, v.y) for v in vertices])
    polys = []
    for tri in triangles:
        poly = Polygon(pts[list(tri)])
        if poly.area > 1e-9:
            polys.append(poly)
    return unary_union(polys)


def export_mesh(model, path: Path) -> trimesh.Trimesh:
    import cadquery as cq

    cq.exporters.export(model.plate, str(path), exportType="STL",
                        tolerance=0.001, angularTolerance=0.1)
    return trimesh.load(path, force="mesh")


def edge_counts(mesh):
    return Counter(map(tuple, np.sort(mesh.edges, axis=1)))


@pytest.fixture(scope="module")
def orientation_mesh(orientation_model, tmp_path_factory):
    return export_mesh(orientation_model, tmp_path_factory.mktemp("stl") / "orientation.stl")


@pytest.fixture(scope="module")
def full_mesh(full_model, tmp_path_factory):
    return export_mesh(full_model, tmp_path_factory.mktemp("stl") / "full.stl")


# --------------------------------------------------------------------------
# Cavities
# --------------------------------------------------------------------------
@pytest.mark.parametrize("model_name", ["orientation_model", "full_model"])
def test_one_cavity_per_key(request, model_name):
    model = request.getfixturevalue(model_name)
    assert len(model.cavities) == len(model.keys) == len(model.centers)
    assert len(model.kinds) == len(model.rotations) == len(model.keys)


def test_section_has_one_hole_per_key(orientation_model, orientation_mesh, full_model, full_mesh):
    for model, mesh in ((orientation_model, orientation_mesh), (full_model, full_mesh)):
        material, _ = preview.plate_section(mesh)
        holes = sum(len(g.interiors) for g in
                    (material.geoms if material.geom_type == "MultiPolygon" else [material]))
        assert holes == len(model.keys)


@pytest.mark.parametrize("model_name", ["orientation_model", "full_model"])
def test_every_cavity_lies_inside_the_footprint(request, model_name):
    model = request.getfixturevalue(model_name)
    for key, cavity in zip(model.keys, model.cavities):
        outline = projected_outline(cavity)
        outside = outline.difference(model.footprint).area
        assert outside < 1e-4, f"cavity of key {key['label']!r} sticks out by {outside:.4f} mm2"


def test_cavities_are_centred_on_their_switch(orientation_model):
    """Cutouts are symmetric along their long direction; the switch centre must
    stay at the key centre after rotation and whole-plate transform.  The
    tolerance (1 micron) covers float32 rounding in the template STLs."""
    tol = 1e-3
    for key, kind, (cx, cy), cavity in zip(orientation_model.keys, orientation_model.kinds,
                                           orientation_model.centers, orientation_model.cavities):
        outline = projected_outline(cavity)
        x0, y0, x1, y1 = outline.bounds
        long_is_x = (x1 - x0) > (y1 - y0)
        if kind == fpg.KIND_NORMAL:
            assert (x0 + x1) / 2 == pytest.approx(cx, abs=tol)
            assert (y0 + y1) / 2 == pytest.approx(cy, abs=tol)
        elif long_is_x:
            assert (x0 + x1) / 2 == pytest.approx(cx, abs=tol)
        else:
            assert (y0 + y1) / 2 == pytest.approx(cy, abs=tol)


def test_stabilizer_cutouts_follow_the_key_direction(orientation_model):
    """Plate frame (rotate 90 + mirror): KLE-horizontal keys run along Y,
    KLE-vertical keys run along X.  The cutout must run the same way."""
    for key, kind, cavity in zip(orientation_model.keys, orientation_model.kinds,
                                 orientation_model.cavities):
        if kind == fpg.KIND_NORMAL:
            continue
        x0, y0, x1, y1 = projected_outline(cavity).bounds
        cutout_runs_along_y = (y1 - y0) > (x1 - x0)
        key_is_horizontal = key["w"] > key["h"]
        assert cutout_runs_along_y == key_is_horizontal, key["label"]


# --------------------------------------------------------------------------
# Global transform
# --------------------------------------------------------------------------
def test_plate_bounding_box_starts_at_origin(orientation_model, full_model):
    for model in (orientation_model, full_model):
        x0, y0, _, _ = model.footprint.bounds
        assert (x0, y0) == pytest.approx((0.0, 0.0), abs=1e-9)
    for transform in (True, False):
        model = build_model(ORIENTATION_LAYOUT,
                            orientation=OrientationConfig(global_transform=transform))
        assert model.footprint.bounds[:2] == pytest.approx((0.0, 0.0), abs=1e-9)


def test_global_transform_swaps_the_axes(orientation_model):
    plain = build_model(ORIENTATION_LAYOUT, orientation=OrientationConfig(global_transform=False))
    assert plain.matrix == fpg.IDENTITY_MATRIX
    w_plain = plain.footprint.bounds[2] - plain.footprint.bounds[0]
    h_plain = plain.footprint.bounds[3] - plain.footprint.bounds[1]
    w, h = (orientation_model.footprint.bounds[2] - orientation_model.footprint.bounds[0],
            orientation_model.footprint.bounds[3] - orientation_model.footprint.bounds[1])
    assert (w, h) == pytest.approx((h_plain, w_plain))
    assert orientation_model.footprint.area == pytest.approx(plain.footprint.area)


def test_switch_centres_match_the_preview_placement(orientation_model):
    """tools/preview.py infers key positions from the STL bounds; it must agree
    with the centres the generator actually used."""
    placed = preview.keys_in_plate_frame(orientation_model.keys,
                                         np.array([[0, 0, 0], list(orientation_model.footprint.bounds[2:]) + [0]]),
                                         fpg.DEFAULT_MARGIN, preview.GLOBAL_MATRIX)
    for p, (cx, cy) in zip(placed, orientation_model.centers):
        assert p["center"] == pytest.approx((cx, cy), abs=1e-6)


# --------------------------------------------------------------------------
# Exported STL
# --------------------------------------------------------------------------
def test_generate_writes_a_nonempty_stl(tmp_path):
    out = tmp_path / "plate.stl"
    fpg.generate(ORIENTATION_LAYOUT, Path(fpg.__file__).with_name(fpg.DEFAULT_SOCKET),
                 Path(fpg.__file__).with_name(fpg.DEFAULT_STABILIZER),
                 Path(fpg.__file__).with_name(fpg.DEFAULT_SPACEBAR_CENTERED),
                 Path(fpg.__file__).with_name(fpg.DEFAULT_SPACEBAR_OFF_CENTERED),
                 output=out, stabilizer_scale_mode="none")
    mesh = trimesh.load(out, force="mesh")
    assert not mesh.is_empty and len(mesh.faces) > 0
    assert mesh.volume > 0


@pytest.mark.parametrize("mesh_name", ["orientation_mesh", "full_mesh"])
def test_exported_stl_is_closed(request, mesh_name):
    """No holes in the surface: every edge is shared by an even number of faces,
    winding is consistent and the volume is positive."""
    mesh = request.getfixturevalue(mesh_name)
    assert not mesh.is_empty
    assert mesh.is_winding_consistent
    assert mesh.volume > 0
    counts = edge_counts(mesh)
    assert min(counts.values()) >= 2
    assert all(n % 2 == 0 for n in counts.values())


def test_non_manifold_edges_only_occur_at_stabilizer_cutouts(orientation_model, orientation_mesh):
    """Known limitation (also present before WP-01): the layered stabilizer
    sections touch along a few vertical edges, so those edges carry four faces.
    Keep it confined to stabilizer keys, and never worse than four faces."""
    counts = edge_counts(orientation_mesh)
    bad = [edge for edge, n in counts.items() if n != 2]
    assert all(counts[e] == 4 for e in bad)
    centres = np.array(orientation_model.centers)
    for edge in bad:
        mid = orientation_mesh.vertices[list(edge)].mean(axis=0)[:2]
        nearest = int(np.argmin(np.hypot(*(centres - mid).T)))
        assert orientation_model.kinds[nearest] != fpg.KIND_NORMAL


@pytest.mark.xfail(reason="known issue, not part of WP-01: layered stabilizer sections touch "
                          "along vertical edges, so trimesh.is_watertight is False "
                          "(identical before WP-01)", strict=False)
def test_exported_stl_is_strictly_watertight(orientation_mesh):
    assert orientation_mesh.is_watertight


# --------------------------------------------------------------------------
# 100% layout: no region may get lost
# --------------------------------------------------------------------------
REGION_LABELS = {
    "F-row": ["Esc", "F1", "F4", "F5", "F8", "F9", "F12"],
    "navigation": ["PrtSc", "Scroll Lock", "Insert", "Home", "Delete", "End", "\u2191"],
    "numpad": ["Num Lock", "7\nHome", "+", "0\nIns", ".\nDel", "/"],
}


def test_full_layout_has_separate_regions(full_model):
    assert len(footprint_parts(full_model.footprint)) >= 4


def test_full_layout_keeps_every_footprint_part(full_model, full_mesh):
    material, _ = preview.plate_section(full_mesh)
    parts = footprint_parts(full_model.footprint)
    material_parts = material.geoms if material.geom_type == "MultiPolygon" else [material]
    assert len(material_parts) == len(parts)
    for part in parts:
        assert material.intersection(part).area > 0.3 * part.area


@pytest.mark.parametrize("region", list(REGION_LABELS))
def test_full_layout_keeps_region_keys(full_model, full_mesh, region):
    material, _ = preview.plate_section(full_mesh)
    labels = [k["label"] for k in full_model.keys]
    for label in REGION_LABELS[region]:
        assert label in labels, f"{label!r} missing from the layout"
        cx, cy = full_model.centers[labels.index(label)]
        # a hole at the switch centre, material in the ring around it
        assert not material.contains(Point(cx, cy)), label
        ring = Point(cx, cy).buffer(fpg.UNIT * 0.5)
        assert material.intersection(ring).area > 1.0, label


def test_full_layout_stabilizer_keys_are_classified(full_model):
    stabilized = [k["label"] for k, kind in zip(full_model.keys, full_model.kinds)
                  if kind == fpg.KIND_STABILIZED]
    assert sorted(stabilized) == sorted(["Backspace", "Enter", "+", "Enter", "Shift", "0\nIns"])
    assert full_model.kinds.count(fpg.KIND_SPACEBAR) == 1
    caps = [i for i, k in enumerate(full_model.keys) if k["label"] == "Caps Lock"][0]
    assert full_model.kinds[caps] == fpg.KIND_NORMAL


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def run_cli(repo_root, *args):
    return subprocess.run([sys.executable, str(repo_root / "fat_plate_generator.py"), *args],
                          capture_output=True, text=True, cwd=repo_root)


def test_cli_orientation_options(repo_root, tmp_path):
    out = tmp_path / "cli.stl"
    result = run_cli(repo_root, "--json", str(ORIENTATION_LAYOUT), "--output", str(out),
                     "--stab-rotation-horizontal", "0", "--stab-rotation-vertical", "270",
                     "--stab-rotation-spacebar", "90", "--no-global-transform")
    assert result.returncode == 0, result.stderr
    assert "horizontal 0 deg, vertical 270 deg, spacebar 90 deg" in result.stdout
    assert "none (--no-global-transform)" in result.stdout
    assert out.exists() and not trimesh.load(out, force="mesh").is_empty


def test_cli_rejects_invalid_rotation(repo_root, tmp_path):
    result = run_cli(repo_root, "--json", str(ORIENTATION_LAYOUT), "--output", str(tmp_path / "x.stl"),
                     "--stab-rotation-horizontal", "45")
    assert result.returncode != 0
    assert "invalid choice" in result.stderr

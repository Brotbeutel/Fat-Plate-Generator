"""Templates: one exact loader for socket, stabilizer and spacebar.

Synthetic templates make the geometry assertions deterministic; the real
template STLs are only compared with their own meshes, so the tests keep
working when the templates are rebuilt.
"""
from __future__ import annotations

import functools
from pathlib import Path

import numpy as np
import pytest
import trimesh
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

import fat_plate_generator as fpg
from fat_plate_generator import TemplateError

ROOT = Path(fpg.__file__).parent
STL_RESOLUTION = 1e-6     # STL stores float32: 7.28 is stored as 7.2800002
REAL_TEMPLATES = [
    ("switch_socket.stl", "socket"),
    ("stabilizer.stl", "stabilizer"),
    ("stabilzer_spacebar.stl", "spacebar"),
    ("stabilzer_spacebar_off-center.stl", "spacebar"),
]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def section_polygon(mesh: trimesh.Trimesh, z: float):
    """Cross-section of a mesh at height z as a shapely geometry.

    Independent of the generator: the triangles are cut with trimesh and the
    segments joined with shapely.  End points are rounded to 1e-9 mm here (test
    code only) so that the segments of neighbouring triangles meet.
    """
    segments = trimesh.intersections.mesh_plane(mesh, [0, 0, 1], [0, 0, z])
    lines = [LineString(np.round(segment[:, :2], 9)) for segment in segments
             if np.abs(segment[0] - segment[1]).max() > 1e-12]
    return unary_union(list(polygonize(unary_union(lines)))) if lines else Polygon()


def cutter_mesh(cutter) -> trimesh.Trimesh:
    vertices, triangles = cutter.tessellate(1e-3)       # all faces are planar, so this is exact
    return trimesh.Trimesh([(v.x, v.y, v.z) for v in vertices], triangles, process=True)


def write_mesh(mesh: trimesh.Trimesh, path: Path) -> Path:
    mesh.export(path)
    return path


def box_mesh(x, y, z0, z1, cx=0.0, cy=0.0):
    mesh = trimesh.creation.box(extents=(x, y, z1 - z0))
    mesh.apply_translation((cx, cy, (z0 + z1) / 2))
    return mesh


def frustum_mesh(half_bottom, half_top, z0, z1):
    corners = lambda h, z: [(sx * h, sy * h, z) for sx in (-1, 1) for sy in (-1, 1)]
    return trimesh.convex.convex_hull(np.array(corners(half_bottom, z0) + corners(half_top, z1)))


def half_size(polygon):
    x0, y0, x1, y1 = polygon.bounds
    assert (x1 - x0) == pytest.approx(y1 - y0, abs=1e-9)
    return (x1 - x0) / 2


# --------------------------------------------------------------------------
# slopes stay slopes (the reason for this loader)
# --------------------------------------------------------------------------
def test_a_slope_is_lofted_exactly(tmp_path):
    """Half size 7.28 at z=-1.8 shrinking to 7.0 at z=-1.5, as in the socket."""
    path = write_mesh(frustum_mesh(7.28, 7.0, -1.8, -1.5), tmp_path / "frustum.stl")
    template = fpg.load_template(path, "socket")
    assert len(template.layers) == 1 and template.vertex_count == 4
    cutter = fpg.template_cutter(template, fpg.IDENTITY_MATRIX)
    mesh = cutter_mesh(cutter)
    for fraction in (0.05, 0.25, 0.5, 0.75, 0.95):
        z = -1.8 + 0.3 * fraction
        expected = 7.28 + (7.0 - 7.28) * fraction
        assert half_size(section_polygon(mesh, z)) == pytest.approx(expected, abs=STL_RESOLUTION)


def test_a_slope_is_not_a_single_step(tmp_path):
    path = write_mesh(frustum_mesh(7.28, 7.0, -1.8, -1.5), tmp_path / "frustum.stl")
    mesh = cutter_mesh(fpg.template_cutter(fpg.load_template(path, "socket"), fpg.IDENTITY_MATRIX))
    sizes = [half_size(section_polygon(mesh, z)) for z in np.linspace(-1.79, -1.51, 8)]
    assert all(a > b for a, b in zip(sizes, sizes[1:])), sizes
    assert sizes[0] > 7.27 and sizes[-1] < 7.01


def test_vertical_walls_stay_vertical(tmp_path):
    path = write_mesh(box_mesh(14.0, 14.0, -5.0, 1.2), tmp_path / "box.stl")
    mesh = cutter_mesh(fpg.template_cutter(fpg.load_template(path, "socket"), fpg.IDENTITY_MATRIX))
    for z in (-4.9, -2.0, 0.0, 1.1):
        assert half_size(section_polygon(mesh, z)) == pytest.approx(7.0, abs=1e-9)


def test_flat_walls_give_four_corners_only(tmp_path):
    """The diagonals of the triangulation are no corners."""
    path = write_mesh(box_mesh(14.0, 14.0, -5.0, 1.2), tmp_path / "box.stl")
    template = fpg.load_template(path, "socket")
    assert [len(r.lines) for layer in template.layers for r in layer.rings] == [4]


# --------------------------------------------------------------------------
# nothing is dropped silently
# --------------------------------------------------------------------------
def test_every_contour_of_a_layer_is_kept(tmp_path):
    left, right = box_mesh(6, 6, -5, 1.2, cx=-10), box_mesh(4, 4, -5, 1.2, cx=10)
    path = write_mesh(trimesh.util.concatenate([left, right]), tmp_path / "two.stl")
    template = fpg.load_template(path, "socket")
    assert [len(layer.rings) for layer in template.layers] == [2]
    mesh = cutter_mesh(fpg.template_cutter(template, fpg.IDENTITY_MATRIX))
    assert section_polygon(mesh, -2.0).area == pytest.approx(36 + 16, abs=1e-9)


def test_nested_contours_are_refused(tmp_path):
    outer, inner = box_mesh(14, 14, -5, 1.2), box_mesh(6, 6, -5, 1.2)
    path = write_mesh(trimesh.util.concatenate([outer, inner]), tmp_path / "nested.stl")
    with pytest.raises(TemplateError, match="nested"):
        fpg.load_template(path, "socket")


def test_missing_and_empty_templates_are_errors(tmp_path):
    with pytest.raises(TemplateError, match="not found"):
        fpg.load_template(tmp_path / "nothing.stl", "socket")
    empty = tmp_path / "empty.stl"
    empty.write_bytes(b"")
    with pytest.raises(Exception):
        fpg.load_template(empty, "socket")


# --------------------------------------------------------------------------
# fixed bounding boxes are checked, never enforced by changing the geometry
# --------------------------------------------------------------------------
def test_exact_bounding_box_gives_no_warning(tmp_path):
    x, y = fpg.TEMPLATE_BOUNDING_BOXES["socket"]
    path = write_mesh(box_mesh(x, y, fpg.PLATE_Z_MIN, fpg.PLATE_Z_MAX), tmp_path / "cell.stl")
    assert fpg.load_template(path, "socket").warnings == []


@pytest.mark.parametrize("extents, expected", [
    ((19.0, 19.05, 6.2), "bounding box x is 19.0000"),
    ((19.05, 19.0478, 6.2), "bounding box y is 19.0478"),
])
def test_deviating_bounding_box_warns(tmp_path, extents, expected):
    path = write_mesh(box_mesh(extents[0], extents[1], fpg.PLATE_Z_MIN, fpg.PLATE_Z_MIN + extents[2]),
                      tmp_path / "cell.stl")
    warnings = fpg.load_template(path, "socket").warnings
    assert any(expected in w for w in warnings), warnings


def test_deviating_height_warns(tmp_path):
    path = write_mesh(box_mesh(19.05, 19.05, fpg.PLATE_Z_MIN, fpg.PLATE_Z_MAX + 0.5), tmp_path / "tall.stl")
    assert any("bounding box top" in w for w in fpg.load_template(path, "socket").warnings)


def test_the_bounding_box_never_changes_the_geometry(tmp_path):
    """A 19.0 mm template is built as 19.0 mm, not stretched to the fixed 19.05 mm."""
    path = write_mesh(box_mesh(19.0, 19.0, fpg.PLATE_Z_MIN, fpg.PLATE_Z_MAX), tmp_path / "small.stl")
    mesh = cutter_mesh(fpg.template_cutter(fpg.load_template(path, "socket"), fpg.IDENTITY_MATRIX))
    assert half_size(section_polygon(mesh, 0.0)) == pytest.approx(9.5, abs=1e-9)


# --------------------------------------------------------------------------
# rotation and mirror go through the same exact matrix for every template
# --------------------------------------------------------------------------
L_OUTLINE = [(0, 0), (6, 0), (6, 2), (2, 2), (2, 5), (0, 5)]      # counter-clockwise


def l_shape_mesh():
    """Asymmetric closed prism (an L), z from -5 to 1.2, built by hand."""
    n = len(L_OUTLINE)
    vertices = [(x, y, -5.0) for x, y in L_OUTLINE] + [(x, y, 1.2) for x, y in L_OUTLINE]
    faces = []
    for i in range(1, n - 1):                                    # fan from the first corner
        faces.append((0, i, i + 1))                              # bottom (reversed below)
    faces = [(a, c, b) for a, b, c in faces] + [(a + n, b + n, c + n) for a, b, c in
                                                [(0, i, i + 1) for i in range(1, n - 1)]]
    for i in range(n):                                           # walls
        j = (i + 1) % n
        faces += [(i, j, j + n), (i, j + n, i + n)]
    return trimesh.Trimesh(vertices, faces, process=True)


@pytest.mark.parametrize("matrix", [
    fpg.IDENTITY_MATRIX, (1, 0, 0, -1), (-1, 0, 0, 1), (0, 1, 1, 0), (0, -1, 1, 0),
])
def test_matrix_maps_the_cutout_exactly(tmp_path, matrix):
    path = write_mesh(l_shape_mesh(), tmp_path / "l.stl")
    template = fpg.load_template(path, "stabilizer")
    cutter = fpg.template_cutter(template, matrix)
    assert cutter.isValid() and cutter.Volume() > 0
    a, b, d, e = matrix
    expected = Polygon([(a * x + b * y, d * x + e * y) for x, y in L_OUTLINE])
    found = section_polygon(cutter_mesh(cutter), -2.0)
    assert found.symmetric_difference(expected).area < 1e-9


# --------------------------------------------------------------------------
# the real templates: the cutter reproduces the template mesh, slopes included
# --------------------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def real_template(name, kind):
    """Template, its own mesh and the section mesh of its cutter (built once)."""
    template = fpg.load_template(ROOT / name, kind)
    source = trimesh.load(ROOT / name, force="mesh")
    cutter = cutter_mesh(fpg.template_cutter(template, fpg.IDENTITY_MATRIX))
    return template, source, cutter


@pytest.mark.parametrize("name, kind", REAL_TEMPLATES)
def test_real_templates_load(name, kind):
    template, _, _ = real_template(name, kind)
    assert template.layers and all(layer.rings for layer in template.layers)
    for lower, upper in zip(template.layers, template.layers[1:]):
        assert lower.z1 == pytest.approx(upper.z0, abs=1e-5)


@pytest.mark.parametrize("name, kind", REAL_TEMPLATES)
def test_real_cutters_follow_their_template_at_every_height(name, kind):
    """At heights inside every layer, including the middle of the slope, the section of
    the cutter and the section of the template mesh agree to 10 micron."""
    template, source, cutter = real_template(name, kind)
    heights = []
    for layer in template.layers:
        heights += [layer.z0 + (layer.z1 - layer.z0) * f for f in (0.1, 0.35, 0.5, 0.65, 0.9)]
    for z in heights:
        wanted, built = section_polygon(source, z), section_polygon(cutter, z)
        distance = wanted.boundary.hausdorff_distance(built.boundary)
        assert distance < 0.01, f"{name} z={z:.3f}: sections differ by {distance * 1000:.1f} um"


@pytest.mark.parametrize("name, kind", REAL_TEMPLATES)
def test_real_templates_keep_their_slopes(name, kind):
    """Somewhere between the first and last layer boundary at least one wall must be
    slanted: the cutter section changes continuously inside a slope layer."""
    template, source, cutter = real_template(name, kind)
    slanted = [layer for layer in template.layers
               if section_polygon(source, layer.z0 + 0.1 * (layer.z1 - layer.z0)).symmetric_difference(
                   section_polygon(source, layer.z1 - 0.1 * (layer.z1 - layer.z0))).area > 1.0]
    for layer in slanted:
        low = section_polygon(cutter, layer.z0 + 0.1 * (layer.z1 - layer.z0)).area
        mid = section_polygon(cutter, 0.5 * (layer.z0 + layer.z1)).area
        high = section_polygon(cutter, layer.z1 - 0.1 * (layer.z1 - layer.z0)).area
        assert low != mid != high and (low - mid) * (mid - high) > 0, (name, layer.z0, low, mid, high)

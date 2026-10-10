#!/usr/bin/env python3
"""Fat Plate Generator

KLE raw JSON -> clean CAD/STL plate.

The normal switch socket is reconstructed from the supplied socket STL.
Stabilized keys use the supplied stabilizer STL as ONE combined cavity
(stabilizer cutout + switch socket).  The stabilizer cross-section is taken
from the actual STL section and preserved as straight CAD geometry; nothing
is scaled, rounded, resampled or smoothed.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from shapely.affinity import affine_transform, rotate, scale, translate
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

VERSION = "0.11"
UNIT = 19.05
DEFAULT_MARGIN = 1
DEFAULT_JSON = "keyboard-layout.json"
DEFAULT_SOCKET = "switch_socket.stl"
DEFAULT_STABILIZER = "stabilizer.stl"
DEFAULT_SPACEBAR_CENTERED = "stabilzer_spacebar.stl"
DEFAULT_SPACEBAR_OFF_CENTERED = "stabilzer_spacebar_off-center.stl"
DEFAULT_OUTPUT = "fat_plate_export.stl"
EPS = 0.02

# ---------------------------------------------------------------------------
# Orientation of stabilizer cutouts and of the whole plate
# ---------------------------------------------------------------------------
# 2D linear maps are kept as exact integer tuples (a, b, d, e) meaning
#     x' = a*x + b*y
#     y' = d*x + e*y
# so that rotations by multiples of 90 degrees never introduce float noise.
ROTATION_CHOICES = (0, 90, 180, 270)
ROTATION_MATRICES = {
    0: (1, 0, 0, 1),
    90: (0, -1, 1, 0),      # counter-clockwise, as in math (x right, y up)
    180: (-1, 0, 0, -1),
    270: (0, 1, -1, 0),
}
IDENTITY_MATRIX = ROTATION_MATRICES[0]
MIRROR_X_MATRIX = (-1, 0, 0, 1)  # x -> -x (mirror at the YZ plane)


@dataclass(frozen=True)
class OrientationConfig:
    """Central configuration of all orientation-related transformations.

    Frames
    ------
    * KLE frame: x to the right, y DOWN (= towards the typist), as stored in
      the KLE JSON, scaled to mm.  KLE y is not flipped anywhere; instead the
      whole-plate transform below contains the mirror that fixes handedness.
    * Plate frame: KLE frame after the whole-plate transform, shifted so that
      the plate's XY bounding box starts at (0, 0).

    Order of operations (see ``build_plate_model``)
    ----------------------------------------------
    1. Per stabilizer: the cutout template (long axis X, wide notches towards
       -Y) is rotated about its switch centre by ``stab_rotation_*`` degrees
       (counter-clockwise, in the KLE frame).
    2. Whole plate (footprint, switch centres, cutouts): rotated by
       ``global_rotation`` degrees about the origin, then mirrored along X if
       ``global_mirror_x``.  With the defaults (180 deg + mirror X) this is
       exactly the KLE -> CAD conversion (y down -> y up), (x, y) -> (x, -y),
       without any further turn of the plate.
    3. Everything is shifted so the plate's bounding box (including margin)
       starts at (0, 0).

    Defaults
    --------
    horizontal 180, vertical 270, spacebar 180, whole plate 180 deg + mirror X.
    The stabilizer rotations are measured in the KLE frame, about the switch
    centre.  Horizontal and spacebar cutouts have their long axis along X and
    the wider side of the cutout (the template is about 0.7 mm wider towards
    -Y) ends up towards +Y, the typist; vertical cutouts have their long axis
    along Y.  The first version of these defaults followed the manual Blender
    corrections of the old TODO.txt (whole plate "rotate 90 deg, mirror X",
    vertical 90); the project owner then adjusted them after checking the
    exported plate.  The old whole-plate transform is still available as
    ``global_rotation=90`` (a transposition, (x, y) -> (y, x)).

    "Rotate 180 deg, then mirror X" equals "flip KLE y".  That is the
    KLE -> CAD handedness fix and nothing else; any other ``global_rotation``
    just turns the finished plate by a further multiple of 90 deg.
    """

    stab_rotation_horizontal: int = 180
    stab_rotation_vertical: int = 270
    stab_rotation_spacebar: int = 180
    global_transform: bool = True
    global_rotation: int = 180
    global_mirror_x: bool = True

    def __post_init__(self):
        for name in ("stab_rotation_horizontal", "stab_rotation_vertical",
                     "stab_rotation_spacebar", "global_rotation"):
            value = getattr(self, name)
            if value not in ROTATION_CHOICES:
                raise ValueError(f"{name} must be one of {ROTATION_CHOICES}, got {value!r}")


def matrix_multiply(outer, inner):
    """Linear map that applies ``inner`` first and then ``outer``."""
    a, b, d, e = outer
    ia, ib, id_, ie = inner
    return (a * ia + b * id_, a * ib + b * ie,
            d * ia + e * id_, d * ib + e * ie)


def rotation_matrix(degrees):
    if degrees not in ROTATION_MATRICES:
        raise ValueError(f"Rotation must be one of {ROTATION_CHOICES}, got {degrees!r}")
    return ROTATION_MATRICES[degrees]


def global_matrix(orientation: OrientationConfig):
    """Linear part of the whole-plate transform (rotation, then optional mirror X)."""
    if not orientation.global_transform:
        return IDENTITY_MATRIX
    m = rotation_matrix(orientation.global_rotation)
    if orientation.global_mirror_x:
        m = matrix_multiply(MIRROR_X_MATRIX, m)
    return m


def apply_matrix(matrix, x, y):
    a, b, d, e = matrix
    return a * x + b * y, d * x + e * y


def parse_kle(data):
    keys = []
    x = y = 0.0
    reset_x = reset_y = 0.0
    p = {"w": 1.0, "h": 1.0, "x2": 0.0, "y2": 0.0,
         "w2": 1.0, "h2": 1.0, "r": 0.0, "rx": 0.0, "ry": 0.0}

    for row in data:
        for item in row:
            if isinstance(item, dict):
                if "r" in item:
                    p["r"] = item["r"]
                if "rx" in item:
                    p["rx"] = item["rx"]
                    reset_x = p["rx"]
                    x = reset_x
                if "ry" in item:
                    p["ry"] = item["ry"]
                    reset_y = p["ry"]
                    y = reset_y
                x += item.get("x", 0)
                y += item.get("y", 0)
                p["w"] = item.get("w", 1.0)
                p["h"] = item.get("h", 1.0)
                p["x2"] = item.get("x2", 0.0)
                p["y2"] = item.get("y2", 0.0)
                p["w2"] = item.get("w2", p["w"])
                p["h2"] = item.get("h2", p["h"])
                continue

            keys.append({"label": item, **p, "x": x, "y": y})
            x += p["w"]
            p.update(w=1.0, h=1.0, x2=0.0, y2=0.0, w2=1.0, h2=1.0)
        x = reset_x
        y += 1.0
    return keys


def local_key_shape(k):
    a = box(0, 0, k["w"], k["h"])
    b = box(k["x2"], k["y2"],
            k["x2"] + k["w2"], k["y2"] + k["h2"])
    g = unary_union((a, b))
    if abs(k["r"]) > 1e-12:
        g = rotate(g, k["r"],
                   origin=(k["rx"] - k["x"], k["ry"] - k["y"]),
                   use_radians=False)
    return g


def switch_center(k):
    cx = k["x"] + k["w"] / 2.0
    cy = k["y"] + k["h"] / 2.0
    if abs(k["r"]) > 1e-12:
        a = math.radians(k["r"])
        dx, dy = cx - k["rx"], cy - k["ry"]
        cx = k["rx"] + dx * math.cos(a) - dy * math.sin(a)
        cy = k["ry"] + dx * math.sin(a) + dy * math.cos(a)
    return cx * UNIT, cy * UNIT


# ---------------------------------------------------------------------------
# Template STLs
# ---------------------------------------------------------------------------
# Every template is a plate cell with the cutout in it.  The outer size of each
# template is fixed (TEMPLATE_BOUNDING_BOXES, PLATE_Z_MIN/MAX) so that new
# templates can be designed against it.  The bounding box is only CHECKED: a
# deviation produces a warning and never changes the geometry.  Only the
# contour of the cutout is read from the STL; the outer rim of the cell is
# ignored.  Socket, stabilizer and spacebar are read and built the same way.
PLATE_Z_MIN = -5.0
PLATE_Z_MAX = 1.2
TEMPLATE_BOUNDING_BOXES = {      # x, y size in mm
    "socket": (19.05, 19.05),
    "stabilizer": (36.3875, 19.05),
    "spacebar": (112.5889, 19.05),
}
BOUNDING_BOX_TOLERANCE = 0.001   # mm; only decides whether a warning is printed
# STL stores float32, so one horizontal plane shows up with slightly different
# z values (about 1e-7 mm).  Values closer than LEVEL_TOLERANCE are the same plane.
# This only finds the planes; no coordinate is changed.
LEVEL_TOLERANCE = 1e-6           # mm
# Contour points computed from neighbouring triangles are the same point if they
# agree to floating point noise.  Only used to join them; no coordinate is changed.
POINT_TOLERANCE = 1e-9           # mm
# The triangles of a flat wall leave contour points in the middle of the wall.
# They are no corners and would slide along the wall between two heights, so
# they are dropped.  Douglas-Peucker guarantees that every dropped point lies
# within FLAT_WALL_TOLERANCE of the straight wall that remains, so the shape
# changes by at most this much (50 nm).  The current templates carry about
# 20 nm of noise on such points; for exact templates this can go down to 1e-9.
FLAT_WALL_TOLERANCE = 5e-5       # mm
# A defect of the mesh (for example a step of half a micron whose triangles run
# slantwise) can make two corners fall together inside a layer.  The tolerance is
# then raised step by step, at most by these factors, until the layer can be
# lofted; every raise is reported as a warning with the tolerance that was used.
FLAT_WALL_RELAXATIONS = (10, 100)
MIN_CORNER_DISTANCE = 1e-6       # mm; closer corners cannot be lofted
# If even that does not help but the walls of the layer hardly move between its
# two ends (by less than STRAIGHT_LAYER_TOLERANCE at most: a template whose walls
# lean by a micron), the layer is built as a straight prism from its section at
# half height, and a warning says by how much the walls lean.  A layer whose walls
# really move (a slope) is never straightened: that is an error.
STRAIGHT_LAYER_TOLERANCE = 5e-3  # mm


class TemplateError(ValueError):
    """A template STL cannot be used as a cutter."""


@dataclass
class Ring:
    """One closed contour of a layer, given as the mesh edges its vertices lie on.

    ``lines[i]`` holds the two end points (x, y, z) of the mesh edge of vertex i.
    Evaluating the lines at a height gives the contour at that height, so a
    slanted wall stays exactly slanted, and the vertex order is the same at
    every height (which is what a loft between two heights needs).
    """

    lines: np.ndarray            # shape (N, 2, 3)

    def at(self, z):
        p0, p1 = self.lines[:, 0], self.lines[:, 1]
        t = (z - p0[:, 2]) / (p1[:, 2] - p0[:, 2])
        return p0[:, :2] + t[:, None] * (p1[:, :2] - p0[:, :2])


@dataclass
class Layer:
    z0: float
    z1: float
    rings: list


@dataclass
class Template:
    path: Path
    kind: str
    bounds: np.ndarray           # exact bounds of the STL, shape (2, 3)
    layers: list
    warnings: list               # readable problems found while reading

    @property
    def vertex_count(self):
        return sum(len(r.lines) for layer in self.layers for r in layer.rings)


def _exact_mesh(path: Path):
    """Read an STL; vertices are merged only where they are exactly equal."""
    if not path.is_file():
        raise TemplateError(f"template STL not found: {path}")
    mesh = trimesh.load(path, force="mesh", process=False)
    if mesh.is_empty or len(mesh.faces) == 0:
        raise TemplateError(f"{path.name}: the template STL is empty")
    vertices, inverse = np.unique(np.asarray(mesh.vertices, dtype=float),
                                  axis=0, return_inverse=True)
    faces = inverse.reshape(-1)[np.asarray(mesh.faces)]
    faces = faces[[len(set(f)) == 3 for f in faces.tolist()]]
    return vertices, faces, np.array([vertices.min(axis=0), vertices.max(axis=0)])


def _levels(z_values):
    """Heights of the horizontal planes of a template (see LEVEL_TOLERANCE)."""
    groups = [[float(z)] for z in np.unique(z_values)[:1]]
    for z in np.unique(z_values)[1:]:
        if z - groups[-1][-1] <= LEVEL_TOLERANCE:
            groups[-1].append(float(z))
        else:
            groups.append([float(z)])
    return [sum(g) / len(g) for g in groups]


def _corner_indices(points, tolerance):
    """Indices of the corners of a closed polygon.

    All other points lie within ``tolerance`` of the straight line between the
    corners next to them (Douglas-Peucker on both halves of the ring, starting
    from two points that are certainly corners: the extreme ones).
    """
    count = len(points)
    first = int(np.argmax(np.hypot(*(points - points.mean(axis=0)).T)))
    second = int(np.argmax(np.hypot(*(points - points[first]).T)))
    keep = {first, second}

    def stretch(i, j):
        return [(i + k) % count for k in range(((j - i) % count) + 1)]

    stack = [stretch(first, second), stretch(second, first)]
    while stack:
        path = stack.pop()
        if len(path) < 3:
            continue
        start, end = points[path[0]], points[path[-1]]
        direction = end - start
        length = float(np.hypot(*direction))
        offsets = points[path[1:-1]] - start
        distance = np.abs(direction[0] * offsets[:, 1] - direction[1] * offsets[:, 0]) / length
        worst = int(np.argmax(distance))
        if distance[worst] > tolerance:
            split = worst + 1
            keep.add(path[split])
            stack.append(path[:split + 1])
            stack.append(path[split:])
    return sorted(keep, key=lambda index: (index - first) % count)


def _ring_is_clean(ring, z_lo, z_hi):
    """No two neighbouring corners fall together at either end of the layer."""
    for z in (z_lo, z_hi):
        points = ring.at(z)
        if np.hypot(*(points - np.roll(points, -1, axis=0)).T).min() < MIN_CORNER_DISTANCE:
            return False
    return True


def _wall_movement(ring, z_lo, z_hi):
    """Largest distance the walls of a contour move between two heights."""
    lower = Polygon(ring.at(z_lo)).buffer(0).boundary
    upper = Polygon(ring.at(z_hi)).buffer(0).boundary
    return float(lower.hausdorff_distance(upper))


def _interval_rings(vertices, faces, z_lo, z_hi, name):
    """Closed contours of the template between two neighbouring levels.

    Between two levels no vertex lies inside, so every wall is a planar strip
    from the lower to the upper level.  The contour is read halfway up and
    chained through the mesh edges it crosses.  Returns ``(rings, dangling)``;
    ``dangling`` lists contour points that belong to no closed contour (a mesh
    defect), which are left out.
    """
    z_mid = 0.5 * (z_lo + z_hi)
    z = vertices[:, 2]
    positions, lines = [], []

    def node(point, edge):
        for k, q in enumerate(positions):
            if abs(point[0] - q[0]) <= POINT_TOLERANCE and abs(point[1] - q[1]) <= POINT_TOLERANCE:
                return k
        positions.append(point)
        lines.append(np.array([vertices[edge[0]], vertices[edge[1]]]))
        return len(positions) - 1

    adjacency = {}
    for face in faces:
        crossings = []
        for i, j in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            if (z[i] < z_mid < z[j]) or (z[j] < z_mid < z[i]):
                t = (z_mid - z[i]) / (z[j] - z[i])
                crossings.append(node(vertices[i, :2] + t * (vertices[j, :2] - vertices[i, :2]), (i, j)))
        if len(crossings) == 2 and crossings[0] != crossings[1]:
            a, b = crossings
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)

    dangling = []
    changed = True
    while changed:
        changed = False
        for n in [n for n, nb in adjacency.items() if len(nb) < 2]:
            if n not in adjacency:
                continue
            dangling.append(positions[n])
            for m in adjacency[n]:
                adjacency[m].discard(n)
            del adjacency[n]
            changed = True

    for n, neighbours in adjacency.items():
        if len(neighbours) != 2:
            x, y = positions[n]
            raise TemplateError(
                f"{name}: the contour branches at x={x:.6f}, y={y:.6f} "
                f"(z={z_mid:.4f}); the template mesh is ambiguous there")

    orders, seen = [], set()
    for start in adjacency:
        if start in seen:
            continue
        order, previous, current = [], None, start
        while True:
            order.append(current)
            seen.add(current)
            first, second = sorted(adjacency[current])
            following = first if first != previous else second
            previous, current = current, following
            if current == start:
                break
        orders.append(order)

    polygons_found = [Polygon([positions[n] for n in order]) for order in orders]
    for i, outer in enumerate(polygons_found):
        for j, inner in enumerate(polygons_found):
            if i != j and outer.contains(inner):
                raise TemplateError(
                    f"{name}: nested contours at z={z_mid:.4f} are not supported "
                    "(a contour inside another one)")
    rings, relaxed, straightened = [], [], []
    for order in orders:
        points = np.array([positions[n] for n in order])
        for factor in (1,) + FLAT_WALL_RELAXATIONS:
            tolerance = FLAT_WALL_TOLERANCE * factor
            corners = _corner_indices(points, tolerance)
            ring = Ring(np.array([lines[order[i]] for i in corners]))
            if len(corners) >= 3 and _ring_is_clean(ring, z_lo, z_hi):
                break
        else:
            moved = _wall_movement(Ring(np.array([lines[n] for n in order])), z_lo, z_hi)
            if moved > STRAIGHT_LAYER_TOLERANCE:
                raise TemplateError(
                    f"{name}: corners of a slanted contour between z={z_lo:.4f} and z={z_hi:.4f} "
                    "fall together inside the layer and the layer cannot be lofted; check the template")
            tolerance = FLAT_WALL_TOLERANCE * FLAT_WALL_RELAXATIONS[-1]
            corners = _corner_indices(points, tolerance)
            ring = Ring(np.array([[[*positions[order[i]], z_lo], [*positions[order[i]], z_hi]]
                                  for i in corners]))
            straightened.append(moved)
            factor = 1
        if factor > 1:
            relaxed.append(tolerance)
        rings.append(ring)
    return rings, dangling, relaxed, straightened


def _bounding_box_warnings(name, kind, bounds):
    spec_x, spec_y = TEMPLATE_BOUNDING_BOXES[kind]
    extents = bounds[1] - bounds[0]
    problems = []
    for axis, label, spec in ((0, "x", spec_x), (1, "y", spec_y)):
        deviation = abs(extents[axis] - spec)
        if deviation > BOUNDING_BOX_TOLERANCE:
            problems.append(f"{name}: bounding box {label} is {extents[axis]:.4f} mm, the fixed "
                            f"size is {spec} mm (off by {deviation:.4f} mm)")
    for value, spec, label in ((bounds[0][2], PLATE_Z_MIN, "bottom"), (bounds[1][2], PLATE_Z_MAX, "top")):
        deviation = abs(value - spec)
        if deviation > BOUNDING_BOX_TOLERANCE:
            problems.append(f"{name}: bounding box {label} is at z={value:.4f} mm, the fixed value "
                            f"is {spec} mm (off by {deviation:.4f} mm)")
    return problems


def load_template(path, kind):
    """Read a template STL (kind: socket, stabilizer or spacebar).

    The cutout is described layer by layer between the horizontal planes of the
    mesh.  Nothing is rounded, simplified or left out silently: every contour
    of every layer is kept, and defects of the mesh and deviations from the
    fixed bounding box are returned as ``Template.warnings``.
    """
    path = Path(path)
    vertices, faces, bounds = _exact_mesh(path)
    levels = _levels(vertices[:, 2])
    found, warnings = [], []
    for z_lo, z_hi in zip(levels[:-1], levels[1:]):
        rings, dangling, relaxed, straightened = _interval_rings(
            vertices, faces, z_lo, z_hi, path.name)
        found.append((z_lo, z_hi, rings))
        if straightened:
            warnings.append(
                f"{path.name}: between z={z_lo:.4f} and z={z_hi:.4f} the walls of {len(straightened)} "
                f"contour(s) lean or twist by up to {max(straightened) * 1000:.1f} um (a defect of the "
                "template); the layer was built as a straight prism from its section at half height")
        if relaxed:
            warnings.append(
                f"{path.name}: between z={z_lo:.4f} and z={z_hi:.4f} corners of the mesh fall together "
                f"inside the layer (a defect of the template); {len(relaxed)} contour(s) were simplified "
                f"with a tolerance of {max(relaxed) * 1000:.1f} um instead of {FLAT_WALL_TOLERANCE * 1000:.2f} um")
        if dangling:
            x, y = dangling[0]
            warnings.append(
                f"{path.name}: {len(dangling)} dangling contour point(s) between z={z_lo:.4f} and "
                f"z={z_hi:.4f} were left out (first at x={x:.6f}, y={y:.6f}); the mesh is not closed there")
    while found and not found[0][2]:
        found.pop(0)
    while found and not found[-1][2]:
        found.pop()
    if not found:
        raise TemplateError(f"{path.name}: no cutout contour found")
    if any(not rings for _, _, rings in found):
        raise TemplateError(f"{path.name}: a layer without a contour lies between two layers with one")
    warnings += _bounding_box_warnings(path.name, kind, bounds)
    return Template(path, kind, bounds, [Layer(a, b, r) for a, b, r in found], warnings)


def polygon_wires(poly):
    outer = (cq.Workplane("XY")
             .polyline(list(poly.exterior.coords)[:-1])
             .close().wire().val())
    holes = [(cq.Workplane("XY")
              .polyline(list(r.coords)[:-1])
              .close().wire().val())
             for r in poly.interiors]
    return outer, holes


def face(poly):
    outer, holes = polygon_wires(poly)
    return cq.Face.makeFromWires(outer, holes)


def polygons(geom):
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)
    raise ValueError(f"Unexpected polygon geometry: {geom.geom_type}")


def extruded_footprint(footprint, z, height):
    solids = []
    for poly in polygons(footprint):
        solids.append(cq.Solid.extrudeLinear(
            face(poly), cq.Vector(0, 0, height)
        ).located(cq.Location(cq.Vector(0, 0, z))))
    if not solids:
        raise RuntimeError("Plate footprint is empty.")
    return solids[0] if len(solids) == 1 else cq.Compound.makeCompound(solids)


def _ring_wire(points, z):
    return cq.Wire.makePolygon([cq.Vector(float(x), float(y), z) for x, y in points], close=True)


def template_cutter(template: Template, matrix):
    """CAD cutter of a template around the origin (= switch centre).

    ``matrix`` is the exact linear 2D map (a, b, d, e) applied to the cutout:
    the per-stabilizer rotation followed by the whole-plate transform (for the
    socket only the whole-plate transform).  Each layer is a ruled loft from
    its lower to its upper contour, so vertical walls stay vertical and slanted
    walls stay slanted, for every template alike.  Below the first and above
    the last layer a straight prism of EPS reaches out of the plate, so that
    the cut never leaves coplanar faces; it lies outside the plate and does not
    change it.
    """
    a, b, d, e = matrix
    linear = np.array([[a, d], [b, e]], dtype=float)      # row vectors: p @ linear

    def loft(name, lower, z0, upper, z1):
        area = 0.5 * np.sum(lower[:, 0] * np.roll(lower[:, 1], -1)
                            - np.roll(lower[:, 0], -1) * lower[:, 1])
        if area < 0:                  # a mirror reverses the ring; extrusion needs counter-clockwise
            lower, upper = lower[::-1], upper[::-1]
        wires = [_ring_wire(lower, z0), _ring_wire(upper, z1)]
        if len(wires[0].Edges()) != len(wires[1].Edges()):
            raise TemplateError(
                f"{name}: contour points lie closer together than CadQuery resolves, "
                "so the layer cannot be lofted; check the template")
        return cq.Solid.makeLoft(wires, ruled=True)

    solids = []
    last = len(template.layers) - 1
    for index, layer in enumerate(template.layers):
        name = f"{template.path.name} (z={layer.z0:.4f}..{layer.z1:.4f})"
        for ring in layer.rings:
            lower, upper = ring.at(layer.z0) @ linear, ring.at(layer.z1) @ linear
            solids.append(loft(name, lower, layer.z0, upper, layer.z1))
            if index == 0:
                solids.append(loft(name, lower, layer.z0 - EPS, lower, layer.z0))
            if index == last:
                solids.append(loft(name, upper, layer.z1, upper, layer.z1 + EPS))
    return solids[0].fuse(*solids[1:]) if len(solids) > 1 else solids[0]


def is_spacebar_key(k):
    # In KLE Raw Data the supplied spacebar is represented by an empty label.
    return k.get("label", "") == "" and max(float(k["w"]), float(k["h"])) >= 6.0


def is_stabilized_key(k, min_units):
    label = k.get("label", "")
    # Caps Lock uses a normal switch cutout.
    if label == "Caps Lock" or is_spacebar_key(k):
        return False
    return max(float(k["w"]), float(k["h"])) >= min_units


KIND_NORMAL = "normal"
KIND_STABILIZED = "stabilized"
KIND_SPACEBAR = "spacebar"


def classify_key(k, min_units=1.75):
    """Return KIND_SPACEBAR, KIND_STABILIZED or KIND_NORMAL for a parsed key."""
    if is_spacebar_key(k):
        return KIND_SPACEBAR
    if is_stabilized_key(k, min_units):
        return KIND_STABILIZED
    return KIND_NORMAL


def stabilizer_rotation(k, orientation: "OrientationConfig", min_units=1.75):
    """Rotation (degrees, counter-clockwise, KLE frame) of a key's cutout.

    Returns ``None`` for keys with a normal switch socket.  Stabilized keys
    that are wider than tall count as horizontal, all others as vertical.
    """
    kind = classify_key(k, min_units)
    if kind == KIND_SPACEBAR:
        return orientation.stab_rotation_spacebar
    if kind == KIND_STABILIZED:
        if k["w"] > k["h"]:
            return orientation.stab_rotation_horizontal
        return orientation.stab_rotation_vertical
    return None


@dataclass
class PlateModel:
    """Result of ``build_plate_model``; everything is in the plate frame."""

    keys: list          # parsed KLE keys
    kinds: list         # classify_key() result per key
    rotations: list     # stabilizer rotation per key in degrees, None if normal
    centers: list       # switch centre per key (mm)
    footprint: object   # shapely (Multi)Polygon of the plate outline
    cavities: list      # one CAD solid per key, same order as ``keys``
    plate: object       # CAD solid with all cavities cut out
    templates: dict     # the templates that were used, by kind
    warnings: list      # problems found in the templates
    spacebar_path: Path
    matrix: tuple       # linear part of the whole-plate transform


def build_plate_model(kle_path: Path, socket_path: Path, stabilizer_path: Path,
                      spacebar_centered_path: Path, spacebar_off_centered_path: Path,
                      spacebar_position="centered", margin=DEFAULT_MARGIN,
                      stabilizer_min_unit=1.75,
                      orientation: OrientationConfig | None = None) -> PlateModel:
    """Build the plate solid without exporting it.

    Transformation order (see ``OrientationConfig``): per-stabilizer rotation
    about its switch centre, then the whole-plate transform about the origin,
    then a shift so that the plate's bounding box (including margin) starts at
    (0, 0).  Rotations and the mirror are exact integer matrices applied to
    the 2D data (footprint, switch centres, cutout sections) before anything
    is extruded; no mirrored CAD solid is ever created.
    """
    orientation = orientation or OrientationConfig()
    data = json.loads(kle_path.read_text(encoding="utf-8"))
    keys = parse_kle(data)
    if not keys:
        raise ValueError("KLE JSON contains no keys.")

    spacebar_path = (spacebar_centered_path if spacebar_position == "centered"
                     else spacebar_off_centered_path)
    template_paths = {"socket": socket_path, "stabilizer": stabilizer_path,
                      "spacebar": spacebar_path}
    templates = {}

    gm = global_matrix(orientation)
    a, b, d, e = gm
    shapes = []
    for k in keys:
        s = local_key_shape(k)
        s = translate(s, xoff=k["x"], yoff=k["y"])
        s = scale(s, xfact=UNIT, yfact=UNIT, origin=(0, 0))
        shapes.append(affine_transform(s, [a, b, d, e, 0, 0]))

    footprint = unary_union(shapes).buffer(margin, join_style=2)
    minx, miny = footprint.bounds[0], footprint.bounds[1]
    footprint = translate(footprint, xoff=-minx, yoff=-miny)

    centers = []
    for k in keys:
        cx, cy = apply_matrix(gm, *switch_center(k))
        centers.append((cx - minx, cy - miny))

    plate = extruded_footprint(footprint, PLATE_Z_MIN, PLATE_Z_MAX - PLATE_Z_MIN)

    # Socket, stabilizer and spacebar cutouts are built by the same code.  The
    # templates are used exactly as supplied (nothing is scaled); the spacebar
    # templates keep their internal switch position (centered/off-centered).
    kinds, rotations, cavities, cutters = [], [], [], {}
    for k, (cx, cy) in zip(keys, centers):
        kind = classify_key(k, stabilizer_min_unit)
        rotation = stabilizer_rotation(k, orientation, stabilizer_min_unit)
        kinds.append(kind)
        rotations.append(rotation)
        template_kind = {KIND_NORMAL: "socket", KIND_STABILIZED: "stabilizer",
                         KIND_SPACEBAR: "spacebar"}[kind]
        if template_kind not in templates:
            templates[template_kind] = load_template(template_paths[template_kind], template_kind)
        # Step 1 (rotation about the switch centre), then step 2 (whole plate).
        m = gm if rotation is None else matrix_multiply(gm, rotation_matrix(rotation))
        if (template_kind, m) not in cutters:
            cutters[(template_kind, m)] = template_cutter(templates[template_kind], m)
        cavities.append(cutters[(template_kind, m)].moved(cq.Location(cq.Vector(cx, cy, 0))))

    if not cavities:
        raise RuntimeError("No cavities generated.")
    cavity = cavities[0]
    for c in cavities[1:]:
        cavity = cavity.fuse(c)

    result = plate.cut(cavity)
    if not result.isValid():
        raise RuntimeError("Generated CAD solid is invalid.")
    result = result.clean()

    return PlateModel(keys=keys, kinds=kinds, rotations=rotations, centers=centers,
                      footprint=footprint, cavities=cavities, plate=result,
                      templates=templates,
                      warnings=[w for t in templates.values() for w in t.warnings],
                      spacebar_path=spacebar_path, matrix=gm)


def check_exported_stl(stl_path: Path, expected_bounds=None,
                       bounds_tolerance: float = 0.1):
    """Check an exported STL without modifying or re-exporting the file.

    Returns ``(mesh, problems)``.  ``problems`` is a list of readable
    messages about the mesh quality (open or shared edges, face direction,
    dimensions); it is empty for a clean STL.  A missing, empty or unreadable
    file cannot be used at all and raises ``RuntimeError``.

    ``expected_bounds`` may be ``(minimum_xyz, maximum_xyz)`` from the source
    CAD model. Mesh processing is performed only in memory so STL triangle
    vertices can be merged for topology checks; the file itself is untouched.
    """
    stl_path = Path(stl_path)
    if not stl_path.is_file():
        raise RuntimeError(f"STL export was not created: {stl_path}")
    if stl_path.stat().st_size == 0:
        raise RuntimeError(f"STL export is empty: {stl_path}")

    try:
        mesh = trimesh.load_mesh(stl_path, force="mesh", process=True)
    except Exception as exc:
        raise RuntimeError(f"Could not read exported STL '{stl_path}': {exc}") from exc

    if not isinstance(mesh, trimesh.Trimesh):
        raise RuntimeError("STL export did not produce a triangle mesh.")
    if mesh.is_empty or len(mesh.vertices) == 0 or len(mesh.faces) == 0:
        raise RuntimeError("STL export contains no triangle geometry.")
    if not np.isfinite(mesh.vertices).all():
        raise RuntimeError("STL export contains NaN or infinite vertex coordinates.")

    bounds = np.asarray(mesh.bounds, dtype=float)
    extents = np.asarray(mesh.extents, dtype=float)
    if bounds.shape != (2, 3) or not np.isfinite(bounds).all():
        raise RuntimeError("STL export has invalid or non-finite bounds.")
    if not np.isfinite(extents).all() or np.any(extents <= 0):
        raise RuntimeError(f"STL export has invalid dimensions: {extents.tolist()}")

    problems = []
    if not mesh.is_watertight:
        _, counts = np.unique(mesh.edges_sorted, axis=0, return_counts=True)
        problems.append(
            "not watertight: "
            f"{int((counts == 1).sum())} open edges (one face only), "
            f"{int((counts > 2).sum())} edges shared by more than two faces"
        )
    if not mesh.is_winding_consistent:
        problems.append("inconsistent face winding")
    if (mesh.is_watertight and mesh.is_winding_consistent
            and (not mesh.is_volume or not np.isfinite(mesh.volume) or mesh.volume <= 0)):
        problems.append("does not describe a valid outward-facing closed volume")

    if expected_bounds is not None:
        try:
            expected_min = np.asarray(expected_bounds[0], dtype=float)
            expected_max = np.asarray(expected_bounds[1], dtype=float)
        except (TypeError, ValueError, IndexError) as exc:
            raise ValueError(
                "expected_bounds must be a pair: (minimum_xyz, maximum_xyz)."
            ) from exc
        if (expected_min.shape != (3,) or expected_max.shape != (3,)
                or not np.isfinite(expected_min).all()
                or not np.isfinite(expected_max).all()
                or np.any(expected_min > expected_max)):
            raise ValueError(
                "expected_bounds must contain finite 3D minimum and maximum coordinates."
            )
        if not np.isfinite(bounds_tolerance) or bounds_tolerance < 0:
            raise ValueError("bounds_tolerance must be a finite non-negative number.")

        min_error = float(np.max(np.abs(bounds[0] - expected_min)))
        max_error = float(np.max(np.abs(bounds[1] - expected_max)))
        if max(min_error, max_error) > bounds_tolerance:
            problems.append(
                "bounds differ from the CAD model "
                f"(minimum error {min_error:.4f} mm, maximum error {max_error:.4f} mm, "
                f"allowed {bounds_tolerance:.4f} mm)"
            )

    return mesh, problems


def report_template_warnings(warnings):
    """Print problems found in the templates; the plate is built from them as they are."""
    if not warnings:
        return
    print("\nWARNING: the template STLs are not exact. The plate is built from them exactly "
          "as they are:", file=sys.stderr)
    for warning in warnings:
        print(f"  - {warning}", file=sys.stderr)


def report_stl_check(mesh, problems, stl_path: Path):
    """Print the result of ``check_exported_stl``; problems become a warning."""
    if not problems:
        print(f"STL check:       passed ({len(mesh.faces)} triangles, "
              f"volume {mesh.volume:.3f} mm³, "
              f"dimensions {[round(float(e), 4) for e in mesh.extents]} mm)")
        return
    print("\nWARNING: the exported STL has problems and may not slice or print "
          "correctly:", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    print(f"The STL was written anyway: {stl_path}", file=sys.stderr)
    print("So far this was caused by template STLs that are not exact "
          "(see README, 'Common Errors').", file=sys.stderr)


def generate(kle_path: Path, socket_path: Path, stabilizer_path: Path,
             spacebar_centered_path: Path, spacebar_off_centered_path: Path,
             spacebar_position="centered",
             output: Path = Path(DEFAULT_OUTPUT), margin=DEFAULT_MARGIN,
             stabilizer_min_unit=1.75,
             orientation: OrientationConfig | None = None):
    orientation = orientation or OrientationConfig()
    model = build_plate_model(
        kle_path, socket_path, stabilizer_path, spacebar_centered_path,
        spacebar_off_centered_path, spacebar_position=spacebar_position,
        margin=margin, stabilizer_min_unit=stabilizer_min_unit,
        orientation=orientation)
    keys = model.keys

    output.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(model.plate, str(output), exportType="STL",
                        tolerance=0.001, angularTolerance=0.1)

    # The STL is checked in memory only (see below).  It is never repaired,
    # filtered by component or re-exported: separated layout regions (F-row,
    # navigation cluster, numpad) must not be silently deleted.
    bb = model.plate.BoundingBox()
    expected_bounds = (
        (bb.xmin, bb.ymin, bb.zmin),
        (bb.xmax, bb.ymax, bb.zmax),
    )

    print(f"\nFat Plate Generator v{VERSION}")
    print("----------------------")
    print(f"KLE:             {kle_path}")
    print(f"Socket:          {socket_path}")
    print(f"Stabilizer:      {stabilizer_path}")
    print(f"Spacebar:        {model.spacebar_path} ({spacebar_position})")
    print(f"Output:          {output}")
    print(f"Keys:            {len(keys)}")
    print(f"Stabilizer keys: {model.kinds.count(KIND_STABILIZED)}")
    print(f"Spacebar keys:   {model.kinds.count(KIND_SPACEBAR)}")
    print(f"Plate thickness: {PLATE_Z_MAX - PLATE_Z_MIN:.4f} mm")
    for kind, template in model.templates.items():
        print(f"Template {kind + ':':11s} {template.path.name}, {len(template.layers)} layers, "
              f"{template.vertex_count} contour vertices")
    print("Caps Lock:       normal switch cutout")
    print(f"Stab rotation:   horizontal {orientation.stab_rotation_horizontal} deg, "
          f"vertical {orientation.stab_rotation_vertical} deg, "
          f"spacebar {orientation.stab_rotation_spacebar} deg")
    if orientation.global_transform:
        mirror = " + mirror X" if orientation.global_mirror_x else ""
        print(f"Plate transform: rotate {orientation.global_rotation} deg{mirror}, "
              f"matrix {model.matrix}")
    else:
        print("Plate transform: none (--no-global-transform)")
    report_template_warnings(model.warnings)
    mesh, problems = check_exported_stl(output, expected_bounds=expected_bounds)
    report_stl_check(mesh, problems, output)
    print("\nDone." if not (problems or model.warnings) else "\nDone, with warnings.")


def main():
    parser = argparse.ArgumentParser(description="Generate a clean Fat Plate STL from KLE JSON.")
    parser.add_argument("--version", action="version", version=f"Fat Plate Generator {VERSION}")
    base = Path(__file__).resolve().parent
    parser.add_argument("--json", type=Path, default=base / DEFAULT_JSON)
    parser.add_argument("--socket", type=Path, default=base / DEFAULT_SOCKET)
    parser.add_argument("--stabilizer", type=Path, default=base / DEFAULT_STABILIZER)
    parser.add_argument("--spacebar-centered", type=Path, default=base / DEFAULT_SPACEBAR_CENTERED)
    parser.add_argument("--spacebar-off-centered", type=Path, default=base / DEFAULT_SPACEBAR_OFF_CENTERED)
    parser.add_argument("--spacebar-position", choices=["centered", "off-centered"], default="centered",
                        help="Spacebar switch position: centered or off-centered.")
    parser.add_argument("--output", type=Path, default=base / DEFAULT_OUTPUT)
    parser.add_argument("--margin", type=float, default=DEFAULT_MARGIN)
    parser.add_argument("--stabilizer-min-unit", type=float, default=1.75)
    defaults = OrientationConfig()
    parser.add_argument("--stab-rotation-horizontal", type=int, choices=ROTATION_CHOICES,
                        default=defaults.stab_rotation_horizontal,
                        help="rotation of horizontal stabilizer cutouts in degrees, counter-clockwise "
                             "(default: %(default)s)")
    parser.add_argument("--stab-rotation-vertical", type=int, choices=ROTATION_CHOICES,
                        default=defaults.stab_rotation_vertical,
                        help="rotation of vertical stabilizer cutouts in degrees (default: %(default)s)")
    parser.add_argument("--stab-rotation-spacebar", type=int, choices=ROTATION_CHOICES,
                        default=defaults.stab_rotation_spacebar,
                        help="rotation of the spacebar cutout in degrees (default: %(default)s)")
    parser.add_argument("--no-global-transform", action="store_true",
                        help="skip the whole-plate transform (KLE y flip); "
                             "mainly for comparison with older output")
    args = parser.parse_args()
    orientation = OrientationConfig(
        stab_rotation_horizontal=args.stab_rotation_horizontal,
        stab_rotation_vertical=args.stab_rotation_vertical,
        stab_rotation_spacebar=args.stab_rotation_spacebar,
        global_transform=not args.no_global_transform)

    try:
        generate(args.json, args.socket, args.stabilizer,
                  args.spacebar_centered, args.spacebar_off_centered,
                  spacebar_position=args.spacebar_position,
                  output=args.output, margin=args.margin,
                  stabilizer_min_unit=args.stabilizer_min_unit,
                  orientation=orientation)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()

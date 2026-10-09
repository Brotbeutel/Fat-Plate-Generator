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
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import polygonize, unary_union

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
SIZE_TOL = 0.08

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


def clustered_z_levels(mesh, decimals=5):
    vals = np.unique(np.round(mesh.vertices[:, 2], decimals))
    if not len(vals):
        raise ValueError("STL has no vertices.")
    groups = [[float(vals[0])]]
    for z in vals[1:]:
        if float(z) - groups[-1][-1] < 0.002:
            groups[-1].append(float(z))
        else:
            groups.append([float(z)])
    return [sum(g) / len(g) for g in groups]


def section_size(mesh, z):
    sec = mesh.section(plane_origin=[0, 0, float(z)],
                       plane_normal=[0, 0, 1])
    if sec is None:
        return None
    if len(sec.entities) == 0:
        return None
    # For the socket STL there is one clean section loop.
    entity = max(sec.entities, key=lambda e: len(e.points))
    pts = sec.vertices[entity.points]
    if len(pts) < 4:
        return None
    ext = pts[:, :2].max(axis=0) - pts[:, :2].min(axis=0)
    return float((ext[0] + ext[1]) / 2.0)


def socket_profile(path: Path):
    mesh = trimesh.load(path, force="mesh")
    if mesh.is_empty:
        raise ValueError(f"Socket STL is empty: {path}")

    zmin = float(mesh.bounds[0, 2])
    zmax = float(mesh.bounds[1, 2])
    thickness = zmax - zmin
    if thickness <= 0:
        raise ValueError("Socket STL has zero Z thickness.")

    levels = clustered_z_levels(mesh)
    intervals = []
    for a, b in zip(levels[:-1], levels[1:]):
        if b - a < 0.002:
            continue
        size = section_size(mesh, (a + b) * 0.5)
        if size is not None:
            intervals.append({"z0": a, "z1": b, "size": size})
    if not intervals:
        raise ValueError("Could not extract a horizontal profile from socket STL.")

    sizes = [i["size"] for i in intervals]
    lower_size = sizes[0]
    top_size = sizes[-1]
    min_size = min(sizes)

    taper_start = next((i["z0"] for i in intervals
                        if i["size"] < lower_size - SIZE_TOL), intervals[0]["z0"])
    taper_end = next((i["z0"] for i in intervals
                      if i["z0"] >= taper_start and
                      abs(i["size"] - min_size) <= SIZE_TOL), taper_start)
    collar_start = next((i["z0"] for i in intervals
                         if i["z0"] >= taper_end and
                         i["size"] >= top_size - SIZE_TOL), intervals[-1]["z0"])

    return {
        "zmin": zmin, "zmax": zmax, "thickness": thickness,
        "lower_size": lower_size, "min_size": min_size, "top_size": top_size,
        "taper_start": max(zmin, min(zmax, taper_start)),
        "taper_end": max(zmin, min(zmax, taper_end)),
        "collar_start": max(zmin, min(zmax, collar_start)),
        "intervals": intervals,
    }



def remove_collinear(poly, tol=1e-5):
    """Remove triangulation-only collinear vertices without changing shape."""
    pts = np.asarray(poly.exterior.coords[:-1], dtype=float)
    changed = True
    while changed and len(pts) > 3:
        changed = False
        keep = []
        n = len(pts)
        for i in range(n):
            a = pts[i - 1]
            b = pts[i]
            c = pts[(i + 1) % n]
            u = b - a
            v = c - b
            cross = abs(float(u[0] * v[1] - u[1] * v[0]))
            dot = float(u[0] * v[0] + u[1] * v[1])
            if cross <= tol and dot >= -tol:
                changed = True
                continue
            keep.append(b)
        pts = np.asarray(keep, dtype=float)
    return Polygon(pts)

def triangle_section_polygon(mesh, z):
    """Intersect every STL triangle with a horizontal plane and polygonize it.

    This avoids topology-dependent behaviour in trimesh.section() and gives
    deterministic, clean polygons directly from the supplied STL faces.
    """
    vertices = np.asarray(mesh.vertices, dtype=float)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    lines = []

    for face_idx in faces:
        tri = vertices[face_idx]
        points = []
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            za, zb = float(a[2]), float(b[2])
            if (za < z < zb) or (zb < z < za):
                t = (z - za) / (zb - za)
                q = a + t * (b - a)
                points.append(np.round(q[:2], 6))
        if len(points) == 2 and np.linalg.norm(points[0] - points[1]) > 1e-8:
            lines.append(LineString(points))

    if not lines:
        raise ValueError(f"No stabilizer section at z={z:.6f}.")

    polygons_found = list(polygonize(unary_union(lines)))
    if not polygons_found:
        raise ValueError(f"Could not polygonize stabilizer section at z={z:.6f}.")

    poly = max(polygons_found, key=lambda p: p.area)
    if not poly.is_valid or poly.area <= 1e-6:
        raise ValueError(f"Invalid stabilizer section at z={z:.6f}.")
    poly = remove_collinear(poly)
    if not poly.is_valid:
        raise ValueError(f"Cleaned stabilizer section at z={z:.6f} is invalid.")
    return poly


def stabilizer_template(path: Path):
    mesh = trimesh.load(path, force="mesh")
    if mesh.is_empty:
        raise ValueError(f"Stabilizer STL is empty: {path}")

    zmin = float(mesh.bounds[0, 2])
    zmax = float(mesh.bounds[1, 2])
    if zmax <= zmin:
        raise ValueError("Stabilizer STL has zero Z thickness.")

    levels = clustered_z_levels(mesh)
    intervals = []
    for a, b in zip(levels[:-1], levels[1:]):
        if b - a < 0.002:
            continue
        poly = triangle_section_polygon(mesh, (a + b) * 0.5)
        intervals.append({"z0": a, "z1": b, "poly": poly})

    if not intervals:
        raise ValueError("Could not reconstruct stabilizer Z profile.")

    base = intervals[0]["poly"]
    ext = np.asarray(base.bounds[2:4]) - np.asarray(base.bounds[0:2])
    all_ext = [np.asarray(i["poly"].bounds[2:4]) -
               np.asarray(i["poly"].bounds[0:2]) for i in intervals]
    long_axis = 1 if ext[1] >= ext[0] else 0
    template_long = max(float(e[long_axis]) for e in all_ext)

    return {
        "zmin": zmin,
        "zmax": zmax,
        "thickness": zmax - zmin,
        "intervals": intervals,
        "long_axis": long_axis,
        "template_long": template_long,
        "vertices": sum(len(i["poly"].exterior.coords) - 1 for i in intervals),
    }


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


def square_wire(size, z, cx=0.0, cy=0.0):
    return (cq.Workplane("XY")
            .workplane(offset=z)
            .center(cx, cy)
            .rect(size, size)
            .wire().val())


def cavity_for_center(profile, cx, cy):
    z0 = profile["zmin"] - EPS
    z1 = profile["zmax"] + EPS
    lower = profile["lower_size"]
    narrow = profile["min_size"]
    top = profile["top_size"]
    ts = profile["taper_start"]
    te = profile["taper_end"]
    cs = profile["collar_start"]
    solids = []

    if ts > z0 + 1e-4:
        solids.append(cq.Solid.extrudeLinear(
            square_wire(lower, z0, cx, cy), [], cq.Vector(0, 0, ts - z0)))
    if te > ts + 1e-4 and abs(lower - narrow) > SIZE_TOL:
        solids.append(cq.Solid.makeLoft([
            square_wire(lower, ts, cx, cy),
            square_wire(narrow, te, cx, cy)], ruled=True))
    if cs > te + 1e-4:
        solids.append(cq.Solid.extrudeLinear(
            square_wire(narrow, te, cx, cy), [], cq.Vector(0, 0, cs - te)))
    if z1 > cs + 1e-4:
        solids.append(cq.Solid.extrudeLinear(
            square_wire(top, cs, cx, cy), [], cq.Vector(0, 0, z1 - cs)))

    result = solids[0]
    for s in solids[1:]:
        result = result.fuse(s)
    return result


def stabilizer_cavity(template, cx, cy, matrix):
    """Build the combined stabilizer + switch cavity.

    ``matrix`` is the exact linear 2D map (a, b, d, e) applied to the template
    around its origin (= switch centre): the per-stabilizer rotation followed
    by the whole-plate transform.  ``(cx, cy)`` is the switch centre in the
    plate frame, i.e. already transformed.
    """
    intervals = template["intervals"]
    a, b, d, e = matrix
    transformed = []
    for i in intervals:
        poly = affine_transform(i["poly"], [a, b, d, e, 0, 0])
        # A mirror flips the ring direction; extrusion needs counter-clockwise.
        transformed.append(orient(poly, 1.0))

    # Preserve each measured STL section as a clean prismatic CAD segment.
    # This avoids fragile high-order boolean lofts while retaining the actual
    # stabilizer profile and its upper collar.
    solids = []
    for i, interval in enumerate(intervals):
        z0 = interval["z0"]
        z1 = interval["z1"]
        if i == 0:
            z0 -= EPS
        if i == len(intervals) - 1:
            z1 += EPS
        solids.append(cq.Solid.extrudeLinear(
            face(transformed[i]), cq.Vector(0, 0, z1 - z0)
        ).located(cq.Location(cq.Vector(0, 0, z0))))

    result = solids[0]
    for solid in solids[1:]:
        result = result.fuse(solid)
    return result.located(cq.Location(cq.Vector(cx, cy, 0)))


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
    profile: dict
    stab: dict
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

    profile = socket_profile(socket_path)
    stab = stabilizer_template(stabilizer_path)
    spacebar_path = (spacebar_centered_path if spacebar_position == "centered"
                     else spacebar_off_centered_path)
    spacebar_stab = stabilizer_template(spacebar_path)

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

    plate = extruded_footprint(footprint, profile["zmin"], profile["thickness"])

    kinds, rotations, cavities = [], [], []
    for k, (cx, cy) in zip(keys, centers):
        kind = classify_key(k, stabilizer_min_unit)
        rotation = stabilizer_rotation(k, orientation, stabilizer_min_unit)
        kinds.append(kind)
        rotations.append(rotation)
        if kind == KIND_NORMAL:
            cavities.append(cavity_for_center(profile, cx, cy))
            continue
        # Step 1 (rotation about the switch centre), then step 2 (whole plate).
        m = matrix_multiply(gm, rotation_matrix(rotation))
        # The templates are used exactly as supplied (no scaling); the spacebar
        # templates keep their internal switch position (centered/off-centered).
        template = spacebar_stab if kind == KIND_SPACEBAR else stab
        cavities.append(stabilizer_cavity(template, cx, cy, m))

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
                      profile=profile, stab=stab, spacebar_path=spacebar_path,
                      matrix=gm)


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
    keys, profile, stab = model.keys, model.profile, model.stab

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
    print(f"Plate thickness: {profile['thickness']:.4f} mm")
    print(f"Normal narrow:   {profile['min_size']:.4f} mm")
    print(f"Stab section:    {stab['vertices']} vertices, {stab['template_long']:.4f} mm long")
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
    mesh, problems = check_exported_stl(output, expected_bounds=expected_bounds)
    report_stl_check(mesh, problems, output)
    print("\nDone." if not problems else "\nDone, with warnings.")


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

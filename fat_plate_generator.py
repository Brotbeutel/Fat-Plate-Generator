#!/usr/bin/env python3
"""Fat Plate Generator v10

KLE raw JSON -> clean CAD/STL plate, without voxelization.

The normal switch socket is reconstructed from the supplied socket STL.
Stabilized keys use the supplied stabilizer STL as ONE combined cavity
(stabilizer cutout + switch socket).  The stabilizer cross-section is taken
from the actual STL section and preserved as straight CAD geometry; no
resampling/loft smoothing is used.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from shapely.affinity import rotate, scale, translate
from shapely.geometry import LineString, Polygon, box
from shapely.ops import polygonize, unary_union

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
        "central_half": 8.0,
        "template_long": template_long,
        "template_half": template_long / 2.0,
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


def transform_stabilizer_polygon(poly, template, key_length_units, mode="auto"):
    if mode == "none":
        return poly

    target_long = template["template_long"] * (key_length_units / 2.0)
    if abs(target_long - template["template_long"]) < 1e-7:
        return poly

    s = ((target_long / 2.0) - template["central_half"]) / \
        (template["template_half"] - template["central_half"])
    if s <= 0:
        raise ValueError("Requested stabilizer size is too small for the template.")

    def tx(x, y):
        v = y if template["long_axis"] == 1 else x
        sign = 1.0 if v >= 0 else -1.0
        av = abs(v)
        if av <= template["central_half"]:
            nv = v
        else:
            nv = sign * (template["central_half"] +
                         (av - template["central_half"]) * s)
        return (x, nv) if template["long_axis"] == 1 else (nv, y)

    coords = [tx(x, y) for x, y in list(poly.exterior.coords)]
    holes = []
    for ring in poly.interiors:
        holes.append([tx(x, y) for x, y in list(ring.coords)])
    return Polygon(coords, holes)


def wire_at(poly, z):
    return (cq.Workplane("XY")
            .workplane(offset=z)
            .polyline(list(poly.exterior.coords)[:-1])
            .close().wire().val())


def stabilizer_cavity(template, cx, cy, key_length_units, rotation_deg, scale_mode):
    intervals = template["intervals"]
    transformed = [transform_stabilizer_polygon(i["poly"], template,
                                                  key_length_units,
                                                  scale_mode)
                   for i in intervals]

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

    if abs(rotation_deg) > 1e-12:
        result = result.rotate((0, 0, 0), (0, 0, 1), rotation_deg)
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


def generate(kle_path: Path, socket_path: Path, stabilizer_path: Path,
             spacebar_centered_path: Path, spacebar_off_centered_path: Path,
             spacebar_position="centered",
             output: Path = Path(DEFAULT_OUTPUT), margin=DEFAULT_MARGIN,
             stabilizer_min_unit=1.75, stabilizer_scale_mode="auto"):
    data = json.loads(kle_path.read_text(encoding="utf-8"))
    keys = parse_kle(data)
    if not keys:
        raise ValueError("KLE JSON contains no keys.")

    profile = socket_profile(socket_path)
    stab = stabilizer_template(stabilizer_path)
    spacebar_path = (spacebar_centered_path if spacebar_position == "centered"
                     else spacebar_off_centered_path)
    spacebar_stab = stabilizer_template(spacebar_path)

    shapes = []
    for k in keys:
        s = local_key_shape(k)
        s = translate(s, xoff=k["x"], yoff=k["y"])
        s = scale(s, xfact=UNIT, yfact=UNIT, origin=(0, 0))
        shapes.append(s)

    minx = min(s.bounds[0] for s in shapes)
    miny = min(s.bounds[1] for s in shapes)
    shapes = [translate(s, xoff=-minx, yoff=-miny) for s in shapes]
    footprint = unary_union(shapes).buffer(margin, join_style=2)

    centers = []
    for k in keys:
        cx, cy = switch_center(k)
        centers.append((cx - minx, cy - miny))

    plate = extruded_footprint(footprint, profile["zmin"], profile["thickness"])

    normal_cavities = []
    stabilizer_cavities = []
    spacebar_cavities = []
    stab_keys = []
    spacebar_keys = []
    for k, (cx, cy) in zip(keys, centers):
        if is_spacebar_key(k):
            spacebar_keys.append(k)
            # The supplied spacebar templates are already horizontal. Their
            # internal switch position (centered/off-centered) is preserved
            # exactly; no length scaling is applied.
            spacebar_cavities.append(
                stabilizer_cavity(spacebar_stab, cx, cy, 6.25,
                                  0.0, "none"))
        elif is_stabilized_key(k, stabilizer_min_unit):
            stab_keys.append(k)
            length_units = max(float(k["w"]), float(k["h"]))
            # Template is vertical (long axis Y). Rotate for horizontal keys.
            rotation = 90.0 if k["w"] > k["h"] else 0.0
            stabilizer_cavities.append(
                stabilizer_cavity(stab, cx, cy, length_units,
                                  rotation, stabilizer_scale_mode))
        else:
            normal_cavities.append(cavity_for_center(profile, cx, cy))

    cavities = normal_cavities + stabilizer_cavities + spacebar_cavities
    if not cavities:
        raise RuntimeError("No cavities generated.")
    cavity = cavities[0]
    for c in cavities[1:]:
        cavity = cavity.fuse(c)

    result = plate.cut(cavity)
    if not result.isValid():
        raise RuntimeError("Generated CAD solid is invalid.")
    result = result.clean()

    output.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(result, str(output), exportType="STL",
                        tolerance=0.001, angularTolerance=0.1)

    # IMPORTANT: never keep only the largest connected component here. KLE
    # layouts such as 100% / Full Size can contain separated regions (F-row,
    # navigation cluster, numpad). Filtering by largest component silently
    # deletes those regions. CadQuery has already validated the BRep above, so
    # the STL is deliberately left exactly as OCC exported it.
    #
    # We only inspect the STL for a basic sanity check; no trimesh.split(),
    # repair or component filtering is performed. This also removes the
    # networkx dependency that caused the previous runtime error.
    exported = trimesh.load_mesh(output, force="mesh")
    if exported.is_empty or len(exported.faces) == 0:
        raise RuntimeError("STL export produced an empty mesh.")
    exported.export(output)

    print("\nFat Plate Generator v10")
    print("----------------------")
    print(f"KLE:             {kle_path}")
    print(f"Socket:          {socket_path}")
    print(f"Stabilizer:      {stabilizer_path}")
    print(f"Spacebar:        {spacebar_path} ({spacebar_position})")
    print(f"Output:          {output}")
    print(f"Keys:            {len(keys)}")
    print(f"Stabilizer keys: {len(stab_keys)}")
    print(f"Spacebar keys:   {len(spacebar_keys)}")
    print(f"Plate thickness: {profile['thickness']:.4f} mm")
    print(f"Normal narrow:   {profile['min_size']:.4f} mm")
    print(f"Stab section:    {stab['vertices']} vertices, {stab['template_long']:.4f} mm long")
    print(f"Stab scale:      {stabilizer_scale_mode} (default: no stretching)")
    print("Stab switch:     central 16 mm opening kept unscaled")
    print("Caps Lock:       normal switch cutout")
    print("Voxelization:    NONE")
    print("\nDone.")


def main():
    parser = argparse.ArgumentParser(description="Generate a clean Fat Plate STL from KLE JSON.")
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
    parser.add_argument("--stabilizer-scale", choices=["auto", "none"], default="none")
    args = parser.parse_args()

    try:
        generate(args.json, args.socket, args.stabilizer,
                  args.spacebar_centered, args.spacebar_off_centered,
                  spacebar_position=args.spacebar_position,
                  output=args.output, margin=args.margin,
                  stabilizer_min_unit=args.stabilizer_min_unit,
                  stabilizer_scale_mode=args.stabilizer_scale)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()

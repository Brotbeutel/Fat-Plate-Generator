#!/usr/bin/env python3
"""Top-view preview of a generated Fat Plate STL (development tool).

Renders a horizontal section through the middle of the plate (half of the
plate height) as a PNG.  Material is drawn gray, cutouts stay white, so the
asymmetric stabilizer cutouts and their orientation are directly visible.
The picture contains

* an axis cross at the CAD origin (+X red, +Y green),
* a scale bar,
* the key labels taken from the KLE raw data JSON, and
* a small compass showing where KLE "right" and KLE "down" (= the typist
  side of the keyboard) ended up in the plate frame.

The preview only needs the STL and the KLE JSON.  It does not call the
generator, so it also works on STLs produced by older generator versions
(use ``--no-global-transform`` for those).

Needs matplotlib (``pip install -r requirements-dev.txt``).  Example::

    python tools/preview.py plate.stl --layout layout.json --output preview.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import shapely
import trimesh
from shapely.affinity import affine_transform, translate
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.ops import polygonize, unary_union

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import fat_plate_generator as fpg  # noqa: E402  (needs the sys.path entry above)

# Linear part (a, b, d, e) of the generator's default whole-plate transform:
#   x' = a*x + b*y,  y' = d*x + e*y
# Taken from the generator so that preview and plate cannot drift apart.  If you
# generate with a non-default global_rotation in code, change it here as well.
GLOBAL_MATRIX = fpg.global_matrix(fpg.OrientationConfig())
IDENTITY_MATRIX = fpg.IDENTITY_MATRIX
SNAP_GRID = 1e-3  # mm, noding tolerance for the section


# --------------------------------------------------------------------------
# Section of the STL
# --------------------------------------------------------------------------
def section_segments(mesh: trimesh.Trimesh, z: float) -> np.ndarray:
    """Intersect all triangles with the plane Z=z; returns (n, 2, 2) segments.

    Pure numpy on purpose: trimesh.section() needs networkx for polygon
    handling, which is not a dependency of this project.
    """
    tri = np.asarray(mesh.triangles, dtype=float)
    d = tri[:, :, 2] - z
    if np.any(np.abs(d) < 1e-9):
        # A vertex lies exactly on the plane; nudge the plane slightly.
        z += 1e-4
        d = tri[:, :, 2] - z

    points = np.full((len(tri), 3, 2), np.nan)
    for slot, (i, j) in enumerate(((0, 1), (1, 2), (2, 0))):
        da, db = d[:, i], d[:, j]
        hit = (da * db) < 0
        t = da[hit] / (da[hit] - db[hit])
        a = tri[hit, i, :2]
        b = tri[hit, j, :2]
        points[hit, slot] = a + t[:, None] * (b - a)

    valid = ~np.isnan(points[:, :, 0])
    two = valid.sum(axis=1) == 2
    if not np.any(two):
        return np.zeros((0, 2, 2))
    return points[two][valid[two]].reshape(-1, 2, 2)


def plate_section(mesh: trimesh.Trimesh, z: float | None = None):
    """Return (material geometry, z) of the horizontal section at height z.

    The default height is half of the plate height.  The material geometry is
    a shapely (Multi)Polygon built with the even-odd rule, so cutouts become
    holes and islands inside cutouts are material again.
    """
    if mesh.is_empty:
        raise ValueError("Mesh is empty.")
    zmin, zmax = float(mesh.bounds[0, 2]), float(mesh.bounds[1, 2])
    if z is None:
        z = (zmin + zmax) / 2.0
    segments = section_segments(mesh, z)
    if len(segments) == 0:
        raise ValueError(f"No section at z={z:.4f} (mesh z range {zmin:.4f}..{zmax:.4f}).")

    # STL meshes may contain T-junctions and slightly offset collinear edges,
    # which break exact noding.  Snap-rounding to a 1 micron grid closes them.
    lines = shapely.linestrings(segments)
    lines = lines[shapely.length(lines) > 1e-9]
    cells = list(polygonize(shapely.union_all(lines, grid_size=SNAP_GRID)))
    if not cells:
        raise ValueError(f"Could not polygonize the section at z={z:.4f}.")

    material = Polygon()
    for cell in cells:
        material = material.symmetric_difference(Polygon(cell.exterior))
    return material, z


# --------------------------------------------------------------------------
# KLE keys in plate coordinates
# --------------------------------------------------------------------------
def keys_in_plate_frame(keys, mesh_bounds, margin, matrix):
    """Place KLE keys into the plate frame of an STL.

    The linear transform ``matrix`` is applied first; the translation is then
    chosen so that the key area sits ``margin`` mm inside the STL's XY
    bounding box.  This holds for every generator version, because the plate
    is always the key footprint plus ``margin``.
    """
    a, b, d, e = matrix
    placed = []
    for k in keys:
        shape = translate(fpg.local_key_shape(k), xoff=k["x"], yoff=k["y"])
        shape = affine_transform(shape, [fpg.UNIT, 0, 0, fpg.UNIT, 0, 0])
        cx, cy = fpg.switch_center(k)
        placed.append({
            "key": k,
            "shape": affine_transform(shape, [a, b, d, e, 0, 0]),
            "center": (a * cx + b * cy, d * cx + e * cy),
        })

    key_area = unary_union([p["shape"] for p in placed])
    dx = float(mesh_bounds[0, 0]) + margin - key_area.bounds[0]
    dy = float(mesh_bounds[0, 1]) + margin - key_area.bounds[1]
    for p in placed:
        p["shape"] = translate(p["shape"], xoff=dx, yoff=dy)
        p["center"] = (p["center"][0] + dx, p["center"][1] + dy)
    return placed


def key_text(k) -> str:
    """Label for a key: KLE legend, or its width when the legend is empty."""
    label = str(k.get("label", "")).replace("\n", " ").strip()
    if not label:
        label = f"{k['w']:g}u"
    if max(float(k["w"]), float(k["h"])) >= 1.75:
        label += f"\n{k['w']:g}x{k['h']:g}u"
    return label


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _polygon_path(poly: Polygon):
    from matplotlib.path import Path as MplPath

    poly = orient(poly, 1.0)
    verts, codes = [], []
    for ring in [poly.exterior, *poly.interiors]:
        pts = list(ring.coords)
        verts += pts
        codes += [MplPath.MOVETO] + [MplPath.LINETO] * (len(pts) - 2) + [MplPath.CLOSEPOLY]
    return MplPath(verts, codes)


def render_preview(stl_path: Path, layout_path: Path, output: Path, *,
                   margin: float = fpg.DEFAULT_MARGIN, global_transform: bool = True,
                   z: float | None = None, dpi: int = 150, labels: bool = True,
                   title: str | None = None) -> Path:
    import json

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch

    mesh = trimesh.load(stl_path, force="mesh")
    material, z = plate_section(mesh, z)
    keys = fpg.parse_kle(json.loads(layout_path.read_text(encoding="utf-8")))
    matrix = GLOBAL_MATRIX if global_transform else IDENTITY_MATRIX
    placed = keys_in_plate_frame(keys, mesh.bounds, margin, matrix)

    x0, y0 = float(mesh.bounds[0, 0]), float(mesh.bounds[0, 1])
    x1, y1 = float(mesh.bounds[1, 0]), float(mesh.bounds[1, 1])
    width, height = x1 - x0, y1 - y0
    pad = 32.0

    inch_per_mm = 0.06 if max(width, height) > 150 else 0.09
    fig_w = max(6.0, (width + 2 * pad) * inch_per_mm)
    fig_h = max(4.0, (height + 2 * pad) * inch_per_mm)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # Material (gray) and cutouts (white).
    geoms = material.geoms if material.geom_type == "MultiPolygon" else [material]
    for g in geoms:
        ax.add_patch(PathPatch(_polygon_path(g), facecolor="#c9cdd2",
                               edgecolor="#20242a", linewidth=0.6, zorder=2))

    # Key outlines (KLE geometry) for reference.
    for p in placed:
        for g in (p["shape"].geoms if p["shape"].geom_type == "MultiPolygon" else [p["shape"]]):
            xs, ys = g.exterior.xy
            ax.plot(xs, ys, color="#7a8794", linewidth=0.4, linestyle=(0, (3, 3)), zorder=3)

    if labels:
        font = 72.0 * fpg.UNIT * inch_per_mm * 0.11
        for p in placed:
            ax.text(p["center"][0], p["center"][1], key_text(p["key"]), ha="center",
                    va="center", fontsize=font, color="#12358a", zorder=5,
                    linespacing=1.0)

    # Axis cross at the CAD origin.
    arrow = dict(arrowstyle="-|>", lw=1.6, shrinkA=0, shrinkB=0)
    ax.annotate("", xy=(22, 0), xytext=(-10, 0), zorder=6,
                arrowprops={**arrow, "color": "#d62728"})
    ax.annotate("", xy=(0, 22), xytext=(0, -10), zorder=6,
                arrowprops={**arrow, "color": "#2ca02c"})
    ax.text(24, -2, "X", color="#d62728", fontsize=9, fontweight="bold", va="top", zorder=6)
    ax.text(-2, 24, "Y", color="#2ca02c", fontsize=9, fontweight="bold", ha="right", zorder=6)
    ax.plot([0], [0], marker="o", color="k", markersize=3, zorder=7)

    # Scale bar below the plate.
    bar = 50.0 if width > 200 else 20.0
    by = y0 - 14
    ax.plot([x0, x0 + bar], [by, by], color="k", linewidth=2.5, solid_capstyle="butt", zorder=6)
    ax.text(x0 + bar / 2, by - 2, f"{bar:g} mm", ha="center", va="top", fontsize=8, zorder=6)

    # Compass: where did KLE "right" and KLE "down" (typist side) end up?
    a, b, d, e = matrix
    cx, cy, length = x1 - 24.0, y1 + 14.0, 14.0
    for (vx, vy), text in (((1, 0), "KLE right"), ((0, 1), "KLE down (typist)")):
        tx, ty = a * vx + b * vy, d * vx + e * vy
        ax.annotate("", xy=(cx + tx * length, cy + ty * length), xytext=(cx, cy), zorder=6,
                    arrowprops=dict(arrowstyle="-|>", color="#12358a", lw=1.4,
                                    shrinkA=0, shrinkB=0))
        ax.text(cx + tx * (length + 2), cy + ty * (length + 2), text, fontsize=7,
                color="#12358a", zorder=6,
                ha="left" if tx > 0 else ("right" if tx < 0 else "center"),
                va="bottom" if ty > 0 else ("top" if ty < 0 else "center"))

    ax.set_xlim(x0 - pad, x1 + pad)
    ax.set_ylim(y0 - pad, y1 + pad)
    ax.set_aspect("equal")
    ax.grid(True, color="#e3e6ea", linewidth=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xlabel("X [mm]")
    ax.set_ylabel("Y [mm]")
    ax.set_title(title or f"{stl_path.name} - section at z={z:.2f} mm, view from +Z "
                 f"({'whole-plate transform' if global_transform else 'no whole-plate transform'})",
                 fontsize=9)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return output


def main():
    parser = argparse.ArgumentParser(description="Render a top-view preview PNG of a Fat Plate STL.")
    parser.add_argument("stl", type=Path, help="plate STL produced by the generator")
    parser.add_argument("--layout", type=Path, required=True, help="KLE raw data JSON used for the plate")
    parser.add_argument("--output", type=Path, default=None, help="PNG path (default: STL name + .png)")
    parser.add_argument("--margin", type=float, default=fpg.DEFAULT_MARGIN,
                        help="margin that was used for the plate (default: %(default)s mm)")
    parser.add_argument("--no-global-transform", action="store_true",
                        help="the STL was made without the whole-plate transform "
                             "(e.g. by generator versions before WP-01)")
    parser.add_argument("--z", type=float, default=None, help="section height in mm (default: half plate height)")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--no-labels", action="store_true", help="do not draw key labels")
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    output = args.output or args.stl.with_suffix(".png")
    render_preview(args.stl, args.layout, output, margin=args.margin,
                   global_transform=not args.no_global_transform, z=args.z, dpi=args.dpi,
                   labels=not args.no_labels, title=args.title)
    print(f"Preview written to {output}")


if __name__ == "__main__":
    main()

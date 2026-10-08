#!/usr/bin/env python3
"""
Fat Plate Generator

Generate a clean, printable keyboard plate from KLE Raw Data JSON.

The geometry is reconstructed directly from the supplied STL templates.
No voxelization is used.

Important design rule
---------------------
KLE describes the physical key geometry.

The supplied stabilizer STL describes a reusable stabilizer cavity template.

These are intentionally treated as two separate coordinate systems.
Stabilizer orientation is resolved explicitly and is never inferred from
the orientation of the generated CAD solid itself.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cadquery as cq
import numpy as np
import trimesh
from shapely.affinity import rotate, scale, translate
from shapely.geometry import LineString, Polygon, box
from shapely.ops import polygonize, unary_union


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UNIT_MM = 19.05

DEFAULT_MARGIN_MM = 1.0
DEFAULT_JSON = "keyboard-layout.json"
DEFAULT_SOCKET = "switch_socket.stl"
DEFAULT_STABILIZER = "stabilizer.stl"
DEFAULT_SPACEBAR_CENTERED = "stabilzer_spacebar.stl"
DEFAULT_SPACEBAR_OFF_CENTERED = "stabilzer_spacebar_off-center.stl"
DEFAULT_OUTPUT = "fat_plate_export.stl"

EPS = 0.02
SIZE_TOL = 0.08
GEOMETRY_TOL = 1e-7


# ---------------------------------------------------------------------------
# Stabilizer transformation configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StabilizerTransform:
    """
    Explicit transformation applied to a stabilizer template.

    Rotation is performed around the template's own geometric center.

    mirror_x / mirror_y are applied in template-local coordinates before
    rotation.

    This configuration deliberately has nothing to do with the KLE key's
    physical width/height. That distinction prevents orientation bugs.
    """

    rotation_deg: float = 0.0
    mirror_x: bool = False
    mirror_y: bool = False


# ---------------------------------------------------------------------------
# USER CONFIGURATION
# ---------------------------------------------------------------------------
#
# This is the place where individual stabilizer orientations can be changed.
#
# The supplied stabilizer STL is considered the canonical template.
#
# Vertical 2U stabilizers:
#     rotation = 0°
#
# Horizontal 2U stabilizers:
#     rotation = 90°
#
# Num+ is explicitly listed because it must use exactly the same orientation
# as the ISO Enter / Num Enter family in the current template set.
#
# If your STL orientation changes later, this table is the only place that
# should normally need adjustment.
#
# Labels are matched against the first line of a KLE label.
#
# ---------------------------------------------------------------------------

STABILIZER_TRANSFORMS: dict[str, StabilizerTransform] = {
    # Main ISO Enter.
    "Enter": StabilizerTransform(rotation_deg=0.0),

    # Numpad plus.
    #
    # IMPORTANT:
    # Num+ must have the same stabilizer orientation as the vertical
    # ISO/Num Enter stabilizers.
    "+": StabilizerTransform(rotation_deg=0.0),

    # Numpad Enter also uses the same orientation.
    #
    # KLE normally labels this simply "Enter", therefore the "Enter" rule
    # above covers it as well.
}


DEFAULT_VERTICAL_STABILIZER_TRANSFORM = StabilizerTransform(
    rotation_deg=0.0
)

DEFAULT_HORIZONTAL_STABILIZER_TRANSFORM = StabilizerTransform(
    rotation_deg=90.0
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Key:
    """Normalized representation of one KLE key."""

    label: str
    x: float
    y: float

    width: float = 1.0
    height: float = 1.0

    x2: float = 0.0
    y2: float = 0.0
    width2: float = 1.0
    height2: float = 1.0

    rotation: float = 0.0
    rotation_x: float = 0.0
    rotation_y: float = 0.0


@dataclass(frozen=True)
class StabilizerSection:
    """One horizontal cross-section of a stabilizer STL."""

    z0: float
    z1: float
    polygon: Polygon


@dataclass(frozen=True)
class StabilizerTemplate:
    """Reconstructed geometry information from a stabilizer STL."""

    zmin: float
    zmax: float
    thickness: float
    intervals: tuple[StabilizerSection, ...]
    long_axis: int
    template_long: float
    template_center: tuple[float, float]
    vertices: int


@dataclass(frozen=True)
class SocketProfile:
    """Reconstructed vertical profile of the normal switch socket."""

    zmin: float
    zmax: float
    thickness: float
    lower_size: float
    min_size: float
    top_size: float
    taper_start: float
    taper_end: float
    collar_start: float
    intervals: tuple[dict[str, float], ...]


# ---------------------------------------------------------------------------
# KLE parsing
# ---------------------------------------------------------------------------

def parse_kle(data: list[list[Any]]) -> list[Key]:
    """
    Parse KLE Raw Data JSON into normalized Key objects.

    KLE uses stateful dictionaries. A dictionary modifies the properties
    of subsequent keys in the same row until another dictionary changes them.
    """

    keys: list[Key] = []

    x = 0.0
    y = 0.0

    reset_x = 0.0
    reset_y = 0.0

    properties: dict[str, float] = {
        "w": 1.0,
        "h": 1.0,
        "x2": 0.0,
        "y2": 0.0,
        "w2": 1.0,
        "h2": 1.0,
        "r": 0.0,
        "rx": 0.0,
        "ry": 0.0,
    }

    for row in data:
        for item in row:
            if isinstance(item, dict):
                if "r" in item:
                    properties["r"] = float(item["r"])

                if "rx" in item:
                    properties["rx"] = float(item["rx"])
                    reset_x = properties["rx"]
                    x = reset_x

                if "ry" in item:
                    properties["ry"] = float(item["ry"])
                    reset_y = properties["ry"]
                    y = reset_y

                x += float(item.get("x", 0.0))
                y += float(item.get("y", 0.0))

                properties["w"] = float(item.get("w", 1.0))
                properties["h"] = float(item.get("h", 1.0))
                properties["x2"] = float(item.get("x2", 0.0))
                properties["y2"] = float(item.get("y2", 0.0))
                properties["w2"] = float(
                    item.get("w2", properties["w"])
                )
                properties["h2"] = float(
                    item.get("h2", properties["h"])
                )

                continue

            keys.append(
                Key(
                    label=str(item),
                    x=x,
                    y=y,
                    width=properties["w"],
                    height=properties["h"],
                    x2=properties["x2"],
                    y2=properties["y2"],
                    width2=properties["w2"],
                    height2=properties["h2"],
                    rotation=properties["r"],
                    rotation_x=properties["rx"],
                    rotation_y=properties["ry"],
                )
            )

            x += properties["w"]

            properties.update(
                w=1.0,
                h=1.0,
                x2=0.0,
                y2=0.0,
                w2=1.0,
                h2=1.0,
            )

        x = reset_x
        y += 1.0

    return keys


# ---------------------------------------------------------------------------
# KLE geometry
# ---------------------------------------------------------------------------

def local_key_shape(key: Key):
    """Return the local 2D shape represented by a KLE key."""

    primary = box(
        0.0,
        0.0,
        key.width,
        key.height,
    )

    secondary = box(
        key.x2,
        key.y2,
        key.x2 + key.width2,
        key.y2 + key.height2,
    )

    shape = unary_union((primary, secondary))

    if abs(key.rotation) > GEOMETRY_TOL:
        shape = rotate(
            shape,
            key.rotation,
            origin=(
                key.rotation_x - key.x,
                key.rotation_y - key.y,
            ),
            use_radians=False,
        )

    return shape


def switch_center(key: Key) -> tuple[float, float]:
    """
    Return the switch center in millimetres.

    KLE rotation is respected here so that the center remains correct for
    rotated layouts.
    """

    cx = key.x + key.width / 2.0
    cy = key.y + key.height / 2.0

    if abs(key.rotation) > GEOMETRY_TOL:
        angle = math.radians(key.rotation)

        dx = cx - key.rotation_x
        dy = cy - key.rotation_y

        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)

        cx = (
            key.rotation_x
            + dx * cos_angle
            - dy * sin_angle
        )

        cy = (
            key.rotation_y
            + dx * sin_angle
            + dy * cos_angle
        )

    return cx * UNIT_MM, cy * UNIT_MM


# ---------------------------------------------------------------------------
# STL analysis
# ---------------------------------------------------------------------------

def clustered_z_levels(
    mesh: trimesh.Trimesh,
    decimals: int = 5,
) -> list[float]:
    """Return stable Z levels from an STL mesh."""

    values = np.unique(
        np.round(mesh.vertices[:, 2], decimals)
    )

    if len(values) == 0:
        raise ValueError("STL has no vertices.")

    groups: list[list[float]] = [[float(values[0])]]

    for z in values[1:]:
        z_value = float(z)

        if z_value - groups[-1][-1] < 0.002:
            groups[-1].append(z_value)
        else:
            groups.append([z_value])

    return [
        sum(group) / len(group)
        for group in groups
    ]


def section_size(
    mesh: trimesh.Trimesh,
    z: float,
) -> float | None:
    """Measure the average XY extent of a horizontal STL section."""

    section = mesh.section(
        plane_origin=[0, 0, float(z)],
        plane_normal=[0, 0, 1],
    )

    if section is None or len(section.entities) == 0:
        return None

    entity = max(
        section.entities,
        key=lambda current: len(current.points),
    )

    points = section.vertices[entity.points]

    if len(points) < 4:
        return None

    extent = (
        points[:, :2].max(axis=0)
        - points[:, :2].min(axis=0)
    )

    return float((extent[0] + extent[1]) / 2.0)


def socket_profile(path: Path) -> SocketProfile:
    """Reconstruct the vertical profile of the supplied switch socket STL."""

    mesh = trimesh.load(path, force="mesh")

    if mesh.is_empty:
        raise ValueError(f"Socket STL is empty: {path}")

    zmin = float(mesh.bounds[0, 2])
    zmax = float(mesh.bounds[1, 2])
    thickness = zmax - zmin

    if thickness <= 0:
        raise ValueError(
            "Socket STL has zero Z thickness."
        )

    levels = clustered_z_levels(mesh)
    intervals: list[dict[str, float]] = []

    for start, end in zip(levels[:-1], levels[1:]):
        if end - start < 0.002:
            continue

        size = section_size(
            mesh,
            (start + end) * 0.5,
        )

        if size is not None:
            intervals.append(
                {
                    "z0": start,
                    "z1": end,
                    "size": size,
                }
            )

    if not intervals:
        raise ValueError(
            "Could not extract a horizontal profile "
            "from socket STL."
        )

    sizes = [interval["size"] for interval in intervals]

    lower_size = sizes[0]
    top_size = sizes[-1]
    min_size = min(sizes)

    taper_start = next(
        (
            interval["z0"]
            for interval in intervals
            if interval["size"] < lower_size - SIZE_TOL
        ),
        intervals[0]["z0"],
    )

    taper_end = next(
        (
            interval["z0"]
            for interval in intervals
            if (
                interval["z0"] >= taper_start
                and abs(interval["size"] - min_size)
                <= SIZE_TOL
            )
        ),
        taper_start,
    )

    collar_start = next(
        (
            interval["z0"]
            for interval in intervals
            if (
                interval["z0"] >= taper_end
                and interval["size"] >= top_size - SIZE_TOL
            )
        ),
        intervals[-1]["z0"],
    )

    return SocketProfile(
        zmin=zmin,
        zmax=zmax,
        thickness=thickness,
        lower_size=lower_size,
        min_size=min_size,
        top_size=top_size,
        taper_start=max(zmin, min(zmax, taper_start)),
        taper_end=max(zmin, min(zmax, taper_end)),
        collar_start=max(zmin, min(zmax, collar_start)),
        intervals=tuple(intervals),
    )


def remove_collinear(
    polygon: Polygon,
    tolerance: float = 1e-5,
) -> Polygon:
    """
    Remove triangulation-only collinear vertices.

    The polygon shape itself is not intentionally simplified.
    """

    points = np.asarray(
        polygon.exterior.coords[:-1],
        dtype=float,
    )

    changed = True

    while changed and len(points) > 3:
        changed = False
        keep: list[np.ndarray] = []
        count = len(points)

        for index in range(count):
            a = points[index - 1]
            b = points[index]
            c = points[(index + 1) % count]

            u = b - a
            v = c - b

            cross = abs(
                float(u[0] * v[1] - u[1] * v[0])
            )

            dot = float(u[0] * v[0] + u[1] * v[1])

            if cross <= tolerance and dot >= -tolerance:
                changed = True
                continue

            keep.append(b)

        points = np.asarray(keep, dtype=float)

    return Polygon(points)


def triangle_section_polygon(
    mesh: trimesh.Trimesh,
    z: float,
) -> Polygon:
    """
    Intersect every STL triangle with a horizontal plane.

    This avoids topology-dependent behaviour in trimesh.section()
    and creates deterministic polygon geometry.
    """

    vertices = np.asarray(
        mesh.vertices,
        dtype=float,
    )

    faces = np.asarray(
        mesh.faces,
        dtype=np.int64,
    )

    lines: list[LineString] = []

    for face_indices in faces:
        triangle = vertices[face_indices]
        points: list[np.ndarray] = []

        for first, second in (
            (triangle[0], triangle[1]),
            (triangle[1], triangle[2]),
            (triangle[2], triangle[0]),
        ):
            z_first = float(first[2])
            z_second = float(second[2])

            if (z_first < z < z_second) or (
                z_second < z < z_first
            ):
                factor = (
                    (z - z_first)
                    / (z_second - z_first)
                )

                point = first + factor * (second - first)
                points.append(np.round(point[:2], 6))

        if (
            len(points) == 2
            and np.linalg.norm(points[0] - points[1]) > 1e-8
        ):
            lines.append(
                LineString(points)
            )

    if not lines:
        raise ValueError(
            f"No stabilizer section at z={z:.6f}."
        )

    polygons_found = list(
        polygonize(unary_union(lines))
    )

    if not polygons_found:
        raise ValueError(
            f"Could not polygonize stabilizer section "
            f"at z={z:.6f}."
        )

    polygon = max(
        polygons_found,
        key=lambda current: current.area,
    )

    if not polygon.is_valid or polygon.area <= 1e-6:
        raise ValueError(
            f"Invalid stabilizer section at z={z:.6f}."
        )

    polygon = remove_collinear(polygon)

    if not polygon.is_valid:
        raise ValueError(
            f"Cleaned stabilizer section at z={z:.6f} "
            "is invalid."
        )

    return polygon


def stabilizer_template(path: Path) -> StabilizerTemplate:
    """Reconstruct the supplied stabilizer STL into clean CAD sections."""

    mesh = trimesh.load(path, force="mesh")

    if mesh.is_empty:
        raise ValueError(
            f"Stabilizer STL is empty: {path}"
        )

    zmin = float(mesh.bounds[0, 2])
    zmax = float(mesh.bounds[1, 2])

    if zmax <= zmin:
        raise ValueError(
            "Stabilizer STL has zero Z thickness."
        )

    levels = clustered_z_levels(mesh)
    intervals: list[StabilizerSection] = []

    for start, end in zip(levels[:-1], levels[1:]):
        if end - start < 0.002:
            continue

        polygon = triangle_section_polygon(
            mesh,
            (start + end) * 0.5,
        )

        intervals.append(
            StabilizerSection(
                z0=start,
                z1=end,
                polygon=polygon,
            )
        )

    if not intervals:
        raise ValueError(
            "Could not reconstruct stabilizer Z profile."
        )

    base_polygon = intervals[0].polygon

    base_extent = (
        np.asarray(base_polygon.bounds[2:4])
        - np.asarray(base_polygon.bounds[0:2])
    )

    all_extents = [
        np.asarray(section.polygon.bounds[2:4])
        - np.asarray(section.polygon.bounds[0:2])
        for section in intervals
    ]

    long_axis = (
        1
        if base_extent[1] >= base_extent[0]
        else 0
    )

    template_long = max(
        float(extent[long_axis])
        for extent in all_extents
    )

    bounds = base_polygon.bounds

    center = (
        (bounds[0] + bounds[2]) / 2.0,
        (bounds[1] + bounds[3]) / 2.0,
    )

    return StabilizerTemplate(
        zmin=zmin,
        zmax=zmax,
        thickness=zmax - zmin,
        intervals=tuple(intervals),
        long_axis=long_axis,
        template_long=template_long,
        template_center=center,
        vertices=sum(
            len(section.polygon.exterior.coords) - 1
            for section in intervals
        ),
    )


# ---------------------------------------------------------------------------
# CAD helpers
# ---------------------------------------------------------------------------

def polygon_wires(
    polygon: Polygon,
):
    """Convert a Shapely polygon to CadQuery wires."""

    outer = (
        cq.Workplane("XY")
        .polyline(
            list(polygon.exterior.coords)[:-1]
        )
        .close()
        .wire()
        .val()
    )

    holes = [
        (
            cq.Workplane("XY")
            .polyline(list(ring.coords)[:-1])
            .close()
            .wire()
            .val()
        )
        for ring in polygon.interiors
    ]

    return outer, holes


def face(polygon: Polygon):
    """Create a CadQuery face from a Shapely polygon."""

    outer, holes = polygon_wires(polygon)

    return cq.Face.makeFromWires(
        outer,
        holes,
    )


def polygons(geometry):
    """Normalize Polygon/MultiPolygon into a list of polygons."""

    if geometry.geom_type == "Polygon":
        return [geometry]

    if geometry.geom_type == "MultiPolygon":
        return list(geometry.geoms)

    raise ValueError(
        f"Unexpected polygon geometry: "
        f"{geometry.geom_type}"
    )


def extruded_footprint(
    footprint,
    z: float,
    height: float,
):
    """Extrude every footprint polygon into a solid."""

    solids = []

    for polygon in polygons(footprint):
        solids.append(
            cq.Solid.extrudeLinear(
                face(polygon),
                cq.Vector(0, 0, height),
            ).located(
                cq.Location(
                    cq.Vector(0, 0, z)
                )
            )
        )

    if not solids:
        raise RuntimeError(
            "Plate footprint is empty."
        )

    return (
        solids[0]
        if len(solids) == 1
        else cq.Compound.makeCompound(solids)
    )


def square_wire(
    size: float,
    z: float,
    cx: float = 0.0,
    cy: float = 0.0,
):
    """Create a square wire centered at an XY position."""

    return (
        cq.Workplane("XY")
        .workplane(offset=z)
        .center(cx, cy)
        .rect(size, size)
        .wire()
        .val()
    )


def cavity_for_center(
    profile: SocketProfile,
    cx: float,
    cy: float,
):
    """Create a normal MX switch cavity."""

    z0 = profile.zmin - EPS
    z1 = profile.zmax + EPS

    lower = profile.lower_size
    narrow = profile.min_size
    top = profile.top_size

    taper_start = profile.taper_start
    taper_end = profile.taper_end
    collar_start = profile.collar_start

    solids = []

    if taper_start > z0 + 1e-4:
        solids.append(
            cq.Solid.extrudeLinear(
                square_wire(
                    lower,
                    z0,
                    cx,
                    cy,
                ),
                [],
                cq.Vector(
                    0,
                    0,
                    taper_start - z0,
                ),
            )
        )

    if (
        taper_end > taper_start + 1e-4
        and abs(lower - narrow) > SIZE_TOL
    ):
        solids.append(
            cq.Solid.makeLoft(
                [
                    square_wire(
                        lower,
                        taper_start,
                        cx,
                        cy,
                    ),
                    square_wire(
                        narrow,
                        taper_end,
                        cx,
                        cy,
                    ),
                ],
                ruled=True,
            )
        )

    if collar_start > taper_end + 1e-4:
        solids.append(
            cq.Solid.extrudeLinear(
                square_wire(
                    narrow,
                    taper_end,
                    cx,
                    cy,
                ),
                [],
                cq.Vector(
                    0,
                    0,
                    collar_start - taper_end,
                ),
            )
        )

    if z1 > collar_start + 1e-4:
        solids.append(
            cq.Solid.extrudeLinear(
                square_wire(
                    top,
                    collar_start,
                    cx,
                    cy,
                ),
                [],
                cq.Vector(
                    0,
                    0,
                    z1 - collar_start,
                ),
            )
        )

    if not solids:
        raise RuntimeError(
            "Could not construct switch cavity."
        )

    result = solids[0]

    for solid in solids[1:]:
        result = result.fuse(solid)

    return result


# ---------------------------------------------------------------------------
# Stabilizer transformations
# ---------------------------------------------------------------------------

def transform_polygon(
    polygon: Polygon,
    transform: StabilizerTransform,
) -> Polygon:
    """
    Apply one explicit stabilizer transformation.

    Transform order:

        1. mirror X
        2. mirror Y
        3. rotate

    The operation is performed around the polygon's own centroid.

    This is critical: rotation must not happen around the global CAD origin.
    """

    center = polygon.centroid

    transformed = polygon

    if transform.mirror_x:
        transformed = scale(
            transformed,
            xfact=-1.0,
            yfact=1.0,
            origin=center,
        )

    if transform.mirror_y:
        transformed = scale(
            transformed,
            xfact=1.0,
            yfact=-1.0,
            origin=center,
        )

    if abs(transform.rotation_deg) > GEOMETRY_TOL:
        transformed = rotate(
            transformed,
            transform.rotation_deg,
            origin=center,
            use_radians=False,
        )

    return transformed


def transform_stabilizer_polygon(
    polygon: Polygon,
    template: StabilizerTemplate,
    key_length_units: float,
    scale_mode: str,
) -> Polygon:
    """
    Scale the stabilizer along its long axis.

    Orientation is intentionally NOT handled here.

    This function only answers:
        "How long should this stabilizer be?"
    """

    if scale_mode == "none":
        return polygon

    target_long = (
        template.template_long
        * (key_length_units / 2.0)
    )

    if abs(
        target_long - template.template_long
    ) < GEOMETRY_TOL:
        return polygon

    central_half = 8.0
    template_half = template.template_long / 2.0

    denominator = template_half - central_half

    if abs(denominator) < GEOMETRY_TOL:
        raise ValueError(
            "Stabilizer template cannot be scaled: "
            "template has no scalable outer section."
        )

    scale_factor = (
        (target_long / 2.0) - central_half
    ) / denominator

    if scale_factor <= 0:
        raise ValueError(
            "Requested stabilizer size is too small "
            "for the template."
        )

    def transform_coordinate(
        x: float,
        y: float,
    ) -> tuple[float, float]:
        value = (
            y
            if template.long_axis == 1
            else x
        )

        sign = (
            1.0
            if value >= 0.0
            else -1.0
        )

        absolute = abs(value)

        if absolute <= central_half:
            new_value = value
        else:
            new_value = (
                sign
                * (
                    central_half
                    + (
                        absolute
                        - central_half
                    )
                    * scale_factor
                )
            )

        if template.long_axis == 1:
            return x, new_value

        return new_value, y

    exterior = [
        transform_coordinate(x, y)
        for x, y in polygon.exterior.coords
    ]

    holes = [
        [
            transform_coordinate(x, y)
            for x, y in ring.coords
        ]
        for ring in polygon.interiors
    ]

    return Polygon(
        exterior,
        holes,
    )


def key_label_for_transform(key: Key) -> str:
    """
    Normalize a KLE label for transform lookup.

    KLE labels often contain multiple lines, e.g. "2\\nPgDn".
    The first line is used as the semantic key identifier.
    """

    return key.label.split("\n", 1)[0].strip()


def is_horizontal_key(key: Key) -> bool:
    """Return True if the stabilized key is physically horizontal."""

    return key.width > key.height


def resolve_stabilizer_transform(
    key: Key,
) -> StabilizerTransform:
    """
    Resolve the explicit stabilizer orientation for one key.

    Priority:

        1. Explicit label override
        2. Physical key orientation

    This means special keys can override the generic horizontal/vertical
    rule without contaminating the geometry implementation.
    """

    label = key_label_for_transform(key)

    explicit = STABILIZER_TRANSFORMS.get(label)

    if explicit is not None:
        return explicit

    if is_horizontal_key(key):
        return DEFAULT_HORIZONTAL_STABILIZER_TRANSFORM

    return DEFAULT_VERTICAL_STABILIZER_TRANSFORM


def stabilizer_cavity(
    template: StabilizerTemplate,
    cx: float,
    cy: float,
    key_length_units: float,
    transform: StabilizerTransform,
    scale_mode: str,
):
    """
    Build one complete stabilizer cavity.

    The transformation pipeline is deliberately explicit:

        STL sections
            ↓
        length scaling
            ↓
        local mirroring
            ↓
        local rotation
            ↓
        translation to switch center
    """

    transformed_sections: list[Polygon] = []

    for section in template.intervals:
        polygon = transform_stabilizer_polygon(
            section.polygon,
            template,
            key_length_units,
            scale_mode,
        )

        polygon = transform_polygon(
            polygon,
            transform,
        )

        transformed_sections.append(polygon)

    solids = []

    for index, section in enumerate(template.intervals):
        z0 = section.z0
        z1 = section.z1

        if index == 0:
            z0 -= EPS

        if index == len(template.intervals) - 1:
            z1 += EPS

        solids.append(
            cq.Solid.extrudeLinear(
                face(
                    transformed_sections[index]
                ),
                cq.Vector(
                    0,
                    0,
                    z1 - z0,
                ),
            ).located(
                cq.Location(
                    cq.Vector(
                        cx,
                        cy,
                        z0,
                    )
                )
            )
        )

    if not solids:
        raise RuntimeError(
            "Stabilizer template produced no geometry."
        )

    result = solids[0]

    for solid in solids[1:]:
        result = result.fuse(solid)

    return result


# ---------------------------------------------------------------------------
# Key classification
# ---------------------------------------------------------------------------

def is_spacebar_key(key: Key) -> bool:
    """
    KLE Raw Data represents the supplied spacebar with an empty label.
    """

    return (
        key.label == ""
        and max(
            key.width,
            key.height,
        ) >= 6.0
    )


def is_stabilized_key(
    key: Key,
    minimum_units: float,
) -> bool:
    """
    Determine whether a key should receive the normal stabilizer cavity.
    """

    if key_label_for_transform(key) == "Caps Lock":
        return False

    if is_spacebar_key(key):
        return False

    return max(
        key.width,
        key.height,
    ) >= minimum_units


# ---------------------------------------------------------------------------
# Boolean helpers
# ---------------------------------------------------------------------------

def fuse_all(solids: list):
    """Fuse a list of CadQuery solids."""

    if not solids:
        raise RuntimeError(
            "Cannot fuse an empty solid list."
        )

    result = solids[0]

    for solid in solids[1:]:
        result = result.fuse(solid)

    return result


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def generate(
    kle_path: Path,
    socket_path: Path,
    stabilizer_path: Path,
    spacebar_centered_path: Path,
    spacebar_off_centered_path: Path,
    *,
    spacebar_position: str = "centered",
    output: Path = Path(DEFAULT_OUTPUT),
    margin: float = DEFAULT_MARGIN_MM,
    stabilizer_min_unit: float = 1.75,
    stabilizer_scale_mode: str = "none",
) -> None:
    """Generate a Fat Plate STL from KLE Raw Data."""

    data = json.loads(
        kle_path.read_text(
            encoding="utf-8"
        )
    )

    keys = parse_kle(data)

    if not keys:
        raise ValueError(
            "KLE JSON contains no keys."
        )

    profile = socket_profile(
        socket_path
    )

    stabilizer = stabilizer_template(
        stabilizer_path
    )

    spacebar_path = (
        spacebar_centered_path
        if spacebar_position == "centered"
        else spacebar_off_centered_path
    )

    spacebar_stabilizer = stabilizer_template(
        spacebar_path
    )

    # ---------------------------------------------------------------
    # Build plate footprint
    # ---------------------------------------------------------------

    key_shapes = []

    for key in keys:
        shape = local_key_shape(key)

        shape = translate(
            shape,
            xoff=key.x,
            yoff=key.y,
        )

        shape = scale(
            shape,
            xfact=UNIT_MM,
            yfact=UNIT_MM,
            origin=(0, 0),
        )

        key_shapes.append(shape)

    min_x = min(
        shape.bounds[0]
        for shape in key_shapes
    )

    min_y = min(
        shape.bounds[1]
        for shape in key_shapes
    )

    key_shapes = [
        translate(
            shape,
            xoff=-min_x,
            yoff=-min_y,
        )
        for shape in key_shapes
    ]

    footprint = unary_union(
        key_shapes
    ).buffer(
        margin,
        join_style=2,
    )

    # ---------------------------------------------------------------
    # Calculate switch centers
    # ---------------------------------------------------------------

    centers = []

    for key in keys:
        cx, cy = switch_center(key)

        centers.append(
            (
                cx - min_x,
                cy - min_y,
            )
        )

    # ---------------------------------------------------------------
    # Base plate
    # ---------------------------------------------------------------

    plate = extruded_footprint(
        footprint,
        profile.zmin,
        profile.thickness,
    )

    normal_cavities = []
    stabilizer_cavities = []
    spacebar_cavities = []

    stabilizer_keys: list[Key] = []
    spacebar_keys: list[Key] = []

    # ---------------------------------------------------------------
    # Generate cavities
    # ---------------------------------------------------------------

    for key, (cx, cy) in zip(
        keys,
        centers,
    ):
        if is_spacebar_key(key):
            spacebar_keys.append(key)

            # Spacebar templates already contain their correct internal
            # switch/stabilizer relationship. No length scaling or generic
            # orientation rule is applied.
            spacebar_cavities.append(
                stabilizer_cavity(
                    spacebar_stabilizer,
                    cx,
                    cy,
                    6.25,
                    StabilizerTransform(),
                    "none",
                )
            )

            continue

        if is_stabilized_key(
            key,
            stabilizer_min_unit,
        ):
            stabilizer_keys.append(key)

            length_units = max(
                key.width,
                key.height,
            )

            transform = resolve_stabilizer_transform(
                key
            )

            stabilizer_cavities.append(
                stabilizer_cavity(
                    stabilizer,
                    cx,
                    cy,
                    length_units,
                    transform,
                    stabilizer_scale_mode,
                )
            )

            continue

        normal_cavities.append(
            cavity_for_center(
                profile,
                cx,
                cy,
            )
        )

    cavities = (
        normal_cavities
        + stabilizer_cavities
        + spacebar_cavities
    )

    if not cavities:
        raise RuntimeError(
            "No cavities generated."
        )

    cavity = fuse_all(cavities)

    # ---------------------------------------------------------------
    # Cut cavities from plate
    # ---------------------------------------------------------------

    result = plate.cut(cavity)

    if not result.isValid():
        raise RuntimeError(
            "Generated CAD solid is invalid."
        )

    result = result.clean()

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cq.exporters.export(
        result,
        str(output),
        exportType="STL",
        tolerance=0.001,
        angularTolerance=0.1,
    )

    # ---------------------------------------------------------------
    # STL sanity check
    # ---------------------------------------------------------------
    #
    # IMPORTANT:
    # Never filter connected components here.
    #
    # A full-size keyboard can legitimately consist of multiple spatially
    # separated plate regions (F-row, navigation cluster, numpad, ...).
    #
    # CadQuery already validated the BRep.
    # Trimesh is only used here to make sure the exported STL isn't empty.
    # ---------------------------------------------------------------

    exported = trimesh.load_mesh(
        output,
        force="mesh",
    )

    if (
        exported.is_empty
        or len(exported.faces) == 0
    ):
        raise RuntimeError(
            "STL export produced an empty mesh."
        )

    exported.export(output)

    # ---------------------------------------------------------------
    # Console output
    # ---------------------------------------------------------------

    print()
    print("Fat Plate Generator")
    print("-------------------")
    print(f"KLE:             {kle_path}")
    print(f"Socket:          {socket_path}")
    print(f"Stabilizer:      {stabilizer_path}")
    print(
        f"Spacebar:        "
        f"{spacebar_path} ({spacebar_position})"
    )
    print(f"Output:          {output}")
    print(f"Keys:            {len(keys)}")
    print(
        f"Stabilizer keys: "
        f"{len(stabilizer_keys)}"
    )
    print(
        f"Spacebar keys:   "
        f"{len(spacebar_keys)}"
    )
    print(
        f"Plate thickness: "
        f"{profile.thickness:.4f} mm"
    )
    print(
        f"Normal narrow:   "
        f"{profile.min_size:.4f} mm"
    )
    print(
        f"Stab section:    "
        f"{stabilizer.vertices} vertices, "
        f"{stabilizer.template_long:.4f} mm long"
    )
    print(
        f"Stab scale:      "
        f"{stabilizer_scale_mode}"
    )
    print(
        "Stab transform:  "
        "explicit per-key configuration"
    )
    print(
        "Num+ transform:  "
        f"{STABILIZER_TRANSFORMS['+']}"
    )
    print(
        "Voxelization:    NONE"
    )
    print()
    print("Done.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""

    base = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description=(
            "Generate a clean Fat Plate STL "
            "from KLE Raw Data JSON."
        )
    )

    parser.add_argument(
        "--json",
        type=Path,
        default=base / DEFAULT_JSON,
        help="KLE Raw Data JSON.",
    )

    parser.add_argument(
        "--socket",
        type=Path,
        default=base / DEFAULT_SOCKET,
        help="Normal switch socket STL.",
    )

    parser.add_argument(
        "--stabilizer",
        type=Path,
        default=base / DEFAULT_STABILIZER,
        help="Normal stabilizer STL.",
    )

    parser.add_argument(
        "--spacebar-centered",
        type=Path,
        default=base / DEFAULT_SPACEBAR_CENTERED,
        help="Centered spacebar stabilizer STL.",
    )

    parser.add_argument(
        "--spacebar-off-centered",
        type=Path,
        default=base / DEFAULT_SPACEBAR_OFF_CENTERED,
        help="Off-centered spacebar stabilizer STL.",
    )

    parser.add_argument(
        "--spacebar-position",
        choices=[
            "centered",
            "off-centered",
        ],
        default="centered",
        help=(
            "Spacebar switch position."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=base / DEFAULT_OUTPUT,
        help="Output STL.",
    )

    parser.add_argument(
        "--margin",
        type=float,
        default=DEFAULT_MARGIN_MM,
        help="Plate margin in millimetres.",
    )

    parser.add_argument(
        "--stabilizer-min-unit",
        type=float,
        default=1.75,
        help=(
            "Minimum key size that receives "
            "a stabilizer cavity."
        ),
    )

    parser.add_argument(
        "--stabilizer-scale",
        choices=[
            "auto",
            "none",
        ],
        default="none",
        help=(
            "Scale stabilizer templates to "
            "different key lengths."
        ),
    )

    return parser


def main() -> None:
    """CLI entry point."""

    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        generate(
            args.json,
            args.socket,
            args.stabilizer,
            args.spacebar_centered,
            args.spacebar_off_centered,
            spacebar_position=args.spacebar_position,
            output=args.output,
            margin=args.margin,
            stabilizer_min_unit=args.stabilizer_min_unit,
            stabilizer_scale_mode=args.stabilizer_scale,
        )

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        raise


if __name__ == "__main__":
    main()
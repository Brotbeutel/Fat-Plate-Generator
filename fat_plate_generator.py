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
from dataclasses import dataclass, field, replace
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from shapely.affinity import affine_transform, rotate, scale, translate
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

VERSION = "0.25"
UNIT = 19.05
DEFAULT_MARGIN = 1
DEFAULT_STABILIZER_MIN_UNIT = 2.0
DEFAULT_JSON = "kle-jsons/keyboard-layout.json"
DEFAULT_SOCKET = "stl-templates/switch_socket.stl"
DEFAULT_SOCKET_WIDE_CAPS = "stl-templates/switch_socket_wide-caps.stl"
DEFAULT_STABILIZER = "stl-templates/stabilizer_2-00u.stl"
DEFAULT_SPACEBAR_CENTERED = "stl-templates/stabilizer_6-25u_centered.stl"
# The off-centered template is the RIGHT one, as designed; the left variant is its
# exact mirror image (see ``TemplateSet.spacebar_for``).
DEFAULT_SPACEBAR_OFF_CENTERED = "stl-templates/stabilizer_6-25u_off-center.stl"
# Switch position of the spacebar template, as seen from above with the typist
# at the bottom of the plate (x to the right).
SPACEBAR_POSITIONS = ("centered", "off-centered-left", "off-centered-right")
DEFAULT_SPACEBAR_POSITION = "centered"
# What a stepped key (KLE "l": true, for example a stepped Caps Lock) gets:
#   standard   the normal socket, at the centre of the first rectangle (w)
#   wide-caps the wide-caps socket template, at the centre of the second rectangle (w2)
# The plate outline always covers both rectangles.
STEPPED_MODES = ("standard", "wide-caps")
DEFAULT_STEPPED_KEY = "standard"
DEFAULT_OUTPUT = "fat_plate_export.stl"
EPS = 0.02
SCRIPT_DIR = Path(__file__).resolve().parent

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
    2. Whole plate: the footprint and the switch centres are rotated by
       ``global_rotation`` degrees about the origin, then mirrored along X if
       ``global_mirror_x``.  With the defaults (180 deg + mirror X) this is
       exactly the KLE -> CAD conversion (y down -> y up), (x, y) -> (x, -y),
       without any further turn of the plate.  The cutouts get only the
       ROTATION of this transform, never the mirror: a mirrored stabilizer
       would be a different part, so every cutout is the template as designed,
       turned in steps of 90 deg.  The one exception is the left off-centered
       spacebar, which IS the right template mirrored: an exact integer matrix in
       the template's own coordinates (x -> -x), applied before step 1, so that
       it stays the mirror image of the right one for every rotation.
    3. Everything is shifted so the plate's bounding box (including margin)
       starts at (0, 0).

    The wide-caps socket template of stepped keys is turned like a stabilizer
    (``wide_caps_rotation``); with the default 180 it comes out as designed.

    Defaults
    --------
    horizontal 180, vertical 90, spacebar 180, whole plate 180 deg + mirror X.
    The stabilizer rotations are measured in the KLE frame, about the switch
    centre.  Horizontal and spacebar cutouts have their long axis along X and
    the wider side of the cutout (the template is about 0.7 mm wider towards
    -Y) ends up towards the typist (low Y of the plate); vertical cutouts have
    their long axis along Y.  The values were chosen by the project owner after
    checking the exported plate; earlier versions mirrored the cutouts with the
    plate and therefore needed vertical 270 for the same result.  The old
    whole-plate transform is still available as ``global_rotation=90`` (a
    transposition, (x, y) -> (y, x)).

    "Rotate 180 deg, then mirror X" equals "flip KLE y".  That is the
    KLE -> CAD handedness fix and nothing else; any other ``global_rotation``
    just turns the finished plate by a further multiple of 90 deg.
    """

    stab_rotation_horizontal: int = 180
    stab_rotation_vertical: int = 90
    stab_rotation_spacebar: int = 180
    wide_caps_rotation: int = 180
    global_transform: bool = True
    global_rotation: int = 180
    global_mirror_x: bool = True

    def __post_init__(self):
        for name in ("stab_rotation_horizontal", "stab_rotation_vertical",
                     "stab_rotation_spacebar", "wide_caps_rotation", "global_rotation"):
            value = getattr(self, name)
            if value not in ROTATION_CHOICES:
                raise ValueError(f"{name} must be one of {ROTATION_CHOICES}, got {value!r}")


@dataclass(frozen=True)
class TemplateSet:
    """The set of STL template paths used to build a plate."""

    socket: Path
    wide_caps: Path
    stabilizer: Path
    spacebar_centered: Path
    spacebar_off_centered: Path

    def __post_init__(self):
        if self.wide_caps is None:
            object.__setattr__(
                self, "wide_caps",
                Path(self.socket).with_name(Path(DEFAULT_SOCKET_WIDE_CAPS).name),
            )

    @classmethod
    def defaults(cls, base: Path | None = None) -> "TemplateSet":
        base = Path(base) if base is not None else SCRIPT_DIR
        return cls(
            socket=base / DEFAULT_SOCKET,
            wide_caps=base / DEFAULT_SOCKET_WIDE_CAPS,
            stabilizer=base / DEFAULT_STABILIZER,
            spacebar_centered=base / DEFAULT_SPACEBAR_CENTERED,
            spacebar_off_centered=base / DEFAULT_SPACEBAR_OFF_CENTERED,
        )

    def spacebar_for(self, position: str) -> tuple[Path, bool]:
        """Template file and mirror flag for a spacebar switch position.

        There is one off-centered template (the right one).  The left position
        is that template mirrored; ``True`` in the second item says so.  This
        is the only place that maps a position to a file.
        """
        mapping = {
            "centered": (self.spacebar_centered, False),
            "off-centered-left": (self.spacebar_off_centered, True),
            "off-centered-right": (self.spacebar_off_centered, False),
        }
        if position not in mapping:
            raise ValueError(f"spacebar_position must be one of {SPACEBAR_POSITIONS}, got {position!r}")
        return mapping[position]

    def replace(self, **kwargs) -> "TemplateSet":
        return replace(self, **kwargs)


@dataclass(frozen=True)
class Settings:
    """Generator settings combining dimensions, features, orientation and templates."""

    margin: float = float(DEFAULT_MARGIN)
    stabilizer_min_unit: float = DEFAULT_STABILIZER_MIN_UNIT
    spacebar_position: str = DEFAULT_SPACEBAR_POSITION
    stepped_key: str = DEFAULT_STEPPED_KEY
    single_mesh: bool = False
    fuse_f_row: bool = False
    orientation: OrientationConfig = field(default_factory=OrientationConfig)
    templates: TemplateSet = field(default_factory=TemplateSet.defaults)

    def __post_init__(self):
        if not isinstance(self.margin, (int, float)) or isinstance(self.margin, bool) or not np.isfinite(self.margin) or self.margin < 0:
            raise ValueError(f"margin must be a non-negative number, got {self.margin!r}")
        if not isinstance(self.stabilizer_min_unit, (int, float)) or isinstance(self.stabilizer_min_unit, bool) or not np.isfinite(self.stabilizer_min_unit) or self.stabilizer_min_unit <= 0:
            raise ValueError(f"stabilizer_min_unit must be a positive number, got {self.stabilizer_min_unit!r}")
        if self.spacebar_position not in SPACEBAR_POSITIONS:
            raise ValueError(f"spacebar_position must be one of {SPACEBAR_POSITIONS}, got {self.spacebar_position!r}")
        if self.stepped_key not in STEPPED_MODES:
            raise ValueError(f"stepped_key must be one of {STEPPED_MODES}, got {self.stepped_key!r}")
        if not isinstance(self.single_mesh, bool):
            raise ValueError(f"single_mesh must be a boolean, got {self.single_mesh!r}")
        if not isinstance(self.fuse_f_row, bool):
            raise ValueError(f"fuse_f_row must be a boolean, got {self.fuse_f_row!r}")
        if not isinstance(self.orientation, OrientationConfig):
            raise ValueError(f"orientation must be an OrientationConfig, got {self.orientation!r}")
        if not isinstance(self.templates, TemplateSet):
            raise ValueError(f"templates must be a TemplateSet, got {self.templates!r}")

    def replace(self, **kwargs) -> "Settings":
        return replace(self, **kwargs)


# ---------------------------------------------------------------------------
# Configuration file (TOML)
# ---------------------------------------------------------------------------
# Every key is optional; what is missing keeps its built-in default.  The
# names are the CLI option names with an underscore instead of a hyphen.  The
# input and output file (--json, --output) are not part of a config file: the
# same config is meant to serve different layouts.
CONFIG_KEYS = {                   # key -> kind of value
    "margin": "number",
    "stabilizer_min_unit": "number",
    "single_mesh": "boolean",
    "fuse_f_row": "boolean",
    "spacebar_position": "string",
    "stepped_key": "string",
}
CONFIG_ORIENTATION_KEYS = {
    "stab_rotation_horizontal": "integer",
    "stab_rotation_vertical": "integer",
    "stab_rotation_spacebar": "integer",
    "wide_caps_rotation": "integer",
    "global_transform": "boolean",
    "global_rotation": "integer",
    "global_mirror_x": "boolean",
}
CONFIG_TEMPLATE_KEYS = {key: "path" for key in (
    "socket", "wide_caps", "stabilizer", "spacebar_centered", "spacebar_off_centered")}
CONFIG_TABLES = {"orientation": CONFIG_ORIENTATION_KEYS, "templates": CONFIG_TEMPLATE_KEYS}
_CONFIG_KIND_TEXT = {"number": "a number", "integer": "an integer", "boolean": "true or false",
                     "string": "a string", "path": "a path (string)"}


def _toml_module():
    """The standard library TOML reader, imported only when a config file is used."""
    try:
        import tomllib
    except ImportError as exc:
        raise ValueError("config files need Python 3.11 or newer "
                         "(the standard library module 'tomllib' is not available)") from exc
    return tomllib


def _config_value(file_name, key, value, kind):
    """``value`` if it has the type ``kind`` (bool is not a number), else a ValueError."""
    if kind == "number":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif kind == "integer":
        valid = isinstance(value, int) and not isinstance(value, bool)
    elif kind == "boolean":
        valid = isinstance(value, bool)
    else:                                   # string and path
        valid = isinstance(value, str) and value != ""
    if not valid:
        raise ValueError(f"{file_name}: '{key}' must be {_CONFIG_KIND_TEXT[kind]}, "
                         f"got {value!r} ({type(value).__name__})")
    return value


def _config_table(file_name, name, table, keys):
    """The checked values of one table: unknown keys and wrong types are errors."""
    if not isinstance(table, dict):
        raise ValueError(f"{file_name}: '{name}' must be a table ([{name}]), "
                         f"got {table!r} ({type(table).__name__})")
    unknown = sorted(set(table) - set(keys))
    if unknown:
        raise ValueError(f"{file_name}: unknown key '{name}.{unknown[0]}' "
                         f"(allowed in [{name}]: {', '.join(keys)})")
    return {key: _config_value(file_name, f"{name}.{key}", value, keys[key])
            for key, value in table.items()}


def settings_from_mapping(raw: dict, config_path: Path, base: Settings | None = None) -> Settings:
    """``base`` (default: the built-in defaults) with the values of a parsed config applied.

    Relative template paths are relative to the folder of the config file.  Any
    unknown key, wrong type, invalid value or missing template file is a
    ValueError that names the file, the key and what is expected.
    """
    base = base or Settings()
    config_path = Path(config_path)
    name = config_path.name
    unknown = sorted(set(raw) - set(CONFIG_KEYS) - set(CONFIG_TABLES))
    if unknown:
        allowed = ", ".join([*CONFIG_KEYS, *(f"[{table}]" for table in CONFIG_TABLES)])
        raise ValueError(f"{name}: unknown key '{unknown[0]}' (allowed: {allowed})")

    changes = {key: _config_value(name, key, raw[key], kind)
               for key, kind in CONFIG_KEYS.items() if key in raw}
    orientation = _config_table(name, "orientation", raw.get("orientation", {}), CONFIG_ORIENTATION_KEYS)
    templates = _config_table(name, "templates", raw.get("templates", {}), CONFIG_TEMPLATE_KEYS)

    folder = config_path.resolve().parent
    for key, value in templates.items():
        path = folder / value                  # an absolute path stays as it is
        if not path.is_file():
            raise ValueError(f"{name}: 'templates.{key}' must name an existing template STL, "
                             f"file not found: {path}")
        templates[key] = path

    try:
        return replace(base, orientation=replace(base.orientation, **orientation),
                       templates=replace(base.templates, **templates), **changes)
    except ValueError as exc:
        raise ValueError(f"{name}: {exc}") from exc


def load_config(path: Path, base: Settings | None = None) -> Settings:
    """Read a TOML config file; see ``settings_from_mapping`` for the rules."""
    path = Path(path)
    tomllib = _toml_module()
    if not path.is_file():
        raise ValueError(f"config file not found: {path}")
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"{path.name}: not a valid TOML file: {exc}") from exc
    return settings_from_mapping(raw, path, base)


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


def plate_rotation_matrix(orientation: OrientationConfig):
    """Rotation part of the whole-plate transform, without the mirror.

    This is what the cutouts get: they turn with the plate but are never mirrored.
    """
    if not orientation.global_transform:
        return IDENTITY_MATRIX
    return rotation_matrix(orientation.global_rotation)


def apply_matrix(matrix, x, y):
    a, b, d, e = matrix
    return a * x + b * y, d * x + e * y


def _key_properties():
    """Properties of the next key as they are before a layout sets any of them."""
    return {"w": 1.0, "h": 1.0, "x2": 0.0, "y2": 0.0, "w2": 1.0, "h2": 1.0, "l": False}


def parse_kle(data):
    """Keys of a KLE Raw Data layout, positioned like the Keyboard Layout Editor does.

    The editor is the reference, not this generator:

    * ``rx`` or ``ry`` in a property object sets the current position to
      ``(rx, ry)``; the one that is not given keeps the value set last
      (initially 0).  ``x`` and ``y`` of the object are added afterwards.
      ``r`` alone does not move anything.  Every row starts at ``rx``.
    * ``r``, ``rx`` and ``ry`` are only allowed on the first item of a row
      (anything else raises ``ValueError``).
    * ``w``, ``h``, ``x2``, ``y2``, ``w2``, ``h2``, ``l`` and ``d`` apply to the
      NEXT key and are reset only after a key; several property objects in a row
      before one key add up.  ``w`` also sets ``w2`` and ``h`` also sets ``h2``;
      a ``w2`` / ``h2`` in the same object overrides that.
    * A decal (``"d": true``) is a legend without a key: it is not returned, but
      the position moves on by its width.
    """
    if not isinstance(data, list):
        raise ValueError(
            "Expected KLE Raw Data from Keyboard Layout Editor as a list of rows."
        )

    keys = []
    x = y = 0.0
    rx = ry = 0.0
    r = 0.0
    props = _key_properties()
    decal = False

    for row_index, row in enumerate(data):
        if row_index == 0 and isinstance(row, dict):
            continue
        if not isinstance(row, list):
            raise ValueError(
                "Expected KLE Raw Data from Keyboard Layout Editor; "
                f"row at index {row_index} must be a list."
            )
        for item_index, item in enumerate(row):
            if isinstance(item, dict):
                misplaced = [name for name in ("r", "rx", "ry") if name in item]
                if misplaced and item_index != 0:
                    raise ValueError(
                        f"KLE Raw Data: {', '.join(repr(n) for n in misplaced)} can only be used "
                        f"on the first key of a row (row at index {row_index}).")
                if "r" in item:
                    r = item["r"]
                if "rx" in item or "ry" in item:
                    rx = item.get("rx", rx)
                    ry = item.get("ry", ry)
                    x, y = rx, ry
                x += item.get("x", 0)
                y += item.get("y", 0)
                if "w" in item:
                    props["w"] = props["w2"] = item["w"]
                if "h" in item:
                    props["h"] = props["h2"] = item["h"]
                for name in ("x2", "y2", "w2", "h2"):
                    if name in item:
                        props[name] = item[name]
                if "l" in item:
                    props["l"] = bool(item["l"])                # stepped key (e.g. Caps Lock)
                if "d" in item:
                    decal = bool(item["d"])
                continue

            if not decal:
                keys.append({"label": item, **props, "r": r, "rx": rx, "ry": ry, "x": x, "y": y})
            x += props["w"]
            props = _key_properties()
            decal = False
        x = rx
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


def local_key_rectangles(k):
    """The rectangles a key is made of (the key and its second part), in key units."""
    rectangles = [box(0, 0, k["w"], k["h"]),
                  box(k["x2"], k["y2"], k["x2"] + k["w2"], k["y2"] + k["h2"])]
    if abs(k["r"]) > 1e-12:
        rectangles = [rotate(r, k["r"], origin=(k["rx"] - k["x"], k["ry"] - k["y"]),
                             use_radians=False) for r in rectangles]
    return rectangles


def switch_center(k, second=False):
    """Switch centre of a key in mm (KLE frame).

    By default the centre of the first rectangle (x, y, w, h).  With ``second``
    the centre of the second rectangle (x2, y2, w2, h2), which is the wider part
    of a stepped key.
    """
    if second:
        cx = k["x"] + k["x2"] + k["w2"] / 2.0
        cy = k["y"] + k["y2"] + k["h2"] / 2.0
    else:
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
    "stabilizer": (38.1, 19.05),
    "spacebar": (114.3015, 19.05),
    # Not defined yet: only the height (z) of this template is checked.
    "wide-caps": (None, None),
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
        if spec is None:
            continue
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


def gap_bridges(rectangles):
    """Rectangles that fill the space between keys that face each other.

    Two keys face each other if one lies to the right of (or above) the other
    and their extents overlap along the other axis.  The bridge spans the
    whole space between them, over the overlap.  This closes gaps of any width
    between keys of the same row or column, for example between Esc and F1.
    """
    boxes = [r.bounds for r in rectangles]
    bridges = []
    for i, (ax0, ay0, ax1, ay1) in enumerate(boxes):
        for j, (bx0, by0, bx1, by1) in enumerate(boxes):
            if i == j:
                continue
            low, high = max(ay0, by0), min(ay1, by1)
            if bx0 - ax1 > 1e-9 and high - low > 1e-9:        # B is right of A
                bridges.append(box(ax1, low, bx0, high))
            low, high = max(ax0, bx0), min(ax1, bx1)
            if by0 - ay1 > 1e-9 and high - low > 1e-9:        # B is above A
                bridges.append(box(low, ay1, high, by0))
    return bridges


TOP_ROW_TOLERANCE = 1e-9         # key units; keys whose KLE y differs by less are in one row
ROTATION_TOLERANCE = 1e-9        # degrees; a rotation below this counts as no rotation


def top_row_keys(keys):
    """The keys of the top row of a layout (the F-row of a 100% layout).

    These are all keys without rotation whose KLE ``y`` equals the smallest
    ``y`` among the unrotated keys.  Rotated keys are never part of the row, and
    a layout without any unrotated key has no top row (an empty list).  This
    works in the KLE frame, before the whole-plate transform, and needs no CAD.
    """
    unrotated = [k for k in keys if abs(k["r"]) < ROTATION_TOLERANCE]
    if not unrotated:
        return []
    top = min(k["y"] for k in unrotated)
    return [k for k in unrotated if abs(k["y"] - top) <= TOP_ROW_TOLERANCE]


def plate_footprint(keys, matrix, margin, single_mesh=False, fuse_top_row=False):
    """Outline of the plate: the keys grown by ``margin`` (before the shift to (0, 0)).

    With ``single_mesh`` the space between keys that face each other is filled
    first (``gap_bridges``); whatever is still separate or enclosed afterwards is
    joined by ``connect_footprint``.

    With ``fuse_top_row`` the same bridges are added, but only between the
    rectangles of the keys of the top row (``top_row_keys``), so that row becomes
    one strip and nothing else is connected to it.  ``single_mesh`` already
    connects everything, so ``fuse_top_row`` changes nothing then.
    """
    a, b, d, e = matrix

    def place(shape, k):
        shape = translate(shape, xoff=k["x"], yoff=k["y"])
        shape = scale(shape, xfact=UNIT, yfact=UNIT, origin=(0, 0))
        return affine_transform(shape, [a, b, d, e, 0, 0])

    shapes = [place(local_key_shape(k), k) for k in keys]
    if single_mesh:
        shapes += gap_bridges([place(r, k) for k in keys for r in local_key_rectangles(k)])
    elif fuse_top_row:
        shapes += gap_bridges([place(r, k) for k in top_row_keys(keys) for r in local_key_rectangles(k)])
    footprint = unary_union(shapes).buffer(margin, join_style=2)
    return connect_footprint(footprint) if single_mesh else footprint


def connect_footprint(footprint):
    """Return the plate outline as ONE polygon without voids.

    The gaps between separated parts are closed by a morphological closing
    (grow, then shrink, both with mitre joins) with the smallest radius that
    joins all parts: half of the longest link of the shortest tree through the
    parts.  Gaps and notches narrower than twice that radius are filled;
    everywhere else the outline stays exactly where it was.  Voids that are
    enclosed by the outline are filled as well.  The key cutouts are not part of
    the outline; they are cut out of the plate afterwards.
    """
    parts = polygons(footprint)
    closed = footprint
    if len(parts) > 1:
        linked, longest = {0}, 0.0
        while len(linked) < len(parts):
            distance, nearest = min((parts[i].distance(parts[j]), j)
                                    for i in linked for j in range(len(parts)) if j not in linked)
            longest = max(longest, distance)
            linked.add(nearest)
        # A hair more than half of the longest gap: parts that are exactly as far
        # apart as the longest link would only touch, and floating point noise
        # decides whether they merge.
        radius = longest / 2.0 * (1.0 + 1e-6)
        for _ in range(50):
            closed = footprint.buffer(radius, join_style=2).buffer(-radius, join_style=2)
            if closed.geom_type == "Polygon":
                break
            radius *= 1.0001
        else:
            raise RuntimeError("The plate outline could not be joined into one piece.")
    return Polygon(closed.exterior)


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
KIND_WIDE_CAPS = "wide-caps"


def classify_key(k, min_units=DEFAULT_STABILIZER_MIN_UNIT, stepped="standard"):
    """Return KIND_SPACEBAR, KIND_STABILIZED, KIND_WIDE_CAPS or KIND_NORMAL.

    A stepped key (``"l": true``) that would get a normal socket is a
    KIND_WIDE_CAPS key when ``stepped`` is ``"wide-caps"``.  Stabilized keys and
    the spacebar keep their cutouts whether they are stepped or not.
    """
    if is_spacebar_key(k):
        return KIND_SPACEBAR
    if is_stabilized_key(k, min_units):
        return KIND_STABILIZED
    if stepped == "wide-caps" and k.get("l", False):
        return KIND_WIDE_CAPS
    return KIND_NORMAL


def stabilizer_rotation(k, orientation: "OrientationConfig", min_units=DEFAULT_STABILIZER_MIN_UNIT, stepped="standard"):
    """Rotation (degrees, counter-clockwise, KLE frame) of a key's cutout.

    Returns ``None`` for keys with a normal switch socket.  Stabilized keys
    that are wider than tall count as horizontal, all others as vertical.  The
    wide-caps socket of a stepped key is turned by ``wide_caps_rotation``.
    """
    kind = classify_key(k, min_units, stepped)
    return rotation_for_kind(k, kind, orientation)


def rotation_for_kind(k, kind, orientation: "OrientationConfig"):
    """Return the cutout rotation for a previously classified key kind."""
    if kind == KIND_WIDE_CAPS:
        return orientation.wide_caps_rotation
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
    mirrored: list      # True where the cutout is the mirrored template (left off-centered spacebar only)
    centers: list       # switch centre per key (mm)
    footprint: object   # shapely (Multi)Polygon of the plate outline
    cavities: list      # one CAD solid per key, same order as ``keys``
    plate: object       # CAD solid with all cavities cut out
    templates: dict     # the templates that were used, by kind
    warnings: list      # problems found in the templates
    spacebar_path: Path
    matrix: tuple       # linear part of the whole-plate transform


def build_plate_model(kle_path: Path, settings: Settings) -> PlateModel:
    """Build the plate solid without exporting it.

    Transformation order (see ``OrientationConfig``): per-stabilizer rotation
    about its switch centre, then the whole-plate transform about the origin,
    then a shift so that the plate's bounding box (including margin) starts at
    (0, 0).  Rotations and the mirror are exact integer matrices applied to
    the 2D data (footprint, switch centres, cutout sections) before anything
    is extruded; no mirrored CAD solid is ever created.  The cutouts are only
    rotated, never mirrored, with one exception: the left off-centered spacebar
    is the right template mirrored (exact integer matrix in the template's own
    coordinates, applied before the rotation; ``PlateModel.mirrored`` says where).

    With ``settings.single_mesh`` the space between keys that face each other
    and voids enclosed by the outline are filled, so the plate is one connected
    piece without gaps (see ``plate_footprint``); otherwise the plate follows
    the keys and falls apart where they are far from each other.  With
    ``settings.fuse_f_row`` only the top row of the layout is joined into one
    strip (``top_row_keys``); it has no effect together with ``single_mesh``.

    A stepped key (KLE ``"l": true``) gets, depending on ``settings.stepped_key``,
    the normal socket at the centre of its first rectangle (``"standard"``, w) or
    the wide-caps socket at the centre of its second rectangle (``"wide-caps"``, w2).
    The plate outline covers both rectangles in either case.  The wide-caps
    template is only read if a stepped key needs it.
    """
    orientation = settings.orientation
    data = json.loads(kle_path.read_text(encoding="utf-8"))
    keys = parse_kle(data)
    if not keys:
        raise ValueError("KLE JSON contains no keys.")

    spacebar_path, spacebar_mirrored = settings.templates.spacebar_for(settings.spacebar_position)
    template_paths = {
        "socket": settings.templates.socket,
        "stabilizer": settings.templates.stabilizer,
        "spacebar": spacebar_path,
        "wide-caps": settings.templates.wide_caps,
    }
    templates = {}

    gm = global_matrix(orientation)
    pm = plate_rotation_matrix(orientation)
    footprint = plate_footprint(keys, gm, settings.margin, settings.single_mesh, settings.fuse_f_row)
    minx, miny = footprint.bounds[0], footprint.bounds[1]
    footprint = translate(footprint, xoff=-minx, yoff=-miny)

    kinds = [classify_key(k, settings.stabilizer_min_unit, settings.stepped_key) for k in keys]
    rotations = [rotation_for_kind(k, kind, orientation) for k, kind in zip(keys, kinds)]
    # The one exception to "cutouts are only turned": the left off-centered
    # spacebar is the right template mirrored (see below).  Nothing else is.
    mirrored = [spacebar_mirrored and kind == KIND_SPACEBAR for kind in kinds]
    centers = []
    for k, kind in zip(keys, kinds):
        cx, cy = apply_matrix(gm, *switch_center(k, second=(kind == KIND_WIDE_CAPS)))
        centers.append((cx - minx, cy - miny))

    plate = extruded_footprint(footprint, PLATE_Z_MIN, PLATE_Z_MAX - PLATE_Z_MIN)

    # Socket, stabilizer and spacebar cutouts are built by the same code.  The
    # templates are used exactly as supplied (nothing is scaled); the spacebar
    # templates keep their internal switch position (centered/off-centered).
    cavities, cutters = [], {}
    for kind, rotation, mirror, (cx, cy) in zip(kinds, rotations, mirrored, centers):
        template_kind = {KIND_NORMAL: "socket", KIND_STABILIZED: "stabilizer",
                         KIND_SPACEBAR: "spacebar", KIND_WIDE_CAPS: "wide-caps"}[kind]
        if template_kind not in templates:
            templates[template_kind] = load_template(template_paths[template_kind], template_kind)
        # Step 1 (rotation about the switch centre), then step 2 (rotation of the
        # whole plate).  The mirror of the whole-plate transform never reaches a cutout.
        m = pm if rotation is None else matrix_multiply(pm, rotation_matrix(rotation))
        if mirror:
            # Left off-centered spacebar: mirror the template in ITS OWN coordinate
            # system, i.e. before the rotation.  The old left template file is the
            # right one mirrored at the template's Y axis (x -> -x); only "mirror first,
            # then rotate" gives exactly that file for every stab_rotation_spacebar and
            # global_rotation.  Mirroring after the rotation would be a different mirror
            # axis for 90 and 270 degrees.  The mirror is an exact integer matrix on the
            # 2D contour (template_cutter reverses the ring order); no mirrored CAD solid.
            m = matrix_multiply(m, MIRROR_X_MATRIX)
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

    return PlateModel(keys=keys, kinds=kinds, rotations=rotations, mirrored=mirrored, centers=centers,
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


def generate(kle_path: Path, settings: Settings, output: Path = Path(DEFAULT_OUTPUT),
             config_path: Path | None = None):
    """Build the plate and export it.  ``config_path`` is only reported in the header."""
    model = build_plate_model(kle_path, settings)
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
    print(f"Config:          {config_path if config_path is not None else 'none'}")
    print(f"KLE:             {kle_path}")
    print(f"Socket:          {settings.templates.socket}")
    print(f"Stabilizer:      {settings.templates.stabilizer}")
    mirrored_note = ", mirrored" if any(model.mirrored) else ""
    print(f"Spacebar:        {model.spacebar_path} ({settings.spacebar_position}{mirrored_note})")
    print(f"Output:          {output}")
    print(f"Keys:            {len(keys)}")
    print(f"Stabilizer keys: {model.kinds.count(KIND_STABILIZED)}")
    print(f"Spacebar keys:   {model.kinds.count(KIND_SPACEBAR)}")
    print(f"Plate thickness: {PLATE_Z_MAX - PLATE_Z_MIN:.4f} mm")
    parts = len(polygons(model.footprint))
    if settings.single_mesh:
        print(f"Plate shape:     one connected mesh (--single-mesh), {parts} part")
        if settings.fuse_f_row:
            print("Note:            --fuse-f-row has no effect with --single-mesh")
    elif settings.fuse_f_row:
        row = len(top_row_keys(keys))
        fused = f"top row fused ({row} keys)" if row else "--fuse-f-row has no effect (no unrotated keys)"
        print(f"Plate shape:     {parts} part(s), separated where the keys are far apart; {fused}")
    else:
        print(f"Plate shape:     {parts} part(s), separated where the keys are far apart")
    for kind, template in model.templates.items():
        print(f"Template {kind + ':':11s} {template.path.name}, {len(template.layers)} layers, "
              f"{template.vertex_count} contour vertices")
    print("Caps Lock:       normal switch cutout")
    stepped = sum(1 for k in keys if k.get("l", False))
    if stepped and settings.stepped_key == "wide-caps":
        print(f"Stepped keys:    {stepped}, wide-caps socket at the centre of w2 "
              f"(rotation {settings.orientation.wide_caps_rotation} deg)")
    elif stepped:
        print(f"Stepped keys:    {stepped}, standard socket at the centre of w")
    print(f"Stab rotation:   horizontal {settings.orientation.stab_rotation_horizontal} deg, "
          f"vertical {settings.orientation.stab_rotation_vertical} deg, "
          f"spacebar {settings.orientation.stab_rotation_spacebar} deg")
    if settings.orientation.global_transform:
        mirror = " + mirror X" if settings.orientation.global_mirror_x else ""
        print(f"Plate transform: rotate {settings.orientation.global_rotation} deg{mirror}, "
              f"matrix {model.matrix}")
    else:
        print("Plate transform: none (--no-global-transform)")
    report_template_warnings(model.warnings)
    mesh, problems = check_exported_stl(output, expected_bounds=expected_bounds)
    report_stl_check(mesh, problems, output)
    print("\nDone." if not (problems or model.warnings) else "\nDone, with warnings.")


def build_parser():
    """The command line parser.

    Options that a config file can also set have ``default=None``: that is how
    ``settings_from_args`` tells "not given" from "given", so that the order is
    command line > config file > built-in default.  The help texts name the
    built-in defaults.
    """
    defaults = Settings()
    orientation = defaults.orientation
    parser = argparse.ArgumentParser(description="Generate a clean Fat Plate STL from KLE JSON.")
    parser.add_argument("--version", action="version", version=f"Fat Plate Generator {VERSION}")
    parser.add_argument("--config", type=Path, default=None,
                        help="TOML config file with the settings below (see fat_plate_config.example.toml); "
                             "options on the command line override it")
    parser.add_argument("--json", type=Path, default=SCRIPT_DIR / DEFAULT_JSON)
    parser.add_argument("--socket", type=Path, default=None,
                        help=f"socket template (default: {DEFAULT_SOCKET})")
    parser.add_argument("--socket-wide-caps", type=Path, default=None,
                        help="socket template for stepped keys with --stepped-key wide-caps "
                             f"(default: {DEFAULT_SOCKET_WIDE_CAPS})")
    parser.add_argument("--stabilizer", type=Path, default=None,
                        help=f"stabilizer template (default: {DEFAULT_STABILIZER})")
    parser.add_argument("--spacebar-centered", type=Path, default=None,
                        help=f"centered spacebar template (default: {DEFAULT_SPACEBAR_CENTERED})")
    parser.add_argument("--spacebar-off-centered", type=Path, default=None,
                        help="off-centered spacebar template, the right one as designed; "
                             "off-centered-left uses it mirrored "
                             f"(default: {DEFAULT_SPACEBAR_OFF_CENTERED})")
    parser.add_argument("--spacebar-position", choices=SPACEBAR_POSITIONS, default=None,
                        help="Spacebar switch position, seen from above with the typist at the "
                             "bottom: centered, off-centered-left or off-centered-right "
                             f"(default: {defaults.spacebar_position}).")
    parser.add_argument("--output", type=Path, default=SCRIPT_DIR / DEFAULT_OUTPUT)
    parser.add_argument("--margin", type=float, default=None,
                        help=f"margin around the keys in mm (default: {defaults.margin})")
    parser.add_argument("--stabilizer-min-unit", type=float, default=None,
                        help="minimum key width or height for a stabilizer cutout "
                             f"(default: {defaults.stabilizer_min_unit})")
    parser.add_argument("--stab-rotation-horizontal", type=int, choices=ROTATION_CHOICES, default=None,
                        help="rotation of horizontal stabilizer cutouts in degrees, counter-clockwise "
                             f"(default: {orientation.stab_rotation_horizontal})")
    parser.add_argument("--stab-rotation-vertical", type=int, choices=ROTATION_CHOICES, default=None,
                        help="rotation of vertical stabilizer cutouts in degrees "
                             f"(default: {orientation.stab_rotation_vertical})")
    parser.add_argument("--stab-rotation-spacebar", type=int, choices=ROTATION_CHOICES, default=None,
                        help=f"rotation of the spacebar cutout in degrees (default: {orientation.stab_rotation_spacebar})")
    parser.add_argument("--stepped-key", choices=STEPPED_MODES, default=None,
                        help="socket of a stepped key (KLE \"l\": true, for example a stepped Caps "
                             "Lock): standard = the normal socket at the centre of w; wide-caps = "
                             f"the wide-caps socket at the centre of w2 (default: {defaults.stepped_key})")
    parser.add_argument("--wide-caps-rotation", type=int, choices=ROTATION_CHOICES, default=None,
                        help=f"rotation of the wide-caps socket in degrees (default: {orientation.wide_caps_rotation})")
    parser.add_argument("--single-mesh", action=argparse.BooleanOptionalAction, default=None,
                        help="generate the plate as one connected mesh without gaps: the space "
                             "between keys that face each other is filled and enclosed voids are "
                             "closed; without it the plate falls apart where the keys are far apart "
                             "(--no-single-mesh overrides a config file; default: off)")
    parser.add_argument("--fuse-f-row", action=argparse.BooleanOptionalAction, default=None,
                        help="join the top row of the layout (the F-row of a full-size layout: Esc, F1-F12, "
                             "PrtSc, Scroll Lock, Pause Break) into one strip of plate; only that row "
                             "is joined, not the main block; it has no effect together with "
                             "--single-mesh (--no-fuse-f-row overrides a config file; default: off)")
    parser.add_argument("--global-transform", action=argparse.BooleanOptionalAction, default=None,
                        help="apply the whole-plate transform (KLE y flip), or skip it with "
                             "--no-global-transform, mainly for comparison with older output "
                             f"(default: {'on' if orientation.global_transform else 'off'})")
    parser.add_argument("--global-rotation", type=int, choices=ROTATION_CHOICES, default=None,
                        help="rotation of the whole plate in degrees, before the mirror "
                             f"(default: {orientation.global_rotation})")
    parser.add_argument("--global-mirror-x", action=argparse.BooleanOptionalAction, default=None,
                        help="mirror the plate along X after the rotation; with the default rotation "
                             f"this is the KLE y flip (default: {'on' if orientation.global_mirror_x else 'off'})")
    return parser


def settings_from_args(args: argparse.Namespace) -> Settings:
    """Settings from the parsed command line: command line > config file > default."""
    settings = load_config(args.config) if args.config is not None else Settings()

    def given(**options):
        return {key: value for key, value in options.items() if value is not None}

    orientation = given(
        stab_rotation_horizontal=args.stab_rotation_horizontal,
        stab_rotation_vertical=args.stab_rotation_vertical,
        stab_rotation_spacebar=args.stab_rotation_spacebar,
        wide_caps_rotation=args.wide_caps_rotation,
        global_transform=args.global_transform,
        global_rotation=args.global_rotation,
        global_mirror_x=args.global_mirror_x)
    templates = given(
        socket=args.socket,
        wide_caps=args.socket_wide_caps,
        stabilizer=args.stabilizer,
        spacebar_centered=args.spacebar_centered,
        spacebar_off_centered=args.spacebar_off_centered)
    return replace(
        settings,
        orientation=replace(settings.orientation, **orientation),
        templates=replace(settings.templates, **templates),
        **given(margin=args.margin,
                stabilizer_min_unit=args.stabilizer_min_unit,
                spacebar_position=args.spacebar_position,
                stepped_key=args.stepped_key,
                single_mesh=args.single_mesh,
                fuse_f_row=args.fuse_f_row))


def main():
    args = build_parser().parse_args()
    try:
        settings = settings_from_args(args)
        generate(args.json, settings, output=args.output, config_path=args.config)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()

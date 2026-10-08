"""User-editable orientation settings for the Fat Plate Generator.

All angles are degrees around the local Z axis.
Mirroring is expressed explicitly per axis so the configuration is easy to
read and cannot be confused with a global CAD workplane name.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Orientation:
    """Orientation applied to a shape around its own local origin."""

    rotation_z: float = 0.0
    mirror_x: bool = False
    mirror_y: bool = False


# Finished plate orientation.
# mirror_x=True means X -> -X (mirror in the YZ plane).
PLATE_ORIENTATION = Orientation(
    rotation_z=0.0,
    mirror_x=False,
    mirror_y=False,
)


# Default orientation for stabilizer templates.
DEFAULT_STABILIZER_ORIENTATION = Orientation()


# Per-label overrides. Keys not listed here use the default orientation.
STABILIZER_ORIENTATIONS = {
    "Enter": Orientation(rotation_z=90.0),
    "NumEnter": Orientation(rotation_z=90.0),
    "Num+": Orientation(rotation_z=0.0),
}


# Spacebar templates have independent orientations.
SPACEBAR_ORIENTATIONS = {
    "centered": Orientation(),
    "off-centered": Orientation(),
}


# Optional 180° flips for horizontal/vertical stabilizers.
FLIP_HORIZONTAL_STABILIZERS = False
FLIP_VERTICAL_STABILIZERS = False

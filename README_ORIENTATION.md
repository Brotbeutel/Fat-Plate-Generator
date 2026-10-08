# Orientation configuration

All orientation settings live in `orientation_config.py`.

The generator deliberately keeps these settings separate from the geometry
code. If a supplied STL is rotated or mirrored differently, edit the config
instead of changing `fat_plate_generator.py`.

## Orientation values

```python
Orientation(rotation_z=90.0)
```

rotates the geometry 90 degrees around its local Z axis.

Mirroring is configured per axis:

- `mirror_x=True` — mirror X, equivalent to a mirror in the YZ plane
- `mirror_y=True` — mirror Y, equivalent to a mirror in the XZ plane

Examples:

```python
Orientation(rotation_z=180.0)
Orientation(mirror_y=True)
Orientation(rotation_z=90.0, mirror_x=True)
```

## Finished plate

`PLATE_ORIENTATION` controls the transformation applied to the complete
finished plate. The current default is:

```python
PLATE_ORIENTATION = Orientation(
    rotation_z=0.0,
    mirror_x=True,
    mirror_y=False,
)
```

## Normal stabilizers

`DEFAULT_STABILIZER_ORIENTATION` applies to every stabilizer whose label does
not have an explicit entry in `STABILIZER_ORIENTATIONS`.

The current special cases are:

```python
STABILIZER_ORIENTATIONS = {
    "Enter": Orientation(rotation_z=90.0),
    "NumEnter": Orientation(rotation_z=90.0),
    "Num+": Orientation(rotation_z=90.0),
}
```

You can add or change individual labels, for example:

```python
STABILIZER_ORIENTATIONS = {
    "Enter": Orientation(rotation_z=90.0),
    "NumEnter": Orientation(rotation_z=90.0),
    "Num+": Orientation(rotation_z=90.0),
    "Backspace": Orientation(rotation_z=180.0),
    "Shift": Orientation(mirror_y=True),
}
```

The key's KLE label is used for the lookup.

## Spacebar

Centered and off-centered Spacebar templates have independent settings:

```python
SPACEBAR_ORIENTATIONS = {
    "centered": Orientation(),
    "off-centered": Orientation(),
}
```

## Horizontal and vertical flips

The existing horizontal/vertical stabilizer flip options remain available.
They add 180 degrees to the configured stabilizer rotation.

Defaults can be changed in `orientation_config.py`:

```python
FLIP_HORIZONTAL_STABILIZERS = False
FLIP_VERTICAL_STABILIZERS = False
```

The CLI flags override these defaults for a single run.

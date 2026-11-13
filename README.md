# Fat Plate Generator V.0.25

The Fat Plate Generator creates a 3D-printable keyboard "fat" plate as an STL from a **KLE Raw Data JSON**.

You can export your keyboard layout from [https://www.keyboard-layout-editor.com/]() and use Fat Plate Generator to generate a keyboard switch plate for 3D printing.

This is still a WIP, but with some 3D editing (for example Blender) you can already make use of it.

## !! Disclaimer !!

This is not a finished product!

It has not yet been tested, if the generated plate fits a real keyboard and switches in 3D-printed form. 
Spacebar stabilizer cutouts are now supported with centered and off-centered (left or right) switch-position options, which is needed for a classic Cherry G80-3000. The left off-centered cutout is the right template mirrored.

If a template STL is not exact (for example one you designed yourself), the generator prints warnings (see *Common Errors*); the STL is written anyway and can be inspected.

## Content

- `fat_plate_generator.py` – the application
- `fat_plate_config.example.toml` – example configuration file with every setting at its default (see *Configuration File*)
- `requirements.txt` – required Python packages
- `requirements-dev.txt` – additional packages for the preview tool and the tests
- `stl-templates/switch_socket.stl` – template for standard switch sockets
- `stl-templates/switch_socket_wide-caps.stl` – template for stepped keys such as a stepped Caps Lock (see *Stepped Keys*)
- `stl-templates/stabilizer_2-00u.stl` – template for standard stabilized keys (2u to under 3u)
- `stl-templates/stabilizer_3-00u.stl` – template for 3u stabilized keys
- `stl-templates/stabilizer_6-00u_centered.stl` – 6u centered spacebar template
- `stl-templates/stabilizer_6-00u_off-center.stl` – 6u off-centered spacebar template
- `stl-templates/stabilizer_6-25u_centered.stl` – centered 6.25u spacebar template
- `stl-templates/stabilizer_6-25u_off-center.stl` – off-centered 6.25u spacebar template (the left position is this template mirrored)
- `stl-templates/stabilizer_7-00u_centered.stl` – centered 7u spacebar template
- `kle-jsons/keyboard-layout.json` – default example layout
- `kle-jsons/` – more example layouts (40%, 100% ISO and ANSI)
- `fat_plate_export_example.stl` – example output
- `tools/preview.py` – top-view preview of a generated STL
- `tests/` – automated tests (`python -m pytest`)
- `docs/` – preview images
- `blender-files/` – Blender sources of the template STLs
- `AGENTS.md`, `ROADMAP.md`, `CHANGELOG.md` – project rules, plans and change history
- `README.md` – this guide

---

# 1. Prerequisites

You need Windows and Python.

## Installing Python

1. Open https://www.python.org/downloads/
2. Download a current Python 3 version.
3. Run the installer.
4. In the first window, make sure to check **Add python.exe to PATH**.
5. Click **Install Now**.

Afterward, reopen PowerShell and test it:

```powershell
python --version
```

If e.g. `Python 3.13.x` appears, everything is set up correctly.

## Blender To Edit 3D-Files

Download Blender at: https://www.blender.org/download/ 

(Only, if you want to edit the source 3D-files)

---

# 2. Getting the Program

Download the repository from GitHub (green **Code** button, then **Download ZIP**) and extract it, or clone it:

```powershell
git clone https://github.com/Brotbeutel/Fat-Plate-Generator.git
```

For example to:

```text
C:\GitHub\Fat-Plate-Generator
```

The folder should look roughly like this:

```text
Fat-Plate-Generator
|
├── kle-jsons
│   ├── keyboard-layout.json
│   ├── keyboard-layout_040-percent_jd40.json
    ├── keyboard-layout_100-percent_ansi_104-keys.json
    ├── keyboard-layout_100-percent-iso-105-keys.json
    ├── keyboard-layout_100-percent-iso-105-keys_g80-3000.json
    ├── keyboard-layout_100-percent-iso-105-keys_stepped-capslock-.json
    ├── keyboard-layout_100-percent-iso-105-keys_stepped-capslock_g80-1800.json
    ├── keyboard-layout_numpad_21-keys_stars21.json
│   └── test_stepped-capslock.json
├── stl-templates
│   ├── switch_socket.stl
│   ├── stabilizer_2-00u.stl
│   ├── stabilizer_3-00u.stl
│   ├── stabilizer_6-00u_centered.stl
│   ├── stabilizer_6-00u_off-center.stl
│   ├── stabilizer_6-25u_centered.stl
│   ├── stabilizer_6-25u_off-center.stl
│   ├── stabilizer_7-00u_centered.stl
│   └── switch_socket_wide-caps.stl
├── fat_plate_generator.py
├── requirements.txt
└── README.md
```

---

# 3. Opening PowerShell in the Program Folder

Open the folder in File Explorer.

Click on the address bar, type:

```text
powershell
```

and press Enter.

Test with:

```powershell
dir
```

You should see `fat_plate_generator.py` and `requirements.txt`.

---

# 4. Creating a Virtual Python Environment

Execute once:

```powershell
python -m venv .venv
```

This creates the `.venv` folder.

---

# 5. Activating the Virtual Environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If it works, the command prompt will start with:

```text
(.venv) PS C:\...
```

## If PowerShell Blocks Activation

Execute once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Confirm with `Y` (or `J` depending on system language) and activate again:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

# 6. Installing Required Packages

As long as `(.venv)` is displayed:

```powershell
python -m pip install -r requirements.txt
```

Wait until the command completes without error messages.

You do not need to install the packages individually.

A notice such as `A new release of pip is available` can be ignored. It only says that a newer pip exists; pip itself is not part of `requirements.txt`. To update it anyway, run `python -m pip install --upgrade pip`.

---

# 7. Running the First Test

An example is included in the package:

```text
kle-jsons/keyboard-layout.json
```

Simply run it with:

```powershell
python .\fat_plate_generator.py
```

The generator automatically uses:

```text
kle-jsons/keyboard-layout.json
stl-templates/switch_socket.stl
stl-templates/stabilizer_2-00u.stl
stl-templates/stabilizer_6-25u_centered.stl
```

and generates:

```text
fat_plate_export.stl
```

You can then open this STL in Blender, Fusion 360, PrusaSlicer, OrcaSlicer, Cura, etc.

---

# 8. Using Your Own KLE Layout

Create your keyboard at:

[https://www.keyboard-layout-editor.com/]()

Export the **Raw Data** as JSON.

Assuming your file is named:

```text
my_keyboard.json
```

and is located in the generator folder.

Then run:

```powershell
python .\fat_plate_generator.py --json my_keyboard.json --output my_keyboard.stl
```

Important: Use the KLE **Raw Data JSON**, not another JSON export format. A `name` and `author` metadata object at the beginning of the Raw Data is allowed and ignored. Other JSON formats are rejected.

The parser follows the Keyboard Layout Editor, so the plate has the keys where the editor shows them: `rx` or `ry` set the position of the next key (the one that is not given keeps its last value), a decal (`"d": true`) is only a legend and not a key (it takes its space, but gets no cutout), and `r`, `rx` and `ry` are only allowed on the first item of a row (anywhere else the generator stops with an error that names the row).

---

# 9. Using Custom STL Files

You can explicitly specify the socket and stabilizer files:

```powershell
python .\fat_plate_generator.py --json my_keyboard.json --socket stl-templates/switch_socket.stl --stabilizer-2u stl-templates/stabilizer_2-00u.stl --output my_keyboard.stl
```

This explicitly defines which files are being used.

---

# 10. What Are the STL Templates?

A template is a plate cell with the cutout in it, centered on the switch. The generator reads the **contour of the cutout** from it and builds the cutter for every key from that contour. Socket, stabilizer and spacebar are read and built in exactly the same way.

## `stl-templates/switch_socket.stl`

This file defines the cutout for a standard key or switch.

## `stl-templates/switch_socket_wide-caps.stl`

This file defines the cutout for a stepped key (for example a stepped Caps Lock). It is only used with `--stepped-key wide-caps` (see *Stepped Keys*), and only if the layout has a stepped key. Like the other templates it is centered on the switch, and it is turned like a stabilizer (`--wide-caps-rotation`), never mirrored.

## `stl-templates/stabilizer_2-00u.stl`

This file contains the **switch socket + stabilizer cutout**.

## `stl-templates/stabilizer_3-00u.stl`

This file contains the **switch socket + stabilizer cutout** for 3u keys.

## Key widths and templates

The stabilizer template is selected by the key width, not by its label. A
spacebar is any key with `w >= 6.0`, including a labelled key. The available
widths are:

| Key width | Template | Status |
| --- | --- | --- |
| 2u to under 3u | `stabilizer_2-00u.stl` | available |
| 3u | `stabilizer_3-00u.stl` | available |
| 6u | `stabilizer_6-00u_centered.stl` / `stabilizer_6-00u_off-center.stl` | available |
| 6.25u, 6.5u | `stabilizer_6-25u_centered.stl` / `stabilizer_6-25u_off-center.stl` | available |
| 7u, 8u | `stabilizer_7-00u_centered.stl` | available |

Off-center positions are supported only for 6u, 6.25u and 6.5u. The left
position is the exact mirror of the supplied right template. Widths such as
3.25u, 4u, 5u, 6.1u, 6.75u, 7.25u and 9u, and vertical keys with `h >= 6`,
are rejected as unsupported.

## `stl-templates/stabilizer_6-25u_centered.stl` and `stl-templates/stabilizer_6-25u_off-center.stl`

These files define the dedicated 6.25u spacebar cutout. The two templates contain the same overall spacebar geometry, but place the switch position differently: centered, or left of the center, seen from above with the typist at the bottom of the plate.

There is only **one** off-centered template, the right one, as designed. The left position is created from it by an exact mirror (x → −x in the template's own coordinates, before the stabilizer rotation, so it works for every `--stab-rotation-spacebar` and plate rotation).

Select the desired variant with:

```powershell
--spacebar-position centered
```

or:

```powershell
--spacebar-position off-centered-left
```

or:

```powershell
--spacebar-position off-centered-right
```

The default is **centered**. The supplied templates are used exactly as they are; nothing is stretched, scaled or rounded. The only change is that exact mirror for `off-centered-left`.

### Caps Lock

Caps Lock is intentionally **not** treated as a stabilized key. It always receives the normal `stl-templates/switch_socket.stl` switch cutout, regardless of its width.

## Fixed bounding boxes

The outer size of every template is fixed. If you design a new template (for example in Blender), build it inside this box and do not change the box:

| Template                | Size X × Y                                 | Height Z      |
| ----------------------- | ------------------------------------------ | ------------- |
| socket                  | 19.05 × 19.05 mm                           | −5.0 … 1.2 mm |
| stabilizer-2u           | 38.1 × 19.05 mm                            | −5.0 … 1.2 mm |
| stabilizer-3u           | not fixed yet (only the height is checked); measured 52.3993 × 19.05 mm | −5.0 … 1.2 mm |
| spacebar-6-25u          | 114.3015 × 19.05 mm                        | −5.0 … 1.2 mm |
| spacebar-6u             | not fixed yet (only the height is checked); measured 109.3004 × 19.05 mm | −5.0 … 1.2 mm |
| spacebar-7u             | not fixed yet (only the height is checked); measured 128.6008 × 19.05 mm | −5.0 … 1.2 mm |
| wide-caps socket        | not fixed yet (only the height is checked) | −5.0 … 1.2 mm |

The plate is exactly 6.2 mm thick (z from −5.0 to 1.2); this comes from the fixed values, not from a template. 19.05 mm is the pitch of a 1u key; the lengths of the stabilizer and spacebar box are the sizes of the current templates.

The box is only **checked**. If a template deviates by more than 0.001 mm, the generator prints a warning with the deviation. The geometry is never stretched, cut or moved to fit the box.

## How a template must be built

- The switch center is the origin (0, 0).
- The cutout is described by closed contours. A contour must not lie inside another contour.
- Between two heights a wall is either vertical or one straight slope. Slopes are kept exactly (see below).
- The mesh should be closed. Defects are reported as warnings.
- Everything outside the cutout (the outer rim of the cell) is ignored.

## How the generator reads a template

The template is cut at every horizontal plane of the mesh. Between two planes each contour is turned into a ruled loft from its lower to its upper outline. Vertical walls therefore stay vertical and **slanted walls stay slanted**, for the socket as well as for the stabilizers. Every contour of every layer is kept, nothing is left out silently, and nothing is rounded or snapped. The only tolerances are:

- Heights closer than 0.000001 mm belong to the same plane (the STL stores float32).
- Contour points closer than 0.000000001 mm are the same point.
- A point in the middle of a flat wall is only a leftover of the triangulation. It is dropped if it lies within 0.00005 mm (50 nm) of the straight wall. For a layer with a defective mesh this is raised in steps up to 0.005 mm, and the generator says so in a warning.
- A layer whose walls lean or twist by less than 0.005 mm and cannot be lofted because of that is built as a straight prism from its section at half height, and the generator says so in a warning. A real slope is never straightened; that is an error.
- The bounding box check described above (warning only).

---

# 11. Important Options

### JSON File

```powershell
--json my_layout.json
```

### Config File

```powershell
--config my_config.toml
```

Reads all settings from a TOML file (see *Configuration File* below). Options on the command line override the file. Without `--config` no config file is used.

### Socket

```powershell
--socket stl-templates/switch_socket.stl
```

### Stabilizer

```powershell
--stabilizer-2u stl-templates/stabilizer_2-00u.stl
--stabilizer-3u stl-templates/stabilizer_3-00u.stl
```

`--stabilizer-2u` is the template for keys from 2u to under 3u, `--stabilizer-3u` the one for 3u keys (see *Key widths and templates*).

### Spacebar switch position

Default: `centered`

```powershell
--spacebar-position centered
```

or:

```powershell
--spacebar-position off-centered-left
```

or:

```powershell
--spacebar-position off-centered-right
```

`centered` selects the centered template for the detected width; `off-centered-right` selects its right-hand template, and `off-centered-left` uses the same file mirrored. The switch position is seen from above with the typist at the bottom of the plate. The five spacebar template paths are configurable only in `[templates]`.

### Output

```powershell
--output my_plate.stl
```

### Version

```powershell
--version
```

### Margin

Default: `1 mm`

```powershell
--margin 2
```

### Minimum Size for Stabilizer Keys

Default: `2u`

The stabilizer applies from `2u` in either the key's width or height. Keys with both dimensions below `2u` receive a normal switch socket. This means 1.75u keys (for example Shift and Enter in some 40% layouts) get a normal socket by default. To give them a stabilizer cutout instead, lower the threshold:

```powershell
--stabilizer-min-unit 1.75
```

### Stabilizer Orientation

Every cutout is its template as designed, turned about its switch center into a **fixed base orientation**. That orientation was set after checking exported plates; it is built into the generator (`TEMPLATE_BASE_ROTATION`, `CUTOUT_FRAME_ROTATION` and `KLE_TO_CAD_MATRIX` in `fat_plate_generator.py`) and is what you get with all options at their defaults. The options below turn a key class **additionally**, in 90° steps, counter-clockwise seen from above, around the switch center. Horizontal keys, vertical keys (for example numpad `+` / `Enter`, ISO Enter) and the spacebar are set separately:

```powershell
--stab-rotation-horizontal 0
--stab-rotation-vertical 0
--stab-rotation-spacebar 0
```

Allowed values are `0`, `90`, `180` and `270`. The values above are the defaults: `0` means no additional rotation. If a stabilizer faces the wrong way in your plate, change only the option of that key class; for example `--stab-rotation-horizontal 180` turns every horizontal stabilizer by another 180°.

The cutouts are only turned, **never mirrored**: every cutout is the template as designed. There are two exceptions: the left off-centered spacebar (`--spacebar-position off-centered-left`), which is the right template mirrored (see *Spacebar switch position*), and the stabilizers if you switch on the mirror options (see *Stabilizer Mirror*).

#### Converting old calls and config files

Before, these options gave the rotation as an absolute value, and the old defaults were 180 (horizontal), 90 (vertical) and 180 (spacebar, wide-caps). Now they are an addition to that base orientation. For a call or config file that used the old default plate transform (`--global-rotation 180` with `--global-mirror-x`), the new value is the old value minus the base rotation of the class, modulo 360:

| old value | horizontal, spacebar, wide-caps (old − 180) | vertical (old − 90) |
| --------- | ------------------------------------------- | ------------------- |
| 0         | 180                                         | 270                 |
| 90        | 270                                         | 0                   |
| 180       | 0                                           | 90                  |
| 270       | 90                                          | 180                 |

The old default call is therefore the new default call: all options `0`. The old plate transform `--global-rotation 180` with `--global-mirror-x` is the new default (`--global-rotation 0`, no `--global-mirror-x`). For other old `--global-rotation` values there is no conversion: the cutouts now turn consistently with the plate, so check such a plate with `tools/preview.py`.

### Stabilizer Mirror

The stabilizer cutouts (the `stabilizer_2-00u.stl` and `stabilizer_3-00u.stl` templates) can be mirrored. Horizontal keys (length along X, for example Shift, Backspace, other 2u and 3u keys) and vertical keys (turned by 90°: ISO Enter, numpad `+` and `Enter`) are set **separately**:

```powershell
--stab-mirror-horizontal
--stab-mirror-vertical
```

`--no-stab-mirror-horizontal` and `--no-stab-mirror-vertical` switch them off again, for example if a config file has turned them on. Both are off by default; then nothing changes. In a config file these are the keys `stab_mirror_horizontal` and `stab_mirror_vertical` in `[orientation]` (`true` or `false`).

**Which keys:** only stabilized keys. A key counts as horizontal if it is wider than tall (`w > h`), every other stabilized key as vertical; this is the same rule as for the rotation. The spacebar (it has `--spacebar-position`), the wide-caps socket and the normal sockets are never mirrored by these options.

**Axis:** the mirror is made in the coordinate system of the template, along its long axis, `(x, y) → (x, −y)`, and **before** the base orientation and the rotations, so it holds for every `--stab-rotation-*` and `--global-rotation`. It is an exact integer matrix on the contour; no mirrored CAD solid is made (the same way as for the left off-centered spacebar).

**Same as another 180° for the current templates:** all current stabilizer templates are symmetric left/right and differ only in Y (the side of the notches). A mirror along the long axis swaps the side of the notches, and for these templates that is the same cutout as turning the key class by another 180° (`--stab-rotation-horizontal 180`, `--stab-rotation-vertical 180`); the tests check this for the 2u and the 3u template. The mirror is still a separate switch: it is unambiguous, and it will matter for templates that are not symmetric.

Example:

```powershell
python .\fat_plate_generator.py --json .\tests\layouts\stabilizer_orientation.json --stab-mirror-vertical --output m.stl
```

The header output then shows `Stab mirror:     horizontal off, vertical on`.

### Stepped Keys

A key that is marked as **stepped** in the keyboard-layout-editor (usually only Caps Lock) has `"l": true` in the raw data, for example:

```json
{ "w": 1.25, "w2": 1.75, "l": true }, "Caps Lock"
```

The plate outline always covers both rectangles of such a key (here 1.75u). The option decides which socket the key gets and where its switch sits:

```powershell
--stepped-key standard
```

The normal `stl-templates/switch_socket.stl`, with the switch at the center of the first rectangle (`w`, here 1.25u). This is the default and the behavior of earlier versions.

```powershell
--stepped-key wide-caps
```

The wide-caps socket `stl-templates/switch_socket_wide-caps.stl`, with the switch at the center of the second rectangle (`w2`, here 1.75u). The file is looked up next to `stl-templates/switch_socket.stl`, or you name it with `--socket-wide-caps my_socket.stl`. Because that template is not symmetric, it can be turned additionally in 90° steps like a stabilizer:

```powershell
--wide-caps-rotation 0
```

The default is `0`: an additional rotation on top of the base orientation, which makes the template come out as designed (seen from above with the typist at the bottom of the plate). A stepped key that is wide enough for a stabilizer, and the spacebar, keep their own cutouts.

### Whole-Plate Transform

KLE counts Y downwards (towards the typist), CAD counts Y upwards. This conversion is built in (it flips the KLE Y axis and is part of the fixed base orientation): the plate is the layout as seen from above, with the typist side at low Y. It needs no option. The plate is then moved so that its bounding box starts at X = 0, Y = 0. The order is: stabilizer rotation first, then the whole-plate transform, then the move.

The whole-plate transform moves the keys and the plate outline. The cutouts get only its rotation (they turn with the plate), so they are never mirrored by it. (The left off-centered spacebar and, if you switch it on, a mirrored stabilizer are mirrored on their own, in the template's coordinates; see *Spacebar switch position* and *Stabilizer Mirror*.)

`--global-rotation` and `--global-mirror-x` (or `global_rotation` and `global_mirror_x` in a config file, see *Configuration File*) are **additional** to the built-in conversion. `--global-rotation` turns the finished plate, that is outline, switch positions and cutouts together; `--global-mirror-x` additionally mirrors the outline and the switch positions along X (the cutouts stay unmirrored):

```powershell
--global-rotation 0
--global-mirror-x
```

Allowed rotations are `0`, `90`, `180` and `270`. The default is `--global-rotation 0` and no mirror: the plate with the built-in conversion only. `--global-mirror-x` is off by default, and `--no-global-mirror-x` switches it off again, for example if a config file has turned it on. If you want the plate turned, use `90`, `180` or `270`; `90` together with the built-in flip gives the transform used in the first version of this tool.

To switch the transform off, for example to compare with older plates:

```powershell
--no-global-transform
```

This skips the whole conversion, including the built-in KLE Y flip. `--global-transform` switches it on again, for example if a config file has turned it off. The default is on. (In a config file this is `global_transform = false` or `true`.)

### Plate as One Connected Mesh

By default the plate follows the keys: where the distance between two groups of keys is larger than twice the margin (for example between F-row, main block and numpad of a 100% layout), the plate falls apart into separate parts. With

```powershell
--single-mesh
```

the plate is one connected mesh without gaps. The space between two keys that face each other, horizontally or vertically, is filled over the whole gap, whatever its width (for example between Esc and F1, or between F-row, main block and numpad). Parts that are still separate after that are joined with the smallest radius that connects them, and voids that are enclosed by the plate outline are filled as well. Where no key faces another one (for example the step above the numpad of a 100% layout) the outline stays as it was. The key cutouts are not affected. Without the option the plate is generated as before. `--no-single-mesh` switches it off again, for example if a config file turns it on.

### Fused F-Row

By default the top row of a full-size layout falls apart into separate islands of plate (Esc, the groups of F keys, PrtSc / Scroll Lock / Pause Break), because the gaps between them are much wider than twice the margin. With

```powershell
--fuse-f-row
```

the top row becomes one connected strip of plate. The space between the keys of that row is filled over the whole key height, in the same way as `--single-mesh` does it, but only for the keys of this row. Nothing else is connected: the strip stays a part of its own and is not joined with the main block (in the G80-3000 layout it is 0.75 u above it). The key cutouts are not affected. Without the option the plate is generated exactly as before; `--no-fuse-f-row` switches it off again, for example if a config file turns it on (config key `fuse_f_row = true`).

Which row is meant: all keys without rotation (no `r` in the KLE data) whose KLE `y` is the smallest `y` among the unrotated keys. Rotated keys are never part of the row, and a layout without an unrotated key is not changed. For a 100% layout these are Esc, F1 to F12, PrtSc, Scroll Lock and Pause Break (16 keys); the generator names the number of keys in its header (`top row fused (16 keys)`). Layouts whose top row has no gaps (for example a 40% layout) come out unchanged. Two tolerances are used, both as named constants in the generator: keys whose `y` differs by at most 1e-9 u are in the same row (`TOP_ROW_TOLERANCE`), and a rotation below 1e-9 degrees counts as no rotation (`ROTATION_TOLERANCE`).

Together with `--single-mesh` the option changes nothing, because that option already connects the whole plate. The generator prints a note (`--fuse-f-row has no effect with --single-mesh`); it is neither an error nor a warning.

---

# 12. Configuration File

All settings of the generator can be kept in a TOML file instead of being typed on every call:

```powershell
python .\fat_plate_generator.py --json my_keyboard.json --config .\fat_plate_config.example.toml --output my_keyboard.stl
```

The file is a convenience, not a different behavior: without `--config`, and with the example file as it is, the generator makes exactly the same plate as before. `fat_plate_config.example.toml` lists every setting with its built-in default and a short explanation. Copy it and keep only the keys you want to change; all keys are optional.

## Format

The key names are the option names with an underscore instead of a hyphen. Orientation and template settings are in their own tables:

```toml
margin = 1.0
stabilizer_min_unit = 2.0
single_mesh = false
fuse_f_row = false                  # true: join only the top row (the F-row) into one strip
spacebar_position = "centered"      # centered | off-centered-left | off-centered-right
stepped_key = "standard"            # standard | wide-caps

[orientation]
stab_rotation_horizontal = 0        # additional rotations on top of the built-in base orientation
stab_rotation_vertical = 0
stab_rotation_spacebar = 0
wide_caps_rotation = 0
stab_mirror_horizontal = false      # mirror the horizontal stabilizer cutouts (see Stabilizer Mirror)
stab_mirror_vertical = false
global_transform = true
global_rotation = 0                 # additional rotation of the finished plate
global_mirror_x = false             # additionally mirror outline and switch positions along X

[templates]
socket = "stl-templates/switch_socket.stl"
wide_caps = "stl-templates/switch_socket_wide-caps.stl"
stabilizer_2u = "stl-templates/stabilizer_2-00u.stl"
stabilizer_3u = "stl-templates/stabilizer_3-00u.stl"
spacebar_6u_centered = "stl-templates/stabilizer_6-00u_centered.stl"
spacebar_6u_off_centered = "stl-templates/stabilizer_6-00u_off-center.stl"
spacebar_6_25u_centered = "stl-templates/stabilizer_6-25u_centered.stl"
spacebar_6_25u_off_centered = "stl-templates/stabilizer_6-25u_off-center.stl"
spacebar_7u_centered = "stl-templates/stabilizer_7-00u_centered.stl"
```

| Config key | Command line option |
| --- | --- |
| `margin` | `--margin` |
| `stabilizer_min_unit` | `--stabilizer-min-unit` |
| `single_mesh` | `--single-mesh` / `--no-single-mesh` |
| `fuse_f_row` | `--fuse-f-row` / `--no-fuse-f-row` |
| `spacebar_position` | `--spacebar-position` |
| `stepped_key` | `--stepped-key` |
| `orientation.stab_rotation_horizontal` | `--stab-rotation-horizontal` |
| `orientation.stab_rotation_vertical` | `--stab-rotation-vertical` |
| `orientation.stab_rotation_spacebar` | `--stab-rotation-spacebar` |
| `orientation.wide_caps_rotation` | `--wide-caps-rotation` |
| `orientation.stab_mirror_horizontal` | `--stab-mirror-horizontal` / `--no-stab-mirror-horizontal` |
| `orientation.stab_mirror_vertical` | `--stab-mirror-vertical` / `--no-stab-mirror-vertical` |
| `orientation.global_transform` | `--global-transform` / `--no-global-transform` |
| `orientation.global_rotation` | `--global-rotation` |
| `orientation.global_mirror_x` | `--global-mirror-x` / `--no-global-mirror-x` |
| `templates.socket` | `--socket` |
| `templates.wide_caps` | `--socket-wide-caps` |
| `templates.stabilizer_2u` | `--stabilizer-2u` |
| `templates.stabilizer_3u` | `--stabilizer-3u` |
| `templates.spacebar_6u_centered` | config only |
| `templates.spacebar_6u_off_centered` | config only |
| `templates.spacebar_6_25u_centered` | config only |
| `templates.spacebar_6_25u_off_centered` | config only |
| `templates.spacebar_7u_centered` | config only |

The input and output file (`--json`, `--output`) are not part of a config file: the same config is meant to serve different layouts.

## Which Value Wins

**Command line option > config file > built-in default.** A setting that is not given on the command line keeps the value of the config file, and a key that is missing in the file keeps the built-in default. Switches can be turned off again on the command line: `--no-single-mesh` overrides `single_mesh = true`, `--no-fuse-f-row` overrides `fuse_f_row = true`, and `--no-global-mirror-x` overrides `global_mirror_x = true`, and `--global-transform` / `--no-global-transform` override `global_transform` in both directions.

A config file is only used if you name it with `--config`. The generator never looks for one by itself, so the result never depends on a file you did not ask for. The header of the output shows which one was used (`Config: ...`, or `Config: none`).

## Paths

- Relative paths **in the config file** are relative to the folder of the config file.
- Paths on the **command line** are relative to the folder you run the command in, as always.
- Without either, the built-in defaults are relative to the folder of `fat_plate_generator.py`.

## Errors

The config is checked strictly. An unknown key (also in `[orientation]` and `[templates]`, so a typo does not go unnoticed), a value of the wrong type (for example `margin = "1"`), an invalid value (for example `stab_rotation_vertical = 45`) and a template file that does not exist stop the generator with an `ERROR:` line that names the file, the key and what is expected. Whole numbers are fine where a decimal number is expected (`margin = 1`).

## Python Version

Config files are read with `tomllib` from the Python standard library, which needs **Python 3.11 or newer**. With an older Python and `--config` the generator says `config files need Python 3.11 or newer`. Without `--config` nothing changes, and no extra package is needed.

---

# 13. Preview Tool

`tools/preview.py` renders a top view of a generated STL as PNG: a horizontal section at half plate height with material in gray, cutouts in white, an axis cross at the origin, a scale bar and the key labels from your KLE JSON. It is meant for checking the orientation of the asymmetric stabilizer cutouts.

It needs matplotlib, which is only a development dependency:

```powershell
python -m pip install -r requirements-dev.txt
python .\tools\preview.py my_plate.stl --layout my_layout.json --output my_plate.png
```

Use `--no-global-transform` here as well if the STL was generated with that option. If the plate was generated with a config file, pass it with `--config my_config.toml`: the preview then reads the margin and the whole-plate transform from it, the same way the generator does (`--margin` and `--no-global-transform` still win). `docs/preview_before.png` and `docs/preview_after.png` show the test layout `tests/layouts/stabilizer_orientation.json` before and after the orientation fix.

The tests run with:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

---

# 14. Most Important Commands

### Create environment (once)

```powershell
python -m venv .venv
```

### Activate environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### Install packages

```powershell
python -m pip install -r requirements.txt
```

### Generate example

```powershell
python .\fat_plate_generator.py
```

### Generate custom layout

```powershell
python .\fat_plate_generator.py --json my_layout.json --output my_plate.stl
```

### Generate with a config file

```powershell
python .\fat_plate_generator.py --json my_layout.json --config .\fat_plate_config.example.toml --output my_plate.stl
```

---

# 15. Common Errors

## `python is not recognized`

Python was not found.

Solution:

1. Install Python.
2. Enable **Add python.exe to PATH** during installation.
3. Close PowerShell.
4. Open a new PowerShell window.
5. Check:

```powershell
python --version
```

---

## `No module named ...`

The required packages are not installed, or the virtual environment is not active.

Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then:

```powershell
python -m pip install -r requirements.txt
```

---

## `Activate.ps1 cannot be loaded`

PowerShell is blocking execution.

Execute once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

## Warning: `the template STLs are not exact`

The generator found something in a template that deviates from the fixed bounding box or from a clean mesh, for example a bounding box that is 0.002 mm too small, a wall that leans by a micron, or contour points that belong to no closed contour. The plate is built from the templates exactly as they are, and every line of the warning says which file and which height is affected. Fix the template in Blender.

---

## Warning: `not watertight`

The generator prints this warning when the exported STL has open edges or edges shared by more than two triangles, so some slicers may not handle it correctly. So far the cause was inexact template STLs: tiny coordinate differences (far below a hundredth of a millimeter) between the layers of a cutout, which leave a few edges shared by four triangles where two layers touch. The STL is written anyway, so you can inspect it. If you use your own templates, check them in Blender.

---

## Missing F-Row or Numpad

Ensure that you are using a current version of the generator.

For 100% layouts, spatially separated key groups are also processed. The F-row, arrow keys, and numpad must not be removed due to their spacing.

---

## Which file was used?

If multiple JSON or STL files are in the folder, specify them explicitly:

```powershell
python .\fat_plate_generator.py --json my_layout.json --socket my_socket.stl --stabilizer-2u my_stabilizer.stl --output my_plate.stl
```

---

# 16. What Happens During Generation?

Simplified:

```text
KLE JSON
   |
   v
KLE Key Positions
   |
   +--> Standard Key ------> switch_socket.stl
   |
   +--> Stabilizer Key ----> stabilizer_2-00u.stl / stabilizer_3-00u.stl  (turned per key class)
   |
   +--> Spacebar ---------> dedicated spacebar STL  (turned)
   |
   |    all three: contour read layer by layer, every layer lofted
   v
CAD Plate  (whole-plate transform, moved to X = 0, Y = 0)
   |
   v
STL File
   |
   v
Validation (closed volume, dimensions)
```

Individual keys are not simply placed side-by-side as independent STL files. The goal is a clean, contiguous plate geometry.

---

# 17. Checking the STL

After successful generation, the STL file will be located in the specified output folder.

The generator also checks every exported STL itself. The file is only read, never changed. The checks are:

- the file exists and is not empty
- the mesh is a closed (watertight) volume with consistent, outward-facing triangles
- the dimensions match the CAD model within 0.1 mm

If a check finds a problem, the generator prints an explicit `WARNING` with the reasons (for example the number of open edges) and carries on. The STL is always written, so you can open it and look at it. Only a missing or empty file is treated as an error.

Before printing, you should verify:

- Are all keys present?
- Are the stabilizer cutouts correct?
- Are the outer dimensions correct?
- Are there any unexpected holes?
- Does your slicer recognize the geometry correctly?

---

# 18. Current Project Status

Currently, the generator supports in particular:

- KLE Raw Data JSON
- Standard switch sockets
- Stabilizer sockets
- Various key sizes
- 60% layouts
- Full-size / 100% layouts
- Spatially separated key groups
- Stabilizer cutouts turned per key class (horizontal, vertical, spacebar)
- CAD-based geometry
- Exact template STLs: the exported plates are watertight
- STL export with automatic validation
- Top-view preview of generated plates (`tools/preview.py`)
- Optional single connected plate without gaps (`--single-mesh`)
- Optional fused F-row: the top row of the layout as one strip of plate (`--fuse-f-row`)
- Stepped keys (stepped Caps Lock): normal socket or wide-caps socket (`--stepped-key`)
- All settings in an optional TOML config file (`--config`)

Planned or currently in development (details in `ROADMAP.md`):

- Rotated KLE keys and a more robust spacebar / Caps Lock detection
- Layout features such as several STL files for separated parts
- Rounded or beveled plate corners and standoffs
- Additional stabilizer variants

---

# 19. In Case of an Error

If something does not work, copy the **entire error message from PowerShell**.

The complete section is particularly helpful:

```text
Traceback (most recent call last):
...
```

Not just the last line. The complete traceback shows where the problem occurs.
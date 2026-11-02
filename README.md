# Fat Plate Generator V.0.11

The Fat Plate Generator creates a 3D-printable keyboard "fat" plate as an STL from a **KLE Raw Data JSON**.

You can export your keyboard layout from [https://www.keyboard-layout-editor.com/]() and use Fat Plate Generator to generate a keyboard switch plate for 3D printing.

This is still a WIP, but with some 3D editing (for example Blender) you can already make use of it.

## !! Disclaimer !!

This is not a finished product!

It has not yet been tested, if the generated plate fits a real keyboard and switches in 3D-printed form. 
Spacebar stabilizer cutouts are now supported with centered and off-centered (left or right) switch-position options, which is needed for a classic Cherry G80-3000.

If a template STL is not exact (for example one you designed yourself), the generator prints warnings (see *Common Errors*); the STL is written anyway and can be inspected.

## Content

- `fat_plate_generator.py` – the application
- `requirements.txt` – required Python packages
- `requirements-dev.txt` – additional packages for the preview tool and the tests
- `switch_socket.stl` – template for standard switch sockets
- `switch_socket_wide-shift.stl` – template for stepped keys such as a stepped Caps Lock (see *Stepped Keys*; not included yet, you add it)
- `stabilizer.stl` – template for standard stabilized keys
- `stabilzer_spacebar.stl` – centered spacebar template
- `stabilzer_spacebar_centered.stl` – identical copy of the centered template (not read by the generator)
- `stabilzer_spacebar_off-center_left.stl` – spacebar template with the switch left of the center
- `stabilzer_spacebar_off-center_right.stl` – spacebar template with the switch right of the center
- `keyboard-layout.json` – example layout
- `KLE-exports/` – more example layouts (40%, 100% ISO and ANSI)
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
└── kle-jsons
    ├── keyboard-layout.json
    ├── keyboard-layout_040-percent_jd40.json
    ├── keyboard-layout_100-percent_ansi_104-keys.json
    ├── keyboard-layout_100-percent-iso-105-keys.json
    ├── keyboard-layout_100-percent-iso-105-keys_g80-3000.json
    ├── keyboard-layout_100-percent-iso-105-keys_stepped-capslock-.json
    ├── keyboard-layout_100-percent-iso-105-keys_stepped-capslock_g80-1800.json
    ├── keyboard-layout_numpad_21-keys_stars21.json
    └── stepped-capslock.json    
└── stl-templates
    ├── switch_socket.stl
    ├── stabilizer.stl
    ├── stabilzer_spacebar.stl
    ├── stabilzer_spacebar_off-center_left.stl
    ├── stabilzer_spacebar_off-center_right.stl
    ├── switch_socket_wide-shift.stl
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
keyboard-layout.json
```

Simply run it with:

```powershell
python .\fat_plate_generator.py
```

The generator automatically uses:

```text
keyboard-layout.json
switch_socket.stl
stabilizer.stl
stabilzer_spacebar.stl
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

Important: Use the KLE **Raw Data JSON**, not another JSON export format.

---

# 9. Using Custom STL Files

You can explicitly specify the socket and stabilizer files:

```powershell
python .\fat_plate_generator.py --json my_keyboard.json --socket switch_socket.stl --stabilizer stabilizer.stl --output my_keyboard.stl
```

This explicitly defines which files are being used.

---

# 10. What Are the STL Templates?

A template is a plate cell with the cutout in it, centered on the switch. The generator reads the **contour of the cutout** from it and builds the cutter for every key from that contour. Socket, stabilizer and spacebar are read and built in exactly the same way.

## `switch_socket.stl`

This file defines the cutout for a standard key or switch.

## `switch_socket_wide-shift.stl`

This file defines the cutout for a stepped key (for example a stepped Caps Lock). It is only used with `--stepped-key wide-shift` (see *Stepped Keys*), and only if the layout has a stepped key. Like the other templates it is centered on the switch, and it is turned like a stabilizer (`--wide-shift-rotation`), never mirrored.

## `stabilizer.stl`

This file contains the **switch socket + stabilizer cutout**.

## `stabilzer_spacebar.stl`, `stabilzer_spacebar_off-center_left.stl` and `stabilzer_spacebar_off-center_right.stl`

These files define the dedicated 6.25u spacebar cutout. The templates contain the same overall spacebar geometry, but place the switch position differently: centered, left of the center or right of the center, seen from above with the typist at the bottom of the plate.

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

The default is **centered**. The supplied templates are used exactly as they are; nothing is stretched, scaled or rounded.

### Caps Lock

Caps Lock is intentionally **not** treated as a stabilized key. It always receives the normal `switch_socket.stl` switch cutout, even though it is 1.75u wide.

## Fixed bounding boxes

The outer size of every template is fixed. If you design a new template (for example in Blender), build it inside this box and do not change the box:

| Template                | Size X × Y                                 | Height Z      |
| ----------------------- | ------------------------------------------ | ------------- |
| socket                  | 19.05 × 19.05 mm                           | −5.0 … 1.2 mm |
| stabilizer              | 38.1 × 19.05 mm                            | −5.0 … 1.2 mm |
| spacebar (all variants) | 114.3015 × 19.05 mm                        | −5.0 … 1.2 mm |
| wide-shift socket       | not fixed yet (only the height is checked) | −5.0 … 1.2 mm |

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

### Socket

```powershell
--socket switch_socket.stl
```

### Stabilizer

```powershell
--stabilizer stabilizer.stl
```

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

The three options select `stabilzer_spacebar.stl`, `stabilzer_spacebar_off-center_left.stl` or `stabilzer_spacebar_off-center_right.stl`. The switch position is seen from above with the typist at the bottom of the plate.

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

Default: `1.75u`

```powershell
--stabilizer-min-unit 2
```

### Stabilizer Orientation

The stabilizer cutouts are asymmetric, so each of them can be turned in 90° steps (counter-clockwise, around the switch center). Horizontal keys, vertical keys (for example numpad `+` / `Enter`, ISO Enter) and the spacebar are set separately:

```powershell
--stab-rotation-horizontal 180
--stab-rotation-vertical 90
--stab-rotation-spacebar 180
```

Allowed values are `0`, `90`, `180` and `270`. The values above are the defaults. If a stabilizer faces the wrong way in your plate, change only the option of that key class.

The cutouts are only turned, **never mirrored**: every cutout is the template as designed, so a left spacebar template stays a left one.

### Stepped Keys

A key that is marked as **stepped** in the keyboard-layout-editor (usually only Caps Lock) has `"l": true` in the raw data, for example:

```json
{ "w": 1.25, "w2": 1.75, "l": true }, "Caps Lock"
```

The plate outline always covers both rectangles of such a key (here 1.75u). The option decides which socket the key gets and where its switch sits:

```powershell
--stepped-key standard
```

The normal `switch_socket.stl`, with the switch at the center of the first rectangle (`w`, here 1.25u). This is the default and the behavior of earlier versions.

```powershell
--stepped-key wide-shift
```

The wide-shift socket `switch_socket_wide-shift.stl`, with the switch at the center of the second rectangle (`w2`, here 1.75u). The file is looked up next to `switch_socket.stl`, or you name it with `--socket-wide-shift my_socket.stl`. Because that template is not symmetric, it can be turned in 90° steps like a stabilizer:

```powershell
--wide-shift-rotation 180
```

The default is `180`, which makes the template come out as designed (seen from above with the typist at the bottom of the plate). A stepped key that is wide enough for a stabilizer, and the spacebar, keep their own cutouts.

### Whole-Plate Transform

KLE counts Y downwards (towards the typist), CAD counts Y upwards. The generated plate is therefore turned by 180° around Z and mirrored along X, which is the same as flipping the KLE Y axis: the plate is the layout as seen from above, with the typist side at low Y. The plate is then moved so that its bounding box starts at X = 0, Y = 0. The order is: stabilizer rotation first, then the whole-plate transform, then the move.

The mirror of the whole-plate transform only moves the keys and the plate outline. The cutouts get just its rotation (they turn with the plate), so they are never mirrored.

The whole-plate rotation is `global_rotation` in `OrientationConfig` (`fat_plate_generator.py`). If you want the plate turned further, change it to `90` or `270`; `90` gives the transform used in the first version of this tool.

To switch the transform off, for example to compare with older plates:

```powershell
--no-global-transform
```

### Plate as One Connected Mesh

By default the plate follows the keys: where the distance between two groups of keys is larger than twice the margin (for example between F-row, main block and numpad of a 100% layout), the plate falls apart into separate parts. With

```powershell
--single-mesh
```

the plate is one connected mesh without gaps. The space between two keys that face each other, horizontally or vertically, is filled over the whole gap, whatever its width (for example between Esc and F1, or between F-row, main block and numpad). Parts that are still separate after that are joined with the smallest radius that connects them, and voids that are enclosed by the plate outline are filled as well. Where no key faces another one (for example the step above the numpad of a 100% layout) the outline stays as it was. The key cutouts are not affected. Without the option the plate is generated as before.

---

# 12. Preview Tool

`tools/preview.py` renders a top view of a generated STL as PNG: a horizontal section at half plate height with material in gray, cutouts in white, an axis cross at the origin, a scale bar and the key labels from your KLE JSON. It is meant for checking the orientation of the asymmetric stabilizer cutouts.

It needs matplotlib, which is only a development dependency:

```powershell
python -m pip install -r requirements-dev.txt
python .\tools\preview.py my_plate.stl --layout my_layout.json --output my_plate.png
```

Use `--no-global-transform` here as well if the STL was generated with that option. `docs/preview_before.png` and `docs/preview_after.png` show the test layout `tests/layouts/stabilizer_orientation.json` before and after the orientation fix.

The tests run with:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

---

# 13. Most Important Commands

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

---

# 14. Common Errors

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
python .\fat_plate_generator.py --json my_layout.json --socket my_socket.stl --stabilizer my_stabilizer.stl --output my_plate.stl
```

---

# 15. What Happens During Generation?

Simplified:

```text
KLE JSON
   |
   v
KLE Key Positions
   |
   +--> Standard Key ------> switch_socket.stl
   |
   +--> Stabilizer Key ----> stabilizer.stl  (turned per key class)
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

# 16. Checking the STL

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

# 17. Current Project Status

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
- Stepped keys (stepped Caps Lock): normal socket or wide-shift socket (`--stepped-key`)

Planned or currently in development (details in `ROADMAP.md`):

- Rotated KLE keys and a more robust spacebar / Caps Lock detection
- Layout features such as one mesh for the F-row and several STL files for separated parts
- Rounded or beveled plate corners and standoffs
- Additional stabilizer variants

---

# 18. In Case of an Error

If something does not work, copy the **entire error message from PowerShell**.

The complete section is particularly helpful:

```text
Traceback (most recent call last):
...
```

Not just the last line. The complete traceback shows where the problem occurs.
# Fat Plate Generator V.0.11

The Fat Plate Generator creates a 3D-printable keyboard "fat" plate as an STL from a **KLE Raw Data JSON**.

You can export your keyboard layout from [https://www.keyboard-layout-editor.com/]() and use Fat Plate Generator to generate a keyboard switch plate for 3D printing.

This is still a WIP, but with some 3D editing (for example Blender) you can already make use of it.



## !! Disclaimer !!

This is not a finished product!

It has not yet been tested, if the generated plate fits a real keyboard and switches in 3D-printed form. 
Spacebar stabilizer cutouts are now supported with centered and off-centered switch-position options, which is needed for a classic Cherry G80-3000.





## Content

- `fat_plate_generator.py` – the application
- `requirements.txt` – required Python packages
- `key_socket.stl` – template for standard switch sockets
- `stabilizer.stl` – template for standard stabilized keys
- `stabilzer_spacebar.stl` – centered spacebar template
- `stabilzer_spacebar_off-center.stl` – off-centered spacebar template
- `keyboard-layout.json` – example layout
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

# 2. Extracting the Program

Extract the ZIP file, for example, to:

```text
C:\GitHub\Fat Plate Generator\fat_plate_generator_v10
```

The folder should look roughly like this:

```text
fat_plate_generator_v10
├── fat_plate_generator.py
├── requirements.txt
├── README.md
├── key_socket.stl
├── stabilizer.stl
└── g80_3000_kle.json
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
key_socket.stl
stabilizer.stl
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
python .\fat_plate_generator.py --json my_keyboard.json --socket key_socket.stl --stabilizer stabilizer.stl --output my_keyboard.stl
```

This explicitly defines which files are being used.

---

# 10. What Are the STL Templates?

## `key_socket.stl`

This file defines the cutout for a standard key or switch.

## `stabilizer.stl`

This file contains the **switch socket + stabilizer cutout**.

## `stabilzer_spacebar.stl` and `stabilzer_spacebar_off-center.stl`

These files define the dedicated 6.25u spacebar cutout. The two templates contain the same overall spacebar geometry, but place the switch position differently.

Select the desired variant with:

```powershell
--spacebar-position centered
```

or:

```powershell
--spacebar-position off-centered
```

The default is **centered**. The supplied spacebar geometry is used without stretching.

### Caps Lock

Caps Lock is intentionally **not** treated as a stabilized key. It always receives the normal `key_socket.stl` switch cutout, even though it is 1.75u wide.

---

# 11. Important Options

### JSON File

```powershell
--json my_layout.json
```

### Socket

```powershell
--socket key_socket.stl
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
--spacebar-position off-centered
```

The two options select `stabilzer_spacebar.stl` or `stabilzer_spacebar_off-center.stl`.

### Output

```powershell
--output my_plate.stl
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

### Whole-Plate Transform

The generated plate is rotated by 90° around Z and mirrored along X, which gives the plate the same orientation as the layout seen from above (the KLE Y axis points down, CAD Y points up). The plate is then moved so that its bounding box starts at X = 0, Y = 0. The order is: stabilizer rotation first, then the whole-plate transform, then the move.

To switch the transform off, for example to compare with older plates:

```powershell
--no-global-transform
```

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
   +--> Standard Key ------> key_socket.stl
   |
   +--> Stabilizer Key ----> stabilizer.stl
   |
   +--> Spacebar ---------> dedicated spacebar STL
   |
   v
CAD Plate
   |
   v
STL File
```

Individual keys are not simply placed side-by-side as independent STL files. The goal is a clean, contiguous plate geometry.

---

# 16. Checking the STL

After successful generation, the STL file will be located in the specified output folder.

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
- CAD-based geometry
- STL export

Planned or currently in development:

- Additional stabilizer variants
- Further KLE edge cases
- Additional convenience features

---

# 18. In Case of an Error

If something does not work, copy the **entire error message from PowerShell**.

The complete section is particularly helpful:

```text
Traceback (most recent call last):
...
```

Not just the last line. The complete traceback shows where the problem occurs.
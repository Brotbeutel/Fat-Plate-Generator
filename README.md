# Fat Plate Generator v0.12

The Fat Plate Generator creates a 3D-printable keyboard plate as an STL from **KLE Raw Data JSON**.

The generator uses the supplied STL templates as the source geometry for switch and stabilizer cutouts and reconstructs them as clean CAD geometry.

## Disclaimer

This is still a WIP. The generated plate should be checked in a CAD viewer and slicer before printing.

## Contents

- `fat_plate_generator.py` – the generator
- `requirements.txt` – required Python packages
- `switch_socket.stl` – standard switch/socket template
- `stabilizer.stl` – standard stabilizer template
- `stabilzer_spacebar.stl` – centered spacebar template
- `stabilzer_spacebar_centered.stl` – centered spacebar template variant
- `stabilzer_spacebar_off-center.stl` – off-centered spacebar template
- `keyboard-layout.json` – example KLE layout
- `README.md` – this guide

---

# 1. Requirements

You need Windows and Python 3.

Install the dependencies with:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Blender is useful if you want to inspect or edit the STL template files, but it is not required for generation.

---

# 2. Basic usage

The included example can be generated with:

```powershell
python .\fat_plate_generator.py
```

This uses:

- `keyboard-layout.json`
- `switch_socket.stl`
- `stabilizer.stl`
- the centered spacebar template

and creates `fat_plate_export.stl`.

For your own KLE Raw Data JSON:

```powershell
python .\fat_plate_generator.py --json my_keyboard.json --output my_keyboard.stl
```

Use KLE **Raw Data JSON**, not another KLE export format.

---

# 3. STL templates

### `switch_socket.stl`

Defines the standard switch/socket cutout.

### `stabilizer.stl`

Defines the combined switch socket and stabilizer cutout for normal stabilized keys. The template geometry is used as supplied.

### Spacebar templates

The spacebar has its own dedicated geometry because the switch position can differ between keyboard designs. Select it with:

```powershell
--spacebar-position centered
```

or:

```powershell
--spacebar-position off-centered
```

The default is `centered`. The selected template is used directly; its internal switch position and stabilizer geometry are preserved.

### Caps Lock

Caps Lock intentionally uses the normal `switch_socket.stl` cutout. It does not receive a stabilizer cutout.

---

# 4. Model orientation

The supplied 3D templates use a common local orientation. The generator applies the project coordinate transforms in code.

### Final plate transform

After the CAD plate has been built, the complete plate is:

1. rotated **90° around Z**
2. mirrored along **X** (equivalent to an X scale of `-1`)

### Stabilizers

Normal stabilizers receive a **90° Z rotation**.

Spacebar stabilizers receive a **180° Z rotation**.

You can independently flip the two stabilizer orientations with the command-line options below. A flip is an additional **180° rotation around Z** for that orientation.

---

# 5. Command-line options

### Layout

```powershell
--json my_layout.json
```

### Switch template

```powershell
--socket switch_socket.stl
```

### Stabilizer template

```powershell
--stabilizer stabilizer.stl
```

### Spacebar position

```powershell
--spacebar-position centered
```

or:

```powershell
--spacebar-position off-centered
```

### Output

```powershell
--output my_plate.stl
```

### Plate margin

Default: `1 mm`

```powershell
--margin 2
```

### Stabilizer detection threshold

Default: `1.75u`. This controls which key sizes are treated as stabilized keys.

```powershell
--stabilizer-min-unit 2
```

### Flip horizontal stabilizers

```powershell
--flip-horizontal-stabilizers
```

### Flip vertical stabilizers

```powershell
--flip-vertical-stabilizers
```

Both options can be used together.

---

# 6. Example commands

Standard generation:

```powershell
python .\fat_plate_generator.py
```

Off-centered spacebar:

```powershell
python .\fat_plate_generator.py --spacebar-position off-centered
```

Flip horizontal stabilizers:

```powershell
python .\fat_plate_generator.py --flip-horizontal-stabilizers
```

Flip vertical stabilizers:

```powershell
python .\fat_plate_generator.py --flip-vertical-stabilizers
```

Flip both:

```powershell
python .\fat_plate_generator.py --flip-horizontal-stabilizers --flip-vertical-stabilizers
```

---

# 7. Generation flow

```text
KLE Raw JSON
    |
    v
KLE key positions
    |
    +--> normal key --------> switch_socket.stl
    |
    +--> stabilized key ----> stabilizer.stl
    |
    +--> spacebar ----------> selected spacebar STL
    |
    v
CAD plate + cutouts
    |
    v
90° Z rotation + X mirror
    |
    v
STL export
```

Spatially separated groups such as an F-row, navigation cluster, or numpad are retained. The generator does not reduce the result to a single connected component.

---

# 8. Checking the result

Before printing, inspect the exported STL in Blender, Fusion 360, PrusaSlicer, OrcaSlicer, Cura, or another suitable tool. Check:

- all keys are present
- the final orientation is correct
- stabilizer cutouts are oriented correctly
- the spacebar variant matches your keyboard
- Caps Lock has the normal switch cutout
- outer dimensions are correct
- there are no unexpected holes or disconnected artifacts

If something fails, copy the complete PowerShell traceback rather than only the final error line.

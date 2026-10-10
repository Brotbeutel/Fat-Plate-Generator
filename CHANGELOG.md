# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added
- `--stab-rotation-horizontal`, `--stab-rotation-vertical` and `--stab-rotation-spacebar` (0/90/180/270) set the stabilizer orientation per key class.
- `--no-global-transform` skips the whole-plate transform (for comparison with older plates).
- `--version` prints the version (`VERSION` in `fat_plate_generator.py`, 0.11, same as the README title).
- Fixed bounding boxes for the templates (`TEMPLATE_BOUNDING_BOXES`, `PLATE_Z_MIN`, `PLATE_Z_MAX`). They are only checked: a deviation of more than 0.001 mm produces a warning and never changes the geometry. The README documents the boxes for people who design new templates.
- Warnings for defects in the templates (dangling contour points, leaning walls) instead of silent corrections.
- Automatic check of the exported STL (`check_exported_stl()`): it must exist, not be empty, be a closed outward-facing volume and match the CAD bounds within 0.1 mm. Mesh problems produce an explicit warning with the reasons (open edges, shared edges, ...) and never stop the run; the STL is always written. Only a missing or empty file is an error.
- `tools/preview.py` renders a top-view PNG of a plate STL with axes, scale and key labels (needs `requirements-dev.txt`).
- Test layout `tests/layouts/stabilizer_orientation.json` and a pytest suite (`python -m pytest`), including unit tests for the validation.
- Workflow files `AGENTS.md`, `ROADMAP.md`; `TODO.txt` was folded into `ROADMAP.md`.

### Changed
- Stabilizer cutouts now follow the key direction. The templates were made horizontal in an earlier commit, but the generator still turned horizontal keys by 90° and left vertical keys at 0°. Defaults: horizontal 180°, vertical 270°, spacebar 180°.
- The plate is rotated by 180° around Z, mirrored along X (together this is the KLE Y flip) and moved so its bounding box starts at (0, 0), which replaces the manual Blender corrections. Existing plates are therefore mirrored compared to earlier output.
- Socket, stabilizer and spacebar cutouts are read and built by one exact loader (`load_template()`, `template_cutter()`). Every layer is a ruled loft from its lower to its upper contour, so the slopes (z = -1.8 ... -1.5) are exact. Before, the stabilizer replaced a slope by one step of half the height (up to 0.13 mm off), and the socket was reduced to a single square size.
- The plate thickness comes from the fixed values (z = -5.0 ... 1.2), not from the socket template.
- The exported STL is no longer re-exported through trimesh; it stays exactly as written by CadQuery.
- The settings are printed before the STL is checked.
- `generate()` is split into `build_plate_model()` and the STL export; key classification lives in `classify_key()`.
- README: file names (`switch_socket.stl`), folder structure, validation, error message and project status brought up to date.
- Spacebar template STLs re-exported (four layers instead of three).

### Removed
- All rounding and tolerances of the old template reading: points rounded to 1e-6, heights rounded to 1e-5 and merged within 2 um, layers thinner than 2 um skipped, `SIZE_TOL` of 0.08 mm, `remove_collinear` and the rule to keep only the largest contour of a layer. The remaining tolerances are listed in the README.
- The stabilizer stretch function: `--stabilizer-scale`, the scale modes and their code. Templates are always used exactly as supplied.
- Voxel wording and the unused `wire_at()` helper.
- `fat_plate_generator_wp1.py`; its changes are part of `fat_plate_generator.py`.

### Known issues
- The template STLs carry coordinate differences of 10 to 20 nm (in places up to 1 µm) between the layers of a cutout, and `stabilizer.stl` has a wall that leans by 1 µm. The plate is built from them exactly as they are; a few edges where two layers touch are shared by four faces, and the check prints the warning `not watertight`. `switch_socket.stl` is 19.0478 mm wide instead of 19.05 mm. The templates are being rebuilt; tests that need exact templates are marked `xfail` until then (see `ROADMAP.md`).

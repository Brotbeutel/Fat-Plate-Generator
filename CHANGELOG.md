# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added
- `--stab-rotation-horizontal`, `--stab-rotation-vertical` and `--stab-rotation-spacebar` (0/90/180/270) set the stabilizer orientation per key class.
- `--no-global-transform` skips the whole-plate transform (for comparison with older plates).
- `--version` prints the version (`VERSION` in `fat_plate_generator.py`, 0.11, same as the README title).
- Automatic check of the exported STL (`check_exported_stl()`): it must exist, not be empty, be a closed outward-facing volume and match the CAD bounds within 0.1 mm. Mesh problems produce an explicit warning with the reasons (open edges, shared edges, ...) and never stop the run; the STL is always written. Only a missing or empty file is an error.
- `tools/preview.py` renders a top-view PNG of a plate STL with axes, scale and key labels (needs `requirements-dev.txt`).
- Test layout `tests/layouts/stabilizer_orientation.json` and a pytest suite (`python -m pytest`), including unit tests for the validation.
- Workflow files `AGENTS.md`, `ROADMAP.md`; `TODO.txt` was folded into `ROADMAP.md`.

### Changed
- Stabilizer cutouts now follow the key direction. The templates were made horizontal in an earlier commit, but the generator still turned horizontal keys by 90° and left vertical keys at 0°. Defaults: horizontal 180°, vertical 270°, spacebar 180°.
- The plate is rotated by 180° around Z, mirrored along X (together this is the KLE Y flip) and moved so its bounding box starts at (0, 0), which replaces the manual Blender corrections. Existing plates are therefore mirrored compared to earlier output.
- The exported STL is no longer re-exported through trimesh; it stays exactly as written by CadQuery.
- The settings are printed before the STL is checked.
- `generate()` is split into `build_plate_model()` and the STL export; key classification lives in `classify_key()`.
- README: file names (`switch_socket.stl`), folder structure, validation, error message and project status brought up to date.
- Spacebar template STLs re-exported (four layers instead of three).

### Removed
- The stabilizer stretch function: `--stabilizer-scale`, the scale modes and their code. Templates are always used exactly as supplied.
- Voxel wording and the unused `wire_at()` helper.
- `fat_plate_generator_wp1.py`; its changes are part of `fat_plate_generator.py`.

### Known issues
- The template STLs carry coordinate differences of 10 to 20 nm (in places up to 0.7 µm) between the layers of a stabilizer cutout. Depending on library versions this leaves open or non-manifold edges in the exported plate, and the check prints the warning `not watertight`. The templates are being rebuilt; tests that need exact templates are marked `xfail` until then (see `ROADMAP.md`).

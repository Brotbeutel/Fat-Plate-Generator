# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added

- Stepped keys: the KLE flag `"l": true` (a stepped Caps Lock) is read. `--stepped-key standard` (default, as before) uses the normal socket at the center of `w`; `--stepped-key wide-caps` uses the new template `switch_socket_wide-caps.stl` (`--socket-wide-caps` to name another file) at the center of `w2`, turned by `--wide-caps-rotation` (default 180, never mirrored). The plate outline covers both rectangles in either mode. The wide-caps template is only read when a stepped key needs it; its bounding box is not fixed yet, only its height is checked.
- `--single-mesh` generates the plate as one connected mesh without gaps: the space between keys that face each other (horizontally or vertically, whatever the gap: Esc and F1, F-row, main block and numpad) is filled, parts that are still separate are joined with the smallest radius that connects them, and voids enclosed by the outline are filled. Without the option the plate is generated as before.
- `--spacebar-position off-centered-left` and `off-centered-right` (with `--spacebar-off-centered-left` / `--spacebar-off-centered-right` for the files) replace `off-centered`; the template `stabilzer_spacebar_off-center.stl` was split into `stabilzer_spacebar_off-center_left.stl` and `..._right.stl`.
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

- `classify_key()`, `stabilizer_rotation()` and `switch_center()` know stepped keys (`stepped` and `second` arguments); `build_plate_model()` and `generate()` take `stepped_key` and `wide_caps_socket_path`.
- The help text of `--single-mesh` describes the current behavior.
- The cutouts are only turned, never mirrored: the mirror of the whole-plate transform now moves only the keys and the plate outline, the cutouts get just its rotation (`plate_rotation_matrix()`). The default vertical stabilizer rotation is 90° instead of 270° because of that; for the symmetric stabilizers the plate is unchanged.
- Fixed bounding boxes: stabilizer 38.1 × 19.05 mm, spacebar 114.3015 × 19.05 mm (socket unchanged: 19.05 × 19.05 mm).
- `build_plate_model()` and `generate()` take the spacebar templates as one dict (`spacebar_paths`, by switch position) and the new argument `single_mesh`.
- Stabilizer cutouts now follow the key direction. The templates were made horizontal in an earlier commit, but the generator still turned horizontal keys by 90° and left vertical keys at 0°. Defaults: horizontal 180°, vertical 270°, spacebar 180°.
- The plate is rotated by 180° around Z, mirrored along X (together this is the KLE Y flip) and moved so its bounding box starts at (0, 0), which replaces the manual Blender corrections. Existing plates are therefore mirrored compared to earlier output.
- Socket, stabilizer and spacebar cutouts are read and built by one exact loader (`load_template()`, `template_cutter()`). Every layer is a ruled loft from its lower to its upper contour, so the slopes (z = -1.8 ... -1.5) are exact. Before, the stabilizer replaced a slope by one step of half the height (up to 0.13 mm off), and the socket was reduced to a single square size.
- The plate thickness comes from the fixed values (z = -5.0 ... 1.2), not from the socket template.
- The exported STL is no longer re-exported through trimesh; it stays exactly as written by CadQuery.
- The settings are printed before the STL is checked.
- `generate()` is split into `build_plate_model()` and the STL export; key classification lives in `classify_key()`.
- README: file names (`switch_socket.stl`), folder structure, validation, error message and project status brought up to date.
- Spacebar template STLs re-exported (four layers instead of three).
- Folder structure and filepaths
- Added 7u Spacebar template
- Renamed wide-caps to wide-caps

### Removed

- All rounding and tolerances of the old template reading: points rounded to 1e-6, heights rounded to 1e-5 and merged within 2 um, layers thinner than 2 um skipped, `SIZE_TOL` of 0.08 mm, `remove_collinear` and the rule to keep only the largest contour of a layer. The remaining tolerances are listed in the README.
- The stabilizer stretch function: `--stabilizer-scale`, the scale modes and their code. Templates are always used exactly as supplied.
- Voxel wording and the unused `wire_at()` helper.
- `fat_plate_generator_wp1.py`; its changes are part of `fat_plate_generator.py`.

### Fixed

- Corrected the default KLE layout path and the default wide-caps template lookup; aligned path-dependent tests and added guards for exact repository path casing and default stepped-key generation.
- Spacebar (and every other) stabilizer cutout was mirrored horizontally by the whole-plate transform; a left spacebar template came out as a right one.

### Known issues

- Adding a Keyboard Name and Author to the KLE-JSON causes extra keys to appear.
- Keys with a width of 1,75 units get a stabilizer added. (Tested with keyboard-layout_040-percent_jd40.json)

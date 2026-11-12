# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added

- 3u stabilizer: keys that are exactly 3u long (horizontal `w = 3` or vertical `h = 3`) use the new template `stl-templates/stabilizer_3-00u.stl` (template kind `stabilizer-3u`). Settings: `TemplateSet.stabilizer_3u`, `DEFAULT_STABILIZER_3U`, config key `templates.stabilizer_3u` (also in `fat_plate_config.example.toml`) and `--stabilizer-3u PATH`. Its bounding box is not fixed yet (`TEMPLATE_BOUNDING_BOXES["stabilizer-3u"]` is `(None, None)`, only the height is checked); it measures 52.3993 x 19.05 mm. Tests for the selection, the CAD result (width, outline, STL check, no warning, vertical key), the config and CLI, and for the template itself; preview images of a horizontal and a vertical 3u key in `docs/stabilizer-sizes/`.
- 6u and 7u spacebar templates are selected by key width. A missing 3u template uses the 2u template with an explicit warning; unsupported widths are errors.
- `--fuse-f-row` / `--no-fuse-f-row` (off by default) and the config key `fuse_f_row` join the top row of the layout (for a 100% layout Esc, F1-F12, PrtSc, Scroll Lock and Pause Break) into one strip of plate. Only that row is joined, not the main block: the space between its keys is filled with the same bridges as `--single-mesh` (`gap_bridges`), over the rectangles of these keys only (`top_row_keys()`: unrotated keys with the smallest KLE `y`). In the G80-3000 and ISO-105 layouts the plate has 5 instead of 9 parts. With `--single-mesh` the option changes nothing and the generator prints a note; without the option the plate is byte-identical to before. The header shows `top row fused (N keys)`.

- `--config PATH` reads all settings from a TOML file (`tomllib`, Python 3.11 or newer). Precedence: command line option > config file > built-in default. The config is only used if named (no automatic search); relative paths in it are relative to the config folder; unknown keys, wrong types, invalid values and missing template files are errors that name the file and the key. The output header shows `Config: <path>` or `Config: none`. `--json` and `--output` are not part of a config.
- `--global-rotation {0,90,180,270}` and `--global-mirror-x` / `--no-global-mirror-x` (before, these were only reachable in code), and `--no-single-mesh`. Their defaults are unchanged.
- `--global-transform` as the positive form of `--no-global-transform` (`--global-transform/--no-global-transform`), so that a config with `global_transform = false` can be overridden on the command line. `--no-global-transform` works as before.
- `fat_plate_config.example.toml` with every setting at its built-in default (a test makes sure it stays equal to the defaults).
- `tools/preview.py --config PATH` reads the margin and the whole-plate transform from the same config, through the generator's own functions.

- Tests for stepped keys / wide-caps classification across all stepped KLE layouts, stabilizer retention for stepped keys with width >= 2u, CAD overlap and margin tests, and top-view preview renders in `docs/wide-caps-test/` (WP-09).

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

- Spacebar detection now uses width instead of the label. 6u, 6.5u and 8u keys use the matching 6u, 6.25u or 7u template family; 3u keys use the documented 2u replacement. The `TemplateSet` fields and config keys now contain the width, `--stabilizer-2u` replaces `--stabilizer`, and the five spacebar template paths are config-only.
- Renamed the stabilizer templates to `stabilizer_2-00u.stl`, `stabilizer_6-25u_centered.stl`, `stabilizer_6-25u_off-center.stl` and `stabilizer_7-00u_centered.stl`; removed the duplicate `stabilzer_spacebar_centered.stl`.
- `parse_kle()` reads the properties of a key like the Keyboard Layout Editor: `w`, `h`, `x2`, `y2`, `w2`, `h2` and `l` apply to the next key and are reset only after a key, so several objects in a row before one key add up (`{"w": 2}, {"c": "#fff"}, "A"` gives A the width 2); `w` also sets `w2` and `h` also sets `h2` unless the same object names them. Single objects before a key give the same result as before (ISO Enter, stepped Caps Lock).
- Decals (`"d": true`) are ignored: they get no footprint and no cutout, but the position moves on by their width. No layout in `kle-jsons/` has decals.
- `r`, `rx` and `ry` anywhere but on the first item of a row are an error (`ValueError` naming the row) instead of being read silently wrong. KLE exports do not produce this.
- The left off-centered spacebar is the right template mirrored instead of a second file. The mirror is an exact integer matrix in the template's own coordinates, applied before the stabilizer rotation (so it matches the former left file for every rotation); it is the only cutout that is mirrored, and `PlateModel.mirrored` records it per key. The plate is unchanged apart from float noise in the templates (`centered` byte-identical; the sections of `off-centered-left` and `off-centered-right` are identical, only the triangulation of the STL differs). `TemplateSet` has one field `spacebar_off_centered` (the right file) instead of two, and `TemplateSet.spacebar_for()` is the single place that maps a position to a file and a mirror flag. `stabilzer_spacebar_off-center_left.stl` stays in the repository but is no longer read. A custom file given with `--spacebar-off-centered` (or `templates.spacebar_off_centered`) is now taken as the RIGHT design.
- `--spacebar-off-centered` and the config key `templates.spacebar_off_centered` replace `--spacebar-off-centered-left` / `--spacebar-off-centered-right` and `spacebar_off_centered_left` / `spacebar_off_centered_right`. The old names are not kept as aliases and are refused as unknown.
- `generate()` and `build_plate_model()` take a `Settings` object (with a `TemplateSet` for the template paths) instead of long parameter lists: `build_plate_model(kle_path, settings)` and `generate(kle_path, settings, output, config_path=None)`. The generated STL is byte-identical to before (checked for the orientation test layout, the 40% layout and the stepped Caps Lock with `--stepped-key wide-caps`).
- The command line options that a config can also set have no built-in default in the parser any more (that is how a given option is told from a missing one); the help texts still name the defaults.
- The default `--stabilizer-min-unit` is now `2.0`: 1.75u keys (for example Enter and Shift in the JD40 layout) receive a normal socket. Use `--stabilizer-min-unit 1.75` to give them a stabilizer cutout.
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

- The 3u template substitution (the 2u template used for 3u keys, with a warning): `PlateModel.substitutions`, the "Template substitutions" section of the output, its effect on `Done, with warnings.` and the tests for it. There is no missing key width left that needs a substitute.
- All rounding and tolerances of the old template reading: points rounded to 1e-6, heights rounded to 1e-5 and merged within 2 um, layers thinner than 2 um skipped, `SIZE_TOL` of 0.08 mm, `remove_collinear` and the rule to keep only the largest contour of a layer. The remaining tolerances are listed in the README.
- The stabilizer stretch function: `--stabilizer-scale`, the scale modes and their code. Templates are always used exactly as supplied.
- Voxel wording and the unused `wire_at()` helper.
- `fat_plate_generator_wp1.py`; its changes are part of `fat_plate_generator.py`.

### Fixed

- Keys after `rx` / `ry` lie where the Keyboard Layout Editor shows them. The editor sets the position to `(rx, ry)` when either is given (the one that is not given keeps its last value); `parse_kle()` set only `x` for `rx` and only `y` for `ry`. Examples: Del in `keyboard-layout_065-percent-iso_royal-kludge-rk65.json` was at (15, 6) instead of (15, 1) and now matches the hand-cleaned `…_rk65_clean.json`; the thumb cluster of `ergodox_split_ergo_67-keys.json` (row 23 with `rx` but no `ry`, 6 keys) moved up by 2 u. All other layouts in `kle-jsons/` parse exactly as before.
- KLE `name` and `author` metadata at the beginning of Raw Data is now ignored instead of being parsed as extra keys.
- Corrected the default KLE layout path and the default wide-caps template lookup; aligned path-dependent tests and added guards for exact repository path casing and default stepped-key generation.
- Spacebar (and every other) stabilizer cutout was mirrored horizontally by the whole-plate transform; a left spacebar template came out as a right one.

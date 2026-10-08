# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added
- `--stab-rotation-horizontal`, `--stab-rotation-vertical` and `--stab-rotation-spacebar` (0/90/180/270) set the stabilizer orientation per key class.
- `--no-global-transform` skips the whole-plate transform (for comparison with older plates).
- `tools/preview.py` renders a top-view PNG of a plate STL with axes, scale and key labels (needs `requirements-dev.txt`).
- Test layout `tests/layouts/stabilizer_orientation.json` and a pytest suite (`python -m pytest`).
- Workflow files `AGENTS.md`, `ROADMAP.md`; `TODO.txt` was folded into `ROADMAP.md`.

### Changed
- Stabilizer cutouts now follow the key direction. The templates were made horizontal in an earlier commit, but the generator still turned horizontal keys by 90° and left vertical keys at 0°. Defaults: horizontal 180°, vertical 270°, spacebar 180°.
- The plate is rotated by 180° around Z, mirrored along X (together this is the KLE Y flip) and moved so its bounding box starts at (0, 0), which replaces the manual Blender corrections. Existing plates are therefore mirrored compared to earlier output.
- `generate()` is split into `build_plate_model()` and the STL export; key classification lives in `classify_key()`.

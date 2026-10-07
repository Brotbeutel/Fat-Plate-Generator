# Roadmap

Status: `[ ]` offen, `[~]` in Arbeit, `[x]` erledigt.

## Arbeitspakete

- [~] **WP-01** Stabilizer-Orientierung + Preview/Tests (aktuell)
  - Orientierung zentral konfigurierbar (horizontal / vertical / spacebar getrennt)
  - Whole-Plate-Transformation und Stabilizer-Rotationen aus der alten TODO.txt in den Code übernehmen
  - Preview-Tool (`tools/preview.py`) und pytest-Suite
- [ ] **WP-02** Aufräumen
  - Stretch-/Voxel-Reste entfernen
  - KLE-Rotation (`r`) für Cavities
  - robustere Spacebar-/Caps-Lock-Erkennung
  - README/Version/Dateinamen konsistent
- [ ] **WP-03** Testdruck: Mini-Testplatte drucken, Passung und Toleranzen prüfen
- [ ] **WP-04** Layout-Features
  - F-Row als ein Mesh
  - getrennte Meshes → mehrere STL-Dateien
  - Pfeilcluster-Box (gefüllte Ecken)
  - Caps-Lock-Optionen (große Aussparung, linksbündig, zentriert)
- [ ] **WP-05** Plattenform: abgerundete/gefaste Ecken, Standoffs/Spacer
- [ ] **WP-06** Weitere Stabilizer-Varianten

## Übernommene offene Punkte aus der alten TODO.txt

| Punkt | Zuordnung |
| --- | --- |
| push | Nutzer (Branch pushen und mergen) |
| code mesh transformations (Plate: 90° um Z + Spiegelung an X; Spacebar-Stabilizer +180°; alle anderen Stabilizer +90°) | WP-01 |
| uniform stabilizer orientation | WP-01 |
| options for stabilizer orientation – horizontal and vertical ones separate | WP-01 |
| clear traces of voxels and stretch function | WP-02 |
| option for F1–F12 row in one mesh | WP-04 |
| option -> create multiple STL files for separated meshes | WP-04 |
| option for rectangular arrow box shape (filled corners) | WP-04 |
| options for CapsLock: big cutout, left-aligned, centered | WP-04 |
| option for rounded/beveled corners | WP-05 |
| option for standoffs/spacer | WP-05 |
| add more stabilizer options | WP-06 |

## Erledigt (aus der alten TODO.txt)

- new default names
- add `stabilizer_spacebar.stl` and `stabilizer_spacebar_off-center.stl`
- add disclaimer to README
- remove stabilizer at Caps Lock position -> normal socket
- upload all files
- give ChatGPT new `key_socket.stl` (turned 90° around Z, code stays the same)
- give ChatGPT `stabilizer_spacebar.stl`
- create GitHub repo
- make STLs orientation uniform
- run test for current status

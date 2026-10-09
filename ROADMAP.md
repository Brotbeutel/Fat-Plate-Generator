# Roadmap

Status: `[ ]` offen, `[~]` in Arbeit, `[x]` erledigt.

## Arbeitspakete

- [x] **WP-01** Stabilizer-Orientierung + Preview/Tests
  - Orientierung zentral konfigurierbar (`OrientationConfig`: horizontal / vertical / spacebar getrennt, Ganzplatten-Transformation)
  - Preview-Tool (`tools/preview.py`) und pytest-Suite
  - Die Defaults hat der Nutzer nach Sichtprüfung angepasst: horizontal 180°, vertical 270°, spacebar 180°, Platte 180° + Spiegelung an X (= KLE-Y-Umrechnung ohne weitere Drehung)
- [~] **WP-02** Aufräumen
  - [x] Stretch-/Voxel-Reste entfernt (`--stabilizer-scale`, Skalierungscode, toter Code)
  - [x] README/Version/Dateinamen konsistent (`VERSION` im Generator, README-Titel, `switch_socket.stl`)
  - [x] STL-Validierung aus `fat_plate_generator_wp1.py` übernommen, STL wird nicht mehr neu exportiert
  - [ ] KLE-Rotation (`r`) für Cavities (zurückgestellt: Design-Entscheidung nötig, wie die Cavity-Drehung mit der Ganzplatten-Transformation zusammenspielt)
  - [ ] robustere Spacebar-/Caps-Lock-Erkennung (zurückgestellt, bis die neuen Spacebar-Templates stehen)
- [ ] **WP-03** Testdruck: Mini-Testplatte drucken, Passung und Toleranzen prüfen
- [ ] **WP-04** Layout-Features
  - F-Row als ein Mesh
  - getrennte Meshes → mehrere STL-Dateien
  - Pfeilcluster-Box (gefüllte Ecken)
  - Caps-Lock-Optionen (große Aussparung, linksbündig, zentriert)
- [ ] **WP-05** Plattenform: abgerundete/gefaste Ecken, Standoffs/Spacer
- [ ] **WP-06** Weitere Stabilizer-Varianten

## Laufend (Nutzer)

- [~] **Template-Neubau**: Die Spacebar-Stabilizer (und danach `stabilizer.stl`) werden in Blender exakt neu gebaut.
  - Ziel: Koordinaten, die in den Schichten eines Ausschnitts identisch sein sollen, sind es auch. In den Templates streuen sie bisher um 10 bis 20 nm, an einzelnen Stellen um bis zu 0,7 µm. Dadurch bleiben im exportierten Mesh offene oder gemeinsam genutzte Kanten zurück, und die neue Validierung meldet `STL export is not watertight`.
  - Nach dem Neubau: die `TEMPLATE_DEFECT`-Marker in `tests/test_plate.py` entfernen. Die Tests sollen dann ohne Marker bestehen, auch `test_exported_stl_is_strictly_watertight` für das Testlayout und das 100%-Layout.
  - Danach `fat_plate_export_example.stl` mit dem aktuellen Stand neu erzeugen.

## Vorschläge (nicht beauftragt)

- `tools/check_templates.py`: listet Koordinaten auf, die in einem Template fast, aber nicht exakt gleich sind. Soll nach dem Neubau 0 Gruppen melden.
- Versionen in den Requirements festschreiben, damit Ergebnisse auf verschiedenen Rechnern reproduzierbar sind.
- Die schweren Tests (100%-Layout) per Marker abtrennbar machen, sodass ein schneller Lauf möglich ist.
- `stabilzer_spacebar_centered.stl` ist byte-identisch mit `stabilzer_spacebar.stl` und wird vom Generator nicht gelesen. Klären, ob die Kopie bleiben soll.
- Dateinamen `stabilzer_*.stl` → `stabilizer_*.stl` korrigieren, sobald die Templates fertig sind (betrifft Generator, Tests, README).

## Übernommene offene Punkte aus der alten TODO.txt

| Punkt | Zuordnung |
| --- | --- |
| option for F1–F12 row in one mesh | WP-04 |
| option -> create multiple STL files for separated meshes | WP-04 |
| option for rectangular arrow box shape (filled corners) | WP-04 |
| options for CapsLock: big cutout, left-aligned, centered | WP-04 |
| option for rounded/beveled corners | WP-05 |
| option for standoffs/spacer | WP-05 |
| add more stabilizer options | WP-06 |

## Erledigt (aus der alten TODO.txt)

- push
- code mesh transformations (Plate, Spacebar-Stabilizer, andere Stabilizer) → WP-01
- uniform stabilizer orientation → WP-01
- options for stabilizer orientation – horizontal and vertical ones separate → WP-01
- clear traces of voxels and stretch function → WP-02
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

# Roadmap

Status: `[ ]` offen, `[~]` in Arbeit, `[x]` erledigt.

## Arbeitspakete

- [x] **WP-01** Stabilizer-Orientierung + Preview/Tests
  - Orientierung zentral konfigurierbar (`OrientationConfig`: horizontal / vertical / spacebar getrennt, Ganzplatten-Transformation)
  - Preview-Tool (`tools/preview.py`) und pytest-Suite
  - Die Defaults hat der Nutzer nach Sichtprüfung angepasst: horizontal 180°, vertical 90°, spacebar 180°, Platte 180° + Spiegelung an X (= KLE-Y-Umrechnung ohne weitere Drehung); die Ausschnitte werden nur gedreht, nie gespiegelt
- [~] **WP-02** Aufräumen
  - [x] Stretch-/Voxel-Reste entfernt (`--stabilizer-scale`, Skalierungscode, toter Code)
  - [x] README/Version/Dateinamen konsistent (`VERSION` im Generator, README-Titel, `switch_socket.stl`)
  - [x] Socket, Stabilizer und Spacebar werden gleich und exakt erzeugt: ein Loader, jede Schicht ein Loft (Schrägen bleiben Schrägen), alle Konturen, keine Rundungen; die alten Verfahren und ihre Toleranzen sind entfernt
  - [x] Feste Bounding Boxen je Template (nur Prüfung mit Warnung, ändern die Geometrie nie), dokumentiert in der README
  - [x] Stabilizer-Ausschnitte werden nur gedreht, nie gespiegelt (die Spiegelung der Ganzplatten-Transformation betrifft nur Tasten und Umriss); Spacebar-Varianten links/rechts (`--spacebar-position`)
  - [x] STL-Prüfung aus `fat_plate_generator_wp1.py` übernommen (als ausdrückliche Warnung statt Abbruch), STL wird nicht mehr neu exportiert
  - [ ] KLE-Rotation (`r`) für Cavities (zurückgestellt: Design-Entscheidung nötig, wie die Cavity-Drehung mit der Ganzplatten-Transformation zusammenspielt)
  - [ ] robustere Spacebar-/Caps-Lock-Erkennung (zurückgestellt; jetzt möglich, die Spacebar-Templates stehen)
- [ ] **WP-03** Testdruck: Mini-Testplatte drucken, Passung und Toleranzen prüfen
- [~] **WP-04** Layout-Features
  - [x] Option `--single-mesh`: die Platte als ein zusammenhängendes Mesh ohne Lücken (Standard bleibt: getrennte Teile)
  - F-Row als ein Mesh (für die ganze Platte durch `--single-mesh` abgedeckt; als eigene Option noch offen)
  - getrennte Meshes → mehrere STL-Dateien
  - Pfeilcluster-Box (gefüllte Ecken)
  - Caps-Lock-Optionen (große Aussparung, linksbündig, zentriert)
- [ ] **WP-05** Plattenform: abgerundete/gefaste Ecken, Standoffs/Spacer
- [ ] **WP-06** Weitere Stabilizer-Varianten

## Laufend (Nutzer)

- [x] **Template-Neubau**: Die Templates sind exakt neu gebaut (Socket 19,05 × 19,05 mm, Stabilizer 38,1 × 19,05 mm, Spacebar 114,3015 × 19,05 mm; Spacebar zusätzlich als links/rechts versetzte Varianten). Der Generator meldet keine Warnungen mehr, die Platten sind watertight, die `TEMPLATE_DEFECT`-Marker sind entfernt.
  - `FLAT_WALL_TOLERANCE` (50 nm) lässt sich noch nicht senken: bei 1e-6 und 1e-7 ändern sich die Eckenzahlen von `stabilizer.stl` (Punkte auf geraden Wänden weichen 1e-6 bis 5e-5 mm von der Geraden ab), bei 1e-9 lässt sich `stabilizer.stl` nicht mehr loften. Möglich wäre es erst, wenn die Wände der Templates bis auf Float32-Genauigkeit exakt gerade sind.
  - Offen: `fat_plate_export_example.stl` mit dem aktuellen Stand neu erzeugen.

## Vorschläge (nicht beauftragt)

- `tools/check_templates.py`: lädt ein Template wie der Generator und listet seine Warnungen, dazu Koordinaten, die fast, aber nicht exakt gleich sind. Soll bei exakten Templates nichts melden.
- Versionen in den Requirements festschreiben, damit Ergebnisse auf verschiedenen Rechnern reproduzierbar sind.
- Die schweren Tests (100%-Layout) per Marker abtrennbar machen, sodass ein schneller Lauf möglich ist.
- `stabilzer_spacebar_centered.stl` ist byte-identisch mit `stabilzer_spacebar.stl` und wird vom Generator nicht gelesen. Klären, ob die Kopie bleiben soll.
- Dateinamen `stabilzer_*.stl` → `stabilizer_*.stl` korrigieren; jetzt möglich, die Templates sind fertig (betrifft Generator, Tests, README).

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

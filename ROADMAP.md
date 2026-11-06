# Roadmap

Status: `[ ]` offen, `[~]` in Arbeit, `[x]` erledigt.

Stand: `main` @ `1574f50` (WP-07 bis WP-09 gemerged). WP-10 liegt auf dem Branch `wp-10-config-file`: Teil A ist gepusht (`14e311b`), Teil B ist laut Abschlussbericht fertig, aber noch nicht auf GitHub.

## Reihenfolge

~~WP-07~~ → ~~WP-08~~ → ~~WP-09~~ → WP-10 (+ Nachtrag) → WP-11 → WP-12 → WP-13. WP-11 bis WP-13 bauen auf dem Settings-Objekt und der Config aus WP-10 auf. Der Prompt für WP-12 folgt, sobald WP-11 gemerged ist.

## Arbeitspakete

- [x] **WP-01** Stabilizer-Orientierung + Preview/Tests
  - Orientierung zentral konfigurierbar (`OrientationConfig`: horizontal / vertical / spacebar getrennt, Ganzplatten-Transformation)
  - Preview-Tool (`tools/preview.py`) und pytest-Suite
  - Die Defaults hat der Nutzer nach Sichtprüfung angepasst: horizontal 180°, vertical 90°, spacebar 180°, Platte 180° + Spiegelung an X (= KLE-Y-Umrechnung ohne weitere Drehung); die Ausschnitte werden nur gedreht, nie gespiegelt
- [x] **WP-02** Aufräumen (abgeschlossen; die zwei offenen Punkte sind nach WP-11/WP-14 verschoben)
  - [x] Stretch-/Voxel-Reste entfernt, README/Version/Dateinamen konsistent
  - [x] Socket, Stabilizer und Spacebar werden gleich und exakt erzeugt (ein Loader, jede Schicht ein Loft, keine Rundungen)
  - [x] Feste Bounding Boxen je Template (nur Prüfung mit Warnung), in der README dokumentiert
  - [x] Stabilizer-Ausschnitte werden nur gedreht, nie gespiegelt; Spacebar-Varianten links/rechts (`--spacebar-position`)
  - [x] STL-Prüfung als ausdrückliche Warnung statt Abbruch, STL wird nicht neu exportiert
  - → KLE-Rotation (`r`) für Cavities: **WP-14**
  - → robustere Spacebar-/Caps-Lock-Erkennung: **WP-13** (Spacebar nach Breite) und **WP-14** (Caps Lock)
- [ ] **WP-03** Testdruck: Mini-Testplatte drucken, Passung und Toleranzen prüfen (Nutzer)
- [~] **WP-04** Layout-Features
  - [x] Stepped Caps Lock (`"l": true`): `--stepped-key standard` oder `wide-caps` (Template `switch_socket_wide-caps.stl` bei `w2`)
  - [x] Option `--single-mesh`: die Platte als ein zusammenhängendes Mesh ohne Lücken
  - getrennte Meshes → mehrere STL-Dateien
  - Pfeilcluster-Box (gefüllte Ecken)
  - → F-Row als ein Mesh: **WP-12**
  - → Caps-Lock-Optionen (große Aussparung, linksbündig, zentriert): nach **WP-09**, falls dann noch gewünscht
- [ ] **WP-05** Plattenform: abgerundete/gefaste Ecken, Standoffs/Spacer
- [ ] **WP-06** Weitere Stabilizer-Varianten (der 7-u-Spacebar ist als **WP-13** ausgegliedert)

### Neue Arbeitspakete

- [x] **WP-07** Repo-Reparatur: Standardpfade, Wide-Caps-Lookup, Tests und Doku wieder konsistent (`wide-shift` → `wide-caps`); Wächter-Tests für die `DEFAULT_*`-Pfade
- [x] **WP-08** Fixes: Stabilizer erst ab 2 u (`DEFAULT_STABILIZER_MIN_UNIT`), KLE-Metadaten (Name/Autor) werden ignoriert, Raw-Data-Validierung, Parser-/Klassifikationstests
- [x] **WP-09** Wide-Caps-Feature testen (`--stepped-key wide-caps`) (Prüfbericht im WP-09 Abschlussbericht)
  - Prüf-WP, **keine Änderung am Generator**: Prüfmatrix (alle Stepped-Layouts × Modus × Rotation), Vorschaubilder in `docs/wide-caps-test/`, Testlücken schließen, Fehler nur berichten
  - Gemessen: Position des Schalterzentrums, Abstand zum Umriss, Stegbreite zu den Nachbar-Cavities, Überlappung
  - Nutzer: feste Bounding Box des Templates bestätigen (gemessen: 23,8125 × 19,05 mm, `TEMPLATE_BOUNDING_BOXES["wide-caps"]` steht noch auf `None`) und anhand der Bilder die Standard-Rotation bestätigen
- [~] **WP-10** Konfigurationsdatei
  - Teil A (reiner Umbau): `Settings` und `TemplateSet` statt der langen Parameterlisten in `generate()` / `build_plate_model()`. Erledigt; vom Planner nachgemessen: die STLs für `stabilizer_orientation`, `jd40` und `stepped-capslock` (wide-caps) sind vor und nach dem Umbau byte-identisch.
  - Teil B: TOML (`tomllib`, Python ≥ 3.11), nur über `--config` (keine automatische Suche), Vorrang CLI > Config > Default, strenge Prüfung, Pfade relativ zum Config-Ordner, `fat_plate_config.example.toml`, `tools/preview.py --config`. Laut Bericht 274 Tests grün; Branch noch nicht auf GitHub, daher vom Planner nicht geprüft.
  - Nachtrag: `--global-transform/--no-global-transform` (positive Form, damit eine Config mit `global_transform = false` auf der CLI überstimmt werden kann)
- [ ] **WP-11** Spacebar-Spiegelung statt links/rechts-Dateien (Voraussetzung: WP-10 gemerged)
  - Gemessen: `stabilzer_spacebar_off-center_left.stl` ist die exakte Spiegelung von `…_right.stl` an der Y-Achse der Template-Koordinaten (Differenzfläche höchstens 9,5e-7 mm² über alle Schichten)
  - Festgelegt (Planner): die **linke** Datei bleibt das Off-Center-Template; die rechte Position entsteht durch Spiegelung **im Template-Koordinatensystem vor der Rotation** (nur so stimmt das Ergebnis für jede Rotationseinstellung mit der bisherigen rechten Datei überein). Exakte Integer-Matrix, kein gespiegelter CAD-Körper.
  - `TemplateSet` bekommt ein Feld `spacebar_off_centered` statt zwei; CLI `--spacebar-off-centered` und Config-Schlüssel `spacebar_off_centered` ersetzen die beiden alten. Die Zuordnung Position → Pfad steht künftig nur noch einmal (heute doppelt).
  - `--spacebar-position` bleibt `centered | off-centered-left | off-centered-right`; die Platte ändert sich nicht (`centered` und `off-centered-left` byte-identisch, `off-centered-right` bis auf Template-Rauschen)
  - AGENTS.md, README und Docstring: Regel „Cutouts werden nie gespiegelt“ bekommt genau diese eine Ausnahme
  - `…_right.stl` bleibt im Repo und wird nur noch von einem Äquivalenztest gelesen; Löschen entscheidet der Nutzer
- [ ] **WP-12** Verschmolzene F-Row
  - Festgelegt (Nutzer, 03.11.2026): Es wird **nur die oberste Reihe** zu einem zusammenhängenden Streifen verbunden, nicht mit dem Hauptblock. Bei einem 100%-Layout sind das Esc, F1–F12, PrtSc, Scroll Lock und Pause Break. Gebraucht wird es vor allem für die G80-3000.
  - Option `--fuse-f-row` (Aufruf in der Config später als Schlüssel); Standard bleibt: aus. „Oberste Reihe“ = alle Tasten mit dem kleinsten KLE-`y`.
  - Umsetzung: die Lückenbrücken von `--single-mesh` (`gap_bridges`) nur für die Tasten dieser Reihe verwenden. Die Lücken im G80-3000-Layout (1 u zwischen Esc und F1, 0,5 u zwischen den F-Gruppen und vor PrtSc) sind weit größer als 2 × Margin, die Brücken füllen sie über die ganze Tastenhöhe.
  - Zusammenspiel mit `--single-mesh`: dann ist die Option wirkungslos (die ganze Platte ist ohnehin verbunden); in der Meldung des Generators ausgeben.
  - Tests: G80-3000-Layout (`kle-jsons/keyboard-layout_100-percent-iso-105-keys_g80-3000.json`) liefert genau einen Teil für die F-Reihe und die übrigen Teile unverändert; ohne Option unverändertes Verhalten.
- [ ] **WP-13** 7-u-Spacebar
  - Template liegt vor (`stabilzer_spacebar_7u.stl`, 128,6008 × 19,05 mm = 6,75 u Zelle), ist aber noch nicht im Generator verdrahtet
  - Spacebar-Templates nach Tastenbreite auswählen (6,25 u / 7 u); unbekannte Breiten ≥ 6 u liefern eine Fehlermeldung statt still das 6,25-u-Template (heute: 6, 7 und 8 u werden alle als 6,25-u-Spacebar behandelt)
  - Feste Bounding Box für das 7-u-Template in Code und README eintragen (heute würde das Laden eine Warnung erzeugen)
- [ ] **WP-14** Parser-Robustheit und Aufräumen (Vorschlag, noch nicht beauftragt)
  - KLE-Rotation (`r`) für Cavities (Footprint und Switch-Zentrum werden gedreht, die Cavity nicht; bis dahin mindestens eine Warnung)
  - Decals (`"d": true`) nicht als Tasten behandeln
  - Caps-Lock-Ausnahme per Label-Vergleich ersetzen (nach WP-08 nur noch für Caps Lock ab 2 u relevant)
  - Platzierungslogik nur einmal (Generator und `tools/preview.py` rechnen sie getrennt)
  - Cavities in einem Schritt verschmelzen (heute eine Schleife mit `fuse`, vermutlich der Grund für die langen Testläufe; erst messen)
  - Modul-Docstring und Meldungstext der STL-Prüfung („So far this was caused by template STLs …“ erscheint bei jedem Problem) aktualisieren

## Laufend (Nutzer)

- [x] **Template-Neubau**: Templates sind exakt neu gebaut (Socket 19,05 × 19,05 mm, Stabilizer 38,1 × 19,05 mm, Spacebar 114,3015 × 19,05 mm), der Generator meldet für diese keine Warnungen mehr.
  - `FLAT_WALL_TOLERANCE` (50 nm) lässt sich noch nicht senken: bei 1e-6 und 1e-7 ändern sich die Eckenzahlen von `stabilizer.stl`, bei 1e-9 lässt sich `stabilizer.stl` nicht mehr loften. Möglich wäre es erst, wenn die Wände der Templates bis auf Float32-Genauigkeit exakt gerade sind.
- [x] **Wide-Caps-Template** liegt im Repo (`switch_socket_wide-caps.stl`). Offen: feste Bounding Box bestätigen (siehe WP-09).
- [x] **7-u-Spacebar-Template** liegt im Repo (`stabilzer_spacebar_7u.stl`); der Generator nutzt es noch nicht (siehe WP-13).
- [ ] Nach WP-11: `stabilzer_spacebar_off-center_right.stl` löschen (und den Eintrag in `.gitignore` entfernen), wenn du sie nicht mehr brauchst.
- [ ] Nach WP-09: Standard-Rotation von `wide-caps` anhand der Bilder in `docs/wide-caps-test/` bestätigen; feste Bounding Box des Wide-Caps-Templates bestätigen und selbst eintragen.
- [ ] `fat_plate_export_example.stl` neu erzeugen, wenn sich die Geometrie ändert.

## Vorschläge (nicht beauftragt)

- **CI:** GitHub Actions führt `python -m pytest` auf Linux aus. Der Stand war zweimal unbemerkt rot (Ordnerumstellung, Rename). Linux fängt zusätzlich Groß-/Kleinschreibung in Pfaden ab, die unter Windows nicht auffällt. Am besten direkt nach WP-07.
- Die schweren Tests (100%-Layout) per Marker abtrennbar machen, sodass ein schneller Lauf möglich ist.
- `tools/check_templates.py`: lädt ein Template wie der Generator und listet seine Warnungen, dazu Koordinaten, die fast, aber nicht exakt gleich sind.
- Versionen in den Requirements festschreiben, damit Ergebnisse auf verschiedenen Rechnern reproduzierbar sind.
- `stabilzer_spacebar_centered.stl` ist nicht byte-identisch mit `stabilzer_spacebar.stl` (gleiche Schichten, Eckenzahl und Maße), wird vom Generator aber nicht gelesen. Klären, ob die Datei bleiben soll.
- `kle-jsons/keyboard-layout.json` ist identisch mit `…_100-percent-iso-105-keys.json`. Klären, ob beides bleiben soll.
- Dateinamen `stabilzer_*.stl` → `stabilizer_*.stl` korrigieren (betrifft Generator, Tests, README, `.gitignore`); jetzt möglich, die Templates sind fertig.

## Übernommene offene Punkte aus der alten TODO.txt

| Punkt                                                    | Zuordnung |
| -------------------------------------------------------- | --------- |
| option for F1–F12 row in one mesh                        | WP-12     |
| option -> create multiple STL files for separated meshes | WP-04     |
| option for rectangular arrow box shape (filled corners)  | WP-04     |
| options for CapsLock: big cutout, left-aligned, centered | WP-04     |
| option for rounded/beveled corners                       | WP-05     |
| option for standoffs/spacer                              | WP-05     |
| add more stabilizer options                              | WP-06     |

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

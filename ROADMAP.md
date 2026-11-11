# Roadmap

Status: `[ ]` offen, `[~]` in Arbeit, `[x]` erledigt.

Stand: `main` @ `7631001` (WP-07 bis WP-12 gemerged, 338 Tests grün laut WP-12-Bericht).

## Reihenfolge

~~WP-07~~ → ~~WP-08~~ → ~~WP-09~~ → ~~WP-10~~ → ~~WP-11~~ → ~~WP-12~~ → ~~WP-13~~ → WP-14. WP-15 ist noch nicht beauftragt und hat niedrige Priorität.

## Arbeitspakete

- [x] **WP-01** Stabilizer-Orientierung + Preview/Tests
  - Orientierung zentral konfigurierbar (`OrientationConfig`: horizontal / vertical / spacebar getrennt, Ganzplatten-Transformation)
  - Preview-Tool (`tools/preview.py`) und pytest-Suite
  - Die Defaults hat der Nutzer nach Sichtprüfung angepasst: horizontal 180°, vertical 90°, spacebar 180°, Platte 180° + Spiegelung an X (= KLE-Y-Umrechnung ohne weitere Drehung); die Ausschnitte werden nur gedreht, nie gespiegelt
- [x] **WP-02** Aufräumen (abgeschlossen; die zwei offenen Punkte sind nach WP-11/WP-15 verschoben)
  - [x] Stretch-/Voxel-Reste entfernt, README/Version/Dateinamen konsistent
  - [x] Socket, Stabilizer und Spacebar werden gleich und exakt erzeugt (ein Loader, jede Schicht ein Loft, keine Rundungen)
  - [x] Feste Bounding Boxen je Template (nur Prüfung mit Warnung), in der README dokumentiert
  - [x] Stabilizer-Ausschnitte werden nur gedreht, nie gespiegelt; Spacebar-Varianten links/rechts (`--spacebar-position`)
  - [x] STL-Prüfung als ausdrückliche Warnung statt Abbruch, STL wird nicht neu exportiert
  - → KLE-Rotation (`r`) für Cavities: **WP-15**
  - → robustere Spacebar-/Caps-Lock-Erkennung: **WP-14** (Spacebar nach Breite) und **WP-15** (Caps Lock)
- [ ] **WP-03** Testdruck: Mini-Testplatte drucken, Passung und Toleranzen prüfen (Nutzer)
- [~] **WP-04** Layout-Features
  - [x] Stepped Caps Lock (`"l": true`): `--stepped-key standard` oder `wide-caps` (Template `switch_socket_wide-caps.stl` bei `w2`)
  - [x] Option `--single-mesh`: die Platte als ein zusammenhängendes Mesh ohne Lücken
  - getrennte Meshes → mehrere STL-Dateien
  - Pfeilcluster-Box (gefüllte Ecken)
  - → F-Row als ein Mesh: **WP-12** (erledigt)
  - → Caps-Lock-Optionen (große Aussparung, linksbündig, zentriert): nach **WP-09**, falls dann noch gewünscht
- [ ] **WP-05** Plattenform: abgerundete/gefaste Ecken, Standoffs/Spacer
- [ ] **WP-06** Weitere Stabilizer-Varianten (der 7-u-Spacebar ist als **WP-14** ausgegliedert)

### Neue Arbeitspakete

- [x] **WP-07** Repo-Reparatur: Standardpfade, Wide-Caps-Lookup, Tests und Doku wieder konsistent (`wide-shift` → `wide-caps`); Wächter-Tests für die `DEFAULT_*`-Pfade
- [x] **WP-08** Fixes: Stabilizer erst ab 2 u (`DEFAULT_STABILIZER_MIN_UNIT`), KLE-Metadaten (Name/Autor) werden ignoriert, Raw-Data-Validierung, Parser-/Klassifikationstests
- [x] **WP-09** Wide-Caps-Feature testen (`--stepped-key wide-caps`) (Prüfbericht im WP-09 Abschlussbericht)
  - Prüf-WP, **keine Änderung am Generator**: Prüfmatrix (alle Stepped-Layouts × Modus × Rotation), Vorschaubilder in `docs/wide-caps-test/`, Testlücken schließen, Fehler nur berichten
  - Gemessen: Position des Schalterzentrums, Abstand zum Umriss, Stegbreite zu den Nachbar-Cavities, Überlappung
  - Nutzer: feste Bounding Box des Templates bestätigen (gemessen: 23,8125 × 19,05 mm, `TEMPLATE_BOUNDING_BOXES["wide-caps"]` steht noch auf `None`) und anhand der Bilder die Standard-Rotation bestätigen
- [x] **WP-10** Konfigurationsdatei: `Settings` und `TemplateSet` statt langer Parameterlisten (Teil A vom Planner nachgemessen: STLs byte-identisch), TOML über `--config` (Vorrang CLI > Config > Default, strenge Prüfung, Pfade relativ zum Config-Ordner), `fat_plate_config.example.toml`, `tools/preview.py --config`, `--global-transform/--no-global-transform`
- [x] **WP-11** Spacebar-Spiegelung statt links/rechts-Dateien: ein Off-Center-Template (die linke Datei), die rechte Position entsteht per exakter Spiegelung im Template-Koordinatensystem vor der Rotation; `…_right.stl` wird nur noch von einem Äquivalenztest gelesen (Löschen entscheidet der Nutzer, siehe „Laufend“)
- [x] **WP-12** Verschmolzene F-Reihe (`--fuse-f-row`)
  - Festgelegt (Nutzer): nur die **oberste Reihe** wird zu einem Streifen verbunden, nicht mit dem Hauptblock; Standard: aus. Gebraucht vor allem für die G80-3000.
  - „Oberste Reihe“ = unrotierte Tasten mit dem kleinsten KLE-`y`. Die Lückenbrücken von `--single-mesh` (`gap_bridges`) werden nur über diese Tasten gebildet. Vorgerechnet: G80-3000 und ISO-105 je 16 Tasten, 9 → 5 Plattenteile; TKL 8 → 4; JD40 unverändert.
  - Mit `--single-mesh` wirkungslos (Hinweis in der Ausgabe). Neuer Config-Schlüssel `fuse_f_row`, CLI `--fuse-f-row/--no-fuse-f-row`.
  - Ohne die Option byte-identisch zu vorher.
  - Umgesetzt: `top_row_keys()` (unrotierte Tasten mit dem kleinsten KLE-`y`) und `plate_footprint(..., fuse_top_row=False)`; `Settings.fuse_f_row`, CLI `--fuse-f-row/--no-fuse-f-row`, Config-Schlüssel `fuse_f_row`. Nachgemessen: Plattenteile vorher → nachher G80-3000 und ISO-105 9 → 5, TKL 8 → 4, JD40 unverändert (1); die STLs für `stabilizer_orientation`, `jd40` und `stepped-capslock` (wide-caps) sind ohne Option byte-identisch zu `392162d`; `--fuse-f-row --single-mesh` ergibt dieselbe Platte wie `--single-mesh` allein. 338 Tests grün.
- [x] **WP-13** KLE-Parser wie der Editor (Bugfix, Priorität 1)
  - Auslöser: `kle-jsons/keyboard-layout_065-percent-iso_royal-kludge-rk65.json` (vom Editor exportiert): Del liegt bei (15, 6) statt (15, 1); `…_rk65_clean.json` ist das richtige Ergebnis.
  - Ursache: Im Editor setzt `rx` **oder** `ry` die aktuelle Position auf `(rx, ry)` (der nicht genannte Wert bleibt auf dem zuletzt gesetzten). `parse_kle()` setzt bei `rx` nur `x` und bei `ry` nur `y`. Gleiches Problem im Ergodox-Layout (Reihe 23: `rx` ohne `ry`, 5 Tasten falsch). Alle anderen Layouts in `kle-jsons/` ändern sich nicht (mit Prototyp verglichen).
  - Mit dabei, weil dieselbe Funktion: Eigenschaften (`w`, `h`, `x2`, …) gelten bis zur nächsten Taste (mehrere Objekte vor einer Taste), Decals (`"d": true`) sind keine Tasten, `r`/`rx`/`ry` nur am Reihenanfang (sonst Fehler wie im Editor)
  - Tests: RK65-Paar (fehlerhaft = bereinigt), Ergodox-Position, Tabelle kleiner Layouts, Fehlerfall; einmaliger Nachweis, dass alle übrigen Layouts unverändert parsen
  - Umgesetzt: `parse_kle()` setzt bei `rx`/`ry` die Position auf `(rx, ry)`, Eigenschaften gelten bis zur nächsten Taste, Decals werden übersprungen (ihre Breite zählt), `r`/`rx`/`ry` nur am Reihenanfang. Nachgemessen: alle 20 Layouts in `kle-jsons/` und `tests/layouts/` vor/nach verglichen; geändert sind nur RK65 (Del, 1 Taste) und Ergodox (6 Tasten, nicht 5: Reihe 23 bis 25 hängen alle an `rx = 13`); RK65 und `…_rk65_clean.json` ergeben byte-identische STLs; die STLs für `stabilizer_orientation`, `jd40` und `stepped-capslock` (wide-caps) sind byte-identisch zu vorher. 370 Tests grün.
- [x] **WP-14** Template-Dateien umbenennen
  - Stabilizer- und Spacebar-Templates sind nach Länge und Position einheitlich benannt; das doppelte centered Spacebar-Template ist entfernt.
  - Die neuen 6u- und 7u-Templates liegen vor, werden aber erst in WP-15 nach Tastenbreite verdrahtet.
- [x] **WP-15** Stabilizer- und Spacebar-Templates nach Tastenbreite
  - KLE-Rotation (`r`) für Cavities: Footprint und Switch-Zentrum werden gedreht, die Cavity nicht. **Konkret betroffen:** `kle-jsons/ergodox_split_ergo_67-keys.json` (12 Tasten mit ±30°). Gemessen: 10 von 76 Cavities ragen aus dem Plattenumriss (bis 27 mm²), ohne dass der Generator warnt. Mindestens eine Warnung oder ein Fehler, besser die echte Unterstützung. Nutzer (Stand jetzt): Layouts mit diagonalen Teilen sollen möglich sein, aber niedrige Priorität. Bis dahin mindestens eine Warnung statt stillem Falschbau.
  - Caps-Lock-Ausnahme per Label-Vergleich ersetzen (nach WP-08 nur noch für Caps Lock ab 2 u relevant)
  - Platzierungslogik nur einmal (Generator und `tools/preview.py` rechnen sie getrennt)
  - Cavities in einem Schritt verschmelzen (heute eine Schleife mit `fuse`, vermutlich der Grund für die langen Testläufe; erst messen)
  - Modul-Docstring und Meldungstext der STL-Prüfung („So far this was caused by template STLs …“ erscheint bei jedem Problem) aktualisieren

## Laufend (Nutzer)

- [ ] 3-u-Template bauen und `stabilizer_2-00u.stl` als Ersatz entfernen.
- [ ] Bounding Boxes der 6u- und 7u-Templates festlegen.
- [ ] Orientierung der 6u- und 7u-Templates anhand der Vorschauen in `docs/spacebar-sizes/` bestätigen.

- [x] **Template-Neubau**: Templates sind exakt neu gebaut (Socket 19,05 × 19,05 mm, Stabilizer 38,1 × 19,05 mm, Spacebar 114,3015 × 19,05 mm), der Generator meldet für diese keine Warnungen mehr.
  - `FLAT_WALL_TOLERANCE` (50 nm) lässt sich noch nicht senken: bei 1e-6 und 1e-7 ändern sich die Eckenzahlen von `stabilizer_2-00u.stl`, bei 1e-9 lässt sich `stabilizer_2-00u.stl` nicht mehr loften. Möglich wäre es erst, wenn die Wände der Templates bis auf Float32-Genauigkeit exakt gerade sind.
- [x] **Wide-Caps-Template** liegt im Repo (`switch_socket_wide-caps.stl`). Offen: feste Bounding Box bestätigen (siehe WP-09).
- [x] **7-u-Spacebar-Template** liegt im Repo (`stabilizer_7-00u_centered.stl`) und wird nach Breite verwendet.
- [ ] Nach WP-09: Standard-Rotation von `wide-caps` anhand der Bilder in `docs/wide-caps-test/` bestätigen; feste Bounding Box des Wide-Caps-Templates bestätigen und selbst eintragen.
- [ ] `fat_plate_export_example.stl` neu erzeugen, wenn sich die Geometrie ändert.

## Vorschläge (nicht beauftragt)

- **Layout-Paare als Regressionstests:** Wird ein Layout falsch gelesen, legt der Nutzer den fehlerhaften Export und eine von Hand bereinigte Fassung mit demselben Ergebnis (`…_clean.json`) in `kle-jsons/` ab. Der Implementer ergänzt einen Test, der beide vergleicht. So ist der RK65-Fehler gefunden worden; das Verfahren lohnt sich für jeden weiteren Fall.

- **CI:** GitHub Actions führt `python -m pytest` auf Linux aus. Der Stand war zweimal unbemerkt rot (Ordnerumstellung, Rename). Linux fängt zusätzlich Groß-/Kleinschreibung in Pfaden ab, die unter Windows nicht auffällt. Am besten direkt nach WP-07.

- Die schweren Tests (100%-Layout) per Marker abtrennbar machen, sodass ein schneller Lauf möglich ist.

- `tools/check_templates.py`: lädt ein Template wie der Generator und listet seine Warnungen, dazu Koordinaten, die fast, aber nicht exakt gleich sind.

- Versionen in den Requirements festschreiben, damit Ergebnisse auf verschiedenen Rechnern reproduzierbar sind.


- `kle-jsons/keyboard-layout.json` ist identisch mit `…_100-percent-iso-105-keys.json`. Klären, ob beides bleiben soll.

- Dateinamen der neuen Layouts angleichen: `kle-jsons/leyboard-layout_065-percent-iso_royal-kludge-rk65.json` hat einen Tippfehler (`leyboard`), `ergodox_split_ergo_67-keys.json` hat nicht das Präfix `keyboard-layout_`.


## Übernommene offene Punkte aus der alten TODO.txt

| Punkt                                                    | Zuordnung        |
| -------------------------------------------------------- | ---------------- |
| option for F1–F12 row in one mesh                        | WP-12 (erledigt) |
| option -> create multiple STL files for separated meshes | WP-04            |
| option for rectangular arrow box shape (filled corners)  | WP-04            |
| options for CapsLock: big cutout, left-aligned, centered | WP-04            |
| option for rounded/beveled corners                       | WP-05            |
| option for standoffs/spacer                              | WP-05            |
| add more stabilizer options                              | WP-06            |

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

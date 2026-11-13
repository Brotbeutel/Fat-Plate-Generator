# Roadmap

Status: `[ ]` offen, `[~]` in Arbeit, `[x]` erledigt.

Stand: `main` @ `98a9f94` (WP-07 bis WP-15 gemerged; 397 Tests grün, vom Planner in einem frischen Clone gemessen).

## Reihenfolge

~~WP-07~~ → ~~WP-08~~ → ~~WP-09~~ → ~~WP-10~~ → ~~WP-11~~ → ~~WP-12~~ → ~~WP-13~~ → ~~WP-14~~ → ~~WP-15~~ → ~~WP-16~~ → ~~WP-17~~. Alle bisher beauftragten Pakete sind durch. Offen sind WP-03 (Testdruck, Nutzer), der Rest von WP-04, WP-05, WP-06, WP-18 (Spiegel-Funktion für Stabilizer, noch nicht beauftragt) und der Vorschlag WP-19; die nächste Reihenfolge legt der Nutzer fest.

## Arbeitspakete

- [x] **WP-01** Stabilizer-Orientierung + Preview/Tests
  - Orientierung zentral konfigurierbar (`OrientationConfig`: horizontal / vertical / spacebar getrennt, Ganzplatten-Transformation)
  - Preview-Tool (`tools/preview.py`) und pytest-Suite
  - Die Defaults hat der Nutzer nach Sichtprüfung angepasst: horizontal 180°, vertical 90°, spacebar 180°, Platte 180° + Spiegelung an X (= KLE-Y-Umrechnung ohne weitere Drehung); die Ausschnitte werden nur gedreht, nie gespiegelt (seit **WP-17** sind diese Werte die feste Grundausrichtung im Code; die Optionen sind Zusatzdrehungen mit Standard 0)
- [x] **WP-02** Aufräumen (abgeschlossen; die zwei offenen Punkte sind nach WP-15/WP-19 verschoben)
  - [x] Stretch-/Voxel-Reste entfernt, README/Version/Dateinamen konsistent
  - [x] Socket, Stabilizer und Spacebar werden gleich und exakt erzeugt (ein Loader, jede Schicht ein Loft, keine Rundungen)
  - [x] Feste Bounding Boxen je Template (nur Prüfung mit Warnung), in der README dokumentiert
  - [x] Stabilizer-Ausschnitte werden nur gedreht, nie gespiegelt; Spacebar-Varianten links/rechts (`--spacebar-position`)
  - [x] STL-Prüfung als ausdrückliche Warnung statt Abbruch, STL wird nicht neu exportiert
  - → KLE-Rotation (`r`) für Cavities: **WP-19**
  - → robustere Spacebar-/Caps-Lock-Erkennung: **WP-15** (Spacebar nach Breite, erledigt) und **WP-19** (Caps Lock)
- [ ] **WP-03** Testdruck: Mini-Testplatte drucken, Passung und Toleranzen prüfen (Nutzer)
- [~] **WP-04** Layout-Features
  - [x] Stepped Caps Lock (`"l": true`): `--stepped-key standard` oder `wide-caps` (Template `switch_socket_wide-caps.stl` bei `w2`)
  - [x] Option `--single-mesh`: die Platte als ein zusammenhängendes Mesh ohne Lücken
  - getrennte Meshes → mehrere STL-Dateien
  - Pfeilcluster-Box (gefüllte Ecken)
  - → F-Row als ein Mesh: **WP-12** (erledigt)
  - → Caps-Lock-Optionen (große Aussparung, linksbündig, zentriert): nach **WP-09**, falls dann noch gewünscht
- [ ] **WP-05** Plattenform: abgerundete/gefaste Ecken, Standoffs/Spacer
- [ ] **WP-06** Weitere Stabilizer-Varianten (7 u und 6 u sind mit **WP-15**, 3 u mit **WP-16** erledigt)

### Neue Arbeitspakete

- [x] **WP-07** Repo-Reparatur: Standardpfade, Wide-Caps-Lookup, Tests und Doku wieder konsistent (`wide-shift` → `wide-caps`); Wächter-Tests für die `DEFAULT_*`-Pfade
- [x] **WP-08** Fixes: Stabilizer erst ab 2 u (`DEFAULT_STABILIZER_MIN_UNIT`), KLE-Metadaten (Name/Autor) werden ignoriert, Raw-Data-Validierung, Parser-/Klassifikationstests
- [x] **WP-09** Wide-Caps-Feature testen (`--stepped-key wide-caps`) (Prüfbericht im WP-09 Abschlussbericht)
  - Prüf-WP, **keine Änderung am Generator**: Prüfmatrix (alle Stepped-Layouts × Modus × Rotation), Vorschaubilder in `docs/wide-caps-test/`, Testlücken schließen, Fehler nur berichten
  - Gemessen: Position des Schalterzentrums, Abstand zum Umriss, Stegbreite zu den Nachbar-Cavities, Überlappung
  - Standard-Rotation von `wide-caps` (180°) vom Nutzer bestätigt (entspricht `docs/wide-caps-test/stepped-capslock_wide-caps_rot180.png`). Offen für den Nutzer: feste Bounding Box eintragen (siehe „Laufend“).
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
  - Namensschema `stabilizer_<Länge>u[_<Position>].stl`: `stabilizer_2-00u`, `stabilizer_6-25u_centered/_off-center`, `stabilizer_7-00u_centered` (umbenannt), `stabilizer_6-00u_centered/_off-center` (neu, vom Nutzer); das identische Duplikat `stabilzer_spacebar_centered.stl` ist gelöscht
  - Vom Planner nachgemessen: Der Stand nach WP-14 erzeugt dieselben STLs wie vorher (SHA256 identisch)
- [x] **WP-15** Stabilizer- und Spacebar-Templates nach Tastenbreite
  - Zuordnung: 2 bis <3 u → 2-u-Stabilizer; 3 u → Ersatz 2-u-Template mit ausdrücklicher Warnung (3-u-Template fehlt); 6 u, 6,25 u (auch 6,5 u), 7 u (auch 8 u) → eigene Spacebar-Templates; Off-Center nur für 6 u und 6,25 u (linke Position per Spiegelung); alle anderen Breiten sind ein Fehler. Die Spacebar wird an der Breite erkannt, nicht mehr am Label.
  - Einstellungen: acht `TemplateSet`-Felder mit den Dateinamen als Config-Schlüssel, `--stabilizer-2u` ersetzt `--stabilizer`, die Spacebar-Pfade sind nur über die Config änderbar. Bounding Boxen von 6 u und 7 u sind `(None, None)` (nur Höhe geprüft).
  - Vom Planner nachgemessen: G80-1800 (6 u) nutzt das 6u-Template, ISO-102/G80-3000 (7 u) das 7u-Template, beide ohne Warnung und mit bestandener STL-Prüfung; 3 u gibt die Warnung und `Done, with warnings.`; 4 u und 7 u mit Off-Center brechen mit klarer Meldung ab; eine 6,25-u-Taste mit Label „Space“ ist jetzt eine Spacebar.
  - Hinweis: `stabilizer_2-00u.stl` wurde im Commit `557deea` (WP-15) vom Nutzer leicht geändert (Schnittdifferenz 3e-5 mm²). Dadurch ändern sich die Referenz-Hashes aller Platten mit 2-u-Stabilizern (siehe „Regression-Referenzen“), ohne dass der Generator etwas damit zu tun hat.
  - Kleinigkeit: die Warnung schreibt „3u key (1 keys; …)“ (Mehrzahl bei 1)
- [x] **WP-16** 3-u-Stabilizer anschließen
  - Tasten mit genau 3 u Länge (waagerecht `w = 3`, senkrecht `h = 3`) nutzen `stl-templates/stabilizer_3-00u.stl` (Art `stabilizer-3u`); der Ersatz (2-u-Template plus Warnung) ist entfernt, samt der Ersatz-Liste im `PlateModel`, dem zugehörigen Abschnitt der Ausgabe, der Wirkung auf `Done, with warnings.` und den Tests dafür. Alle anderen Zuordnungsregeln bleiben; 3 < L < 6 ist weiter ein Fehler, die Meldung führt 3u als unterstützte Breite.
  - Einstellungen: `TemplateSet.stabilizer_3u`, `DEFAULT_STABILIZER_3U`, Config-Schlüssel `templates.stabilizer_3u`, `--stabilizer-3u PATH`.
  - Bounding Box: `TEMPLATE_BOUNDING_BOXES["stabilizer-3u"] = (None, None)` (nur die Höhe wird geprüft); gemessen 52,3993 × 19,05 mm. Der Wert ist Sache des Nutzers (siehe „Laufend“).
  - Vorschaubilder einer waagerechten und einer senkrechten 3-u-Taste: `docs/stabilizer-sizes/3u_horizontal.png`, `docs/stabilizer-sizes/3u_vertical.png`.
  - Die fünf Regression-Referenzen (siehe unten) sind byte-identisch geblieben.
- [x] **WP-17** Rotations- und Plattentransform-Defaults auf 0
  - Alle Rotationsoptionen (`stab_rotation_*`, `wide_caps_rotation`, `global_rotation`) haben Standard 0, `global_mirror_x` ist standardmäßig aus; sie sind Zusatzdrehungen (Offsets). Die bisherigen Werte sind die feste, benannte Grundausrichtung im Code: `TEMPLATE_BASE_ROTATION` (horizontal 180, vertical 90, spacebar 180, wide-caps 180), `CUTOUT_FRAME_ROTATION` (180) und `KLE_TO_CAD_MATRIX` ((1, 0, 0, -1)). Sie können auf 0 gehen, sobald die Templates in Blender so gedreht sind, dass 0 passt.
  - Es ändert sich keine Geometrie: jede Platte mit Standardeinstellungen ist byte-identisch. Alte Aufrufe und Configs müssen umgerechnet werden (Tabelle in der README, Abschnitt „Stabilizer Orientation“).
- [ ] **WP-18** Spiegel-Funktion für Stabilizer (noch nicht beauftragt; im Prompt von WP-17 genannt)
- [ ] **WP-19** Parser-Robustheit und Aufräumen (Vorschlag, noch nicht beauftragt; hieß zuvor WP-16 und kurz WP-17, diese Nummern gingen an den 3-u-Stabilizer und die Null-Defaults)
  - KLE-Rotation (`r`) für Cavities: Footprint und Switch-Zentrum werden gedreht, die Cavity nicht. **Konkret betroffen:** `kle-jsons/ergodox_split_ergo_67-keys.json` (12 Tasten mit ±30°). Gemessen: 10 von 76 Cavities ragen aus dem Plattenumriss (bis 27 mm²), ohne dass der Generator warnt. Nutzer: Layouts mit diagonalen Teilen sollen möglich sein, niedrige Priorität. Bis dahin mindestens eine Warnung statt stillem Falschbau.
  - Caps-Lock-Ausnahme per Label-Vergleich ersetzen (nach WP-08 nur noch für Caps Lock ab 2 u relevant)
  - Platzierungslogik nur einmal (Generator und `tools/preview.py` rechnen sie getrennt)
  - Cavities in einem Schritt verschmelzen (heute eine Schleife mit `fuse`, vermutlich der Grund für die langen Testläufe; erst messen)
  - Modul-Docstring und Meldungstext der STL-Prüfung („So far this was caused by template STLs …“ erscheint bei jedem Problem) aktualisieren

## Laufend (Nutzer)

- [x] **Template-Neubau**: Templates sind exakt neu gebaut (Socket 19,05 × 19,05 mm, Stabilizer 38,1 × 19,05 mm, Spacebar 114,3015 × 19,05 mm), der Generator meldet für diese keine Warnungen mehr.
  - `FLAT_WALL_TOLERANCE` (50 nm) lässt sich noch nicht senken: bei 1e-6 und 1e-7 ändern sich die Eckenzahlen von `stabilizer_2-00u.stl`, bei 1e-9 lässt sich `stabilizer_2-00u.stl` nicht mehr loften. Möglich wäre es erst, wenn die Wände der Templates bis auf Float32-Genauigkeit exakt gerade sind.
- [x] Templates liegen im Repo: Wide-Caps, 6 u (zentriert und Off-Center), 7 u; der Generator nutzt sie.
- [x] **3-u-Stabilizer-Template**: liegt im Repo (`stabilizer_3-00u.stl`), der Generator nutzt es; der Ersatz in der Zuordnung ist mit **WP-16** entfernt.
- [ ] **Bounding Boxen** selbst festlegen: `TEMPLATE_BOUNDING_BOXES` in `fat_plate_generator.py` (Einträge `wide-caps`, `stabilizer-3u`, `spacebar-6u`, `spacebar-7u`, jetzt `(None, None)`) und die Tabelle „Fixed bounding boxes“ in der README. Gemessen: Wide-Caps 23,8125 × 19,05 mm, 3 u 52,3993 × 19,05 mm, 6 u 109,3004 × 19,05 mm, 7 u 128,6008 × 19,05 mm.
- [ ] **Orientierung** der 6u- und 7u-Templates anhand der Bilder in `docs/spacebar-sizes/` bestätigen. (Der Planner hat 6 u und 6,25 u verglichen: Schalter rechts von der Mitte, Kerben zur Tippseite, beide gleich; 7 u bitte selbst ansehen.)
- [ ] **Orientierung** des 3-u-Templates anhand der Bilder in `docs/stabilizer-sizes/` bestätigen (waagerecht und senkrecht; die Bilder sind unbewertet).
- [ ] `fat_plate_export_example.stl` neu erzeugen, wenn sich die Geometrie ändert.

## Regression-Referenzen

SHA256-Anfang der STLs, mit denen die Implementer „keine Änderung“ nachweisen (Linux, Python 3.12, CadQuery 2.8, vom Planner gemessen; die Hashes ändern sich nur, wenn sich ein Template-STL ändert, dann trägt der Planner sie neu ein):

| Aufruf | SHA256 (Anfang) |
| --- | --- |
| `--json tests/layouts/stabilizer_orientation.json` | `91b460a5…` |
| dasselbe mit `--spacebar-position off-centered-left` | `07c2c64e…` |
| dasselbe mit `--spacebar-position off-centered-right` | `71d4c0db…` |
| `--json kle-jsons/keyboard-layout_040-percent_jd40.json` | `74c0c55c…` |
| `--json kle-jsons/test_stepped-capslock.json --stepped-key wide-caps` | `7642cc2c…` |

Vor `557deea` galt für das erste Layout `34ed1d42…` (alte 2-u-Stabilizer-Datei); die ältere Datei hieß außerdem `kle-jsons/stepped-capslock.json`.

## Vorschläge (nicht beauftragt)

- **`.gitignore` für Patch-Dateien:** Dort stehen einzelne Namen (`wp-10-teil-b.patch`, `wp-12-fuse-f-row.patch`); ein allgemeines `*.patch` würde auch künftige Patch-Dateien abfangen (die Patch-Dateien im Repo sind inzwischen entfernt).

- **Layout-Paare als Regressionstests:** Wird ein Layout falsch gelesen, legt der Nutzer den fehlerhaften Export und eine von Hand bereinigte Fassung mit demselben Ergebnis (`…_clean.json`) in `kle-jsons/` ab. Der Implementer ergänzt einen Test, der beide vergleicht. So ist der RK65-Fehler gefunden worden; das Verfahren lohnt sich für jeden weiteren Fall.

- **CI:** GitHub Actions führt `python -m pytest` auf Linux aus. Der Stand war zweimal unbemerkt rot (Ordnerumstellung, Rename). Linux fängt zusätzlich Groß-/Kleinschreibung in Pfaden ab, die unter Windows nicht auffällt. Am besten direkt nach WP-07.

- Die schweren Tests (100%-Layout) per Marker abtrennbar machen, sodass ein schneller Lauf möglich ist. Die Suite hat jetzt 397 Tests und läuft mehrere Minuten (7 Minuten, als noch andere Prozesse liefen).

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

# AGENTS.md – Projektregeln

Gilt für alle Agenten/Implementer, die an diesem Repository arbeiten.

## Arbeitsweise

- Ein Arbeitspaket (WP) zugleich. Branch pro WP: `wp-NN-kurzname`. Kleine Commits im Stil von Conventional Commits. Den Merge macht der Nutzer.
- Das aktuelle WP wird genau so umgesetzt wie beschrieben, nicht mehr. Dinge außerhalb des WP höchstens im Abschlussbericht erwähnen.
- Bei Unklarheit nachfragen statt raten.
- Kommunikation auf Deutsch; Code, Kommentare und Commit-Messages auf Englisch.
- Vor Beginn `git fetch` und auf dem aktuellen `origin/main` aufsetzen. Der Nutzer committet und pusht auch selbst (Templates, Beispiel-STL, Einstellungen). Fremde Änderungen werden nie überschrieben.
- Legt der Nutzer zusätzliche Dateien ins Repo (z. B. eine alternative Version des Generators), zuerst mit dem aktuellen Stand vergleichen, dann gezielt übernehmen und im Bericht nennen.

## Projektüberblick

- `fat_plate_generator.py`: die Anwendung. Kern: `build_plate_model()` (Platte bauen), `generate()` (Export), `validate_exported_stl()` (Prüfung), `OrientationConfig` (zentrale Orientierungs-Defaults), `classify_key()` (normal / stabilized / spacebar).
- `switch_socket.stl`, `stabilizer.stl`, `stabilzer_spacebar*.stl`: Template-STLs. Die Quellen liegen in `blender-files/`.
- `tools/preview.py`: Draufsicht-PNG einer erzeugten STL.
- `tests/`: pytest-Suite. `tests/layouts/stabilizer_orientation.json` ist das Testlayout.
- `docs/`: Preview-Bilder. `ROADMAP.md`, `CHANGELOG.md`, `README.md`: Plan, Änderungen, Anleitung.

## Befehle (PowerShell)

```powershell
python -m pip install -r requirements-dev.txt   # einmalig, inkl. Tests und Preview
python -m pytest                                # Tests
python .\fat_plate_generator.py                 # Beispiel erzeugen
python .\tools\preview.py plate.stl --layout my_layout.json --output plate.png
```

## Geometrie und Genauigkeit

- Keine Werte runden, auf ein Raster snappen oder glätten. Alles bleibt präzise und exakt. Ungenauigkeiten werden an der Quelle behoben (Blender-Dateien, Templates), nicht im Code kaschiert. Mängel in Templates im Bericht melden, nicht verstecken.
- Transformationsreihenfolge: Rotation je Stabilizer um dessen Switch-Zentrum, dann Gesamttransformation um den Ursprung, dann Verschiebung, sodass die Bounding-Box bei (0, 0) beginnt. Rotationen und Spiegelung sind exakte Integer-Matrizen auf den 2D-Daten, es entstehen keine gespiegelten CAD-Körper.
- Die Orientierungs-Defaults stehen zentral in `OrientationConfig`. Die Werte hat der Nutzer nach Sichtprüfung festgelegt; nicht ohne Auftrag ändern.
- Die exportierte STL wird nur im Speicher validiert, nie repariert, nach Komponenten gefiltert oder neu exportiert.

## Dateien und Abhängigkeiten

- Keine Dateien umbenennen oder verschieben und keine Template-STLs ändern, außer das WP verlangt es. Die Templates baut der Nutzer in Blender; auch den Tippfehler „stabilzer" nicht korrigieren, solange das nicht beauftragt ist.
- Neue Dependencies nur mit Begründung. Dev-Tools gehören in `requirements-dev.txt`, nicht in `requirements.txt`.
- Generierte STLs nicht committen. Ausnahmen: die Template-STLs und `fat_plate_export_example.stl`.
- Zeilenenden bestehender Dateien nicht ändern (`.gitignore` hat CRLF, alle anderen Dateien LF).

## Tests

- `python -m pytest` vor jedem Abschluss. Der Lauf dauert mehrere Minuten, weil das 100%-Layout einmal pro Lauf gebaut wird.
- Neue Funktionalität bekommt Tests. Erwartungen wenn möglich aus der Konfiguration ableiten, statt Zahlen festzuschreiben.
- Tests, die exakte Templates voraussetzen, tragen den Marker `TEMPLATE_DEFECT` (xfail, nicht strikt). Marker nur mit Begründung und Eintrag in `ROADMAP.md` setzen und entfernen, sobald die Templates exakt sind.

## Kompatibilität und Doku

- Windows-kompatibel: `pathlib` verwenden, keine Shell-Annahmen (Nutzer arbeitet mit PowerShell).
- README bei CLI-Änderungen aktuell halten, `CHANGELOG.md` bei jeder sichtbaren Änderung ergänzen, Status in `ROADMAP.md` pflegen.
- Die Versionsnummer steht in `VERSION` (Generator) und im Titel der README. Erhöhen macht der Nutzer.

## Abschluss eines WP

- Am Ende immer den Abschlussbericht im vom WP vorgegebenen Format liefern.
- Definition of Done: Akzeptanzkriterien erfüllt, Tests grün (`python -m pytest`), Bericht geliefert.

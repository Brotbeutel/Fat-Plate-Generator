# AGENTS.md – Projektregeln

Gilt für alle Agenten/Implementer, die an diesem Repository arbeiten.

## Arbeitsweise

- Ein Arbeitspaket (WP) zugleich. Branch pro WP: `wp-NN-kurzname`. Kleine Commits im Stil von Conventional Commits. Den Merge macht der Nutzer.
- Das aktuelle WP wird genau so umgesetzt wie beschrieben, nicht mehr. Dinge außerhalb des WP höchstens im Abschlussbericht erwähnen.
- Bei Unklarheit nachfragen statt raten.
- Kommunikation auf Deutsch; Code, Kommentare und Commit-Messages auf Englisch.

## Dateien und Abhängigkeiten

- Keine Dateien umbenennen oder verschieben und keine Template-STLs ändern, außer das WP verlangt es.
- Neue Dependencies nur mit Begründung. Dev-Tools gehören in `requirements-dev.txt`, nicht in `requirements.txt`.
- Generierte STLs nicht committen. Ausnahmen: die Template-STLs und `fat_plate_export_example.stl`.

## Kompatibilität und Doku

- Windows-kompatibel: `pathlib` verwenden, keine Shell-Annahmen (Nutzer arbeitet mit PowerShell).
- README bei CLI-Änderungen aktuell halten.

## Abschluss eines WP

- Am Ende immer den Abschlussbericht im vom WP vorgegebenen Format liefern.
- Definition of Done: Akzeptanzkriterien erfüllt, Tests grün (`python -m pytest`), Bericht geliefert.

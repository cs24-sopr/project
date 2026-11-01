---
name: export-status-pdf
description: >-
  Exports and bundles weekly sprint status reports from all project teams
  into a single consolidated PDF document for course submission.
---

# Statusberichte als PDF bündeln

Dieses Skill führt die von den Teams ausgearbeiteten MDX-Statusberichte
direkt und ungefiltert in einem gemeinsamen PDF-Dokument zusammen.

## Wann dieses Skill verwendet wird

- Zur Vorbereitung der wöchentlichen Abgabe an die Dozentin.
- Zum Bündeln aller vorliegenden Teamberichte (`sprint-*.mdx` oder `kw*.mdx`)
  in eine PDF-Sammlung ohne zusätzliche Übersichtsseiten oder Kommentare.

## Vorbereitung: Neueste Stände abrufen

Vor dem Export die neuesten Remote-Stände einbinden:

```bash
git fetch origin --prune
git merge origin/main
```

Falls ein Team auf einem eigenen Branch eingereicht hat (z. B.
`origin/research/team-update`), diesen ebenfalls mergen.

## Befehle zur Ausführung

### 1. Prüfmodus (nur gefundene Berichte auflisten)

```bash
python3 scripts/export_status_pdf.py --sprint 1 --check-only
```

Listet die gefundenen Berichtsdateien je Team sowie fehlende Teams auf.

### 2. PDF-Sammlung generieren

```bash
python3 scripts/export_status_pdf.py --sprint 1
```

Erzeugt standardmäßig:
`docs/content/project/statusberichte/Sprint_1_Statusberichte.pdf`.

Jeder Teambericht beginnt auf einer neuen Seite und wird mit originalgetreuem
Markdown-Layout (Überschriften, Listen, Checkboxen, Tabellen) formatiert.

Optionale Parameter:
- `--sprint <NUMMER>`: Sprintnummer (Standard: 1).
- `--output <PFAD>`: Zielpfad für die PDF-Datei.

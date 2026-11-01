---
name: export-status-pdf
description: >-
  Exports and bundles weekly sprint status reports from all project teams
  into a single consolidated PDF document for course submission.
---

# Statusberichte als PDF exportieren

Dieses Skill bündelt die wöchentlichen Statusberichte aller Projektteams zu
einem PDF-Dokument für die Abgabe an die Dozentin.

## Wann dieses Skill verwendet wird

- Zur Vorbereitung der wöchentlichen Abgabe an die Dozentin (Stichtag:
  Sonntag 23:59 Uhr bzw. Montag 09:00 Uhr).
- Zur Prüfung, welche Teams ihr Statusprotokoll vollständig eingereicht haben
  und welche noch fehlen.
- Zum Generieren eines gebündelten PDF-Dokuments mit Deckblatt,
  Ampelübersicht, Detailberichten und Mängelliste.

## Vorbereitung: Neueste Remote-Stände abrufen

Vor dem Export immer den neuesten Stand aus dem Remote-Repository laden, da
Teams ihre Berichte auf `main` oder Team-Branches einreichen:

```bash
git fetch origin --prune
git merge origin/main
```

Falls ein Team auf einem separaten Branch eingereicht hat (z. B.
`origin/research/team-update`), diesen Branch ebenfalls mergen.

## Verfügbare Befehle

### 1. Prüfmodus (nur Status anzeigen, kein PDF schreiben)

```bash
python3 scripts/export_status_pdf.py --sprint 1 --check-only
```

Gibt eine kompakte Übersicht aller Teams mit aktuellem Einreichungsstatus,
Ampelbewertung, erkannter Berichtsdatei und Ansprechperson aus.

### 2. PDF-Gesamtexport erstellen

```bash
python3 scripts/export_status_pdf.py --sprint 1
```

Erstellt standardmäßig die Datei:
`docs/content/project/statusberichte/Sprint_1_Gesamtstatus.pdf`.

Unterstützte Namensschemata je Team:
- Sprint-Schema: `sprint-1.mdx`
- Kalenderwochen-Schema: `kw44.mdx`

Optionale Parameter:
- `--sprint <NUMMER>`: Sprintnummer (Standard: 1).
- `--output <PFAD>`: Zielpfad für die PDF-Datei.
- `--separate-missing`: Erzeugt separate Platzhalterseiten für fehlende Teams
  statt einer kompakten Sammelseite.

## Struktur der Statusberichte im Repository

- Basisordner: `docs/content/project/statusberichte/`
- Team-Ordner:
  - `orga-lead-infra/` (Organisation, Leitung & Infrastruktur)
  - `builder/` (Builder-Team)
  - `asset-design/` (Asset-Design)
  - `coding-interactions/` (Coding & Interactions)
  - `recherche-publishing-courses/` (Recherche, Publishing & Courses)
  - `story-design/` (Story-Design)
- Vorlage: `docs/content/project/vorlagen/team-update.mdx`

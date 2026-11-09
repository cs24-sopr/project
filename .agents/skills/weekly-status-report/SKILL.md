---
name: weekly-status-report
description: >-
  Creates a standardized weekly status report MDX file for a project team
  by reading closed GitHub issues, determining sprint/week context, and
  filling in the official report template while asking for clarification
  on any uncertain details.
---

# Wöchentlichen Statusbericht erstellen

Dieses Skill unterstützt Projektteams und Agenten bei der automatisierten
und standardisierten Erstellung der wöchentlichen Statusberichte
(Abgabe-Artefakte für Betreuerin und Orga-Team).

## Wann dieses Skill verwendet wird

- Bei Aufforderung zur Erstellung eines wöchentlichen Statusberichts.
- Beim Aufruf des Slash-Commands `/weekly-status-report`.
- Wenn ein Team zum Abschluss eines Sprints oder einer Kalenderwoche
  den Bericht (`sprint-<N>.mdx` oder `kw<KW>.mdx`) anlegen möchte.

## Wichtigste Grundregel: Nachfragen statt Halluzinieren

Bei unvollständigen oder mehrdeutigen Angaben darf der Agent **keine
Annahmen erfinden** (Halluzinationsverbot).

Vor dem Schreiben der Datei müssen folgende Punkte zweifelsfrei feststehen:
1. **Team:** Welches der 6 Teilteams reicht den Bericht ein?
2. **Sprint & Kalenderwoche:** Für welche Sprint-Nummer bzw. KW gilt der
   Bericht?
3. **Ampelstatus:** 🟢 (stabil), 🟡 (Risiken / Klärungen) oder 🔴 (Blocker)?
   Der Status darf **nie eigenmächtig auf grün gesetzt werden**, wenn
   offene Blocker-Tickets oder ungelöste Risiken vorliegen.
4. **Verantwortliche Ansprechperson:** Name der Teamleitung / Ansprechperson.
5. **Anforderungs- & Schnittstellenänderungen:** Gab es inhaltliche
   Abstimmungen, die nicht direkt in GitHub Issues dokumentiert sind?

Falls ein Punkt unklar ist: **Immer direkt die Nutzenden fragen!**

---

## Standard-Konventionen für Titel und Header

Jede Berichtsdatei liegt unter:
`docs/content/project/statusberichte/<team-ordner>/`

### 1. Dateinamen
- Für Teams mit Sprint-Rhythmus (Orga, Builder, Coding):
  `sprint-<N>.mdx` (z. B. `sprint-3.mdx`)
- Für Teams mit Wochen-Rhythmus (Asset-Design, Story, Recherche):
  `kw<KW>.mdx` (z. B. `kw46.mdx`)

### 2. Frontmatter & Header-Struktur
```markdown
---
sidebar_position: <fortlaufende_nummer>
---

# Wöchentliches Update: <Offizieller Teamname>

- **Datum:** <YYYY-MM-DD>
- **Sprint / Berichtszeitraum:** <TEAM-SPRINT-X> / KW <KW>
- **Verantwortliche Ansprechperson:** <Name>
```

### 3. Zuordnung der Teams

| Team-Key | Verzeichnis | Label | Standard-Ansprechperson |
| :--- | :--- | :--- | :--- |
| `orga` | `orga-lead-infra` | `orga` | Lucas |
| `builder` | `builder` | `building` | Lilly Tschampke |
| `assets` | `asset-design` | `assets` | Aljoscha Burger |
| `recherche`| `recherche-publishing-courses` | `research` | David Huslistyi |
| `coding` | `coding-interactions` | `code` | Paul Prietzel |
| `story` | `story-design` | `story` | Juliane Koch |

---

## Workflow für den Agenten

### Schritt 1: Kontext ermitteln und Unklarheiten erfragen

1. Team bestimmen (aus Nutzerprompt oder durch Nachfrage).
2. Bestehende Dateien im Teamordner prüfen
   (`ls -la docs/content/project/statusberichte/<team>/`).
3. Nächste Sprint-Nummer, Kalenderwoche und `sidebar_position` berechnen.
4. Bei fehlenden Angaben zu Ampelstatus oder Blocker gezielt nachfragen.

### Schritt 2: GitHub Issues abfragen

Abgeschlossene und offene Issues für das Teamlabel via `gh` CLI abfragen:

```bash
# Abgeschlossene Issues abrufen
gh issue list --repo cs24-sopr/project --state closed \
  --label <team-label> --limit 20 \
  --json number,title,labels,closedAt

# Aktuell offene Issues abrufen
gh issue list --repo cs24-sopr/project --state open \
  --label <team-label> --limit 10 \
  --json number,title,labels
```

### Schritt 3: Bericht generieren

Entweder direkt mit dem mitgelieferten Hilfsskript:

```bash
# Interaktiv oder mit definierten Parametern ausführen
python3 scripts/create_weekly_status.py \
  --team <team-key> \
  --sprint <sprint-nr> \
  --kw <kw-nr> \
  --status <green|yellow|red> \
  --author "<Name>"
```

Oder als Trockenlauf zur Vorabprüfung:

```bash
python3 scripts/create_weekly_status.py --team <team-key> --dry-run
```

### Schritt 4: Qualitätssicherung

1. Prüfen, dass keine Zeile mehr als 80 Zeichen lang ist.
2. Prüfen, dass keine Em-Dashes (`—`) oder typografischen Anführungszeichen
   enthalten sind (`AGENTS.md`).
3. Trockenlauf der PDF-Bündelung ausführen:
   `python3 scripts/export_status_pdf.py --sprint <N> --check-only`

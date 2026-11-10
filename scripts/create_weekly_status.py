#!/usr/bin/env python3
"""
Create a standardized weekly status report MDX file for a project team.

Reads finished GitHub issues, computes the next sprint / calendar week,
and generates the report adhering to
docs/content/project/vorlagen/team-update.mdx.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap
from typing import Any, Dict, List, Optional, Tuple

REPO_DEFAULT = "cs24-sopr/project"
STATUS_BASE_DIR = Path("docs/content/project/statusberichte")


@dataclass(frozen=True)
class TeamConfig:
    """Configuration metadata for a project team."""

    key: str
    dir_name: str
    display_name: str
    label: str
    default_author: str
    sprint_prefix: str
    file_prefix: str


TEAMS: Dict[str, TeamConfig] = {
    "orga": TeamConfig(
        key="orga",
        dir_name="orga-lead-infra",
        display_name="Organisation, Leitung und Infrastruktur",
        label="orga",
        default_author="Lucas",
        sprint_prefix="ORGA-SPRINT-",
        file_prefix="sprint",
    ),
    "builder": TeamConfig(
        key="builder",
        dir_name="builder",
        display_name="Builder",
        label="building",
        default_author="Lilly Tschampke",
        sprint_prefix="SPRINT-",
        file_prefix="sprint",
    ),
    "assets": TeamConfig(
        key="assets",
        dir_name="asset-design",
        display_name="Asset-Design",
        label="assets",
        default_author="Aljoscha Burger",
        sprint_prefix="ASSET-SPRINT-",
        file_prefix="kw",
    ),
    "recherche": TeamConfig(
        key="recherche",
        dir_name="recherche-publishing-courses",
        display_name="Recherche-Team",
        label="research",
        default_author="David Huslistyi",
        sprint_prefix="RECHERCHE-SPRINT-",
        file_prefix="kw",
    ),
    "coding": TeamConfig(
        key="coding",
        dir_name="coding-interactions",
        display_name="Coding",
        label="code",
        default_author="Paul Prietzel",
        sprint_prefix="CODE-SPRINT-",
        file_prefix="sprint",
    ),
    "story": TeamConfig(
        key="story",
        dir_name="story-design",
        display_name="Story Team",
        label="story",
        default_author="Juliane Koch",
        sprint_prefix="STORY-SPRINT-",
        file_prefix="kw",
    ),
}

# Alias mapping for command-line convenience
ALIASES: Dict[str, str] = {
    "orga-lead-infra": "orga",
    "infra": "orga",
    "building": "builder",
    "asset-design": "assets",
    "recherche-publishing-courses": "recherche",
    "research": "recherche",
    "coding-interactions": "coding",
    "code": "coding",
    "story-design": "story",
}


def resolve_team(name: str) -> Optional[TeamConfig]:
    """Resolve a team name or alias to a TeamConfig instance."""
    normalized = name.strip().lower()
    if normalized in TEAMS:
        return TEAMS[normalized]
    if normalized in ALIASES:
        return TEAMS[ALIASES[normalized]]
    return None


def get_existing_report_files(team_dir: Path) -> List[Path]:
    """Return all existing markdown report files in a team directory."""
    if not team_dir.is_dir():
        return []
    files = [
        p
        for p in team_dir.glob("*.md*")
        if p.is_file() and not p.name.startswith("README")
    ]
    files.sort(key=lambda p: p.name)
    return files


def detect_next_sequence(
    team_cfg: TeamConfig, base_dir: Path = STATUS_BASE_DIR
) -> Tuple[int, int, int]:
    """
    Detect the next sprint number, calendar week, and sidebar position.

    Returns:
        (next_sprint, current_kw, next_sidebar_position)
    """
    team_dir = base_dir / team_cfg.dir_name
    files = get_existing_report_files(team_dir)

    highest_sprint = 0
    highest_kw = 0

    for f in files:
        # Match sprint-X
        m_sprint = re.search(r"sprint-(\d+)", f.stem, re.IGNORECASE)
        if m_sprint:
            highest_sprint = max(highest_sprint, int(m_sprint.group(1)))

        # Match kwXX
        m_kw = re.search(r"kw(\d+)", f.stem, re.IGNORECASE)
        if m_kw:
            highest_kw = max(highest_kw, int(m_kw.group(1)))

    next_sprint = (highest_sprint + 1) if highest_sprint > 0 else 1
    current_kw = date.today().isocalendar().week
    if highest_kw > 0 and highest_kw >= current_kw:
        current_kw = highest_kw + 1

    next_sidebar_position = len(files) + 2
    return next_sprint, current_kw, next_sidebar_position


def fetch_github_issues(
    repo: str,
    label: Optional[str] = None,
    state: str = "closed",
    limit: int = 30,
) -> List[Dict[str, Any]]:
    """Fetch issues from GitHub using the gh CLI."""
    cmd = [
        "gh",
        "issue",
        "list",
        "--repo",
        repo,
        "--state",
        state,
        "--limit",
        str(limit),
        "--json",
        "number,title,labels,closedAt,assignees",
    ]
    if label:
        cmd.extend(["--label", label])

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=20,
        )
        return json.loads(res.stdout)
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        json.JSONDecodeError,
    ):
        return []


def fetch_single_issue(repo: str, issue_num: int) -> Optional[Dict[str, Any]]:
    """Fetch a single issue from GitHub by issue number."""
    cmd = [
        "gh",
        "issue",
        "view",
        str(issue_num),
        "--repo",
        repo,
        "--json",
        "number,title,labels,closedAt,state,assignees",
    ]
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=20,
        )
        return json.loads(res.stdout)
    except (
        subprocess.SubprocessError,
        FileNotFoundError,
        json.JSONDecodeError,
    ):
        return None


def format_issue_bullet(
    issue: Dict[str, Any], initial_indent: str = "  - "
) -> str:
    """Format a single GitHub issue into a wrapped markdown list bullet."""
    num = issue.get("number")
    title = issue.get("title", "").strip()
    raw = f"{initial_indent}`#{num}`: {title}"
    subsequent_indent = " " * len(initial_indent)
    return textwrap.fill(
        raw,
        width=78,
        subsequent_indent=subsequent_indent,
    )


def generate_mdx_content(
    team_cfg: TeamConfig,
    sprint_num: int,
    kw_num: int,
    sidebar_pos: int,
    report_date: str,
    author: str,
    status: str,
    closed_issues: List[Dict[str, Any]],
    open_issues: List[Dict[str, Any]],
    blocker_text: Optional[str] = None,
    req_changes_text: Optional[str] = None,
) -> str:
    """Generate the MDX text adhering to project report standards."""
    status_lower = status.strip().lower()
    green_chk = "x" if status_lower == "green" else " "
    yellow_chk = "x" if status_lower == "yellow" else " "
    red_chk = "x" if status_lower == "red" else " "

    # Erledigte Issues
    if closed_issues:
        closed_lines = [format_issue_bullet(i) for i in closed_issues]
        closed_md = "\n".join(closed_lines)
    else:
        closed_md = "  - Keine abgeschlossenen Issues in diesem Zeitraum."

    # In Arbeit
    if open_issues:
        open_lines = [format_issue_bullet(i) for i in open_issues]
        open_md = "\n".join(open_lines)
    else:
        open_md = "  - Keine aktiven Issues im Backlog für diesen Sprint."

    # Blocker & Risiken
    if status_lower == "green":
        blockers_md = "- [x] Keine aktuellen Blocker."
    elif blocker_text:
        blockers_md = f"- [x] {blocker_text}"
    else:
        blockers_md = (
            "- [ ] Klärungsbedarf vorhanden (bitte hier beschreiben,\n"
            "  welches Thema oder welche Abstimmung aktuell bremst)."
        )

    # Anforderungen
    if req_changes_text:
        req_md = req_changes_text
    else:
        req_md = "- [x] Keine Änderungen an Anforderungen seit letzter Woche."

    # Geplante Aufgaben aus offenen Issues ableiten
    if open_issues:
        planned_lines = [
            format_issue_bullet(i, initial_indent="- ")
            for i in open_issues[:4]
        ]
        planned_md = "\n".join(planned_lines)
    else:
        planned_md = "- Geplante Aufgaben für die kommende Woche ergänzen."

    sprint_id = f"{team_cfg.sprint_prefix}{sprint_num}"

    content = f"""---
sidebar_position: {sidebar_pos}
---

# Wöchentliches Update: {team_cfg.display_name}

- **Datum:** {report_date}
- **Sprint / Berichtszeitraum:** {sprint_id} / KW {kw_num}
- **Verantwortliche Ansprechperson:** {author}

### 1. Gesamtstatus
- [{green_chk}] 🟢 **stabil** (im Zeitplan, keine wesentlichen Hindernisse)
- [{yellow_chk}] 🟡 **Risiken / Klärungen** (Klärungsbedarf vorhanden)
- [{red_chk}] 🔴 **relevante Blocker** (Arbeit stockt, externe Hilfe nötig)

### 2. Fortschritt im aktuellen Sprint
- **Erledigte GitHub Issues:**
{closed_md}
- **Aktuell in Arbeit:**
{open_md}

### 3. Änderungen an Anforderungen seit letzter Woche
{req_md}

### 4. Schnittstellen (neu, geändert oder abgestimmt)
- [x] Keine Änderungen

### 5. Blocker & Risiken
{blockers_md}

### 6. Geplante Aufgaben bis nächste Woche
{planned_md}
"""
    return content


def build_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Create a standardized weekly status report MDX file."
    )
    parser.add_argument(
        "--team",
        type=str,
        help="Team key or alias (e.g. orga, builder, coding).",
    )
    parser.add_argument(
        "--sprint",
        type=int,
        help="Sprint number (e.g. 1, 2, 3).",
    )
    parser.add_argument(
        "--kw",
        type=int,
        help="Calendar week (e.g. 45). Defaults to current ISO week.",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=date.today().isoformat(),
        help="Report date in YYYY-MM-DD format (default: today).",
    )
    parser.add_argument(
        "--author",
        type=str,
        help="Responsible contact person (Ansprechperson).",
    )
    parser.add_argument(
        "--status",
        type=str,
        choices=["green", "yellow", "red"],
        default="green",
        help="Overall traffic light status (green, yellow, red).",
    )
    parser.add_argument(
        "--issues",
        type=str,
        help="Comma-separated list of closed issue numbers (e.g. 61,62,73).",
    )
    parser.add_argument(
        "--in-progress-issues",
        type=str,
        help="Comma-separated list of in-progress issue numbers (e.g. 44,93).",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=REPO_DEFAULT,
        help=f"GitHub repository (default: {REPO_DEFAULT}).",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Do not query GitHub API for issues.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated report content without writing to disk.",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Custom output file path.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for missing or uncertain details instead of defaults.",
    )
    return parser


def prompt_user(prompt: str, default: Optional[str] = None) -> str:
    """Prompt the user via standard input with an optional default."""
    if default:
        formatted_prompt = f"{prompt} [{default}]: "
    else:
        formatted_prompt = f"{prompt}: "
    value = input(formatted_prompt).strip()
    return value if value else (default or "")


def main() -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    team_str = args.team
    if not team_str:
        if args.interactive or sys.stdin.isatty():
            print("Verfügbare Teams:")
            for key, cfg in TEAMS.items():
                print(f"  - {key}: {cfg.display_name}")
            team_str = prompt_user("Bitte Team wählen")
        else:
            print(
                "Fehler: Kein Team angegeben (--team erforderlich).",
                file=sys.stderr,
            )
            return 1

    team_cfg = resolve_team(team_str)
    if not team_cfg:
        print(
            f"Fehler: Unbekanntes Team '{team_str}'.",
            file=sys.stderr,
        )
        return 1

    detected_sprint, detected_kw, sidebar_pos = detect_next_sequence(team_cfg)

    sprint_num = args.sprint
    if sprint_num is None:
        if args.interactive:
            sprint_input = prompt_user(
                "Sprint-Nummer", str(detected_sprint)
            )
            sprint_num = int(sprint_input)
        else:
            sprint_num = detected_sprint

    kw_num = args.kw
    if kw_num is None:
        if args.interactive:
            kw_input = prompt_user("Kalenderwoche (KW)", str(detected_kw))
            kw_num = int(kw_input)
        else:
            kw_num = detected_kw

    author = args.author
    if not author:
        if args.interactive:
            author = prompt_user(
                "Verantwortliche Ansprechperson", team_cfg.default_author
            )
        else:
            author = team_cfg.default_author

    status = args.status
    if args.interactive:
        status_input = prompt_user(
            "Ampelstatus (green/yellow/red)", status
        ).lower()
        if status_input in ["green", "yellow", "red"]:
            status = status_input

    # Fetch GitHub issues if enabled
    closed_issues: List[Dict[str, Any]] = []
    open_issues: List[Dict[str, Any]] = []

    if args.issues:
        for num_str in args.issues.split(","):
            cleaned = num_str.strip().lstrip("#")
            if cleaned.isdigit():
                issue_data = fetch_single_issue(args.repo, int(cleaned))
                if issue_data:
                    closed_issues.append(issue_data)
                else:
                    closed_issues.append({
                        "number": int(cleaned),
                        "title": f"Issue #{cleaned}",
                    })
    elif not args.no_fetch:
        closed_issues = fetch_github_issues(
            repo=args.repo,
            label=team_cfg.label,
            state="closed",
            limit=20,
        )

    if args.in_progress_issues:
        for num_str in args.in_progress_issues.split(","):
            cleaned = num_str.strip().lstrip("#")
            if cleaned.isdigit():
                issue_data = fetch_single_issue(args.repo, int(cleaned))
                if issue_data:
                    open_issues.append(issue_data)
                else:
                    open_issues.append({
                        "number": int(cleaned),
                        "title": f"Issue #{cleaned}",
                    })
    elif not args.no_fetch:
        open_issues = fetch_github_issues(
            repo=args.repo,
            label=team_cfg.label,
            state="open",
            limit=10,
        )

    mdx = generate_mdx_content(
        team_cfg=team_cfg,
        sprint_num=sprint_num,
        kw_num=kw_num,
        sidebar_pos=sidebar_pos,
        report_date=args.date,
        author=author,
        status=status,
        closed_issues=closed_issues,
        open_issues=open_issues,
    )

    if args.dry_run:
        print("=== DRY RUN: Generierter Statusbericht ===")
        print(mdx)
        return 0

    if args.output:
        target_path = Path(args.output)
    else:
        team_dir = STATUS_BASE_DIR / team_cfg.dir_name
        team_dir.mkdir(parents=True, exist_ok=True)
        if team_cfg.file_prefix == "sprint":
            filename = f"sprint-{sprint_num}.mdx"
        else:
            filename = f"kw{kw_num}.mdx"
        target_path = team_dir / filename

    if target_path.exists() and not args.interactive:
        print(
            f"Warnung: Datei {target_path} existiert bereits und wird "
            "überschrieben.",
            file=sys.stderr,
        )

    target_path.write_text(mdx, encoding="utf-8")
    print(f"Statusbericht erfolgreich erstellt: {target_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

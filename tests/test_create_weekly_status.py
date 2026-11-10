#!/usr/bin/env python3
"""Unit tests for create_weekly_status.py."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from scripts.create_weekly_status import (
    ALIASES,
    TEAMS,
    TeamConfig,
    detect_next_sequence,
    format_issue_bullet,
    generate_mdx_content,
    resolve_team,
)


class TestCreateWeeklyStatus(unittest.TestCase):
    """Test suite for weekly status report generator."""

    def test_resolve_team_valid_keys(self) -> None:
        """Verify resolution of standard team keys."""
        keys = [
            "orga",
            "builder",
            "assets",
            "recherche",
            "coding",
            "story",
        ]
        for key in keys:
            cfg = resolve_team(key)
            self.assertIsNotNone(cfg)
            self.assertEqual(cfg.key, key)

    def test_resolve_team_aliases(self) -> None:
        """Verify resolution of team aliases."""
        self.assertEqual(resolve_team("infra").key, "orga")
        self.assertEqual(resolve_team("orga-lead-infra").key, "orga")
        self.assertEqual(resolve_team("building").key, "builder")
        self.assertEqual(resolve_team("asset-design").key, "assets")
        self.assertEqual(resolve_team("research").key, "recherche")
        self.assertEqual(resolve_team("coding-interactions").key, "coding")
        self.assertEqual(resolve_team("story-design").key, "story")

    def test_resolve_team_unknown(self) -> None:
        """Verify resolution of unknown team returns None."""
        self.assertIsNone(resolve_team("nonexistent-team"))

    def test_detect_next_sequence_empty_dir(self) -> None:
        """Verify next sequence detection with no existing files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            cfg = TEAMS["builder"]
            (base / cfg.dir_name).mkdir(parents=True)

            sprint, kw, pos = detect_next_sequence(cfg, base_dir=base)
            self.assertEqual(sprint, 1)
            self.assertGreater(kw, 0)
            self.assertEqual(pos, 2)

    def test_detect_next_sequence_existing_sprints(self) -> None:
        """Verify next sequence detection with existing sprint files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            cfg = TEAMS["orga"]
            team_dir = base / cfg.dir_name
            team_dir.mkdir(parents=True)
            (team_dir / "README.mdx").write_text("# Readme")
            (team_dir / "sprint-1.mdx").write_text("# Sprint 1")
            (team_dir / "sprint-2.mdx").write_text("# Sprint 2")

            sprint, kw, pos = detect_next_sequence(cfg, base_dir=base)
            self.assertEqual(sprint, 3)
            self.assertEqual(pos, 4)

    def test_format_issue_bullet_line_wrap(self) -> None:
        """Verify that long issue titles are wrapped within 80 chars."""
        long_title = (
            "This is an extremely long issue title that describes a "
            "complicated task that spans multiple components and requires "
            "extensive architectural documentation"
        )
        issue = {"number": 123, "title": long_title}
        bullet = format_issue_bullet(issue, initial_indent="  - ")
        for line in bullet.splitlines():
            self.assertLessEqual(len(line), 80)
        self.assertTrue(bullet.startswith("  - `#123`:"))

    def test_generate_mdx_content_structure(self) -> None:
        """Verify that all required template sections exist."""
        cfg = TEAMS["coding"]
        closed = [
            {"number": 42, "title": "Implement door interaction"},
            {"number": 43, "title": "Refactor camera control script"},
        ]
        opened = [
            {"number": 55, "title": "Add quest log UI"},
        ]

        mdx = generate_mdx_content(
            team_cfg=cfg,
            sprint_num=3,
            kw_num=46,
            sidebar_pos=5,
            report_date="2026-11-09",
            author="Paul Prietzel",
            status="green",
            closed_issues=closed,
            open_issues=opened,
        )

        self.assertIn("sidebar_position: 5", mdx)
        self.assertIn("# Wöchentliches Update: Coding", mdx)
        self.assertIn("**Datum:** 2026-11-09", mdx)
        self.assertIn("CODE-SPRINT-3 / KW 46", mdx)
        self.assertIn("**Verantwortliche Ansprechperson:** Paul Prietzel", mdx)
        self.assertIn("[x] 🟢 **stabil**", mdx)
        self.assertIn("[ ] 🟡 **Risiken / Klärungen**", mdx)
        self.assertIn("[ ] 🔴 **relevante Blocker**", mdx)
        self.assertIn("### 2. Fortschritt im aktuellen Sprint", mdx)
        self.assertIn("`#42`: Implement door interaction", mdx)
        self.assertIn("`#43`: Refactor camera control script", mdx)
        self.assertIn(
            "### 3. Änderungen an Anforderungen seit letzter Woche", mdx
        )
        self.assertIn(
            "### 4. Schnittstellen (neu, geändert oder abgestimmt)", mdx
        )
        self.assertIn("### 5. Blocker & Risiken", mdx)
        self.assertIn("### 6. Geplante Aufgaben bis nächste Woche", mdx)

    def test_generate_mdx_traffic_lights(self) -> None:
        """Verify traffic light selection."""
        cfg = TEAMS["assets"]
        mdx_yellow = generate_mdx_content(
            team_cfg=cfg,
            sprint_num=2,
            kw_num=45,
            sidebar_pos=3,
            report_date="2026-11-09",
            author="Aljoscha Burger",
            status="yellow",
            closed_issues=[],
            open_issues=[],
            blocker_text="Kurze Frist für Quest-Assets.",
        )
        self.assertIn("[ ] 🟢 **stabil**", mdx_yellow)
        self.assertIn("[x] 🟡 **Risiken / Klärungen**", mdx_yellow)
        self.assertIn("- [x] Kurze Frist für Quest-Assets.", mdx_yellow)

    def test_generated_output_line_lengths(self) -> None:
        """Verify that no line in generated output exceeds 80 characters."""
        cfg = TEAMS["story"]
        closed = [
            {
                "number": 101,
                "title": (
                    "Konzeption der Dialoge für den Bibliothekar und das "
                    "Erwachen im Tutorialbereich"
                ),
            }
        ]
        opened = [
            {
                "number": 102,
                "title": (
                    "Ausarbeitung der Questbeschreibungen für das Questlog "
                    "in Abstimmung mit Coding"
                ),
            }
        ]
        mdx = generate_mdx_content(
            team_cfg=cfg,
            sprint_num=2,
            kw_num=45,
            sidebar_pos=3,
            report_date="2026-11-09",
            author="Juliane Koch",
            status="green",
            closed_issues=closed,
            open_issues=opened,
        )
        for idx, line in enumerate(mdx.splitlines()):
            self.assertLessEqual(
                len(line),
                80,
                f"Line {idx + 1} exceeds 80 chars ({len(line)}): {line}",
            )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""
Export weekly sprint status reports to a bundled PDF document.

Parses team reports in docs/content/project/statusberichte/ and
generates a formatted overview and combined PDF for course submission.
"""

import argparse
import datetime
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo

PAGE_WIDTH = 595.28  # A4 width in points (72 dpi)
PAGE_HEIGHT = 841.89  # A4 height in points
MARGIN_X = 42.0
MARGIN_TOP = 36.0
MARGIN_BOTTOM = 36.0
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN_X
CONTENT_HEIGHT = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

TEAMS = [
    {
        "id": "orga-lead-infra",
        "name": "Organisation, Leitung & Infrastruktur",
        "lead": "Lucas",
    },
    {
        "id": "builder",
        "name": "Builder-Team",
        "lead": "Lilly Tschampke",
    },
    {
        "id": "asset-design",
        "name": "Asset-Design",
        "lead": "Yoshi",
    },
    {
        "id": "coding-interactions",
        "name": "Coding & Interactions",
        "lead": "Marius Brunner",
    },
    {
        "id": "recherche-publishing-courses",
        "name": "Recherche, Publishing & Courses",
        "lead": "Rebecca John",
    },
    {
        "id": "story-design",
        "name": "Story-Design",
        "lead": "Juliane Koch",
    },
]


def escape_pango(text: str) -> str:
    """Escape text for Pango markup."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def inline_markdown_to_pango(text: str) -> str:
    """Convert simple inline markdown to Pango markup."""
    code_tokens: List[str] = []

    def save_code(match: re.Match) -> str:
        code_tokens.append(match.group(1))
        return f"__CODE_TOKEN_{len(code_tokens) - 1}__"

    text = re.sub(r"`([^`]+)`", save_code, text)
    text = escape_pango(text)

    # Bold: **bold**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)

    # Italic: *italic*
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)

    # Restore code spans with monospace font
    for idx, code in enumerate(code_tokens):
        escaped_code = escape_pango(code)
        markup = (
            f'<span font_family="Monospace" font_size="8pt" '
            f'background="#e2e8f0">{escaped_code}</span>'
        )
        text = text.replace(f"__CODE_TOKEN_{idx}__", markup)

    return text


def find_team_report_file(
    team_dir: str, sprint_num: int
) -> Optional[str]:
    """Find the best matching report file for a team and sprint."""
    if not os.path.isdir(team_dir):
        return None

    # Priority 1: exact sprint filename
    sprint_file = os.path.join(team_dir, f"sprint-{sprint_num}.mdx")
    if os.path.exists(sprint_file):
        return sprint_file

    # Priority 2: kw files corresponding to sprint 1 (kw41 to kw45)
    kw_candidates = [f"kw{kw}.mdx" for kw in range(41, 46)]
    for kw_f in kw_candidates:
        candidate_path = os.path.join(team_dir, kw_f)
        if os.path.exists(candidate_path):
            return candidate_path

    # Priority 3: any non-README mdx/md file
    all_files = [
        f
        for f in os.listdir(team_dir)
        if f.endswith((".mdx", ".md")) and not f.startswith("README")
    ]
    if all_files:
        all_files.sort()
        return os.path.join(team_dir, all_files[-1])

    return None


def parse_status_file(filepath: Optional[str]) -> Dict[str, Any]:
    """Parse a team status report markdown file."""
    if not filepath or not os.path.exists(filepath):
        return {"exists": False}

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove YAML frontmatter
    content = re.sub(
        r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL
    )

    # Extract metadata
    date_match = re.search(r"\*\*Datum:\*\*\s*(.+)", content)
    sprint_match = re.search(
        r"\*\*(?:Sprint|Berichtszeitraum)[^:]*:\*\*\s*(.+)", content
    )
    contact_re = (
        r"\*\*(?:Verantwortliche Ansprechperson|Ansprechperson)"
        r"[^:]*:\*\*\s*(.+)"
    )
    contact_match = re.search(contact_re, content)

    # Traffic light detection
    status_light = "unbekannt"
    if re.search(r"-\s*\[x\]\s*🟢", content, re.IGNORECASE):
        status_light = "🟢 stabil"
    elif re.search(r"-\s*\[x\]\s*🟡", content, re.IGNORECASE):
        status_light = "🟡 Risiken"
    elif re.search(r"-\s*\[x\]\s*🔴", content, re.IGNORECASE):
        status_light = "🔴 Blocker"

    return {
        "exists": True,
        "filename": os.path.basename(filepath),
        "raw_content": content,
        "lines": content.splitlines(),
        "date": date_match.group(1).strip() if date_match else "-",
        "sprint": sprint_match.group(1).strip() if sprint_match else "-",
        "contact": contact_match.group(1).strip() if contact_match else "-",
        "status_light": status_light,
    }


class PDFBuilder:
    """Builds and renders status reports to Cairo PDF."""

    def __init__(
        self,
        output_path: str,
        sprint_num: int,
        team_data: List[Dict[str, Any]],
        total_pages: int = 1,
        separate_missing: bool = False,
    ) -> None:
        self.output_path = output_path
        self.sprint_num = sprint_num
        self.team_data = team_data
        self.total_pages = total_pages
        self.separate_missing = separate_missing
        self.current_page = 1
        self.surface = cairo.PDFSurface(
            output_path, PAGE_WIDTH, PAGE_HEIGHT
        )
        self.cr = cairo.Context(self.surface)
        self.current_y = MARGIN_TOP

    def check_page_break(self, required_height: float) -> None:
        """Advance to new page if remaining vertical space is low."""
        if self.current_y + required_height > (PAGE_HEIGHT - MARGIN_BOTTOM):
            self.new_page()

    def new_page(self) -> None:
        """Finish current page and advance to next."""
        self.draw_decorations()
        self.surface.show_page()
        self.current_page += 1
        self.current_y = MARGIN_TOP

    def draw_decorations(self) -> None:
        """Draw running header and footer."""
        cr = self.cr
        # Running header (pages after cover page)
        if self.current_page > 1:
            cr.set_source_rgb(0.4, 0.45, 0.5)
            layout = PangoCairo.create_layout(cr)
            desc = Pango.font_description_from_string("Sans 8")
            layout.set_font_description(desc)
            header_text = (
                f"Virtueller Nachbau DHSN Leipzig - Sprint {self.sprint_num}"
            )
            layout.set_text(header_text)
            cr.move_to(MARGIN_X, 24.0)
            PangoCairo.show_layout(cr, layout)

            # Header line
            cr.set_source_rgb(0.82, 0.86, 0.9)
            cr.set_line_width(0.75)
            cr.move_to(MARGIN_X, 36.0)
            cr.line_to(PAGE_WIDTH - MARGIN_X, 36.0)
            cr.stroke()

        # Running footer line
        cr.set_source_rgb(0.82, 0.86, 0.9)
        cr.set_line_width(0.75)
        cr.move_to(MARGIN_X, PAGE_HEIGHT - 32.0)
        cr.line_to(PAGE_WIDTH - MARGIN_X, PAGE_HEIGHT - 32.0)
        cr.stroke()

        cr.set_source_rgb(0.45, 0.5, 0.55)
        layout = PangoCairo.create_layout(cr)
        desc = Pango.font_description_from_string("Sans 8")
        layout.set_font_description(desc)

        # Left footer
        footer_msg = "Softwareprojekt 5. Semester - Querschnittsaufgabe RI"
        layout.set_text(footer_msg)
        cr.move_to(MARGIN_X, PAGE_HEIGHT - 25.0)
        PangoCairo.show_layout(cr, layout)

        # Right footer: Page numbers
        page_str = f"Seite {self.current_page} von {self.total_pages}"
        layout.set_text(page_str)
        _, rect = layout.get_extents()
        pw = rect.width / Pango.SCALE
        cr.move_to(PAGE_WIDTH - MARGIN_X - pw, PAGE_HEIGHT - 25.0)
        PangoCairo.show_layout(cr, layout)

    def draw_cover_page(self) -> None:
        """Render summary cover page with wrapped text and dynamic boxes."""
        cr = self.cr

        # Title Card Header Box
        box_height = 76.0
        cr.set_source_rgb(0.08, 0.16, 0.28)  # Deep navy
        cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, box_height)
        cr.fill()

        # Title text
        layout = PangoCairo.create_layout(cr)
        desc = Pango.font_description_from_string("Sans Bold 15")
        layout.set_font_description(desc)
        layout.set_markup(
            '<span color="#ffffff">Virtueller Nachbau DHSN Leipzig</span>'
        )
        cr.move_to(MARGIN_X + 16.0, self.current_y + 14.0)
        PangoCairo.show_layout(cr, layout)

        # Subtitle
        desc = Pango.font_description_from_string("Sans 10.5")
        layout.set_font_description(desc)
        sub_text = (
            f'<span color="#93c5fd">Statusberichte aller Teams - '
            f'Sprint {self.sprint_num}</span>'
        )
        layout.set_markup(sub_text)
        cr.move_to(MARGIN_X + 16.0, self.current_y + 42.0)
        PangoCairo.show_layout(cr, layout)

        self.current_y += box_height + 14.0

        # Metadata bar
        now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M Uhr")
        meta_markup = (
            f"<b>Stichtag der Abgabe:</b> Sonntag, 01.11.2026 (23:59 Uhr) | "
            f"<b>Export generiert:</b> {now_str}"
        )
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(
            Pango.font_description_from_string("Sans 8.5")
        )
        layout.set_markup(meta_markup)
        cr.move_to(MARGIN_X, self.current_y)
        PangoCairo.show_layout(cr, layout)
        self.current_y += 20.0

        # KPI Metrics Cards
        submitted_cnt = sum(1 for t in self.team_data if t["info"]["exists"])
        missing_cnt = len(self.team_data) - submitted_cnt

        card_width = (CONTENT_WIDTH - 20.0) / 3.0
        card_height = 46.0

        # Card 1: Submitted
        cr.set_source_rgb(0.93, 0.98, 0.94)
        cr.rectangle(MARGIN_X, self.current_y, card_width, card_height)
        cr.fill()
        cr.set_source_rgb(0.18, 0.55, 0.24)
        cr.set_line_width(1.0)
        cr.rectangle(MARGIN_X, self.current_y, card_width, card_height)
        cr.stroke()

        layout.set_markup(
            f'<span font="Sans 7.5" color="#166534">EINGEREICHT</span>\n'
            f'<span font="Sans Bold 13" color="#14532d">'
            f'{submitted_cnt} von {len(self.team_data)} Teams</span>'
        )
        cr.move_to(MARGIN_X + 10.0, self.current_y + 6.0)
        PangoCairo.show_layout(cr, layout)

        # Card 2: Missing
        card_x2 = MARGIN_X + card_width + 10.0
        cr.set_source_rgb(0.99, 0.95, 0.95)
        cr.rectangle(card_x2, self.current_y, card_width, card_height)
        cr.fill()
        cr.set_source_rgb(0.85, 0.25, 0.25)
        cr.rectangle(card_x2, self.current_y, card_width, card_height)
        cr.stroke()

        layout.set_markup(
            f'<span font="Sans 7.5" color="#991b1b">NOCH AUSSTEHEND</span>\n'
            f'<span font="Sans Bold 13" color="#7f1d1d">'
            f'{missing_cnt} von {len(self.team_data)} Teams</span>'
        )
        cr.move_to(card_x2 + 10.0, self.current_y + 6.0)
        PangoCairo.show_layout(cr, layout)

        # Card 3: Overall Traffic Light
        card_x3 = MARGIN_X + 2 * (card_width + 10.0)
        cr.set_source_rgb(0.95, 0.97, 1.0)
        cr.rectangle(card_x3, self.current_y, card_width, card_height)
        cr.fill()
        cr.set_source_rgb(0.25, 0.45, 0.8)
        cr.rectangle(card_x3, self.current_y, card_width, card_height)
        cr.stroke()

        layout.set_markup(
            '<span font="Sans 7.5" color="#1e40af">GESAMTSTATUS (ORGA)</span>\n'
            '<span font="Sans Bold 13" color="#1e3a8a">🟢 Stabil</span>'
        )
        cr.move_to(card_x3 + 10.0, self.current_y + 6.0)
        PangoCairo.show_layout(cr, layout)

        self.current_y += card_height + 18.0

        # Section Heading: Team Overview Table
        layout.set_markup(
            '<span font="Sans Bold 11" color="#0f172a">'
            'Übersicht der Team-Einreichungen</span>'
        )
        cr.move_to(MARGIN_X, self.current_y)
        PangoCairo.show_layout(cr, layout)
        self.current_y += 16.0

        # Draw Table with strict cell wrapping to prevent overlap
        col_w = [190.0, 115.0, 105.0, 95.28]  # Sum: 505.28 = CONTENT_WIDTH
        hdr_h = 22.0

        # Header Row
        cr.set_source_rgb(0.15, 0.23, 0.35)
        cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, hdr_h)
        cr.fill()

        headers = ["Team", "Ansprechperson", "Status", "Abgabedatum"]
        cur_x = MARGIN_X
        for idx, h in enumerate(headers):
            layout.set_markup(
                f'<span font="Sans Bold 8.5" color="#ffffff">'
                f'{escape_pango(h)}</span>'
            )
            layout.set_width(int((col_w[idx] - 10.0) * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            cr.move_to(cur_x + 6.0, self.current_y + 4.0)
            PangoCairo.show_layout(cr, layout)
            cur_x += col_w[idx]

        self.current_y += hdr_h

        # Data Rows
        for r_idx, t in enumerate(self.team_data):
            info = t["info"]

            # Compute row height based on cell with highest height
            cell_markups = []

            # Col 1: Team Name
            cell_markups.append(
                f'<span font="Sans 8.5" color="#1e293b">'
                f'{escape_pango(t["name"])}</span>'
            )
            # Col 2: Lead / Contact
            lead_text = escape_pango(info.get("contact", t["lead"]))
            cell_markups.append(
                f'<span font="Sans 8" color="#334155">{lead_text}</span>'
            )
            # Col 3: Status
            if info["exists"]:
                color = "#166534" if "🟢" in info["status_light"] else "#854d0e"
                status_str = f"<b>{info['status_light']}</b>"
            else:
                color = "#b91c1c"
                status_str = "<b>⚠️ Fehlt</b>"
            cell_markups.append(
                f'<span font="Sans 8" color="{color}">{status_str}</span>'
            )
            # Col 4: Date
            date_str = escape_pango(info["date"] if info["exists"] else "-")
            cell_markups.append(
                f'<span font="Sans 8" color="#475569">{date_str}</span>'
            )

            max_h = 22.0
            for i, markup in enumerate(cell_markups):
                layout.set_markup(markup)
                layout.set_width(int((col_w[i] - 10.0) * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                _, rect = layout.get_extents()
                ch = (rect.height / Pango.SCALE) + 6.0
                if ch > max_h:
                    max_h = ch

            # Background
            bg_c = (0.97, 0.98, 0.99) if r_idx % 2 == 1 else (1.0, 1.0, 1.0)
            cr.set_source_rgb(*bg_c)
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, max_h)
            cr.fill()

            # Border
            cr.set_source_rgb(0.88, 0.9, 0.94)
            cr.set_line_width(0.5)
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, max_h)
            cr.stroke()

            # Draw cells
            cur_x = MARGIN_X
            for i, markup in enumerate(cell_markups):
                layout.set_markup(markup)
                layout.set_width(int((col_w[i] - 10.0) * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                cr.move_to(cur_x + 6.0, self.current_y + 4.0)
                PangoCairo.show_layout(cr, layout)
                cur_x += col_w[i]

            self.current_y += max_h

        self.current_y += 16.0

        # Dynamic Missing Teams Warning Box
        if missing_cnt > 0:
            missing_names = [
                escape_pango(t["name"])
                for t in self.team_data
                if not t["info"]["exists"]
            ]
            missing_list_str = ", ".join(missing_names)

            warn_markup = (
                f'<span font="Sans Bold 9" color="#9a3412">'
                f'Hinweis zur Vollständigkeit der Abgabe:</span>\n'
                f'<span font="Sans 8" color="#7c2d12">'
                f'Für <b>{missing_cnt} Teams</b> liegt zum Stichtag noch '
                f'kein wöchentlicher Statusbericht vor:\n'
                f'• {missing_list_str}\n'
                f'Die Teams wurden erinnert, ihre Updates anhand der '
                f'Vorlage schnellstmöglich nachzureichen.</span>'
            )
            layout.set_width(int((CONTENT_WIDTH - 24.0) * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            layout.set_markup(warn_markup)
            _, rect = layout.get_extents()
            box_h = (rect.height / Pango.SCALE) + 16.0

            cr.set_source_rgb(0.99, 0.96, 0.92)  # Amber background
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, box_h)
            cr.fill()
            cr.set_source_rgb(0.85, 0.55, 0.15)  # Amber border
            cr.set_line_width(1.0)
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, box_h)
            cr.stroke()

            cr.move_to(MARGIN_X + 12.0, self.current_y + 8.0)
            PangoCairo.show_layout(cr, layout)
            layout.set_width(-1)

            self.current_y += box_h + 14.0

    def draw_team_report(self, team: Dict[str, Any]) -> None:
        """Render individual team report content with clean typography."""
        info = team["info"]
        self.new_page()

        cr = self.cr

        # Team Banner
        banner_h = 40.0
        cr.set_source_rgb(0.12, 0.22, 0.36)
        cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, banner_h)
        cr.fill()

        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(
            Pango.font_description_from_string("Sans Bold 11")
        )
        escaped_name = escape_pango(team["name"])
        layout.set_markup(
            f'<span color="#ffffff">Team: {escaped_name}</span>'
        )
        cr.move_to(MARGIN_X + 10.0, self.current_y + 5.0)
        PangoCairo.show_layout(cr, layout)

        desc_meta = Pango.font_description_from_string("Sans 7.5")
        layout.set_font_description(desc_meta)
        status_banner = (
            info["status_light"] if info["exists"] else "⚠️ Nicht eingereicht"
        )
        contact_esc = escape_pango(info.get("contact", team["lead"]))
        file_esc = escape_pango(info.get("filename", "-"))
        layout.set_markup(
            f'<span color="#93c5fd">Status: <b>{status_banner}</b>   |   '
            f'Ansprechperson: {contact_esc}   |   Datei: {file_esc}</span>'
        )
        cr.move_to(MARGIN_X + 10.0, self.current_y + 22.0)
        PangoCairo.show_layout(cr, layout)

        self.current_y += banner_h + 8.0

        if not info["exists"]:
            # Placeholder for missing report
            cr.set_source_rgb(0.98, 0.95, 0.95)
            box_h = 80.0
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, box_h)
            cr.fill()
            cr.set_source_rgb(0.8, 0.25, 0.25)
            cr.set_line_width(0.75)
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, box_h)
            cr.stroke()

            folder_esc = escape_pango(
                f"docs/content/project/statusberichte/{team['id']}/"
            )
            layout.set_markup(
                f'<span font="Sans Bold 9.5" color="#991b1b">'
                f'Statusbericht für Sprint {self.sprint_num} fehlt</span>\n\n'
                f'<span font="Sans 8.5" color="#7f1d1d">'
                f'Das Team hat bis zum Stichtag noch keinen Bericht im '
                f'Verzeichnis <tt>{folder_esc}</tt> hinterlegt.\n'
                f'Verbindliche Vorlage: '
                f'<tt>docs/content/project/vorlagen/team-update.mdx</tt>'
                f'</span>'
            )
            layout.set_width(int((CONTENT_WIDTH - 24.0) * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            cr.move_to(MARGIN_X + 12.0, self.current_y + 8.0)
            PangoCairo.show_layout(cr, layout)
            layout.set_width(-1)
            self.current_y += box_h + 12.0
            return

        # Render parsed Markdown lines
        lines = info["lines"]
        idx = 0
        while idx < len(lines):
            line = lines[idx]

            # Skip top-level title header
            if line.startswith("# ") and not line.startswith("### "):
                idx += 1
                continue

            # Blockquote
            if line.startswith(">"):
                quote_text = line.lstrip("> ").strip()
                layout.set_markup(
                    f'<span font="Sans Italic 8" color="#475569">'
                    f'{escape_pango(quote_text)}</span>'
                )
                layout.set_width(int((CONTENT_WIDTH - 20.0) * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                _, rect = layout.get_extents()
                lh = (rect.height / Pango.SCALE) + 6.0
                self.check_page_break(lh)

                # Quote indicator line
                cr.set_source_rgb(0.7, 0.75, 0.8)
                cr.set_line_width(2.0)
                cr.move_to(MARGIN_X + 2.0, self.current_y)
                cr.line_to(MARGIN_X + 2.0, self.current_y + lh - 3.0)
                cr.stroke()

                cr.move_to(MARGIN_X + 10.0, self.current_y + 1.0)
                PangoCairo.show_layout(cr, layout)
                layout.set_width(-1)
                self.current_y += lh
                idx += 1
                continue

            # Section Header (### or ##) - prevent orphan headers
            if line.startswith("### ") or line.startswith("## "):
                header_text = line.lstrip("#").strip()
                layout.set_markup(
                    f'<span font="Sans Bold 8.5" color="#1e3a8a">'
                    f'{escape_pango(header_text)}</span>'
                )
                self.check_page_break(38.0)
                cr.move_to(MARGIN_X, self.current_y + 3.0)
                PangoCairo.show_layout(cr, layout)

                # Light underline
                cr.set_source_rgb(0.85, 0.9, 0.95)
                cr.set_line_width(0.5)
                cr.move_to(MARGIN_X, self.current_y + 14.0)
                cr.line_to(PAGE_WIDTH - MARGIN_X, self.current_y + 14.0)
                cr.stroke()

                self.current_y += 16.0
                idx += 1
                continue

            # Markdown Table detection
            if line.startswith("|") and line.endswith("|"):
                table_lines = []
                while idx < len(lines) and lines[idx].startswith("|"):
                    table_lines.append(lines[idx])
                    idx += 1
                self.render_table(table_lines)
                continue

            # Bullet points / Checklist items
            if line.strip().startswith("- "):
                clean_line = line.strip()[2:].strip()
                # Checkbox
                if clean_line.startswith("[x]") or clean_line.startswith("[X]"):
                    clean_line = "☑ " + clean_line[3:].strip()
                elif clean_line.startswith("[ ]"):
                    clean_line = "☐ " + clean_line[3:].strip()
                else:
                    clean_line = "• " + clean_line

                indent = len(line) - len(line.lstrip())
                indent_x = MARGIN_X + (indent * 5.0)

                markup = inline_markdown_to_pango(clean_line)
                layout.set_markup(
                    f'<span font="Sans 7.5" color="#1e293b">{markup}</span>'
                )
                w = CONTENT_WIDTH - (indent * 5.0)
                layout.set_width(int(w * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                _, rect = layout.get_extents()
                lh = (rect.height / Pango.SCALE) + 1.2
                self.check_page_break(lh)

                cr.move_to(indent_x, self.current_y)
                PangoCairo.show_layout(cr, layout)
                layout.set_width(-1)
                self.current_y += lh
                idx += 1
                continue

            # Regular text paragraph
            if line.strip():
                markup = inline_markdown_to_pango(line.strip())
                layout.set_markup(
                    f'<span font="Sans 7.5" color="#334155">{markup}</span>'
                )
                layout.set_width(int(CONTENT_WIDTH * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                _, rect = layout.get_extents()
                lh = (rect.height / Pango.SCALE) + 2.0
                self.check_page_break(lh)

                cr.move_to(MARGIN_X, self.current_y)
                PangoCairo.show_layout(cr, layout)
                layout.set_width(-1)
                self.current_y += lh

            idx += 1

    def render_table(self, table_lines: List[str]) -> None:
        """Render parsed markdown table lines with auto column wrapping."""
        if len(table_lines) < 2:
            return

        cr = self.cr

        # Parse raw table cells
        raw_rows: List[List[str]] = []
        for line in table_lines:
            cells = [c.strip() for c in line.strip().split("|")[1:-1]]
            raw_rows.append(cells)

        headers = raw_rows[0]
        # Filter out separator row
        data_rows = [
            r
            for r in raw_rows[1:]
            if not all(c.startswith("-") or c.startswith(":") for c in r)
        ]

        num_cols = len(headers)
        if num_cols == 0:
            return

        # Balanced column widths
        if num_cols == 4:
            # Issue, Art, Begründung, Betrifft Nachbarteams?
            col_widths = [75.0, 90.0, 220.28, 120.0]
        elif num_cols == 3:
            col_widths = [110.0, 275.28, 120.0]
        else:
            col_widths = [CONTENT_WIDTH / num_cols] * num_cols

        layout = PangoCairo.create_layout(cr)

        def draw_header_row() -> float:
            # Determine header height dynamically from wrapped text
            header_cell_markups = [
                f'<span font="Sans Bold 8" color="#ffffff">'
                f'{escape_pango(h)}</span>'
                for h in headers
            ]
            max_hdr_h = 18.0
            for i, markup in enumerate(header_cell_markups):
                w = col_widths[i] if i < len(col_widths) else 80.0
                layout.set_markup(markup)
                layout.set_width(int((w - 8.0) * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                _, rect = layout.get_extents()
                ch = (rect.height / Pango.SCALE) + 6.0
                if ch > max_hdr_h:
                    max_hdr_h = ch

            cr.set_source_rgb(0.2, 0.28, 0.38)
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, max_hdr_h)
            cr.fill()

            cx = MARGIN_X
            for i, markup in enumerate(header_cell_markups):
                w = col_widths[i] if i < len(col_widths) else 80.0
                layout.set_markup(markup)
                layout.set_width(int((w - 8.0) * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                cr.move_to(cx + 4.0, self.current_y + 3.0)
                PangoCairo.show_layout(cr, layout)
                cx += w
            return max_hdr_h

        self.check_page_break(35.0)
        self.current_y += draw_header_row()

        if not data_rows:
            self.current_y += 4.0
            return

        # Render data rows
        for r_idx, row in enumerate(data_rows):
            cell_markups = []
            max_cell_h = 14.0

            for i, cell_txt in enumerate(row):
                w = col_widths[i] if i < len(col_widths) else 80.0
                markup = inline_markdown_to_pango(cell_txt)
                cell_markups.append(markup)
                layout.set_markup(
                    f'<span font="Sans 7.5" color="#1e293b">{markup}</span>'
                )
                layout.set_width(int((w - 8.0) * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                _, rect = layout.get_extents()
                cell_h = (rect.height / Pango.SCALE) + 4.5
                if cell_h > max_cell_h:
                    max_cell_h = cell_h

            if self.current_y + max_cell_h > (PAGE_HEIGHT - MARGIN_BOTTOM):
                self.new_page()
                self.current_y += draw_header_row()

            # Background color
            bg = (0.97, 0.98, 0.99) if r_idx % 2 == 1 else (1.0, 1.0, 1.0)
            cr.set_source_rgb(*bg)
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, max_cell_h)
            cr.fill()

            # Border
            cr.set_source_rgb(0.85, 0.88, 0.92)
            cr.set_line_width(0.5)
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, max_cell_h)
            cr.stroke()

            # Render cell texts
            cx = MARGIN_X
            for i, markup in enumerate(cell_markups):
                w = col_widths[i] if i < len(col_widths) else 80.0
                layout.set_markup(
                    f'<span font="Sans 7.5" color="#1e293b">{markup}</span>'
                )
                layout.set_width(int((w - 8.0) * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                cr.move_to(cx + 4.0, self.current_y + 3.0)
                PangoCairo.show_layout(cr, layout)
                layout.set_width(-1)
                cx += w

            self.current_y += max_cell_h

        self.current_y += 6.0

    def draw_missing_teams_page(
        self, missing_teams: List[Dict[str, Any]]
    ) -> None:
        """Render consolidated page for all missing team reports."""
        if not missing_teams:
            return

        self.new_page()
        cr = self.cr

        # Page Banner (height: 48pt)
        banner_h = 48.0
        cr.set_source_rgb(0.45, 0.15, 0.15)  # Muted deep red
        cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, banner_h)
        cr.fill()

        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(
            Pango.font_description_from_string("Sans Bold 12")
        )
        layout.set_markup(
            '<span color="#ffffff">Ausstehende Statusberichte '
            f'(Sprint {self.sprint_num})</span>'
        )
        cr.move_to(MARGIN_X + 12.0, self.current_y + 7.0)
        PangoCairo.show_layout(cr, layout)

        desc_meta = Pango.font_description_from_string("Sans 8.5")
        layout.set_font_description(desc_meta)
        layout.set_markup(
            f'<span color="#fecaca">'
            f'{len(missing_teams)} Teams ohne eingereichten Bericht '
            f'zum offiziellen Stichtag</span>'
        )
        cr.move_to(MARGIN_X + 12.0, self.current_y + 27.0)
        PangoCairo.show_layout(cr, layout)

        self.current_y += banner_h + 16.0

        # Introductory explanation
        layout.set_markup(
            f'<span font="Sans 8" color="#334155">'
            f'Die folgenden Teams haben bis zum Abgabetermin am Sonntagabend '
            f'noch keinen wöchentlichen Statusbericht für Sprint '
            f'{self.sprint_num} in ihrem jeweiligen Teamverzeichnis '
            f'unter <tt>docs/content/project/statusberichte/&lt;team&gt;/</tt> '
            f'hinterlegt. Die Ansprechpersonen wurden benachrichtigt.'
            f'</span>'
        )
        layout.set_width(int(CONTENT_WIDTH * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        _, rect = layout.get_extents()
        lh = (rect.height / Pango.SCALE) + 12.0
        cr.move_to(MARGIN_X, self.current_y)
        PangoCairo.show_layout(cr, layout)
        layout.set_width(-1)
        self.current_y += lh

        # Render an info box for each missing team with dynamic height
        for t in missing_teams:
            name_esc = escape_pango(t["name"])
            lead_esc = escape_pango(t["lead"])
            path_esc = escape_pango(
                f"docs/content/project/statusberichte/{t['id']}/"
                f"sprint-{self.sprint_num}.mdx"
            )

            box_markup = (
                f'<span font="Sans Bold 9" color="#991b1b">'
                f'{name_esc}</span>   '
                f'<span font="Sans 8" color="#475569">'
                f'(Ansprechperson: {lead_esc})</span>\n'
                f'<span font="Sans 7.5" color="#7f1d1d">'
                f'Status: ⚠️ Ausstehend   |   Erwartete Datei: '
                f'<tt>{path_esc}</tt></span>'
            )
            layout.set_markup(box_markup)
            layout.set_width(int((CONTENT_WIDTH - 24.0) * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            _, rect = layout.get_extents()
            box_h = (rect.height / Pango.SCALE) + 16.0

            self.check_page_break(box_h + 8.0)

            cr.set_source_rgb(0.99, 0.96, 0.96)
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, box_h)
            cr.fill()

            cr.set_source_rgb(0.85, 0.35, 0.35)
            cr.set_line_width(0.75)
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, box_h)
            cr.stroke()

            # Left accent indicator bar
            cr.set_source_rgb(0.8, 0.2, 0.2)
            cr.rectangle(MARGIN_X, self.current_y, 4.0, box_h)
            cr.fill()

            cr.move_to(MARGIN_X + 12.0, self.current_y + 8.0)
            PangoCairo.show_layout(cr, layout)
            layout.set_width(-1)

            self.current_y += box_h + 8.0

    def generate(self) -> None:
        """Render all document pages."""
        self.draw_cover_page()

        submitted_teams = [t for t in self.team_data if t["info"]["exists"]]
        missing_teams = [
            t for t in self.team_data if not t["info"]["exists"]
        ]

        # Render submitted reports first
        for team in submitted_teams:
            self.draw_team_report(team)

        # Render missing teams
        if self.separate_missing:
            for team in missing_teams:
                self.draw_team_report(team)
        else:
            self.draw_missing_teams_page(missing_teams)

        self.draw_decorations()
        self.surface.show_page()
        self.surface.finish()


def collect_team_status(
    status_base_dir: str, sprint_num: int
) -> List[Dict[str, Any]]:
    """Gather status report data for all teams for the given sprint."""
    results = []
    for team in TEAMS:
        team_id = team["id"]
        team_dir = os.path.join(status_base_dir, team_id)
        report_file = find_team_report_file(team_dir, sprint_num)
        info = parse_status_file(report_file)
        results.append(
            {
                "id": team_id,
                "name": team["name"],
                "lead": team["lead"],
                "report_path": report_file,
                "info": info,
            }
        )
    return results


def export_pdf(
    status_dir: str,
    sprint_num: int,
    output_path: str,
    separate_missing: bool = False,
) -> Tuple[int, int]:
    """Execute two-pass rendering to produce exact total page numbers."""
    team_data = collect_team_status(status_dir, sprint_num)

    # Pass 1: Render to dummy surface to compute exact total page count
    dummy_path = "/tmp/status_report_dummy.pdf"
    pass1_builder = PDFBuilder(
        dummy_path,
        sprint_num,
        team_data,
        total_pages=1,
        separate_missing=separate_missing,
    )
    pass1_builder.generate()
    total_pages = pass1_builder.current_page
    if os.path.exists(dummy_path):
        os.remove(dummy_path)

    # Pass 2: Render actual PDF with correct total pages
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    pass2_builder = PDFBuilder(
        output_path,
        sprint_num,
        team_data,
        total_pages=total_pages,
        separate_missing=separate_missing,
    )
    pass2_builder.generate()

    submitted = sum(1 for t in team_data if t["info"]["exists"])
    return total_pages, submitted


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Export weekly sprint status reports to bundled PDF."
    )
    parser.add_argument(
        "--sprint",
        type=int,
        default=1,
        help="Sprint number to export (default: 1)",
    )
    parser.add_argument(
        "--status-dir",
        type=str,
        default="docs/content/project/statusberichte",
        help="Path to statusberichte directory",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Target output PDF path",
    )
    parser.add_argument(
        "--separate-missing",
        action="store_true",
        help="Render individual placeholder pages for each missing team",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only display status summary without writing PDF",
    )

    args = parser.parse_args()

    workspace_root = os.getcwd()
    status_dir = os.path.abspath(os.path.join(workspace_root, args.status_dir))

    if args.output is None:
        out_path = os.path.join(
            status_dir, f"Sprint_{args.sprint}_Gesamtstatus.pdf"
        )
    else:
        out_path = os.path.abspath(args.output)

    team_data = collect_team_status(status_dir, args.sprint)

    # Print terminal summary
    print("=" * 70)
    print(f"Statusberichte Übersicht - Sprint {args.sprint}")
    print("=" * 70)
    submitted_count = 0
    missing_teams = []

    for t in team_data:
        info = t["info"]
        if info["exists"]:
            submitted_count += 1
            print(
                f"[OK]   {t['name']:<35} | {info['status_light']:<15} | "
                f"Datei: {info['filename']}"
            )
        else:
            missing_teams.append(t["name"])
            print(
                f"[MISS] {t['name']:<35} | ⚠️ FEHLT          | "
                f"Lead: {t['lead']}"
            )

    print("-" * 70)
    print(
        f"Zusammenfassung: {submitted_count} von {len(team_data)} "
        f"Teams haben ihr Protokoll eingereicht."
    )

    if missing_teams:
        print("\nAusstehende Teams:")
        for m in missing_teams:
            print(f"  - {m}")

    if args.check_only:
        return

    print("\nGeneriere gebündeltes PDF...")
    total_pages, submitted = export_pdf(
        status_dir,
        args.sprint,
        out_path,
        separate_missing=args.separate_missing,
    )
    print(f"Erfolg! PDF gespeichert: {out_path}")
    print(f"Seitenanzahl: {total_pages} Seiten")
    print("=" * 70)


if __name__ == "__main__":
    main()

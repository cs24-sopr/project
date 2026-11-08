#!/usr/bin/env python3
"""
Bundle team status report MDX files into a single consolidated PDF.

Directly converts the MDX reports written by the teams in
docs/content/project/statusberichte/ into one bundled PDF document
without adding artificial summaries, cover pages, or commentary.
"""

import argparse
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
MARGIN_X = 40.0
MARGIN_TOP = 30.0
MARGIN_BOTTOM = 30.0
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN_X
CONTENT_HEIGHT = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

# Standard team ordering for the collection
TEAM_DIRS = [
    "orga-lead-infra",
    "builder",
    "asset-design",
    "recherche-publishing-courses",
    "coding-interactions",
    "story-design",
]


def escape_pango(text: str) -> str:
    """Escape text for Pango markup."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def inline_markdown_to_pango(text: str) -> str:
    """Convert inline markdown to Pango markup."""
    code_tokens: List[str] = []

    def save_code(match: re.Match) -> str:
        code_tokens.append(match.group(1))
        return f"§§CODE{len(code_tokens) - 1}§§"

    text = re.sub(r"`([^`]+)`", save_code, text)
    text = escape_pango(text)

    # Bold: **bold** or __bold__
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__([^_]+)__", r"<b>\1</b>", text)

    # Italic: *italic* or _italic_
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    text = re.sub(r"_([^_]+)_", r"<i>\1</i>", text)

    # Restore code spans
    for idx, code in enumerate(code_tokens):
        escaped = escape_pango(code)
        markup = (
            f'<span font_family="Monospace" font_size="7.5pt" '
            f'background="#f1f5f9">{escaped}</span>'
        )
        text = text.replace(f"§§CODE{idx}§§", markup)

    return text


def find_team_report(team_path: str, sprint_num: int) -> Optional[str]:
    """Find the status report MDX file for a given team directory."""
    if not os.path.isdir(team_path):
        return None

    # Priority 1: sprint-{num}.mdx or sprint-{num}.md
    for ext in (".mdx", ".md"):
        sprint_file = os.path.join(team_path, f"sprint-{sprint_num}{ext}")
        if os.path.exists(sprint_file):
            return sprint_file

    # Priority 2: corresponding kw files for this sprint
    # (Sprint 1 -> KW44, Sprint 2 -> KW45)
    target_kw = 43 + sprint_num
    candidates = [
        f"kw{target_kw}.mdx",
        f"kw{target_kw}.md",
        f"KW{target_kw}.mdx",
        f"KW{target_kw}.md",
    ]
    for cand in candidates:
        p = os.path.join(team_path, cand)
        if os.path.exists(p):
            return p

    # Priority 3: any other kw files in reverse order
    for kw in range(48, 40, -1):
        for ext in (".mdx", ".md"):
            for prefix in ("kw", "KW"):
                candidate = os.path.join(team_path, f"{prefix}{kw}{ext}")
                if os.path.exists(candidate):
                    return candidate

    # Priority 4: any other non-README mdx/md file
    all_files = [
        f
        for f in os.listdir(team_path)
        if f.endswith((".mdx", ".md")) and not f.startswith("README")
    ]
    if all_files:
        all_files.sort()
        return os.path.join(team_path, all_files[-1])

    return None


class MDXCollectionRenderer:
    """Renders raw team MDX files into a single unified PDF."""

    def __init__(
        self,
        output_path: str,
        files: List[Tuple[str, str]],
        total_pages: int = 1,
    ) -> None:
        self.output_path = output_path
        self.files = files  # List of (team_id, file_path)
        self.total_pages = total_pages
        self.current_page = 1
        self.surface = cairo.PDFSurface(
            output_path, PAGE_WIDTH, PAGE_HEIGHT
        )
        self.cr = cairo.Context(self.surface)
        self.current_y = MARGIN_TOP

    def check_page_break(self, required_height: float) -> None:
        """Advance to next page if vertical room is insufficient."""
        if self.current_y + required_height > (PAGE_HEIGHT - MARGIN_BOTTOM):
            self.new_page()

    def new_page(self) -> None:
        """End current page and start a fresh page."""
        self.draw_footer()
        self.surface.show_page()
        self.current_page += 1
        self.current_y = MARGIN_TOP

    def draw_footer(self) -> None:
        """Draw minimal page footer."""
        cr = self.cr
        cr.set_source_rgb(0.5, 0.55, 0.6)
        layout = PangoCairo.create_layout(cr)
        desc = Pango.font_description_from_string("Sans 8")
        layout.set_font_description(desc)

        # Centered page number
        page_str = f"Seite {self.current_page} von {self.total_pages}"
        layout.set_text(page_str)
        _, rect = layout.get_extents()
        pw = rect.width / Pango.SCALE
        cr.move_to((PAGE_WIDTH - pw) / 2.0, PAGE_HEIGHT - 28.0)
        PangoCairo.show_layout(cr, layout)

    def render_file(self, filepath: str) -> None:
        """Render one MDX report file directly."""
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()

        # Remove YAML frontmatter
        content = re.sub(r"^---\s*\n.*?\n---\s*\n", "", raw, flags=re.DOTALL)
        lines = content.splitlines()

        cr = self.cr
        layout = PangoCairo.create_layout(cr)

        idx = 0
        while idx < len(lines):
            line = lines[idx]

            # Heading 1: # ...
            if line.startswith("# ") and not line.startswith("## "):
                title_text = line.lstrip("#").strip()
                layout.set_markup(
                    f'<span font="Sans Bold 14" color="#0f172a">'
                    f'{escape_pango(title_text)}</span>'
                )
                _, rect = layout.get_extents()
                th = (rect.height / Pango.SCALE)
                self.check_page_break(th + 16.0)
                cr.move_to(MARGIN_X, self.current_y)
                PangoCairo.show_layout(cr, layout)

                # Clean divider below title
                line_y = self.current_y + th + 4.0
                cr.set_source_rgb(0.85, 0.88, 0.92)
                cr.set_line_width(0.75)
                cr.move_to(MARGIN_X, line_y)
                cr.line_to(PAGE_WIDTH - MARGIN_X, line_y)
                cr.stroke()

                self.current_y = line_y + 8.0
                idx += 1
                continue

            # Heading 2 or 3: ## ... or ### ...
            if line.startswith("## ") or line.startswith("### "):
                header_text = line.lstrip("#").strip()
                layout.set_markup(
                    f'<span font="Sans Bold 9.5" color="#1e293b">'
                    f'{escape_pango(header_text)}</span>'
                )
                _, rect = layout.get_extents()
                hh = (rect.height / Pango.SCALE)
                # Ensure heading stays with at least first item
                self.check_page_break(hh + 18.0)

                # Add comfortable spacing before heading
                self.current_y += 4.0
                cr.move_to(MARGIN_X, self.current_y)
                PangoCairo.show_layout(cr, layout)
                self.current_y += hh + 3.0
                idx += 1
                continue

            # Horizontal rule: ---, ***, ___
            if re.match(r"^(\*{3,}|-{3,}|_{3,})$", line.strip()):
                self.check_page_break(10.0)
                cr.set_source_rgb(0.88, 0.9, 0.94)
                cr.set_line_width(0.5)
                line_y = self.current_y + 3.0
                cr.move_to(MARGIN_X, line_y)
                cr.line_to(PAGE_WIDTH - MARGIN_X, line_y)
                cr.stroke()
                self.current_y = line_y + 5.0
                idx += 1
                continue

            # Blockquote: > ...
            if line.startswith(">"):
                quote_text = line.lstrip("> ").strip()
                layout.set_markup(
                    f'<span font="Sans Italic 8" color="#475569">'
                    f'{escape_pango(quote_text)}</span>'
                )
                layout.set_width(int((CONTENT_WIDTH - 20.0) * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                _, rect = layout.get_extents()
                lh = (rect.height / Pango.SCALE) + 4.0
                self.check_page_break(lh)

                # Left bar
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
                    indent_chars = len(line) - len(line.lstrip())
                    prefix = "• " if indent_chars < 4 else "◦ "
                    clean_line = prefix + clean_line

                indent = len(line) - len(line.lstrip())
                indent_x = MARGIN_X + (indent * 4.5)

                markup = inline_markdown_to_pango(clean_line)
                layout.set_markup(
                    f'<span font="Sans 7.5" color="#1e293b">{markup}</span>'
                )
                w = CONTENT_WIDTH - (indent * 4.5)
                layout.set_width(int(w * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                _, rect = layout.get_extents()
                lh = (rect.height / Pango.SCALE) + 0.8
                self.check_page_break(lh)

                cr.move_to(indent_x, self.current_y)
                PangoCairo.show_layout(cr, layout)
                layout.set_width(-1)
                self.current_y += lh
                idx += 1
                continue

            # Plain paragraph text
            if line.strip():
                markup = inline_markdown_to_pango(line.strip())
                layout.set_markup(
                    f'<span font="Sans 7.5" color="#334155">{markup}</span>'
                )
                layout.set_width(int(CONTENT_WIDTH * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                _, rect = layout.get_extents()
                lh = (rect.height / Pango.SCALE) + 1.5
                self.check_page_break(lh)

                cr.move_to(MARGIN_X, self.current_y)
                PangoCairo.show_layout(cr, layout)
                layout.set_width(-1)
                self.current_y += lh

            idx += 1

    def render_table(self, table_lines: List[str]) -> None:
        """Render parsed markdown table lines."""
        if len(table_lines) < 2:
            return

        cr = self.cr

        # Parse cells
        raw_rows: List[List[str]] = []
        for line in table_lines:
            cells = [c.strip() for c in line.strip().split("|")[1:-1]]
            raw_rows.append(cells)

        headers = raw_rows[0]
        data_rows = [
            r
            for r in raw_rows[1:]
            if not all(c.startswith("-") or c.startswith(":") for c in r)
        ]

        num_cols = len(headers)
        if num_cols == 0:
            return

        # Width distribution
        if num_cols == 4:
            # Issue, Art, Begründung, Betrifft Nachbarteams?
            col_widths = [75.0, 90.0, 220.28, 120.0]
        elif num_cols == 3:
            col_widths = [110.0, 275.28, 120.0]
        else:
            col_widths = [CONTENT_WIDTH / num_cols] * num_cols

        layout = PangoCairo.create_layout(cr)

        def draw_header_row() -> float:
            markups = [
                f'<span font="Sans Bold 8" color="#1e293b">'
                f'{escape_pango(h)}</span>'
                for h in headers
            ]
            max_h = 18.0
            for i, m in enumerate(markups):
                w = col_widths[i] if i < len(col_widths) else 80.0
                layout.set_markup(m)
                layout.set_width(int((w - 8.0) * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                _, rect = layout.get_extents()
                ch = (rect.height / Pango.SCALE) + 6.0
                if ch > max_h:
                    max_h = ch

            # Subtle gray header
            cr.set_source_rgb(0.93, 0.94, 0.96)
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, max_h)
            cr.fill()

            # Border
            cr.set_source_rgb(0.8, 0.83, 0.88)
            cr.set_line_width(0.75)
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, max_h)
            cr.stroke()

            cx = MARGIN_X
            for i, m in enumerate(markups):
                w = col_widths[i] if i < len(col_widths) else 80.0
                layout.set_markup(m)
                layout.set_width(int((w - 8.0) * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                cr.move_to(cx + 4.0, self.current_y + 3.0)
                PangoCairo.show_layout(cr, layout)
                cx += w
            return max_h

        self.check_page_break(35.0)
        self.current_y += draw_header_row()

        if not data_rows:
            self.current_y += 6.0
            return

        for r_idx, row in enumerate(data_rows):
            cell_markups = []
            max_cell_h = 16.0

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
                ch = (rect.height / Pango.SCALE) + 6.0
                if ch > max_cell_h:
                    max_cell_h = ch

            if self.current_y + max_cell_h > (PAGE_HEIGHT - MARGIN_BOTTOM):
                self.new_page()
                self.current_y += draw_header_row()

            # Alternating white / very light gray rows
            bg = (0.98, 0.99, 1.0) if r_idx % 2 == 1 else (1.0, 1.0, 1.0)
            cr.set_source_rgb(*bg)
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, max_cell_h)
            cr.fill()

            # Border
            cr.set_source_rgb(0.85, 0.88, 0.92)
            cr.set_line_width(0.5)
            cr.rectangle(MARGIN_X, self.current_y, CONTENT_WIDTH, max_cell_h)
            cr.stroke()

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

        self.current_y += 5.0

    def generate(self) -> None:
        """Render all team files sequentially with page breaks in between."""
        for idx, (team_id, file_path) in enumerate(self.files):
            if idx > 0:
                self.new_page()
            self.render_file(file_path)

        self.draw_footer()
        self.surface.show_page()
        self.surface.finish()


def collect_report_files(
    status_dir: str, sprint_num: int, include_ri: bool = True
) -> List[Tuple[str, str]]:
    """Gather all available MDX reports across teams."""
    files = []
    if include_ri:
        ri_dir = os.path.join(status_dir, "ri-wochenberichte")
        ri_file = find_team_report(ri_dir, sprint_num)
        if ri_file and os.path.exists(ri_file):
            files.append(("ri-wochenberichte", ri_file))
    for team_id in TEAM_DIRS:
        team_dir = os.path.join(status_dir, team_id)
        report_file = find_team_report(team_dir, sprint_num)
        if report_file and os.path.exists(report_file):
            files.append((team_id, report_file))
    return files


def export_pdf(
    status_dir: str,
    sprint_num: int,
    output_path: str,
    include_ri: bool = True,
) -> Tuple[int, List[Tuple[str, str]]]:
    """Execute two-pass rendering to produce bundled PDF."""
    files = collect_report_files(status_dir, sprint_num, include_ri)
    if not files:
        print("Keine Statusberichte gefunden.")
        return 0, []

    # Pass 1: compute total page count
    dummy_path = "/tmp/bundle_dummy.pdf"
    pass1 = MDXCollectionRenderer(dummy_path, files, total_pages=1)
    pass1.generate()
    total_pages = pass1.current_page
    if os.path.exists(dummy_path):
        os.remove(dummy_path)

    # Pass 2: actual rendering
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    pass2 = MDXCollectionRenderer(
        output_path, files, total_pages=total_pages
    )
    pass2.generate()

    return total_pages, files


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Bundle team status report MDX files into a single PDF."
    )
    parser.add_argument(
        "--sprint",
        type=int,
        default=1,
        help="Sprint number to bundle (default: 1)",
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
        "--check-only",
        action="store_true",
        help="List found files without generating PDF",
    )
    parser.add_argument(
        "--no-ri",
        dest="include_ri",
        action="store_false",
        default=True,
        help="Exclude RI update from the bundle (included by default)",
    )

    args = parser.parse_args()

    workspace_root = os.getcwd()
    status_dir = os.path.abspath(os.path.join(workspace_root, args.status_dir))

    if args.output is None:
        out_path = os.path.join(
            workspace_root,
            "exports",
            "statusberichte",
            f"Sprint_{args.sprint}_Statusberichte.pdf",
        )
    else:
        out_path = os.path.abspath(args.output)

    files = collect_report_files(
        status_dir, args.sprint, include_ri=args.include_ri
    )

    print("=" * 70)
    print(f"Gefundene Berichte für Sprint {args.sprint}:")
    print("=" * 70)
    for team_id, fpath in files:
        rel_path = os.path.relpath(fpath, workspace_root)
        print(f"  • {team_id:<32} -> {rel_path}")

    missing = [t for t in TEAM_DIRS if not any(t == f[0] for f in files)]
    if missing:
        print("\nOhne Bericht in diesem Sprint:")
        for m in missing:
            print(f"  • {m}")
    print("=" * 70)

    if args.check_only:
        return

    print("\nGeneriere gebündeltes PDF...")
    total_pages, _ = export_pdf(
        status_dir, args.sprint, out_path, include_ri=args.include_ri
    )
    print(f"Erfolg! PDF gespeichert: {out_path}")
    print(f"Enthaltene Berichte: {len(files)} Teams")
    print(f"Gesamtseiten: {total_pages}")
    print("=" * 70)


if __name__ == "__main__":
    main()

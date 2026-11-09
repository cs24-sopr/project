# Changelog

All notable changes to this project will be documented in this file.

## [2026-11-08]

### Changed

- Updated Docusaurus callout syntax across guideline documents.
- Removed redundant issue creation steps in `agiles-arbeiten.mdx` in favour of
  direct references.

## [2026-11-06]

### Changed

- Streamlined GitHub Issue Form `task.yml` to focus strictly on essential
  fields (WHAT, HOW, TEST) and automated board linking (`projects`), removing
  redundant pseudo-metadata form fields.

## [2026-11-04]

### Added

- GitHub Issue Form `task.yml` for structured task, feature, and requirement
  creation (`.github/ISSUE_TEMPLATE/task.yml`).
- Documentation for issue template approach and YAML form guidelines in
  `docs/content/project/richtlinien/issue-templates.mdx`.
- Cross-references to the issue template guide in `agiles-arbeiten.mdx`,
  `project-board.mdx`, `anforderungsmanagement.mdx`, and `anleitung.mdx`.

### Changed

- Migrated organisation issue template from legacy markdown (`task.md`) to
  structured GitHub Issue Form (`task.yml`).

### Removed

- Deprecated legacy markdown issue template (`.github/ISSUE_TEMPLATE/task.md`).

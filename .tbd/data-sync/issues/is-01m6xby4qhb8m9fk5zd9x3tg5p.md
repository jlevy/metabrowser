---
type: is
id: is-01m6xby4qhb8m9fk5zd9x3tg5p
title: Correct fresh-release verification commands and trust overview
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6wdjwawp9g1bvnefz2hxze3
created_at: 2026-11-08T10:40:46.832Z
updated_at: 2026-11-08T10:40:46.832Z
---
Read-only release-doc review at1ede1e220 found three bounded gaps, to correct in a separate docs PR after the frozen prefetch gate. D1 Medium: docs/publishing.md fresh-release uvx probes omit the package-scoped cool-off exception/cache refresh already used in publish.yml; mirror that recipe portably on macOS while preserving dependency cool-off. D2 Medium: public Agent Skill release check uses floating npx installer and main source despite installation.md requiring reviewed exact installer/source pins for automation. Verify current official CLI tag/full-commit syntax, document pins and compare installed bytes with approved RELEASE_COMMIT; local verified-existing-content receipts are not public installer evidence. D3 Low: README trust-switch summary omits0.12 inert Markdown and shell CSP behavior already documented in command-line.md, CHANGELOG and CLI source. Review actual docs/flags, preserve user approval of exact commit/notes before any tag/publication, and keep all final acceptance gates open. Private report: release-docs-readiness-20261108/report.md; no new product defect or untracked acceptance requirement identified. Future mb-itzy remains paused.

---
type: is
id: is-01m88wfn2yajt34x77vftk8cm6
title: Fold expanders draw KPress's expand/contract pair, not the disclosure chevron
kind: task
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T08:17:18.416Z
updated_at: 2026-11-25T09:59:32.890Z
started_at: 2026-11-25T08:18:43.915Z
closed_at: 2026-11-25T09:59:32.889Z
close_reason: "Merged in #833"
resolution: null
duplicate_of: null
---
User request 2026-11-25: folded lines and blocks in the PR view (every .fold-expander: the diff fold bar for code runs, Markdown unchanged blocks and hunk gaps, and the pull page hunk earlier-lines summary) use the expand/contract icon pair KPress TOC uses (Lucide chevrons-up-down when closed, chevrons-down-up when open) instead of the rotating > chevron. The rotating chevron stays for disclosures of a row. Update the design system (Fold Expanders, the One Chevron rule, the icon catalog) so the conventions are aligned and enforced.

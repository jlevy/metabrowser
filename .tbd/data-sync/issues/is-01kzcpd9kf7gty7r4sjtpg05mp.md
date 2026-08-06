---
type: is
id: is-01kzcpd9kf7gty7r4sjtpg05mp
title: "lint.py: exclude attic/ from Markdown doc lint paths"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-06T23:26:50.991Z
updated_at: 2026-08-06T23:33:22.675Z
closed_at: 2026-08-06T23:33:22.674Z
close_reason: Added attic to DOC_PATHS exclusion set in devtools/lint.py
---
devtools/lint.py DOC_PATHS rglobs all *.md with a fixed exclusion set that omits attic/. The checkout-third-party-repo shortcut creates gitignored attic/ checkouts, whose Markdown then fails codespell in make lint-check / make verify. Fix: add 'attic' to the exclusion set.

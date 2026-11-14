---
type: is
id: is-01m7dqr8dg594qf7mjq3hdr9xd
title: "Docs checks: links resolve, documents reachable, no tracker IDs in guides"
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmd3wafkq2x9r1y2gt57v
created_at: 2026-11-14T19:15:07.824Z
updated_at: 2026-11-14T19:15:07.824Z
---
Phase 1, PR 1 (spec: New Checks 1-3). Lands first; the rest of the stack rebases on it.

Add to tests/test_docs_discipline.py, each proven by a failing fixture (pattern: tests/test_experiment_storage.py):

1. Links resolve: every relative link in human-authored Markdown, every github.com/jlevy/metabrowser/blob/main/ link, and every document path named in src/ and apps/ names an existing file and heading anchor. Anchors via heading_slug in src/metabrowser/inert_html.py after stripping inline Markdown, with GitHub repeat numbering (the private _Anchors class does that today). Exempt docs/tbd/, tests/golden/, .tbd/.
2. Reachability: links from README.md reach every docs/*.md outside docs/project/ and docs/tbd/; links from docs/project/README.md reach every file under docs/project/.
3. No bead IDs (whole tokens; data-mb-copy must not match) in README.md, the user guides in the spec's map, skills/metabrowser/SKILL.md, and apps/macos/README.md.

Fix whatever they find. An approximate scan found no broken relative links at c098e6a8.

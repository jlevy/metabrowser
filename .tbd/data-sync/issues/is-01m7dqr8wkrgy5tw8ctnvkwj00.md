---
type: is
id: is-01m7dqr8wkrgy5tw8ctnvkwj00
title: "README: app icon, thesis, and first-principles outline"
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmd3wafkq2x9r1y2gt57v
created_at: 2026-11-14T19:15:08.306Z
updated_at: 2026-11-15T05:56:36.146Z
---
Phase 1, PR 2 (spec: The README).

- Title block: `<p align="center"><img src="images/metabrowser-icon.png" alt="Metabrowser app icon" width="192"></p>` then `<h1 align="center">Metabrowser</h1>`. Relative path (spec open question 3 covers PyPI).
- Extend apps/macos/scripts/build-icon.sh to render images/metabrowser-icon.png at 512 px from apps/macos/AppIcon/metabrowser-icon.svg (the release master, not the gold-rimmed dev master) with AppIcon/render-svg.swift. Compile it with `swiftc -O` as the script does; the interpreted `swift` path takes minutes. Add the file to AppIcon/README.md's table.
- Thesis in three sentences (the author approves the wording), a refreshed Files-tab screenshot of this repository with no personal paths, a short first-person Why, Quick Start, What You Can Do (linking guides as they exist), Mac App, Scale (hundreds of thousands of files; link docs/scale-benchmark.md once it exists; no figures), Extend It, Security (three lines), Direction (planned pillars; the engine named only as a faster native inventory engine), Documentation index, Contributing and License. About 150 lines.
- Remove to their owners: trust flags, plugin discovery order, developer tool versions, File Rollup Format, link and transclusion semantics, shortcut scheme.
- Drop stale claims: "100,000 files or more" (README:87; the serving cap is 500,000) and "commit graph beside the file tree" (README:101; Commits is a main tab).
- Verify rendering on GitHub (the pull request view) and with `metab .` on the branch.

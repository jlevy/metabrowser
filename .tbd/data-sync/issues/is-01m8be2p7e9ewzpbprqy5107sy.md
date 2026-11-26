---
type: is
id: is-01m8be2p7e9ewzpbprqy5107sy
title: One SDK helper that ensures and applies the repository links, so no surface can forget the load
kind: task
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
hold: null
hold_until: null
created_at: 2026-11-26T08:03:16.846Z
updated_at: 2026-11-26T19:07:57.294Z
started_at: 2026-11-26T19:07:57.294Z
---
From the Fable review of #874 (design rec 8): every consumer calls ensureAsset('repository-links') then window.MetabrowserRepositoryLinks?.enhance, so a forgotten load degrades silently to github.com links. A helper in the on-demand sdk-views bundle (not the startup scripts, which are at budget) would make that impossible by construction.

---
type: is
id: is-01m6t6db612aj6w19qbxhcrp9a
title: Rename the Git navigation tab to Commits
kind: task
status: closed
priority: 2
version: 5
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T05:06:30.208Z
updated_at: 2026-11-07T05:53:26.331Z
started_at: 2026-11-07T05:07:08.055Z
closed_at: 2026-11-07T05:53:26.331Z
close_reason: "Implemented and independently reviewed in PR #321; full local verification and all CI passed, exact build installed, both preview modes verified."
resolution: null
duplicate_of: null
---
Use Commits for the visible main navigation tab and its shortcut help. Keep the fixed second shortcut position and independently remembered tab selection. Verify the installed left-aligned Markdown/README layout with its right-side KPress TOC and compact drawer, update current documentation, and publish as a new stacked PR.

## Notes

Completed in https://github.com/jlevy/metabrowser/pull/321 at a7d3c0139a12204fc556da463dbc2c8e40f3bc1a, appended above #320 in native stack #302. Independent review and Qodo found no material issues; all nine current-head CI jobs passed and the PR is CLEAN/MERGEABLE. Full make verify: 4892 tests passed with nine expected skips, 384 golden scenarios, both audits and installed distribution checks. Built-in-browser checks verified Commits, shortcut Help/selection, both repository modes, left-aligned README prose, desktop right-side TOC, and narrow drawer navigation. Installed exact wheel 0.11.1.dev1216+a7d3c013 for both CLI aliases and replaced both preview servers, preserving normal user settings/cache. Durable evidence: /Volumes/spud-ext2/agent-evidence/metabrowser-commits-tab-20261107/. Source worktree clean; owner merge only.

---
type: is
id: is-01m83qnf0r556qas7pn6vwdfat
title: "PR #745 A4: no test reaches sectionForPath, pathForSection, the page's place-by-file wiring, or the pullChanges history memory"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T08:16:53.782Z
updated_at: 2026-11-23T09:29:18.085Z
started_at: 2026-11-23T08:20:24.490Z
closed_at: 2026-11-23T09:29:18.059Z
close_reason: "Fixed in 59ca188c9: diff-file-jump-session.js pins sectionForPath and pathForSection; github-pull-changes-follow-behavior.js drives the mounted page with a section map and a history entry. Dispositions: https://github.com/jlevy/metabrowser/pull/745#issuecomment-7096707973"
resolution: null
duplicate_of: null
---
Review A of #745. grep over tests/ finds no reference to sectionForPath, pathForSection, or pullChanges; the mounted-page tests use a stand-in diff view and no history state. The pure functions (followedFrom, followedNote, rememberedChanges, scrollTopOf, holdAt) are pinned, but returning null from both diff-view accessors, or never writing pullChanges, fails nothing. Add a diff-view DOM test for the two accessors (a renamed file by its old path, a deleted file, a disposed view) and a mounted-page test that follows a head with a real section map and a history stand-in, then mounts again on that entry.

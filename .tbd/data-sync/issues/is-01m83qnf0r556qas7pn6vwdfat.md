---
type: is
id: is-01m83qnf0r556qas7pn6vwdfat
title: "PR #745 A4: no test reaches sectionForPath, pathForSection, the page's place-by-file wiring, or the pullChanges history memory"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
created_at: 2026-11-23T08:16:53.782Z
updated_at: 2026-11-23T08:16:53.782Z
---
Review A of #745. grep over tests/ finds no reference to sectionForPath, pathForSection, or pullChanges; the mounted-page tests use a stand-in diff view and no history state. The pure functions (followedFrom, followedNote, rememberedChanges, scrollTopOf, holdAt) are pinned, but returning null from both diff-view accessors, or never writing pullChanges, fails nothing. Add a diff-view DOM test for the two accessors (a renamed file by its old path, a deleted file, a disposed view) and a mounted-page test that follows a head with a real section map and a history stand-in, then mounts again on that entry.

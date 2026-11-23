---
type: is
id: is-01m83z9hk4cvwb4vnnhkt17t1b
title: "PR #745 B1: a second follow while the followed diff loads writes the top of the page as the reader's place"
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
created_at: 2026-11-23T10:30:11.811Z
updated_at: 2026-11-23T10:52:13.699Z
started_at: 2026-11-23T10:34:31.895Z
closed_at: 2026-11-23T10:52:13.698Z
close_reason: "Fixed in 389508dff on #745: the keeper's holdThrough keeps the held place, else the entry's, while no diff is mounted; three behaviour-test steps fail before and pass after. Dispositions: https://github.com/jlevy/metabrowser/pull/745#issuecomment-7098626515"
resolution: null
duplicate_of: null
---
Review B (follow-up, round 2) of #745, at 5344eff2c. keepPlaceThrough (pull-page.js:7244) holds place.measure(), and measure reads the body. When a second follow (another push read while the first followed diff is still being read), or a press of Show the earlier changes in the note painted over that load, calls showChanges or showEarlier again, the body is the emptied one mountDiff left (host and spinner, no .diff-file blocks), so measure() answers {block:-1,offset:0,top:0} and holdAt writes the top over the reader's kept place. The same happens on a page loaded again on its entry, as a followed pin reloads it on a repository URL, when a push arrives while its first diff is read: the landing's saved place is overwritten. Reproduced with two attic probes built on tests/dom/github-pull-changes-follow-behavior.js: pullPlace goes from {block:2,offset:120,top:1220,file:"c.py"} to {block:-1,offset:0,top:0}, and the pane lands at 0 instead of 1220. Fix: while no diff is mounted (diffHandle null), keep the place the keeper already holds instead of measuring, e.g. const held = place.keeper.snapshot().holding; place.keeper.holdAt(diffHandle === null && held !== null ? held : place.measure()); verified against both probes and the existing behaviour test. Add the second push during the gate, and the reload variant, as steps of the behaviour test.

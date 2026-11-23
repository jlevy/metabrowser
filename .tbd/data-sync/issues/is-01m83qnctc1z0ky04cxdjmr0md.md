---
type: is
id: is-01m83qnctc1z0ky04cxdjmr0md
title: "PR #745 A3: a followed Changes diff writes the top of the page as the reader's place while the newer diff loads, so a reload in that window loses the place"
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
created_at: 2026-11-23T08:16:51.502Z
updated_at: 2026-11-23T09:29:16.285Z
started_at: 2026-11-23T08:20:24.017Z
closed_at: 2026-11-23T09:29:16.282Z
close_reason: "Fixed in 59ca188c9: the place is held and written before mountDiff empties the body; github-pull-changes-follow-behavior.js fails without it. Dispositions: https://github.com/jlevy/metabrowser/pull/745#issuecomment-7096707973"
resolution: null
duplicate_of: null
---
Review A of #745. showChanges measures keepAt and mountDiff empties the body; the pane clamps to the top and the keeper, holding nothing, writes {block:-1,top:0} after PLACE_WRITE_MS. holdAt writes the place back only when the newer diff has mounted. On a repository URL the freshness row reloads the page when the pin follows, at about the same moment, so a comparison slower than 350 ms to read leaves the entry at the top for that reload. Shown at the keeper level by a probe (scrolled, write timer, then holdAt); the browser timing is by reading. Fix: hold keepAt (holding set, written) before mountDiff empties the body, so scrolled() writes nothing until the diff lands.

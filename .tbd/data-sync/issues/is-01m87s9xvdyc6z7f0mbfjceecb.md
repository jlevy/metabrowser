---
type: is
id: is-01m87s9xvdyc6z7f0mbfjceecb
title: "Guided review: tell a moved range from a changed one in a stale guide"
kind: feature
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m87ky2a36j5yg4pf9827xxd6
created_at: 2026-11-24T22:02:30.616Z
updated_at: 2026-11-24T22:02:30.616Z
---
A9 of review A on #795 (https://github.com/jlevy/metabrowser/pull/795). A stale guide's steps are read at the pull request's current comparison, so a ranged reference in a file changed since the guide draws today's lines at the guide's line numbers under the note "This file changed after the guide was written." (or "may have changed" when what changed is unknown). When the store has both comparisons (history ahead or rewritten), the route could also read the reference at the guide's pins and compare rows: only references whose rows differ would get a note or a refusal, and a range that only shifted could be re-anchored to its new lines. Also consider the rename pairing A6 named: count a cited path as changed when its change kind or rename partner differs between the two manifests. Needs a plan for the cost (a second manifest and hydration per stale step) before building.

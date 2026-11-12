---
type: is
id: is-01m78aemsn8khscdby1adb96ch
title: "PR #375 A2: flowmark would reformat CHANGELOG.md"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ae0p02ghts4vw9h2vrmhp
hold: null
hold_until: null
created_at: 2026-11-12T16:46:29.172Z
updated_at: 2026-11-12T17:22:19.034Z
started_at: 2026-11-12T16:46:40.684Z
closed_at: 2026-11-12T17:22:19.028Z
close_reason: "Fixed in bc6a7b4f (flowmark-rs 0.3.2 --auto --no-cache: blank line between entries). Disposition: https://github.com/jlevy/metabrowser/pull/375#issuecomment-6830783051"
resolution: null
duplicate_of: null
---
High. PR #375 review A (https://github.com/jlevy/metabrowser/pull/375#pullrequestreview-5871448143). CHANGELOG.md:24 is 89 characters, past flowmark's 88-column width; the lint job prints Would reformat. Fix: run the pinned flowmark (with --no-cache if the cache hides it) and commit.

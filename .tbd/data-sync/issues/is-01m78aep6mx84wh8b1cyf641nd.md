---
type: is
id: is-01m78aep6mx84wh8b1cyf641nd
title: "PR #375 A5: docs still show the --show views line without keys"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ae0p02ghts4vw9h2vrmhp
hold: null
hold_until: null
created_at: 2026-11-12T16:46:30.611Z
updated_at: 2026-11-12T17:22:20.699Z
started_at: 2026-11-12T16:46:42.063Z
closed_at: 2026-11-12T17:22:20.697Z
close_reason: "Fixed in 5d52b575: docs/command-line.md --show example and QA runbook Pass criteria. Disposition: https://github.com/jlevy/metabrowser/pull/375#issuecomment-6830783051"
resolution: null
duplicate_of: null
---
Medium. PR #375 review A (https://github.com/jlevy/metabrowser/pull/375#pullrequestreview-5871448143). docs/command-line.md:831 prints views: rendered (default), source; docs/qa-v012-repository-library.md:2092-2093 Pass criteria expect preview (default), source and preview, source (default). Fix: update both to the keyed output and say keys print uppercase.

---
type: is
id: is-01m78aep6mx84wh8b1cyf641nd
title: "PR #375 A5: docs still show the --show views line without keys"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ae0p02ghts4vw9h2vrmhp
hold: null
hold_until: null
created_at: 2026-11-12T16:46:30.611Z
updated_at: 2026-11-12T16:46:42.064Z
started_at: 2026-11-12T16:46:42.063Z
---
Medium. PR #375 review A (https://github.com/jlevy/metabrowser/pull/375#pullrequestreview-5871448143). docs/command-line.md:831 prints views: rendered (default), source; docs/qa-v012-repository-library.md:2092-2093 Pass criteria expect preview (default), source and preview, source (default). Fix: update both to the keyed output and say keys print uppercase.

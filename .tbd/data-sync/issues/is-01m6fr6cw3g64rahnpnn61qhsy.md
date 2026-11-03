---
type: is
id: is-01m6fr6cw3g64rahnpnn61qhsy
title: "PR #285 A9: a hold past 500 ms fetches the first press row"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6fr5ndwyynz3p0n04v5nmkt
created_at: 2026-11-03T03:45:38.178Z
updated_at: 2026-11-03T04:45:07.392Z
closed_at: 2026-11-03T04:45:07.391Z
close_reason: "A9 fixed in 6998cc9b: a page a held key opened waits to ask while the key is held. Reply: https://github.com/jlevy/metabrowser/pull/285#issuecomment-6595667497"
resolution: null
duplicate_of: null
---
Low. pulls-panel.js first press opens at once and its page asks to fetch after REFRESH_ASK_MS. Review A https://github.com/jlevy/metabrowser/pull/285#pullrequestreview-5746647815

## Notes

A9 fixed in 6998cc9b: a page a held key opened waits to ask while the key is held. Reply: https://github.com/jlevy/metabrowser/pull/285#issuecomment-6595667497

---
type: is
id: is-01m8be2nhqt2rt2xa90vkcr2qv
title: "Pull request texts: react to metabrowser:pin-changed as rendered diffs do"
kind: task
status: in_progress
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
hold: null
hold_until: null
created_at: 2026-11-26T08:03:16.151Z
updated_at: 2026-11-26T10:28:58.952Z
started_at: 2026-11-26T10:05:09.422Z
---
From the Fable review of #874 (L3): /view/ links in a PR's texts localized 'at the head' keep that address after another tab switches the pin, until the pin guard reloads. Re-run enhance on pin change (it is idempotent and reads the authored href).

## Notes

Security review B of https://github.com/jlevy/metabrowser/pull/874 (round 1, head 2bf458b8) found that rerunning enhance alone kept a previously localized href and click interceptor when the new answer was null, so a refresh fix must restore the original anchor. mb-b6qw (4cea6585, restoreAuthoredLink) restores the authored href, target, and rel; what remains here is the pin-changed listener itself, which b6927a16 may cover for stack pages.

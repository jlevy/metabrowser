---
type: is
id: is-01m7k0jy32db0grxkssw7skzfp
title: "PR #479 B2: the Chrome checks cited for A4 can no longer fail"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7jp047k8p38s3q818n9hvc1
created_at: 2026-11-16T20:25:42.753Z
updated_at: 2026-11-16T21:02:55.630Z
closed_at: 2026-11-16T21:02:55.629Z
close_reason: "Fixed for PR #479 review B at 0727dde7a; disposition reply https://github.com/jlevy/metabrowser/pull/479#issuecomment-6929246126"
resolution: null
duplicate_of: null
---
Low. PR #479 review B (https://github.com/jlevy/metabrowser/pull/479#pullrequestreview-5926995563). tests/dom/git-commit-summary-chrome.mjs:262-263 sweeps 180-400 px in 4 px steps and :376 narrows the hover card to 160 px; with groups dissolved the session still passes. Sweep 60-400 px in 1 px steps, sweep the hover card the same way, confirm both fail with groups dissolved, correct '180 to 400 px' in builtin_plugins/diff/styles.css:108, docs/design-system.md:539-541, arch-views-models-routes.md:1017.

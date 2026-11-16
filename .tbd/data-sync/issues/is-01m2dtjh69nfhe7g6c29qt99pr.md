---
type: is
id: is-01m2dtjh69nfhe7g6c29qt99pr
title: Adopt KPress release containing jlevy/kpress#72 and drop the 0.3.5 code-border fallback
kind: task
status: in_progress
priority: 2
version: 4
delegate: claude-code@spud10.local
labels:
  - kpress
  - upstream
dependencies: []
hold: null
hold_until: null
created_at: 2026-09-13T16:45:56.807Z
updated_at: 2026-11-16T23:52:11.583Z
started_at: 2026-11-16T23:52:11.582Z
---
Metabrowser pins kpress==0.3.5 and sets the public --kpress-code-border / --kpress-code-radius tokens, plus explicit bridge selectors in src/metabrowser/static/styles.css (the comment ending 'the currently pinned KPress 0.3.5 and can leave with that pin') so inline and block monospace share one gentle solid border with zero radius. Upstream PR jlevy/kpress#72 (TOC scrollspy + typography tokens) is green but unmerged. After it merges and KPress publishes a release: KPress is first-party, so upgrade it the standard way; review the full 0.3.5..new diff first (an audit found about 130 files / +20k lines since 0.3.5); bump the pin and uv.lock; delete the bridge selectors; rerun make verify and the KPress dependency-contract tests.

## Notes

2026-11-14 audit: still blocked upstream; jlevy/kpress#72 is open and v0.3.5 is the latest KPress release. Standalone by design (kpress/upstream labels); mb-x0sv and the trusted-path part of mb-jt6l also need a KPress release after 0.3.5.

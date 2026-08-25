---
type: is
id: is-01m0vs8p2ffqnpf1fcfmm11bg2
title: Remove the redundant tooltip from the gear menu trigger
kind: bug
status: closed
priority: 1
version: 4
labels:
  - release:v0.7.1
dependencies:
  - type: blocks
    target: is-01m0vs93dx079avphqe2v0c8y7
parent_id: is-01m0vs8cjjpcz1h53bz34290n5
created_at: 2026-08-25T06:21:03.950Z
updated_at: 2026-08-25T06:30:37.256Z
closed_at: 2026-08-25T06:30:37.255Z
close_reason: Removed the gear trigger tooltip, retained the accessible label, added a rendered-shell regression test, and validated the behavior in the live browser.
resolution: null
duplicate_of: null
---
The gear button opens the Metabrowser menu but also participates in the delayed tooltip system, so the word Metabrowser can appear over or beside the open menu. Reproduce the hover/open timing, add a regression test, remove the trigger from tooltip discovery while preserving its accessible name, and validate the interaction in a real browser.

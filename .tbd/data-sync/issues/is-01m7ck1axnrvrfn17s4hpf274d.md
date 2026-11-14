---
type: is
id: is-01m7ck1axnrvrfn17s4hpf274d
title: "Flaky: Overview alignment test reads the active tab before it is set (900px)"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-14T08:33:27.879Z
updated_at: 2026-11-14T08:33:27.879Z
---
tests/test_folder_overview_alignment.py (#405, budgeted by #409) failed in CI on PR #418 (job 132280637063, test (3.12), 2026-11-14): "900px: the active preview tab: actual undefined, expected Overview" at folder-overview-alignment-chrome.mjs:155, after a 28.2 s cold Chrome launch; phases banner 0.5 s, chrome 28.2 s, navigated 0.1 s, panels 1.3 s, readme 0.1 s, rollup 0.0 s. #418 does not touch the Overview. Likely the measurement reads the active tab before it is rendered or settled at a resized width. Done when the test waits for the condition it measures, repeated runs under load pass, and a real misalignment still fails.

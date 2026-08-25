---
type: is
id: is-01m0w52zzfx6qf6qf8536jxcxh
title: Add a CDP Git revision navigation scenario and baseline
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w539fx31x7vj0rv24twqmm
  - type: blocks
    target: is-01m0w53vkse6krjp4g03k5x7q6
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T09:47:40.399Z
updated_at: 2026-08-25T09:54:51.073Z
closed_at: 2026-08-25T09:54:51.072Z
close_reason: Added the trusted CDP git-revisions scenario, documented its use, captured three visible-Chrome unchanged-product baselines, and passed make verify.
resolution: null
duplicate_of: null
---
Files/functions: extend explorations/performance-loop/capture-browser.js parseArgs, usage, capture, and trusted CDP click helpers; extend explorations/performance-loop/run.py cmd_capture/parser; add a scenario probe module if separation keeps the driver generic; update tests/test_browser_performance_capture.py and performance-loop README. Behavior: --scenario git-revisions opens the Git panel, warms one commit, performs trusted cold and prepared revision clicks, waits for selected/ready DOM milestones and double RAF, records per-transition total/blank time, raw fetch total/server/bytes, phase labels, long work, exceptions, heap, and mounted-resource bounds. Baseline: at least three visible-Chrome runs against the unchanged product on one corpus, stored under .bench. Acceptance: argument/shape tests fail first then pass; scenario rejects missing rows, no diff-ready milestone, extra mounts, blank measurement gaps, and page exceptions; default capture remains byte-for-byte compatible in schema; baseline evidence is reproducible and summarized in the spec/experiment work.

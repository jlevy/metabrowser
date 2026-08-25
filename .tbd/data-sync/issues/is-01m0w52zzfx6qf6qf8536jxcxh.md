---
type: is
id: is-01m0w52zzfx6qf6qf8536jxcxh
title: Add a CDP Git revision navigation scenario and baseline
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w539fx31x7vj0rv24twqmm
  - type: blocks
    target: is-01m0w53vkse6krjp4g03k5x7q6
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T09:47:40.399Z
updated_at: 2026-08-25T10:34:41.146Z
closed_at: 2026-08-25T09:54:51.072Z
close_reason: Added the trusted CDP git-revisions scenario, documented its use, captured three visible-Chrome unchanged-product baselines, and passed make verify.
resolution: null
duplicate_of: null
---
Files/functions: explorations/performance-loop/capture-browser.js parseArgs, usage, dispatchTrustedClickForSelector, dispatchTrustedPointerForSelector, startGitBlankFrameMonitor, stopGitBlankFrameMonitor, waitForGitRevision, measureGitTransition, runGitRevisionScenario, and capture; explorations/performance-loop/run.py cmd_capture and capture parser; tests/test_browser_performance_capture.py; explorations/performance-loop/README.md. Behavior: --scenario git-revisions warms one commit, performs trusted cold and prepared selections, waits for exact selected and double-RAF ready milestones, and records blank frames, raw request total/server/bytes, client labels, long work, exceptions, heap, and mounted comparison count in git-revision-navigation/v1 without changing the initial-load schema or ledger. Acceptance: argument and shape tests pass; missing rows/readiness, extra mounts, page exceptions, and unknown scenarios fail; three visible-Chrome unchanged-product baselines use one frozen corpus.

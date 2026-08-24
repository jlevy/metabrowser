---
type: is
id: is-01m0pe6q1kyxarxs3dx6hht3zz
title: "H51: measure LCP and CLS in a visible window"
kind: task
status: closed
priority: 0
version: 6
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0ppz44v9tdxhhdhhfyxg7c5
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T04:31:32.914Z
updated_at: 2026-08-24T04:15:29.175Z
closed_at: 2026-08-24T04:15:29.174Z
close_reason: Four admissible visible 1600x900 harness-14 runs per installed build capture non-null LCP and CLS. Candidate LCP is 146 ms median and CLS is zero in every run; direct visual debts remain separate targets. See exp-014.
resolution: null
duplicate_of: null
---
Chromium does not compute largest-contentful-paint for a page that has never been visible, and the exploration pane reports visibilityState=hidden permanently, so lcp_ms is null on every run. CLS is recorded but meaningless while the pane collapses to 0x0 on navigation. The probe now records both plus page_visible and page_laid_out so the absence reads as an environment limit rather than a good result. Needs a run in a real window -- a headed browser, or a person -- to get the numbers a browser would actually report. Until then this loop cannot speak to LCP at all.

## Notes

Promoted to P0 by exp-009/exp-010. The property this project most wants to control -- no flicker, nothing moving -- is the one property this environment cannot see. lcp_ms and cls are null on every recorded run because the pane reports visibilityState hidden permanently, so H56's visual-states metric cannot be validated and H11/H52 cannot be scored on what they are actually for. The client-side ordering below it is guesswork until a headed run exists.

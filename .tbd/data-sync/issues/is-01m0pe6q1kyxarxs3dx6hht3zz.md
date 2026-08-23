---
type: is
id: is-01m0pe6q1kyxarxs3dx6hht3zz
title: "H51: measure LCP and CLS in a visible window"
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T04:31:32.914Z
updated_at: 2026-08-23T04:31:32.914Z
---
Chromium does not compute largest-contentful-paint for a page that has never been visible, and the exploration pane reports visibilityState=hidden permanently, so lcp_ms is null on every run. CLS is recorded but meaningless while the pane collapses to 0x0 on navigation. The probe now records both plus page_visible and page_laid_out so the absence reads as an environment limit rather than a good result. Needs a run in a real window -- a headed browser, or a person -- to get the numbers a browser would actually report. Until then this loop cannot speak to LCP at all.

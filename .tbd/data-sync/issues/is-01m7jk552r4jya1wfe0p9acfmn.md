---
type: is
id: is-01m7jk552r4jya1wfe0p9acfmn
title: Reinstall the macOS app from main once the stacks land (owner, 2026-11-16)
kind: task
status: open
priority: 1
version: 4
labels:
  - skipped-by-owner
dependencies: []
parent_id: is-01m7hcanw7czjv3kgedg9zjbew
hold: paused
created_at: 2026-11-16T16:30:59.664Z
updated_at: 2026-11-17T03:38:54.498Z
---
Owner: "Make sure you reinstall the app once you're done." After stack #446 (and #452/#453) merge: build the app from main and install it (attic/coord/install-review-build.sh pattern), restart the dev app on main, and run cache-clear for repositories a stack build cached at catalog projection 3.

## Notes

2026-11-17: the owner said in chat to skip the dev-app reinstall in this coordination session (cloud Linux container, no Mac). Left open for the owner.

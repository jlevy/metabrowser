---
type: is
id: is-01m7nyeb57h28trbdp2m1hy2wk
title: "macOS app: open https GitHub repo and pull request URLs"
kind: feature
status: open
priority: 1
version: 1
labels:
  - skill
  - alpha
dependencies: []
created_at: 2026-11-17T23:45:58.438Z
updated_at: 2026-11-17T23:45:58.438Z
---
Alpha slice of plan #534 per the skill review: AppDelegate accepts https GitHub URLs (today AppDelegate.swift:225 drops non-file URLs while open exits 0); resolve through metab --present --dry-run --json; key the session by repository, not path or pin; an already-open repository navigates (showFrontWindow(page:)); a refusal shows metab's reason; ServerLaunch passes the URL, not root.path; ServerSupervisor no longer abandons at 60 s while clone progress arrives; add the capability marker --present checks; source roots stay out of recents and the saved session for the alpha. ShellCoreTests for the key and deadline.

---
type: is
id: is-01m7nyeb57h28trbdp2m1hy2wk
title: "macOS app: open https GitHub repo and pull request URLs"
kind: feature
status: open
priority: 1
version: 7
labels:
  - skill
  - alpha
dependencies: []
child_order_hints:
  - is-01m7ps02xeyq573ycx69a5zw38
  - is-01m7ps03b12jamq4mztv5v25ec
  - is-01m7ps03rss4e5hh2634xpvmcf
  - is-01m7ps046phmwqanz6qn7cp44b
created_at: 2026-11-17T23:45:58.438Z
updated_at: 2026-11-18T07:30:04.117Z
---
Alpha slice of plan #534 per the skill review: AppDelegate accepts https GitHub URLs (today AppDelegate.swift:225 drops non-file URLs while open exits 0); resolve through metab --present --dry-run --json; key the session by repository, not path or pin; an already-open repository navigates (showFrontWindow(page:)); a refusal shows metab's reason; ServerLaunch passes the URL, not root.path; ServerSupervisor no longer abandons at 60 s while clone progress arrives; add the capability marker --present checks; source roots stay out of recents and the saved session for the alpha. ShellCoreTests for the key and deadline.

## Notes

2026-11-17 owner decisions for PR #539 (after reviews A and B): (1) a link into a repository that already has a window, naming a different branch/commit/PR head than the window shows: SWITCH the window to the link commit (the pin switch View on branch uses), then open the page; (2) consent: ASK only when the repository is not yet cached (one confirmation naming the repo, that it will clone and read with the gh sign-in); cached repositories open directly.
2026-11-18 recents plan (claude/recent-folders 0e0a5cd8c): metab records the target at serve start in both modes, so #539 rule "repository windows stay out of Open Recent" is dropped by construction (remove it from #539 docs/plan text); the saved-session exclusion stays. The recents PR touches AppDelegate only on the recentFolders property line and one refresh in applicationDidBecomeActive.

---
type: is
id: is-01m7wysqjj7ps8vx91xva66k54
title: In-app web panes and View on GitHub in the macOS app
kind: epic
status: open
priority: 3
version: 5
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
child_order_hints:
  - is-01m7s8m8y3w8ktzkpxjfet7eba
  - is-01m7rtj7p306d936wdd0hhbzt4
  - is-01m7s8m8d8tc46wkks59n1ngaq
  - is-01m7wy16p4jdamff7t1kgdq3re
created_at: 2026-11-20T17:06:52.625Z
updated_at: 2026-11-20T17:30:26.909Z
---
The macOS app's web view layer names no site: a web pane, a profile per site (the domains that stay in the pane and the hosts a marked link may open), one shared website data store, and a generic page marker, with GitHub as the first site (mb-730z; PR #602 is still open). View on GitHub opens github.com in a native popover that is signed in once (#586), and the page header carries one split button wherever a github.com counterpart exists (#595).

What remains: bookmarks saved and browsed in nav, shown in the pane (mb-qhh8), and the working-tree counterpart follow-ups from #595's review (mb-djlc).

---
type: is
id: is-01m88zm3nj4r1ct9nw4hpjnpkt
title: "Pulls nav rows: one inline wrapping line (title • stack n/m • #N • diff summary ›) with hanging indent; only summary and chevron toggle"
kind: task
status: in_progress
priority: 1
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/827
    at: 2026-11-25T09:13:23.852Z
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T09:12:10.123Z
updated_at: 2026-11-25T09:13:23.853Z
started_at: 2026-11-25T09:13:22.837Z
---
User request. In the Pulls nav column, each PR row reads as one inline run that wraps with a hanging indent (continuation lines indent past the icon, as the nav tree's titles do): title, then a bullet and the stack position (e.g. 5/12) when the PR is in a stack, then a bullet and the PR number (#123), then the diff summary (+12 -3, or the A/M/R file-count variant) with the expand chevron at its end. Same order as the PR page's stack button (stack position, title, PR number) adapted to title first. The diff summary and chevron are the toggle; clicking the title only selects the PR and does not toggle. Supersedes the row's current separate lines, and the chevron placement from mb-f0pz for Pulls rows.

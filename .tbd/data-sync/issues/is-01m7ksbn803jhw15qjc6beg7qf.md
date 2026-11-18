---
type: is
id: is-01m7ksbn803jhw15qjc6beg7qf
title: "Coordinate landing the open PRs, Fast CI Phases 1-2, plan currency and 0.13 prep per PR #497 handoff (2026-11-17)"
kind: epic
status: in_progress
priority: 1
version: 32
delegate: claude-code@vm
labels: []
dependencies: []
child_order_hints:
  - is-01m7ksbsx0kcg5rk05fy23nxc5
  - is-01m7ksbtamcsdcpqvenk75j282
  - is-01m7n6sq6kd04jh61a4nfkedb3
  - is-01m7n6sqzbdemvtxvszccht5en
  - is-01m7n6srhvhffn7j57ck8fwrmg
  - is-01m7n6ss8csneee6w3jpykdj2m
  - is-01m7n6st95vqhhc1jayfshp503
  - is-01m7nb50wb8thbyrmhdh8yxnqx
  - is-01m7nn141emz0myav6bkd5r0b4
  - is-01m7p85nbqk60nq344hw1w62s7
  - is-01m7p85p0mg9yybh66113y5101
  - is-01m7p85phm6snf3y2y889ngqem
  - is-01m7p85q22ndxrh6c6s5kdq22p
  - is-01m7p85qm1k4gy83g78hfbtmf9
  - is-01m7p85rbgvd5kha2bqqk8026r
  - is-01m7p8c8jxvvb9qgs08wea9nk3
  - is-01m7p8e0d30md4n29d9q7r5taw
  - is-01m7p8hjk6jd7ckmr0fnjmpqca
  - is-01m7p8sr3qvsj1e11zadq5vt0d
  - is-01m7p9mbrvcda53samf39e6xq0
  - is-01m7p9wxbnv6essbhr1rask8ve
  - is-01m7pab7r3k7xe521vyg5xmrgb
  - is-01m7pac84jxgvafgawtsn1wgn0
  - is-01m7pevxh1fs23z06attcq9v2g
hold: null
hold_until: null
created_at: 2026-11-17T03:38:38.720Z
updated_at: 2026-11-18T04:33:00.448Z
started_at: 2026-11-17T03:38:54.763Z
---

## Notes

2026-11-18 ~03:30 UTC coordinator handoff (account spend limit hit; agents stopped; resets Nov 21 9pm PT).

MERGED today: #514 #513 #515 #521 #509+#510 #523 #511 #516 #499+#504 (Fast CI) #524. (#517 #522 #538 merged by other sessions.) Main green at d46d0359a; main run for a604716eb (#524) was running.

MERGE QUEUE (each after main's newest ci.yml run is green, per AGENTS.md; never auto-merge):
1. #529 (eb55a28f4; review A + dispositions published) - CI was finishing.
2. #525 then #526 (benchmark chain; #525 retargeted to main after #524) - #525 rerun of a Chrome-start flake pending.
3. #528 -> #530 -> #533 (drawn-from-disk chain; their session was still pushing; #533 had 19 failing checks - wait for its session's note).
4. #543 (#517 review A follow-up; review A Lows addressed at ac2210033) - CI was running.
5. #532 -> #536 (loading-box chain) - CI was running.
6. #506 (agent addressing review A with owner decisions: keys 1/2 stable, Refresh last in row of ages; note drops out whole; hold in note's place) - agent stopped; resume.
7. #544 help bar (needs owner's narrow-pane decision implemented: drop items from the end, one row, Shift always shown; then review).
8. mb-z6hb legend hover PR (agent stopped mid-way, branch claude/legend-hover-all-bars in overview-legend-hover worktree, not yet pushed/PR'd?) then mb-39h4 treemap legend stacked on it.
9. mb-40k4 recents (branch claude/recent-folders, plan text at 0e0a5cd8c; code in progress).
OTHER LANES: Local build review owns #527 #539 #540 #541 #542 and Open URL (mb-m4mg).
OWNER DECISIONS 2026-11-18: recents file in config dir (~/.config/metabrowser/recent-targets.json); no route for recents yet (CLI only). Help bar narrow: drop items from end. Legend hover: all visible bars, darker/wider, eased, gentle shimmer (own tokens, akin to progress), also on the legend entry and its color; treemap gets same legend+behavior. Mode indicator icons: mirror = GitHub mark (+cloud if clean), folder = folder icon (mb-wup3).
OWNER TODO: add the ci-ok ruleset (mb-m4ct); quit and reopen the app to load the rebuilt server.
UPDATE: #536 head is now d59be9d2845c8fba0fbcdbc4d4cda6e04d063461 (golden regenerated, dispositions marker moved); #532 unchanged at 5e740dc9e.
UPDATE: drawn-from-disk chain new heads: #528 b25a0566a1a404d433519df88b29d3534bb8840d, #530 5b6d509ec2cced11210f4ea982a246494535ad84, #533 a4fbad00fa9a1b7d03f827531058bae0b5e0c26f (merges only; reviews unchanged; dispositions updated). Local build review recorded the six recents binding points on mb-m4mg/mb-87j0 and will drop #539's Open Recent exclusion.
UPDATE: owner wants configs in YAML with a short format string (mf01...), bead mb-3x6y; recents (mb-40k4) must follow it: YAML file + format string.
UPDATE: #526 new head 48fd4af3ab3d19b5be990f2150c3f58f7acd4707 (base now main; dispositions reposted). #525 merged 5b1d2b055. #529 merged baaf52898. New PRs: #544 help bar (A addressed, ef464f34d), #545/#547 legend stack (review running), #546 recents (owner decisions in; review running), #549 print (review running; golden fix pending), #550 header (merging main), #551 writer race (review running).

---
type: is
id: is-01m7ksbn803jhw15qjc6beg7qf
title: "Coordinate landing the open PRs, Fast CI Phases 1-2, plan currency and 0.13 prep per PR #497 handoff (2026-11-17)"
kind: epic
status: closed
priority: 1
version: 48
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
  - is-01m7pf8zxej09pn6zygh242t14
  - is-01m7pfyp9qqhp6cg721a6cqp7r
  - is-01m7pg5xfxged1tw9c86yy0w12
  - is-01m7pk3bscmhvp7jcf22xwp2r3
  - is-01m7pk99cegx2xz0sc5wwddsdj
  - is-01m7pme15tmgzne6mwwnr1jykp
  - is-01m7pr9vw086ntmjbhs35vhxe3
  - is-01m7pr9wa6wb3anxmbsb5cq9rb
  - is-01m7pr9wr8d30pckgvp4teba1z
  - is-01m7pr9x6jds5pb33d72apcyqp
  - is-01m7qrt4bdwgj652xr6qw9va4m
  - is-01m7r4k134fe1bs8n8z7p8030a
hold: null
hold_until: null
created_at: 2026-11-17T03:38:38.720Z
updated_at: 2026-11-20T17:00:26.767Z
started_at: 2026-11-17T03:38:54.763Z
closed_at: 2026-11-20T17:00:26.758Z
close_reason: "Landing coordination complete: every PR its notes list is merged (#499, #504, #506, #509-#511, #513-#517, #521-#530, #532, #533, #536, #538-#547, #549-#552, #554); #555 was closed on the owner's decision. Its live follow-ups moved to feature epics"
resolution: null
duplicate_of: null
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
UPDATE 04:44: merged #525 (5b1d2b055), #529 (baaf52898), #528 (1c06d4635). #530 head b18a811b5 / #533 head 8ec461d22 (merged up; dispositions reposted) -> gh stack merge 533 when green. Queue after main green: #526 48fd4af3a, #543 ac2210033, #544 ef464f34d, #530+#533.
UPDATE 05:50: merged #526 (227853ce7); app restarted on it. #555 closed (owner: leave inks). Reviews published: #546 A, #547 B (approve), #550 A, #552 A, #554 A, #551 B (approve; B1 -> bead). Design: Fable review saved as attic/coord/design-review-open-modes.md; owner answered Q1-Q9 (all recommended; terminology: follow Git); design doc PR in progress (mb-lsx1, branch claude/arch-open-modes). Queue: #551 next (fixes CI race), then #543, #544, #530+#533, #545, #549 (CI rerun), #547, then #506/#546/#550/#552/#554 after fixes.
UPDATE 06:13: owner asked for autonomous overnight progress; questions accumulate in attic/coord/morning-questions.md.

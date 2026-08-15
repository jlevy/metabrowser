---
type: is
id: is-01kzyxv1db2hhw2ncc20kdr8mp
title: Implement end-to-end GitHub and Obsidian Markdown navigation
kind: epic
status: closed
priority: 1
version: 17
spec_path: docs/project/specs/done/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies: []
child_order_hints:
  - is-01kzz02ezkw9g4axaqmtfj595a
  - is-01kzz03fmd769zawq6gf5d1hd7
  - is-01kzz03fwfcvam3ft3zvfwqx7g
  - is-01kzz03g4npz4pma4px6mdq2s0
  - is-01kzz03gcp4q0qfw350d6krs7q
  - is-01kzz03gmzn17gpzrtbs6jfh1x
  - is-01kzz1vg2y797pnar5ga707mq7
created_at: 2026-08-14T01:23:01.160Z
updated_at: 2026-08-14T04:56:18.581Z
closed_at: 2026-08-14T04:53:27.187Z
close_reason: End-to-end GitHub and Obsidian Markdown navigation baseline is implemented, documented, and passes make verify.
---
Implement the approved baseline end to end in one branch and PR: replace hash-as-file routing with the sole canonical /view/<path>#<fragment> contract; replace the pre-stable link-navigation SDK with one typed navigation namespace; resolve standard GitHub repository Markdown links and safe resources exactly; and support standard Obsidian note, heading, named-block, label, and media wiki-links through the same resolver. There is no legacy URL or link-SDK compatibility requirement. Do not close the epic after the GitHub phase; all five implementation beads and make verify must pass. Keep site adapters, remote GitHub URL localization, backlinks, graphs, alias lookup, multi-root navigation, and full note transclusion in separate future bead mb-fbm2.

## Notes

Implementation is active on new branch codex/markdown-navigation, created directly from fetched origin/main f63ab1d and then populated with the three substantive approved planning commits. The plan-implementation-with-beads shortcut expanded the five required phase features into 13 dependency-wired P1 tasks: mb-b6bb -> mb-xt9v -> mb-ftti -> mb-pi55 -> mb-plxn -> mb-ma28 -> mb-e0gk -> mb-9y9n -> mb-7ve6 -> mb-quiz, then mb-lmub and mb-x2xp in parallel, then mb-k1r7. Seven deferred extensions are separately tracked under future epic mb-fbm2. Complete the required chain end to end before closing mb-yq1f.

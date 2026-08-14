---
type: is
id: is-01kzyxv1db2hhw2ncc20kdr8mp
title: Implement end-to-end GitHub and Obsidian Markdown navigation
kind: epic
status: in_progress
priority: 1
version: 14
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
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
updated_at: 2026-08-14T02:48:10.717Z
---
Implement the approved baseline end to end in one branch and PR: replace hash-as-file routing with the sole canonical /view/<path>#<fragment> contract; replace the pre-stable link-navigation SDK with one typed navigation namespace; resolve standard GitHub repository Markdown links and safe resources exactly; and support standard Obsidian note, heading, named-block, label, and media wiki-links through the same resolver. There is no legacy URL or link-SDK compatibility requirement. Do not close the epic after the GitHub phase; all five implementation beads and make verify must pass. Keep site adapters, remote GitHub URL localization, backlinks, graphs, alias lookup, multi-root navigation, and full note transclusion in separate future bead mb-fbm2.

## Notes

Implementation handoff prepared on branch codex/markdown-link-research at e36063e, draft PR #39. The research and approved clean-break plan are committed and pushed; make verify passed (981 passed, 1 skipped; 30 CLI goldens) and all five GitHub CI jobs passed. Implement the full child chain mb-ln8z -> mb-zm16 -> mb-4pv4 -> mb-8qnd -> mb-08is end to end; do not close this epic after only the GitHub phases. Future extensions stay in mb-fbm2.

---
type: is
id: is-01m7hhr3n6wpvfm1zpsxjh210t
title: "Release 0.13.0: changelog, candidate review, and owner approval"
kind: task
status: in_progress
priority: 1
version: 12
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/727
    at: 2026-11-23T03:30:57.284Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45107154662
    title: Passing 0.13.0 release-prep draft CI
    at: 2026-11-23T03:43:34.280Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
child_order_hints:
  - is-01m838y6g93s7w74dzqmas02ca
hold: null
hold_until: null
created_at: 2026-11-16T06:47:09.221Z
updated_at: 2026-11-23T06:28:46.432Z
started_at: 2026-11-23T03:14:00.397Z
---

## Notes

2026-11-17 coordinator: exp-088 renumbered to exp-099. Rename the 0.13.0 heading to '## 0.13.0' (0.12.0 was tagged as '(unreleased)', breaking its release-notes anchor). Draft at the coordinator's /home/user/wt/coord/release/.

2026-11-17 coordinator: plugin SDK ruling (Fable, /home/user/wt/coord/release/sdk-version-ruling.md): no bump, PLUGIN_SDK_VERSION stays 0.7. .menu-section-label was a private host class; climbing relative URLs out of /plugin-static/<name>/ were undocumented (absolute addresses and ensureKindAssets still work); fileTypes.schemaVersion 5 is the registry's own version (precedent 3->4 in 0.9.0). The release-prep PR rewords CHANGELOG entries at about lines 561-563, 864-869 and 1243-1245, opens the Plugin SDK group with 'remains 0.7', and may rename the stale test_deferred_plugin_asset_lifecycle_is_sdk_0_5.

2026-11-22: Assembled and validated the 0.13.0 changelog and drafted release notes at b6636949b, based on main 44c475dd5. The changelog preserves 318 entries and prior release history. All 67 focused changelog, docs, and macOS version tests passed. Draft PR #727 uses hosted CI for its full verification after the local push hook stalled in type checks under system load. The release candidate still needs the diff layout fragment after it lands, the measured comparison in mb-icss, candidate validation in mb-brvm, and resolution of mb-t7wx. Obtain approval for the exact final main commit and notes before tagging. The exp-099 name in the older note belongs to a previous investigation.

2026-11-22: Refreshed draft #727 at 29f9f8c36661ffde18d02990873771088522e662, based on merged #728 at ed952387f673f59d1c662f36125d6f1297c40518. Folded mb-rdwj into the 0.13.0 release. Verified that the 319 entries from the previous Unreleased section and 116 fragments all survived, and the previous release history is byte-identical. The 67 focused tests, public hygiene, changelog checks, and pre-commit checks passed on the refreshed head. Hosted CI run 45107154662 passed, including ci-ok job 137471966193. The draft is ready for review and remains pending final candidate quality, measured performance, the f02 cache decision, and approval of the exact release commit and notes.

Reviewed corrected release-prep head a7e85ff98e4ed474845b6219172bca105ced7877, after folding the 118 fragments and preserving v0.12.0+ byte-for-byte. Exact Review D https://github.com/jlevy/metabrowser/pull/727#pullrequestreview-6017123166 . PR CI 45120576350 and isolated full make verify 45120609494 are pending. Earlier 96c06c77 gates caught a public hygiene label in exp-102. Latest local whole-repository public hygiene and changelog checks pass. Exact 0.13.0 tag and notes approval will follow landed main CI.

Release-prep #727 merged at 51ca65a3ecf58bee890ad9c8ec724c8f15840267. Exact full make verify 45120609494 tested the identical a7e85ff tree and exact landed main CI 45123419039 passed. Approval still required for this SHA and release notes with SHA-256 f86937e202650e47c0ca039483b030f2ffad0ffd823c31dfebf49514ea8310bf. Live tag preflight returned 404 and public PyPI and GitHub latest remain 0.12.0. No tag created.

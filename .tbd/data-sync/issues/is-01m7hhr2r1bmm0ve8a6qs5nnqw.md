---
type: is
id: is-01m7hhr2r1bmm0ve8a6qs5nnqw
title: "Release 0.13: make verify, opt-in tiers, installed-wheel checkpoint and manual browser checks at the candidate"
kind: task
status: in_progress
priority: 1
version: 9
refs:
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45095985926
    at: 2026-11-23T03:16:19.489Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/727
    at: 2026-11-23T03:41:02.850Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45106819001
    at: 2026-11-23T03:41:02.852Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/730
    at: 2026-11-23T04:25:10.291Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45111635471
    at: 2026-11-23T04:27:15.971Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
child_order_hints:
  - is-01m839ga4kf87q8n4p3q29rqrv
hold: null
hold_until: null
created_at: 2026-11-16T06:47:08.288Z
updated_at: 2026-11-23T04:27:16.040Z
started_at: 2026-11-23T03:13:34.119Z
---

## Notes

Current stabilization baseline: main ed952387f673f59d1c662f36125d6f1297c40518 incorporates the reviewed rendered-diff fix. The rebuilt development app restored its window and served the exact stylesheet from its new runtime. The real checkout showed repository-wide Pulls and Commits again, and the installed runtime recognized the ordinary Codex SQLite database.

The previous main passed hosted CI. Its local make verify passed lint, types, parity and the app contract, then was stopped when the recorded source was superseded midway through the test tier. Treat the hosted runs as stabilization evidence. The complete local gate, opt-in tiers and release QA still belong to the final 0.13.0 commit, after the release prep and remaining cache decision. The arm64 release-variant DMG rehearsal passed on the earlier matching stabilization tree with an ad hoc signature. Production signing and clean-account checks remain open.

CLI-first release kickoff: #727 includes the reviewed SDK 0.8 correction (mb-smxw) and is updated to main after #730, the live GitHub smoke test correction (mb-mvwg). The authoritative Files pin and repository-wide Commits HEAD remain separate. The prior opt-in run passed 70 checks and found that stale assertion; the corrected live case passed independently. The local distribution check passed on e2b69be74, including exact candidate wheel, source archive, isolated console scripts, packaged contracts, setup doctor and navigation API. The newer release draft changes only the live test, so the runtime artifacts and measurements remain representative. Run the complete gate against the exact new draft and again verify final main after the prep lands.

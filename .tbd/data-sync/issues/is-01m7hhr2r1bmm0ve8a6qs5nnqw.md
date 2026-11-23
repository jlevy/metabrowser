---
type: is
id: is-01m7hhr2r1bmm0ve8a6qs5nnqw
title: "Release 0.13: make verify, opt-in tiers, installed-wheel checkpoint and manual browser checks at the candidate"
kind: task
status: in_progress
priority: 1
version: 14
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
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45111575033
    at: 2026-11-23T04:52:31.248Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
child_order_hints:
  - is-01m839ga4kf87q8n4p3q29rqrv
  - is-01m83anmkn4q6grheww9z22vva
hold: null
hold_until: null
created_at: 2026-11-16T06:47:08.288Z
updated_at: 2026-11-23T05:54:50.827Z
started_at: 2026-11-23T03:13:34.119Z
---

## Notes

Current stabilization baseline: main ed952387f673f59d1c662f36125d6f1297c40518 incorporates the reviewed rendered-diff fix. The rebuilt development app restored its window and served the exact stylesheet from its new runtime. The real checkout showed repository-wide Pulls and Commits again, and the installed runtime recognized the ordinary Codex SQLite database.

The previous main passed hosted CI. Its local make verify passed lint, types, parity and the app contract, then was stopped when the recorded source was superseded midway through the test tier. Treat the hosted runs as stabilization evidence. The complete local gate, opt-in tiers and release QA still belong to the final 0.13.0 commit, after the release prep and remaining cache decision. The arm64 release-variant DMG rehearsal passed on the earlier matching stabilization tree with an ad hoc signature. Production signing and clean-account checks remain open.

CLI-first release kickoff: #727 includes the reviewed SDK 0.8 correction (mb-smxw) and is updated to main after #730, the live GitHub smoke test correction (mb-mvwg). The authoritative Files pin and repository-wide Commits HEAD remain separate. The prior opt-in run passed 70 checks and found that stale assertion; the corrected live case passed independently. The local distribution check passed on e2b69be74, including exact candidate wheel, source archive, isolated console scripts, packaged contracts, setup doctor and navigation API. The newer release draft changes only the live test, so the runtime artifacts and measurements remain representative. Run the complete gate against the exact new draft and again verify final main after the prep lands.

The CLI baseline draft at 3d3533af3e4c73be92e3e4f1c12dacf54cc4fedf completed the full isolated Linux make verify, including lint and parity, 9,393 parallel tests, 66 serial plus 66 Chrome tests, all 133 golden files, dependency audits, distribution checks, and installed-wheel smoke. Runner log confirms the checkout SHA. Ordinary exact #727 CI also passed. This is the pre-font-fix baseline; verify the actual final release candidate separately.

Project-local Agent Skill rehearsal passed against the reviewed draft commit 3d3533af3e4c73be92e3e4f1c12dacf54cc4fedf. npm admitted skills@1.7.6 with the repository's 14-day cool-off, engine checking and disabled lifecycle scripts. The installer is the Vercel Labs MIT package published 2026-11-03T00:17:11.594Z. npm verified all eight package signatures and the installer attestation and found no known advisories. The verified SLSA source 77cfce8221e6e112a70152a230abc848b8b14c19 is the direct parent of signed v1.7.6 commit 7a5e920bead4b1039a6d6df5d7e1163b7b09423a, with only the package version changed. The scratch npm lock SHA-256 is c2741430853b2515ca061f9ccc4c664e5cfb2bab7e73441e60a41903a1f21ca5.

The public exact-commit installation to .agents/skills/metabrowser/SKILL.md in the fresh scratch project matched the source Git blob byte for byte. The installed SHA-256 was 20b76561c6f65b82e01efecac529d6b07288f5f824cb6fd56f1336824900c99e. The skill kept its local metab preference and uvx metabrowser@latest fallback. For the required post-release smoke, follow publishing.md step 10 with the full approved landed RELEASE_COMMIT and the reviewed skills@1.7.6 lock. Run the installed skills entry point as add "jlevy/metabrowser@$RELEASE_COMMIT" --skill metabrowser --agent codex --copy --yes in a fresh project with DISABLE_TELEMETRY=1, then cmp against git show "$RELEASE_COMMIT:skills/metabrowser/SKILL.md". Record the exact absolute install path and hash in the release evidence.

TCP #733 and sidebar #731 merged reviewed. Combined focused release tests: 348 passed on 96c06c77. In a7e85ff only the changelog and benchmark explanation changed, with local public-hygiene and changelog gates green. Exact hosted full release gate https://github.com/jlevy/metabrowser/actions/runs/45120609494 is running. Baseline and Agent Skill evidence retained outside scratch.

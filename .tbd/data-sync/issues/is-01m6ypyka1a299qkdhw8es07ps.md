---
type: is
id: is-01m6ypyka1a299qkdhw8es07ps
title: Simplify contract namespaces and safely upgrade the owner configuration
kind: task
status: closed
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m5wdbsy6z6d95sgg03kwmm76
hold: null
hold_until: null
created_at: 2026-11-08T23:12:30.527Z
updated_at: 2026-11-09T01:34:47.269Z
started_at: 2026-11-08T23:12:31.097Z
closed_at: 2026-11-09T01:34:47.261Z
close_reason: "Reviewed and verified in PRs #343 and #344. Owner-approved stack #345 merged into main at 87b8ec812774bb12a4d9f5f29901719b8b66d323 with the same tree as the qualified installed wheel. All 18 PR CI jobs passed. Merged-main CI and release gates remain on the release tracker."
resolution: null
duplicate_of: null
---
Owner requested concise hosting-independent names: metabrowser.config:ApplicationConfig/v1 and metabrowser.cache:* instead of com.github.jlevy.metabrowser.*. This is alpha with no external users; only the existing owner account needs a smooth upgrade. Trace and document the origin/Softschema naming rule, update canonical constants, generated schemas, tests/goldens and relevant current examples, and implement the smallest safe one-time upgrade through the existing storage mechanisms. No permanent old-name aliases or speculative backward compatibility. Preserve unknown user settings/comments, private modes, cache identities and Git objects; atomic/idempotent writes and a narrow old-namespace migration boundary. On malformed/unreadable config, fail without traceback or overwriting it and print its location plus a clear instruction to move aside or remove config and restart to recreate it; repository cache remains intact. Track/review migration design before substantial edits. Use a new forward stack layer on reviewed/gated b2fb62099 (PR342); normal full gate/CI/independent review before account promotion. Actual account upgrade is explicitly authorized, but only after qualifying the new artifact and coordinating all four installed servers. Keep private config contents out of public output.

## Notes

November 8 release contract checkpoint: this blocker is implementation-in-progress, not delivered. The current qualified/installed b2fb predecessor passed its full gate and is published as stack #339 through #342; its final CI/actual merges remain separate. The user wants canonical metabrowser.config and metabrowser.cache identifiers with no shipped old aliases, f02 or permanent compatibility, retaining f01/v1 payloads. Malformed config needs exact path and move/remove/restart-to-recreate guidance, without traceback or cache loss. Read-only inventory found one config root, one cache root, 17 headers and valid config; no account writes. Explicitly authorized one-account alpha upgrade still needs independent review/gate; safer reversible delta-header journal is planned after automatic review rejected raw YAML duplication. No actual migration or raw backup is claimed. Parent mb-4bd2 depends on this blocker. Separate macOS spike #341 is outside this release and must not be added as a blocker. Preserve current delegate/status/dependencies; no closure before qualified delivery and actual merge.

November 8/9 gate checkpoint: independent production approval at 445cd18b (23 files, A1 typed read/create I/O resolved) and private account-tool approval at SHA256 81caab84… (B1 exact header span and four fixtures). The normal first full gate failed after 4,931 Python passes and nine expected skips: 283 golden cases passed and 105 stopped in the before hook across six files. The runner had inherited a prior disposable scratch configuration with the old namespace; exact fixture setup reproduced the refusal with a synthetic old-header config. No branch push, artifact or live account change occurred. The narrow fixture-only correction gives the six before hooks the same sandbox config as their commands, leaves runtime and all output assertions intact, and is undergoing full golden preflight under the unchanged synthetic old config. Original gate logs remain preserved. R2 full gate, exact CI and 17-header account rollout are still required.

November 9 source-equivalent browser checkpoint. Space commit a53907948f348345ea0c6cbafbfe138c6513ba70, tree cdb95f003ddddceb9d231e194b88658962551a1f, parent a1f8393b04a378e5ba25d8dabefd4f4020fa03a3. The functional session ran in a patched scratch source checkout and locked environment with equivalent tree content. Evidence: release-followups-r3-20261108/source-browser-session.json.

The preceding config R2 reached 4,931 Python passes and nine expected skips before the shared editable/tooling interruption. The terminal returned 130. The trap's exit-0 marker was false qualification. No push followed. R3 is running the normal full make verify and atomic two-ref push from the combined Space commit in a dedicated environment.

Disposable malformed YAML refused with one path-and-remedy line. Config and cache digests matched across refusal. Moving the malformed config aside and opening the bare public repository URL recreated canonical private config and reused the pinned revision without invoking Git. A separate cached blob reopen stayed at the same revision and did not clone again. The disposable local pin also reopened at the exact cached tip after its origin was moved, with content and a typed refresh warning. Qualified-wheel recovery/reuse and the live 17-header account upgrade remain separate requirements.

November 9 pre-merge checkpoint.

The normal R3 full gate and atomic two-ref push passed in 1,444.45 seconds, with 4,931 Python passes, nine expected skips, 388 goldens, clean audits and packaged-wheel checks. Both CLI aliases now run 0.11.1.dev1308+a53907948, tree cdb95f003ddddceb9d231e194b88658962551a1f, wheel SHA-256 2aa96c7924e4bd4c52836a0b91086f12d2b076b1cb5d8b5045ab30821dc6684e.

The authorized private one-account upgrade changed exactly 17 headers in place and preserved settings, record bodies, modes, cache identity and nine Git-directory fingerprints. Five healthy previews were verified. The full release and merged-main checks remain separate.

Stack #345 is ready for the exact forward atomic merge into main a2677882. PR #343 at a1f8393b04a378e5ba25d8dabefd4f4020fa03a3 has nine green CI jobs in 42543688913. PR #344 at a53907948f348345ea0c6cbafbfe138c6513ba70 has nine green jobs in 42543714994. Independent reviews are verified and no threads remain unresolved. Automatic review rejected the merge command because the retained owner handoff requires approval for this exact stack. Both PRs remain open and owner merge approval is pending.

Evidence: release-followups-r3-20261108/stack345-merge-readiness.json, installed-iab-receipt.json and qualified-55-receipt.json. Quiet preflight evidence: host-a539-20261109T011536Z-decision.json.

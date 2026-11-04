---
type: is
id: is-01m6k1e50h9aysq7g03btn8n67
title: Preserve the latest file-list outcome alongside the strongest provider hold
kind: bug
status: in_progress
priority: 2
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6jhbnan8czw6c97gr5511mr
hold: null
hold_until: null
created_at: 2026-11-04T10:24:52.751Z
updated_at: 2026-11-04T10:32:11.982Z
started_at: 2026-11-04T10:32:11.978Z
---
New postpush PR288 review comment discussion_r4466332226 questions read_files_refresh choosing the entire strongest-deadline stamp and potentially hiding a newer memory cache_unwritable outcome. Ordinary older durable hold is already copied into the memory refusal; verify the concurrent later-publication case through real worker/route behavior before accepting or rebutting. Preserve strongest live provider reset and automatic retry behavior. Independent read-only adjudication assigned; source0487921d remains frozen. Public finding: https://github.com/jlevy/metabrowser/pull/288#discussion_r4466332226. Keep landing gated on a concrete disposition.

## Notes

2026-11-04 independently verified Medium on exact048 via real two-process worker/route interleaving. ProcessA admits source, creates rate_limited at12:00:00/reset12:10 and pauses before normal durable publication. ProcessB at12:00:01 genuinely refuses future-layout source admission and exposes memory cache_unwritable; home/config fingerprints unchanged and no provider work. ReleasingA publishes older-at/stronger-reset disk stamp; read_files_refresh then returns the older outcome/message and hides the newer refusal. Automatic retry is still held: observability bug, not lost provider deadline. Ordinary preexisting disk hold is already copied into the refusal and does not reproduce. Evidence qodo-288-outcome-adjudication-048/probe-red.json. Minimal outside-source patch under independent preparation: latest-at outcome with strongest active reset, preserving deterministic equal-at tie and existing admission policy. Landing remains gated; root source048 frozen until reviewed patch.

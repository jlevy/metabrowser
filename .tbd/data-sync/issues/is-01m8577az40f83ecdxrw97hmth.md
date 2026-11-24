---
type: is
id: is-01m8577az40f83ecdxrw97hmth
title: "Review PR #766 (Rendered shows every diff the Document view renders) with review-github-pr and address its findings"
kind: task
status: closed
priority: 2
version: 25
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/766
    at: 2026-11-23T22:10:12.046Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
child_order_hints:
  - is-01m85aw4wayd65kbz7pz0ctjzf
  - is-01m85aw6yft0sc8r6atthantry
  - is-01m85aw8nmg7q749g5r3q4x6hs
  - is-01m85awaaqk2dyye7vppq9w4jf
  - is-01m85awcmmb6n9dc2wacagzqzn
  - is-01m85awec2kajkjnsqpe9cbcfr
  - is-01m85awg5b4qbfmk39116p8t5q
  - is-01m85awj8kmmnm4bzc63tv2p0d
  - is-01m85awm5kgzt3tx7m9xyk7fwj
  - is-01m85awnmj0w1bs9ydvpxt83fe
  - is-01m85awrp3d7ar9mc5asr5qydr
  - is-01m85awv09s01et4hb66eqq4zk
  - is-01m85awxr29b0ayvy8zn2x1e8j
  - is-01m85ax0b8x8m875azx03pwmqy
  - is-01m85ax3fxjgdrtgegy1hg2dhd
  - is-01m85ax5p3w9nj40rtabj9nrmj
  - is-01m87ccajvpvb9d2q4e8d11rk4
  - is-01m87ccbvmmezxbdkyh1wztq9x
hold: null
hold_until: null
created_at: 2026-11-23T22:08:02.530Z
updated_at: 2026-11-24T18:16:39.022Z
started_at: 2026-11-23T22:10:11.293Z
closed_at: 2026-11-24T01:10:25.349Z
close_reason: "Review A of PR #766 addressed: every finding has a disposition in https://github.com/jlevy/metabrowser/pull/766#issuecomment-7118822652 at head 4bc0c18b2, CI green (run 45299956083). Deferred and still open: mb-p39s (A3), mb-5b1w (A12), mb-zrng (child memory follow-up)."
resolution: null
duplicate_of: null
---

## Notes

Review A (senior, round 1) published 2026-11-23 by the review sub-agent, pinned to head 7ad9df05ad21e36f2aab61e8f7a54194979dfe16, base claude/docs-tab-file-header at ddac23df3:
https://github.com/jlevy/metabrowser/pull/766#pullrequestreview-6030955099

Verdict: changes requested (COMMENT event). 13 findings, 3 suggestions.
- High: A1 raw HTML reaches the sanitizer on the thread path with no bound (23,988 B: 9.1 s, 485 MB; base refused in 2 ms). A2 a document's own <ins>/<del> are drawn as the projection's change marks. A3 base is #759's branch and the PR is in no formal stack (stacks API answers []).
- Medium: A4 an added or deleted JSON file's hidden duplicate value is not source_only. A5 text between two inline raw tags (<svg>, <title>, <script>, <style>) is not in the hidden signature. A6 `>b<table>^[]` still answers unsupported (descent into a slice extended by an attached note).
- Low: A7 hidden JSON value moved between objects; A8 two recorded measurements below the worst the bounds admit; A9 _raw_markup cache keeps blocks of any size; A10 footnote number differs inside $...$; A11 marker digits in a raw heading's anchor; A12 KPress drops text after a bare <td>/<th>; A13 arch doc claim nothing maintains.
- Suggestions: A14 open <details> in changed blocks; A15 ruler.__rules__; A16 two unwrapped docstring lines.

Focused tests at the head: 283 passed. CI green at the head. Not closed: the main session closes this after the findings are addressed. tbd sync not run by the sub-agent.

Addressed by the fix sub-agent, pushed at 4bc0c18b262735cb8034cfaf92e6599301d27eea (base claude/docs-tab-file-header 22dfd4543 merged; no conflicts):
- fixed: A2 8cce7c365, A4 0d87c5fc2, A5 d2637263e, A6 8bf2662a6, A7 0d87c5fc2, A8 883a0f055, A9 d2637263e, A10 b78cebec2, A11 624bdfabd, A13 2eb9b0dc5 (clause removed; 1,404 projections of the 468 tracked .md files all ready, 426 s at load ~450), A14 354aee864 + 4bc0c18b2, A15 1a3325b9c, A16 1a3325b9c. Those child beads are closed.
- A1 (mb-mvzo): thread path fixed in 1398903ac (a thread refuses raw HTML with a no-reason budget refusal; the child projects it). Left open: the coordinator's further ask, capping the child's memory, is escalated (mb-zrng P1; KPress kpr-mgc0).
- deferred: A3 mb-p39s (the coordinator links the native stack); A12 mb-5b1w (KPress kpr-gtv7; CommonMark and GitHub keep the text, KPress drops it).
- Disposition reply drafted (attic/review-a-reply.txt in the fix worktree), not posted: it waits on the A1 escalation.

Escalation decided by the coordinator: the A1 child memory cap is option 1, an RSS watchdog with a cost refusal, in a stacked follow-up under mb-zrng (P1); kpr-mgc0 is the long-term fix. mb-mvzo closed as fixed. The CI attempt-1 setup-uv timeout is mb-0sl8. Disposition reply posted at head 4bc0c18b2 (CI run 45299956083 green, attempt 2): https://github.com/jlevy/metabrowser/pull/766#issuecomment-7118822652

---
type: is
id: is-01m85cnf2t83p297repn82nafk
title: "Markdown child: bound its memory, which only the deadline bounds today (KPress sanitizer formatting rebuild)"
kind: bug
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/929
    at: 2026-11-28T18:10:10.150Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: null
hold_until: null
created_at: 2026-11-23T23:43:08.354Z
updated_at: 2026-11-28T18:10:10.151Z
started_at: 2026-11-28T17:49:40.859Z
---
Found addressing review A1 on PR #766 (https://github.com/jlevy/metabrowser/pull/766#pullrequestreview-6030955099). KPress's sanitize_raw_html calls nh3.clean (ammonia/html5ever), whose HTML5 tree builder rebuilds every formatting element left open at each later block (reconstruct the active formatting elements). One line of raw HTML, n distinct <b a=i> then m <div>x</div>, renders n*m elements. The Markdown child, which renders every untrusted document for the Document view and, after PR #766, every Rendered diff that holds raw HTML, is bounded by its deadline in time only. Measured 2026-11-23, Apple M1 Pro, Python 3.14.7, KPress 0.3.9, load average 320-340, warm, stopped 10 s after the call: 47,988 B (n=2,511, m=1,998) reached 1,295 MB still inside nh3; 258,902 B (n=2,000, m=20,000) reached 1,016 MB; 262,128 B and 1,048,561 B at an even split reached only 80-100 MB, since the n-squared prefix (Noah's Ark checks over n open elements) ate the deadline. nh3 alone on 47,988 B took 40 s and 1,281 MB. At a lower load the deadline admits several times the work, so several GB. Scripts: attic/a1_child.py, attic/a1_measure.py, attic/a1_drive.py on branch claude/rendered-diff-no-content-refusals (gitignored attic; copy before the worktree goes). No count over the input is a sound bound: Markdown-made elements can be stranded by raw HTML (a raw <table> inside **bold** leaves the strong in the list; </strong> inside the table is not in scope and removes nothing), so a sound estimate needs the tree builder's markers, scopes, Noah's Ark and adoption agency. Options: (1) a watchdog thread in the child (nh3 releases the GIL; checked) that exits when ru_maxrss passes a measured cap, with the parent answering a truthful cost refusal for renders (renderer_exited) and for projections (a new reason; today a child that dies twice answers unsupported); (2) KPress bounds the rebuild itself (kpress bead filed alongside). The thread path is bounded in PR #766: a thread refuses raw HTML with a budget refusal and the child projects it.

## Notes

KPress side filed as kpr-mgc0 (KPress tbd, under kpr-t59f), with the reproduction and the measurements. Options 1 (a watchdog with a truthful cost refusal) and 2 (KPress bounds the rebuild) are escalated to the coordinator from PR #766's review A.

Decided 2026-11-23 by the coordinator: option 1. An RSS watchdog in the Markdown child answers with a cost refusal, landing as a stacked follow-up PR on #766 under this bead (P1). kpr-mgc0 is the long-term fix. Not started yet.

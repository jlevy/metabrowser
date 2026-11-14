---
type: is
id: is-01m3w465p1fgn0da5w3cgxknpj
title: "Invisible-character and PR-header follow-ups from the #244 review"
kind: task
status: open
priority: 3
version: 4
spec_path: docs/project/specs/done/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-10-01T16:19:01.413Z
updated_at: 2026-11-14T18:50:01.311Z
---
From the independent review of PR #244, not fixed before landing. Variation selectors: any printable non-ASCII base keeps any of the 256 selectors, so a name with a non-ASCII character can have an invisible twin (low exploitability; no all-ASCII name gains one); a cheap narrowing is U+E0100-E01EF only after a CJK ideograph and U+FE0E/FE0F only after a symbol or punctuation base plus the keycap rule. Deleted-fork PR header: the record keeps only ref and repo.full_name, so the page prints 'branch (deleted fork)' and drops the owner GitHub still reports in head.label and head.user.login; github.com's own wording for a deleted fork is unverified. Tests: the default-ignorable table test pins only order and count (moving rows passes); no test has a selector after a C1, private-use or unassigned base; '*' as a keycap base is untested; invisible_chars.py has no dedicated test file and its table test sits in the GitHub plugin's tests; invisible_chars.py:92 (base.isspace()) is dead. The reducer runs hidden_at on the raw path+query+fragment rather than on each decoded component (harmless today). Other raw sites reaching a terminal through --api JSON (ensure_ascii=False): diff entry paths, commit files[].path, /api/source/status and refs, pull record refs and review-comment paths; decide whether --api output should escape. Legitimate emoji ZWJ sequences, tag flags, Persian ZWNJ and Mongolian FVS are refused raw and shown with U+FFFD while a plain emoji with VS16 is kept: inconsistent, acceptable for the alpha.

## Notes

2026-11-14 audit: invisible_chars.py:92 is now :166. The --api escaping question overlaps mb-1cpe; decide it there. Reparented with mb-hall's close; apply only if mb-hall closes.

---
type: is
id: is-01m7tb5hr58w6wt67a59yaqgjr
title: Review, land, and test end to end the Mermaid diagram PRs (jlevy/kpress#80, jlevy/metabrowser#597) on jlevy/markform
kind: task
status: in_progress
priority: 1
version: 7
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T16:45:19.492Z
updated_at: 2026-11-20T17:03:44.614Z
started_at: 2026-11-19T16:47:12.227Z
---
Owner, 2026-11-19, verbatim: "can you review and make sure all the mermaid diagram PRs are reviewed and merged as well and let me test end to end" and "let's use the jlevy/markform repo as an example for testing as it has a mermaid document on the readme". #597 depends on kpress#80 (builds KPress from claude/diagrams-mermaid-mode via [tool.uv.sources]; publish.yml refuses a release while a source is set). Plan tracked under mb-qz51.

## Notes

2026-11-19 E2E on jlevy/markform README with #597 a431e686a (kpress 5037f8a), GitHub URL source: the flowchart's overlapping labels are NOT a #597/kpress bug. github.com renders the same diagram with the same overlaps (attic/mermaid-e2e/markform-readme-github.com.jpg); Metabrowser trusted (no CSP) and untrusted image placements lay out identically (viewBox 518.6x411). Cause: Mermaid 12.3.0 (GitHub's release) on empty subgraphs whose titles are long multi-line <br/> labels. The console style-src-elem violation is Mermaid's measuring <style>, harmless here. Fix belongs in markform's README source (make L1-L4 and IMPL nodes, not empty subgraphs) - owner's call. Owner told the Mermaid session they will merge kpress#80 themselves: no merge or KPress release without their word. Repin steps are bead mb-d515.

2026-11-19 owner, verbatim: "I'm not merging kpress PR until I see everything work. That does not block you making progress. You don't need to repin or do any of that. I want to see everything working with the branch of KPress. Once everything is working, I will merge, and we'll update later." So the order is: Mermaid session folds review A fixes into kpress#80 and #597 (still pinned to the kpress#80 branch); I merge #597's branch into the app's integration build and restart the app; owner tests on jlevy/markform; owner merges kpress#80; then release, repin (mb-d515, deferred), land #597.

2026-11-19 the Mermaid session reports the owner told it directly: "I want to see all of this working and merged on this repo with the pin on the kpress branch" and "There is no problem with keeping the pin on the branch." So #597 merges to main pinned (rev = kpress#80 head commit) once review A is folded and CI is green; that session merges it and sends me the head SHA first for the app build. kpress#80 head 5a8e9ae; owner merges kpress#80 after testing.

2026-11-20 audit: moved from in_progress back to open. #597 merged on 2026-11-19 (pinned to the kpress#80 branch) and #616 (Mermaid in PR text) on 2026-11-20. jlevy/kpress#80 is still open, by the owner's decision (merged after testing end to end on jlevy/markform). Remaining, all the owner's: test, merge kpress#80, release KPress, then repin (mb-d515, deferred).

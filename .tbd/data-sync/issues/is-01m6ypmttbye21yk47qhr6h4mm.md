---
type: is
id: is-01m6ypmttbye21yk47qhr6h4mm
title: "Review PR #341 native shell spike for safe, isolated landing"
kind: task
status: open
priority: 2
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6yk0ja99gwp0vcsh73xaqsn
hold: null
hold_until: null
created_at: 2026-11-08T23:07:10.538Z
updated_at: 2026-11-08T23:09:28.626Z
started_at: 2026-11-08T23:07:27.950Z
---
Independently review the separately authored native macOS shell spike PR #341, pinned initially to 274d01b4574d6efe22e4a285ab7a2505d494be71 over main196ee3c5. User requested all open PRs reviewed for safe landing. Inspect every changed Swift/build/distribution path, process lifecycle, navigation/security, test evidence and packaging isolation. The author reports a no-verify push, incomplete manual coverage and known spike limitations. Read-only review first; do not mutate its active author branch or silently include it in product stack339. Root product stack337/336/340/342 remains a separate merge set. Publish findings on PR, track dispositions and require proper exact-head validation before any later merge. No native architecture or release acceptance is inferred.

## Notes

November 8, owner scope clarification: the macOS app spike is separate from landing and releasing the existing Metabrowser feature set. Root stopped the read-only PR341 review cleanly, with no publication or source mutation. Keep this task open for that separate workflow; it is not a dependency of product stack339 or the current release. Existing implementation task mb-rvcj stays with its author.

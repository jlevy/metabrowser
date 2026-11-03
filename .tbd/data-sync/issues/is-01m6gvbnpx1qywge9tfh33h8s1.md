---
type: is
id: is-01m6gvbnpx1qywge9tfh33h8s1
title: Restore bounded ordered dotenv expansion for existing logging settings
kind: bug
status: closed
priority: 2
version: 4
delegate: checkout_design
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
hold: null
hold_until: null
created_at: 2026-11-03T14:00:11.228Z
updated_at: 2026-11-03T15:35:22.510Z
started_at: 2026-11-03T14:00:18.889Z
closed_at: 2026-11-03T15:35:22.509Z
close_reason: "Owner superseded this compatibility requirement: bundled local frontend/backend needs one current explicit-number contract, with no old-client compatibility. The prototype was forward-reverted; current contract and core browsing stability are tracked under mb-ow6w."
resolution: canceled
duplicate_of: null
---
Current main expands dotenv references for the two allowlisted logging settings. PR 280 commit54a9000c disabled expansion to avoid quadratic resolution; strict additive acceptance requires restoring ordered reference/default semantics while keeping regular-file, input-size, warning, and bounded expansion safeguards. Own layer280 from64fa6b1f; no pushes or sync by worker.

## Notes

Candidate2945bbfe536f368d621b0629a8d9a469a6d82425 is a clean direct child of owning280head64fa6b1f, branch codex/pr-dotenv-expansion-01a1a051. Five files only: ordered dotenv loader, two test modules, SECURITY and CHANGELOG. Preserves current-main reference/default/None/duplicate/self-reference/quote/shell/file semantics and allowlist. Reuses UTF-8 DotEnv.parse, one shell snapshot plus prior-binding layered lookup, and a forward scanner equivalent to variable grammar. Inclusive limits:1,048,576 characters per value and4,194,304 aggregate per file including overwritten helpers. Refuses whole file before applying any setting, warns once without values, continues .env.local. Existing64KiB regular-file/input and warning protections retained. Initial compatibility cases14failed/1passed on broken source; final43tests passed5.95s including57,987 grammar comparisons and actual logging consumers. Affected security CLIgolden8checks passed; full make lint-check and normal hooks passed. Independent pre-pin encoding default observation fixed with explicit UTF-8 and real ASCII-locale regression. Nine paired7k-binding parse medians602.870ms stock versus64.802ms bounded; max malformed bounded60,031byte file1.807ms median9; 1Mi doubling refusal0.265ms, near4Mi aggregate0.330ms. Author evidence is not independent approval; exact pin given to independent ReviewF, root read delta without new finding. No dependency/lock/Make/browser edits, push/sync/PR merge/history rewrite. Coordinator owns final independent disposition, forward propagation, integrated gates and closure.

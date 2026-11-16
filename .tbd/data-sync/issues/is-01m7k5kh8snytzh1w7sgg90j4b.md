---
type: is
id: is-01m7k5kh8snytzh1w7sgg90j4b
title: "PR #485 A13: Several claims cite sources that do not contain them"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:25.271Z
updated_at: 2026-11-16T22:10:01.774Z
started_at: 2026-11-16T21:53:40.709Z
closed_at: 2026-11-16T22:10:01.772Z
close_reason: "Fixed in 83ef69fc3: Xcode 13 dropped from the TN3147 citation; codesign --verify first and --check-notarization on app and image marked as the plan's own; quarantine-not-API re-cited to thread 851710; the syspolicy_check claim replaced with thread 130560's less-accurate wording; the agreements sentence marked as an assumption for API keys."
resolution: null
duplicate_of: null
---
Low. PLAN:250, :255, :260-261, :196-198, :393-394, :441, :542-543. Fix: re-cite each claim (thread 851710 for quarantine not being API; thread 130560 for the command-line checks' accuracy), or mark it as the plan's own observation (codesign --verify first, agreements for API keys, Xcode 13 in TN3147, --check-notarization on the app and image). Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258

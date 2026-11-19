---
type: is
id: is-01m7rmjmzgk91n9czy6g19qk75
title: "One declared contract between the macOS app and metab: a declaration, a golden of the whole surface, and a check on both sides"
kind: feature
status: in_progress
priority: 1
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7rj9pgz3qf89emdaz0rbenn
hold: null
hold_until: null
created_at: 2026-11-19T00:51:17.102Z
updated_at: 2026-11-19T02:18:14.628Z
started_at: 2026-11-19T00:51:25.272Z
---
Owner, 2026-11-18, verbatim: "We should also encode some sort of default convention, we are in if we change metab in a way that's incompatible with the front end, then we should create a new minor or major release but not a patch release (unless it's a bugfix), this contract would be at the minor release level or above" and "we should have a way to understand what that convention is and make sure it's reflected in our tests in a sensible way, where we're following our golden testing rules, but we know that those are compatible with the way that the native browser uses it. Maybe what we need is some golden test that represents all of the native browser surface area."

Split from mb-bxli, which keeps the written versioning convention, the minor-release test on minimumRelease, the gh and git requirements, --doctor coverage, and Check Setup.

Deliverables:
- apps/macos/metab-contract.toml: the one declaration of every command, route, JSON key, output line, variable, behavior and copied value the app depends on.
- tests/golden/app-contract.txt, written by tests/test_app_contract_golden.py: each declared command and route run through metab with the app's argument list, recording only what the app reads.
- apps/macos/Tests/ShellCoreTests/AppContractTests.swift: the app's own builders and readers held to that golden.
- devtools/check_app_contract.py in make lint-check: declaration against the Swift sources and the golden, both directions; a changed contract needs a marked changelog fragment; no patch release section holds a contract change.
- docs/project/architecture/arch-app-contract.md.

## Notes

PR #593 (claude/app-contract-golden, based on main after #590, #582, #581 and the folder stack merged). Not merged: the coordinator lands it after review.

Review A round (2026-11-18), fixed in 0698bf11c: A1 FolderPage.swift in [files.http]; A2 a command's JSON answer recorded in metab's own framing, with stderr; A3 shown and opaque keys recorded as <text> and <opaque>, lines as the part parsed; A4 behaviors, copies and app-side entries in the declared surface, and tests/golden/app-contract-copies.txt; A5 pinned_by a session or golden with holds; A6 stable_console in the harness; A7 problems print the TOML line; A8 blind spots stated, interpreter variables and the two names declared, subscript and coding-key search; A9 the pins test reads the declaration. Dispositions comment posted on the PR.

Landing order, from the coordinator: #595, then #586, then #593. After #586 lands: merge main and add [files.http] and [files.script] for GitHubPopover.swift, [files.script] for GitHubViewRequests.swift naming a [[behavior]] for the a[data-view-on-github="open"] marker, pinned by #595's session with the marker in holds.

Owner decisions open, in the PR body: what "App contract fix:" may change; a release step that runs `check_app_contract accepts` against the minimum release once it is on PyPI; whether metab should state a contract number the app checks.

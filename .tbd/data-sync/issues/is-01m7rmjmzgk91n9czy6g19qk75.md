---
type: is
id: is-01m7rmjmzgk91n9czy6g19qk75
title: "One declared contract between the macOS app and metab: a declaration, a golden of the whole surface, and a check on both sides"
kind: feature
status: closed
priority: 1
version: 10
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/593
    at: 2026-11-20T17:02:40.711Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
parent_id: is-01m7rj9pgz3qf89emdaz0rbenn
hold: null
hold_until: null
created_at: 2026-11-19T00:51:17.102Z
updated_at: 2026-11-20T18:01:20.203Z
started_at: 2026-11-19T00:51:25.272Z
closed_at: 2026-11-19T03:39:30.449Z
close_reason: "Landed in #593"
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 96011acb-5380-4c3d-b8d1-1203cf62e37e
    linked_at: 2026-11-20T18:01:20.136Z
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

PR #593 (claude/app-contract-golden), head 9a1729a46, based on main at 91d7fa9d2. Not merged: the coordinator lands it.

Review A round, fixed in 0698bf11c: A1 FolderPage.swift in [files.http]; A2 a command's JSON answer recorded in metab's own framing; A3 shown and opaque keys recorded as <text> and <opaque>, lines as the part parsed; A4 behaviors, copies and app-side entries in the declared surface, and tests/golden/app-contract-copies.txt; A5 pinned_by a session or golden with holds; A6 stable_console in the harness; A7 problems print the TOML line; A8 blind spots stated, interpreter variables and the two names declared, subscript and coding-key search; A9 the pins test reads the declaration.

After #595 and #586 landed, 35cca1d6c: GitHubPopover.swift and GitHubViewRequests.swift listed; the behavior view-on-github-link pinned by the counterpart golden through holds; GitHubViewRequests.marker as a copy, pinned by a new test in tests/test_macos_app_pins.py.

Review B round, fixed in 9a1729a46: B1 the golden builds its own cache and origin, and records a value the app does not tell apart as <other>; B2 the release rule compares the declared surface by value, not by order, label, or module; B3 a route's block is status and keys, the console script is recorded as defined, and only JSON-framing lines of stderr are kept; B4 `// not-contract: <why>` on a line exempts its key from the scan and is listed by report; B5 the documents say the source check runs in the lint job. Dispositions comments for A and B are on the PR.

Next: #596 (doctor and Check Setup) lands after #593 and declares its own surface, with its own `App contract:` fragment.

Owner decisions open, in the PR body: what "App contract fix:" may change; a release step that runs `check_app_contract accepts` against the minimum release once it is on PyPI; whether metab should state a contract number the app checks.

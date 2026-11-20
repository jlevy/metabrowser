---
type: is
id: is-01m7s00sfe12d516htcrkccr9s
title: "App contract follow-ups from #596 review B: git stand-in above the floor, CHECKOUT_PROJECT copy, fidelity nits"
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-19T04:11:14.797Z
updated_at: 2026-11-20T17:24:46.534Z
---
From PR #596 review B (attic/landing/reviews/pr596-senior-r2.txt, posted on the PR). B1: tests/fixtures/doctor/git answers 2.50.1 = ACQUISITION_NEWEST_PATCHED, so a Git security-floor bump turns the contract golden's git row into a warning and fails the contract lint and AppContractTests; use a stand-in version far above every floor (e.g. FAKE_GIT_VERSION 99.0.0) in _doctor. B2: CHECKOUT_PROJECT regex is not in the [[copy]] values; expose its source as a str constant (CHECKOUT_PROJECT_LINE) listed in the copy, or have one side's test read the other's sample table. B3: (1) doctor/as-the-app's config warning, relative cache dir, MAX_FIRST_CLONE_KB=1 are sandbox-made: say so in _doctor's docstring and the Swift test comment; (2) LiveMetabTests.swift:312-313 passes appBundle then replaces spec.environment, so METABROWSER_DOCTOR_APP never reaches the live run; (3) metab-contract.toml distribution-name 'what' should say uv and pipx.

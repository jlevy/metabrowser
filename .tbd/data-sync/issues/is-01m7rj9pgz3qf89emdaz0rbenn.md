---
type: is
id: is-01m7rj9pgz3qf89emdaz0rbenn
title: "One rule for the app's command-line dependencies (metab, gh, future tools): minimum versions and upgrade guidance"
kind: feature
status: closed
priority: 1
version: 10
delegate: claude-code@spud10
labels: []
dependencies: []
child_order_hints:
  - is-01m7rmjmzgk91n9czy6g19qk75
hold: null
hold_until: null
created_at: 2026-11-19T00:11:26.622Z
updated_at: 2026-11-19T04:11:15.458Z
started_at: 2026-11-19T00:12:06.859Z
closed_at: 2026-11-19T04:11:15.457Z
close_reason: "Phases 1-3 landed: #590 (minimum release and versioning rule), #596 (metab --doctor checks, gh minimum, Help > Check Setup..., contract entries). Review B Lows tracked separately."
resolution: null
duplicate_of: null
---
Owner, 2026-11-18, verbatim: "another question for us to review is to be clear about the dependency between metab CLI and the native app. Let's figure out what the best way to handle this is. Probably it's just to have a minimum version dependency represented in each native app build and then to instruct the user on how to upgrade metab if necessary. And same for gh and potentially, in the future, other CLI dependencies". Today: MetabRequirement.minimumRelease (apps/macos ShellCore) for metab; the gh status check (mb-si2g, PR #581) for gh. Goal: one declared requirement per tool in each app build (name, minimum version, how it is found, how its version is read, upgrade instructions by install method), one status/remedy UI in the app, one doc, and the rule for when a minimum is raised.

## Notes

Owner, 2026-11-18, verbatim: "We should also encode some sort of default convention, we are in if we change metab in a way that's incompatible with the front end, then we should create a new minor or major release but not a patch release (unless it's a bugfix), this contract would be at the minor release level or above". So: the app's minimum metab is always X.Y.0 or above; a patch never raises it. Document in publishing.md and AGENTS.md, and check it where a check fits.

Progress 2026-11-18 (PR #590, branch claude/cli-dependencies): Phase 1 done there. minimumRelease 0.12.1 -> 0.13.0; pyproject uv-dynamic-versioning bump = {enable, index 1} so a checkout reports 0.13.0.devN; [tool.uv] cache-keys add git commit and tags so make install rebuilds a checkout's version after each commit or tag (review A1; measured: no-op sync 0.05-0.09 s, rebuild 2.4-3.6 s once per commit/tag; keys in uv.toml are ignored). tests/test_macos_app_pins.py: minor-release form + bump, cache keys, minimum <= next minor after latest CHANGELOG release with isReleased false while newer (review A4). Rule written once in docs/publishing.md#choosing-a-version; AGENTS.md, development.md, arch-macos-app.md, MetabRequirement link to it. 0.x, 1.0+, and app-needed-fix treatment are proposals under the plan's Owner Decisions (seven). Plan: docs/project/specs/active/plan-2026-11-18-cli-dependencies-and-doctor.md.

Review A on #590 (2 Medium, 5 Low) all fixed at head 0fe93f6d0; dispositions posted; CI green (23 pass, 1 skipping). Phase 2 (after #581 merges): gh minimum as one constant in gh_status.py, gh_too_old compares gh_version with it (unknown-flag probe as fallback), fix is install-method upgrade, extend #581's github object (no gh entry in checks) per #581 review A6; the checks list; app Info.plist minimum; ShellCore-has-no-gh/git-version check plus AGENTS.md rule; golden; parity. Phase 3: metab install-method steps in MetabRequirement only (no Swift gh/git requirement), decoded doctor report, Help > Check Setup... reading github.gh_path/gh_version from the doctor. App contract golden is a separate PR (another agent).


Progress 2026-11-18 (PR #596, branch claude/doctor-check-setup, head c22544545+docs 6b607cfdb, base 8ce5c4c72): Phases 2 and 3 built. Phase 2: cli/doctor.py checks list (metab: version/executable/python/install method + app minimum from Info.plist MetabrowserMinimumMetab read via doctor_open_in; git: ACQUISITION_MINIMUM and PARTIAL_CLONE_GIT_MINIMUM with install-method remedy; config; cache incl. free space). Warning never changes exit; config/cache problem exits 1. gh: GH_MINIMUM (2,81,0) in gh_status.py (gh auth status --json, cli/cli#11544), gh_too_old by version then probe, fix by install method (tool_install.py), github.gh_minimum. Golden tests/golden/cli-doctor.tryscript.md (9 tests), parity row app.check-setup, distribution smoke gets a private cache dir. Not built (plan lists as follow-ups): markdown_renderer, browser, recent_targets, locks, stale editable install; the ShellCore no-gh/git-literal text check (dropped, reason in plan); uv check (decided no); network check (off, proposal). Phase 3: MetabInstall (uv receipt/pipx metadata/checkout .venv) and MetabRequirement.upgradeCommand(for:); DoctorReport/DoctorRun decode (unknown keys ignored, unknown state shown, missing checks = older 0.13.0.devN, unreadable shows output); Help > Check Setup... window with Check Again and Copy Report; Settings button opens it. Pins in test_macos_app_pins (plist minimum, upgrade commands). Minimum not raised (0.13.0 unreleased). Owner decisions now eight (uv added). Local: lint-check pass, goldens pass, focused pytest pass, Swift suites pass (quarantine-helper script check fails locally, environmental). Window hand checks written, not run.


CI 2026-11-18: PR #596 head 7afa78fd0 all checks pass (macOS 26 job included; stack-integration skipped). First run failed tests/test_icon_catalog.py (Check Setup SF Symbols uncataloged); fixed by rows in docs/design-system-icons.md. Not merged; awaiting owner decisions 1-8 in the plan.


Review A on #596 (3 Medium, 6 Low) fixed 2026-11-18 at head 723f83172 (commits 6e55a1087 metab, a7799dc5a app, a66395e31 docs; merges main a36923688): plugins and open_in are checks; github.remedy {text, command, url} (command only for gh_status._COMMANDS); app rows only from checks + github, CodingKeys with raw values, lossy per-check decoding (unreadable row); config dir problem reported once (open_in "not read" detail; METABROWSER_OPEN_IN error stays a problem); override warning when an app is found (app servers get no storage vars); low free space warning via low_free_space_bytes() (first-clone limit x1.1; LOW_FREE_SPACE_BYTES default) and not-creatable dir problem; METABROWSER_DOCTOR_APP (DoctorRun.spec sets the app bundle) for the metab check's minimum, open_in unchanged; one checkout rule (.venv beside pyproject.toml with name = "metabrowser") both sides, pinned per case and marker; Check Again always enabled; gh_too_old wording and docs (uncached PR + doctor check need 2.81.0); hand-check stand-ins runnable. Golden pins METABROWSER_MAX_FIRST_CLONE_KB=1. Changelog has an App contract entry. Dispositions: https://github.com/jlevy/metabrowser/pull/596#issuecomment-6998435819. Local: lint-check pass, focused pytest 361 pass, 4 goldens pass, Swift suites pass (quarantine-helper script check fails locally, environmental). #593 lands first: then add the contract entries (doctor command, DoctorReport.swift JSON reader, app_side MetabrowserMinimumMetab, MetabInstall copy, [[env]] METABROWSER_DOCTOR_APP).

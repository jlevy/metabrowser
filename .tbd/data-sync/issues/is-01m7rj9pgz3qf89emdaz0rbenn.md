---
type: is
id: is-01m7rj9pgz3qf89emdaz0rbenn
title: "One rule for the app's command-line dependencies (metab, gh, future tools): minimum versions and upgrade guidance"
kind: feature
status: in_progress
priority: 1
version: 6
delegate: claude-code@spud10
labels: []
dependencies: []
child_order_hints:
  - is-01m7rmjmzgk91n9czy6g19qk75
hold: null
hold_until: null
created_at: 2026-11-19T00:11:26.622Z
updated_at: 2026-11-19T00:59:18.721Z
started_at: 2026-11-19T00:12:06.859Z
---
Owner, 2026-11-18, verbatim: "another question for us to review is to be clear about the dependency between metab CLI and the native app. Let's figure out what the best way to handle this is. Probably it's just to have a minimum version dependency represented in each native app build and then to instruct the user on how to upgrade metab if necessary. And same for gh and potentially, in the future, other CLI dependencies". Today: MetabRequirement.minimumRelease (apps/macos ShellCore) for metab; the gh status check (mb-si2g, PR #581) for gh. Goal: one declared requirement per tool in each app build (name, minimum version, how it is found, how its version is read, upgrade instructions by install method), one status/remedy UI in the app, one doc, and the rule for when a minimum is raised.

## Notes

Owner, 2026-11-18, verbatim: "We should also encode some sort of default convention, we are in if we change metab in a way that's incompatible with the front end, then we should create a new minor or major release but not a patch release (unless it's a bugfix), this contract would be at the minor release level or above". So: the app's minimum metab is always X.Y.0 or above; a patch never raises it. Document in publishing.md and AGENTS.md, and check it where a check fits.

Progress 2026-11-18 (PR #590, branch claude/cli-dependencies): Phase 1 done there. minimumRelease 0.12.1 -> 0.13.0; pyproject uv-dynamic-versioning bump = {enable, index 1} so a checkout reports 0.13.0.devN; [tool.uv] cache-keys add git commit and tags so make install rebuilds a checkout's version after each commit or tag (review A1; measured: no-op sync 0.05-0.09 s, rebuild 2.4-3.6 s once per commit/tag; keys in uv.toml are ignored). tests/test_macos_app_pins.py: minor-release form + bump, cache keys, minimum <= next minor after latest CHANGELOG release with isReleased false while newer (review A4). Rule written once in docs/publishing.md#choosing-a-version; AGENTS.md, development.md, arch-macos-app.md, MetabRequirement link to it. 0.x, 1.0+, and app-needed-fix treatment are proposals under the plan's Owner Decisions (seven). Plan: docs/project/specs/active/plan-2026-11-18-cli-dependencies-and-doctor.md.

Review A on #590 (2 Medium, 5 Low) all fixed at head 0fe93f6d0; dispositions posted; CI green (23 pass, 1 skipping). Phase 2 (after #581 merges): gh minimum as one constant in gh_status.py, gh_too_old compares gh_version with it (unknown-flag probe as fallback), fix is install-method upgrade, extend #581's github object (no gh entry in checks) per #581 review A6; the checks list; app Info.plist minimum; ShellCore-has-no-gh/git-version check plus AGENTS.md rule; golden; parity. Phase 3: metab install-method steps in MetabRequirement only (no Swift gh/git requirement), decoded doctor report, Help > Check Setup... reading github.gh_path/gh_version from the doctor. App contract golden is a separate PR (another agent).

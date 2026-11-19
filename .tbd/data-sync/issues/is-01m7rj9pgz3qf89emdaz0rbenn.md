---
type: is
id: is-01m7rj9pgz3qf89emdaz0rbenn
title: "One rule for the app's command-line dependencies (metab, gh, future tools): minimum versions and upgrade guidance"
kind: feature
status: in_progress
priority: 1
version: 5
delegate: claude-code@spud10
labels: []
dependencies: []
child_order_hints:
  - is-01m7rmjmzgk91n9czy6g19qk75
hold: null
hold_until: null
created_at: 2026-11-19T00:11:26.622Z
updated_at: 2026-11-19T00:51:17.102Z
started_at: 2026-11-19T00:12:06.859Z
---
Owner, 2026-11-18, verbatim: "another question for us to review is to be clear about the dependency between metab CLI and the native app. Let's figure out what the best way to handle this is. Probably it's just to have a minimum version dependency represented in each native app build and then to instruct the user on how to upgrade metab if necessary. And same for gh and potentially, in the future, other CLI dependencies". Today: MetabRequirement.minimumRelease (apps/macos ShellCore) for metab; the gh status check (mb-si2g, PR #581) for gh. Goal: one declared requirement per tool in each app build (name, minimum version, how it is found, how its version is read, upgrade instructions by install method), one status/remedy UI in the app, one doc, and the rule for when a minimum is raised.

## Notes

Owner, 2026-11-18, verbatim: "We should also encode some sort of default convention, we are in if we change metab in a way that's incompatible with the front end, then we should create a new minor or major release but not a patch release (unless it's a bugfix), this contract would be at the minor release level or above". So: the app's minimum metab is always X.Y.0 or above; a patch never raises it. Document in publishing.md and AGENTS.md, and check it where a check fits.

Progress 2026-11-18 (PR #590, branch claude/cli-dependencies): Phase 1 done there. minimumRelease 0.12.1 -> 0.13.0; pyproject uv-dynamic-versioning bump = {enable, index 1} so a checkout reports 0.13.0.devN; tests/test_macos_app_pins.py::test_the_apps_minimum_metab_is_a_minor_release and MetabVersionTests.theMinimumIsAMinorRelease; rule in docs/publishing.md#choosing-a-version, AGENTS.md, development.md, arch-macos-app.md, MetabRequirement doc comment. Plan: docs/project/specs/active/plan-2026-11-18-cli-dependencies-and-doctor.md (inventory, design, phases, six owner questions). Phase 2 (doctor checks list, gh minimum in gh_status.py, app Info.plist minimum, golden, parity) waits for #581 to merge. Phase 3: ToolRequirement in ShellCore, decoded doctor report, Help > Check Setup... Contract-surface golden is a separate PR (owner scope change, 2026-11-18).

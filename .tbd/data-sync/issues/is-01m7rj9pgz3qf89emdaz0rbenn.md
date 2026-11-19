---
type: is
id: is-01m7rj9pgz3qf89emdaz0rbenn
title: "One rule for the app's command-line dependencies (metab, gh, future tools): minimum versions and upgrade guidance"
kind: feature
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T00:11:26.622Z
updated_at: 2026-11-19T00:12:06.866Z
started_at: 2026-11-19T00:12:06.859Z
---
Owner, 2026-11-18, verbatim: "another question for us to review is to be clear about the dependency between metab CLI and the native app. Let's figure out what the best way to handle this is. Probably it's just to have a minimum version dependency represented in each native app build and then to instruct the user on how to upgrade metab if necessary. And same for gh and potentially, in the future, other CLI dependencies". Today: MetabRequirement.minimumRelease (apps/macos ShellCore) for metab; the gh status check (mb-si2g, PR #581) for gh. Goal: one declared requirement per tool in each app build (name, minimum version, how it is found, how its version is read, upgrade instructions by install method), one status/remedy UI in the app, one doc, and the rule for when a minimum is raised.

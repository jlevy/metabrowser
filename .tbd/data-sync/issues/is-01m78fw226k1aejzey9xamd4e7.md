---
type: is
id: is-01m78fw226k1aejzey9xamd4e7
title: "macOS app: Settings > Plugins and the repository bar"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:11.621Z
updated_at: 2026-11-12T21:17:47.368Z
---
Phase 4, on the macOS app stack (plan: The macOS App). A native Settings > Plugins list from metab --plugins --json with each source's kind, scope, location, providers, and problems; Add... runs metab-plugins --add --dry-run --json PATH (metadata only), shows a native confirmation with the environment, providers, declared environment names, the privacy-grant note, and the hash, then runs metab-plugins --add --expect SHA256 --json PATH; Remove. The repository bar for an undecided clone or a new provider, with Trust (runs metab-plugins ROOT --trust --expect SHA256), Review, and Not Now; a missing environment is reported with what the repository documents, never set up by the app. Restart affected servers after a change through the upgrade-restart path until reload lands. Hide plugin settings and show the upgrade command when metab --plugins --json lacks sources. A LiveMetabTests check that stopping a folder leaves no worker; README sections.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.

# Feature: Link Preview Tooltips

**Date:** 2026-11-26 (last updated 2026-11-26)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft

## Overview

A link in rendered text that opens a page in Metabrowser looks like any other link, so a
reader cannot tell, before clicking, what it opens or that it stays in the app.
This phase gives such a link a concise tooltip: what kind of object it opens, that
object’s title or description when the app knows it, and that it opens here.
Resting on the link also starts loading the page it opens, so the click is fast.
Tooltips on links follow one rule everywhere, documented in the design system.

It builds on [In-App Link Resolution](plan-2026-11-26-in-app-link-resolution.md), whose
resolver (`static/repository-links.js`) already decides what each link opens, and is
stacked on the pull request that opens route links in place (`mb-0uzt`).

The owner asked, on 2026-11-26:

> “With page-to-page linking, let’s make sure that we offer concise tooltips.
> We should be able to recognize what the object is and prefetch it if it’s on the link.
> And then the tooltip could show the title or the description of what the linked GitHub
> object is, if available.
> It would also make it clear that it’s a local link, so it’s easy to click without
> navigating away from metabrowser.”
> 
> “This should follow a consistent design system that aligns with everything else we’ve
> done, and we should be consistent on tooltips on links in general.
> And document the design system.”

## Goals

- A link the resolver opens in the app (a file or folder, a pull request or one of its
  tabs or changed files, a stack, a commit, the pull request list) shows, on pointer
  rest, a tooltip that names the object’s kind and identity, its title or description
  where known, and that it opens in Metabrowser.
- Resting on such a link prefetches what its click opens, within existing budgets.
- One documented rule for tooltips on links in general, in-app and external, in
  `docs/design-system.md`, held by a check where it can be.

## Non-Goals

- Tooltips on the app’s own chrome links whose text already says what they open (a Pulls
  row’s title, a crumb): the design system’s “Tooltips Add Information” keeps those
  without one.
- New GitHub requests made only to fill a tooltip.

## Background

The design system already fixes how a tooltip behaves
([One Tooltip, and It Is Ours](../../../design-system.md#one-tooltip-and-it-is-ours)
through
[A Surface Puts Away Only Its Own Tooltip](../../../design-system.md#a-surface-puts-away-only-its-own-tooltip)):
the app’s own tooltip and never `title`, only when it adds information, pointer-only,
placed on its anchor and holding still, and put away by the surface that showed it.
The Git panel’s commit hover card and the table plugin’s reference card are the existing
rich cards. [External GitHub Links](../../../design-system.md#external-github-links)
gives an outside GitHub link its mark.

## Design

To be completed from the survey of the tooltip primitives, the data each kind of object
already has on the client, and the prefetch facilities.

## Implementation Plan

### Phase 1: Link Previews

- [ ] The design-system rule for tooltips on links
- [ ] The preview card and its data for each kind
- [ ] Prefetch on pointer rest
- [ ] Every surface the resolver serves shows it

## Testing Strategy

Browserless sessions run the exact production modules, with a golden transcript and a
parity row for each new surface (AGENTS.md, CLI and Functional UI Parity); a Chrome
check confirms the tooltip’s placement and timing.

## Open Questions

- None yet.

## References

- [In-App Link Resolution](plan-2026-11-26-in-app-link-resolution.md)
- [Design System: tooltips](../../../design-system.md#one-tooltip-and-it-is-ours)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

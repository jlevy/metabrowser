# Feature: Diff Presentation

**Status:** Implemented

Use the same comparison controls for pull requests, stacks, commits, patch files, and
files cited together in a guided review.
Ship the shared controls, defaults, rendering, and design-system documentation in one
pull request against `main`.

## Interaction

The comparison toolbar holds three joined choices.
A guided review puts the same control directly above the references in its step.

| Choice | Tooltip | Content |
| --- | --- | --- |
| Diff | Show additions and removals with surrounding context. | Both sides of a change in a form appropriate to the file. |
| Excerpt | Show the new version around the changes. | The new side around changes, with deletion locations marked. |
| Full | Show the entire new version at the revision under review. | The pinned new side with change marks where available. |

Each supported file has a **Rendered** or **Source** choice and a collapsible header.
Format is local to the file and survives a mode change.
A file in Diff can expand its unchanged sections while keeping deletions visible.
Source in Diff can use Split or Unified.
Excerpt and Full use one column.
Preferences sets the default source layout.
The visible layout chooser overrides it for this comparison and keeps its selection
while a reading mode is active.
A narrow pane can fit Unified before an explicit Split choice.
Docs and guide excerpts use their existing one-column layout.

## Defaults and Bounds

- Changes opens on Diff and prefers Rendered where available.
  Existing saved view choices keep their meaning.
- Docs prefers Full per file and uses Excerpt when the document crosses the existing
  bounds for opening it whole.
  A user can request the complete document at the comparison’s revision.
  A file that cannot show Full inline states why.
- A guide starts with each reference’s existing drawing policy.
  An explicit choice applies to the files in that block.
  Source ranges stay within the cited comparison and scope, including references to
  removed lines. Open full diff goes to the comparison that supplied the citation.
- A patch with no accessible complete file offers Diff and Excerpt.
  Binary, deleted, truncated, and unavailable content retain their status notices.
  Keep existing render limits, lazy loading, cancellation, and scroll and focus
  restoration.

## Implementation and Evidence

Use the diff plugin’s projection, toolbar, and file disclosure for both standalone
comparisons and guide blocks.
Use the existing pinned content access for Full source.
Keep format decisions separate from Markdown coverage and from the tree disclosure
state.
Test the production interaction state in browserless sessions and exercise layout,
focus, and scroll in Chrome.
Update the design system, user guides, parity records, and changelog with the
implementation.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

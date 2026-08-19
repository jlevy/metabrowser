# Nav Containers: Item-Like and Folder-Like Roles

**Status:** Design.
Directories already behave this way; the generalization is not built.
The first adopter is the diff work in the
[general diff rendering plan](../specs/active/plan-2026-08-17-general-diff-rendering.md).

## The two roles

Every entry in the navigation tree plays one or both of two roles:

- **Item-like:** selecting it opens a document with view tabs.
  A file is item-like.
  So is one file’s change inside a patch.
- **Folder-like:** it expands in place to child entries, and selecting the entry itself
  — as opposed to expanding it — opens an overview of the whole.
  A directory is folder-like.
  So is a patch file.

The roles are capabilities, not types.
An entry can be both: a patch file is item-like (it is a real file with bytes and views)
and folder-like (its file changes are worth navigating individually).
This is the load-bearing distinction: nothing in the tree contract should ask “is this a
directory?”, only “does this entry expand, and what does selecting it open?”

## Directories are the precedent, not a special case

The tree already implements the full contract for one kind: clicking a folder row opens
the folder’s Overview as main content, the expansion triangle discloses children,
keyboard expansion and lazy child loading work, and selection-follows-focus opens
whatever the focus lands on.
The generalization keeps every one of those behaviors and widens who may declare them,
so a design question about containers can usually be answered by asking what a directory
already does.

## Container kinds

| Container | Children | Outer selection (overview) | Inner selection |
| --- | --- | --- | --- |
| Directory | Files and folders | Folder Overview | The file’s views |
| Patch / diff file | One entry per file change | The change-set summary (the whole-document diff view) | That file’s diff, as view tabs (Diff, later Before/After) |
| GitHub PR mirror | The PR’s changed files | PR summary: title, state, totals, description | Same as patch, plus review-thread anchors later |
| Archive (`.zip`) | The archive’s members | Listing or summary | The member file’s ordinary views, by its own kind |

The inner entries are ordinary item-like objects: a file change carries the diff view
family; a zip member is just a file whose kind is detected as usual.
No new rendering machinery — the same envelope of view descriptors, mounted lazily as
tabs, with the container choosing the context default (Diff inside a comparison).

## What stays uniform

- **URLs.** The canonical `/view/<path>` grammar extends by paths, because container
  membership is path-shaped: `/view/changes.patch` is the overview and
  `/view/changes.patch/src/app.py` is one file’s diff.
  Fragments keep meaning in-document locations; presentation state stays in reserved
  `_mb_` query keys.
- **Tree mechanics.** Roving focus, `aria-expanded`, lazy child pagination, filtering,
  and selection-follows-focus apply to every container identically.
  Filters filter inner entries like any rows; a comparison is, among other things, a
  filter down to the files that changed.
- **The plugin boundary.** A plugin that owns a kind declares the folder-like capability
  the way it declares views today: children come from a data hook, the overview is a
  view. Core provides the contract; the diff plugin, an archive plugin, and a PR plugin
  provide the containers.

## Materialization: transient caches, one discipline

Containers whose children are not directly on disk — a PR that must be fetched, a patch
anchoring against a base, an archive that must be unpacked — materialize into bounded,
transient cache directories, and the ordinary serving path routes into the materialized
tree. One mechanism with one eviction and bounds policy, shared across container kinds,
not a per-kind cache.
The git-specific acquisition workflow (reference clones, `refs/pull/N/head`, transient
worktrees) is the diff plan’s instance of this.

## Zoom

Because a container is a subtree, “focus on this PR” is re-rooting the tree at the
container — the same move as serving a subdirectory, applied at a container boundary.
This is future work, but it falls out of the model rather than needing one: any
folder-like entry is a possible root.

## Boundaries

- A container’s children are entries, not mounts: nothing above the container changes,
  and closing it releases whatever it materialized.
- Overviews are views, so they follow the renderer rules — disposal paths, lazy
  mounting, measured size bounds.
- Live updates follow the source: a directory’s children track the filesystem, an
  immutable comparison never repaints under the reader, an uncommitted one goes stale
  with a refresh offer.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

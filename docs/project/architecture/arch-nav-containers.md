# Nav Containers: Item-Like and Folder-Like Roles

**Status:** Implemented for the first two container kinds (directories and patch files);
archives and PR mirrors are planned.
The diff plugin is the first adopter, through the
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
| Hosted-review collection | Cached change requests | Query, freshness, completeness, and offline summary | The change-request document and views |
| Hosted change-request bundle | The change request’s changed files | Change summary: title, state, totals, description | Same as patch, plus hosted-review state and review-thread anchors |
| Archive (`.zip`) | The archive’s members | Listing or summary | The member file’s ordinary views, by its own kind |

The inner entries are ordinary item-like objects: a file change carries the diff view
family; a zip member is just a file whose kind is detected as usual.
No new rendering machinery — the same envelope of view descriptors, mounted lazily as
tabs, with the container choosing the context default (Diff inside a comparison).

## The mechanism

A kind declares the folder-like role in its manifest:

```toml
[[kind]]
id = "diff"
match = { ext = ".patch" }
container = { children = "children" }
```

`container.children` names one of the plugin’s own `[[data_hook]]` routes, validated at
manifest load; the hook returns `{children: [{name, path, badge?, muted?}]}` for
`?path=<container file>`. Three consequences follow, and no other machinery is added:

- **The tree** renders such a file with a chevron and an empty child group, fetches the
  children on first expand, and renders them as ordinary item-like rows.
  Disclosure is a capability throughout: the ARIA synchronizer and the arrow-key
  handlers ask whether a row owns a child group, never whether it is a folder.
- **The server** resolves `<container-file>/<inner>` by walking the requested path’s
  ancestors — bounded, through the same safe-path gate — and letting the nearest
  existing *file* ancestor of a container kind claim everything beneath it.
  A real directory ancestor means the leaf is genuinely missing, so ordinary 404s are
  unchanged. On a `GitRevisionSubject` there is no filesystem ancestor walk: contiguous
  `g1-` tokens are the container’s `GitPath`, and anything after that prefix is the
  virtual inner path. Only implemented patch/diff blobs claim an inner; archives remain
  later.
- **The views** of that kind render the virtual path, because the envelope carries the
  same `kind` plus `container` and `container_inner`. The diff plugin’s document hook
  answers a virtual path with the change set narrowed to that file, so the renderer
  needs no notion of containment at all.

One row per inner path: a patch spells a type change as delete-plus-add at one path, and
two rows sharing a virtual path would be two rows opening the same thing, so the
children hook groups by path and the narrowed document carries both halves.

## What stays uniform

- **URLs.** Container membership is path-shaped, so a container’s children extend its
  own address: `/view/changes.patch` is the overview and
  `/view/changes.patch/src/app.py` is one file’s diff.
  The same shape works in any address space — `/commit/<rev>` and
  `/commit/<rev>/src/app.py` are a commit’s container and child — because the route
  names the space and the rest is `<container address>/<inner path>`. See
  [Browser URL Grammar](../../architecture.md#browser-url-grammar).
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

## Collection panels

A folder-like container does not have to live in the Files tree.
The planned Pull Requests nav panel exposes one virtual hosted-review collection whose
children come from a bounded `ChangeRequestIndex/v1`. It reuses Git history’s paged
loading, virtualization, roving selection, and restoration mechanics, while each
selected PR uses the container behavior above to expose changed files.

Counts, grouping, and folder visibility come from the complete bounded collection model,
never from currently mounted rows.
The collection overview makes its query, bounds, freshness, completeness, offline state,
and refresh diagnostics visible.

## Transient projections and the four cache lifetimes

“Cache” does not name one interchangeable storage mechanism:

1. The repository library durably owns a shared worktree-free Git object store and
   private refs.
2. A provider mirror durably owns immutable hosted-review snapshots and current
   manifests under stable provider-repository and authorization identity, independently
   of source aliases and local checkouts.
3. A subsystem that genuinely needs filesystem bytes owns its bounded transient
   projection. Archive extraction is one example; immutable Git subjects read trees and
   blobs directly and do not create a filesystem projection.
4. Inventory pages, comparison manifests, patches, and browser projections are bounded,
   recomputable session caches.

Only the third layer contains transient filesystem projections.
Review anchors are provider-domain records in layer 2, while diff manifests and patches
are recomputable records in layer 4; neither is a materialized directory.
Projection types share low-level safe-path or lease helpers only after two implemented
owners prove the same contract, and each owner keeps its own admission, bounds, and
reclamation policy. The
[repository-source architecture](arch-repository-sources-and-provider-mirrors.md) owns
the worktree-free store and subject boundary; the
[hosted-review architecture](arch-hosted-review-model.md) owns layer 2 and defines how
the four compose.

## Zoom

Because a container is a subtree, “focus on this PR” is re-rooting the tree at the
container — the same move as serving a subdirectory, applied at a container boundary.
This is future work, but it falls out of the model rather than needing one: any
folder-like entry is a possible root.

## Boundaries

- A container’s children are entries, not mounts: nothing above the container changes,
  and closing it releases whatever it materialized.
- Expansion state is held in the DOM, exactly as folder expansion is: a full tree
  repaint renders containers collapsed again (one bounded refetch on re-expand), while
  filter changes leave expanded children in place.
- Overviews are views, so they follow the renderer rules — disposal paths, lazy
  mounting, measured size bounds.
- Live updates follow the source: a directory’s children track the filesystem, an
  immutable comparison never repaints under the reader, an uncommitted one goes stale
  with a refresh offer.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

# Source Sessions and Pins

**Status:** Implemented: one active subject per server process, either an attached
folder or a pinned Git revision; the content-source contract and capabilities; `GitPath`
projection on every content route; switching the pin within one store; and the pin
guard. A server that serves several subjects at once is not designed: it would need
subject-qualified addresses on every route.

A session’s **subject** is what it browses.
Where the subject’s Git objects come from is the
[repository cache](arch-repository-cache.md), and how a mirror is fetched and refreshed
is in [mirror acquisition and refresh](arch-mirror-acquisition-and-refresh.md).
[Git Reading and History](arch-git.md) covers the Git commands a subject’s routes run.

## Subjects

There are two kinds, `RepositorySubjectKind` in `source.py`:

- **An attached folder** (`attached_filesystem`) is the authority for a user’s own
  files, including uncommitted changes, with the watcher, the filesystem inventory, and
  safe-path containment.
  Metabrowser never fetches into, switches, resets, locks, or writes a checkout or its
  `.git` directory.
- **A pinned revision** (`git_revision`, `GitRevisionSubject` in `git/tree_source.py`)
  is one commit of a Metabrowser-owned, worktree-free repository store.
  A branch, tag, or pull-request head is resolved once to a full commit ID; the subject
  records the ref it came from and the ID, and every tree, blob, history, and diff read
  uses the ID.

Because a pin reads Git objects directly, two server processes can serve different
branches of one store at the same time, with no index, checked-out branch, or detached
worktree.

## The Source Session

`SourceSession` in `source.py` is the one active subject of this process: the subject, a
`generation` that counts attachments in this process, and a lease.
`get_source_session()` returns it; a request that arrives while a configured subject is
not open, before startup or after shutdown, raises `SubjectNotOpenError` rather than
serving the working directory in the pin’s place.

`replace_owned_subject` switches the served pin: it attaches the new subject under a new
generation first, so every request that starts afterwards reads it, and then closes the
old one, which releases only its share of the store’s batch readers.
`/api/source/status` reports the subject, its generation, and the pin.

## Content Sources

Both kinds of subject answer one content contract (`ContentSource` and `ContentRef` in
`source.py`), not one invented filesystem:

- resolve an identity to readable content, or `None` when it escapes the root, names
  nothing, or names a directory or tree;
- split a container address `<content>/<inner>` for the suffixes the calling container
  claims;
- give a fingerprint that changes exactly when the bytes can have, the logical
  extension, and the stored size, with no read;
- read a bounded byte window.

`FilesystemContentSource` serves a folder.
`GitTreeSource` enumerates trees with NUL-framed `ls-tree` and reads blobs through
pooled batch `cat-file` processes, at most `MAX_BATCH_READERS_PER_STORE` per store.
One actor serializes each batch process, asks `info` before `contents`, enforces the
declared size bound, drains the whole frame, and restarts the process after a
cancellation or a framing failure.
A tree entry has a Git mode, kind, and object ID, and a blob’s size comes from
`cat-file` info. It never invents an mtime, ignore state, owner, or watcher event.

A blob the tree names can be missing when a store is damaged or a borrowing store’s
lender lost the object.
The read answers `object_unavailable` without contacting the origin; repair is a
separate, explicit operation.

## Capabilities

`SourceCapabilities` declares what a subject can do: `navigation`, `index`, `recency`,
`ignore`, `watcher`, `activity`, and `mutation`. A folder has all of them
(`FILESYSTEM_CAPABILITIES`, where `mutation` is a source fact, not the content-trust
setting that keeps writes off).
A pin has navigation and an index, and nothing else (`GIT_REVISION_CAPABILITIES`).

A route that needs an absent capability answers 409 `unsupported_for_subject` with the
capability’s name, or its view is absent; it never answers a fake zero, an empty event
stream, or a placeholder timestamp.
So on a pin `/api/recent`, `/api/activity`, `/api/stream`, recency filters, and editing
are unavailable, while size and kind rollups answer from the blob index.

## The Plugin Content Boundary

`plugin_api.py` gives plugin hooks bounded operations over an opaque `ContentRef`:
`resolve_content`, `resolve_content_container`, `stat_content`, and
`read_content_window`. A hook passes back the identity its client holds, an inventory
path on a folder or a `GitPath` wire on a pin, and never builds one or branches on the
subject kind.

- `resolve_content` answers `None` for every identity that names nothing readable.
  `resolve_content_container` scopes a container address to the suffixes the calling
  container claims, so one plugin cannot open another’s files.
  Both return the identity to echo back, the logical extension, a fingerprint a hook can
  key its cache on, and the stored size.
- `read_content_window` requires `max_bytes`, a bound on bytes rather than on decoded
  text, and says whether content continues past the window.
  On a pin a window streams the blob from its start, so reaching an offset costs reading
  up to it, and no blob is refused for its size.
  `stat_content` is the separate, costlier call for a validated logical size.
- Every failure is a `ContentReadError` with a `code` and an `http_status`, the statuses
  the pinned routes answer with.
  `tests/test_plugin_content_reader.py` pins them against
  `git_content_failure_response`.

`resolve_path`, `resolve_directory`, `served_root`, and `open_content` are
filesystem-only and raise `UnsupportedSourceCapabilityError` on a subject with no
filesystem root. These calls add to the Python helper surface and leave the browser SDK
alone, so `PLUGIN_SDK_VERSION` does not move for them.

## Path Projection

A pin’s tree can hold names that are not valid inventory paths, or not UTF-8 at all.
`GitPath` in `git/tree_source.py` is the identity: a tuple of raw byte segments, each
non-empty and free of NUL and `/`, and never a host `Path`.

- **The wire form** writes each segment as `g1-` and its unpadded base64url, joined by
  `/`. It is lossless, and decoding refuses any non-canonical spelling.
  `static/git-path.js` is the browser’s codec; the server writes it into a pin’s page,
  and the diff plugin imports it on demand beside a checkout.
- **A container address** is the `GitPath` prefix of `g1-` tokens plus a host inner path
  (`split_git_container_wire`), so a patch file inside a pinned tree is addressed as it
  is in a folder.
- **The display form** passes each segment through `display_segment` in
  `invisible_chars.py`, which turns control characters, characters that draw as nothing,
  and bytes that are not UTF-8 into U+FFFD; that module holds the tables and their known
  gap. Display text is for reading and never becomes an identity.

`/view/` on a pin accepts a `GitPath` wire, optionally with a container inner path, and
refuses a filesystem spelling.
Markdown and wiki links on a pin resolve to `GitPath` wires, and the known-file catalog
indexes display names.
The browser’s path chrome and copy-path decode wires to display names; navigation
identities stay wires.

## What a Pin Serves

The content routes answer a pin from the tree and blob index with the same envelopes a
folder gets, minus every fact a Git tree does not have.
`git/content_routes.py` and `git/tree_source.py` hold the route-by-route details in
their module docstrings.
The rules they follow:

- **Listings** (`/api/tree`) keep Git-native `entries` and project the browser’s `tree`
  nodes, with `cat-file` blob sizes and recursive `total_files` and `total_size`.
  `depth` nests children as on a folder.
  Gitlinks are unsized files.
  There is no mtime and no ignore state, so `include_ignored=0` is a no-op and the
  browser hides Modified within.
- **The whole-tree index** is complete at once: `/api/catalog`, `/api/rollup`, the type
  rows and `summary` on `/api/tree`, and `/api/index/progress`, `/api/index/meta`, and
  `/api/capabilities` answer from the recursive blob index with no watcher.
  An incomplete size tally omits `summary` and the rollup rather than answering zero.
  `types` and `min_size` filter as on a folder, using the same bounded compound-tail
  logical extension. Group by works by file type: `group_by=type` answers each display
  group’s tree from the same blob index, and `group=type:<id>` lists one group’s tree.
  A group’s `size` is null when its blob sizes are incomplete, and its `files` too when
  the index is truncated.
  `group_by=age` and `group=age:…` answer `unsupported_for_subject` (409), as `recency`
  does, and the page offers no Age.
- **A tree** answered by `/api/file` is folder chrome with recursive tallies.
  A direct-child README mounts Overview, and a complete size tally mounts the treemap.
- **A blob** answered by `/api/file` chooses its kind from its name’s last extension, as
  a folder’s file does.
  It carries no compressed identity, since blobs are stored bytes with no gzip smudge.
  Markdown carries parsed `frontmatter`, text keeps the folder’s first-window and
  highlight bound, and an image is image chrome with `/raw` serving the stored bytes.
  LFS pointers stay pointer bytes.
- **Symlinks:** `/api/file`, `/raw`, KPress, and plugin hooks follow an in-tree relative
  symlink blob; listings show the link, and kind checks use the leaf path.
- **Plugin data:** binary chunks, structured parses, and agent-log charts read one blob
  by its `GitPath` and key on its object ID. Inventory-backed JSONL `/api/stream`
  answers `unsupported_for_subject`.

`tests/test_serve_pin.py` asks every registered GET route of a served mirror for its
answers.

## Switching the Pin and the Pin Guard

`POST /api/source/pin` switches the served pin to another branch, tag, or commit of the
same store, resolved in the mirror alone.
Given the `/view/` address the page shows, it answers `view_href`, where that page goes
on the new pin. How a selection is resolved, and what happens when the mirror lacks it,
is in [mirror acquisition and refresh](arch-mirror-acquisition-and-refresh.md).

A switch, or a restarted server serving another commit, can leave a tab showing the old
pin. Reading the new pin’s files into a page labeled with the old one would mix two
revisions, so every data request from a pin’s page names its commit:

- The server writes `static/source-pin-guard.js` inline into a pin’s page, with the
  commit the page was rendered for, before any other script can fetch.
  It wraps `fetch` so every same-origin `/api/` request outside `/api/source/` carries
  the commit in `x-metabrowser-pin`.
- `SourcePinGuard` in `source_routes.py` refuses a request that names another commit
  with 409 `pin_changed` and the served commit in `x-metabrowser-pin-changed`. A request
  that names no commit, from `curl`, `metab --api`, or a folder’s page, is not checked.
- The page announces the refusal as a `metabrowser:pin-changed` event, and the freshness
  row offers a reload.
  Nothing changes under a reader who is looking at the page.

The commit is the token rather than the generation, because a generation restarts with
every server process while a commit names exactly the content the page shows.
Loads that are not `fetch` calls, such as an image in rendered Markdown, carry no
commit.

Back and forward restore a page without asking the server, from the back/forward cache
or the HTTP cache, so a restored page can name a commit the server stopped serving.
The page stays cacheable; on a history landing, and only then, the guard asks
`/api/source/status` once and reloads, at most once, when another commit is served.
`Cache-Control: no-store` would have kept every pin page out of the back/forward cache;
the comparison is measured in the module header and in
[the history-landing record](../../../explorations/history-landing/README.md).
The functional rows `source.stale-pin-guard` and `source.history-landing` in the
[parity registry](arch-parity-registry.md) pin both behaviors.

**View file and View on branch.** A diff’s file bar opens the file the change makes, its
new side, in the main UI: **View file** on a commit’s diff, and **View on branch** on a
pull request’s Changes while the diff shows the pull request’s head.
The comparison document says which commit that side is at, so on a pin’s page the
control is a link to its `/view/` address when the page shows that commit, and otherwise
a button that switches the pin with `POST /api/source/pin`, naming the address so the
answer’s `view_href` says where to go.
A pull request’s switch names the commit and, as `under`, its `refs/pull/<n>/head`, so
the page lands on the pull request rather than a bare commit or another pull request
with the same head. When that ref is no longer at the commit, because the pull request
moved on after the page was drawn, the pin route refuses with `409 ref_moved` and
switches nothing, so View on branch and Browse code on that page say the head moved
instead of opening a bare commit.
Beside a checkout, which has no pin, View on branch is a link to the working-tree file
while the checkout’s `HEAD` is the diff’s head.
The old side has no control: a parent is a bare commit, and a merge base is on no
branch. Only a regular file’s side gets a control, since a submodule’s side is another
repository’s commit and a symbolic link’s would open its target.

The pin is server-wide, so a switch from one tab moves every tab’s; a tab learns it when
a data request is refused (`metabrowser:pin-changed`). A mounted diff then turns each
link into the button that switches back, since the same `/view/` address now opens the
other pin, and its rendered Markdown’s links to files of the head into plain text.
A switch and the navigation after it are two steps, because a `/view/` address names no
revision; that is a limit of this design, not something View on branch adds.
`builtin_plugins/diff/diff-view-file.js` holds the rules in its header, and the parity
rows `diff.view-file` and `diff.view-file-sides` pin them.

## How a Mirror’s Page Names Itself

A served mirror’s page is headed by its repository’s name, as a folder’s is by its own,
and every route answer stays free of cache and store paths but one field.
[What a Mirror’s Page Is Called](arch-mirror-acquisition-and-refresh.md#what-a-mirrors-page-is-called)
holds the naming rule, the exception, and the test that guards it.

## References

- [Git Reading and History](arch-git.md)
- [Diff Pipeline](arch-diff-pipeline.md)
- [Repository cache](arch-repository-cache.md)
- [Mirror acquisition and refresh](arch-mirror-acquisition-and-refresh.md)
- [Views, models, and routes](arch-views-models-routes.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

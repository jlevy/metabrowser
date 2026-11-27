# Source Sessions and Pins

**Status:** Implemented: one active subject per server process, either a folder’s
working tree or a pinned revision, of a mirror or of a repository folder’s own checkout;
the content-source contract and capabilities; `GitPath` projection on every content
route; switching the pin within one store; a folder’s server showing a
[revision of its own checkout](#revisions-of-a-checkout) in its working tree’s place
([Open Modes](arch-open-modes.md), `mb-8ob8`); and the pin guard.
A server that serves several subjects at once is not designed: it would need
subject-qualified addresses on every route.

A server’s root, and whether it is a folder or a mirror, are fixed for its life
([Open Modes](arch-open-modes.md)). Its **subject** is the view it shows now: a folder’s
working tree, or one revision.
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
  `.git` directory. A branch, tag, or commit of a checkout is a revision too, and showing
  one never switches, fetches into, or writes the checkout.
  [Open Modes](arch-open-modes.md#views) says which views a root has, and
  [Revisions of a Checkout](#revisions-of-a-checkout) how a checkout’s revision is read.
- **A pinned revision** (`git_revision`, `GitRevisionSubject` in `git/tree_source.py`)
  is one commit of a Metabrowser-owned, worktree-free repository store.
  A branch, tag, or pull-request head is resolved once to a full commit ID; the subject
  records the ref it came from and the ID, and every tree, blob, history, and diff read
  uses the ID. A folder’s server can serve one commit of its own checkout the same way,
  read from the checkout’s Git directory and still never written
  ([Revisions of a Checkout](#revisions-of-a-checkout)).

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
A pin has navigation and an index, and nothing else (`GIT_REVISION_CAPABILITIES`). Where
the Git can date its files, it also has `recency`
(`GIT_REVISION_CAPABILITIES_WITH_AGES`, [file ages](arch-git.md#file-ages)).

A route that needs an absent capability answers 409 `unsupported_for_subject` with the
capability’s name, or its view is absent; it never answers a fake zero, an empty event
stream, or a placeholder timestamp.
So on a pin `/api/activity`, `/api/stream`, and editing are unavailable, and so are
`/api/recent` and the recency filters where the Git cannot date its files, while size
and kind rollups answer from the blob index.

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
  There is no ignore state, so `include_ignored=0` is a no-op.
  A node has an `mtime` only from [file ages](arch-git.md#file-ages), the last commit
  that changed it, when the Git can read them and the background read has finished.
- **The whole-tree index** is complete at once: `/api/catalog`, `/api/rollup`, the type
  rows and `summary` on `/api/tree`, and `/api/index/progress`, `/api/index/meta`, and
  `/api/capabilities` answer from the recursive blob index with no watcher.
  An incomplete size tally omits `summary` and the rollup rather than answering zero.
  `types` and `min_size` filter as on a folder, using the same bounded compound-tail
  logical extension. Group by works by file type: `group_by=type` answers each display
  group’s tree from the same blob index, and `group=type:<id>` lists one group’s tree.
  A group’s `size` is null when its blob sizes are incomplete, and its `files` too when
  the index is truncated.
  `group_by=age`, `group=age:…`, and the recency filter read the times of
  [file ages](arch-git.md#file-ages), cut at one instant per request, and a file with no
  time is in the `undated` group alone and in no window.
  Where the Git cannot date a revision, `recency` is false
  (`GitRevisionSubject.capabilities`) and they answer `unsupported_for_subject` (409),
  as `/api/recent` does, and the page offers neither.
- **A tree** answered by `/api/file` is folder chrome with recursive tallies.
  A direct-child README mounts Overview, and a complete size tally mounts the treemap.
- **A blob** answered by `/api/file` chooses its kind from its name’s last extension, as
  a folder’s file does.
  It carries no compressed identity, since blobs are stored bytes with no gzip smudge.
  Markdown carries parsed `frontmatter`, text keeps the folder’s first-window and
  highlight bound, and an image is image chrome with `/raw` serving the stored bytes.
  LFS pointers stay pointer bytes.
- **Rendered Markdown:** a pin always runs under the untrusted profile, so
  `/api/kpress/render` renders a blob in the server’s Markdown child
  (`diff/markdown_projection_worker.py`), never on a server thread, with fenced code
  plain and the HTML reduced to the inert allowlist there.
  A served pin starts the child as its server’s lifespan opens, so its first document
  does not wait for the child to start.
  A render past the child’s deadline stops the child and answers `422` with the code
  `render_deadline`; the refusal is kept by the blob’s object ID for `_VERDICT_TTL_S`,
  among at most `_MAX_VERDICTS` kept, so a reload within it is refused without rendering
  again. How the child is shared with the other renders and the diff projections is in
  that module’s docstring (“One child for both jobs”). The page then shows the file’s
  source with one line saying why, in the Document tab and in the folder Overview’s
  README panel alike.
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
`POST /api/source/link` switches it the same way for a link into the served repository,
which the macOS app sends for every such link
([GitHub Links](arch-macos-app.md#github-links)): a branch, folder, file, or the
repository itself is served at the revision the link names before the window goes to its
address, and a pull request or a commit, each a page of its own, switches nothing.

`GET /api/source/refs` lists what a switch chooses among, and a branch that is the head
of a pull request lists it on its row: `pulls`, open first and then newest first, from
what the repository’s provider has cached (`ref_pulls_for` in `cache/providers.py`), and
a filter that matches a pull request’s number or title lists its branch too.
The route never fetches and never waits for the provider’s service.
Its envelope says, in `pull_requests`, whether the provider’s cache holds the pull
requests yet and whether a job is filling it, so the page asks again while one is; the
answer is kept under the cache’s revision as well as the refs’ state, so a page that
asks on every keystroke runs no Git and reads no row.
A tag list, and a subject no provider has pull requests for, say `null`. Only a branch
of the repository itself has a pull request: a fork’s branch of the same name is another
branch, and a pull request’s `refs/pull/<n>/head` is not a row, being its branch’s pull
request.

A switch, or a restarted server serving another commit, can leave a tab showing the old
pin. Reading the new pin’s files into a page labeled with the old one would mix two
revisions, so every data request from a pin’s page names its commit:

- The server writes `static/source-pin-guard.js` inline into a pin’s page, with the
  commit the page was rendered for, before any other script can fetch.
  A checkout’s working-tree page is guarded too, by another route
  ([Revisions of a Checkout](#revisions-of-a-checkout)). It wraps `fetch` so every
  same-origin `/api/` request outside `/api/source/` carries the commit in
  `x-metabrowser-pin`.
- `SourcePinGuard` in `source_routes.py` refuses a request that names another commit
  with 409 `pin_changed` and the served commit in `x-metabrowser-pin-changed`, except a
  checkout’s `/api/git/` requests, whose answers no switch changes.
  A request that names no commit, from `curl`, `metab --api`, or a plain folder’s page,
  is not checked. A repository folder’s working-tree page names the working tree the same
  way, so a tab left on either view is refused when the other is served
  ([Open Modes](arch-open-modes.md#views)). Where that page’s guard can arrive after its
  first requests, a checkout’s server also refuses a page’s own request that names
  nothing ([Revisions of a Checkout](#revisions-of-a-checkout)); a mirror’s server
  answers one, as before.
- The page announces the refusal as a `metabrowser:pin-changed` event, and the freshness
  row offers a reload.
  A switch made elsewhere changes nothing under a reader who is looking at the page.
  A pin on a branch or tag that a refresh moved is different: the server follows the
  ref, and the page goes with it to the same address
  ([Following a Branch](arch-mirror-acquisition-and-refresh.md#following-a-branch)).
- The page that makes a switch is left behind too, from the moment it asks the pin route
  until it has gone, so its guarded requests wait out the switch (`createSwitchHold` in
  `source-pin-guard.js`): they go as soon as the switch is refused or changes nothing,
  and are held while the page goes.
  A page the back/forward cache shows again sends them at once: they are answered when
  the server serves that page’s subject again, and otherwise the history guard reloads
  the page. The hold ends `SWITCH_HOLD_MS` after the ask in any case, for a pin route
  that does not answer or a navigation the reader stopped; after a stopped navigation
  the requests are refused and the page offers a reload.
  A request whose signal aborts while it is held settles at once and is not sent.

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
pull request’s Changes and Docs while the diff shows the pull request’s head.
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
[Open Modes](arch-open-modes.md#pull-requests-in-a-repository-folder) designs what
replaces that: the pull request’s head as a revision view in the repository folder, with
the working-tree copy a separate, labelled action.
The old side has no control: a parent is a bare commit, and a merge base is on no
branch. Only a regular file’s side gets a control, since a submodule’s side is another
repository’s commit and a symbolic link’s would open its target.

The pin is server-wide, so a switch from one tab moves every tab’s; a tab learns it when
a data request is refused (`metabrowser:pin-changed`). A mounted diff then turns each
link into the button that switches back, since the same `/view/` address now opens the
other pin; its rendered Markdown’s links to files of the head open those files at the
head on github.com instead, and each GitHub link it opened in place is the link the text
wrote again (`closeHeadLinks` in `builtin_plugins/diff/diff-markdown.js`). A switch and
the navigation after it are two steps, because a `/view/` address names no revision;
that is a limit of this design, not something View on branch adds.
`builtin_plugins/diff/diff-view-file.js` holds the rules in its header, and the parity
rows `diff.view-file` and `diff.view-file-sides` pin them.

## Revisions of a Checkout

A folder that is a repository’s root can show any branch or tag of its checkout as a
mirror shows one, a pinned revision read from Git objects, while the working tree, which
is what a folder opens on, stays a separate choice.
The checked-out branch, chosen as a ref, shows its last commit, not the working tree.
This section is the mechanism.
Which modes exist, what each shows, and why is [Open Modes](arch-open-modes.md).

- **Which folders.** The chooser follows the open root: it is offered when the served
  root is a repository’s root, by the discovery behind the
  [exact-root gate](arch-git.md#discovery-and-the-exact-root-gate), which is also what
  draws the Commits tab.
  `checkout_revisions` in `checkout_revisions.py` offers it from the root’s `.git`
  entry, with no Git process, and the first listing or switch asks Git.
  A “no” is not kept, so a repository made in a served folder gets its chooser on the
  next load, as it gets its Commits tab.
  Any other root answers `unsupported_for_subject`, and so does a `.git` entry Git
  refuses, a hollow one or a repository of another owner: the page then removes the row
  it was drawn, as discovery removes Commits.
- **Which directory.** The Git directory read is the one Git names for the root,
  `rev-parse --git-common-dir`, which is a linked worktree’s main repository and a
  submodule’s directory under its superproject.
  The `.git` pointer is never parsed a second time, since a second parser can disagree
  with Git’s and `--git-dir` skips Git’s ownership check.
- **Which Git.** One the acquisition floor admits (`require_acquisition_git` in
  `git/process.py`), since `GIT_NO_LAZY_FETCH` is all that keeps a partial clone’s read
  from fetching into the reader’s `.git`, and a mirror’s store has no promisor remote
  where a checkout can.
  An older Git answers 409 `unsupported_git` with the release needed
  (`CheckoutGitUnsupportedError`), the panel shows those words, `--ref` fails the start
  with them, and the working tree is served as before.
  A partial clone, one whose configuration names a promisor remote, needs a Git from
  `PARTIAL_CLONE_GIT_MINIMUM` on: before it the variable refuses the fetch and then ends
  the process at the first missing object, so a revision could not even list its tree.
  An admitted Git older than that is refused for a partial clone in the same way, and
  asks nothing more of an ordinary checkout.
- **Listing.** `GET /api/source/refs` answers the mirror’s envelope from one
  `for-each-ref` over the checkout’s Git directory, the common one of a linked worktree.
  `RefNamespaces` in `cache/resolve.py` says where each kind is kept: a mirror’s
  branches are its origin’s under `refs/remotes/origin/`, a checkout’s are
  `refs/heads/`, and its remote-tracking branches are a third list, `kind=remote`.
  `kinds` names the lists a subject has, in the order of the chooser’s tabs: a
  checkout’s begin with `working_tree`, which lists no ref.
  `working_tree` is null for a mirror and otherwise says whether the working tree is
  served, which branch `HEAD` is on and which commit it is at, and the folder’s `name`
  and `location`, as the page names the folder, and a row’s `checked_out` marks that
  branch. `HEAD` is read from the checkout’s own files as each listing is made
  (`checked_out_head`), not from the repository identity `repo_info` keeps for a few
  seconds, and a kept identity those files contradict is dropped, so a listing asked for
  the moment a page hears `HEAD` moved names the branch just checked out.
  `kind=working_tree` answers `working_tree` alone and runs no Git: it is what the
  chooser’s Working tree tab shows and what a page asks each time its watch on
  `HEAD_WATCH_PATH` says `HEAD` moved
  ([File Watches](arch-live-delivery.md#file-watches)). The listing groups primary and
  known default branches first and sorts each group by committer date, newest first,
  then by name. Tags use the same date and name ordering.
  The memo keys the answer on the checkout’s ref state and the branch `HEAD` is on, as a
  mirror’s is on its store’s. Each row has its commit and `committed_at`, the committer
  date a row’s age is read from: a tag’s is its commit’s, by `for-each-ref`’s
  `*committerdate`, in the same one process.
  The page shortens the commit as every line names one (`shortCommit` in
  `static/formatters.js`), and keeps the folder’s `name` whole at the end of its
  `location`.
- **Showing one.** `POST /api/source/pin` resolves a selection in the checkout’s refs
  with the mirror’s resolver, a branch, then a tag, then a remote-tracking branch, then
  a commit ID, never revision syntax, and `replace_owned_subject` attaches a
  `GitRevisionSubject` over the checkout’s Git directory in the folder’s place.
  The selector names a row by its full ref.
  Nothing is fetched for a selection the checkout lacks.
  The folder’s inventory and watcher are not closed, so they are current when the
  working tree is served again.
- **The Commits tab shows the revision.** The chooser heads the Files and Commits tabs
  alike, and the history routes, `/api/git/repo`, `/api/git/refs`, `/api/git/summary`,
  and `/api/git/log`, read the revision’s store target as a commit’s page and its diffs
  do (`session_git_location` in `git/routes.py`), under the policies below: its commit’s
  ancestry, or with `scope=all` every ref of the Git directory the revision is read
  from, and a detached `HEAD` at the commit.
  That directory is the checkout’s, except for an origin branch or tag read from the
  origin’s store (`read_from` `origin`, set in `CheckoutRevisions.switch_pin`, as
  [Open Modes](arch-open-modes.md) says when one is), whose `scope=all` lists only the
  store’s refs: the origin’s branches and tags, without the checkout’s own branches.
  A mirror’s Commits tab walks its pin the same way.
  Since every one of these answers depends on the revision served, the guard refuses a
  page’s `/api/git/` requests that name a revision no longer served, as it refuses its
  tree’s, and the page offers to reload.
- **Returning.** `{"working_tree": true}` on the same route calls
  `restore_filesystem_subject`, which attaches the folder under a new generation and
  then closes the revision’s batch readers.
  A branch never returns to it, the checked-out one included.
- **From a terminal.** `metab PATH --ref NAME` opens the folder on a revision:
  `open_on_ref` tells the next application lifespan, and `lifespan_checkout` makes the
  pin route’s own switch as it starts.
  Serving, `--api`, `--show`, and `--check-api` all run that lifespan, so each reads a
  checkout’s revision by the routes a page does.
  A ref the checkout lacks, or a root with no checkout, fails the start with a message
  that names no path (`fail_subject_open`).
- **Never written.** A revision’s target is the checkout’s Git directory with no
  worktree, read under the store policies of
  [the process boundary](arch-git.md#the-process-boundary): no optional lock, and
  `GIT_NO_LAZY_FETCH=1`, so a partial clone’s missing object is `object_unavailable` and
  is not fetched into the reader’s `.git`. Those policies isolate the reader’s user and
  system configuration, and not the checkout’s local one, which can name a diff driver
  and select it from its own `info/attributes` or a local `core.attributesFile`. So
  every `diff` and `show` at a store target says `--no-textconv --no-ext-diff`
  (`GitLocation.diff_driver_args`): no driver runs, and `cachetextconv` writes no ref.
  That configuration can also set `log.showSignature`, under which `log` and `show` run
  the program `gpg.program` names, so every command at a `GitLocation` sets
  `log.showSignature=false` (`GIT_NO_SIGNATURE_ARGS`). A superproject’s
  `diff.submodule=diff` would diff a moved submodule in a child Git with the submodule’s
  own drivers, so every command at a store target sets `diff.submodule=short`
  (`GIT_NO_SUBMODULE_DIFF_ARGS`). It also sets `format.pretty=medium`,
  `core.fsmonitor=false`, and `core.hooksPath` at the null device, so no format,
  fsmonitor, or hook the checkout names runs either.
  `spawn_git_process` refuses a store read that lacks the options it needs, and the
  argument shapes known to start a configured program
  (`_require_no_configured_program`), so a later read cannot forget them;
  [the process boundary](arch-git.md#the-process-boundary) lists the shapes and what the
  check does not see. `tests/test_checkout_revisions.py` compares every entry under the
  checkout, `.git` included, with each file’s inode and modification time, across a
  session of trees, files, history, commit views, and diffs, with an edited, a staged,
  and an untracked file in the fixture, and with a hostile configuration, a driver and a
  signature program, planted each of those ways.
  It repeats the session in a linked worktree, in a submodule served as the root, and in
  a superproject whose commit moves its submodule.
  A blobless clone asked for a commit and a comparison whose blobs it lacks answers
  `object_unavailable` for each, and no pack arrives.
- **Trust.** A pinned revision is never trusted, a mirror’s or a checkout’s, whatever
  the process’s block: `capabilities_for` in `capabilities.py` answers the untrusted
  block for a pin, and each route takes it for the subject it resolved before anything
  is awaited. The routes of `git/content_routes.py` are handed their pin and use the
  untrusted block outright; the shell decides its policy from the subject it read at the
  top of the request; and `/raw` marks the request when its handler answers a pin, so
  the trust headers are a pin’s whatever was served when the request arrived.
  A folder’s server therefore needs no flag to show a revision, and its working tree’s
  requests get the folder’s own block.
- **Addresses.** A folder names an entry by its path and a revision by a `GitPath` wire.
  A switch’s `view_href` translates the page’s address to the other side, and
  `crossed_view_href` in `source_routes.py` does the same for a `/view/` address that
  arrives while the other is served, from a tab, a history entry, or a bookmark: the
  shell redirects it to the same names on the served side when they exist there.
- **What it is called.** `/api/source/status` reports a revision of a checkout as a pin
  with no origin, named by the folder, with `location` the checkout’s path and nothing
  refreshable. `/api/identity` keeps `kind: folder`, since the mode is how the root was
  opened, and adds `@<ref>` to `full_name`. A remote-tracking branch keeps its remote,
  `origin/topic` (`checkout_ref_name`).
- **The guard.** The page of a checkout’s working tree names `working-tree` where a
  pin’s page names its commit (`WORKING_TREE_PIN`), and is refused with `pin_changed`
  while a revision is served; a plain folder’s page still names nothing.
  That page takes `source-pin-guard.js` with the selector’s on-demand bundle and not
  inline, so until it arrives its requests name nothing.
  The server covers that moment: while a checkout’s revision is served, a page’s own
  `fetch` that names no commit, which a browser marks `Sec-Fetch-Site: same-origin` with
  `Sec-Fetch-Dest: empty`, cannot be the pin’s page and is refused the same way.
  `curl` and `metab --api` send neither header and are answered.
  The refusal is a checkout’s server’s alone: a mirror has no working-tree page, its
  pages carry the guard inline, and a request there that names nothing, a plugin’s
  worker’s or a preload’s, is answered as it was.
  A checkout’s page has no freshness row, so its selector makes the offer to reload in
  one of its own at the foot of the pane, where every tab shows it: the Pulls tab’s
  requests and a comparison’s are refused as the Files tab’s are, and the selector is in
  the Files toolbar, which the other tabs hide.
- **The origin’s branches and tags** are the exception to reading in place: they are
  listed and served from the store Metabrowser keeps beside the checkout, which borrows
  the checkout’s objects, and such a pin is fetched and followed as a mirror’s is
  ([Origin Branches in a Repository Folder](arch-open-modes.md#origin-branches-in-a-repository-folder)).
  `CheckoutRevisions.serves` answers for a revision of either, so the page of one is
  still the folder’s.
- **Revision reads.** The checkout serves a pinned commit of its own directly from its
  own Git objects.
- **Following a branch.** A revision served under one of the checkout’s own branches,
  remote-tracking branches, or tags (`FOLLOWED_CHECKOUT_REFS` in
  `checkout_revisions.py`) reads that ref, not one commit of it, as a mirror’s pin does
  ([Following a Branch](arch-mirror-acquisition-and-refresh.md#following-a-branch)), so
  it moves when the reader’s commit or the reader’s own fetch moves the ref.
  Only a selection that names the ref, as `ref` or as `under`, follows it.
  A commit opened by its ID alone stays: it is served under no ref, or under the ref
  last served while it is that ref’s tip, so that the selector names the ref, and then
  too `follows` is false.
  Asking for the revision already served the other way changes only that.
  The working tree is no revision.
  - **The move is read, never fetched.** A visible page makes its own ask,
    `POST /api/source/refresh` with `{"for": "page"}`, as often as its status says in
    `probe_every_s` (`CHECKOUT_REFS_POLL_S`), and `CheckoutRevisions.observe` answers
    it: it names the checkout’s
    [ref state](arch-git.md#answers-kept-under-the-refs-state), one `stat` per ref file
    and no Git process, and reads the ref with Git only when that state is not the one
    it was last read under.
    The ask names the state before it takes the locks a switch is made under, and takes
    them only when the state changed; an ask within `CHECKOUT_REFS_FLOOR_S` of the last
    reading, another visible page’s, is answered from memory.
    The measurements of what an ask costs, and the reasoning that chose a poll by the
    page over a watch of the Git directory, are beside the constant.
  - **The server follows** with the mirror’s own step, `follow_served_ref` in
    `mirror_refresh.py`: under the locks a switch is made under, it opens the ref’s new
    commit and serves it under a new generation.
    It records the new revision as the checkout’s before attaching it, as a switch does.
    A ref the reader deleted keeps its last commit served, and `latest` is then null,
    which the page’s row says: the branch no longer exists in the checkout, and the page
    shows its last commit.
  - **The page follows** as a mirror’s does: `static/source-freshness.js` sees the ref
    it was drawn for served at another commit, asks the pin route for that ref with its
    own `/view/` address, and goes where `view_href` says, the same file or folder when
    the new commit has it, or the root.
    A hidden page asks nothing, so a branch nobody is looking at is read again when its
    page is shown.
  - **The status** of such a revision has `follows` true and `latest`, the ref’s commit
    as last read in the checkout, whether or not the folder keeps a store; `refreshable`
    and the fetch fields are still the store’s alone, since nothing is fetched into a
    checkout. A folder that keeps no store answers the ask with `200` and `probed` while
    such a revision is served, and `409` otherwise, as before.
    Where it keeps one, the same ask is also the store’s, which fetches a store older
    than `FRESHNESS_WINDOW_S`, quietly.
  - **Never written.** `tests/test_checkout_revisions.py` compares every entry under the
    checkout, `.git` included, across an ask, a follow, and the new commit’s files.
- **Pull requests.** A GitHub checkout’s Pulls tab and branch list use the same
  repository catalog on the working tree and its pinned revisions.
  Opening a pull request leaves the Files pin in place.

## How a Mirror’s Page Names Itself

A served mirror’s page is headed by its repository’s name, as a folder’s is by its own,
and every route answer stays free of cache and store paths but one field.
[What a Mirror’s Page Is Called](arch-mirror-acquisition-and-refresh.md#what-a-mirrors-page-is-called)
holds the naming rule, the exception, and the test that guards it.

## References

- [Open Modes](arch-open-modes.md)
- [Git Reading and History](arch-git.md)
- [Diff Pipeline](arch-diff-pipeline.md)
- [Repository cache](arch-repository-cache.md)
- [Mirror acquisition and refresh](arch-mirror-acquisition-and-refresh.md)
- [Views, models, and routes](arch-views-models-routes.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

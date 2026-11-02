# Review: Changes to Existing Behavior in the v0.12 Stack

**Date:** 2026-10-01

**Status:** A dated record for the user’s sign-off, not a maintained table.
It is the list of intended changes to behavior that existed in v0.11.0. The landing gate
(`mb-2g6f`) requires that list in writing, because the stack is not purely additive.
The landing decision is `mb-n2ro`; this record is evidence for it.

**Addendum, 2026-10-26.** Two rows were added after the original date, because the list
was incomplete for a reader asked to sign it.
[#268](https://github.com/jlevy/metabrowser/pull/268) landed on 2026-10-04, three days
after this record was written, and changed where the cache and configuration live, which
is a change to behavior v0.11.0 had and so belongs here; it is the new section below on
cache and configuration roots.
The landing gate’s re-run on the release head then found one more, the `/api/stream`
cursor-past-end-of-file change, which is the third row in the table of deliberate
changes with no `CHANGELOG.md` entry.
Both are marked `Run, 2026-10-26` or `Data, 2026-10-26` and were checked against `main`
at `c2d493e9`, not against the tree the rest of this record was taken from.
Two other statements the original closing paragraph makes have since been overtaken, and
are left as written rather than edited: the two regressions it declines to accept were
fixed in [#267](https://github.com/jlevy/metabrowser/pull/267), which landed, and the
browser differential it says nothing of has since reported, with no product regression
(`mb-2g6f`). Also on 2026-10-26, one row was removed from the table of deliberate
changes with no `CHANGELOG.md` entry, because the claim was false: the change it named
is documented under Fixes.
Extending that table’s search hint, so a reader could re-run the search the sentence
claims, is what exposed it.
The paragraph after the table says which row and why.
Nothing else in this record was changed.

**Addendum, 2026-11-01.** Written for the reader asked to sign this record; nothing
above or below it was changed.
[#272](https://github.com/jlevy/metabrowser/pull/272) adds `CHANGELOG.md` entries for
both rows of the table of deliberate changes with no entry: `/api/stream` under Page
lifecycle, and `--end-of-options` under Content trust.
So once #272 is on `main`, that table and the sentence above it describe the tree this
record was checked on: a search of the file for `end-of-options` and `rotated` now finds
those entries, not nothing.
The sign-off’s “a request to add entries” is answered by them, and signing accepts the
two changes as those entries state them.
The `--end-of-options` entry leaves out the row’s “No response differed”, but the claim
was checked again and stands.
Of the 157 rows the re-run’s data differential reports as deliberate with no entry, 149
are this change, and all of their 702 elements are the Git command line the harness
records (`fx.calls`), not a route’s answer or a command’s output.
This record’s statement that the `/api/plugin/diff/comparison` entry does not say other
requests are refused was also checked, on `c934a0b4`, and was true: the file’s only
mention of `base_policy` was the sentence that the route honors `merge_base`. #272 adds
the refusal to that entry, as the code in `builtin_plugins/diff/sidekick.py` has it, and
running both cases answered 400 `diff_comparison`. One more statement has been overtaken
and is left as written: A Known Defect says the fix is #262, held out of the stack.
#268 carries the fix and #262 was closed unmerged, and `mb-tdmd` is closed, with Back in
Safari and Firefox checked under `mb-etqi`. One row needs reading more widely than it
states. The row on `/api/plugin/structured/parsed` for a file it cannot open names
0.11.0’s answer as a 200 with a `PermissionError`, which was run at the default limit.
For an uncompressed file larger than `STRUCTURED_PARSE_MAX_BYTES`, as any such file with
content is at a limit of zero, 0.11.0 did not open it and answered `truncated`; it now
answers the same 404 `content_unavailable`. Run on 2026-11-01 at limits of 0 and 1
against v0.11.0’s source.
Signing that row accepts this case too, and `CHANGELOG.md` now states it.
This list also has no row for a compressed patch, so that change is stated here for
signing.
`/api/plugin/diff/document` on a `.patch.gz` now reads the patch the file holds,
where v0.11.0 parsed the compressed bytes and answered 200 with 0 files for every
`.patch.gz`, a valid one included.
A compressed file whose stream cannot be decoded now answers 404 `diff_document`, “This
file is not available.”, where v0.11.0 answered that same 200 with 0 files.
With the damage in the first 512 KiB that `/api/file` reads, both builds show the file
as bytes.
With the damage past that, as in an 8.5 MB patch whose gzip is cut at 80%, both
say `kind: diff`, so the Diff view now shows that message where v0.11.0 showed an empty
change set. Run on 2026-11-01 against v0.11.0’s source, except the view’s message, which
is read from the plugin’s code.
`CHANGELOG.md` states it under Fixes: “A compressed patch is read as the patch it
holds.”

**Addendum, 2026-11-02.** Written for the reader asked to sign this record, because the
list was incomplete for that reader again.
[Stack 278](https://github.com/jlevy/metabrowser/stack/278) lands above `c934a0b4`, the
tree the addendum above checked, and
[#275](https://github.com/jlevy/metabrowser/pull/275) in it changes what a regular
folder’s pages and routes do.
`CHANGELOG.md` states those changes, and the new section
[Stack 278 on a Regular Folder](#stack-278-on-a-regular-folder) lists them here for
signing, with one more bullet each under How Each Claim Was Checked and What Sign-Off
Means. Nothing else in this record was changed.

**Scope:** What a user or a plugin author sees differently on something v0.11.0 already
did: a regular folder served or inspected, the CLI, the Plugin SDK, and the package’s
requirements. New features are listed only where they show on a regular folder.
`CHANGELOG.md` holds the full 0.12.0 entry, and each row names the part of it that
states the change.

## How Each Claim Was Checked

The **Checked** column of each table says one of these:

- **Run:** run for this record on 2026-10-01, on #265’s tree (commit `fd029ab9`, which
  adds only documents to it) and on the installed v0.11.0 wheel, with the same folder
  and an isolated application home.
  CLI and route claims compare the two builds’ output; page claims compare the two
  builds in stock Chrome 152, headless.
- **Audit:** from the landing gate’s evidence audit, which classified every hunk the
  stack made in the tests, goldens, and fixtures that existed on v0.11.0, and ran
  v0.11.0’s goldens and test suite against the stack.
- **Data:** from the landing gate’s data differential: 20,234 comparisons of the two
  builds on regular folders, over every route v0.11.0 registers, every CLI mode and
  flag, response headers, third-party plugins, and environment handling.
  It reports no unexplained difference.
- **Changelog:** stated by `CHANGELOG.md` and not run here.
- **Run, 2026-10-26** and **Data, 2026-10-26:** the same two methods, carried out on the
  later date for the two addendum rows only, against `main` at `c2d493e9` rather than
  #265’s tree. The data differential behind them is the gate’s re-run on the release
  head: 20,310 comparisons at `--jobs 4`, which reports no unexplained product
  difference.
- **Run, 2026-11-02:** the same method, on the later date, for the section on stack 278
  only, with [#275](https://github.com/jlevy/metabrowser/pull/275)’s head at `2ca297fa`
  in place of #265’s tree.
  The folder was a scratch Git repository holding a hidden folder, a symbolic link to a
  folder, and a JSONL log.

The audit and the differential ran at #259’s head, `f62c16b1`, below #261, #263, #264,
and #265, and their reports are session files, so their substance is copied here.
Neither judged paint.
The gate’s third check, a browser differential, had not reported when this was written;
it has since run on the release head, and the addendum above says what it found.

## Breaking for Plugin Authors: Plugin SDK 0.7

| What changes | `CHANGELOG.md` entry | PR | Checked |
| --- | --- | --- | --- |
| A plugin whose manifest says `sdk_version = "0.6"` is refused when it loads. `metab --doctor --plugins-dir` exits 1 and names the fix, where v0.11.0 reported it OK | Plugin SDK: “**Breaking:** `PLUGIN_SDK_VERSION` is now `0.7`” | #237 | Run |
| A copy control a plugin or a document wrote by hand (`data-mb-copy`, `data-mb-copy-text`) does nothing, silently, unless it carries the page’s owner mark. A planted button put its text on the clipboard on v0.11.0 and leaves the clipboard alone now. The migration is `mb.ownDelegate(el)` or `mb.delegateOwnerAttribute()` | The same entry; Content trust: “The application’s document-wide handlers act only on controls the page created” | #237 | Run |
| `partialNoticeHtml`’s `action` string no longer becomes an inline `onclick`, and a hand-built `button.metabrowser-load-more` does nothing. A view that continues its own content passes `action: null` and wires its own listener | The same entry; Content trust: “The application writes no inline event handlers” | #234, #237 | Run |
| The file header’s print button has no `id="print-view-btn"` | Content trust: “The application’s document-wide handlers act only on controls the page created” | #237 | Run |
| `mb.sizeHtml(undefined)` renders nothing; `null` still renders the pending skeleton | Plugin SDK: “`mb.sizeHtml(undefined)` now renders nothing” | #216 | Run |
| The SDK’s view helpers, `renderSourceView` among them, load on demand in `plugin-sdk-views.js` and are in place before any plugin’s code runs. `ensureKindAssets(kind)` rejects when they cannot be fetched, and appends one `modulepreload` link per plugin module | Plugin SDK: “`ensureKindAssets(kind)` rejects when the SDK’s own view helpers cannot be fetched” | #254, #264 | Run for the request and the link; Changelog for the rejection |
| `renderSourceView` adds a line-number gutter beside the code, and writes LF where the source has CRLF or a lone CR. The text shown and the text copied are unchanged | Plugin SDK: “`renderSourceView` renders a line-number gutter” | #235, #264 | Run for the gutter; Changelog for the line endings |
| `metabrowser.plugin_api` exports more names for reading content on either kind of source; none is removed (16 names on v0.11.0, 30 now). `resolve_path`, `served_root`, and `open_content` raise on a Git pin and behave as before on a folder | Plugin SDK: “`metabrowser.plugin_api` exports the content-source boundary” and the entry after it | #216, #264 | Run for the names; Changelog for the pin |
| `metab --plugin <name>` prints `sdk_version: 0.7`, and for `markdown` lists three more assets: `inert-render.js`, `inert-toc.js`, and `place-rendered.js` | Content trust: “Markdown from an untrusted source renders inert” | #234, #254 | Run |
| The private `app.js` global `copyContent` is gone. It had no caller and was never part of the SDK | None; the audit traced it to a commit that says so | #238 | Run |

## Breaking for Stored State: Cache and Configuration Roots

Added 2026-10-26. This landed in [#268](https://github.com/jlevy/metabrowser/pull/268)
on 2026-10-04, after the rest of this record was written.

| What changes | `CHANGELOG.md` entry | PR | Checked |
| --- | --- | --- | --- |
| **`METABROWSER_HOME` is no longer read, and neither is the old single-home layout.** Cache and configuration are separate XDG locations: `~/.cache/metabrowser` and `~/.config/metabrowser/config.yml`. Anyone who set `METABROWSER_HOME` to move Metabrowser’s state is silently served from the default locations instead, so the state they pointed at is not found. Existing files are left untouched, so nothing is destroyed and the old directory can be deleted by hand once its contents are no longer wanted | “**Breaking:** Cache and configuration now use separate XDG locations”, the first entry of 0.12.0 | #268 | Run, 2026-10-26 |
| `--cache-dir` / `METABROWSER_CACHE_DIR` and `--config-dir` / `METABROWSER_CONFIG_DIR` name an exact directory each, and override the XDG variables. They are the migration for a `METABROWSER_HOME` user, and the two new flags in `metab --help`, which gained three in all and lost none, 41 to 44 | The same entry | #268 | Run, 2026-10-26 |
| Serving or inspecting a plain folder still creates neither directory: a missing cache home is reported `absent` rather than created. Checked with an isolated `--cache-dir` and `--config-dir` on a folder, with neither `git` nor `gh` on `PATH`; both were left uncreated | Repository cache: “New read-only routes”, which says a missing home is reported `absent` rather than created | #140, #268 | Run, 2026-10-26 |

## Changed Meaning of Existing Flags

| What changes | `CHANGELOG.md` entry | PR | Checked |
| --- | --- | --- | --- |
| `--untrusted` and `--no-active-content`, and `METAB_UNTRUSTED=1` and `METAB_ACTIVE_CONTENT=0`, on a folder now render Markdown inert: `/api/kpress/render` answers `inert: true` and markup without class attributes, code blocks lose highlighting, an outside image becomes a link, and wiki links and embeds show as text. In v0.11.0 those flags only dropped `allow-scripts` from the `/raw` sandbox and withdrew the HTML Preview tab | Content trust: “**Changed for a folder on disk:**” | #234 | Run for the render; Changelog for the details |
| Under those flags the page carries a Content-Security-Policy and `X-Frame-Options: DENY`, and `/raw` refuses a browsed file requested as a script (403 where v0.11.0 answered 200) and sends JavaScript and CSS as `text/plain` | Content trust: “With active content off the application page carries a Content-Security-Policy” | #234 | Run for the headers and the 403; Changelog for `text/plain` |
| A folder served with neither flag has no policy header on either build and renders as before | The same entry | #234 | Run |

## CLI Differences

| What changes | `CHANGELOG.md` entry | PR | Checked |
| --- | --- | --- | --- |
| `metab ""` is refused, `invalid ROOT (empty)`, exit 1. v0.11.0 read it as the current directory | Repository cache: “An argument that names an existing path is that path, whatever it resembles” | #226, #249 | Run |
| An argument that starts with `scheme://` is always a source, even when a folder of that spelling exists: `metab https://host/x` no longer serves `https:/host/x`. Write the path with one slash, or as `./https://host/x`. A folder named `file:notes`, `a::b`, or `me@host:dir` is still served | The same entry | #249 | Run |
| A source-like argument that names nothing on disk is classified, where v0.11.0 said it was not a directory: `nosuch::thing` is `invalid ROOT (remote_helper_syntax)`, and `me@host:dir` is read as an ssh Git source | Repository cache: “The CLI classifies `ROOT` as a string before any path is constructed” | #217 | Run |
| A server whose start-up fails exits 1 with `Error: the server did not start; the log above says why`. v0.11.0 exited 0 | Repository cache: “`metab ROOT` exits non-zero when the server’s startup fails” | #229 | Run |
| `metab --doctor` counts 11 plugins where v0.11.0 counted 10, and also validates the packaged cache record schemas. The healthy sentence is the same. It takes about 250 ms longer, 1.78x the work in instructions retired | Repository cache: “`metab --doctor` also checks the packaged cache record schemas” | #246, #264 | Run for the count; the time is `mb-67s1`’s measurement |
| `metab --help`: `ROOT` is typed `TEXT`, not `PATH`, and describes Git sources; a `--no-serve` row; `--untrusted` and `--no-active-content` reworded; two `file://` examples | Repository cache: “The CLI classifies `ROOT` as a string”; Content trust: the Content-Security-Policy entry’s last sentence | #217, #249 | Run |
| `/api/plugin/structured/parsed` for a file it cannot open answers 404 `content_unavailable` and names the served path. v0.11.0 answered 200 with a `PermissionError` that spelled the file’s absolute path | Fixes: “`/api/plugin/structured/parsed` no longer answers with a path on the host” | #264 | Run |
| `/api/plugin/diff/comparison` validates `base_policy`: a value other than `direct` or `merge_base`, or one given with a single revision, answers 400. v0.11.0 ignored the parameter. The entry says the route honors `merge_base`; it does not say that other requests are now refused | GitHub URLs and HTTPS, under “Pull-request data”: “`/api/plugin/diff/comparison` now honors `base_policy=merge_base`” | #232 | Run |
| `/api/git/commit/<id>` for an unknown commit: the 404 gains `"code": "commit_not_found"`. Status and message are unchanged | GitHub URLs and HTTPS: “A served page opened at `/commit/<id>`” | #249 | Audit |

Two deliberate changes have no `CHANGELOG.md` entry, which a search of the file for
`end-of-options` and `rotated` confirms, each returning nothing:

| What changes | PR | Checked |
| --- | --- | --- |
| The comparison adapter runs `git rev-parse --verify --end-of-options <rev>^{commit}`, so a revision that begins with `-` is an argument and not an option. No response differed because of it | #216 | Data |
| `GET /api/stream` asked to resume past the end of the file now ends the stream instead of continuing it. v0.11.0 clamped the cursor to the file’s size (`read_cursor = min(read_cursor, st_size)`) and kept streaming, so the client saw `: heartbeat`; it now sends `event: closed` with `data: {"reason": "rotated"}` and stops (`src/metabrowser/sse.py`). The new answer is the correct one — a cursor past the end means the file was rotated or truncated under the reader, and clamping resumes at the wrong offset — and it is the server side of the entry “A live log deleted or truncated while the page was away stops showing as live on return.” That entry states what the page does, not what the route answers, and a plugin or script reading `/api/stream` directly sees the difference | #268 | Data, 2026-10-26 |

A third row stood here until 2026-10-26 and was wrong.
It said `/api/plugin/diff/document` answering a typed 404 for a file it cannot open had
no `CHANGELOG.md` entry.
It has one, under Fixes, whose last sentence is “They now answer 404 `diff_document` or
`diff_children` and name the served path” and which opens by saying that
`/api/plugin/diff/document` and `/api/plugin/diff/children` no longer answer with a path
on the host either. It describes that change exactly.
The row is removed rather than corrected in place, because the change is documented and
so belongs in no list of undocumented ones.
The likely history is that the entry was written after this record was, in the changelog
work on [#264](https://github.com/jlevy/metabrowser/pull/264).

One more is cosmetic: `--show` loads the dotenv chain at two more points, so a malformed
`.env` prints python-dotenv’s warning more often (Data).

## Visible Page Differences on a Regular Folder

| What changes | `CHANGELOG.md` entry | PR | Checked |
| --- | --- | --- | --- |
| A text or source file’s Source view shows line numbers, with `#L` anchors and keyboard anchors | Source views: “A text or source file’s Source view shows line numbers” | #235, #239 | Run |
| An address with a line anchor or `?plain=1` opens a file’s Source view. `overview.md#L3-L5` opened the Document view on v0.11.0 | Source views: “An address with a line anchor, or with GitHub’s `?plain=1`” | #239 | Run |
| The preview pane scrolls inside a new non-scrolling `div.preview-frame`, so the table-of-contents button stays in place in a narrow pane. It used to scroll away | Fixes: “In a pane too narrow for the Contents rail” | #243 | Run for the frame |
| Copy, Load more, the address crumbs, the parent-folder button, and print carry the page’s owner mark and act only with it, and the page writes no inline event handler. A reader sees no difference | Content trust: the two entries named under Plugin SDK 0.7 | #234, #237 | Run |
| The Git panel no longer rebuilds a different history under the rows on screen when refs move. It keeps the rows and offers **Reload history** | Repository cache: “The Git panel no longer rebuilds a different history” | #230 | Changelog |
| A filename holding a backslash lists and opens, as `%5C` in addresses. On v0.11.0 one such file failed the folder’s whole index | Fixes: “A served folder holding a filename with a backslash” and the entry after it | #237, #240 | Data |

## New Things That Appear on Every Folder

| What appears | `CHANGELOG.md` entry | PR | Checked |
| --- | --- | --- | --- |
| A built-in `github` plugin: a row in `metab --plugins`, a name in the `Plugins:` line a server prints, and one more in `--doctor`’s count. On a folder `/api/plugin/github/pull` answers `state: "absent"` and `pull-markdown?part=body` answers 409 | GitHub URLs and HTTPS: “The pull-request page and its routes are a new built-in plugin, `github`” | #232, #264 | Run |
| Twelve more registered routes, 36 to 48, none removed. On a folder `/api/source/refs`, `refresh`, and `pin` answer 409 `unsupported_for_subject`; `/api/cache/layout` answers 200 with the home `absent` and creates nothing. Each answered 404 on v0.11.0 | Repository cache: the entries that begin “New read-only routes”, “New `GET /api/source/status`”, “New `POST /api/source/pin`” | #140, #229, #230, #236 | Run for the counts and the answers; Audit for none removed |
| `/api/source/status` on a folder answers 200 with `subject: "attached_filesystem"`, and `name`, `origin`, and `location` each `null` | GitHub URLs and HTTPS: “A page served from a mirror is headed by the repository’s name” | #229, #263 | Run |
| No application home is created by serving or inspecting a folder. Every run for this record used a scratch home, and none existed afterwards | Repository cache: “New read-only routes”, which says a missing home is reported `absent` rather than created | #140 | Run |

## Stack 278 on a Regular Folder

Added 2026-11-02. [Stack 278](https://github.com/jlevy/metabrowser/stack/278) is
[#272](https://github.com/jlevy/metabrowser/pull/272) to
[#277](https://github.com/jlevy/metabrowser/pull/277), and every row here is
[#275](https://github.com/jlevy/metabrowser/pull/275), as its head stands at `2ca297fa`,
after the reviews of that pull request were addressed.
Each entry named is under Fixes in `CHANGELOG.md`’s 0.12.0 section.

| What changes | `CHANGELOG.md` entry | PR | Checked |
| --- | --- | --- | --- |
| A folder the inventory leaves out, a hidden one such as `/view/.github/` or a symbolic link to a folder, says why it has no totals. File Overview says “Metabrowser does not index hidden folders, so this one has no file totals.”, or for a link “Metabrowser does not follow symbolic links when it indexes, so this folder has no file totals here.”, and the header shows no tally. v0.11.0 said “Could not load file types.”, kept the totals’ skeleton, and left the header’s tally pending forever. The Treemap tab says “Treemap unavailable.” without the reason (`mb-o12l`, open), where v0.11.0 kept its skeleton. The page and any README show on both | “A folder the inventory leaves out says why it has no totals.” | [#275](https://github.com/jlevy/metabrowser/pull/275) | Run, 2026-11-02 |
| `/api/file` on such a folder gains `dir.not_indexed`, `hidden` or `symlink`. It still answers 200, the rest of the hidden folder’s answer is the same as v0.11.0’s, and another folder’s answer is unchanged | The same entry | [#275](https://github.com/jlevy/metabrowser/pull/275) | Run, 2026-11-02 |
| The Treemap gives up its skeleton when no rollup is coming. A failed or refused `/api/rollup`, or an index that finished without the folder, shows “Treemap unavailable.”, where v0.11.0 kept the skeleton. **A refresh that fails during a scan also says “Treemap unavailable.”**, until the next answer, and an answer that the scan is running brings the skeleton back; a map already drawn stays through a failed refresh. File Overview keeps its failure’s message when Files, Bytes, or Show ignored changes, and the totals’ skeleton stops with it | “File Overview and Treemap no longer keep a loading skeleton when the rollup cannot supply one.” | [#275](https://github.com/jlevy/metabrowser/pull/275) | Run, 2026-11-02 for the first failure and a failed refresh on both builds, with `/api/rollup` failed or forged in the browser, because no real scan’s request was made to fail; the map that stays is read from the plugin’s code; Changelog for the rest |
| File Overview’s type table has a visible `<caption>` on every folder, naming what its shares count, such as “Share of Total (6 files)” or “Share of Files (536 files)”. It follows Show ignored and the measure, and is the table’s accessible caption. v0.11.0 had none | “File Overview’s type distribution says which population it counts” | [#275](https://github.com/jlevy/metabrowser/pull/275) | Run, 2026-11-02 for the caption; Changelog for what it follows |
| A JSONL log’s event rows are keyboard controls. Each header has `role="button"`, a tab stop, and `aria-expanded`, and Enter or Space opens and closes it. A click opens it as on v0.11.0, and now also takes focus to the row. On v0.11.0 a header had none of these, Enter did nothing, and a click left focus on the preview pane | “A JSONL log’s event rows answer the keyboard.” | [#275](https://github.com/jlevy/metabrowser/pull/275) | Run, 2026-11-02 for a click and Enter; Changelog for Space |
| Back or Forward onto a `/commit/` entry shows the commit. With a file opened in-page over a commit, v0.11.0 changed the address and left the file showing | “Back or Forward onto a `/commit/` entry shows the commit.” | [#275](https://github.com/jlevy/metabrowser/pull/275) | Run, 2026-11-02 for Back; Changelog for Forward |
| `/api/git/commit/<rev>` for a short ID, or a ref name with no slash, gains `"code": "revision_not_full"` beside the same 400 and `error`. A `/commit/` address with one says “Full commit ID needed” and that a commit’s address uses its full 40- or 64-character lowercase ID, where v0.11.0 said “Could not load this commit.” | “A `/commit/` address with a short commit ID, or a ref name with no slash in it” | [#275](https://github.com/jlevy/metabrowser/pull/275) | Run, 2026-11-02 |
| On an index stopped at its 500,000-file cap, `/api/rollup` answers `index_status: "truncated"` and `truncated: true`, where v0.11.0 answered `idle` and `false`, and `/api/tree` and `/api/recent` answer `tally_cache_status: "truncated"`, where v0.11.0 answered `idle`. So the page now says so: “File list incomplete.” in the file list, “Summary is partial” in File Overview, and Treemap draws the indexed files under “Index capped at 500,000 files”. v0.11.0 showed none of these, and its Treemap kept the skeleton | “A tree that reaches the 500,000-file cap now says so.” | [#275](https://github.com/jlevy/metabrowser/pull/275) | Run, 2026-11-02, on both builds with `INVENTORY_MAX_FILES` set to 3 in the process |
| A tree row replaced during the tooltip’s 300 ms delay, as when its folder re-renders, no longer puts a tooltip at the window’s top-left corner until the next hover | “A tree row replaced during the tooltip’s 300 ms delay” | [#275](https://github.com/jlevy/metabrowser/pull/275) | Changelog |

One fault showed in the capped run, which is a defect and not an intended change.
At `2ca297fa` the file list’s note goes on “Metabrowser stopped after 3 files files”,
because the sentence writes the noun after a count that already has it (`mb-kp7q`,
open). v0.11.0 has the same code but never reached it on a capped index.

[#277](https://github.com/jlevy/metabrowser/pull/277) adds no row, because it restores
what v0.11.0 does. A served folder’s first diff requests the same six diff modules
v0.11.0 requests, by name and order, where `c934a0b4` requests seven.
Under `--untrusted` and `--no-active-content` a kept image carries `loading="lazy"`
again, so images below the fold wait for the scroll, as they do on v0.11.0 and on a
trusted folder; `c934a0b4` fetched them all on load.
Those are
[review C](https://github.com/jlevy/metabrowser/pull/277#pullrequestreview-5743891343)’s
measurements against the v0.11.0 wheel, in which `--no-active-content` was not loaded;
[#277](https://github.com/jlevy/metabrowser/pull/277)’s description holds that profile’s
counts. The other three layers add no row either, read from their diffs under `src` and
not run: [#273](https://github.com/jlevy/metabrowser/pull/273) changes the pull-request
page and how the inert layer writes a link’s scheme,
[#274](https://github.com/jlevy/metabrowser/pull/274) changes only Git-source paths, and
[#276](https://github.com/jlevy/metabrowser/pull/276) changes nothing a reader sees.

The landing gate’s three checks last ran on `c2d493e9`, so none of them has seen these
rows. They are owed again on the head that is tagged, as the
[alpha test plan](../specs/active/plan-2026-09-22-v012-alpha-testing.md) says.

## Dependencies and Minimum Tools

| What changes | `CHANGELOG.md` entry | PR | Checked |
| --- | --- | --- | --- |
| `softschema==0.8.1` is a new runtime dependency, and the minimum `frontmatter-format` rises from 0.3.0 to 0.4.0. The Python range is unchanged | Repository cache: “The cache validates the records it writes with SoftSchema” | #136 | Run, on each build’s package metadata |
| Git 2.43.7, or the patched release on a later track, is required only to acquire or refresh a URL or `file://` source. Serving a folder does not check it | Repository cache: “Acquiring or refreshing a Git source requires Git 2.43.7” | #217 | Changelog |
| `gh` 2.81.0 or newer, signed in, is required only to read pull-request data | GitHub URLs and HTTPS, under “Pull-request data” | #232 | Changelog |
| A URL or `file://` source needs a POSIX system. Serving a folder does not | Repository cache: “Opening a URL or `file://` source needs a POSIX system” | #264 | Changelog |

## Unintended Differences the Gate Found

Three were restored to v0.11.0’s behavior in #264 (`mb-y28u`), and each was run for this
record on both builds:

| Difference | Found by | State now |
| --- | --- | --- |
| Hover prefetch fetched a JSONL file with a compound name, such as `run.codex.jsonl`, where v0.11.0 skipped every `.jsonl` | The evidence audit | Restored. Hovering that row fetches nothing on either build, and hovering a `.py` row fetches it on both |
| `size` in `/api/plugin/structured/parsed` was the decoded bytes read, capped at the parse limit, where v0.11.0 answered the size on disk | The evidence audit, and the data differential independently | Restored. A 69-byte `small.json.gz` answers `size: 69` on both |
| The same route decoded strictly: a file with bytes that are not UTF-8, and a compressed file that cannot be decoded, answered differently | #264’s independent review | Restored. A Latin-1 `.json` opens as a tree with U+FFFD on both |

Two more, found by the data differential, are **not fixed** at #265. Both still
reproduced there when run for this record, and both are fixed in
[#267](https://github.com/jlevy/metabrowser/pull/267) (`mb-55tr`):

| Difference | On v0.11.0 | On the stack |
| --- | --- | --- |
| `STRUCTURED_CACHE_SIZE=0` breaks every structured view | Parses and answers 200 | Answers the degraded `plugin_error` envelope, `ValueError: value too large`, and logs a traceback |
| `/api/plugin/diff/document` for a file whose name does not end in `.patch` or `.diff`, which a third-party plugin can make the built-in `diff` kind | Parses whatever file it is given and answers 200 | Answers 404 `diff_document` |

## A Known Defect, Unchanged From v0.11.0

After about five full page loads in one tab of a served folder, the next page’s requests
wait for a connection, because each page kept for Back holds its event stream open
(`mb-tdmd`). Run for this record, ten page loads in one tab: the sixth page was ready
after 2.6 s on v0.11.0 and 2.9 s on the stack, against about 0.1 s for the others.
#262’s author measured about 57 s on v0.11.0 in the runbook’s longer walk.
A mirrored repository opens no event stream and is not affected.
The fix is [#262](https://github.com/jlevy/metabrowser/pull/262), held out of the stack
until after the landing, because its review found that it would change how a regular
page behaves on Back.

## What Sign-Off Means

Approving this list accepts, for the 0.12.0 release:

- the Plugin SDK break, with its migration in `CHANGELOG.md`;
- the cache and configuration roots moving to separate XDG locations, and
  `METABROWSER_HOME` no longer being read (added 2026-10-26);
- the stronger meaning of `--untrusted` and `--no-active-content` on a folder;
- the CLI differences above, including the slower `--doctor`;
- the two deliberate changes that have no `CHANGELOG.md` entry, or a request to add
  entries for them;
- the page differences and the new routes and plugin row on every folder;
- the differences in the section on stack 278 (added 2026-11-02).

It does not accept the two regressions still being fixed, and it says nothing of the
browser differential.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

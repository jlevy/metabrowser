# Review: Changes to Existing Behavior in the v0.12 Stack

**Date:** 2026-10-01

**Status:** A dated record for the user’s sign-off, not a maintained table.
It is the list of intended changes to behavior that existed in v0.11.0. The landing gate
(`mb-2g6f`) requires that list in writing, because the stack is not purely additive.
The landing decision is `mb-n2ro`; this record is evidence for it.

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

The audit and the differential ran at #259’s head, `f62c16b1`, below #261, #263, #264,
and #265, and their reports are session files, so their substance is copied here.
Neither judged paint.
The gate’s third check, a browser differential, had not reported when this was written.

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
`end-of-options` and `diff/document` confirms:

| What changes | PR | Checked |
| --- | --- | --- |
| The comparison adapter runs `git rev-parse --verify --end-of-options <rev>^{commit}`, so a revision that begins with `-` is an argument and not an option. No response differed because of it | #216 | Data |
| `/api/plugin/diff/document` for a file it cannot open answers a typed 404, `diff_document`. v0.11.0 answered the degraded `plugin_error` envelope and logged a `PermissionError` traceback | #216 | Run |

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

Two more, found by the data differential, are **not yet fixed** at #265. Both still
reproduced when run for this record, and both are being fixed in the layer above #265:

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
- the stronger meaning of `--untrusted` and `--no-active-content` on a folder;
- the CLI differences above, including the slower `--doctor`;
- the two deliberate changes that have no `CHANGELOG.md` entry, or a request to add
  entries for them;
- the page differences and the new routes and plugin row on every folder.

It does not accept the two regressions still being fixed, and it says nothing of the
browser differential.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

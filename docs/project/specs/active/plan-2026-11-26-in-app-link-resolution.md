# Plan: In-App Link Resolution

**Date:** 2026-11-26

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Implemented in [#874](https://github.com/jlevy/metabrowser/pull/874), after
an engineering review, a security review, and a technical and design review, and
[Phase 2](#phase-2-routes-in-place) opens every in-app page a link names in place; the
beads linked to this spec track it
(`tbd list --spec plan-2026-11-26-in-app-link-resolution.md`), and
[Follow-ups](#follow-ups) names what it leaves.

## Overview

The owner asked, on 2026-11-26, for one definition of what a link in rendered text
opens, applied everywhere Metabrowser shows authored text: Markdown files, a folder’s
README, a pull request’s description, comments, and reviews, Guided Review notes, and
commit messages.

> “Any place GitHub resolves links to other GitHub repos or to the repo itself in these
> kinds of contexts, we should do the same thing, but we should resolve it to a
> Metabrowser first. For complex or unusual links, they should link directly out as
> usual, but if something is linking to a relative URL or it’s linking to the same repo
> we’re browsing, then it should navigate to the appropriate entity in the browser.
> … it should respect the current branch we’re on.
> … if we navigate to a PR or any other entity type that we handle, like a commit, if
> the Git is a straight link and it matches after basic normalization, then we should go
> to the corresponding page.
> Otherwise, it should go ahead and link to the external link.”

The example that did not work was `[Trade Runner](docs/trade-runner/README.md)` in a
pull request’s text.

## Goals

- A relative link in any rendered text opens the file it names in Metabrowser, at the
  revision the text belongs to.
- A `github.com` link into the served repository opens the matching in-app page when one
  exists and shows the same content: a file or folder, the repository root, a pull
  request and its tabs, a commit, or the pull request list.
- Every other link stays the external link it was.
- One pure resolver decides every surface’s links, so they cannot drift apart.

## Non-Goals

- **Switching the served revision from a link.** No `/view/` address names a revision,
  and the codebase holds that authored content never chooses what the server serves
  (`markdownTargets` in `diff-markdown.js`, and the text-action rule in
  [Design System: Control Families](../../../design-system.md#control-families)). A link
  that would need a switch stays external.
- Linkifying bare URLs, `#123`, or `@user`: KPress renders with linkify off, as
  `git/message.py` records, and this plan does not change what becomes a link.
- Issues, compare views, Actions, releases, and wiki pages, which have no in-app page.
- Images in pull-request texts, which keep the allowlist’s rules in `inert_html.py`.
- Repository folders switching to a pull request’s head, which
  [Open Modes](../../architecture/arch-open-modes.md#implementation-status) tracks.

## Background

### What Exists Today

Measured on `origin/main` at `cb3bf843` against a fixture checkout whose origin is
`github.com/acme/widgets`, and against the GitHub pull-request fixture
(`tests/github_pull_fixture.py --guided`) in headless Chromium.

| Surface | Where links are decided | Relative link | Same-repo `github.com` link |
| --- | --- | --- | --- |
| Markdown file, folder README, transclusion | `markdown/link-enhancer.js` with `links.js` and `github-localizer.js` | Opens the file, from the document, at the served revision | `blob` and `tree` on the served branch or commit open in place; every other kind is external |
| Pull request description, comments, reviews, review comments | Server `harden(link_base=html_url)` in `pull_text_render.py`; client `inertProse` in `pull-page.js` | Resolved against the pull request’s page: `docs/x.md` becomes `github.com/<o>/<r>/pull/docs/x.md`, a page that does not exist | External |
| Guided Review notes, on a pull request or a stack | The same render; `loadDrawProse` in `pull-page.js` and `stack-page.js` | As above (pinned by `cli-github-guided-review.tryscript.md`) | External |
| Commit message body | `git/message.py` with base `about:blank`; `commitKpressHost` in `git-panel.js` | Loses its address and keeps its text | External |
| Rendered Markdown in Changes, Docs, and guided documents | `pull_snapshot.py` writes `/view/` at the head; `markdownTargets` in `diff-markdown.js` | Opens the file only while the served pin is the head; plain text otherwise | External, without the external-link mark |

In the Markdown file view, links to the repository root, a pull request, its Changes
tab, a commit, and a `tree` URL naming the branch root all left for `github.com`, and a
pull request’s `[the guide](docs/new.md)` opened `github.com/octo/demo/pull/docs/new.md`
in a new tab.

The server already reads every `github.com` URL shape (`builtin_plugins/github/urls.py`)
and maps a selection to an in-app address (`cli/selection_href.py`), reached by
`POST /api/source/link`, which the macOS app uses and which switches the pin for a
branch, folder, or file.
No browser code used it, and the only browser mapping was `localizeGithubUrl`, inside
the Markdown plugin.

### How github.com Resolves the Same Links

A Markdown file’s relative link resolves from the file, at the branch or commit being
viewed. A description or comment has no file: its relative link resolves against the
page’s URL, so `docs/x.md` lands under `/pull/` and fails, while `../blob/main/x.md`
works. A commit message is not Markdown there, and its relative text is no link.

## Design

### One Resolver

A core on-demand script, `static/repository-links.js`, holds the whole decision, and
`metabrowser.loadRepositoryLinks()` (in `static/plugin-sdk-views.js`, beside
`loadChangedFilesTree`) is the one way a view gets it: the runtime on a page with a
GitHub repository’s identity.
The shared loader returns null when the asset is unavailable or misses its deadline.
A later view can use the asset once it has loaded.
The bundle carries the GitPath codec the resolver spells a pin’s addresses with.

The module reads a link the way a GitHub URL is built,
`github.com/<owner>/<repo>/<page>/<args>`: one reader for the host, repository, path,
query, and fragment (`readRepositoryUrl`), then one handler per GitHub page (`PAGES`),
then one function per in-app address it can answer with and one for github.com addresses
(`fileUrl`, `viewFileUrl`). Its header holds the table of what each GitHub URL opens;
the rules below are the design that table implements.
It replaces `markdown/github-localizer.js`. It lives in core rather than in the Markdown
plugin because its consumers are core (`git-panel.js`) and three plugins (Markdown,
GitHub, diff), and the routes it writes, `/view/`, `/commit/`, `/pull/`, `/stack/`, and
`/pulls`, are core’s grammar.
It is on demand rather than in the startup scripts because only a page that shows
authored text from a GitHub repository uses it, and the startup scripts are at their
transfer budget (`performance-budgets.toml`).

- `localize(url, context, options)` classifies one absolute URL and answers an in-app
  target, a replacement external URL, or `null` for “leave it as it is”.
- `enhance(root, mb, options)` applies `localize` to every `a[href]` of an inert text
  already reduced to the allowlist, rewrites each in-app link’s `href`, drops its
  `target` and `rel`, and returns how many links it changed.
  A plain click opens a `/view/` target through `mb.navigation.open`, and a route
  through the page’s own `options.open` when it takes it, as a pull request’s page takes
  another’s, and otherwise through the shell’s `mb.navigation.openRoute`
  ([Phase 2](#phase-2-routes-in-place)). A link whose address the navigation codec will
  not spell is left as written, and the text’s other links are still read.
  It keeps the sanitized link attributes in a weak map so a later pass can update the
  address and its click handler, or restore the original link.
  The Markdown link enhancer keeps its own DOM pass and calls only `localize`, and a
  plain click on a route it localized asks `mb.navigation.openRoute` too.

### Resolution Rules

A URL is a **repository link** when its scheme is `http` or `https`, its host is
`github.com` or `www.github.com`, it carries no credentials or port, and its first two
path segments are ASCII names of the served repository, compared without case and with
one trailing `.git` removed.
Anything else is left as it is, and so is a link whose query holds a `%` that starts no
escape, which a raw HTML link can carry and no `/view/` address can spell.

| Repository link | In-app target |
| --- | --- |
| `/<o>/<r>`, with or without a fragment, or with the repository page’s `?tab=readme-ov-file` | `/view/` and the fragment, which scrolls the root’s README as GitHub’s repository page does; only when the served root is the repository root |
| `tree/<ref>[/<path>]`, `blob/<ref>/<path>` naming the served branch or the served commit’s full or abbreviated ID | `/view/<path>`, `/view/` for the branch’s root; query and fragment kept |
| `pull/<n>` | `/pull/<n>` |
| `pull/<n>/files`, `pull/<n>/changes` | `/pull/<n>/files` when the link has no anchor |
| `pull/<n>/checks` | `/pull/<n>/checks` |
| `pull/<n>/commits/<id>`, `commit/<id>`, with a full commit ID | `/commit/<id>`, lowercased, when the link has no anchor |
| `pulls`, with no query | `/pulls` |
| Anything else: another branch, a tag, another or abbreviated commit, `issues`, `compare`, `commits`, `wiki`, `raw`, a query on `/pulls`, a pull-request or commit fragment | Left external |

A path in a `/view/` target is the repository path less the served prefix; a path
outside the served prefix is left external.
On a pinned revision it is written in the GitPath wire (`MetabrowserGitPath.wire`), as
every `/view/` address on a pin is.

Another branch stays external because no in-app address names it: opening it would mean
switching the served pin, which a link in authored text never does.
A link that does name the served branch or commit opens the same content in place, which
is what “respect the current branch” requires; a relative link always does, since
`/view/` addresses the served revision.

### Texts of a Pull Request

A description, comment, review, review comment, or Guided Review note has the pull
request’s page as its base on the server, unchanged, so the page receives the same
absolute URLs github.com would, and `localize` reads them with a **text context**: the
commit the text describes and the paths its comparison changes on the head side.
The hardener marks path-relative references before making them absolute.
The marker distinguishes an authored file reference from an absolute GitHub URL such as
a pull request’s patch link.

A marked URL under `/<o>/<r>/pull/` whose rest names no pull request is read as a
repository path at the head.
A pull-request address begins with GitHub’s `new`, the page that opens a pull request,
or with a number followed by nothing or one of a pull request’s pages (`files`,
`changes`, `checks`, `commits`), so `7/files` is still pull request 7’s Changes and
`2024/notes.md` is a folder named with digits.
A bare `pull` is no reference.
The path opens where Metabrowser can show that file without switching what it serves:

1. in place at `/view/<path>`, when the page is pinned to the head and the path is
   inside the served root;
2. in the pull request’s Changes at that file, `/pull/<n>/files/<path>`, or a stack’s,
   `/stack/<n>/changes/<path>`, when the head side changes the file and the link has no
   query or anchor to keep.
   The page opens it in place.
3. otherwise, the external link to that path at the head,
   `github.com/<o>/<r>/blob/<head>/<path>`, or `tree/` for a path ending in `/`,
   preserving any query or fragment.

So `docs/x.md` and `./docs/x.md` name the head’s file, and `../blob/main/x.md` and
`/<o>/<r>/blob/main/x.md` mean what they mean on github.com.
A checkout at the head can contain local edits.
Its PR text uses Changes or GitHub for the head’s file.
If the server’s pin moves, the stale page uses GitHub until reloaded.
The changed files can arrive after a text is drawn; the page then runs `enhance` again
over its drawn texts, which reads each link as the text wrote it.
A stack’s Guided Review notes use the stack page’s drawn comparison, its head and its
files, since the stack’s guide describes the whole stack.

### Commit Messages and Rendered Diffs

A commit body keeps its `about:blank` base, so a relative reference stays text, as on
github.com. Its repository links are localized against the served tree.
When a checkout lacks a linked commit object, the commit pane offers that commit on
GitHub.

In rendered Markdown in Changes, Docs, and guided documents, a link to a file of the
head opens it in place while the served pin is the head: a plain click opens its
`/view/` address through `mb.navigation.open` (`openHeadLinks` in `diff-markdown.js`,
reading the click with the resolver’s `isPlainClick`), as the resolver’s own `/view/`
targets beside it open, where it once loaded the page again; when the pin is not the
head, or it changes, the link becomes the external link to that file at the head instead
of plain text, and its click is the browser’s. Its repository links are localized as
everywhere else, and its external links get the external-link mark the other surfaces
give them.

A repository link the resolver would open at a `/view/` address follows the same rule
(`mb-e2lo`): a `blob/` or `tree/` link to the served branch or commit opens in place, as
in a README, only while the page shows the head (`headLinksOpen` in
`builtin_plugins/diff/index.js`, the one rule both kinds of link read), and stays as
written beside a checkout or on a page pinned elsewhere, the head’s branch at an earlier
commit among them.
When another tab changes the pin, `closeHeadLinks` points the server’s
links to a file of the head at github.com and has `enhance` read the rest again with
`views: false`, which restores each `/view/` target it made to the link the text wrote,
with its click; so a link drawn before the change reads as one drawn after it, and no
link opens another pin’s `/view/` address.
The two kinds are told apart by who made them: `sanitizeBlock` records the links it kept
at `/view/`, the only ones converted by their address, and the resolver restores its own
from the link it kept, since its targets include folders and queries, which
`viewFileUrl` does not read.

### Invariants

- An in-app link’s `href` is the address a plain click opens, so a new tab, a copied
  address, and the browser’s history open what the click opens.
- A plain click opens an in-app page in place whenever the shell can show it, on every
  surface: no route link loads the page again once the shell’s tabs have loaded.
- No link in authored text switches the served pin, starts a fetch, or posts anything.
- `localize` is a pure function of the URL, the repository context, and the text
  context: one table of cases pins every surface.
- A URL that is not a repository link, or that no rule matches, is returned unchanged.

## Implementation Plan

### Phase 1: Resolver and Surfaces

One pull request.

- [x] `static/repository-links.js`, organized by the structure of a GitHub URL, its
  on-demand bundle with the GitPath codec, `metabrowser.loadRepositoryLinks()`, its
  runtime type, and its session; `github-localizer.js` removed
- [x] Markdown documents: `link-enhancer.js` uses `localize` for every repository link,
  with the runtime `rendered.js` loads through the SDK’s bounded loader
- [x] Pull request texts and Guided Review notes, on a pull request and a stack: the
  text context, the Changes step, and a re-read when changed files arrive or the served
  pin moves
- [x] Commit bodies: `commitKpressHost` applies `enhance`
- [x] Rendered diffs: the head-link fallback (`viewFileUrl`) and repository links
- [x] Parity rows, sessions and goldens, user guides, the skill’s guidance on links in
  notes, architecture documents, the Markdown navigation plan’s pointer, and a changelog
  fragment

### Phase 2: Routes in Place

`mb-0uzt`, from a design review of #874: a `/view/` link opened in place, but a link to
a commit’s page, to the list, or, outside the pull request’s page, to another pull
request loaded the page again, which lost the shell’s state.

- [x] One opener in the shell: the tab controller’s `openRoute` (`static/main-tabs.js`)
  pushes the link’s address and lands it as a tab’s button lands its destination
  (`openMainTab`, through the same `land`): the tab that holds it in front, its panel
  revealing the item, and the pane showing what the address names, the Commits panel
  selecting a commit as Back makes it select one.
  The address already shown it opens again where it is, as `navigation.open` does: it
  pushes no entry and lands nothing, so the page keeps its place, and the panel reveals
  the item again, as Quick Search for the item shown does.
  It answers false for any other address, and before the shell tools have loaded, and
  the browser follows the link.
- [x] The SDK’s `metabrowser.navigation.openRoute(href)`, an additive method of the
  facade, so `PLUGIN_SDK_VERSION` stays; it is one eager line that asks the controller.
- [x] `enhance` falls back to it for every route a page’s own `open` declines, so the
  pull request’s and stack’s pages keep switching their own tabs in place and every
  surface opens a commit’s page and the list in place, a commit’s message and a rendered
  diff with no change of their own; the Markdown link enhancer asks it for its route
  links.

## Testing Strategy

- `tests/dom/repository-links-session.js` runs the exact `repository-links.js` against
  one table of URLs and contexts (each rule above, its refusals, a served prefix, a
  pinned revision, and pull request and stack texts at and away from their heads, with
  and without their changed files), its `viewFileUrl`, and `enhance` read once and
  again; `cli-ui-repository-links.tryscript.md` pins it, and parity row
  `shell.repository-links` credits it.
- `tests/test_repository_links_js.py` holds those answers to the server’s own reading of
  the same URLs: each in-app page is the one `GithubUrlReducer` and
  `selection_view_href` open the URL at, each Changes route the one the route decoders
  read back, each pinned address the server’s GitPath spelling, and each github.com
  fallback that file at the head; and one click listener a link, however often its text
  is read.
- The pull request page’s mount behavior, the stack guide session, the commit body
  session, `markdown-link-enhancer-behavior.js`, and the diff Markdown session assert
  each surface’s wiring with the real resolver (parity rows `github.pull-text-links`,
  `github.stack-note-links`, `git.commit-body-markdown`). Each but the diff Markdown
  session, which draws without the diff’s view, clicks a link to a commit’s page, to the
  list, and to another pull request, plainly and with a modifier;
  `diff-view-behavior.js` does for the production diff view.
  The diff Markdown session and `diff-view-behavior.js` also click a link to a file of
  the head the server spelled, at the head and after the pin changes, the second at the
  target the shell’s own `parse` reads its address as.
- `tests/dom/nav-reveal-session.js`’s part `links` runs the SDK’s `openRoute` and the
  tab controller’s whole over the shell’s tabs: each address it opens, what each part of
  the shell is asked, and the addresses it leaves to the browser;
  `cli-ui-nav-reveal.tryscript.md` pins it, and parity row `navigation.route-open`
  credits it.
- `cli-github-guided-review.tryscript.md` keeps pinning the server’s render, which does
  not change; the browser side is the sessions above.
- A real-browser check of a fixture checkout and the GitHub pull request fixture: the
  guided note’s `docs/new.md` link opens the file at the head in the same tab, and away
  from the head the file at the head on github.com.

## Rollout Plan

Ships in the next release with a changelog fragment; nothing persists, so there is
nothing to migrate.

## Open Questions

None blocking. Two choices the owner may revisit, each a one-line change in `localize`:

- **Another branch’s link opens externally.** The alternative, switching the pin on a
  click as `POST /api/source/link` does for the macOS app, contradicts the rule that
  content never chooses what the server serves.
- **The repository root opens the served root**, not the default branch, since no in-app
  address names the default branch either.

## Follow-ups

Beads under the Markdown rendering epic, each from a review of #874:

- `mb-e2lo`: a rendered diff localizes `/view/` targets while it shows the head.
  Done: [Commit Messages and Rendered Diffs](#commit-messages-and-rendered-diffs) has
  the design, and the diff Markdown session (`cli-ui-diff-markdown.tryscript.md`) pins
  each page’s answer, a click with and without a modifier, and the change of pin.
- `mb-40en`: a single helper that loads and applies the links; the loader now makes a
  forgotten load impossible, and the bead is whether more is worth it.

## References

- [Markdown Navigation Extensions](plan-2026-08-13-markdown-navigation-extensions.md),
  whose Verified GitHub URL Localization this plan widens
- [View on Branch](plan-2026-11-17-view-on-branch.md), for the rule on rendered links in
  diffs
- [Views, Models, and Routes: Browser URL Grammar](../../architecture/arch-views-models-routes.md#browser-url-grammar)
- [GitHub Links](../../architecture/arch-macos-app.md#github-links)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

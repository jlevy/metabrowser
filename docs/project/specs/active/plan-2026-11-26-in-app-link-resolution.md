# Plan: In-App Link Resolution

**Date:** 2026-11-26

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** In implementation, as the owner asked on 2026-11-26; the beads linked to
this spec track it (`tbd list --spec plan-2026-11-26-in-app-link-resolution.md`).

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

A new core on-demand script, `static/repository-links.js`, published as
`MetabrowserRepositoryLinks` through `metabrowser.ensureAsset("repository-links")`,
holds the whole decision.
It is pure apart from one DOM helper, it does no I/O, and it reads only what the page
already has: `metabrowser.repository` (owner, name, branch, revision, and served prefix
of the served tree) and `metabrowser.sourceKind()`.

It replaces `markdown/github-localizer.js`. It lives in core rather than in the Markdown
plugin because its consumers are core (`git-panel.js`) and three plugins (Markdown,
GitHub, diff), and the routes it writes, `/view/`, `/commit/`, `/pull/`, and `/pulls`,
are core’s grammar. It is on demand rather than in the startup scripts because only a
page that shows authored text from a GitHub repository uses it, and the startup scripts
are at their transfer budget (`performance-budgets.toml`).

- `localize(url, context, options)` classifies one absolute URL and answers an in-app
  target, a replacement external URL, or `null` for “leave it as it is”.
- `enhance(root, mb, options)` applies `localize` to every `a[href]` of an inert text
  already reduced to the allowlist, rewrites each in-app link’s `href`, drops its
  `target` and `rel`, opens a `/view/` target through `mb.navigation.open` on a plain
  click, and returns a disposer.
  The Markdown link enhancer keeps its own DOM pass and calls only `localize`.

### Resolution Rules

A URL is a **repository link** when its scheme is `http` or `https`, its host is
`github.com` or `www.github.com`, it carries no credentials or port, and its first two
path segments name the served repository, compared without case and with one trailing
`.git` removed. Anything else is left as it is.

| Repository link | In-app target |
| --- | --- |
| `/<o>/<r>`, with or without a fragment | `/view/` and the fragment, which scrolls the root’s README as GitHub’s repository page does; only when the served root is the repository root |
| `tree/<ref>[/<path>]`, `blob/<ref>/<path>` naming the served branch or the served commit’s full ID | `/view/<path>`, `/view/` for the branch’s root; query and fragment kept |
| `pull/<n>` | `/pull/<n>` |
| `pull/<n>/files`, `pull/<n>/changes` | `/pull/<n>/files`; a `#diff-<hash>` anchor is dropped, since only the server can name its file |
| `pull/<n>/checks` | `/pull/<n>/checks` |
| `pull/<n>/commits/<id>`, `commit/<id>`, with a full commit ID | `/commit/<id>`, lowercased; a file anchor is dropped, as `urls.py` does |
| `pulls`, with no query | `/pulls` |
| Anything else: another branch, a tag, another or abbreviated commit, `issues`, `compare`, `commits`, `wiki`, `raw`, a query on `/pulls`, a pull-request fragment other than a file anchor | Left external |

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
pull request’s page and the commit its text describes, the head.

A URL under `/<o>/<r>/pull/` whose rest is not a pull-request address (a number, then
nothing or a tab) is what a path-relative reference becomes against that page, and is
read as the repository path it names, at the head:

- when the served revision is the head, it opens in place at `/view/<path>`;
- otherwise it becomes the external link to that path at the head,
  `github.com/<o>/<r>/blob/<head>/<path>`, or `tree/` for a path ending in `/`, which
  shows exactly the file the author meant, where github.com itself showed a missing
  page.

So `docs/x.md` and `./docs/x.md` name the head’s file, `../blob/main/x.md` and
`/<o>/<r>/blob/main/x.md` mean what they mean on github.com, and `7/files` is still pull
request 7’s Changes.
A stack’s Guided Review notes use the stack page’s drawn comparison head as their
commit, since the stack’s guide describes the whole stack.

### Commit Messages and Rendered Diffs

A commit body keeps its `about:blank` base, so a relative reference stays text, as on
github.com; its repository links are localized against the served tree.

In rendered Markdown in Changes, Docs, and guided documents, a link to a file of the
head opens it in place while the served pin is the head, as now; when it is not, or the
pin changes, it becomes the external link to that file at the head instead of plain
text. Its repository links are localized as everywhere else, and its external links get
the external-link mark the other surfaces give them.

### Invariants

- An in-app link’s `href` is the address a plain click opens, so a new tab, a copied
  address, and the browser’s history open what the click opens.
- No link in authored text switches the served pin, starts a fetch, or posts anything.
- `localize` is a pure function of the URL, the repository context, and the text
  context: one table of cases pins every surface.
- A URL that is not a repository link, or that no rule matches, is returned unchanged.

## Implementation Plan

### Phase 1: Resolver and Surfaces

One pull request.

- [ ] `static/repository-links.js`: `localize` and `enhance`, its on-demand registration
  in `server.py`, its runtime type in `static/types.d.ts`, and its behavior test,
  carrying `github-localizer.js`’s cases; remove `github-localizer.js`
- [ ] Markdown documents: `link-enhancer.js` uses `localize` for every repository link;
  `rendered.js` ensures the asset when the page has a repository context
- [ ] Pull request texts: `inertProse`, Guided Review’s `loadDrawProse`, and the stack
  page’s `loadDrawProse` call `enhance` with the text context
- [ ] Commit bodies: `commitKpressHost` calls `enhance`
- [ ] Rendered diffs: the head-link fallback and repository links in `diff-markdown.js`
- [ ] Parity row, browserless session and golden, user guides (`browsing-files.md`,
  `reviewing-pull-requests.md`, the skill’s guidance on links in notes), architecture
  documents, the Markdown navigation plan’s pointer, and a changelog fragment

## Testing Strategy

- A browserless session runs the exact `repository-links.js` against one table of URLs
  and contexts (each rule above, its refusals, a served prefix, a pinned revision, and a
  text context at and away from the head) and pins its output in a golden; the parity
  check credits `localize` and `enhance` to the row.
- `markdown-link-enhancer-behavior.js` and the pull-request page, Guided Review, commit
  body, and diff sessions assert the rewritten `href`s and that a plain click on a
  `/view/` target goes through `mb.navigation.open`.
- `cli-github-guided-review.tryscript.md` keeps pinning the server’s render, which does
  not change; the browser side is the sessions above.
- A real-browser check of the fixture checkout and the guided fixture repeats the
  measurements in [What Exists Today](#what-exists-today).

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

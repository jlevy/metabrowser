---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Inert Table of Contents

Under the untrusted profile -- every served mirror, and a folder served with
`--untrusted` -- the page runs no KPress script, so KPress’s table of contents cannot
run. The render route takes KPress’s table of contents out of the inert HTML, says in
`toc` whether KPress drew one, and points KPress’s entries (`model.headings`) at the
headings’ `user-content-` anchors.
The page draws its own table of contents from those entries in KPress’s markup, so
KPress’s stylesheets place it in the side rail or the narrow drawer, and runs it: the
entry for the section at the reading line is active, the narrow toggle opens and closes
the drawer, and an entry click closes it.

This browserless session runs the production `builtin_plugins/markdown/inert-render.js`
and `builtin_plugins/markdown/inert-toc.js`, and `static/inert-html.js` on the inert
render `tests/test_inert_toc.py` records in `tests/fixtures/inert-toc-render.json`. It
shows the anchors of a guide with a repeated heading, a heading named like a prototype
member, and a raw HTML heading with an `id` of its own; the entries drawn; that a render
KPress drew no table of contents for gets none; that an entry which does not point at an
anchor in the document is left out and a depth out of range is clamped; and the state
after scrolling, opening the drawer, clicking an entry, and clicking the backdrop.
Disposal removes every listener.

```console
$ node tests/dom/markdown-inert-toc-session.js
{
  "headingIds": [
    "user-content-guide",
    "user-content-install",
    "user-content-usage",
    "user-content-usage-1",
    "user-content-constructor",
    "user-content-raw-heading",
    "user-content-troubleshooting"
  ],
  "layout": "kpress-doc-layout kpress-content-with-toc",
  "entries": [
    {
      "level": "kpress-toc-level-1 toc-h1",
      "href": "#user-content-install",
      "text": "Install"
    },
    {
      "level": "kpress-toc-level-1 toc-h1",
      "href": "#user-content-usage",
      "text": "Usage"
    },
    {
      "level": "kpress-toc-level-2 toc-h2",
      "href": "#user-content-usage-1",
      "text": "Usage"
    },
    {
      "level": "kpress-toc-level-1 toc-h1",
      "href": "#user-content-constructor",
      "text": "constructor"
    },
    {
      "level": "kpress-toc-level-1 toc-h1",
      "href": "#user-content-troubleshooting",
      "text": "Troubleshooting"
    }
  ],
  "withoutToc": true,
  "forgedEntries": [
    {
      "level": "kpress-toc-level-6 toc-h6",
      "href": "#user-content-install",
      "text": "Install"
    }
  ],
  "atTop": {
    "scrollTop": 0,
    "active": "#user-content-install",
    "activeMarked": "#user-content-install",
    "expanded": "false",
    "drawerOpen": false,
    "backdropVisible": false,
    "toggleShown": false
  },
  "scrollFramesQueued": 1,
  "scrolled": {
    "scrollTop": 3900,
    "active": "#user-content-constructor",
    "activeMarked": "#user-content-constructor",
    "expanded": "false",
    "drawerOpen": false,
    "backdropVisible": false,
    "toggleShown": true
  },
  "toggleOpened": {
    "scrollTop": 3900,
    "active": "#user-content-constructor",
    "activeMarked": "#user-content-constructor",
    "expanded": "true",
    "drawerOpen": true,
    "backdropVisible": true,
    "toggleShown": true
  },
  "entryClicked": {
    "scrollTop": 3900,
    "active": "#user-content-troubleshooting",
    "activeMarked": "#user-content-troubleshooting",
    "expanded": "false",
    "drawerOpen": false,
    "backdropVisible": false,
    "toggleShown": true
  },
  "backdropClicked": {
    "scrollTop": 3900,
    "active": "#user-content-troubleshooting",
    "activeMarked": "#user-content-troubleshooting",
    "expanded": "false",
    "drawerOpen": false,
    "backdropVisible": false,
    "toggleShown": true
  },
  "disposed": {
    "listeners": 0
  }
}
? 0
```

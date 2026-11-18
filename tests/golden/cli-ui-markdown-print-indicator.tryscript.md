---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: Document Print Button

A rendered document whose view prints the document itself carries a print button in the
upper right corner of its card: the Markdown file’s Document view and the README on a
folder’s Overview ask for it, and a mount whose host does not ask has none.
The shell’s header has no print button, and printing is the browser’s: the button calls
`window.print()`, as Command-P prints, and the macOS app answers a page’s print with
File > Print’s path.

This browserless session runs the production `builtin_plugins/markdown/index.js`,
`builtin_plugins/markdown/rendered.js`, `builtin_plugins/markdown/print-indicator.js`,
`builtin_plugins/folder/readme-panel.js`, and the trusted and inert placement modules on
a small DOM of its own.
It shows the button in the document’s own card and not a nested transclusion’s, last in
it, named and labelled, owner-marked, with no `id`; that a click prints once and a
document’s own copy of its markup prints nothing; that an inert render has the same
button, and a failed render and a host that does not ask have none; and that disposing
removes it with its listener, so a view mounted again has one.
Where the button lands, that nothing moves when it arrives, and the table of contents
toggle beside it are layout, which `tests/test_document_print_chrome.py` measures in
headless Chrome.

```console
$ node tests/dom/markdown-print-indicator-session.js
{
  "broken": {
    "buttons": 0,
    "card": false
  },
  "click": {
    "documentCopy": 0,
    "pageButton": 1,
    "documentListeners": 0
  },
  "disposed": {
    "buttons": 0,
    "listeners": 0,
    "removed": true
  },
  "file": {
    "buttons": 1,
    "ariaLabel": "Print document",
    "className": "icon-btn metabrowser-print-indicator",
    "icon": "printer",
    "id": null,
    "inCard": true,
    "lastInCard": true,
    "ownerMarked": true,
    "tipText": "Print document",
    "type": "button"
  },
  "hosts": {
    "asked": 1,
    "notAsked": 0,
    "off": 0
  },
  "inert": {
    "buttons": 1,
    "lastInCard": true
  },
  "note": {
    "buttons": 1,
    "lastInCard": true
  },
  "readme": {
    "buttons": 1,
    "lastInCard": true
  },
  "replaced": 1,
  "failures": []
}
? 0
```

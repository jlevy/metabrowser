---
cwd: ../..
sandbox: false
---
# Golden test: the View on GitHub button

The button every page with a github.com counterpart draws in its header’s upper right
(docs/design-system.md, “View on GitHub”): the production `counterpartButton` and
`mountCounterpart` from `static/plugin-sdk-views.js`, loaded with the SDK into a context
of their own over a stand-in DOM that keeps attributes, focus, `hidden`, listeners, and
containment.

`markup` is the button’s tree: a joined chip group of the link, the GitHub mark and its
label, and the chevron, a menu button, then the menu of Copy Link and Open in Browser,
hidden, and an empty status line, a polite live region.
The root carries `data-view-on-github`, which names the button, and the link and Open in
Browser carry the hooks the macOS app reads, which name no site (`data-web-view="open"`
and `="external"`), and both links open the counterpart in a new tab.

`menu` walks it: a click on the chevron opens the menu with focus on Copy Link; the
arrow keys, Home, and End move focus and wrap, and take the key’s default; another key
does nothing; Escape closes the menu, gives focus back to the chevron, and stops there;
the arrow keys on the chevron open the menu at its first or last item; Tab closes it and
leaves focus to the browser’s own move; a second click on the chevron and a click on
Open in Browser close it and give focus back to the chevron; and a press outside the
button closes it while one on an item does not.
A chord held with Command, Control, or Option is the browser’s: it neither opens the
menu nor moves in it, and Option-Tab, with which Safari moves focus, closes it as Tab
does.
Focus that leaves the button for a frame, which sends the document no press, closes
the menu once it lands; focus that goes nowhere leaves the menu to a press.
The button holds its one listener on the document only while the menu is open.

`copy` is Copy Link with a clipboard that takes the link, one that refuses it, and none:
the menu closes, focus goes back to the chevron, and the status line under the button
and the chevron’s tooltip say “Link copied” or “Copy failed” for 1.5 s, then the line
empties and the tooltip says its own words again.
A second copy before the first one’s time ends keeps its confirmation for its own time.

`mount` is what a header’s corner asks the server and keeps: the page’s address encoded
into one `GET /api/counterpart` per page, asked once for a page the corner already
shows; the button for an answer with a counterpart, under the provider’s own hook and
label for another provider; an empty corner for a page with none, an address that is not
https, a failed request, and a refused one; and the answer for the page asked last, when
an earlier page’s answer lands after it.
A new corner for a page answered before, as a repaint or a return draws, shows its last
answer before the new one lands, and keeps the button when the answer is the same.
A page the shell asked for as it started loading (`prefetchCounterpart`) is asked once,
and its answer, when it lands first, is drawn with the header.

```console
$ node tests/dom/counterpart-session.js
{
  "markup": {
    "tag": "span",
    "class": "counterpart",
    "data-view-on-github": "",
    "children": [
      {
        "tag": "span",
        "class": "chip-group counterpart-group",
        "dataset.layout": "joined",
        "children": [
          {
            "tag": "a",
            "class": "chip counterpart-open",
            "data-web-view": "open",
            "href": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md",
            "target": "_blank",
            "rel": "noopener",
            "dataset.tipText": "github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md",
            "children": [
              {
                "tag": "span",
                "class": "counterpart-mark",
                "aria-hidden": "true",
                "html": "<svg viewBox=\"0 0 16 16\" fill=\"currentColor\"><pa…"
              },
              {
                "tag": "span",
                "class": "counterpart-label",
                "children": [
                  "View on GitHub"
                ]
              }
            ]
          },
          {
            "tag": "button",
            "class": "chip chip-menu-trigger counterpart-more disclosure-toggle",
            "type": "button",
            "aria-haspopup": "menu",
            "aria-expanded": "false",
            "aria-label": "View on GitHub: Copy Link or Open in Browser",
            "dataset.tipText": "Copy Link or Open in Browser",
            "children": [
              {
                "tag": "span",
                "class": "chip-menu-caret",
                "aria-hidden": "true",
                "html": "<svg data-icon=\"toggle\"></svg>"
              }
            ]
          }
        ]
      },
      {
        "tag": "div",
        "class": "menu counterpart-menu",
        "role": "menu",
        "aria-label": "View on GitHub",
        "hidden": true,
        "children": [
          {
            "tag": "button",
            "class": "menu-item",
            "role": "menuitem",
            "tabindex": "-1",
            "data-mb-owner": "(page owner)",
            "type": "button",
            "dataset.counterpartAction": "copy",
            "children": [
              {
                "tag": "span",
                "class": "menu-item-icon",
                "aria-hidden": "true",
                "html": "<svg data-icon=\"copy\"></svg>"
              },
              {
                "tag": "span",
                "class": "menu-item-label",
                "children": [
                  "Copy Link"
                ]
              }
            ]
          },
          {
            "tag": "a",
            "class": "menu-item",
            "role": "menuitem",
            "tabindex": "-1",
            "data-mb-owner": "(page owner)",
            "data-web-view": "external",
            "href": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md",
            "target": "_blank",
            "rel": "noopener",
            "children": [
              {
                "tag": "span",
                "class": "menu-item-icon",
                "aria-hidden": "true",
                "html": "<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"cur…"
              },
              {
                "tag": "span",
                "class": "menu-item-label",
                "children": [
                  "Open in Browser"
                ]
              }
            ]
          }
        ]
      },
      {
        "tag": "span",
        "class": "counterpart-status",
        "role": "status"
      }
    ]
  },
  "menu": [
    {
      "step": "drawn",
      "menu": "closed",
      "expanded": "false",
      "focus": "nothing",
      "outsideListeners": 0
    },
    {
      "step": "a click on the chevron",
      "menu": "open",
      "expanded": "true",
      "focus": "Copy Link",
      "outsideListeners": 1,
      "prevented": false,
      "stopped": false
    },
    {
      "step": "ArrowDown",
      "menu": "open",
      "expanded": "true",
      "focus": "Open in Browser",
      "outsideListeners": 1,
      "prevented": true,
      "stopped": false
    },
    {
      "step": "ArrowDown again, past the last item",
      "menu": "open",
      "expanded": "true",
      "focus": "Copy Link",
      "outsideListeners": 1,
      "prevented": true,
      "stopped": false
    },
    {
      "step": "ArrowUp, past the first item",
      "menu": "open",
      "expanded": "true",
      "focus": "Open in Browser",
      "outsideListeners": 1,
      "prevented": true,
      "stopped": false
    },
    {
      "step": "Home",
      "menu": "open",
      "expanded": "true",
      "focus": "Copy Link",
      "outsideListeners": 1,
      "prevented": true,
      "stopped": false
    },
    {
      "step": "End",
      "menu": "open",
      "expanded": "true",
      "focus": "Open in Browser",
      "outsideListeners": 1,
      "prevented": true,
      "stopped": false
    },
    {
      "step": "a letter",
      "menu": "open",
      "expanded": "true",
      "focus": "Open in Browser",
      "outsideListeners": 1,
      "prevented": false,
      "stopped": false
    },
    {
      "step": "Escape",
      "menu": "closed",
      "expanded": "false",
      "focus": "the chevron",
      "outsideListeners": 0,
      "prevented": true,
      "stopped": true
    },
    {
      "step": "ArrowDown on the chevron",
      "menu": "open",
      "expanded": "true",
      "focus": "Copy Link",
      "outsideListeners": 1,
      "prevented": true,
      "stopped": false
    },
    {
      "step": "Escape",
      "menu": "closed",
      "expanded": "false",
      "focus": "the chevron",
      "outsideListeners": 0,
      "prevented": true,
      "stopped": true
    },
    {
      "step": "ArrowUp on the chevron",
      "menu": "open",
      "expanded": "true",
      "focus": "Open in Browser",
      "outsideListeners": 1,
      "prevented": true,
      "stopped": false
    },
    {
      "step": "Tab",
      "menu": "closed",
      "expanded": "false",
      "focus": "Open in Browser",
      "outsideListeners": 0,
      "prevented": false,
      "stopped": false
    },
    {
      "step": "a click on the chevron",
      "menu": "open",
      "expanded": "true",
      "focus": "Copy Link",
      "outsideListeners": 1,
      "prevented": false,
      "stopped": false
    },
    {
      "step": "a click on the chevron again",
      "menu": "closed",
      "expanded": "false",
      "focus": "the chevron",
      "outsideListeners": 0,
      "prevented": false,
      "stopped": false
    },
    {
      "step": "a press on an item, inside the button",
      "menu": "open",
      "expanded": "true",
      "focus": "Copy Link",
      "outsideListeners": 1
    },
    {
      "step": "a press outside the button",
      "menu": "closed",
      "expanded": "false",
      "focus": "Copy Link",
      "outsideListeners": 0
    },
    {
      "step": "a click on Open in Browser",
      "menu": "closed",
      "expanded": "false",
      "focus": "the chevron",
      "outsideListeners": 0
    },
    {
      "step": "Command-ArrowDown on the chevron",
      "menu": "closed",
      "expanded": "false",
      "focus": "the chevron",
      "outsideListeners": 0,
      "prevented": false,
      "stopped": false
    },
    {
      "step": "Control-End",
      "menu": "open",
      "expanded": "true",
      "focus": "Copy Link",
      "outsideListeners": 1,
      "prevented": false,
      "stopped": false
    },
    {
      "step": "Command-Escape",
      "menu": "open",
      "expanded": "true",
      "focus": "Copy Link",
      "outsideListeners": 1,
      "prevented": false,
      "stopped": false
    },
    {
      "step": "Option-Tab",
      "menu": "closed",
      "expanded": "false",
      "focus": "Copy Link",
      "outsideListeners": 0,
      "prevented": false,
      "stopped": false
    },
    {
      "step": "focus into a frame",
      "menu": "closed",
      "expanded": "false",
      "focus": "a frame",
      "outsideListeners": 0
    },
    {
      "step": "focus to nothing",
      "menu": "open",
      "expanded": "true",
      "focus": "the page",
      "outsideListeners": 1
    }
  ],
  "copy": [
    {
      "step": "Copy Link, a clipboard that takes",
      "menu": "closed",
      "expanded": "false",
      "focus": "the chevron",
      "outsideListeners": 0,
      "tip": "Link copied",
      "status": [
        "Link copied",
        "copied"
      ],
      "confirmedFor": [
        1500
      ],
      "tipAfter": "Copy Link or Open in Browser",
      "statusAfter": [
        "",
        null
      ]
    },
    {
      "step": "Copy Link, a clipboard that refuses",
      "menu": "closed",
      "expanded": "false",
      "focus": "the chevron",
      "outsideListeners": 0,
      "tip": "Copy failed",
      "status": [
        "Copy failed",
        "failed"
      ],
      "confirmedFor": [
        1500
      ],
      "tipAfter": "Copy Link or Open in Browser",
      "statusAfter": [
        "",
        null
      ]
    },
    {
      "step": "Copy Link, a clipboard that is not there",
      "menu": "closed",
      "expanded": "false",
      "focus": "the chevron",
      "outsideListeners": 0,
      "tip": "Copy failed",
      "status": [
        "Copy failed",
        "failed"
      ],
      "confirmedFor": [
        1500
      ],
      "tipAfter": "Copy Link or Open in Browser",
      "statusAfter": [
        "",
        null
      ]
    },
    {
      "step": "Copy Link twice, the first confirmation's time ending",
      "menu": "closed",
      "expanded": "false",
      "focus": "the chevron",
      "outsideListeners": 0,
      "statusBetween": [
        "Link copied",
        "copied"
      ],
      "statusAfter": [
        "",
        null
      ]
    },
    {
      "written": [
        "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md",
        "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md",
        "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md",
        "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md"
      ]
    }
  ],
  "mount": [
    {
      "step": "a page with a counterpart",
      "asked": [
        "/api/counterpart?page=%2Fview%2FREADME.md"
      ],
      "returned": "the button in the corner",
      "corner": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md",
      "hook": "data-view-on-github",
      "label": "View on GitHub"
    },
    {
      "step": "the same page again",
      "asked": [],
      "returned": "the button in the corner",
      "corner": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md",
      "hook": "data-view-on-github",
      "label": "View on GitHub"
    },
    {
      "step": "a page with none",
      "asked": [
        "/api/counterpart?page=%2Fview%2Fnotes.txt"
      ],
      "returned": null,
      "corner": "empty",
      "hook": null,
      "label": null
    },
    {
      "step": "another page asked before the first answers",
      "asked": [
        "/api/counterpart?page=%2Fpull%2F7%2Ffiles"
      ],
      "returned": "the button in the corner",
      "corner": "https://github.com/octo/demo/pull/7/files",
      "hook": "data-view-on-github",
      "label": "View on GitHub"
    },
    {
      "step": "the first answer lands late",
      "returned": null,
      "corner": "https://github.com/octo/demo/pull/7/files"
    },
    {
      "step": "an answer whose address is not https",
      "asked": [
        "/api/counterpart?page=%2Fview%2Fhttp.md"
      ],
      "returned": null,
      "corner": "empty",
      "hook": null,
      "label": null
    },
    {
      "step": "an answer whose address is a script",
      "asked": [
        "/api/counterpart?page=%2Fview%2Fscript.md"
      ],
      "returned": null,
      "corner": "empty",
      "hook": null,
      "label": null
    },
    {
      "step": "a page with a counterpart",
      "asked": [
        "/api/counterpart?page=%2Fview%2FREADME.md"
      ],
      "returned": "the button in the corner",
      "corner": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md",
      "hook": "data-view-on-github",
      "label": "View on GitHub"
    },
    {
      "step": "a request that fails",
      "asked": [
        "/api/counterpart?page=%2Fview%2Fgone.md"
      ],
      "returned": null,
      "corner": "empty",
      "hook": null,
      "label": null
    },
    {
      "step": "a page with a counterpart",
      "asked": [
        "/api/counterpart?page=%2Fview%2FREADME.md"
      ],
      "returned": "the button in the corner",
      "corner": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md",
      "hook": "data-view-on-github",
      "label": "View on GitHub"
    },
    {
      "step": "a request the server refuses",
      "asked": [
        "/api/counterpart?page=%2Fview%2Frefused.md"
      ],
      "returned": null,
      "corner": "empty",
      "hook": null,
      "label": null
    },
    {
      "step": "another provider's answer",
      "asked": [
        "/api/counterpart?page=%2Fview%2Felsewhere.md"
      ],
      "returned": "the button in the corner",
      "corner": "https://gitlab.com/octo/demo/-/blob/0/elsewhere.md",
      "hook": "data-view-on-gitlab",
      "label": "View on GitLab"
    },
    {
      "step": "a page with a space and a hash",
      "asked": [
        "/api/counterpart?page=%2Fview%2Fa%20b%23c.md"
      ],
      "returned": null,
      "corner": "empty",
      "hook": null,
      "label": null
    },
    {
      "step": "a new corner for a page answered before",
      "drawnBeforeTheAnswer": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md",
      "asked": [
        "/api/counterpart?page=%2Fview%2FREADME.md"
      ],
      "corner": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md",
      "sameButton": true
    },
    {
      "step": "a page whose answer changed since",
      "drawnBeforeTheAnswer": "https://github.com/octo/demo/blob/0123456789abcdef0123456789abcdef01234567/README.md",
      "asked": [
        "/api/counterpart?page=%2Fview%2FREADME.md"
      ],
      "corner": "https://github.com/octo/demo/blob/89abcdef0123456789abcdef0123456789abcdef/README.md"
    },
    {
      "step": "a page whose answer came before its header",
      "drawnBeforeTheAnswer": "https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567/docs",
      "asked": [
        "/api/counterpart?page=%2Fview%2Fdocs%2F"
      ],
      "corner": "https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567/docs"
    },
    {
      "step": "a page whose answer is in flight when its header is drawn",
      "drawnBeforeTheAnswer": "nothing",
      "asked": [
        "/api/counterpart?page=%2Fview%2Fsrc%2F"
      ],
      "corner": "https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567/src"
    }
  ]
}
? 0
```

---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
patterns:
  STORE: '[0-9a-f]{16}'
---
# Golden Test: Rendered Markdown in a Pull Request’s Changes

A pull request’s Changes opens each changed Markdown file in **Rendered** when the
server can map its Git hunks to the document, and every changed Markdown file has the
**Rendered** | **Source** chooser, whatever its size and whatever the server answers.
The comparison names the route that answers a file’s rendered redline,
`GET github/pull-rendered-diff`, and the route its images load from,
`GET github/pull-image`; the diff plugin spells neither.
Before the reader opens Changes, the page asks for the projections of the Markdown files
among the first eight, at most four, so the first screen finds them computed.

Every Markdown file waits for its rendered view with Source hidden for the app’s loading
delay, 50 ms, so an answer within it paints Rendered first and never replaces Source in
view; past it, Source shows and Rendered replaces it when it arrives.
A file is asked for when it comes within a viewport of the screen, one request at a
time, and its progress mark counts down to visible only while its request waits.
A busy server is transient: the file keeps Rendered and asks again after 100 ms,
doubling to 1.6 s. A file the server refuses shows Source and keeps its chooser, with
Rendered unavailable: the chip says why, as its tooltip and in its accessible name, in
the words of the reason the refusal names or, where it names none, of its status.
Choosing it changes nothing and asks for nothing.
A file whose changes did not load has the chooser too, with Rendered unavailable for the
reason its Source body gives, and no projection is asked for it.
A failed request leaves the file in Source with Rendered to choose, which asks again.
None of these writes anything in the body: nothing but the rendered body is drawn beside
Source. An answer that arrives after the reader chose Source is kept, and choosing
Rendered again shows it without asking.

Front matter is the Document view’s Frontmatter disclosure, keys sorted as it sorts
them: open, with each changed key removed and added, when the front matter changed;
closed, as the Document view’s is, above the body’s changes when it did not; and one
open removed or added row, every key with it, when the file lost or gained it.
Rendered blocks are removed, added, or unchanged, with changed words marked.
Raw HTML, here a centered image, a line break, a key, and a `<details>` around Markdown,
keeps what the server’s sanitizer and the shared allowlist keep of it, as the Document
view does, except that the `<details>` in an added row is open.
A block whose source changed in a way its render does not show, here an HTML comment, is
drawn like any other and never folds, and nothing is drawn to say that Source shows
more: each row is its label and its content, and the session fails on anything else.
Long runs of unchanged blocks fold, and a fold builds its blocks when it opens.
An image of the head keeps its address on the image route.
A link to a file of the head keeps its `/view/` address only while the page shows the
head, which is where that address opens the file; the server’s answer is the same for
every page, and a page that learns another pin is served makes every such link plain
text. Every other local address is dropped before the shared sanitizer.

This browserless session loads the production `builtin_plugins/diff/diff-markdown.js`,
`builtin_plugins/diff/index.js`, and `static/inert-html.js` whole, and plays the
server’s side from `tests/fixtures/diff-markdown-responses.json`: what the production
projection answers for these documents, bound to a pull request’s head, with Python’s
HTML parse of every block, from which the session builds the template a page parses a
block into. `tests/test_diff_markdown_session.py` fails when the recording drifts.
The route itself is pinned by `tests/golden/cli-github-pull-rendered.txt`. The shared
chip family, the stylesheet loader, and the diff’s layout are stand-ins, the page is an
element tree that records what the production code builds, and time is a clock the
session advances by hand.
The plugin mounts the pull request’s comparison on each page the shell renders and hands
the diff its rule for which addresses open there, which this session draws with.

`links.pages` says whether a link to a file of the head opens on each page: pinned at
the comparison’s head, pinned at its merge base, beside a checkout at the head, which
has no pin, and pinned at the head once another tab changed the pin.
`links.opens` says which addresses in a rendered block open something on the page pinned
at the head. Each step lists the requests the page made and each file whose state it
changed: its chooser (`*` chosen, and `unavailable` with the reason for a Rendered that
cannot be chosen), what its body shows (`nothing` while it waits within the loading
delay), `progress` while its mark counts down, and its rendered rows.
The session fails if a file’s chooser is ever gone.

```console
$ node tests/dom/diff-markdown-session.js
{
  "links": {
    "route": "/api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=[STORE]",
    "pages": {
      "pinned at the comparison's head": true,
      "pinned at the merge base": false,
      "beside a checkout at the head, which has no pin": false,
      "pinned at the comparison's head, after another tab changed the pin": false
    },
    "opens": {
      "link /view/g1-ZG9jcw/g1-c2V0dXAubWQ": true,
      "link /view/g1-ZG9jcw/g1-c2V0dXAubWQ#user-content-setup": true,
      "image /api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=[STORE]&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc": true,
      "link /api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=[STORE]&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc": false,
      "image /api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=[STORE]&side=head&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc": false,
      "image /api/plugin/github/pull-image?number=7&left=0aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=[STORE]": false,
      "link /api/tree?path=docs": false
    }
  },
  "steps": [
    {
      "step": "the page asks for the first screen's projections ahead of Changes",
      "asks": [
        "f1",
        "f2",
        "f3",
        "f4"
      ],
      "lookahead": "0px 0px 100% 0px"
    },
    {
      "step": "mount: a Markdown file waits for Rendered with Source hidden; one whose changes did not load shows Source",
      "requests": [],
      "files": {
        "f1 docs/guide.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing"
        },
        "f2 docs/renamed.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing"
        },
        "f3 docs/deep.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing"
        },
        "f4 README.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing"
        },
        "f6 docs/notes.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing"
        },
        "f7 docs/plain.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing"
        },
        "f8 docs/huge.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing"
        },
        "f9 docs/unread.md": {
          "chooser": "Rendered (unavailable: This change is too large to show inline.) | *Source",
          "shows": "source"
        }
      }
    },
    {
      "step": "the first screen asks for its first file; a file away from it shows Source",
      "requests": [
        "f1"
      ],
      "files": {
        "f1 docs/guide.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing",
          "progress": "counting"
        },
        "f3 docs/deep.md": {
          "chooser": "*Rendered | Source",
          "shows": "source"
        },
        "f4 README.md": {
          "chooser": "*Rendered | Source",
          "shows": "source"
        },
        "f6 docs/notes.md": {
          "chooser": "*Rendered | Source",
          "shows": "source"
        },
        "f7 docs/plain.md": {
          "chooser": "*Rendered | Source",
          "shows": "source"
        },
        "f8 docs/huge.md": {
          "chooser": "*Rendered | Source",
          "shows": "source"
        }
      }
    },
    {
      "step": "an answer within the loading delay paints Rendered first",
      "requests": [
        "f2"
      ],
      "files": {
        "f1 docs/guide.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "[Frontmatter, open]",
            "  removed: owner = docs",
            "  added: owner = platform",
            "  context: title = Guide",
            "context: <h1 id=\"user-content-9db1f7c43fe35b9a67d97ca0-new-guide-\">Guide </h1>",
            "removed: <p>Read the <span>setup notes</span> first.</p>",
            "added: <p>Read the <a href=\"/view/g1-ZG9jcw/g1-c2V0dXAubWQ\">first setup notes</a> first.</p>",
            "context: <p>Unchanged paragraph 0.</p>",
            "context: <p>Unchanged paragraph 1.</p>",
            "[5 unchanged blocks]",
            "context: <p>Unchanged paragraph 7.</p>",
            "context: <img loading=\"lazy\" src=\"/api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=[STORE]&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc\" alt=\"Diagram\">",
            "removed: <p>The <del>old</del> closing line.</p>",
            "added: <p>The <ins>new</ins> closing line.</p>"
          ]
        },
        "f2 docs/renamed.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing",
          "progress": "counting"
        }
      }
    },
    {
      "step": "past the loading delay a waiting file shows Source",
      "requests": [],
      "files": {
        "f2 docs/renamed.md": {
          "chooser": "*Rendered | Source",
          "shows": "source",
          "progress": "counting"
        }
      }
    },
    {
      "step": "a file Rendered cannot show stays in Source, and its chooser says why",
      "requests": [],
      "files": {
        "f2 docs/renamed.md": {
          "chooser": "Rendered (unavailable: This file's content did not change.) | *Source",
          "shows": "source"
        }
      }
    },
    {
      "step": "choosing an unavailable Rendered changes nothing and asks for nothing",
      "requests": [],
      "files": {}
    },
    {
      "step": "a busy server keeps Rendered and asks again after a wait",
      "requests": [
        "f3"
      ],
      "files": {}
    },
    {
      "step": "the wait is over",
      "requests": [
        "f3"
      ],
      "files": {
        "f3 docs/deep.md": {
          "chooser": "*Rendered | Source",
          "shows": "source",
          "progress": "counting"
        }
      }
    },
    {
      "step": "a file nested too deeply shows Source and says why; Source chosen while a request runs",
      "requests": [
        "f4"
      ],
      "files": {
        "f3 docs/deep.md": {
          "chooser": "Rendered (unavailable: This file is nested too deeply to show rendered.) | *Source",
          "shows": "source"
        },
        "f4 README.md": {
          "chooser": "Rendered | *Source",
          "shows": "source"
        }
      }
    },
    {
      "step": "the answer is kept, not shown",
      "requests": [],
      "files": {
        "f4 README.md": {
          "chooser": "Rendered | *Source",
          "shows": "source",
          "rows": [
            "added: <p align=\"center\"><img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://example.com/logo.png\" width=\"64\"></p>",
            "added: <h1 id=\"user-content-16979ee89c3406b5dab20e21-new-demo\">Demo</h1>",
            "added: <p>Welcome.<br>Press <kbd>Ctrl</kbd> to begin.</p>",
            "added: <details open=\"\"> <summary>More</summary> <p>The <strong>details</strong>.</p> </details>"
          ]
        }
      }
    },
    {
      "step": "choosing Rendered again shows the kept answer without asking",
      "requests": [],
      "files": {
        "f4 README.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "added: <p align=\"center\"><img loading=\"lazy\" referrerpolicy=\"no-referrer\" src=\"https://example.com/logo.png\" width=\"64\"></p>",
            "added: <h1 id=\"user-content-16979ee89c3406b5dab20e21-new-demo\">Demo</h1>",
            "added: <p>Welcome.<br>Press <kbd>Ctrl</kbd> to begin.</p>",
            "added: <details open=\"\"> <summary>More</summary> <p>The <strong>details</strong>.</p> </details>"
          ]
        }
      }
    },
    {
      "step": "opening a fold builds its blocks",
      "requests": [],
      "files": {
        "f1 docs/guide.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "[Frontmatter, open]",
            "  removed: owner = docs",
            "  added: owner = platform",
            "  context: title = Guide",
            "context: <h1 id=\"user-content-9db1f7c43fe35b9a67d97ca0-new-guide-\">Guide </h1>",
            "removed: <p>Read the <span>setup notes</span> first.</p>",
            "added: <p>Read the <a href=\"/view/g1-ZG9jcw/g1-c2V0dXAubWQ\">first setup notes</a> first.</p>",
            "context: <p>Unchanged paragraph 0.</p>",
            "context: <p>Unchanged paragraph 1.</p>",
            "[5 unchanged blocks, open]",
            "  context: <p>Unchanged paragraph 2.</p>",
            "  context: <p>Unchanged paragraph 3.</p>",
            "  context: <p>Unchanged paragraph 4.</p>",
            "  context: <p>Unchanged paragraph 5.</p>",
            "  context: <p>Unchanged paragraph 6.</p>",
            "context: <p>Unchanged paragraph 7.</p>",
            "context: <img loading=\"lazy\" src=\"/api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=[STORE]&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc\" alt=\"Diagram\">",
            "removed: <p>The <del>old</del> closing line.</p>",
            "added: <p>The <ins>new</ins> closing line.</p>"
          ]
        }
      }
    },
    {
      "step": "switching formats asks for nothing",
      "requests": [],
      "files": {}
    },
    {
      "step": "front matter that did not change is closed above the body's change, and front matter removed is one removed row",
      "requests": [
        "f6",
        "f7"
      ],
      "files": {
        "f6 docs/notes.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "[Frontmatter]",
            "  context: title = Notes",
            "context: <h1 id=\"user-content-53205693cc2502516bbe3652-new-notes\">Notes</h1>",
            "removed: <p>The <del>old</del> body.</p>",
            "added: <p>The <ins>new</ins> body.</p>"
          ]
        },
        "f7 docs/plain.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "[Frontmatter, open, removed]",
            "  removed: draft = True",
            "  removed: title = Plain",
            "context: <h1 id=\"user-content-71ee10c56ecf50774ee672b1-new-plain\">Plain</h1>",
            "context: <p>Text.</p>"
          ]
        }
      }
    },
    {
      "step": "a file past the route's read bound says it is too large; no projection is asked for a file whose changes did not load",
      "requests": [
        "f8"
      ],
      "files": {
        "f8 docs/huge.md": {
          "chooser": "Rendered (unavailable: This file is too large to show rendered.) | *Source",
          "shows": "source"
        }
      }
    },
    {
      "step": "a page that learns another pin is served keeps no link to a file",
      "requests": [],
      "files": {
        "f1 docs/guide.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "[Frontmatter, open]",
            "  removed: owner = docs",
            "  added: owner = platform",
            "  context: title = Guide",
            "context: <h1 id=\"user-content-9db1f7c43fe35b9a67d97ca0-new-guide-\">Guide </h1>",
            "removed: <p>Read the <span>setup notes</span> first.</p>",
            "added: <p>Read the <a>first setup notes</a> first.</p>",
            "context: <p>Unchanged paragraph 0.</p>",
            "context: <p>Unchanged paragraph 1.</p>",
            "[5 unchanged blocks, open]",
            "  context: <p>Unchanged paragraph 2.</p>",
            "  context: <p>Unchanged paragraph 3.</p>",
            "  context: <p>Unchanged paragraph 4.</p>",
            "  context: <p>Unchanged paragraph 5.</p>",
            "  context: <p>Unchanged paragraph 6.</p>",
            "context: <p>Unchanged paragraph 7.</p>",
            "context: <img loading=\"lazy\" src=\"/api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=[STORE]&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc\" alt=\"Diagram\">",
            "removed: <p>The <del>old</del> closing line.</p>",
            "added: <p>The <ins>new</ins> closing line.</p>"
          ]
        }
      }
    },
    {
      "step": "disposal unbinds the chooser and stops every timer",
      "requests": [],
      "files": {}
    },
    {
      "step": "after disposal",
      "unbound": [
        "unbound"
      ],
      "timers": 0
    }
  ]
}
? 0
```

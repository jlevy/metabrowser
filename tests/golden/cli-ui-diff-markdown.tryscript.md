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
server can map its Git hunks to the document.
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
doubling to 1.6 s. An unsupported or over-budget answer leaves the file in Source with
no chooser, and a failed request leaves it in Source with the chooser, so choosing
Rendered asks again.
Neither says so: nothing but the rendered body is drawn beside Source.
An answer that arrives after the reader chose Source is kept, and choosing Rendered
again shows it without asking.

Front matter is the Document view’s Frontmatter disclosure, keys sorted as it sorts
them: open, with each changed key removed and added, when the front matter changed, and
closed, as the Document view’s is, when it did not.
Rendered blocks are removed, added, or unchanged, with changed words marked.
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
changed: its chooser (`*` chosen, `none` when the file can show only Source), what its
body shows (`nothing` while it waits within the loading delay), `progress` while its
mark counts down, and its rendered rows.

```console
$ node tests/dom/diff-markdown-session.js
{
  "links": {
    "route": "/api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=0123456789abcdef",
    "pages": {
      "pinned at the comparison's head": true,
      "pinned at the merge base": false,
      "beside a checkout at the head, which has no pin": false,
      "pinned at the comparison's head, after another tab changed the pin": false
    },
    "opens": {
      "link /view/g1-ZG9jcw/g1-c2V0dXAubWQ": true,
      "link /view/g1-ZG9jcw/g1-c2V0dXAubWQ#user-content-setup": true,
      "image /api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=0123456789abcdef&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc": true,
      "link /api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=0123456789abcdef&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc": false,
      "image /api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=0123456789abcdef&side=head&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc": false,
      "image /api/plugin/github/pull-image?number=7&left=0aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=0123456789abcdef": false,
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
      "step": "mount: every Markdown file waits for Rendered with Source hidden",
      "requests": [],
      "files": {
        "f1 docs/guide.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing"
        },
        "f2 docs/tasks.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing"
        },
        "f3 docs/big.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing"
        },
        "f4 README.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing"
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
        "f3 docs/big.md": {
          "chooser": "*Rendered | Source",
          "shows": "source"
        },
        "f4 README.md": {
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
            "context: <img loading=\"lazy\" src=\"/api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=0123456789abcdef&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc\" alt=\"Diagram\">",
            "removed: <p>The <del>old</del> closing line.</p>",
            "added: <p>The <ins>new</ins> closing line.</p>"
          ]
        },
        "f2 docs/tasks.md": {
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
        "f2 docs/tasks.md": {
          "chooser": "*Rendered | Source",
          "shows": "source",
          "progress": "counting"
        }
      }
    },
    {
      "step": "an unsupported file stays in Source and has no chooser",
      "requests": [],
      "files": {
        "f2 docs/tasks.md": {
          "chooser": "none",
          "shows": "source"
        }
      }
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
        "f3 docs/big.md": {
          "chooser": "*Rendered | Source",
          "shows": "source",
          "progress": "counting"
        }
      }
    },
    {
      "step": "a file over budget shows Source; Source chosen while a request runs",
      "requests": [
        "f4"
      ],
      "files": {
        "f3 docs/big.md": {
          "chooser": "none",
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
            "added: <h1 id=\"user-content-16979ee89c3406b5dab20e21-new-demo\">Demo</h1>",
            "added: <p>Welcome.</p>"
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
            "added: <h1 id=\"user-content-16979ee89c3406b5dab20e21-new-demo\">Demo</h1>",
            "added: <p>Welcome.</p>"
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
            "context: <img loading=\"lazy\" src=\"/api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=0123456789abcdef&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc\" alt=\"Diagram\">",
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
            "context: <img loading=\"lazy\" src=\"/api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=0123456789abcdef&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc\" alt=\"Diagram\">",
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

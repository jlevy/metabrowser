---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
patterns:
  STORE: '[0-9a-f]{16}'
---
# Golden Test: Rendered Markdown in a Pull Request’s Changes

A pull request’s Changes opens changed Markdown files in **Rendered** when the server
can map their Git hunks to the document.
**Rendered | Source** belongs to each file.
The comparison’s presentation sets the rendered coverage.
The comparison names the route that answers a file’s rendered redline,
`GET github/pull-rendered-diff`, and the route its images load from,
`GET github/pull-image`; the diff plugin spells neither.
Before the reader opens Changes, the page asks for the projections of the Markdown files
among the first eight, at most four, so the first screen finds them computed.

Every Markdown file waits for its rendered view with Source hidden for the app’s loading
delay, 50 ms, so an answer within it paints its rendering first and never replaces
Source in view; past it, Source shows and the rendering replaces it when it arrives.
A file is asked for when it comes within a viewport of the screen, one request at a
time, and its progress mark counts down to visible only while its request waits.
A busy server is transient: the file keeps its view and asks again after 100 ms,
doubling to 1.6 s. A file the server refuses shows Source and keeps its chooser.
Rendered is unavailable and gives the reason in its tooltip and accessible name.
A file whose changes did not load has the chooser too, with Rendered unavailable for the
reason its Source body gives, and no projection is asked for it.
A failed request leaves the file in Source with its views to choose, which asks again.
None of these writes anything in the body: nothing but the rendered body is drawn beside
Source. An answer that arrives after the reader chose Source is kept for the next time
they choose Rendered.

Front matter is the Document view’s Frontmatter disclosure, keys sorted as it sorts
them: open, with each changed key removed and added, when the front matter changed;
closed, as the Document view’s is, above the body’s changes when it did not; and one
open removed or added row, every key with it, when the file lost or gained it.
Rendered blocks are removed, added, or unchanged, with changed words marked.
Each run of changed blocks is one change, and each run of one kind in it one run, the
one box that draws its band (`changeRuns`), so a band has no gap between two of its
blocks: the session fails on a changed row outside a run of its kind, two runs of one
kind side by side, or two changes side by side.
Raw HTML, here a centered image, a line break, a key, and a `<details>` around Markdown,
keeps what the server’s sanitizer and the shared allowlist keep of it, as the Document
view does, except that the `<details>` in an added row is open.
A block whose source changed in a way its render does not show, here an HTML comment, is
drawn like any other and never folds, and nothing is drawn to say that Source shows
more: each row is its label and its content, and the session fails on anything else.
In Diff, each long run of unchanged blocks folds behind the diff’s own fold bar, which
builds its blocks when it opens.
A fold of fewer than `INLINE_FOLD_MAX_LINES` source lines comes with the answer, so
opening it asks for nothing; a longer fold’s blocks are withheld, and asked for
(`blocks=`) when it opens or a link goes to a heading inside it, which the page goes to
once they are drawn; the file’s progress mark counts down while they are asked for.
A fold whose blocks do not load closes again, and its bar says so and that a press asks
again. Full draws the new document, asking for any withheld blocks while still showing
the available excerpt.
A failed Full request leaves Source chosen if the reader switched formats.
Returning to Full can retry the request.
Switching back asks for nothing, and the folds the reader opened stay open.
A document past `WHOLE_UNITS` blocks is drawn a chunk at a time: a chunk not drawn yet
keeps the place of its estimated height, and is drawn when the reader comes near it,
joined to the change on either side of it when a run crosses into it, and a link to a
heading in a later chunk draws every chunk through it before it goes there.
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
The route itself is pinned by `tests/golden/cli-github-pull-rendered.txt`, and its views
by `tests/golden/cli-github-pull-rendered-views.txt`. The shared chip family, the
stylesheet loader, and the diff’s layout are stand-ins, the page is an element tree that
records what the production code builds, and time is a clock the session advances by
hand. The plugin mounts the pull request’s comparison on each page the shell renders and
hands the diff its rule for which addresses open there, which this session draws with.

`links.pages` says whether a link to a file of the head opens on each page: pinned at
the comparison’s head, pinned at its merge base, beside a checkout at the head, which
has no pin, and pinned at the head once another tab changed the pin.
`links.opens` says which addresses in a rendered block open something on the page pinned
at the head. Each step lists the requests the page made and each file whose state it
changed: its chooser (`*` chosen, and `unavailable` with the reason for a view that
cannot be chosen), what its body shows (`nothing` while it waits within the loading
delay), `progress` while its mark counts down, and its rendered rows, a fold as its bar
and a chunk not drawn yet as the place it keeps, a long file’s rows shortened to their
first and last four.
The session fails if a file’s chooser is ever gone.
It prints its transcript in two parts, each a block of its own: the links and the steps
before the long document’s, then the long document’s steps on (`long`).

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
      "lookahead": "0px 0px 100% 0px",
      "chunks": "100% 0px 100% 0px"
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
        },
        "f10 docs/long.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing"
        },
        "f11 docs/book.md": {
          "chooser": "*Rendered | Source",
          "shows": "nothing"
        }
      }
    },
    {
      "step": "the first screen asks for its first file; a file away from it shows Source",
      "requests": [
        "f1 view=concise"
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
        },
        "f10 docs/long.md": {
          "chooser": "*Rendered | Source",
          "shows": "source"
        },
        "f11 docs/book.md": {
          "chooser": "*Rendered | Source",
          "shows": "source"
        }
      }
    },
    {
      "step": "an answer within the loading delay paints Rendered first",
      "requests": [
        "f2 view=concise"
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
      "step": "choosing an unavailable view changes nothing and asks for nothing",
      "requests": [],
      "files": {}
    },
    {
      "step": "a busy server keeps Rendered and asks again after a wait",
      "requests": [
        "f3 view=concise"
      ],
      "files": {}
    },
    {
      "step": "the wait is over",
      "requests": [
        "f3 view=concise"
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
        "f4 view=concise"
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
      "files": {}
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
      "step": "opening a fold draws its blocks, which the answer holds",
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
            "[Hide 5 blocks, open]",
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
      "step": "switching formats asks for nothing, and an open fold stays open",
      "requests": [],
      "files": {}
    },
    {
      "step": "expanding unchanged sections draws every block already held",
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
            "context: <p>Unchanged paragraph 2.</p>",
            "context: <p>Unchanged paragraph 3.</p>",
            "context: <p>Unchanged paragraph 4.</p>",
            "context: <p>Unchanged paragraph 5.</p>",
            "context: <p>Unchanged paragraph 6.</p>",
            "context: <p>Unchanged paragraph 7.</p>",
            "context: <img loading=\"lazy\" src=\"/api/plugin/github/pull-image?number=7&left=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&right=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&store=[STORE]&path=g1-ZG9jcw%2Fg1-ZGlhZ3JhbS5wbmc\" alt=\"Diagram\">",
            "removed: <p>The <del>old</del> closing line.</p>",
            "added: <p>The <ins>new</ins> closing line.</p>"
          ]
        }
      }
    },
    {
      "step": "front matter that did not change is closed above the body's change, and front matter removed is one removed row",
      "requests": [
        "f6 view=concise",
        "f7 view=concise"
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
            "removed: <h1 id=\"user-content-71ee10c56ecf50774ee672b1-old-plain\">Plain</h1>",
            "added: <h1 id=\"user-content-71ee10c56ecf50774ee672b1-new-plain-page\">Plain <ins>Page</ins></h1>",
            "context: <p>Text.</p>"
          ]
        }
      }
    },
    {
      "step": "a file past the route's read bound says it is too large; no projection is asked for a file whose changes did not load",
      "requests": [
        "f8 view=concise"
      ],
      "files": {
        "f8 docs/huge.md": {
          "chooser": "Rendered (unavailable: This file is too large to show rendered.) | *Source",
          "shows": "source"
        }
      }
    }
  ]
}
? 0
```

```console
$ node tests/dom/diff-markdown-session.js long
{
  "steps": [
    {
      "step": "Rendered Diff folds a short run with its blocks and withholds the long runs' blocks",
      "requests": [
        "f10 view=concise"
      ],
      "files": {
        "f10 docs/long.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "context: <h1 id=\"user-content-25ebc7ae7b51d35c4452a791-new-long\">Long</h1>",
            "removed: <p>See <span>the deep part</span> <del>now</del>.</p>",
            "added: <p>See <a href=\"#user-content-25ebc7ae7b51d35c4452a791-new-deep-heading\">the deep part</a> <ins>today</ins>.</p>",
            "context: <p>Paragraph 0.</p>",
            "context: <p>Paragraph 1.</p>",
            "[2 unchanged blocks]",
            "context: <p>Paragraph 4.</p>",
            "context: <p>Paragraph 5.</p>",
            "removed: <p>Middle <del>old</del>.</p>",
            "added: <p>Middle <ins>new</ins>.</p>",
            "context: <p>Intro A.</p>",
            "context: <p>Intro B.</p>",
            "[2 unchanged blocks]",
            "context: <p>Outro A.</p>",
            "context: <p>Outro B.</p>",
            "removed: <p>Later <del>old</del>.</p>",
            "added: <p>Later <ins>new</ins>.</p>",
            "context: <p>Note A.</p>",
            "context: <p>Note B.</p>",
            "[2 unchanged blocks]",
            "context: <p>Coda A.</p>",
            "context: <p>Coda B.</p>",
            "removed: <p>The <del>old</del> end.</p>",
            "added: <p>The <ins>new</ins> end.</p>"
          ]
        }
      }
    },
    {
      "step": "opening the short run's fold asks for nothing",
      "requests": [],
      "files": {
        "f10 docs/long.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "context: <h1 id=\"user-content-25ebc7ae7b51d35c4452a791-new-long\">Long</h1>",
            "removed: <p>See <span>the deep part</span> <del>now</del>.</p>",
            "added: <p>See <a href=\"#user-content-25ebc7ae7b51d35c4452a791-new-deep-heading\">the deep part</a> <ins>today</ins>.</p>",
            "context: <p>Paragraph 0.</p>",
            "context: <p>Paragraph 1.</p>",
            "[Hide 2 blocks, open]",
            "  context: <p>Paragraph 2.</p>",
            "  context: <p>Paragraph 3.</p>",
            "context: <p>Paragraph 4.</p>",
            "context: <p>Paragraph 5.</p>",
            "removed: <p>Middle <del>old</del>.</p>",
            "added: <p>Middle <ins>new</ins>.</p>",
            "context: <p>Intro A.</p>",
            "context: <p>Intro B.</p>",
            "[2 unchanged blocks]",
            "context: <p>Outro A.</p>",
            "context: <p>Outro B.</p>",
            "removed: <p>Later <del>old</del>.</p>",
            "added: <p>Later <ins>new</ins>.</p>",
            "context: <p>Note A.</p>",
            "context: <p>Note B.</p>",
            "[2 unchanged blocks]",
            "context: <p>Coda A.</p>",
            "context: <p>Coda B.</p>",
            "removed: <p>The <del>old</del> end.</p>",
            "added: <p>The <ins>new</ins> end.</p>"
          ]
        }
      }
    },
    {
      "step": "a withheld fold asks for its blocks, the file's progress mark counting",
      "requests": [
        "f10 blocks=21-23"
      ],
      "files": {
        "f10 docs/long.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "progress": "counting",
          "folds": [
            "Hide 2 blocks, open",
            "2 unchanged blocks",
            "Hide 2 blocks, open, loading"
          ]
        }
      }
    },
    {
      "step": "blocks that did not load close the fold again, and its bar says so",
      "requests": [],
      "files": {
        "f10 docs/long.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "folds": [
            "Hide 2 blocks, open",
            "2 unchanged blocks",
            "Could not load 2 unchanged blocks. Retry"
          ]
        }
      }
    },
    {
      "step": "the failure is logged, not shown",
      "logged": [
        "metabrowser diff: a fold's blocks did not load"
      ]
    },
    {
      "step": "a press on it asks again",
      "requests": [
        "f10 blocks=21-23"
      ],
      "files": {
        "f10 docs/long.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "progress": "counting",
          "folds": [
            "Hide 2 blocks, open",
            "2 unchanged blocks",
            "Hide 2 blocks, open, loading"
          ]
        }
      }
    },
    {
      "step": "a link to a heading a withheld fold holds waits for it",
      "prevented": true
    },
    {
      "step": "its fold opens and asks for its blocks",
      "requests": [
        "f10 blocks=13-15"
      ],
      "files": {
        "f10 docs/long.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "progress": "counting",
          "rows": [
            "context: <h1 id=\"user-content-25ebc7ae7b51d35c4452a791-new-long\">Long</h1>",
            "removed: <p>See <span>the deep part</span> <del>now</del>.</p>",
            "added: <p>See <a href=\"#user-content-25ebc7ae7b51d35c4452a791-new-deep-heading\">the deep part</a> <ins>today</ins>.</p>",
            "context: <p>Paragraph 0.</p>",
            "context: <p>Paragraph 1.</p>",
            "[Hide 2 blocks, open]",
            "  context: <p>Paragraph 2.</p>",
            "  context: <p>Paragraph 3.</p>",
            "context: <p>Paragraph 4.</p>",
            "context: <p>Paragraph 5.</p>",
            "removed: <p>Middle <del>old</del>.</p>",
            "added: <p>Middle <ins>new</ins>.</p>",
            "context: <p>Intro A.</p>",
            "context: <p>Intro B.</p>",
            "[Hide 2 blocks, open, loading]",
            "context: <p>Outro A.</p>",
            "context: <p>Outro B.</p>",
            "removed: <p>Later <del>old</del>.</p>",
            "added: <p>Later <ins>new</ins>.</p>",
            "context: <p>Note A.</p>",
            "context: <p>Note B.</p>",
            "[Could not load 2 unchanged blocks. Retry]",
            "context: <p>Coda A.</p>",
            "context: <p>Coda B.</p>",
            "removed: <p>The <del>old</del> end.</p>",
            "added: <p>The <ins>new</ins> end.</p>"
          ]
        }
      }
    },
    {
      "step": "its blocks are drawn, and the page goes to the heading",
      "requests": [],
      "files": {
        "f10 docs/long.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "context: <h1 id=\"user-content-25ebc7ae7b51d35c4452a791-new-long\">Long</h1>",
            "removed: <p>See <span>the deep part</span> <del>now</del>.</p>",
            "added: <p>See <a href=\"#user-content-25ebc7ae7b51d35c4452a791-new-deep-heading\">the deep part</a> <ins>today</ins>.</p>",
            "context: <p>Paragraph 0.</p>",
            "context: <p>Paragraph 1.</p>",
            "[Hide 2 blocks, open]",
            "  context: <p>Paragraph 2.</p>",
            "  context: <p>Paragraph 3.</p>",
            "context: <p>Paragraph 4.</p>",
            "context: <p>Paragraph 5.</p>",
            "removed: <p>Middle <del>old</del>.</p>",
            "added: <p>Middle <ins>new</ins>.</p>",
            "context: <p>Intro A.</p>",
            "context: <p>Intro B.</p>",
            "[Hide 2 blocks, open]",
            "  context: <h2 id=\"user-content-25ebc7ae7b51d35c4452a791-new-deep-heading\">Deep heading</h2>",
            "  context: <p>Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line.</p>",
            "context: <p>Outro A.</p>",
            "context: <p>Outro B.</p>",
            "removed: <p>Later <del>old</del>.</p>",
            "added: <p>Later <ins>new</ins>.</p>",
            "context: <p>Note A.</p>",
            "context: <p>Note B.</p>",
            "[Could not load 2 unchanged blocks. Retry]",
            "context: <p>Coda A.</p>",
            "context: <p>Coda B.</p>",
            "removed: <p>The <del>old</del> end.</p>",
            "added: <p>The <ins>new</ins> end.</p>"
          ]
        }
      }
    },
    {
      "step": "scrolled into view",
      "scrolled": [
        {
          "id": "user-content-25ebc7ae7b51d35c4452a791-new-deep-heading",
          "block": "start"
        }
      ]
    },
    {
      "step": "expanding unchanged sections asks for the blocks still withheld",
      "requests": [
        "f10 view=full"
      ],
      "files": {
        "f10 docs/long.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "progress": "counting",
          "rows": [
            "context: <h1 id=\"user-content-25ebc7ae7b51d35c4452a791-new-long\">Long</h1>",
            "removed: <p>See <span>the deep part</span> <del>now</del>.</p>",
            "added: <p>See <a href=\"#user-content-25ebc7ae7b51d35c4452a791-new-deep-heading\">the deep part</a> <ins>today</ins>.</p>",
            "context: <p>Paragraph 0.</p>",
            "context: <p>Paragraph 1.</p>",
            "[Hide 2 blocks, open]",
            "  context: <p>Paragraph 2.</p>",
            "  context: <p>Paragraph 3.</p>",
            "context: <p>Paragraph 4.</p>",
            "context: <p>Paragraph 5.</p>",
            "removed: <p>Middle <del>old</del>.</p>",
            "added: <p>Middle <ins>new</ins>.</p>",
            "context: <p>Intro A.</p>",
            "context: <p>Intro B.</p>",
            "[Hide 2 blocks, open]",
            "  context: <h2 id=\"user-content-25ebc7ae7b51d35c4452a791-new-deep-heading\">Deep heading</h2>",
            "  context: <p>Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line.</p>",
            "context: <p>Outro A.</p>",
            "context: <p>Outro B.</p>",
            "removed: <p>Later <del>old</del>.</p>",
            "added: <p>Later <ins>new</ins>.</p>",
            "context: <p>Note A.</p>",
            "context: <p>Note B.</p>",
            "[Could not load 2 unchanged blocks. Retry]",
            "context: <p>Coda A.</p>",
            "context: <p>Coda B.</p>",
            "removed: <p>The <del>old</del> end.</p>",
            "added: <p>The <ins>new</ins> end.</p>"
          ]
        }
      }
    },
    {
      "step": "Full failing after Source was chosen leaves Source chosen",
      "requests": [],
      "files": {
        "f10 docs/long.md": {
          "chooser": "Rendered | *Source",
          "shows": "source",
          "folds": [
            "Hide 2 blocks, open",
            "Hide 2 blocks, open",
            "Could not load 2 unchanged blocks. Retry"
          ]
        }
      }
    },
    {
      "step": "the failure is logged all the same",
      "logged": [
        "metabrowser diff: Full did not load"
      ]
    },
    {
      "step": "expanding unchanged sections again retries the request",
      "requests": [
        "f10 view=full"
      ],
      "files": {
        "f10 docs/long.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "progress": "counting",
          "folds": [
            "Hide 2 blocks, open",
            "Hide 2 blocks, open",
            "Could not load 2 unchanged blocks. Retry"
          ]
        }
      }
    },
    {
      "step": "Full draws every block once they arrive",
      "requests": [],
      "files": {
        "f10 docs/long.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "context: <h1 id=\"user-content-25ebc7ae7b51d35c4452a791-new-long\">Long</h1>",
            "removed: <p>See <span>the deep part</span> <del>now</del>.</p>",
            "added: <p>See <a href=\"#user-content-25ebc7ae7b51d35c4452a791-new-deep-heading\">the deep part</a> <ins>today</ins>.</p>",
            "context: <p>Paragraph 0.</p>",
            "context: <p>Paragraph 1.</p>",
            "context: <p>Paragraph 2.</p>",
            "context: <p>Paragraph 3.</p>",
            "context: <p>Paragraph 4.</p>",
            "context: <p>Paragraph 5.</p>",
            "removed: <p>Middle <del>old</del>.</p>",
            "added: <p>Middle <ins>new</ins>.</p>",
            "context: <p>Intro A.</p>",
            "context: <p>Intro B.</p>",
            "context: <h2 id=\"user-content-25ebc7ae7b51d35c4452a791-new-deep-heading\">Deep heading</h2>",
            "context: <p>Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line.</p>",
            "context: <p>Outro A.</p>",
            "context: <p>Outro B.</p>",
            "removed: <p>Later <del>old</del>.</p>",
            "added: <p>Later <ins>new</ins>.</p>",
            "context: <p>Note A.</p>",
            "context: <p>Note B.</p>",
            "context: <h2 id=\"user-content-25ebc7ae7b51d35c4452a791-new-appendix\">Appendix</h2>",
            "context: <p>Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row. Row.</p>",
            "context: <p>Coda A.</p>",
            "context: <p>Coda B.</p>",
            "removed: <p>The <del>old</del> end.</p>",
            "added: <p>The <ins>new</ins> end.</p>"
          ]
        }
      }
    },
    {
      "step": "collapsing unchanged sections keeps the folds the reader opened",
      "requests": [],
      "files": {
        "f10 docs/long.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "context: <h1 id=\"user-content-25ebc7ae7b51d35c4452a791-new-long\">Long</h1>",
            "removed: <p>See <span>the deep part</span> <del>now</del>.</p>",
            "added: <p>See <a href=\"#user-content-25ebc7ae7b51d35c4452a791-new-deep-heading\">the deep part</a> <ins>today</ins>.</p>",
            "context: <p>Paragraph 0.</p>",
            "context: <p>Paragraph 1.</p>",
            "[Hide 2 blocks, open]",
            "  context: <p>Paragraph 2.</p>",
            "  context: <p>Paragraph 3.</p>",
            "context: <p>Paragraph 4.</p>",
            "context: <p>Paragraph 5.</p>",
            "removed: <p>Middle <del>old</del>.</p>",
            "added: <p>Middle <ins>new</ins>.</p>",
            "context: <p>Intro A.</p>",
            "context: <p>Intro B.</p>",
            "[Hide 2 blocks, open]",
            "  context: <h2 id=\"user-content-25ebc7ae7b51d35c4452a791-new-deep-heading\">Deep heading</h2>",
            "  context: <p>Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line. Line.</p>",
            "context: <p>Outro A.</p>",
            "context: <p>Outro B.</p>",
            "removed: <p>Later <del>old</del>.</p>",
            "added: <p>Later <ins>new</ins>.</p>",
            "context: <p>Note A.</p>",
            "context: <p>Note B.</p>",
            "[2 unchanged blocks]",
            "context: <p>Coda A.</p>",
            "context: <p>Coda B.</p>",
            "removed: <p>The <del>old</del> end.</p>",
            "added: <p>The <ins>new</ins> end.</p>"
          ]
        }
      }
    },
    {
      "step": "a long document draws its first chunk and keeps the place of the rest",
      "requests": [
        "f11 view=concise"
      ],
      "files": {
        "f11 docs/book.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "added: <p>See <a href=\"#user-content-551f72faeefec8bfd215686a-new-the-last-part\">the last part</a>.</p>",
            "added: <p>Page 0.</p>",
            "added: <p>Page 1.</p>",
            "added: <p>Page 2.</p>",
            "... 98 rows ...",
            "[blocks 300-400 not drawn: 2384px]",
            "[blocks 400-500 not drawn: 2384px]",
            "[blocks 500-600 not drawn: 2384px]",
            "[blocks 600-623 not drawn: 564px]"
          ]
        }
      }
    },
    {
      "step": "coming near a place draws the chunk there",
      "requests": [],
      "files": {
        "f11 docs/book.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "added: <p>See <a href=\"#user-content-551f72faeefec8bfd215686a-new-the-last-part\">the last part</a>.</p>",
            "added: <p>Page 0.</p>",
            "added: <p>Page 1.</p>",
            "added: <p>Page 2.</p>",
            "... 197 rows ...",
            "[blocks 300-400 not drawn: 2384px]",
            "[blocks 400-500 not drawn: 2384px]",
            "[blocks 500-600 not drawn: 2384px]",
            "[blocks 600-623 not drawn: 564px]"
          ]
        }
      }
    },
    {
      "step": "coming near a later place first draws that chunk alone",
      "requests": [],
      "files": {
        "f11 docs/book.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "added: <p>See <a href=\"#user-content-551f72faeefec8bfd215686a-new-the-last-part\">the last part</a>.</p>",
            "added: <p>Page 0.</p>",
            "added: <p>Page 1.</p>",
            "added: <p>Page 2.</p>",
            "... 296 rows ...",
            "added: <p>Page 497.</p>",
            "added: <p>Page 498.</p>",
            "[blocks 500-600 not drawn: 2384px]",
            "[blocks 600-623 not drawn: 564px]"
          ]
        }
      }
    },
    {
      "step": "a link into a chunk not drawn yet",
      "prevented": false
    },
    {
      "step": "draws every chunk through it, and the link goes there",
      "requests": [],
      "files": {
        "f11 docs/book.md": {
          "chooser": "*Rendered | Source",
          "shows": "rendered",
          "rows": [
            "added: <p>See <a href=\"#user-content-551f72faeefec8bfd215686a-new-the-last-part\">the last part</a>.</p>",
            "added: <p>Page 0.</p>",
            "added: <p>Page 1.</p>",
            "added: <p>Page 2.</p>",
            "... 615 rows ...",
            "added: <p>Page 618.</p>",
            "added: <p>Page 619.</p>",
            "added: <h2 id=\"user-content-551f72faeefec8bfd215686a-new-the-last-part\">The last part</h2>",
            "added: <p>The end.</p>"
          ]
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
            "context: <p>Unchanged paragraph 2.</p>",
            "context: <p>Unchanged paragraph 3.</p>",
            "context: <p>Unchanged paragraph 4.</p>",
            "context: <p>Unchanged paragraph 5.</p>",
            "context: <p>Unchanged paragraph 6.</p>",
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

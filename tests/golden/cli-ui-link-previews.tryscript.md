---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Link Card

A link in rendered text that opens a page in Metabrowser shows the link card on pointer
rest: what kind of object it opens and which, its title where the app knows it, and
where it opens ([Tooltips on Links](../../docs/design-system.md#tooltips-on-links)). One
module, `static/link-previews.js`, holds the registry of such links by identity, one
delegated pointer listener per root, the intent timer, the providers’ reads and
prefetches, and the one renderer, `card`.

This session runs the exact module whole, beside `static/formatters.js` and the
`repository-links` bundle’s `static/git-path.js` and `static/repository-links.js`. The
page’s tooltip is app.js’s own code, lifted verbatim, on this file’s clock.
The SDK’s glyph owners are stand-ins whose glyphs name themselves, so a card’s compact
form leads with the glyph it asked for in brackets: `[pull]` for the neutral pull
request mark that `decorateExternalLink` draws, `[merged]` and the other states for the
github plugin’s `pullStateIcon`, `[layers]` for a stack, and a file’s type.
Each log entry says when, in milliseconds, the module asked the tooltip to `show` or
`hide`, a provider was asked for a `summary` or a `prefetch`, a plugin was loaded, or
the session read the `tooltip` the reader would see.

- `subjects` is what `subject` reads from the resolver’s answers: a pull request, its
  Changes and Checks, a changed file of a pull request’s text and of a stack’s note, a
  commit, the pull request list, a file or folder by a branch’s link, which opens in the
  served working tree, or by the served commit’s, and the root.
  A pin’s GitPath wire decodes to the same path, by the page’s source kind, and so does
  a rendered diff’s head link; a name that is not text, an anchor that does not decode,
  another site, and a malformed route name nothing.
  A file’s or folder’s subject keeps the navigation target as the address spelled it,
  the resolver’s own or a head link’s wire path with its fragment decoded, for a
  provider to look up and open.
- `cards` is what `card` draws for each kind with and without a provider’s data.
  A line that is the link’s own text, in any case and spacing, or a line above is left
  out, and the first line kept leads with the mark.
  The last line says where the link opens, or what the provider says is missing.
  A provider’s text is escaped, and an answer that is not data is none.
- `states`: a pull request’s state glyph is drawn only where its summary gives the
  state, once the github plugin’s glyphs have loaded, which the first such summary asks
  for.
- `timing`: the card is asked for at once and appears on the tooltip’s own 300 ms delay;
  the summary and the prefetch start at 250 ms, the tree’s hover delay.
  An answer that arrives while the tooltip still waits is shown with it, which waits the
  delay again from then; a later one is the provider’s to keep, and the next rest’s card
  says it from the pointer’s arrival (`known`), when the provider answers its summary at
  once (`kept`); a pass across a link reads nothing, and moving within it changes
  nothing.
- `requests`: one read and one prefetch are in flight; a newer rest waits for them
  rather than aborting them, and a link the pointer leaves before its intent delay is
  never read.
- `modality`: focus, keys, and a touch show no card; a pen’s rest does.
  A Tab or a click onto the link the pointer rests on, while its read is out, ends the
  rest: the read’s answer and the state glyphs it loads bring no card back.
- `failures`: the registry keeps no answer, so a provider that throws, rejects, or
  answers null is asked again at the next rest, and one that knew nothing at the first
  rest says what it knows at the next; each card still says where the link opens.
- `disposal`: `dispose` puts away its own root’s card and leaves another root’s; a
  disposed root shows no card; a later `register` of the link asks for its card again,
  which a card already up does not take, and `forget` puts the card away.

```console
$ node tests/dom/link-previews-session.js
{
 "subjects": [
  {
   "label": "a pull request",
   "subject": {
    "kind": "pull",
    "number": 12,
    "tab": "",
    "file": ""
   }
  },
  {
   "label": "its Changes",
   "subject": {
    "kind": "pull",
    "number": 12,
    "tab": "files",
    "file": ""
   }
  },
  {
   "label": "its Checks",
   "subject": {
    "kind": "pull",
    "number": 12,
    "tab": "checks",
    "file": ""
   }
  },
  {
   "label": "a changed file in a pull request's text",
   "subject": {
    "kind": "pull",
    "number": 7,
    "tab": "files",
    "file": "src/app.py"
   }
  },
  {
   "label": "a changed file in a stack's note",
   "subject": {
    "kind": "stack",
    "number": 3,
    "file": "src/app.py"
   }
  },
  {
   "label": "a commit",
   "subject": {
    "kind": "commit",
    "revision": "0123456789abcdef0123456789abcdef01234567"
   }
  },
  {
   "label": "the pull request list",
   "subject": {
    "kind": "pulls"
   }
  },
  {
   "label": "a file on the served branch",
   "subject": {
    "kind": "file",
    "path": "docs/guide.md",
    "opens": "working-tree",
    "target": {
     "path": "docs/guide.md"
    }
   }
  },
  {
   "label": "a file at the served commit",
   "subject": {
    "kind": "file",
    "path": "docs/guide.md",
    "opens": "here",
    "target": {
     "path": "docs/guide.md"
    }
   }
  },
  {
   "label": "a folder on the served branch",
   "subject": {
    "kind": "folder",
    "path": "docs",
    "opens": "working-tree",
    "target": {
     "path": "docs/"
    }
   }
  },
  {
   "label": "the repository",
   "subject": {
    "kind": "folder",
    "path": "",
    "opens": "working-tree",
    "target": {
     "path": ""
    }
   }
  },
  {
   "label": "a name holding %",
   "subject": {
    "kind": "file",
    "path": "docs/100%.md",
    "opens": "working-tree",
    "target": {
     "path": "docs/100%25.md"
    }
   }
  },
  {
   "label": "a file with a query and an anchor",
   "subject": {
    "kind": "file",
    "path": "docs/guide.md",
    "opens": "working-tree",
    "target": {
     "path": "docs/guide.md",
     "query": "plain=1",
     "fragment": "install"
    }
   }
  },
  {
   "label": "a pin's address for it",
   "path": "g1-ZG9jcw/g1-Z3VpZGUubWQ"
  },
  {
   "label": "the same file on the pin",
   "subject": {
    "kind": "file",
    "path": "docs/guide.md",
    "opens": "here",
    "target": {
     "path": "g1-ZG9jcw/g1-Z3VpZGUubWQ"
    }
   }
  },
  {
   "label": "a pin's folder",
   "subject": {
    "kind": "folder",
    "path": "docs",
    "opens": "here",
    "target": {
     "path": "g1-ZG9jcw/"
    }
   }
  },
  {
   "label": "a pin's folder read as a folder's",
   "subject": {
    "kind": "folder",
    "path": "g1-ZG9jcw",
    "opens": "here",
    "target": {
     "path": "g1-ZG9jcw/"
    }
   }
  },
  {
   "label": "a rendered diff's head link",
   "subject": {
    "kind": "file",
    "path": "docs/guide.md",
    "opens": "here",
    "target": {
     "path": "g1-ZG9jcw/g1-Z3VpZGUubWQ",
     "fragment": "install"
    }
   }
  },
  {
   "label": "a head link with an escaped anchor",
   "subject": {
    "kind": "file",
    "path": "docs/guide.md",
    "opens": "here",
    "target": {
     "path": "g1-ZG9jcw/g1-Z3VpZGUubWQ",
     "fragment": "über-uns"
    }
   }
  },
  {
   "label": "a head link whose anchor does not decode",
   "subject": null
  },
  {
   "label": "a head link whose name is not text",
   "subject": null
  },
  {
   "label": "a head link that is not a file's",
   "subject": null
  },
  {
   "label": "a link to another site",
   "subject": null
  },
  {
   "label": "a pull request numbered 0",
   "subject": null
  },
  {
   "label": "a commit by a short ID",
   "subject": null
  },
  {
   "label": "nothing",
   "subject": null
  },
  {
   "label": "the same file on the pin, as the page's source kind reads it",
   "subject": {
    "kind": "file",
    "path": "docs/guide.md",
    "opens": "here",
    "target": {
     "path": "g1-ZG9jcw/g1-Z3VpZGUubWQ"
    }
   }
  }
 ],
 "cards": [
  {
   "label": "a pull request, no data",
   "linkText": "#12",
   "preview": null,
   "html": "<div class=\"tip-name link-card-name\"><span class=\"link-card-mark\" aria-hidden=\"true\"><svg data-glyph=\"pull\"></svg></span><span>Pull request #12</span></div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "a pull request, its title and state",
   "linkText": "#12",
   "preview": {
    "title": "fix(parser): keep a heading's trailing text",
    "state": "merged"
   },
   "html": "<div class=\"tip-name link-card-name\"><span class=\"link-card-mark\" aria-hidden=\"true\"><span class=\"github-pull-state-icon\" data-state=\"merged\" aria-hidden=\"true\"><svg data-glyph=\"merged\"></svg></span></span><span>Pull request #12</span></div><div class=\"link-card-title\"><span class=\"title-prefix\">fix(parser):</span> keep a heading&#39;s trailing text</div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "its Changes at a file",
   "linkText": "the guide",
   "preview": {
    "title": "fix(parser): keep a heading's trailing text",
    "state": "open"
   },
   "html": "<div class=\"tip-name link-card-name\"><span class=\"link-card-mark\" aria-hidden=\"true\"><span class=\"github-pull-state-icon\" data-state=\"open\" aria-hidden=\"true\"><svg data-glyph=\"open\"></svg></span></span><span>Pull request #12 · Changes · docs/guide.md</span></div><div class=\"link-card-title\"><span class=\"title-prefix\">fix(parser):</span> keep a heading&#39;s trailing text</div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "its Checks",
   "linkText": "the checks",
   "preview": null,
   "html": "<div class=\"tip-name link-card-name\"><span class=\"link-card-mark\" aria-hidden=\"true\"><svg data-glyph=\"pull\"></svg></span><span>Pull request #12 · Checks</span></div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "a stack's changed file, no data",
   "linkText": "app.py",
   "preview": null,
   "html": "<div class=\"tip-name link-card-name\"><span class=\"link-card-mark\" aria-hidden=\"true\"><svg data-glyph=\"layers\"></svg></span><span>Stack #3 · Changes · src/app.py</span></div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "a stack's changed file, its top's title",
   "linkText": "app.py",
   "preview": {
    "title": "Stack the parser"
   },
   "html": "<div class=\"tip-name link-card-name\"><span class=\"link-card-mark\" aria-hidden=\"true\"><svg data-glyph=\"layers\"></svg></span><span>Stack #3 · Changes · src/app.py</span></div><div class=\"link-card-title\">Stack the parser</div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "a commit, no data",
   "linkText": "this commit",
   "preview": null,
   "html": "<div class=\"tip-name\">Commit <span class=\"git-commit-sha\">0123456</span></div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "a commit, its subject and author",
   "linkText": "it",
   "preview": {
    "title": "fix(parser): keep a heading's trailing text",
    "detail": "Ada · 3 days ago"
   },
   "html": "<div class=\"tip-name\">Commit <span class=\"git-commit-sha\">0123456</span></div><div class=\"link-card-title\"><span class=\"title-prefix\">fix(parser):</span> keep a heading&#39;s trailing text</div><div class=\"tip-detail\">Ada · 3 days ago</div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "a commit the repository lacks",
   "linkText": "it",
   "preview": {
    "missing": "Not in this repository"
   },
   "html": "<div class=\"tip-name\">Commit <span class=\"git-commit-sha\">0123456</span></div><div class=\"tip-detail\">Not in this repository</div>"
  },
  {
   "label": "a file, no data",
   "linkText": "the guide",
   "preview": null,
   "html": "<div class=\"tip-name link-card-name\"><span class=\"link-card-mark file-identity-icon ft-md\" aria-hidden=\"true\"><svg data-glyph=\"md\"></svg></span><span>docs/guide.md</span></div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "a file, its title",
   "linkText": "read this",
   "preview": {
    "title": "The Guide"
   },
   "html": "<div class=\"tip-name link-card-name\"><span class=\"link-card-mark file-identity-icon ft-md\" aria-hidden=\"true\"><svg data-glyph=\"md\"></svg></span><span>docs/guide.md</span></div><div class=\"link-card-title\">The Guide</div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "a file on the served branch",
   "linkText": "the guide",
   "preview": null,
   "html": "<div class=\"tip-name link-card-name\"><span class=\"link-card-mark file-identity-icon ft-md\" aria-hidden=\"true\"><svg data-glyph=\"md\"></svg></span><span>docs/guide.md</span></div><div class=\"tip-detail\">Opens in the served working tree</div>"
  },
  {
   "label": "a folder",
   "linkText": "the docs",
   "preview": {
    "detail": "12 files · 3.4 KB"
   },
   "html": "<div class=\"tip-name\">docs/</div><div class=\"tip-detail\">12 files · 3.4 KB</div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "the root, from a branch's link",
   "linkText": "the repository",
   "preview": null,
   "html": "<div class=\"tip-name\">/</div><div class=\"tip-detail\">Opens in the served working tree</div>"
  },
  {
   "label": "the pull request list",
   "linkText": "open pull requests",
   "preview": null,
   "html": "<div class=\"tip-name\">Pull requests</div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "a title with markup",
   "linkText": "#12",
   "preview": {
    "title": "<img src=x onerror=\"go()\"> & 'q'"
   },
   "html": "<div class=\"tip-name link-card-name\"><span class=\"link-card-mark\" aria-hidden=\"true\"><svg data-glyph=\"pull\"></svg></span><span>Pull request #12</span></div><div class=\"link-card-title\">&lt;img src=x onerror=&quot;go()&quot;&gt; &amp; &#39;q&#39;</div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "an answer that is not data",
   "linkText": "#12",
   "preview": "<b>bold</b>",
   "html": "<div class=\"tip-name link-card-name\"><span class=\"link-card-mark\" aria-hidden=\"true\"><svg data-glyph=\"pull\"></svg></span><span>Pull request #12</span></div><div class=\"tip-detail\">Opens here in Metabrowser</div>"
  },
  {
   "label": "an author's title, no object title",
   "linkText": "#12",
   "preview": null,
   "authorTitle": "Read this first",
   "text": "[pull] Pull request #12 | Read this first | Opens here in Metabrowser"
  },
  {
   "label": "an author's title beside the object's",
   "linkText": "#12",
   "preview": {
    "title": "fix(parser): keep a heading's trailing text"
   },
   "authorTitle": "Read this first",
   "text": "[pull] Pull request #12 | fix(parser): keep a heading's trailing text | Read this first | Opens here in Metabrowser"
  },
  {
   "label": "an author's title that is the object's",
   "linkText": "#12",
   "preview": {
    "title": "fix(parser): keep a heading's trailing text"
   },
   "authorTitle": "FIX(PARSER): KEEP A HEADING'S TRAILING TEXT",
   "text": "[pull] Pull request #12 | fix(parser): keep a heading's trailing text | Opens here in Metabrowser"
  },
  {
   "label": "the link's text is the title",
   "linkText": "  FIX(parser): keep a heading's\ntrailing text ",
   "text": "[pull] Pull request #12 | Opens here in Metabrowser"
  },
  {
   "label": "the link's text is the path",
   "linkText": "docs/guide.md",
   "text": "[md] The Guide | Opens here in Metabrowser"
  },
  {
   "label": "the link's text is the identity",
   "linkText": "Pull request #12",
   "text": "[draft] fix(parser): keep a heading's trailing text | Opens here in Metabrowser"
  },
  {
   "label": "the link's text is the subject",
   "linkText": "fix(parser): keep a heading's trailing text",
   "text": "Commit 0123456 | Opens here in Metabrowser"
  },
  {
   "label": "not a subject",
   "html": ""
  }
 ],
 "states": {
  "beforeTheGlyphsLoad": "[pull] Pull request #12 | Opens here in Metabrowser",
  "rest": [
   {
    "at": 0,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 250,
    "summary": "pull 12"
   },
   {
    "at": 250,
    "prefetch": "pull 12"
   },
   {
    "at": 251,
    "load": "github"
   },
   {
    "at": 251,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Keep the tail | Opens here in Metabrowser"
   },
   {
    "at": 256,
    "show": "twelve",
    "card": "[merged] Pull request #12 | Keep the tail | Opens here in Metabrowser"
   },
   {
    "at": 600,
    "tooltip": "[merged] Pull request #12 | Keep the tail | Opens here in Metabrowser"
   }
  ],
  "after": {
   "no data": "[pull] Pull request #12 | Opens here in Metabrowser",
   "a title alone": "[pull] Pull request #12 | Untold | Opens here in Metabrowser",
   "a draft": "[draft] Pull request #12 | Opens here in Metabrowser",
   "a state the card does not know": "[pull] Pull request #12 | Opens here in Metabrowser"
  }
 },
 "timing": {
  "no provider: the card at the tooltip's own delay": [
   {
    "at": 0,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 299,
    "tooltip": null
   },
   {
    "at": 320,
    "tooltip": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 400,
    "hide": "twelve"
   }
  ],
  "an answer during the delay: the card waits for it": [
   {
    "at": 0,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 250,
    "summary": "pull 12"
   },
   {
    "at": 250,
    "prefetch": "pull 12"
   },
   {
    "at": 251,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Keep the tail | Opens here in Metabrowser"
   },
   {
    "at": 320,
    "tooltip": null
   },
   {
    "at": 570,
    "tooltip": "[pull] Pull request #12 | Keep the tail | Opens here in Metabrowser"
   },
   {
    "at": 700,
    "hide": "twelve"
   }
  ],
  "a late answer: kept for the next rest": [
   {
    "at": 0,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 250,
    "summary": "pull 12"
   },
   {
    "at": 250,
    "prefetch": "pull 12"
   },
   {
    "at": 320,
    "tooltip": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 350,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Keep the tail | Opens here in Metabrowser"
   },
   {
    "at": 400,
    "tooltip": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 450,
    "hide": "twelve"
   },
   {
    "at": 600,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Keep the tail | Opens here in Metabrowser"
   },
   {
    "at": 850,
    "summary": "pull 12",
    "kept": true
   },
   {
    "at": 850,
    "prefetch": "pull 12"
   },
   {
    "at": 920,
    "tooltip": "[pull] Pull request #12 | Keep the tail | Opens here in Metabrowser"
   },
   {
    "at": 1000,
    "hide": "twelve"
   }
  ],
  "a pass across the link: nothing is read": [
   {
    "at": 0,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 100,
    "hide": "twelve"
   },
   {
    "at": 500,
    "tooltip": null
   }
  ],
  "moving within the link: nothing changes": [
   {
    "at": 0,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 250,
    "summary": "pull 12"
   },
   {
    "at": 250,
    "prefetch": "pull 12"
   },
   {
    "at": 251,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Keep the tail | Opens here in Metabrowser"
   },
   {
    "at": 570,
    "tooltip": "[pull] Pull request #12 | Keep the tail | Opens here in Metabrowser"
   }
  ]
 },
 "requests": {
  "log": [
   {
    "at": 0,
    "show": "one",
    "card": "[pull] Pull request #1 | Opens here in Metabrowser"
   },
   {
    "at": 250,
    "summary": "pull 1"
   },
   {
    "at": 250,
    "prefetch": "pull 1"
   },
   {
    "at": 300,
    "hide": "one"
   },
   {
    "at": 300,
    "show": "two",
    "card": "[pull] Pull request #2 | Opens here in Metabrowser"
   },
   {
    "at": 650,
    "summary": "pull 2"
   },
   {
    "at": 650,
    "prefetch": "pull 2"
   },
   {
    "at": 980,
    "tooltip": "[pull] Pull request #2 | Opens here in Metabrowser"
   },
   {
    "at": 1000,
    "hide": "two"
   },
   {
    "at": 1000,
    "show": "three",
    "card": "[pull] Pull request #3 | Opens here in Metabrowser"
   },
   {
    "at": 1100,
    "hide": "three"
   },
   {
    "at": 2000,
    "tooltip": null
   }
  ],
  "counts": {
   "reads": 0,
   "prefetches": 0,
   "maxReads": 1,
   "maxPrefetches": 1,
   "signals": 0
  }
 },
 "modality": {
  "focus, keys, and a touch": [
   {
    "at": 600,
    "tooltip": null
   }
  ],
  "then a pen": [
   {
    "at": 800,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 1050,
    "summary": "pull 12"
   },
   {
    "at": 1050,
    "prefetch": "pull 12"
   },
   {
    "at": 1051,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Keep the tail | Opens here in Metabrowser"
   },
   {
    "at": 1400,
    "tooltip": "[pull] Pull request #12 | Keep the tail | Opens here in Metabrowser"
   }
  ],
  "focus during the read": [
   {
    "at": 0,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 250,
    "summary": "pull 12"
   },
   {
    "at": 250,
    "prefetch": "pull 12"
   },
   {
    "at": 260,
    "focus": "twelve"
   },
   {
    "at": 280,
    "tooltip": null
   },
   {
    "at": 290,
    "load": "github"
   },
   {
    "at": 1000,
    "tooltip": null
   }
  ],
  "a press during the read": [
   {
    "at": 0,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 250,
    "summary": "pull 12"
   },
   {
    "at": 250,
    "prefetch": "pull 12"
   },
   {
    "at": 260,
    "press": "twelve"
   },
   {
    "at": 280,
    "tooltip": null
   },
   {
    "at": 290,
    "load": "github"
   },
   {
    "at": 1000,
    "tooltip": null
   }
  ]
 },
 "failures": {
  "a provider that throws": {
   "asked": 2,
   "cards": [
    "Commit 0123456 | Opens here in Metabrowser",
    "Commit 0123456 | Opens here in Metabrowser"
   ],
   "warnings": [
    "metabrowser: a link's summary was not read: no record",
    "metabrowser: a link's summary was not read: no record"
   ]
  },
  "a provider that rejects": {
   "asked": 2,
   "cards": [
    "Commit 0123456 | Opens here in Metabrowser",
    "Commit 0123456 | Opens here in Metabrowser"
   ],
   "warnings": [
    "metabrowser: a link's summary was not read: offline",
    "metabrowser: a link's summary was not read: offline"
   ]
  },
  "a provider that answers null": {
   "asked": 2,
   "cards": [
    "Commit 0123456 | Opens here in Metabrowser",
    "Commit 0123456 | Opens here in Metabrowser"
   ],
   "warnings": []
  },
  "a provider that answers null, then a subject": {
   "asked": 2,
   "cards": [
    "Commit 0123456 | Opens here in Metabrowser",
    "Commit 0123456 | Found at the second rest | Opens here in Metabrowser"
   ],
   "warnings": []
  }
 },
 "disposal": {
  "dispose": [
   {
    "at": 0,
    "show": "guide",
    "card": "[md] docs/guide.md | Opens here in Metabrowser"
   },
   {
    "at": 320,
    "tooltip": "[md] docs/guide.md | Opens here in Metabrowser"
   },
   {
    "at": 320,
    "hide": "comment"
   },
   {
    "at": 340,
    "tooltip": "[md] docs/guide.md | Opens here in Metabrowser"
   },
   {
    "at": 340,
    "hide": "readme"
   },
   {
    "at": 600,
    "tooltip": null
   },
   {
    "at": 1200,
    "tooltip": null
   }
  ],
  "register again, then forget": [
   {
    "at": 1300,
    "show": "twelve",
    "card": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 1620,
    "tooltip": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 1620,
    "show": "twelve",
    "card": "[pull] Pull request #12 · Checks | Opens here in Metabrowser"
   },
   {
    "at": 1640,
    "tooltip": "[pull] Pull request #12 | Opens here in Metabrowser"
   },
   {
    "at": 1640,
    "hide": "twelve"
   },
   {
    "at": 1900,
    "tooltip": null
   }
  ]
 }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

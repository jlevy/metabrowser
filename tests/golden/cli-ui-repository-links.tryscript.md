---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: What a Link in Rendered Text Opens

Every surface that shows authored text decides its links with one module,
`static/repository-links.js`: a Markdown file and a folder’s README, a pull request’s
description, comments, reviews, and Guided Review notes, a commit’s message, and
Markdown rendered in a diff.
A `github.com` link into the served repository opens its page in Metabrowser when one
exists here and shows the same thing; anything else stays the link it was.
The
[in-app link resolution plan](../../docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md)
is the design.

This session loads the exact production module whole, beside `static/git-path.js`, the
GitPath codec a pinned revision’s shell loads first.
`localized` reads one table of URLs in each context a page can have and prints what
`localize` answers: a `view` target, a `/view/` address of the served tree; a `route`, a
pull request’s page or tab, a commit’s, or the list’s; an `external` replacement; or
null, for a link left as written.

- `checkout` is a folder on the branch `feature/navigation`, whose name holds a slash.
  A file or folder on that branch or at its commit opens in place, and so does the
  repository’s root; a pull request, its Changes and Checks, one of its commits, a
  commit by its full ID, and the pull request list open their pages.
  Another branch, a tag, an abbreviated commit, an issue, a comparison, a comment’s
  fragment, a query the page would lose, another repository or host, an owner spelled
  with a sign that folds to a letter, and a malformed address stay external, a query
  with a `%` that starts no escape among them, since the navigation codec cannot spell
  it.
- `subfolder` serves `packages/handbook` of the same checkout: a path outside it, the
  repository’s root among them, stays external.
- `pin` is a mirror pinned at `main`, whose addresses spell each path in the GitPath
  wire.
- The three text contexts are a pull request’s text, whose links the server resolved
  against the pull request’s page: an address under `pull/` that is not a pull
  request’s, which is what a path-relative reference becomes there, names the head’s
  file. It opens in place when the served tree is the head and serves the path, in the
  pull request’s or stack’s Changes when its comparison changes the file, as the file on
  github.com at the head otherwise, and stays as written while the head is not known.
  GitHub’s `new`, the page that opens a pull request, and a number followed by nothing
  or one of a pull request’s pages, are pull requests’ addresses; a folder named with
  digits is a folder.

`viewFiles` is what a rendered diff’s link to a file of the head, a pin’s
`/view/<GitPath wire>` address, opens on github.com at the head when the page does not
show it (`viewFileUrl`): the file the wire names, and nothing for a name that is not
text or an address that is not a pin’s.

`enhanced` runs `enhance` over four links of an inert text, as a pull request’s page and
a commit’s page call it, and clicks each plainly and with a modifier.
An in-app link loses the new tab the allowlist gave it; a plain click on a `/view/`
target opens it through `metabrowser.navigation.open`, a pull request’s page opens
another in place through the page’s own router, and every other click is the browser’s.
A text read again once the page knows the files its pull request changes reads each link
as the text wrote it, which the first pass kept, and moves the link’s one click handler
to the new answer, so each in-app link has one listener (`listeners`), even one that
goes outside while its head moves past its files and comes back when the new files
arrive. A commit’s message has no text context, so its path-relative reference stays as
written. `tests/test_repository_links_js.py` holds these answers to the server’s own
reading of the same URLs.

```console
$ node tests/dom/repository-links-session.js
{
  "localized": {
    "checkout": [
      {
        "label": "the repository",
        "url": "https://github.com/example/docs",
        "result": {
          "kind": "view",
          "target": {
            "path": ""
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "the repository, its README's heading, as GitHub spells it",
        "url": "https://github.com/example/docs#install",
        "result": {
          "kind": "view",
          "target": {
            "path": "",
            "fragment": "install"
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "the repository, any case, .git, www",
        "url": "https://www.github.com/Example/Docs.git/",
        "result": {
          "kind": "view",
          "target": {
            "path": ""
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "the repository with a query",
        "url": "https://github.com/example/docs?tab=readme",
        "result": null
      },
      {
        "label": "the repository's README, as its anchors copy",
        "url": "https://github.com/example/docs?tab=readme-ov-file#install",
        "result": {
          "kind": "view",
          "target": {
            "path": "",
            "fragment": "install"
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "a file on the served branch",
        "url": "https://github.com/example/docs/blob/feature/navigation/guide/intro.md#Setup",
        "result": {
          "kind": "view",
          "target": {
            "path": "guide/intro.md",
            "fragment": "Setup"
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "a file shown as source",
        "url": "https://github.com/example/docs/blob/feature/navigation/src/app.py?plain=1#L3-L5",
        "result": {
          "kind": "view",
          "target": {
            "path": "src/app.py",
            "query": "plain=1",
            "fragment": "L3-L5"
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "a folder on the served branch",
        "url": "https://github.com/example/docs/tree/feature/navigation/guide",
        "result": {
          "kind": "view",
          "target": {
            "path": "guide/"
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "the served branch's root",
        "url": "https://github.com/example/docs/tree/feature/navigation",
        "result": {
          "kind": "view",
          "target": {
            "path": ""
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "a file at the served commit",
        "url": "https://github.com/example/docs/blob/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/guide/intro.md",
        "result": {
          "kind": "view",
          "target": {
            "path": "guide/intro.md"
          },
          "localization": "revision"
        }
      },
      {
        "label": "the served commit's root",
        "url": "https://github.com/example/docs/tree/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "result": {
          "kind": "view",
          "target": {
            "path": ""
          },
          "localization": "revision"
        }
      },
      {
        "label": "a name with a percent sign",
        "url": "https://github.com/example/docs/blob/feature/navigation/100%25.md",
        "result": {
          "kind": "view",
          "target": {
            "path": "100%25.md"
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "a file on another branch",
        "url": "https://github.com/example/docs/blob/main/guide/intro.md",
        "result": null
      },
      {
        "label": "a file at another commit",
        "url": "https://github.com/example/docs/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/guide/intro.md",
        "result": null
      },
      {
        "label": "a file at the served commit, abbreviated",
        "url": "https://github.com/example/docs/blob/aaaaaaa/guide/intro.md",
        "result": {
          "kind": "view",
          "target": {
            "path": "guide/intro.md"
          },
          "localization": "revision"
        }
      },
      {
        "label": "a file at another commit, abbreviated",
        "url": "https://github.com/example/docs/blob/bbbbbbb/guide/intro.md",
        "result": null
      },
      {
        "label": "a file at a tag",
        "url": "https://github.com/example/docs/blob/v1.2.3/guide/intro.md",
        "result": null
      },
      {
        "label": "a blob naming only the branch",
        "url": "https://github.com/example/docs/blob/feature/navigation",
        "result": null
      },
      {
        "label": "a pull request",
        "url": "https://github.com/example/docs/pull/12",
        "result": {
          "kind": "route",
          "href": "/pull/12",
          "localization": "pull",
          "pull": {
            "number": 12,
            "tab": "",
            "file": "",
            "stack": false
          }
        }
      },
      {
        "label": "its Changes",
        "url": "https://github.com/example/docs/pull/12/files",
        "result": {
          "kind": "route",
          "href": "/pull/12/files",
          "localization": "pull",
          "pull": {
            "number": 12,
            "tab": "files",
            "file": "",
            "stack": false
          }
        }
      },
      {
        "label": "its Changes, at one file and line",
        "url": "https://github.com/example/docs/pull/12/changes#diff-0000000000000000000000000000000000000000000000000000000000000000R3",
        "result": null
      },
      {
        "label": "its Checks",
        "url": "https://github.com/example/docs/pull/12/checks",
        "result": {
          "kind": "route",
          "href": "/pull/12/checks",
          "localization": "pull",
          "pull": {
            "number": 12,
            "tab": "checks",
            "file": "",
            "stack": false
          }
        }
      },
      {
        "label": "one of its commits",
        "url": "https://github.com/example/docs/pull/12/commits/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "result": {
          "kind": "route",
          "href": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
          "localization": "commit",
          "pull": null
        }
      },
      {
        "label": "its commit list",
        "url": "https://github.com/example/docs/pull/12/commits",
        "result": null
      },
      {
        "label": "a comment on it",
        "url": "https://github.com/example/docs/pull/12#issuecomment-7",
        "result": null
      },
      {
        "label": "its Changes with a query",
        "url": "https://github.com/example/docs/pull/12/files?w=1",
        "result": null
      },
      {
        "label": "no pull request number",
        "url": "https://github.com/example/docs/pull/docs/new.md",
        "result": null
      },
      {
        "label": "a commit",
        "url": "https://github.com/example/docs/commit/BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        "result": {
          "kind": "route",
          "href": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
          "localization": "commit",
          "pull": null
        }
      },
      {
        "label": "a commit, at one file",
        "url": "https://github.com/example/docs/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb#diff-0000000000000000000000000000000000000000000000000000000000000000",
        "result": null
      },
      {
        "label": "a commit comment",
        "url": "https://github.com/example/docs/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb#r123",
        "result": null
      },
      {
        "label": "a commit's patch",
        "url": "https://github.com/example/docs/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.patch",
        "result": null
      },
      {
        "label": "an abbreviated commit",
        "url": "https://github.com/example/docs/commit/bbbbbbb",
        "result": null
      },
      {
        "label": "the pull request list",
        "url": "https://github.com/example/docs/pulls",
        "result": {
          "kind": "route",
          "href": "/pulls",
          "localization": "pulls",
          "pull": null
        }
      },
      {
        "label": "a search of pull requests",
        "url": "https://github.com/example/docs/pulls?q=is%3Aopen",
        "result": null
      },
      {
        "label": "an issue",
        "url": "https://github.com/example/docs/issues/3",
        "result": null
      },
      {
        "label": "a comparison",
        "url": "https://github.com/example/docs/compare/main...feature/navigation",
        "result": null
      },
      {
        "label": "the commit list",
        "url": "https://github.com/example/docs/commits/feature/navigation",
        "result": null
      },
      {
        "label": "a raw file",
        "url": "https://github.com/example/docs/raw/feature/navigation/guide/intro.md",
        "result": null
      },
      {
        "label": "another repository",
        "url": "https://github.com/example/other/blob/feature/navigation/a.md",
        "result": null
      },
      {
        "label": "another host",
        "url": "https://gitlab.com/example/docs/-/blob/main/a.md",
        "result": null
      },
      {
        "label": "a host that only starts like GitHub's",
        "url": "https://github.com.example.net/example/docs",
        "result": null
      },
      {
        "label": "credentials",
        "url": "https://reader@github.com/example/docs",
        "result": null
      },
      {
        "label": "a port",
        "url": "https://github.com:8443/example/docs",
        "result": null
      },
      {
        "label": "a malformed escape",
        "url": "https://github.com/example/docs/blob/feature/navigation/%zz.md",
        "result": null
      },
      {
        "label": "a dot segment, escaped",
        "url": "https://github.com/example/docs/blob/feature/navigation/%2e%2e/secret.md",
        "result": null
      },
      {
        "label": "a query with a stray percent sign",
        "url": "https://github.com/example/docs/blob/feature/navigation/a.md?a=50%",
        "result": null
      },
      {
        "label": "a query with a malformed escape",
        "url": "https://github.com/example/docs/blob/feature/navigation/a.md?q=%zz",
        "result": null
      },
      {
        "label": "an owner spelled with a sign that folds to a letter",
        "url": "https://github.com/exampl%E2%84%AAe/docs",
        "result": null
      },
      {
        "label": "its Changes, at a file anchor in capitals",
        "url": "https://github.com/example/docs/pull/12/files#diff-0000000000000000000000000000000000000000000000000000000000000000",
        "result": null
      },
      {
        "label": "not a URL",
        "url": "docs/new.md",
        "result": null
      }
    ],
    "subfolder": [
      {
        "label": "a file inside the served folder",
        "url": "https://github.com/example/docs/blob/feature/navigation/packages/handbook/a.md",
        "result": {
          "kind": "view",
          "target": {
            "path": "a.md"
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "a permalink inside it",
        "url": "https://github.com/example/docs/blob/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/packages/handbook/guide.md#Install",
        "result": {
          "kind": "view",
          "target": {
            "path": "guide.md",
            "fragment": "Install"
          },
          "localization": "revision"
        }
      },
      {
        "label": "the served folder itself",
        "url": "https://github.com/example/docs/tree/feature/navigation/packages/handbook",
        "result": {
          "kind": "view",
          "target": {
            "path": ""
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "a file outside it",
        "url": "https://github.com/example/docs/blob/feature/navigation/README.md",
        "result": null
      },
      {
        "label": "the repository",
        "url": "https://github.com/example/docs",
        "result": null
      }
    ],
    "pin": [
      {
        "label": "a file on the pinned branch",
        "url": "https://github.com/example/docs/blob/main/docs/雪.md",
        "result": {
          "kind": "view",
          "target": {
            "path": "g1-ZG9jcw/g1-6ZuqLm1k"
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "a folder on the pinned branch",
        "url": "https://github.com/example/docs/tree/main/docs",
        "result": {
          "kind": "view",
          "target": {
            "path": "g1-ZG9jcw/"
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "the pinned branch's root",
        "url": "https://github.com/example/docs/tree/main",
        "result": {
          "kind": "view",
          "target": {
            "path": ""
          },
          "localization": "working-tree"
        }
      },
      {
        "label": "a file at the pinned commit",
        "url": "https://github.com/example/docs/blob/cccccccccccccccccccccccccccccccccccccccc/README.md",
        "result": {
          "kind": "view",
          "target": {
            "path": "g1-UkVBRE1FLm1k"
          },
          "localization": "revision"
        }
      }
    ],
    "text beside a checkout of its head": [
      {
        "label": "a head file uses GitHub even if checkout bytes differ",
        "url": "https://github.com/example/docs/pull/docs/guide.md",
        "result": {
          "kind": "external",
          "url": "https://github.com/example/docs/blob/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/docs/guide.md"
        }
      }
    ],
    "text at the served head": [
      {
        "label": "a path-relative reference",
        "url": "https://github.com/example/docs/pull/docs/trade-runner/README.md",
        "result": {
          "kind": "view",
          "target": {
            "path": "g1-ZG9jcw/g1-dHJhZGUtcnVubmVy/g1-UkVBRE1FLm1k"
          },
          "localization": "revision"
        }
      },
      {
        "label": "a folder",
        "url": "https://github.com/example/docs/pull/docs/",
        "result": {
          "kind": "view",
          "target": {
            "path": "g1-ZG9jcw/"
          },
          "localization": "revision"
        }
      },
      {
        "label": "the root",
        "url": "https://github.com/example/docs/pull/",
        "result": null
      },
      {
        "label": "with a query and fragment",
        "url": "https://github.com/example/docs/pull/src/app.py?plain=1#L2",
        "result": {
          "kind": "view",
          "target": {
            "path": "g1-c3Jj/g1-YXBwLnB5",
            "query": "plain=1",
            "fragment": "L2"
          },
          "localization": "revision"
        }
      },
      {
        "label": "a pull request's Changes, still",
        "url": "https://github.com/example/docs/pull/7/files",
        "result": {
          "kind": "route",
          "href": "/pull/7/files",
          "localization": "pull",
          "pull": {
            "number": 7,
            "tab": "files",
            "file": "",
            "stack": false
          }
        }
      },
      {
        "label": "a number first, then a pull request's page",
        "url": "https://github.com/example/docs/pull/7/commits",
        "result": null
      },
      {
        "label": "a folder named with digits",
        "url": "https://github.com/example/docs/pull/2024/notes.md",
        "result": {
          "kind": "view",
          "target": {
            "path": "g1-MjAyNA/g1-bm90ZXMubWQ"
          },
          "localization": "revision"
        }
      },
      {
        "label": "a bare pull, which is no reference",
        "url": "https://github.com/example/docs/pull",
        "result": null
      },
      {
        "label": "GitHub's page that opens a pull request",
        "url": "https://github.com/example/docs/pull/new/feature/navigation",
        "result": null
      },
      {
        "label": "a stray percent sign",
        "url": "https://github.com/example/docs/pull/docs/a.md?q=%zz",
        "result": null
      },
      {
        "label": "a file on another branch, still external",
        "url": "https://github.com/example/docs/blob/main/README.md",
        "result": null
      }
    ],
    "text away from its head": [
      {
        "label": "a file the pull request changes, in its Changes",
        "url": "https://github.com/example/docs/pull/docs/trade-runner/README.md",
        "result": {
          "kind": "route",
          "href": "/pull/7/files/docs/trade-runner/README.md",
          "localization": "pull",
          "pull": {
            "number": 7,
            "tab": "files",
            "file": "docs/trade-runner/README.md",
            "stack": false
          }
        }
      },
      {
        "label": "an authored absolute patch URL",
        "url": "https://github.com/example/docs/pull/7.patch",
        "result": null
      },
      {
        "label": "the same resolution from an authored relative file",
        "url": "https://github.com/example/docs/pull/7.patch",
        "result": {
          "kind": "external",
          "url": "https://github.com/example/docs/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/7.patch"
        }
      },
      {
        "label": "an anchored changed file, on GitHub",
        "url": "https://github.com/example/docs/pull/docs/trade-runner/README.md#install",
        "result": {
          "kind": "external",
          "url": "https://github.com/example/docs/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/docs/trade-runner/README.md#install"
        }
      },
      {
        "label": "a file it does not change, on github.com",
        "url": "https://github.com/example/docs/pull/docs/guide.md",
        "result": {
          "kind": "external",
          "url": "https://github.com/example/docs/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/docs/guide.md"
        }
      },
      {
        "label": "a changed file with a query, on github.com",
        "url": "https://github.com/example/docs/pull/docs/trade-runner/README.md?plain=1",
        "result": {
          "kind": "external",
          "url": "https://github.com/example/docs/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/docs/trade-runner/README.md?plain=1"
        }
      },
      {
        "label": "a folder",
        "url": "https://github.com/example/docs/pull/docs/",
        "result": {
          "kind": "external",
          "url": "https://github.com/example/docs/tree/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/docs/"
        }
      },
      {
        "label": "the root",
        "url": "https://github.com/example/docs/pull/",
        "result": null
      },
      {
        "label": "with a query and fragment",
        "url": "https://github.com/example/docs/pull/src/app.py?plain=1#L2",
        "result": {
          "kind": "external",
          "url": "https://github.com/example/docs/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/src/app.py?plain=1#L2"
        }
      },
      {
        "label": "a name that needs escaping",
        "url": "https://github.com/example/docs/pull/docs/space%20name.md",
        "result": {
          "kind": "external",
          "url": "https://github.com/example/docs/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/docs/space%20name.md"
        }
      },
      {
        "label": "a file on the pinned branch, in place",
        "url": "https://github.com/example/docs/blob/main/README.md",
        "result": {
          "kind": "view",
          "target": {
            "path": "g1-UkVBRE1FLm1k"
          },
          "localization": "working-tree"
        }
      }
    ],
    "text at the served head, from a subfolder": [
      {
        "label": "a file inside the served folder",
        "url": "https://github.com/example/docs/pull/packages/handbook/a.md",
        "result": {
          "kind": "view",
          "target": {
            "path": "g1-YS5tZA"
          },
          "localization": "revision"
        }
      },
      {
        "label": "a file outside it, on github.com",
        "url": "https://github.com/example/docs/pull/README.md",
        "result": {
          "kind": "external",
          "url": "https://github.com/example/docs/blob/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/README.md"
        }
      }
    ],
    "a stack's note away from its head": [
      {
        "label": "a file the stack changes, in its Changes",
        "url": "https://github.com/example/docs/pull/src/app.py",
        "result": {
          "kind": "route",
          "href": "/stack/3/changes/src/app.py",
          "localization": "pull",
          "pull": {
            "number": 3,
            "tab": "changes",
            "file": "src/app.py",
            "stack": true
          }
        }
      },
      {
        "label": "a file it does not change, on github.com",
        "url": "https://github.com/example/docs/pull/README.md",
        "result": {
          "kind": "external",
          "url": "https://github.com/example/docs/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/README.md"
        }
      }
    ],
    "text with no head yet": [
      {
        "label": "a path-relative reference",
        "url": "https://github.com/example/docs/pull/docs/new.md",
        "result": null
      }
    ]
  },
  "viewFiles": {
    "a file": {
      "href": "/view/g1-ZG9jcw/g1-6ZuqLm1k",
      "url": "https://github.com/example/docs/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/docs/%E9%9B%AA.md"
    },
    "a file, at a heading": {
      "href": "/view/g1-ZG9jcw/g1-c2V0dXAubWQ#user-content-install",
      "url": "https://github.com/example/docs/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/docs/setup.md#user-content-install"
    },
    "a name with a leading byte-order mark": {
      "href": "/view/g1-77u_cGxhbi5tZA",
      "url": "https://github.com/example/docs/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/%EF%BB%BFplan.md"
    },
    "a name with a literal replacement character": {
      "href": "/view/g1-ZG9jcw/g1-77-9Lm1k",
      "url": "https://github.com/example/docs/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/docs/%EF%BF%BD.md"
    },
    "a name with a control character": {
      "href": "/view/g1-YQcubWQ",
      "url": null
    },
    "a name with a backslash": {
      "href": "/view/g1-YVxiLm1k",
      "url": null
    },
    "a name that is not text": {
      "href": "/view/g1-_w",
      "url": null
    },
    "a partially encoded path": {
      "href": "/view/g1-ZG9jcw/setup.md",
      "url": null
    },
    "not a pin's address": {
      "href": "/view/docs/setup.md",
      "url": null
    },
    "not a view": {
      "href": "/pull/7/files/docs/setup.md",
      "url": null
    }
  },
  "enhanced": {
    "a text at its served head": {
      "changed": [
        3
      ],
      "anchors": {
        "file": {
          "data-metabrowser-github-localization": "revision",
          "data-metabrowser-path-relative": "",
          "href": "/view/g1-ZG9jcw/g1-bmV3Lm1k"
        },
        "pull": {
          "data-metabrowser-github-localization": "pull",
          "href": "/pull/12/files"
        },
        "commit": {
          "data-metabrowser-github-localization": "commit",
          "href": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        },
        "other": {
          "href": "https://example.com/",
          "rel": "noopener noreferrer",
          "target": "_blank"
        }
      },
      "clicks": {
        "file": {
          "plain": true,
          "withMeta": false,
          "listeners": 1
        },
        "pull": {
          "plain": false,
          "withMeta": false,
          "listeners": 1
        },
        "commit": {
          "plain": false,
          "withMeta": false,
          "listeners": 1
        },
        "other": {
          "plain": false,
          "withMeta": false,
          "listeners": 0
        }
      },
      "opened": [
        {
          "path": "g1-ZG9jcw/g1-bmV3Lm1k"
        }
      ],
      "routed": []
    },
    "a text away from its head, with the page's own router": {
      "changed": [
        3
      ],
      "anchors": {
        "file": {
          "data-metabrowser-path-relative": "",
          "href": "https://github.com/example/docs/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/docs/new.md",
          "rel": "noopener noreferrer",
          "target": "_blank"
        },
        "pull": {
          "data-metabrowser-github-localization": "pull",
          "href": "/pull/12/files"
        },
        "commit": {
          "data-metabrowser-github-localization": "commit",
          "href": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        },
        "other": {
          "href": "https://example.com/",
          "rel": "noopener noreferrer",
          "target": "_blank"
        }
      },
      "clicks": {
        "file": {
          "plain": false,
          "withMeta": false,
          "listeners": 0
        },
        "pull": {
          "plain": true,
          "withMeta": false,
          "listeners": 1
        },
        "commit": {
          "plain": false,
          "withMeta": false,
          "listeners": 1
        },
        "other": {
          "plain": false,
          "withMeta": false,
          "listeners": 0
        }
      },
      "opened": [],
      "routed": [
        "/pull/12/files {\"number\":12,\"tab\":\"files\",\"file\":\"\",\"stack\":false}"
      ]
    },
    "a text whose pull request's changed files arrive after it is drawn": {
      "changed": [
        3,
        3
      ],
      "anchors": {
        "file": {
          "data-metabrowser-github-localization": "pull",
          "data-metabrowser-path-relative": "",
          "href": "/pull/7/files/docs/new.md"
        },
        "pull": {
          "data-metabrowser-github-localization": "pull",
          "href": "/pull/12/files"
        },
        "commit": {
          "data-metabrowser-github-localization": "commit",
          "href": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        },
        "other": {
          "href": "https://example.com/",
          "rel": "noopener noreferrer",
          "target": "_blank"
        }
      },
      "clicks": {
        "file": {
          "plain": true,
          "withMeta": false,
          "listeners": 1
        },
        "pull": {
          "plain": true,
          "withMeta": false,
          "listeners": 1
        },
        "commit": {
          "plain": false,
          "withMeta": false,
          "listeners": 1
        },
        "other": {
          "plain": false,
          "withMeta": false,
          "listeners": 0
        }
      },
      "opened": [],
      "routed": [
        "/pull/7/files/docs/new.md {\"number\":7,\"tab\":\"files\",\"file\":\"docs/new.md\",\"stack\":false}",
        "/pull/12/files {\"number\":12,\"tab\":\"files\",\"file\":\"\",\"stack\":false}"
      ]
    },
    "a text whose head moves past its files, and whose new files then arrive": {
      "changed": [
        3,
        3,
        3
      ],
      "anchors": {
        "file": {
          "data-metabrowser-github-localization": "pull",
          "data-metabrowser-path-relative": "",
          "href": "/pull/7/files/docs/new.md"
        },
        "pull": {
          "data-metabrowser-github-localization": "pull",
          "href": "/pull/12/files"
        },
        "commit": {
          "data-metabrowser-github-localization": "commit",
          "href": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        },
        "other": {
          "href": "https://example.com/",
          "rel": "noopener noreferrer",
          "target": "_blank"
        }
      },
      "clicks": {
        "file": {
          "plain": true,
          "withMeta": false,
          "listeners": 1
        },
        "pull": {
          "plain": true,
          "withMeta": false,
          "listeners": 1
        },
        "commit": {
          "plain": false,
          "withMeta": false,
          "listeners": 1
        },
        "other": {
          "plain": false,
          "withMeta": false,
          "listeners": 0
        }
      },
      "opened": [],
      "routed": [
        "/pull/7/files/docs/new.md {\"number\":7,\"tab\":\"files\",\"file\":\"docs/new.md\",\"stack\":false}",
        "/pull/12/files {\"number\":12,\"tab\":\"files\",\"file\":\"\",\"stack\":false}"
      ]
    },
    "a commit's message, which has no text context": {
      "changed": [
        2
      ],
      "anchors": {
        "file": {
          "data-metabrowser-path-relative": "",
          "href": "https://github.com/example/docs/pull/docs/new.md",
          "rel": "noopener noreferrer",
          "target": "_blank"
        },
        "pull": {
          "data-metabrowser-github-localization": "pull",
          "href": "/pull/12/files"
        },
        "commit": {
          "data-metabrowser-github-localization": "commit",
          "href": "/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        },
        "other": {
          "href": "https://example.com/",
          "rel": "noopener noreferrer",
          "target": "_blank"
        }
      },
      "clicks": {
        "file": {
          "plain": false,
          "withMeta": false,
          "listeners": 0
        },
        "pull": {
          "plain": false,
          "withMeta": false,
          "listeners": 1
        },
        "commit": {
          "plain": false,
          "withMeta": false,
          "listeners": 1
        },
        "other": {
          "plain": false,
          "withMeta": false,
          "listeners": 0
        }
      },
      "opened": [],
      "routed": []
    },
    "a page with no repository": {
      "changed": [
        0
      ],
      "anchors": {
        "file": {
          "data-metabrowser-path-relative": "",
          "href": "https://github.com/example/docs/pull/docs/new.md",
          "rel": "noopener noreferrer",
          "target": "_blank"
        },
        "pull": {
          "href": "https://github.com/example/docs/pull/12/files",
          "rel": "noopener noreferrer",
          "target": "_blank"
        },
        "commit": {
          "href": "https://github.com/example/docs/commit/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
          "rel": "noopener noreferrer",
          "target": "_blank"
        },
        "other": {
          "href": "https://example.com/",
          "rel": "noopener noreferrer",
          "target": "_blank"
        }
      },
      "clicks": {
        "file": {
          "plain": false,
          "withMeta": false,
          "listeners": 0
        },
        "pull": {
          "plain": false,
          "withMeta": false,
          "listeners": 0
        },
        "commit": {
          "plain": false,
          "withMeta": false,
          "listeners": 0
        },
        "other": {
          "plain": false,
          "withMeta": false,
          "listeners": 0
        }
      },
      "opened": [],
      "routed": []
    }
  }
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->

---
cwd: ../..
sandbox: false
---
# Golden Test: A Commit’s Body as Markdown on Its Page

This session runs the production `placeCommitBody`, `fetchCommitBody`, and
`prepareRevision` from `static/git-panel.js`, with `static/inert-html.js`, over a
stand-in DOM, against the answers of `GET /api/git/commit-markdown/{revision}`: the
rendered one is what `cli-api-git-commit-markdown.tryscript.md` pins for its fixture
commit. Each step prints the requests it made, the SDK assets it loaded, what the body’s
box holds, what the panel warned of, and which bodies it keeps.

A body’s message as written is held out of sight (`waiting`) until its Markdown comes,
then replaced by a KPress article of the allowlist’s nodes, as a pull request’s page
sets a description: its code in KPress’s code block, an absolute link decorated as an
outside link, a relative one with only its text, and the trailers after it as written.
A kept render is placed at once with no request, and two callers share one request.
A hover’s preparation (`prepareRevision`) asks for the body once its detail comes, and
the reader’s open joins that request; when the hover’s request ends in a refusal the
panel does not keep, such as a busy renderer, the open asks again and shows its own
answer. A preparation given up before its detail comes asks for no body.
A body of only trailers has no article.
On a page with the served repository’s identity, `static/repository-links.js` decides
what the body’s links open: a same-repository pull request’s, commit’s, and pull request
list’s link becomes its in-app page, `/pull/<n>`, `/commit/<id>`, or `/pulls`, which a
plain click has the shell open in place (`navigation.openRoute`), and a file on the
served branch its `/view/` address, which a plain click opens through the navigation; a
modified click on any of them is the browser’s. A relative reference stays text, as on
github.com, where a commit’s message is not Markdown, and another site stays an outside
link.

A body the route will not render shows as written: one too long, with a notice that is
not asked for again, and one past the renderer’s deadline, with a notice that is.
A request that never arrives, and KPress’s stylesheets or the allowlist failing to load,
leave it as written with no notice, and the next body asks for the stylesheets again.
A commit with no body asks for nothing.

```console
$ node tests/dom/git-commit-body-session.js
{
  "stylesheets that fail leave the body as written": {
    "waiting": true,
    "requests": [
      "/api/git/commit-markdown/1111111111111111111111111111111111111111"
    ],
    "assets": [
      "inert-html",
      "kpress:1"
    ],
    "box": {
      "div.git-commit-body.page-card.chrome-prose": [
        {
          "div.git-commit-body-plain": "styled"
        }
      ]
    },
    "warnings": [
      "metabrowser git: a commit body's Markdown could not be shown"
    ],
    "kept": []
  },
  "a body opens as Markdown": {
    "waiting": true,
    "requests": [
      "/api/git/commit-markdown/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    ],
    "assets": [
      "inert-html",
      "kpress:1"
    ],
    "box": {
      "div.git-commit-body.page-card.chrome-prose": [
        {
          "div.metabrowser-kpress-host": [
            {
              "article.kpress.kpress-inert": [
                {
                  "div.kpress-prose": [
                    {
                      "p": "The app counted to one. This change wraps its prose at seventy-two\ncolumns, as a commit body does, and the page reflows it."
                    },
                    {
                      "ul": [
                        {
                          "li": "a bullet that wraps onto\na second line"
                        },
                        {
                          "li": "another, which fixes #12; see https://example.com/issue"
                        }
                      ]
                    },
                    {
                      "ul": [
                        {
                          "li": [
                            "a star bullet with ",
                            {
                              "b": "bold"
                            }
                          ]
                        }
                      ]
                    },
                    {
                      "p": "An example:"
                    },
                    {
                      "pre.kpress-code": [
                        {
                          "code": "indented code stays code\n"
                        }
                      ]
                    },
                    {
                      "p": [
                        "A ",
                        {
                          "a[href=https://example.com/doc target=_blank rel=noopener noreferrer data-decorated=external]": "link"
                        },
                        " and a ",
                        {
                          "a": "relative one"
                        },
                        "."
                      ]
                    }
                  ]
                }
              ]
            }
          ]
        },
        {
          "div.git-commit-trailers": "Signed-off-by: Test <test@example.com>\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
        }
      ]
    },
    "warnings": [],
    "kept": [
      "aaaaaaa"
    ]
  },
  "a kept body opens at once": {
    "waiting": false,
    "requests": [],
    "assets": [],
    "box": {
      "div.git-commit-body.page-card.chrome-prose": [
        {
          "div.metabrowser-kpress-host": [
            {
              "article.kpress.kpress-inert": [
                {
                  "div.kpress-prose": [
                    {
                      "p": "The app counted to one. This change wraps its prose at seventy-two\ncolumns, as a commit body does, and the page reflows it."
                    },
                    {
                      "ul": [
                        {
                          "li": "a bullet that wraps onto\na second line"
                        },
                        {
                          "li": "another, which fixes #12; see https://example.com/issue"
                        }
                      ]
                    },
                    {
                      "ul": [
                        {
                          "li": [
                            "a star bullet with ",
                            {
                              "b": "bold"
                            }
                          ]
                        }
                      ]
                    },
                    {
                      "p": "An example:"
                    },
                    {
                      "pre.kpress-code": [
                        {
                          "code": "indented code stays code\n"
                        }
                      ]
                    },
                    {
                      "p": [
                        "A ",
                        {
                          "a[href=https://example.com/doc target=_blank rel=noopener noreferrer data-decorated=external]": "link"
                        },
                        " and a ",
                        {
                          "a": "relative one"
                        },
                        "."
                      ]
                    }
                  ]
                }
              ]
            }
          ]
        },
        {
          "div.git-commit-trailers": "Signed-off-by: Test <test@example.com>\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
        }
      ]
    },
    "warnings": [],
    "kept": [
      "aaaaaaa"
    ]
  },
  "two callers share one request": {
    "requests": [
      "/api/git/commit-markdown/3333333333333333333333333333333333333333"
    ],
    "same": true,
    "kind": "rendered"
  },
  "a hover prefetches, and the open joins it": {
    "hovered": 1,
    "requests": [
      "/api/git/commit/4444444444444444444444444444444444444444",
      "/api/git/commit-markdown/4444444444444444444444444444444444444444"
    ],
    "box": {
      "div.git-commit-body.page-card.chrome-prose": [
        {
          "div.metabrowser-kpress-host": [
            {
              "article.kpress.kpress-inert": [
                {
                  "div.kpress-prose": [
                    {
                      "p": "prefetched"
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    },
    "kept": true
  },
  "a hover's refusal is asked again by the open": {
    "hovered": 1,
    "requests": [
      "/api/git/commit/5555555555555555555555555555555555555555",
      "/api/git/commit-markdown/5555555555555555555555555555555555555555",
      "/api/git/commit-markdown/5555555555555555555555555555555555555555"
    ],
    "box": {
      "div.git-commit-body.page-card.chrome-prose": [
        {
          "div.metabrowser-kpress-host": [
            {
              "article.kpress.kpress-inert": [
                {
                  "div.kpress-prose": [
                    {
                      "p": "rendered on the reader's request"
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    },
    "kept": true
  },
  "a preparation given up asks for no body": {
    "requests": [
      "/api/git/commit/6666666666666666666666666666666666666666"
    ]
  },
  "a body of only trailers": {
    "waiting": true,
    "requests": [
      "/api/git/commit-markdown/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    ],
    "assets": [
      "inert-html"
    ],
    "box": {
      "div.git-commit-body.page-card.chrome-prose": [
        {
          "div.git-commit-trailers": "Signed-off-by: Test <test@example.com>"
        }
      ]
    },
    "warnings": [],
    "kept": [
      "aaaaaaa",
      "3333333",
      "4444444",
      "5555555",
      "bbbbbbb"
    ]
  },
  "a body too long to render": {
    "waiting": true,
    "requests": [
      "/api/git/commit-markdown/cccccccccccccccccccccccccccccccccccccccc"
    ],
    "assets": [],
    "box": {
      "div.git-commit-body.page-card.chrome-prose": [
        {
          "div.git-commit-body-plain": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        },
        {
          "div.notice.git-commit-body-notice[role=status data-severity=warning]": "This message is too long to render, so it is shown as written."
        }
      ]
    },
    "warnings": [],
    "kept": [
      "aaaaaaa",
      "3333333",
      "4444444",
      "5555555",
      "bbbbbbb",
      "ccccccc"
    ]
  },
  "a body too long, again": {
    "waiting": false,
    "requests": [],
    "assets": [],
    "box": {
      "div.git-commit-body.page-card.chrome-prose": [
        {
          "div.git-commit-body-plain": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        },
        {
          "div.notice.git-commit-body-notice[role=status data-severity=warning]": "This message is too long to render, so it is shown as written."
        }
      ]
    },
    "warnings": [],
    "kept": [
      "aaaaaaa",
      "3333333",
      "4444444",
      "5555555",
      "bbbbbbb",
      "ccccccc"
    ]
  },
  "a render past its deadline": {
    "waiting": true,
    "requests": [
      "/api/git/commit-markdown/dddddddddddddddddddddddddddddddddddddddd"
    ],
    "assets": [],
    "box": {
      "div.git-commit-body.page-card.chrome-prose": [
        {
          "div.git-commit-body-plain": "slow"
        },
        {
          "div.notice.git-commit-body-notice[role=status data-severity=warning]": "This message took too long to render, so it is shown as written."
        }
      ]
    },
    "warnings": [],
    "kept": [
      "aaaaaaa",
      "3333333",
      "4444444",
      "5555555",
      "bbbbbbb",
      "ccccccc"
    ]
  },
  "past its deadline, again": {
    "waiting": true,
    "requests": [
      "/api/git/commit-markdown/dddddddddddddddddddddddddddddddddddddddd"
    ],
    "assets": [],
    "box": {
      "div.git-commit-body.page-card.chrome-prose": [
        {
          "div.git-commit-body-plain": "slow"
        },
        {
          "div.notice.git-commit-body-notice[role=status data-severity=warning]": "This message took too long to render, so it is shown as written."
        }
      ]
    },
    "warnings": [],
    "kept": [
      "aaaaaaa",
      "3333333",
      "4444444",
      "5555555",
      "bbbbbbb",
      "ccccccc"
    ]
  },
  "a request that never arrives": {
    "waiting": true,
    "requests": [
      "/api/git/commit-markdown/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    ],
    "assets": [],
    "box": {
      "div.git-commit-body.page-card.chrome-prose": [
        {
          "div.git-commit-body-plain": "offline"
        }
      ]
    },
    "warnings": [],
    "kept": [
      "aaaaaaa",
      "3333333",
      "4444444",
      "5555555",
      "bbbbbbb",
      "ccccccc"
    ]
  },
  "an allowlist that cannot load": {
    "waiting": true,
    "requests": [
      "/api/git/commit-markdown/2222222222222222222222222222222222222222"
    ],
    "assets": [
      "inert-html"
    ],
    "box": {
      "div.git-commit-body.page-card.chrome-prose": [
        {
          "div.git-commit-body-plain": "x"
        }
      ]
    },
    "warnings": [
      "metabrowser git: a commit body's Markdown could not be shown"
    ],
    "kept": [
      "aaaaaaa",
      "3333333",
      "4444444",
      "5555555",
      "bbbbbbb",
      "ccccccc"
    ]
  },
  "a body's links into the served repository": {
    "waiting": true,
    "requests": [
      "/api/git/commit-markdown/7777777777777777777777777777777777777777"
    ],
    "assets": [
      "inert-html",
      "repository-links"
    ],
    "box": {
      "div.git-commit-body.page-card.chrome-prose": [
        {
          "div.metabrowser-kpress-host": [
            {
              "article.kpress.kpress-inert": [
                {
                  "div.kpress-prose": [
                    {
                      "p": [
                        "See ",
                        {
                          "a[href=/pull/12 data-metabrowser-github-localization=pull]": "the pull request"
                        },
                        ", ",
                        {
                          "a[href=/commit/9999999999999999999999999999999999999999 data-metabrowser-github-localization=commit]": "a commit"
                        },
                        ", ",
                        {
                          "a[href=/pulls data-metabrowser-github-localization=pulls]": "the pull requests"
                        },
                        ", ",
                        {
                          "a[href=/view/docs/guide.md data-metabrowser-github-localization=working-tree data-tip-text=Open the corresponding path in the currently served working tree.]": "the guide"
                        },
                        ", ",
                        {
                          "a": "a relative one"
                        },
                        ", and ",
                        {
                          "a[href=https://example.com/doc target=_blank rel=noopener noreferrer data-decorated=external]": "another site"
                        },
                        "."
                      ]
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    },
    "warnings": [],
    "kept": [
      "aaaaaaa",
      "3333333",
      "4444444",
      "5555555",
      "bbbbbbb",
      "ccccccc",
      "7777777"
    ],
    "clicks": [
      "the pull request: the shell opens /pull/12",
      "a commit: the shell opens /commit/9999999999999999999999999999999999999999",
      "the pull requests: the shell opens /pulls",
      "the guide: /view/docs/guide.md",
      "another site: the browser follows it",
      "Command-click the pull request: the browser follows it",
      "Command-click a commit: the browser follows it",
      "Command-click the pull requests: the browser follows it",
      "Command-click the guide: the browser follows it",
      "Command-click another site: the browser follows it"
    ]
  },
  "a commit with no body": {
    "waiting": false,
    "requests": [],
    "assets": [],
    "box": null,
    "warnings": [],
    "kept": [
      "aaaaaaa",
      "3333333",
      "4444444",
      "5555555",
      "bbbbbbb",
      "ccccccc",
      "7777777"
    ]
  },
  "notes": {
    "body_too_large": "This message is too long to render, so it is shown as written.",
    "render_deadline": "This message took too long to render, so it is shown as written.",
    "renderer_exited": "This message could not be rendered, so it is shown as written.",
    "renderer_unavailable": "This message could not be rendered, so it is shown as written. Reload the page to try again.",
    "renderer_busy": "This message could not be rendered, so it is shown as written. Reload the page to try again.",
    "render_failed": "This message could not be rendered, so it is shown as written.",
    "commit_not_found": null,
    "none": null
  }
}
? 0
```

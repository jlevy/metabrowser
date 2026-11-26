---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
  GIT_CONFIG_GLOBAL: "/dev/null"
  GIT_CONFIG_SYSTEM: "/dev/null"
before: >-
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_PREFIX GIT_NAMESPACE GIT_CEILING_DIRECTORIES &&
  mkdir -p denseroot/build denseroot/src/lib &&
  git -C denseroot init -q --initial-branch=main . &&
  printf 'build/\n*.log\n' > denseroot/.gitignore &&
  printf '%0400d' 0 > denseroot/build/out.bin &&
  printf '%020d' 0 > denseroot/top.md &&
  printf '%0200d' 0 > denseroot/src/main.py &&
  printf '%060d' 0 > denseroot/src/run.log &&
  printf '%0100d' 0 > denseroot/src/lib/util.py &&
  printf '%050d' 0 > denseroot/src/lib/io.py &&
  printf '%020d' 0 > 'denseroot/src/lib/notes v2.md' &&
  printf '%030d' 0 > denseroot/src/lib/trace.log &&
  for i in 1 2 3 4; do printf '%010d' 0 > denseroot/src/lib/t$i.py; done &&
  find denseroot -path denseroot/.git -prune -o -exec touch -t 202311142213.20 {} +
---
# Golden test: the Treemap’s dense rollup through `--api`

The Treemap asks `/api/rollup` for as much of a folder as it can draw: the largest node
budget, gitignored entries left out when Show ignored is off, and the compact encoding.
This transcript pins those three parameters, `nodes`, `ignored`, and `encoding`, on a
real folder; the File Rollup Format document describes them.

The fixture ignores `build/` and `*.log`:

| Path | Bytes | Ignored |
| --- | --- | --- |
| `build/out.bin` | 400 | yes, by its folder |
| `top.md` | 20 |  |
| `src/main.py` | 200 |  |
| `src/run.log` | 60 | yes |
| `src/lib/util.py` | 100 |  |
| `src/lib/io.py` | 50 |  |
| `src/lib/notes v2.md` | 20 |  |
| `src/lib/trace.log` | 30 | yes |
| `src/lib/t1.py` to `t4.py` | 10 each |  |

## Test: the compact encoding writes a folder’s files as entries

Each expanded folder keeps only its folders in `children` and lists its files in `files`
as `[name, size, mtime, ext, gitignored]`. A file’s path is its folder’s path, a `/`,
and its name, so `notes v2.md` is `src/lib/notes v2.md`. The envelope says
`"encoding": "compact"`.

```console
$ metab denseroot --api '/api/rollup?path=src&depth=max&top=max&nodes=max&encoding=compact'
api: /api/rollup?path=src&depth=max&top=max&nodes=max&encoding=compact
status: 200
{
  "root": "<ROOT>",
  "path": "src",
  "encoding": "compact",
  "node": {
    "name": "src",
    "path": "src",
    "type": "dir",
    "state": "complete",
    "total_files": 10,
    "total_size": 500,
    "unignored_files": 8,
    "unignored_size": 410,
    "mtime": 1700000000.0,
    "gitignored": false,
    "dominant_ext": ".py",
    "children": [
      {
        "name": "lib",
        "path": "src/lib",
        "type": "dir",
        "state": "complete",
        "total_files": 8,
        "total_size": 240,
        "unignored_files": 7,
        "unignored_size": 210,
        "mtime": 1700000000.0,
        "gitignored": false,
        "dominant_ext": ".py",
        "children": [],
        "files": [
          [
            "util.py",
            100,
            1700000000.0,
            ".py",
            0
          ],
          [
            "io.py",
            50,
            1700000000.0,
            ".py",
            0
          ],
          [
            "trace.log",
            30,
            1700000000.0,
            ".log",
            1
          ],
          [
            "notes v2.md",
            20,
            1700000000.0,
            ".md",
            0
          ],
          [
            "t1.py",
            10,
            1700000000.0,
            ".py",
            0
          ],
          [
            "t2.py",
            10,
            1700000000.0,
            ".py",
            0
          ],
          [
            "t3.py",
            10,
            1700000000.0,
            ".py",
            0
          ],
          [
            "t4.py",
            10,
            1700000000.0,
            ".py",
            0
          ]
        ]
      }
    ],
    "files": [
      [
        "main.py",
        200,
        1700000000.0,
        ".py",
        0
      ],
      [
        "run.log",
        60,
        1700000000.0,
        ".log",
        1
      ]
    ]
  },
  "ext_tallies": [
    [
      ".py",
      7,
      390,
      7,
      390
    ],
    [
      ".log",
      2,
      90,
      0,
      0
    ],
    [
      ".md",
      1,
      20,
      1,
      20
    ]
  ],
  "file_type_breakdown": {
    "schema": "file-type-breakdown-v1",
    "registry": {
      "schema_version": 5,
      "revision": 5,
      "fingerprint": "526dd932ae6bbed9e2e5e4a2d134b3f4aeacf9abcb6a156a9f3b94724c16708c"
    },
    "metrics": {
      "all": {
        "files": 10,
        "bytes": 500
      },
      "unignored": {
        "files": 8,
        "bytes": 410
      }
    },
    "groups": [
      {
        "id": "code",
        "families": [
          {
            "id": "python",
            "metrics": {
              "all": {
                "files": 7,
                "bytes": 390
              },
              "unignored": {
                "files": 7,
                "bytes": 390
              }
            },
            "extensions": [
              {
                "extension": ".py",
                "metrics": {
                  "all": {
                    "files": 7,
                    "bytes": 390
                  },
                  "unignored": {
                    "files": 7,
                    "bytes": 390
                  }
                }
              }
            ]
          }
        ]
      },
      {
        "id": "docs",
        "families": [
          {
            "id": "markdown",
            "metrics": {
              "all": {
                "files": 1,
                "bytes": 20
              },
              "unignored": {
                "files": 1,
                "bytes": 20
              }
            },
            "extensions": [
              {
                "extension": ".md",
                "metrics": {
                  "all": {
                    "files": 1,
                    "bytes": 20
                  },
                  "unignored": {
                    "files": 1,
                    "bytes": 20
                  }
                }
              }
            ]
          }
        ]
      },
      {
        "id": "other",
        "families": [
          {
            "id": "log-files",
            "metrics": {
              "all": {
                "files": 2,
                "bytes": 90
              },
              "unignored": {
                "files": 0,
                "bytes": 0
              }
            },
            "extensions": [
              {
                "extension": ".log",
                "metrics": {
                  "all": {
                    "files": 2,
                    "bytes": 90
                  },
                  "unignored": {
                    "files": 0,
                    "bytes": 0
                  }
                }
              }
            ]
          }
        ]
      }
    ],
    "no_extension": {
      "metrics": {
        "all": {
          "files": 0,
          "bytes": 0
        },
        "unignored": {
          "files": 0,
          "bytes": 0
        }
      },
      "filenames": [],
      "others": null
    },
    "remaining_types": {
      "metrics": {
        "all": {
          "files": 0,
          "bytes": 0
        },
        "unignored": {
          "files": 0,
          "bytes": 0
        }
      },
      "extensions": [],
      "others": null
    }
  },
  "file_type_legend": {
    "schema": "file-type-legend-v1",
    "limit": 9,
    "minimum_share_percent": 1,
    "files": {
      "all": {
        "total": 10,
        "named": [
          {
            "family": "python",
            "value": 7
          },
          {
            "family": "log-files",
            "value": 2
          },
          {
            "family": "markdown",
            "value": 1
          }
        ],
        "other": 0
      },
      "unignored": {
        "total": 8,
        "named": [
          {
            "family": "python",
            "value": 7
          },
          {
            "family": "markdown",
            "value": 1
          }
        ],
        "other": 0
      }
    },
    "bytes": {
      "all": {
        "total": 500,
        "named": [
          {
            "family": "python",
            "value": 390
          },
          {
            "family": "log-files",
            "value": 90
          },
          {
            "family": "markdown",
            "value": 20
          }
        ],
        "other": 0
      },
      "unignored": {
        "total": 410,
        "named": [
          {
            "family": "python",
            "value": 390
          },
          {
            "family": "markdown",
            "value": 20
          }
        ],
        "other": 0
      }
    }
  },
  "index_status": "done",
  "indexed_files": 12,
  "max_files": 500000,
  "truncated": false
}
? 0
```

## Test: ignored=exclude leaves the ignored entries out and nothing else

`run.log` and `trace.log` are not emitted, and every total, tally, and breakdown is the
one above: `src` still counts 10 files, 8 of them unignored.

```console
$ metab denseroot --api '/api/rollup?path=src&depth=max&top=max&nodes=max&ignored=exclude'
api: /api/rollup?path=src&depth=max&top=max&nodes=max&ignored=exclude
status: 200
{
  "root": "<ROOT>",
  "path": "src",
  "node": {
    "name": "src",
    "path": "src",
    "type": "dir",
    "state": "complete",
    "total_files": 10,
    "total_size": 500,
    "unignored_files": 8,
    "unignored_size": 410,
    "mtime": 1700000000.0,
    "gitignored": false,
    "dominant_ext": ".py",
    "children": [
      {
        "name": "lib",
        "path": "src/lib",
        "type": "dir",
        "state": "complete",
        "total_files": 8,
        "total_size": 240,
        "unignored_files": 7,
        "unignored_size": 210,
        "mtime": 1700000000.0,
        "gitignored": false,
        "dominant_ext": ".py",
        "children": [
          {
            "name": "util.py",
            "path": "src/lib/util.py",
            "type": "file",
            "size": 100,
            "mtime": 1700000000.0,
            "ext": ".py",
            "gitignored": false
          },
          {
            "name": "io.py",
            "path": "src/lib/io.py",
            "type": "file",
            "size": 50,
            "mtime": 1700000000.0,
            "ext": ".py",
            "gitignored": false
          },
          {
            "name": "notes v2.md",
            "path": "src/lib/notes v2.md",
            "type": "file",
            "size": 20,
            "mtime": 1700000000.0,
            "ext": ".md",
            "gitignored": false
          },
          {
            "name": "t1.py",
            "path": "src/lib/t1.py",
            "type": "file",
            "size": 10,
            "mtime": 1700000000.0,
            "ext": ".py",
            "gitignored": false
          },
          {
            "name": "t2.py",
            "path": "src/lib/t2.py",
            "type": "file",
            "size": 10,
            "mtime": 1700000000.0,
            "ext": ".py",
            "gitignored": false
          },
          {
            "name": "t3.py",
            "path": "src/lib/t3.py",
            "type": "file",
            "size": 10,
            "mtime": 1700000000.0,
            "ext": ".py",
            "gitignored": false
          },
          {
            "name": "t4.py",
            "path": "src/lib/t4.py",
            "type": "file",
            "size": 10,
            "mtime": 1700000000.0,
            "ext": ".py",
            "gitignored": false
          }
        ]
      },
      {
        "name": "main.py",
        "path": "src/main.py",
        "type": "file",
        "size": 200,
        "mtime": 1700000000.0,
        "ext": ".py",
        "gitignored": false
      }
    ]
  },
  "ext_tallies": [
    [
      ".py",
      7,
      390,
      7,
      390
    ],
    [
      ".log",
      2,
      90,
      0,
      0
    ],
    [
      ".md",
      1,
      20,
      1,
      20
    ]
  ],
  "file_type_breakdown": {
    "schema": "file-type-breakdown-v1",
    "registry": {
      "schema_version": 5,
      "revision": 5,
      "fingerprint": "526dd932ae6bbed9e2e5e4a2d134b3f4aeacf9abcb6a156a9f3b94724c16708c"
    },
    "metrics": {
      "all": {
        "files": 10,
        "bytes": 500
      },
      "unignored": {
        "files": 8,
        "bytes": 410
      }
    },
    "groups": [
      {
        "id": "code",
        "families": [
          {
            "id": "python",
            "metrics": {
              "all": {
                "files": 7,
                "bytes": 390
              },
              "unignored": {
                "files": 7,
                "bytes": 390
              }
            },
            "extensions": [
              {
                "extension": ".py",
                "metrics": {
                  "all": {
                    "files": 7,
                    "bytes": 390
                  },
                  "unignored": {
                    "files": 7,
                    "bytes": 390
                  }
                }
              }
            ]
          }
        ]
      },
      {
        "id": "docs",
        "families": [
          {
            "id": "markdown",
            "metrics": {
              "all": {
                "files": 1,
                "bytes": 20
              },
              "unignored": {
                "files": 1,
                "bytes": 20
              }
            },
            "extensions": [
              {
                "extension": ".md",
                "metrics": {
                  "all": {
                    "files": 1,
                    "bytes": 20
                  },
                  "unignored": {
                    "files": 1,
                    "bytes": 20
                  }
                }
              }
            ]
          }
        ]
      },
      {
        "id": "other",
        "families": [
          {
            "id": "log-files",
            "metrics": {
              "all": {
                "files": 2,
                "bytes": 90
              },
              "unignored": {
                "files": 0,
                "bytes": 0
              }
            },
            "extensions": [
              {
                "extension": ".log",
                "metrics": {
                  "all": {
                    "files": 2,
                    "bytes": 90
                  },
                  "unignored": {
                    "files": 0,
                    "bytes": 0
                  }
                }
              }
            ]
          }
        ]
      }
    ],
    "no_extension": {
      "metrics": {
        "all": {
          "files": 0,
          "bytes": 0
        },
        "unignored": {
          "files": 0,
          "bytes": 0
        }
      },
      "filenames": [],
      "others": null
    },
    "remaining_types": {
      "metrics": {
        "all": {
          "files": 0,
          "bytes": 0
        },
        "unignored": {
          "files": 0,
          "bytes": 0
        }
      },
      "extensions": [],
      "others": null
    }
  },
  "file_type_legend": {
    "schema": "file-type-legend-v1",
    "limit": 9,
    "minimum_share_percent": 1,
    "files": {
      "all": {
        "total": 10,
        "named": [
          {
            "family": "python",
            "value": 7
          },
          {
            "family": "log-files",
            "value": 2
          },
          {
            "family": "markdown",
            "value": 1
          }
        ],
        "other": 0
      },
      "unignored": {
        "total": 8,
        "named": [
          {
            "family": "python",
            "value": 7
          },
          {
            "family": "markdown",
            "value": 1
          }
        ],
        "other": 0
      }
    },
    "bytes": {
      "all": {
        "total": 500,
        "named": [
          {
            "family": "python",
            "value": 390
          },
          {
            "family": "log-files",
            "value": 90
          },
          {
            "family": "markdown",
            "value": 20
          }
        ],
        "other": 0
      },
      "unignored": {
        "total": 410,
        "named": [
          {
            "family": "python",
            "value": 390
          },
          {
            "family": "markdown",
            "value": 20
          }
        ],
        "other": 0
      }
    }
  },
  "index_status": "done",
  "indexed_files": 12,
  "max_files": 500000,
  "truncated": false
}
? 0
```

A fully ignored folder is not a child at all.
At the root, `build/` is left out, while the root’s totals still count its file, and its
`dominant_ext` is still `.bin`, which only an ignored file has: totals and
`dominant_ext` count every file.

```console
$ metab denseroot --api '/api/rollup?path=.&depth=1&ignored=exclude&encoding=compact' > root.out
? 0
```

```console
$ sed -n '/"node"/,/"ext_tallies"/p' root.out
  "node": {
    "name": "denseroot",
    "path": "",
    "type": "dir",
    "state": "complete",
    "total_files": 12,
    "total_size": 920,
    "unignored_files": 9,
    "unignored_size": 430,
    "mtime": 1700000000.0,
    "gitignored": false,
    "dominant_ext": ".bin",
    "children": [
      {
        "name": "src",
        "path": "src",
        "type": "dir",
        "state": "complete",
        "total_files": 10,
        "total_size": 500,
        "unignored_files": 8,
        "unignored_size": 410,
        "mtime": 1700000000.0,
        "gitignored": false,
        "dominant_ext": ".py",
        "children": null
      }
    ],
    "files": [
      [
        "top.md",
        20,
        1700000000.0,
        ".md",
        0
      ]
    ]
  },
  "ext_tallies": [
? 0
```

## Test: a node budget is shared by what each folder holds

`nodes=8` is `src` and seven more.
`src` emits its three children, and `lib`, the one folder left, may spend the four nodes
that remain, its share of the demand still waiting.
The four files it leaves out are in its `rest`; `children: null` would mean a folder the
budget did not reach.
With ignored entries included, `trace.log` spends a node like any other.

```console
$ metab denseroot --api '/api/rollup?path=src&depth=max&top=max&nodes=8'
api: /api/rollup?path=src&depth=max&top=max&nodes=8
status: 200
{
  "root": "<ROOT>",
  "path": "src",
  "node": {
    "name": "src",
    "path": "src",
    "type": "dir",
    "state": "complete",
    "total_files": 10,
    "total_size": 500,
    "unignored_files": 8,
    "unignored_size": 410,
    "mtime": 1700000000.0,
    "gitignored": false,
    "dominant_ext": ".py",
    "children": [
      {
        "name": "lib",
        "path": "src/lib",
        "type": "dir",
        "state": "complete",
        "total_files": 8,
        "total_size": 240,
        "unignored_files": 7,
        "unignored_size": 210,
        "mtime": 1700000000.0,
        "gitignored": false,
        "dominant_ext": ".py",
        "children": [
          {
            "name": "util.py",
            "path": "src/lib/util.py",
            "type": "file",
            "size": 100,
            "mtime": 1700000000.0,
            "ext": ".py",
            "gitignored": false
          },
          {
            "name": "io.py",
            "path": "src/lib/io.py",
            "type": "file",
            "size": 50,
            "mtime": 1700000000.0,
            "ext": ".py",
            "gitignored": false
          },
          {
            "name": "trace.log",
            "path": "src/lib/trace.log",
            "type": "file",
            "size": 30,
            "mtime": 1700000000.0,
            "ext": ".log",
            "gitignored": true
          },
          {
            "name": "notes v2.md",
            "path": "src/lib/notes v2.md",
            "type": "file",
            "size": 20,
            "mtime": 1700000000.0,
            "ext": ".md",
            "gitignored": false
          }
        ],
        "rest": {
          "dirs": 0,
          "files": 4,
          "size": 40,
          "unignored_files": 4,
          "unignored_size": 40
        }
      },
      {
        "name": "main.py",
        "path": "src/main.py",
        "type": "file",
        "size": 200,
        "mtime": 1700000000.0,
        "ext": ".py",
        "gitignored": false
      },
      {
        "name": "run.log",
        "path": "src/run.log",
        "type": "file",
        "size": 60,
        "mtime": 1700000000.0,
        "ext": ".log",
        "gitignored": true
      }
    ]
  },
  "ext_tallies": [
    [
      ".py",
      7,
      390,
      7,
      390
    ],
    [
      ".log",
      2,
      90,
      0,
      0
    ],
    [
      ".md",
      1,
      20,
      1,
      20
    ]
  ],
  "file_type_breakdown": {
    "schema": "file-type-breakdown-v1",
    "registry": {
      "schema_version": 5,
      "revision": 5,
      "fingerprint": "526dd932ae6bbed9e2e5e4a2d134b3f4aeacf9abcb6a156a9f3b94724c16708c"
    },
    "metrics": {
      "all": {
        "files": 10,
        "bytes": 500
      },
      "unignored": {
        "files": 8,
        "bytes": 410
      }
    },
    "groups": [
      {
        "id": "code",
        "families": [
          {
            "id": "python",
            "metrics": {
              "all": {
                "files": 7,
                "bytes": 390
              },
              "unignored": {
                "files": 7,
                "bytes": 390
              }
            },
            "extensions": [
              {
                "extension": ".py",
                "metrics": {
                  "all": {
                    "files": 7,
                    "bytes": 390
                  },
                  "unignored": {
                    "files": 7,
                    "bytes": 390
                  }
                }
              }
            ]
          }
        ]
      },
      {
        "id": "docs",
        "families": [
          {
            "id": "markdown",
            "metrics": {
              "all": {
                "files": 1,
                "bytes": 20
              },
              "unignored": {
                "files": 1,
                "bytes": 20
              }
            },
            "extensions": [
              {
                "extension": ".md",
                "metrics": {
                  "all": {
                    "files": 1,
                    "bytes": 20
                  },
                  "unignored": {
                    "files": 1,
                    "bytes": 20
                  }
                }
              }
            ]
          }
        ]
      },
      {
        "id": "other",
        "families": [
          {
            "id": "log-files",
            "metrics": {
              "all": {
                "files": 2,
                "bytes": 90
              },
              "unignored": {
                "files": 0,
                "bytes": 0
              }
            },
            "extensions": [
              {
                "extension": ".log",
                "metrics": {
                  "all": {
                    "files": 2,
                    "bytes": 90
                  },
                  "unignored": {
                    "files": 0,
                    "bytes": 0
                  }
                }
              }
            ]
          }
        ]
      }
    ],
    "no_extension": {
      "metrics": {
        "all": {
          "files": 0,
          "bytes": 0
        },
        "unignored": {
          "files": 0,
          "bytes": 0
        }
      },
      "filenames": [],
      "others": null
    },
    "remaining_types": {
      "metrics": {
        "all": {
          "files": 0,
          "bytes": 0
        },
        "unignored": {
          "files": 0,
          "bytes": 0
        }
      },
      "extensions": [],
      "others": null
    }
  },
  "file_type_legend": {
    "schema": "file-type-legend-v1",
    "limit": 9,
    "minimum_share_percent": 1,
    "files": {
      "all": {
        "total": 10,
        "named": [
          {
            "family": "python",
            "value": 7
          },
          {
            "family": "log-files",
            "value": 2
          },
          {
            "family": "markdown",
            "value": 1
          }
        ],
        "other": 0
      },
      "unignored": {
        "total": 8,
        "named": [
          {
            "family": "python",
            "value": 7
          },
          {
            "family": "markdown",
            "value": 1
          }
        ],
        "other": 0
      }
    },
    "bytes": {
      "all": {
        "total": 500,
        "named": [
          {
            "family": "python",
            "value": 390
          },
          {
            "family": "log-files",
            "value": 90
          },
          {
            "family": "markdown",
            "value": 20
          }
        ],
        "other": 0
      },
      "unignored": {
        "total": 410,
        "named": [
          {
            "family": "python",
            "value": 390
          },
          {
            "family": "markdown",
            "value": 20
          }
        ],
        "other": 0
      }
    }
  },
  "index_status": "done",
  "indexed_files": 12,
  "max_files": 500000,
  "truncated": false
}
? 0
```

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
  mkdir -p legendroot/build &&
  git -C legendroot init -q --initial-branch=main . &&
  printf 'build/\n' > legendroot/.gitignore &&
  for i in $(seq 1 10); do printf 'jj' > legendroot/d$i.json; done &&
  for i in $(seq 1 20); do printf 'jj' > legendroot/build/b$i.json; done &&
  for i in $(seq 1 20); do printf 'yyy' > legendroot/c$i.yaml; done &&
  for i in $(seq 1 15); do printf '%020d' 0 > legendroot/m$i.md; done &&
  for i in $(seq 1 12); do printf '%025d' 0 > legendroot/t$i.ts; done &&
  for i in $(seq 1 8); do printf '%050d' 0 > legendroot/p$i.py; done &&
  for i in $(seq 1 6); do printf '%0100d' 0 > legendroot/s$i.js; done &&
  printf '%010d' 0 > legendroot/r1.rs &&
  for i in $(seq 1 5); do printf 'nnnn' > legendroot/notes$i; done &&
  for i in $(seq 1 3); do printf '%050d' 0 > legendroot/u$i.zzq; done &&
  find legendroot -path legendroot/.git -prune -o -exec touch -t 202311142213.20 {} +
---
# Golden test: the File Overview legend through `--api`

File Overview shows a legend of a folder’s largest file-type families under its
population bars, and keeps the full type table behind Details.
Which families the legend names is decided by `/api/rollup`, as `file_type_legend`, so
this transcript pins the decision through `metab` on a real folder.

The fixture has 100 files, 20 of them JSON files in an ignored `build/` directory:

| Type | Files | Bytes each |
| --- | --- | --- |
| JSON | 30, of which 20 ignored | 2 |
| YAML | 20 | 3 |
| Markdown | 15 | 20 |
| TypeScript | 12 | 25 |
| Python | 8 | 50 |
| JavaScript | 6 | 100 |
| Rust | 1 | 10 |
| No extension | 5 | 4 |
| `.zzq`, an unknown extension | 3 | 50 |

The legend answers every measure and population at once, so the browser switches them
without asking again:

- By files over the whole folder it names JSON, YAML, Markdown, TypeScript, and Python,
  and leaves 15 files for Other: JavaScript, Rust, No extension, and Other types, which
  are never named.
- By files over the unignored files, JSON falls to fourth.
- By bytes, JavaScript leads.
  Markdown and TypeScript tie at 300 bytes and Markdown comes first on files; JSON and
  YAML tie at 60 bytes and JSON takes the fifth place on files.
- Over unignored bytes YAML takes JSON’s place.
- At most five are named, and only above 1% of the population, the share at which the
  type table folds a row into “N more”.

## Test: a folder’s rollup carries its legend

```console
$ metab legendroot --api '/api/rollup?path=.&depth=0'
api: /api/rollup?path=.&depth=0
status: 200
{
  "root": "<ROOT>",
  "path": "",
  "node": {
    "name": "legendroot",
    "path": "",
    "type": "dir",
    "state": "complete",
    "total_files": 100,
    "total_size": 1900,
    "unignored_files": 80,
    "unignored_size": 1860,
    "mtime": 1700000000.0,
    "gitignored": false,
    "dominant_ext": ".js",
    "children": null
  },
  "ext_tallies": [
    [
      ".js",
      6,
      600,
      6,
      600
    ],
    [
      ".py",
      8,
      400,
      8,
      400
    ],
    [
      ".md",
      15,
      300,
      15,
      300
    ],
    [
      ".ts",
      12,
      300,
      12,
      300
    ],
    [
      ".zzq",
      3,
      150,
      3,
      150
    ],
    [
      ".yaml",
      20,
      60,
      20,
      60
    ],
    [
      ".json",
      30,
      60,
      10,
      20
    ],
    [
      "(none)",
      5,
      20,
      5,
      20
    ],
    [
      ".rs",
      1,
      10,
      1,
      10
    ]
  ],
  "file_type_breakdown": {
    "schema": "file-type-breakdown-v1",
    "registry": {
      "schema_version": 5,
      "revision": 3,
      "fingerprint": "78c00764ddfcb68cc0724f8b9801428f0d3fcb178d6ed5f29cc720ffbcfe7704"
    },
    "metrics": {
      "all": {
        "files": 100,
        "bytes": 1900
      },
      "unignored": {
        "files": 80,
        "bytes": 1860
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
                "files": 8,
                "bytes": 400
              },
              "unignored": {
                "files": 8,
                "bytes": 400
              }
            },
            "extensions": [
              {
                "extension": ".py",
                "metrics": {
                  "all": {
                    "files": 8,
                    "bytes": 400
                  },
                  "unignored": {
                    "files": 8,
                    "bytes": 400
                  }
                }
              }
            ]
          },
          {
            "id": "javascript",
            "metrics": {
              "all": {
                "files": 6,
                "bytes": 600
              },
              "unignored": {
                "files": 6,
                "bytes": 600
              }
            },
            "extensions": [
              {
                "extension": ".js",
                "metrics": {
                  "all": {
                    "files": 6,
                    "bytes": 600
                  },
                  "unignored": {
                    "files": 6,
                    "bytes": 600
                  }
                }
              }
            ]
          },
          {
            "id": "typescript",
            "metrics": {
              "all": {
                "files": 12,
                "bytes": 300
              },
              "unignored": {
                "files": 12,
                "bytes": 300
              }
            },
            "extensions": [
              {
                "extension": ".ts",
                "metrics": {
                  "all": {
                    "files": 12,
                    "bytes": 300
                  },
                  "unignored": {
                    "files": 12,
                    "bytes": 300
                  }
                }
              }
            ]
          },
          {
            "id": "rust",
            "metrics": {
              "all": {
                "files": 1,
                "bytes": 10
              },
              "unignored": {
                "files": 1,
                "bytes": 10
              }
            },
            "extensions": [
              {
                "extension": ".rs",
                "metrics": {
                  "all": {
                    "files": 1,
                    "bytes": 10
                  },
                  "unignored": {
                    "files": 1,
                    "bytes": 10
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
                "files": 15,
                "bytes": 300
              },
              "unignored": {
                "files": 15,
                "bytes": 300
              }
            },
            "extensions": [
              {
                "extension": ".md",
                "metrics": {
                  "all": {
                    "files": 15,
                    "bytes": 300
                  },
                  "unignored": {
                    "files": 15,
                    "bytes": 300
                  }
                }
              }
            ]
          }
        ]
      },
      {
        "id": "data",
        "families": [
          {
            "id": "json",
            "metrics": {
              "all": {
                "files": 30,
                "bytes": 60
              },
              "unignored": {
                "files": 10,
                "bytes": 20
              }
            },
            "extensions": [
              {
                "extension": ".json",
                "metrics": {
                  "all": {
                    "files": 30,
                    "bytes": 60
                  },
                  "unignored": {
                    "files": 10,
                    "bytes": 20
                  }
                }
              }
            ]
          },
          {
            "id": "yaml",
            "metrics": {
              "all": {
                "files": 20,
                "bytes": 60
              },
              "unignored": {
                "files": 20,
                "bytes": 60
              }
            },
            "extensions": [
              {
                "extension": ".yaml",
                "metrics": {
                  "all": {
                    "files": 20,
                    "bytes": 60
                  },
                  "unignored": {
                    "files": 20,
                    "bytes": 60
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
          "files": 5,
          "bytes": 20
        },
        "unignored": {
          "files": 5,
          "bytes": 20
        }
      },
      "filenames": [
        {
          "basename": "notes1",
          "metrics": {
            "all": {
              "files": 1,
              "bytes": 4
            },
            "unignored": {
              "files": 1,
              "bytes": 4
            }
          }
        },
        {
          "basename": "notes2",
          "metrics": {
            "all": {
              "files": 1,
              "bytes": 4
            },
            "unignored": {
              "files": 1,
              "bytes": 4
            }
          }
        },
        {
          "basename": "notes3",
          "metrics": {
            "all": {
              "files": 1,
              "bytes": 4
            },
            "unignored": {
              "files": 1,
              "bytes": 4
            }
          }
        },
        {
          "basename": "notes4",
          "metrics": {
            "all": {
              "files": 1,
              "bytes": 4
            },
            "unignored": {
              "files": 1,
              "bytes": 4
            }
          }
        },
        {
          "basename": "notes5",
          "metrics": {
            "all": {
              "files": 1,
              "bytes": 4
            },
            "unignored": {
              "files": 1,
              "bytes": 4
            }
          }
        }
      ],
      "others": null
    },
    "remaining_types": {
      "metrics": {
        "all": {
          "files": 3,
          "bytes": 150
        },
        "unignored": {
          "files": 3,
          "bytes": 150
        }
      },
      "extensions": [
        {
          "extension": ".zzq",
          "metrics": {
            "all": {
              "files": 3,
              "bytes": 150
            },
            "unignored": {
              "files": 3,
              "bytes": 150
            }
          }
        }
      ],
      "others": null
    }
  },
  "file_type_legend": {
    "schema": "file-type-legend-v1",
    "limit": 5,
    "minimum_share_percent": 1,
    "files": {
      "all": {
        "total": 100,
        "named": [
          {
            "family": "json",
            "value": 30
          },
          {
            "family": "yaml",
            "value": 20
          },
          {
            "family": "markdown",
            "value": 15
          },
          {
            "family": "typescript",
            "value": 12
          },
          {
            "family": "python",
            "value": 8
          }
        ],
        "other": 15
      },
      "unignored": {
        "total": 80,
        "named": [
          {
            "family": "yaml",
            "value": 20
          },
          {
            "family": "markdown",
            "value": 15
          },
          {
            "family": "typescript",
            "value": 12
          },
          {
            "family": "json",
            "value": 10
          },
          {
            "family": "python",
            "value": 8
          }
        ],
        "other": 15
      }
    },
    "bytes": {
      "all": {
        "total": 1900,
        "named": [
          {
            "family": "javascript",
            "value": 600
          },
          {
            "family": "python",
            "value": 400
          },
          {
            "family": "markdown",
            "value": 300
          },
          {
            "family": "typescript",
            "value": 300
          },
          {
            "family": "json",
            "value": 60
          }
        ],
        "other": 240
      },
      "unignored": {
        "total": 1860,
        "named": [
          {
            "family": "javascript",
            "value": 600
          },
          {
            "family": "python",
            "value": 400
          },
          {
            "family": "markdown",
            "value": 300
          },
          {
            "family": "typescript",
            "value": 300
          },
          {
            "family": "yaml",
            "value": 60
          }
        ],
        "other": 200
      }
    }
  },
  "index_status": "done",
  "indexed_files": 100,
  "max_files": 500000,
  "truncated": false
}
? 0
```

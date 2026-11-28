---
sandbox: true
path:
  - ../../.venv/bin
env:
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
before: >-
  mkdir corpus &&
  printf '%s\n' '{"speaker":{"name":"Ada","roles":["host",null]}}' > corpus/block.json &&
  printf '%s\n' 'speaker:' '  name: Ada' '  roles: [host, null]' > corpus/block.yaml &&
  printf '%s\n' 'speaker: {name: Ada, roles: [host, null]}' > corpus/flow.yaml &&
  printf '%s\r\n' '---' '# Original comment' 'speaker: {name: Ada}' '---' '# Body' > corpus/flow.md &&
  printf '%s\n' '---' '{"speaker":{"name":"Ada"}}' '---' '# Body' > corpus/json.md &&
  printf '%s\r\n' '# Notes' '' '~~~json' '{"who": [' '  "Zoé", null' ']}' '~~~' 'After.' > corpus/fences.md &&
  touch -t 202311142213.20 corpus/block.json corpus/block.yaml corpus/flow.yaml corpus/flow.md corpus/json.md corpus/fences.md
---
# Golden test: structured JSON and YAML nodes

## Test: Markdown frontmatter keeps comments and original line endings

```console
$ metab corpus --api '/api/plugin/structured/parsed?projection=nodes&frontmatter=1&source=1&path=flow.md'
api: /api/plugin/structured/parsed?projection=nodes&frontmatter=1&source=1&path=flow.md
status: 200
{
  "type": "structured_nodes",
  "path": "flow.md",
  "ext": ".md",
  "mtime_hash": "flow_md_60_1700000000000000000_k3mw680b0ukgjxfrupkr41vxo1vdxm8",
  "size": 60,
  "status": "ready",
  "document_count": 1,
  "record_table": false,
  "node": {
    "kind": "object",
    "child_count": 1,
    "source_range": {
      "start_byte": 25,
      "end_byte": 47
    }
  },
  "children": [
    {
      "segment": "speaker",
      "node": {
        "kind": "object",
        "child_count": 1,
        "source_range": {
          "start_byte": 34,
          "end_byte": 45
        }
      }
    }
  ],
  "next_offset": null,
  "excerpt": {
    "start_byte": 5,
    "end_byte": 47
  },
  "source_text": "# Original comment\r\nspeaker: {name: Ada}\r\n",
  "source_start_line": 2
}
? 0
```

## Test: a JSON frontmatter value opens its original spelling and line

```console
$ metab corpus --api '/api/plugin/structured/parsed?projection=nodes&frontmatter=1&source=1&path=json.md&node=%5B%22speaker%22%5D'
api: /api/plugin/structured/parsed?projection=nodes&frontmatter=1&source=1&path=json.md&node=%5B%22speaker%22%5D
status: 200
{
  "type": "structured_nodes",
  "path": "json.md",
  "ext": ".md",
  "mtime_hash": "json_md_42_1700000000000000000_p9okp7hr3or2wn3zggzj75xgndf5fn5",
  "size": 42,
  "status": "ready",
  "document_count": 1,
  "record_table": false,
  "node": {
    "kind": "object",
    "child_count": 1,
    "source_range": {
      "start_byte": 15,
      "end_byte": 29
    }
  },
  "children": [
    {
      "segment": "name",
      "node": {
        "kind": "string",
        "child_count": 0,
        "source_range": {
          "start_byte": 23,
          "end_byte": 28
        },
        "value": "Ada"
      }
    }
  ],
  "next_offset": null,
  "excerpt": {
    "start_byte": 4,
    "end_byte": 31
  },
  "source_text": "{\"name\":\"Ada\"}",
  "source_start_line": 2,
  "format": "json"
}
? 0
```

## Test: JSON yields ordered children with original source ranges

```console
$ metab corpus --api '/api/plugin/structured/parsed?projection=nodes&path=block.json&node=%5B%22speaker%22%5D'
api: /api/plugin/structured/parsed?projection=nodes&path=block.json&node=%5B%22speaker%22%5D
status: 200
{
  "type": "structured_nodes",
  "path": "block.json",
  "ext": ".json",
  "mtime_hash": "block_json_49_1700000000000000000_r1puyrpz4am2pa4q2z9cjk98wplescz",
  "size": 49,
  "status": "ready",
  "document_count": 1,
  "record_table": false,
  "node": {
    "kind": "object",
    "child_count": 2,
    "source_range": {
      "start_byte": 11,
      "end_byte": 47
    }
  },
  "children": [
    {
      "segment": "name",
      "node": {
        "kind": "string",
        "child_count": 0,
        "source_range": {
          "start_byte": 19,
          "end_byte": 24
        },
        "value": "Ada"
      }
    },
    {
      "segment": "roles",
      "node": {
        "kind": "array",
        "child_count": 2,
        "source_range": {
          "start_byte": 33,
          "end_byte": 46
        }
      }
    }
  ],
  "next_offset": null
}
? 0
```

## Test: block YAML yields the same ordered children with its own source ranges

```console
$ metab corpus --api '/api/plugin/structured/parsed?projection=nodes&path=block.yaml&node=%5B%22speaker%22%5D'
api: /api/plugin/structured/parsed?projection=nodes&path=block.yaml&node=%5B%22speaker%22%5D
status: 200
{
  "type": "structured_nodes",
  "path": "block.yaml",
  "ext": ".yaml",
  "mtime_hash": "block_yaml_43_1700000000000000000_dz3w44fa486yxsdeyhdgqb64l2bt00i",
  "size": 43,
  "status": "ready",
  "document_count": 1,
  "record_table": false,
  "node": {
    "kind": "object",
    "child_count": 2,
    "source_range": {
      "start_byte": 11,
      "end_byte": 43
    }
  },
  "children": [
    {
      "segment": "name",
      "node": {
        "kind": "string",
        "child_count": 0,
        "source_range": {
          "start_byte": 17,
          "end_byte": 20
        },
        "value": "Ada"
      }
    },
    {
      "segment": "roles",
      "node": {
        "kind": "array",
        "child_count": 2,
        "source_range": {
          "start_byte": 30,
          "end_byte": 42
        }
      }
    }
  ],
  "next_offset": null
}
? 0
```

## Test: flow YAML yields the same ordered children with its own source ranges

```console
$ metab corpus --api '/api/plugin/structured/parsed?projection=nodes&path=flow.yaml&node=%5B%22speaker%22%5D'
api: /api/plugin/structured/parsed?projection=nodes&path=flow.yaml&node=%5B%22speaker%22%5D
status: 200
{
  "type": "structured_nodes",
  "path": "flow.yaml",
  "ext": ".yaml",
  "mtime_hash": "flow_yaml_42_1700000000000000000_cf3afy525otkf10pba0gmi6b1n1nxr2",
  "size": 42,
  "status": "ready",
  "document_count": 1,
  "record_table": false,
  "node": {
    "kind": "object",
    "child_count": 2,
    "source_range": {
      "start_byte": 9,
      "end_byte": 41
    }
  },
  "children": [
    {
      "segment": "name",
      "node": {
        "kind": "string",
        "child_count": 0,
        "source_range": {
          "start_byte": 16,
          "end_byte": 19
        },
        "value": "Ada"
      }
    },
    {
      "segment": "roles",
      "node": {
        "kind": "array",
        "child_count": 2,
        "source_range": {
          "start_byte": 28,
          "end_byte": 40
        }
      }
    }
  ],
  "next_offset": null
}
? 0
```

## Test: a sequence page preserves index and explicit null

```console
$ metab corpus --api '/api/plugin/structured/parsed?projection=nodes&path=flow.yaml&node=%5B%22speaker%22%2C%22roles%22%5D&offset=1&limit=1'
api: /api/plugin/structured/parsed?projection=nodes&path=flow.yaml&node=%5B%22speaker%22%2C%22roles%22%5D&offset=1&limit=1
status: 200
{
  "type": "structured_nodes",
  "path": "flow.yaml",
  "ext": ".yaml",
  "mtime_hash": "flow_yaml_42_1700000000000000000_cf3afy525otkf10pba0gmi6b1n1nxr2",
  "size": 42,
  "status": "ready",
  "document_count": 1,
  "record_table": false,
  "node": {
    "kind": "array",
    "child_count": 2,
    "source_range": {
      "start_byte": 28,
      "end_byte": 40
    }
  },
  "children": [
    {
      "segment": 1,
      "node": {
        "kind": "null",
        "child_count": 0,
        "source_range": {
          "start_byte": 35,
          "end_byte": 39
        },
        "value": null
      }
    }
  ],
  "next_offset": null
}
? 0
```

## Test: an inline page keeps nested values and their original source ranges

```console
$ metab corpus --api '/api/plugin/structured/parsed?projection=nodes&path=flow.md&frontmatter=1&depth=3'
api: /api/plugin/structured/parsed?projection=nodes&path=flow.md&frontmatter=1&depth=3
status: 200
{
  "type": "structured_nodes",
  "path": "flow.md",
  "ext": ".md",
  "mtime_hash": "flow_md_60_1700000000000000000_k3mw680b0ukgjxfrupkr41vxo1vdxm8",
  "size": 60,
  "status": "ready",
  "document_count": 1,
  "record_table": false,
  "node": {
    "kind": "object",
    "child_count": 1,
    "source_range": {
      "start_byte": 25,
      "end_byte": 47
    }
  },
  "children": [
    {
      "segment": "speaker",
      "node": {
        "kind": "object",
        "child_count": 1,
        "source_range": {
          "start_byte": 34,
          "end_byte": 45
        },
        "children": [
          {
            "segment": "name",
            "node": {
              "kind": "string",
              "child_count": 0,
              "source_range": {
                "start_byte": 41,
                "end_byte": 44
              },
              "value": "Ada"
            }
          }
        ]
      }
    }
  ],
  "next_offset": null,
  "excerpt": {
    "start_byte": 5,
    "end_byte": 47
  }
}
? 0
```

## Test: a page from a stale file version asks for refresh

```console
$ metab corpus --api '/api/plugin/structured/parsed?projection=nodes&path=flow.yaml&mtime_hash=old'
api: /api/plugin/structured/parsed?projection=nodes&path=flow.yaml&mtime_hash=old
status: 409
{
  "type": "structured_nodes",
  "path": "flow.yaml",
  "ext": ".yaml",
  "mtime_hash": "flow_yaml_42_1700000000000000000_cf3afy525otkf10pba0gmi6b1n1nxr2",
  "size": 42,
  "status": "changed"
}
Error: /api/plugin/structured/parsed?projection=nodes&path=flow.yaml&mtime_hash=old returned HTTP 409
? 1
```

## Test: copy a nested field with its key and the complete value

```console
$ metab corpus --api '/api/plugin/structured/parsed?projection=nodes&path=flow.yaml&node=%5B%22speaker%22%2C%22roles%22%5D&copy=row&limit=1'
api: /api/plugin/structured/parsed?projection=nodes&path=flow.yaml&node=%5B%22speaker%22%2C%22roles%22%5D&copy=row&limit=1
status: 200
{
  "type": "structured_nodes",
  "path": "flow.yaml",
  "ext": ".yaml",
  "mtime_hash": "flow_yaml_42_1700000000000000000_cf3afy525otkf10pba0gmi6b1n1nxr2",
  "size": 42,
  "copy_text": "{roles: [host, null]}",
  "status": "ready",
  "document_count": 1,
  "record_table": false,
  "node": {
    "kind": "array",
    "child_count": 2,
    "source_range": {
      "start_byte": 28,
      "end_byte": 40
    }
  },
  "children": [
    {
      "segment": 0,
      "node": {
        "kind": "string",
        "child_count": 0,
        "source_range": {
          "start_byte": 29,
          "end_byte": 33
        },
        "value": "host"
      }
    }
  ],
  "next_offset": 1
}
? 0
```

## Test: a fenced field keeps its original lines, parsed children, and complete copy

```console
$ metab corpus --api '/api/plugin/structured/parsed?projection=nodes&path=fences.md&fence_line=3&node=%5B%22who%22%5D&source=1&tree=1&copy=row&limit=1'
api: /api/plugin/structured/parsed?projection=nodes&path=fences.md&fence_line=3&node=%5B%22who%22%5D&source=1&tree=1&copy=row&limit=1
status: 200
{
  "type": "structured_nodes",
  "path": "fences.md",
  "ext": ".md",
  "mtime_hash": "fences_md_64_1700000000000000000_deq6q02i2lmb3ho4fsxtfbqtc38gmig",
  "size": 64,
  "copy_text": "{\"who\": [\r\n  \"Zoé\", null\r\n]}",
  "tree_value": [
    "Zoé",
    null
  ],
  "status": "ready",
  "document_count": 1,
  "record_table": false,
  "node": {
    "kind": "array",
    "child_count": 2,
    "source_range": {
      "start_byte": 28,
      "end_byte": 48
    }
  },
  "children": [
    {
      "segment": 0,
      "node": {
        "kind": "string",
        "child_count": 0,
        "source_range": {
          "start_byte": 33,
          "end_byte": 39
        },
        "value": "Zoé"
      }
    }
  ],
  "next_offset": 1,
  "excerpt": {
    "start_byte": 20,
    "end_byte": 51
  },
  "source_text": "[\r\n  \"Zoé\", null\r\n]",
  "source_start_line": 4,
  "format": "json"
}
? 0
```

```console
$ (printf 'inventory: demo\nentries:\n'; awk 'BEGIN {for(i=1;i<=1200;i++) printf "  entry_%04d: generated member for the documented inventory\n",i}') > corpus/large.yaml
? 0
```

```console
$ metab corpus --api '/api/plugin/structured/parsed?projection=nodes&path=large.yaml&depth=2' --format json > oversized-preview.json
? 0
```

```console
$ jq -c '{status,preview,partial:.node.partial,child_preview:(.children[]|select(.segment=="entries")|.node.partial),has_source_range:(.node|has("source_range"))}' oversized-preview.json
{"status":"ready","preview":true,"partial":true,"child_preview":true,"has_source_range":false}
? 0
```

```console
$ metab corpus --api '/api/plugin/structured/parsed?projection=nodes&path=large.yaml&node=%5B%22entries%22,%22entry_0001%22%5D&copy=row' --format json > oversized-copy.json
? 0
```

```console
$ jq -c '{status,copy_text}' oversized-copy.json
{"status":"ready","copy_text":"entry_0001: generated member for the documented inventory"}
? 0
```

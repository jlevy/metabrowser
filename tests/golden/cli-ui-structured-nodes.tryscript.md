---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden test: structured node tables

## Test: expand, collapse and page a branch in place, then dispose a pending page

```console
$ node tests/dom/structured-node-table-session.js
{
  "summaries": [
    "[\"host\", \"editor\"]",
    "{\"a\": 1, \"b\": [true, null]}",
    "{\"quote\\\"\": \"line\\nnext\"}",
    "[9007199254740993]",
    "[1, …] (12 items)",
    "{…} (2 keys)"
  ],
  "root": "FieldValue0[{\"record\": {…}}] (1 item)0{\"record\": {…}} (1 key)record{…} (2 keys)keep\"sibling\"Next page",
  "nested": "FieldValue0[{\"record\": {…}}] (1 item)0{\"record\": {…}} (1 key)record{…} (2 keys)id9007199254740993Morekeep\"sibling\"Next page",
  "paged": "FieldValue0[{\"record\": {…}}] (1 item)0{\"record\": {…}} (1 key)record{…} (2 keys)last9007199254740993First pagekeep\"sibling\"Next page",
  "positions": [
    {
      "path": [],
      "offset": 0,
      "depth": 3
    },
    {
      "path": [
        "0",
        0,
        "record"
      ],
      "offset": 0,
      "depth": 1
    },
    {
      "path": [
        "0",
        0,
        "record"
      ],
      "offset": 1,
      "depth": 1
    },
    {
      "path": [],
      "offset": 1,
      "depth": 3
    }
  ],
  "selections": [
    [],
    [
      "0",
      0,
      "record"
    ],
    [
      "0",
      0,
      "record"
    ],
    [
      "0",
      0,
      "record"
    ],
    []
  ]
}
? 0
```

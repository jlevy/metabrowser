---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
before: >-
  uv --config-file "$TRYSCRIPT_TEST_DIR/../../uv.toml" run --frozen --no-sync
  --project "$TRYSCRIPT_TEST_DIR/../.." python "$TRYSCRIPT_TEST_DIR/../cache_home_fixture.py" .
  > fixture.log 2>&1
---
# Golden tests: repository cache state through `--api`

The `/api/cache/` routes are how persisted cache state is asserted: layout and config
formats, source and store identity, alias generations, publication state, and what
reclamation left. They report logical state only, never a cache path, a pack file, a Git
internal, or the application home itself.

`tests/cache_home_fixture.py` builds every home below the sandbox with the production
writers: `ensure_home` and `migrate_layout`, staged publication under the owning locks,
`quarantine_entries`, and `reclaim_store`. Addresses, versions, and timestamps are
fixed, so identities, slugs, and records are asserted literally.
The one random value is the quarantine entry name, which `quarantine_entries` chooses,
so it is elided.

Each command names its home with `METABROWSER_HOME`, because the routes resolve the home
per request. `root` is an empty directory to serve; the cache routes do not read it.

## Test: a missing home is an answer, not an error

```console
$ METABROWSER_HOME=$PWD/missing metab root --api /api/cache/layout
api: /api/cache/layout
status: 200
{
  "home": "absent",
  "supported_format": "f01",
  "state": "absent",
  "layout": null,
  "config": null,
  "reclamation": null
}
? 0
```

```console
$ METABROWSER_HOME=$PWD/missing metab root --api /api/cache/sources
api: /api/cache/sources
status: 200
{
  "home": "absent",
  "layout_format": null,
  "sources": [],
  "unrecognized_entries": 0,
  "limit": 50,
  "next_after": null
}
? 0
```

## Test: an empty cache has a current layout and nothing in it

```console
$ METABROWSER_HOME=$PWD/empty metab root --api /api/cache/layout
api: /api/cache/layout
status: 200
{
  "home": "present",
  "supported_format": "f01",
  "state": "current",
  "layout": {
    "format": "f01",
    "created_by": "0.11.0"
  },
  "config": {
    "format": "f01",
    "written_by": "0.11.0",
    "upgrades": []
  },
  "reclamation": {
    "staging_entries": 0,
    "trash_entries": 0,
    "quarantine_entries": 0,
    "quarantine": [],
    "quarantine_truncated": false
  }
}
? 0
```

```console
$ METABROWSER_HOME=$PWD/empty metab root --api /api/cache/stores
api: /api/cache/stores
status: 200
{
  "home": "present",
  "layout_format": "f01",
  "stores": [],
  "unrecognized_entries": 0,
  "limit": 50,
  "next_after": null
}
? 0
```

## Test: reclamation outcomes on a populated cache

The populated home has two flask sources, one over HTTPS and one over SSH, aliasing one
store; the SSH alias was repointed once, so it is at generation 2. click’s acquisition
published its store and source but not its alias.
jinja’s store failed revalidation and was quarantined with its alias, and werkzeug’s
unreferenced store was reclaimed, so it appears nowhere.
An interrupted acquisition left one staging entry for the next sweep.

```console
$ METABROWSER_HOME=$PWD/populated metab root --api /api/cache/layout
api: /api/cache/layout
status: 200
{
  "home": "present",
  "supported_format": "f01",
  "state": "current",
  "layout": {
    "format": "f01",
    "created_by": "0.11.0"
  },
  "config": {
    "format": "f01",
    "written_by": "0.11.0",
    "upgrades": []
  },
  "reclamation": {
    "staging_entries": 1,
    "trash_entries": 0,
    "quarantine_entries": 1,
    "quarantine": [
      {
        "entry": "quarantine-[..]",
        "sources": [
          "github-com--pallets--jinja--1b7f05892a34"
        ],
        "stores": [
          "sha256:f68db9d30e59b33c3db7869b2f860dda22207fddaf4ce29f8782c44710f1c142"
        ],
        "truncated": false
      }
    ],
    "quarantine_truncated": false
  }
}
? 0
```

## Test: sources with their identity, alias generation, and publication

```console
$ METABROWSER_HOME=$PWD/populated metab root --api /api/cache/sources
api: /api/cache/sources
status: 200
{
  "home": "present",
  "layout_format": "f01",
  "sources": [
    {
      "slug": "github-com--pallets--click--76d8973c8c6c",
      "publication": "unattached",
      "identity": {
        "id": "sha256:76d8973c8c6c75bf3de6ea688ad89b5990a44d85a3e0d203fd4c44e24b109c46",
        "display_url": "https://github.com/pallets/click",
        "clone_url": "https://github.com/pallets/click",
        "transport": "https",
        "created_at": "2026-09-17T12:00:00Z"
      },
      "alias": null,
      "state": null,
      "problems": []
    },
    {
      "slug": "github-com--pallets--flask--74fe6e07e4b9",
      "publication": "published",
      "identity": {
        "id": "sha256:74fe6e07e4b9e366cbfea79bdb0f6051ae58c0742e1a6748ba6c9dea86b1e231",
        "display_url": "git@github.com:pallets/flask.git",
        "clone_url": "git@github.com:pallets/flask.git",
        "transport": "ssh",
        "created_at": "2026-09-17T12:00:00Z"
      },
      "alias": {
        "store_id": "sha256:4c2d8559cb0179baca3afa2f633e1cfd7271b82e4fb7f0c451dfa9354aa70aff",
        "generation": 2,
        "updated_at": "2026-09-17T12:10:00Z"
      },
      "state": null,
      "problems": []
    },
    {
      "slug": "github-com--pallets--flask--e7b7fe0ffe8a",
      "publication": "published",
      "identity": {
        "id": "sha256:e7b7fe0ffe8a446772b8a863f51222c90d256e511e1a4da3daec599735962fa9",
        "display_url": "https://github.com/pallets/flask",
        "clone_url": "https://github.com/pallets/flask",
        "transport": "https",
        "created_at": "2026-09-17T12:00:00Z"
      },
      "alias": {
        "store_id": "sha256:4c2d8559cb0179baca3afa2f633e1cfd7271b82e4fb7f0c451dfa9354aa70aff",
        "generation": 1,
        "updated_at": "2026-09-17T12:00:06Z"
      },
      "state": {
        "last_opened_at": "2026-09-17T12:30:00Z"
      },
      "problems": []
    }
  ],
  "unrecognized_entries": 0,
  "limit": 50,
  "next_after": null
}
? 0
```

## Test: stores with the aliases that name them

The flask store is referenced by both sources.
click’s store is unreferenced, which is what makes it reclaimable.

```console
$ METABROWSER_HOME=$PWD/populated metab root --api /api/cache/stores
api: /api/cache/stores
status: 200
{
  "home": "present",
  "layout_format": "f01",
  "stores": [
    {
      "id": "sha256:4c2d8559cb0179baca3afa2f633e1cfd7271b82e4fb7f0c451dfa9354aa70aff",
      "publication": "published",
      "identity": {
        "created_at": "2026-09-17T12:00:00Z",
        "acquisition": {
          "strategy": "blobless",
          "git_version": "2.50.1",
          "object_format": "sha1"
        }
      },
      "state": {
        "object_state": "converging",
        "default_remote_ref": "refs/remotes/origin/trunk",
        "default_revision": "5f4c1a2e8b0d9c7e6a5f4b3c2d1e0f9a8b7c6d5e",
        "last_fetch_at": "2026-09-17T12:00:05Z",
        "last_operation": {
          "kind": "acquire",
          "outcome": "succeeded",
          "at": "2026-09-17T12:00:05Z"
        }
      },
      "problems": [],
      "referenced_by": [
        {
          "slug": "github-com--pallets--flask--74fe6e07e4b9",
          "generation": 2
        },
        {
          "slug": "github-com--pallets--flask--e7b7fe0ffe8a",
          "generation": 1
        }
      ],
      "reference_state": "referenced"
    },
    {
      "id": "sha256:c3c36fb283ea2c90a566bfb072d621839b3940b93ef33c8a53b8d4e120dc22bf",
      "publication": "published",
      "identity": {
        "created_at": "2026-09-17T12:00:00Z",
        "acquisition": {
          "strategy": "blobless",
          "git_version": "2.50.1",
          "object_format": "sha1"
        }
      },
      "state": {
        "object_state": "complete",
        "default_remote_ref": null,
        "default_revision": null,
        "last_fetch_at": "2026-09-17T12:00:05Z",
        "last_operation": {
          "kind": "acquire",
          "outcome": "succeeded",
          "at": "2026-09-17T12:00:05Z"
        }
      },
      "problems": [],
      "referenced_by": [],
      "reference_state": "unreferenced"
    }
  ],
  "unrecognized_entries": 0,
  "limit": 50,
  "next_after": null
}
? 0
```

## Test: one source with its recency and its store’s head

```console
$ METABROWSER_HOME=$PWD/populated metab root --api /api/cache/source/github-com--pallets--flask--e7b7fe0ffe8a
api: /api/cache/source/github-com--pallets--flask--e7b7fe0ffe8a
status: 200
{
  "home": "present",
  "layout_format": "f01",
  "source": {
    "slug": "github-com--pallets--flask--e7b7fe0ffe8a",
    "publication": "published",
    "identity": {
      "id": "sha256:e7b7fe0ffe8a446772b8a863f51222c90d256e511e1a4da3daec599735962fa9",
      "display_url": "https://github.com/pallets/flask",
      "clone_url": "https://github.com/pallets/flask",
      "transport": "https",
      "created_at": "2026-09-17T12:00:00Z"
    },
    "alias": {
      "store_id": "sha256:4c2d8559cb0179baca3afa2f633e1cfd7271b82e4fb7f0c451dfa9354aa70aff",
      "generation": 1,
      "updated_at": "2026-09-17T12:00:06Z"
    },
    "state": {
      "last_opened_at": "2026-09-17T12:30:00Z"
    },
    "problems": [],
    "store": {
      "id": "sha256:4c2d8559cb0179baca3afa2f633e1cfd7271b82e4fb7f0c451dfa9354aa70aff",
      "publication": "published",
      "identity": {
        "created_at": "2026-09-17T12:00:00Z",
        "acquisition": {
          "strategy": "blobless",
          "git_version": "2.50.1",
          "object_format": "sha1"
        }
      },
      "state": {
        "object_state": "converging",
        "default_remote_ref": "refs/remotes/origin/trunk",
        "default_revision": "5f4c1a2e8b0d9c7e6a5f4b3c2d1e0f9a8b7c6d5e",
        "last_fetch_at": "2026-09-17T12:00:05Z",
        "last_operation": {
          "kind": "acquire",
          "outcome": "succeeded",
          "at": "2026-09-17T12:00:05Z"
        }
      },
      "problems": []
    }
  }
}
? 0
```

## Test: pages follow slug order

```console
$ METABROWSER_HOME=$PWD/populated metab root --api '/api/cache/sources?limit=2'
api: /api/cache/sources?limit=2
status: 200
{
  "home": "present",
  "layout_format": "f01",
  "sources": [
    {
      "slug": "github-com--pallets--click--76d8973c8c6c",
      "publication": "unattached",
      "identity": {
        "id": "sha256:76d8973c8c6c75bf3de6ea688ad89b5990a44d85a3e0d203fd4c44e24b109c46",
        "display_url": "https://github.com/pallets/click",
        "clone_url": "https://github.com/pallets/click",
        "transport": "https",
        "created_at": "2026-09-17T12:00:00Z"
      },
      "alias": null,
      "state": null,
      "problems": []
    },
    {
      "slug": "github-com--pallets--flask--74fe6e07e4b9",
      "publication": "published",
      "identity": {
        "id": "sha256:74fe6e07e4b9e366cbfea79bdb0f6051ae58c0742e1a6748ba6c9dea86b1e231",
        "display_url": "git@github.com:pallets/flask.git",
        "clone_url": "git@github.com:pallets/flask.git",
        "transport": "ssh",
        "created_at": "2026-09-17T12:00:00Z"
      },
      "alias": {
        "store_id": "sha256:4c2d8559cb0179baca3afa2f633e1cfd7271b82e4fb7f0c451dfa9354aa70aff",
        "generation": 2,
        "updated_at": "2026-09-17T12:10:00Z"
      },
      "state": null,
      "problems": []
    }
  ],
  "unrecognized_entries": 0,
  "limit": 2,
  "next_after": "github-com--pallets--flask--74fe6e07e4b9"
}
? 0
```

## Test: a quarantined source is no longer a source

```console
$ METABROWSER_HOME=$PWD/populated metab root --api /api/cache/source/github-com--pallets--jinja--1b7f05892a34
api: /api/cache/source/github-com--pallets--jinja--1b7f05892a34
status: 404
{
  "error": "No source has this slug.",
  "code": "source_not_found"
}
Error: /api/cache/source/github-com--pallets--jinja--1b7f05892a34 returned HTTP 404
? 1
```

## Test: a newer home is refused before any entry is read

```console
$ METABROWSER_HOME=$PWD/future metab root --api /api/cache/sources
api: /api/cache/sources
status: 409
{
  "error": "This Metabrowser application home uses format f02, and this release reads formats up to f01. Upgrade Metabrowser, or set METABROWSER_HOME to a different directory.",
  "code": "future_format",
  "found": "f02",
  "supported": "f01"
}
Error: /api/cache/sources returned HTTP 409
? 1
```

## Test: a home other users can read is refused without naming it

```console
$ METABROWSER_HOME=$PWD/shared metab root --api /api/cache/layout
api: /api/cache/layout
status: 409
{
  "error": "The Metabrowser application home is accessible to other users (mode 0755). Run chmod 700 on it, or set METABROWSER_HOME to a private directory you own.",
  "code": "home_not_private",
  "location": "home",
  "violation": "permissive"
}
Error: /api/cache/layout returned HTTP 409
? 1
```

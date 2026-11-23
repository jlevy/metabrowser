- A repository folder whose origin Metabrowser does not fetch, over `http://` or
  `git://`, no longer shows part of a password or token that holds a raw `?` or `#`: the
  branch chooser and `GET /api/source/refs` showed the address up to that character.
  A userinfo holding a raw `@` is now removed whole there, in the list of remotes a
  refused `--checkout` prints, and in the
  [event log](docs/realtime-debugging.md#event-log).

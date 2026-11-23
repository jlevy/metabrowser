- A remote whose userinfo holds a raw `@`, as in `http://a@b@host/x.git`, now has its
  userinfo removed whole, not only up to the first `@`, in the list of remotes a refused
  `--checkout` prints and in the [event log](docs/realtime-debugging.md#event-log).

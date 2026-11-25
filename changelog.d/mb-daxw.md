- **Every age draws in its freshness ink again.** A Pulls row’s age had turned gray; it
  takes its yellow shade and weight again, as do the ages of the agents views’ session
  rows, session list, and a session’s Active time, which were gray and spelled their own
  way, “2 min ago” where every other age reads “2m ago”.
  One builder now draws every age, and no stylesheet but its freshness rule colors one
  ([Age](docs/design-system.md#age)).

- **Plugin SDK:** `metabrowser.ageLabel(epochSeconds, options)` and
  `metabrowser.ageLabelHtml(epochSeconds, options)` draw an age a view shows, its label
  in its freshness class after your own `className`, which only places it, with `tip`
  for its exact time; `metabrowser.retellAge(element, epochSeconds, options)` tells a
  drawn age again as time passes.
  `formatAge` and the builders take `{now}` to tell an age as of a given time, and
  `ageLabelHtml` takes these options too ([Plugin SDK](docs/plugins.md)).

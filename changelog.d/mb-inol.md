- A one-shot `metab --api` request now finishes every job its work starts before it
  exits, where it used to stop any that started while it was waiting: a
  `POST /api/plugin/github/pulls-refresh` whose look at the mirror found a base branch
  moved now completes the status scan that look starts, so the next
  `GET /api/plugin/github/pull-statuses` reports it instead of the scan before.
  The command still waits at most one Git deadline in all.

- The event log no longer counts a conditional read GitHub answered unchanged as a
  failure: `gh` exits 1 on an HTTP `304`, so every cache check that found nothing new
  ended its `gh` span failed and filled `/api/event-log/failures` with “gh: HTTP 304”.
  It now ends answered; a refusal GitHub answered (`4xx`, `5xx`) still ends failed.

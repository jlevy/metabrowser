"""The versioned repository cache under the Metabrowser application home.

The package owns the ``f01`` layout: its records and SoftSchema contracts, atomic record
publication, the fixed lock hierarchy, the application-home probe, reclamation of
staging, trash, and quarantine, the CLI root-argument grammar in :mod:`metabrowser.cache.urls`,
and the read-only ``/api/cache/`` projections of that state. Owner-only storage
enforcement stays in :mod:`metabrowser.home`, which every module here calls before
touching the home. Ordinary local browsing imports only the route table in
:mod:`metabrowser.cache.routes`, which loads the rest of the package inside a cache
request. The CLI classifies a root only when it is not a plain local path, so
``metab .`` never imports :mod:`metabrowser.cache.urls`. :mod:`metabrowser.cache.acquire`
can fetch a classified ``file://`` source into staging; it does not publish a store or
serve content, and the CLI still fails closed.
"""

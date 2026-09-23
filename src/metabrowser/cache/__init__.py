"""The versioned repository cache under the Metabrowser application home.

The package owns the ``f01`` layout: its records and SoftSchema contracts, atomic record
publication, the fixed lock hierarchy, the application-home probe, the startup sweep of
staging, the CLI root-argument grammar in :mod:`metabrowser.cache.urls`,
and the read-only ``/api/cache/`` projections of that state. Owner-only storage
enforcement stays in :mod:`metabrowser.home`, which every module here calls before
touching the home. Ordinary local browsing imports only the route table in
:mod:`metabrowser.cache.routes`, which loads the rest of the package inside a cache
request. The CLI classifies a root only when it is not a plain local path, so
``metab .`` never imports :mod:`metabrowser.cache.urls`. :mod:`metabrowser.cache.acquire`
can fetch a classified ``file://`` source into a published store and source alias; it
does not serve content. :mod:`metabrowser.cache.repository_store` opens a pinned commit
OID in a published store without writing to it or holding a lock. The CLI acquires that
source with ``--no-serve`` or as a side effect of ``--api /api/cache/…``, and still
refuses to serve acquired content.
"""

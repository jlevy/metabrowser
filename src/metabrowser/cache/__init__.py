"""The versioned repository cache under the Metabrowser application home.

The package owns the ``f01`` layout: its records and SoftSchema contracts, atomic record
publication, the fixed lock hierarchy, the application-home probe, and reclamation of
staging, trash, and quarantine. Owner-only storage enforcement stays in
:mod:`metabrowser.home`, which every module here calls before touching the home.
Nothing in ordinary local browsing imports this package.
"""

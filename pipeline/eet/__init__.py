"""European Economy Tracker data pipeline (standard library only).

Entry points, run from ``pipeline/``:

    python3 -m eet.build            # fetch, store, build site/data
    python3 -m eet.build --offline  # rebuild site/data from store/ only
    python3 -m eet.check            # validate site/data against CONTRACT.md

See ``eet/registry/README.md`` for how to add series and charts.
"""

__version__ = "1.0"

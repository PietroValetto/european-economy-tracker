"""Repository paths used by the pipeline. Everything is relative to the repo root."""
import os

PIPELINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(PIPELINE)
CACHE = os.path.join(PIPELINE, ".cache")
STORE = os.path.join(ROOT, "store")
SITE_DATA = os.path.join(ROOT, "site", "data")
CHARTS = os.path.join(SITE_DATA, "charts")

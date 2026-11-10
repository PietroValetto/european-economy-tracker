"""Repository paths used by the pipeline. Everything is relative to the repo root."""
import os
import threading

PIPELINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(PIPELINE)
CACHE = os.path.join(PIPELINE, ".cache")
STORE = os.path.join(ROOT, "store")
SITE_DATA = os.path.join(ROOT, "site", "data")
CHARTS = os.path.join(SITE_DATA, "charts")
LOCK = os.path.join(CACHE, "build.lock")  # serialises writes to store/_meta.json and site/data/*.json


def atomic_write(path, text):
    """Write ``text`` to ``path`` through a temp file in the same folder, then rename (atomic on
    POSIX). The temp name carries the process id, so two writers never share one temp file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, path)


class build_lock:
    """Exclusive lock (``with build_lock(): ...``) for the read-merge-write of shared files, so
    concurrent ``--only`` builds never drop each other's entries. Re-entrant within a thread."""
    _local = threading.local()

    def __init__(self, path=None):
        self.path = path or LOCK
        self.fh = None

    def __enter__(self):
        depth = getattr(build_lock._local, "depth", 0)
        if depth == 0:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self.fh = open(self.path, "a+")
            try:
                import fcntl
                fcntl.flock(self.fh, fcntl.LOCK_EX)
            except ImportError:  # no fcntl (Windows): run unlocked
                pass
        build_lock._local.depth = depth + 1
        return self

    def __exit__(self, *exc):
        build_lock._local.depth -= 1
        if self.fh is not None:
            try:
                import fcntl
                fcntl.flock(self.fh, fcntl.LOCK_UN)
            except ImportError:
                pass
            self.fh.close()
            self.fh = None
        return False

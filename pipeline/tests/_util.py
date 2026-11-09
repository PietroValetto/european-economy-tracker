"""Shared helpers for tests (no network)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(HERE)
if PIPELINE not in sys.path:
    sys.path.insert(0, PIPELINE)
FIXTURES = os.path.join(HERE, "fixtures")


def fixture(name, mode="rb"):
    with open(os.path.join(FIXTURES, name), mode) as fh:
        return fh.read()

import os
import tempfile
import unittest

import _util  # noqa: F401

from eet import store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_only_on_change(self):
        obs = [("2026-08", 3.2, ""), ("2026-09", 3.8, ""), ("2026-10", 4.0, "e")]
        s = store.update("x", obs, today="2026-11-04", root=self.root)
        self.assertEqual(s, {"new": 3, "revised": 0, "total": 3})
        mtime = os.path.getmtime(store.path_for("x", self.root))
        s = store.update("x", obs, today="2026-11-05", prev_fetch="2026-11-04", root=self.root)
        self.assertEqual(s["new"] + s["revised"], 0)
        self.assertEqual(len(store.read_rows("x", self.root)), 3)
        self.assertEqual(os.path.getmtime(store.path_for("x", self.root)), mtime)

    def test_revision_keeps_old_vintage(self):
        store.update("x", [("2026-10", 4.0, "e")], today="2026-11-04", root=self.root)
        s = store.update("x", [("2026-10", 4.1, ""), ("2026-11", 3.9, "e")], today="2026-11-18",
                         prev_fetch="2026-11-17", root=self.root)
        self.assertEqual((s["new"], s["revised"]), (1, 1))
        rows = store.read_rows("x", self.root)
        self.assertEqual(len(rows), 3)
        old = [r for r in rows if r["period"] == "2026-10" and r["value"] == "4"][0]
        self.assertEqual((old["flag"], old["first_seen"], old["last_seen"]), ("e", "2026-11-04", "2026-11-17"))
        self.assertEqual(store.load("x", self.root), [("2026-10", 4.1, ""), ("2026-11", 3.9, "e")])

    def test_flag_change_alone_is_a_revision(self):
        store.update("x", [("2026-10", 4.0, "e")], today="2026-11-04", root=self.root)
        s = store.update("x", [("2026-10", 4.0, "")], today="2026-11-18", root=self.root)
        self.assertEqual(s["revised"], 1)

    def test_float_noise_is_not_a_revision(self):
        store.update("x", [("2026-10", 0.1 + 0.2, "")], today="2026-11-04", root=self.root)
        s = store.update("x", [("2026-10", 0.3, "")], today="2026-11-05", root=self.root)
        self.assertEqual(s["revised"], 0)

    def test_header_and_missing(self):
        self.assertEqual(store.load("nothing", self.root), [])
        store.update("x", [("2026", 1.0, "")], today="2026-11-04", root=self.root)
        with open(store.path_for("x", self.root)) as fh:
            self.assertEqual(fh.readline().strip(), "period,value,flag,first_seen,last_seen")

    def test_children_and_meta(self):
        store.update("p__DE", [("2026", 1.0, "")], today="2026-11-04", root=self.root)
        store.update("p__FR", [("2026", 1.0, "")], today="2026-11-04", root=self.root)
        self.assertEqual(store.children("p", self.root), ["p__DE", "p__FR"])
        store.save_meta({"p__DE": {"updated": "x"}}, root=self.root)
        self.assertEqual(store.load_meta(self.root)["p__DE"]["updated"], "x")


if __name__ == "__main__":
    unittest.main()

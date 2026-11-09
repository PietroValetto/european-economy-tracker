import unittest

import _util  # noqa: F401

from eet import periods as P
from eet import transforms as T


def monthly(values, start="2024-01"):
    out, p = [], start
    for v in values:
        out.append((p, v, ""))
        p = P.shift(p, 1)
    return out


class PeriodTests(unittest.TestCase):
    def test_shift(self):
        self.assertEqual(P.shift("2026-01", -1), "2025-12")
        self.assertEqual(P.shift("2026-Q1", -1), "2025-Q4")
        self.assertEqual(P.shift("2026", 2), "2028")
        self.assertEqual(P.shift("2026-03-01", -1), "2026-02-28")

    def test_freq_and_dates(self):
        self.assertEqual(P.freq_of("2026-Q3"), "Q")
        self.assertEqual(P.end_date("2026-Q3").isoformat(), "2026-09-30")
        self.assertEqual(P.to_freq("2026-11-06", "Q"), "2026-Q4")
        self.assertEqual(P.normalize("2026-W44"), "2026-10-30")


class TransformTests(unittest.TestCase):
    def test_level_is_copy(self):
        obs = monthly([1, 2])
        out = T.level(obs)
        self.assertEqual(out, obs)
        self.assertIsNot(out, obs)

    def test_yoy_monthly(self):
        obs = monthly([100] * 12 + [104])
        out = T.yoy(obs)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "2025-01")
        self.assertAlmostEqual(out[0][1], 4.0)

    def test_yoy_uses_calendar_not_position(self):
        obs = [("2024-01", 100.0, ""), ("2024-03", 100.0, ""), ("2025-01", 102.0, ""), ("2025-03", 103.0, "")]
        out = dict((p, v) for p, v, _ in T.yoy(obs))
        self.assertAlmostEqual(out["2025-01"], 2.0)
        self.assertAlmostEqual(out["2025-03"], 3.0)

    def test_yoy_quarterly_and_daily(self):
        q = [("2025-Q1", 100.0, ""), ("2025-Q2", 101.0, ""), ("2025-Q3", 102.0, ""), ("2025-Q4", 103.0, ""),
             ("2026-Q1", 110.0, "p")]
        self.assertEqual(T.yoy(q), [("2026-Q1", 10.000000000000009, "p")])
        d = [("2025-01-01", 1.0, ""), ("2025-06-01", 1.5, ""), ("2026-01-02", 1.2, "")]
        out = T.yoy(d)
        self.assertAlmostEqual(out[-1][1], 20.0)

    def test_mom_and_flags(self):
        obs = [("2026-01", 100.0, ""), ("2026-02", 101.0, "e")]
        self.assertEqual(T.mom(obs), [("2026-02", 1.0000000000000009, "e")])

    def test_annualised(self):
        obs = monthly([100, 100, 100, 101])
        out = T.ann3m(obs)
        self.assertAlmostEqual(out[-1][1], (1.01 ** 4 - 1) * 100)
        out6 = T.ann6m(monthly([100] * 6 + [102]))
        self.assertAlmostEqual(out6[-1][1], (1.02 ** 2 - 1) * 100)
        q = [("2025-Q4", 100.0, ""), ("2026-Q1", 100.5, "")]
        self.assertAlmostEqual(T.ann1q(q)[-1][1], (1.005 ** 4 - 1) * 100)

    def test_diff_and_change_12m(self):
        obs = monthly([2.0] * 12 + [2.5])
        self.assertEqual(T.change_12m(obs), [("2025-01", 0.5, "")])
        self.assertEqual(T.diff(monthly([1.0, 3.0])), [("2024-02", 2.0, "")])

    def test_rolling_mean(self):
        out = T.rolling_mean(monthly([1, 2, 3, 4]), 3)
        self.assertEqual(out, [("2024-03", 2.0, ""), ("2024-04", 3.0, "")])
        gap = T.rolling_mean(monthly([1, None, 3, 4, 5]), 2)
        self.assertEqual([v for _, v, _ in gap], [3.5, 4.5])  # leading gaps dropped

    def test_rebase(self):
        obs = monthly([50, 100, 150])
        self.assertEqual(T.rebase(obs, "2024-02")[2][1], 150.0)
        self.assertEqual(T.rebase(obs, "2024")[1][1], 100.0)
        with self.assertRaises(ValueError):
            T.rebase(obs, "2030-01")

    def test_spread(self):
        a = monthly([3.0, 3.5, 4.0])
        b = [("2024-02", 2.5, ""), ("2024-03", 2.0, "")]
        self.assertEqual(T.spread(a, b), [("2024-02", 1.0, ""), ("2024-03", 2.0, "")])

    def test_zscore(self):
        obs = monthly([1, 2, 3, 10])
        out = T.zscore(obs, "2024-01", "2024-03")
        self.assertAlmostEqual(out[1][1], 0.0)
        self.assertAlmostEqual(out[3][1], 8.0)

    def test_trim(self):
        self.assertEqual([p for p, _, _ in T.trim(monthly([1, 2, 3]), "2024-02")], ["2024-02", "2024-03"])

    def test_step(self):
        ev = [("2026-06-17", 2.25, ""), ("2026-09-16", 2.5, "")]
        out = T.step(ev, end="2026-11-09")
        self.assertEqual(out, [("2026-06-17", 2.25, ""), ("2026-09-15", 2.25, ""), ("2026-09-16", 2.5, ""),
                               ("2026-11-09", 2.5, "")])

    def test_resample_ffill_event(self):
        ev = [("2026-06-17", 2.25, ""), ("2026-09-16", 2.5, "")]
        out = T.resample(ev, "Q", "last", ffill=True, end="2027-01-10")
        self.assertEqual(out, [("2026-Q2", 2.25, ""), ("2026-Q3", 2.5, ""), ("2026-Q4", 2.5, ""), ("2027-Q1", 2.5, "")])
        self.assertEqual(T.resample(monthly([1, 3, 5]), "Q", "mean"), [("2024-Q1", 3.0, "")])

    def test_apply_strings(self):
        obs = monthly([100] * 12 + [103])
        self.assertEqual(T.apply(obs, "yoy|scale:2")[-1][1], 6.0000000000000053)
        self.assertEqual(T.apply(obs, None), obs)
        with self.assertRaises(ValueError):
            T.apply(obs, "nonsense")
        with self.assertRaises(ValueError):
            T.validate_spec("yoy|bogus:1")

    def test_pure(self):
        obs = monthly([1, 2, 3])
        before = list(obs)
        for f in (T.yoy, T.mom, T.ann3m, T.change_12m, lambda o: T.rolling_mean(o, 2)):
            f(obs)
        self.assertEqual(obs, before)


if __name__ == "__main__":
    unittest.main()

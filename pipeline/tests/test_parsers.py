import gzip
import json
import unittest

from _util import fixture

from eet import http, periods
from eet.parsers import csvdata, jsonstat


class JsonStatTests(unittest.TestCase):
    def test_single_series_sparse(self):
        obs, updated = jsonstat.parse(fixture("eurostat_hicp_headline.json"))
        self.assertEqual(updated, "2026-11-04T11:00:00+0100")
        self.assertEqual(obs[-1], ("2026-10", 4.0, "e"))
        self.assertEqual([o[0] for o in obs], sorted(o[0] for o in obs))
        self.assertTrue(all(isinstance(o[1], float) for o in obs))

    def test_split_dimension(self):
        groups, _ = jsonstat.parse_multi(fixture("eurostat_hicp_release.json"), split="release")
        self.assertEqual(set(groups), {"FLS", "FIN"})
        self.assertEqual(groups["FLS"][-1], ("2026-10", 4.0, "e"))
        self.assertNotIn("2026-10", [p for p, _, _ in groups["FIN"]])

    def test_non_unique_selection_raises(self):
        with self.assertRaises(jsonstat.JsonStatError):
            jsonstat.parse(fixture("eurostat_hicp_release.json"))

    def test_empty_dimension_raises(self):
        d = json.loads(fixture("eurostat_hicp_headline.json"))
        d["size"][d["id"].index("geo")] = 0
        d["dimension"]["geo"]["category"]["index"] = {}
        d["value"] = {}
        with self.assertRaises(jsonstat.JsonStatError):
            jsonstat.parse(json.dumps(d))

    def test_dense_arrays(self):
        d = json.loads(fixture("eurostat_hicp_headline.json"))
        n = d["size"][-1]
        d["value"] = [d["value"].get(str(i)) for i in range(n)]
        d["status"] = [d["status"].get(str(i)) for i in range(n)]
        obs, _ = jsonstat.parse(json.dumps(d))
        self.assertEqual(obs[-1], ("2026-10", 4.0, "e"))

    def test_publisher_error(self):
        with self.assertRaises(jsonstat.JsonStatError):
            jsonstat.parse(b'{"error":[{"status":400,"label":"INVALID_QUERY_DIMENSION"}]}')


class CsvTests(unittest.TestCase):
    def test_ecb_csvdata(self):
        obs = csvdata.parse(fixture("ecb_supercore.csv"))
        self.assertEqual(obs[-1], ("2026-09", 2.5, ""))
        self.assertEqual(len(obs), 5)

    def test_panel_by_key_position(self):
        groups = csvdata.parse_multi(fixture("ecb_spf_panel.csv"), csvdata.ecb_key_part(4))
        self.assertEqual(set(groups), {"P3M", "P6M"})
        self.assertEqual(groups["P3M"][-1][0], "2026-Q4")

    def test_multi_key_without_split_raises(self):
        with self.assertRaises(ValueError):
            csvdata.parse(fixture("ecb_spf_panel.csv"))

    def test_weekly_periods_become_fridays(self):
        obs = csvdata.parse(fixture("ecb_ilm_weekly.csv"))
        self.assertEqual(obs[-1][0], "2026-10-30")
        self.assertEqual(periods.freq_of(obs[-1][0]), "D")

    def test_indeed_filter_and_missing(self):
        obs = csvdata.parse(fixture("indeed_ea.csv"), period_col="date", value_col="indeed_job_postings_index_SA",
                            flag_col="", where={"variable": "total postings"})
        self.assertEqual(obs, [("2026-10-28", 104.1, ""), ("2026-10-29", 104.3, ""), ("2026-10-30", 104.38, "")])

    def test_empty_values_skipped(self):
        body = b"KEY,TIME_PERIOD,OBS_VALUE\nX.D.ES,2026-11-06,0.01\nX.D.ES,2026-11-09,\n"
        self.assertEqual(csvdata.parse(body), [("2026-11-06", 0.01, "")])

    def test_gzip_sniffing(self):
        raw = fixture("ecb_supercore.csv")
        self.assertEqual(http.ungzip(gzip.compress(raw)), raw)
        self.assertEqual(http.ungzip(raw), raw)


if __name__ == "__main__":
    unittest.main()

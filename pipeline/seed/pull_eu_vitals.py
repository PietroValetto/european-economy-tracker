#!/usr/bin/env python3
"""EU EconVitals: pull headline euro area series and print a tidy snapshot.

Stdlib only. Single source of truth for series codes: the SERIES list below.

Usage:
    python3 -I pull_eu_vitals.py <out_dir> [--today YYYY-MM-DD]

Writes <out_dir>/eu_vitals_snapshot.csv and caches every raw response in
<out_dir>/raw/<series_id>.<ext> so a failed run can be inspected.

Sources:
  eurostat  JSON-stat 2.0, https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/<ds>?<filters>
  ecb       SDMX 2.1 REST csvdata, https://data-api.ecb.europa.eu/service/data/<flow>/<key>
  indeed    GitHub CSV, hiring-lab/job_postings_tracker

Notes verified on 2026-11-09:
  * Euro area code is EA21 since Bulgaria joined (EA20 is still published as a fixed composition, and some
    datasets also carry "EA" = evolving composition).
  * prc_hicp_manr / prc_hicp_midx / prc_hicp_fp ended in 2025-12 (ECOICOP v1). Use prc_hicp_minr / prc_hicp_fpd.
  * jvs_q_nace2 ended in 2025-Q4 (NACE Rev. 2). Use jvs_q_r21 (NACE Rev. 2.1, dimension nace_r2_1).
  * ECB ICP flow ends 2025-12. Use the ECB HICP flow (provider 4D0 for Eurostat-sourced, 4F0 for ECB-computed).
  * ECB API sometimes returns 504 after ~30 s for valid keys: retried with backoff below.
  * Invalid Eurostat filter codes do NOT error: they silently return an empty dimension. We treat
    "no observations" as an error.
"""
import csv, datetime, gzip, io, json, os, sys, time, urllib.error, urllib.parse, urllib.request

EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
ECB = "https://data-api.ecb.europa.eu/service/data/"
INDEED = "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/"
# A descriptive custom UA was rejected by the IMF CDN; keep the UA plain and honest.
UA = "eu-econvitals/0.1 (python-urllib)"

# ---------------------------------------------------------------------------------------------
# THE CODE DICTIONARY. One entry per headline series.
#   kind: eurostat -> (dataset, filters dict); ecb -> (flow, key); indeed -> (country, variable)
#   calc: optional post-processing ("spread" uses two ECB keys)
# ---------------------------------------------------------------------------------------------
SERIES = [
    dict(id="gdp_qoq", name="Real GDP, q/q %", kind="eurostat", ds="namq_10_gdp",
         f=dict(geo="EA21", unit="CLV_PCH_PRE", s_adj="SCA", na_item="B1GQ")),
    dict(id="gdp_yoy", name="Real GDP, y/y %", kind="eurostat", ds="namq_10_gdp",
         f=dict(geo="EA21", unit="CLV_PCH_SM", s_adj="SCA", na_item="B1GQ")),
    dict(id="emp_qoq", name="Employment (persons), q/q %", kind="eurostat", ds="namq_10_pe",
         f=dict(geo="EA21", unit="PCH_PRE_PER", s_adj="SCA", na_item="EMP_DC")),
    dict(id="unemp", name="Unemployment rate, % (SA)", kind="eurostat", ds="une_rt_m",
         f=dict(geo="EA21", s_adj="SA", sex="T", age="TOTAL", unit="PC_ACT")),
    dict(id="jvr", name="Job vacancy rate, % (B-T, SA)", kind="eurostat", ds="jvs_q_r21",
         f=dict(geo="EA21", nace_r2_1="B-T", sizeclas="TOTAL", s_adj="SA", indic_em="JVR")),
    dict(id="hicp", name="HICP headline, y/y %", kind="eurostat", ds="prc_hicp_minr",
         f=dict(geo="EA21", unit="RCH_A", coicop18="TOTAL")),
    dict(id="hicp_core", name="HICP ex energy, food, alc, tob, y/y %", kind="eurostat", ds="prc_hicp_minr",
         f=dict(geo="EA21", unit="RCH_A", coicop18="TOT_X_NRG_FOOD")),
    dict(id="hicp_serv", name="HICP services, y/y %", kind="eurostat", ds="prc_hicp_minr",
         f=dict(geo="EA21", unit="RCH_A", coicop18="SERV")),
    dict(id="hicp_supercore", name="HICP supercore (ECB), y/y %", kind="ecb", flow="HICP",
         key="M.U2.N.SPRXEF.4F0.ANR"),
    dict(id="negwages", name="Negotiated wages (ECB), y/y %", kind="ecb", flow="INW",
         key="Q.U2.N.INWR.000000.4F0.GY.IX"),
    dict(id="wagetracker", name="ECB wage tracker (incl. one-offs), y/y %", kind="ecb", flow="EWT",
         key="Q.U2.N.WT.INWR._T.4F0.GY", lag="forward"),
    dict(id="lci", name="Labour cost index, y/y % (B-S, SCA)", kind="eurostat", ds="lc_lci_r2_q",
         f=dict(geo="EA21", s_adj="SCA", unit="PCH_SM", nace_r2="B-S", lcstruct="D1_D4_MD5")),
    dict(id="dfr", name="ECB deposit facility rate, %", kind="ecb", flow="FM",
         key="B.U2.EUR.4F.KR.DFR.LEV", lag="in_force"),
    dict(id="estr", name="EUR short-term rate (EUR STR), %", kind="ecb", flow="EST",
         key="B.EU000A2X2A25.WT"),
    dict(id="y10_aaa", name="10y yield, AAA euro area curve, %", kind="ecb", flow="YC",
         key="B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y"),
    dict(id="y10_all", name="10y yield, all euro area govts curve, %", kind="ecb", flow="YC",
         key="B.U2.EUR.4F.G_N_C.SV_C_YM.SR_10Y"),
    dict(id="slope_10y2y", name="AAA curve 10y minus 2y, pp", kind="ecb_spread", flow="YC",
         key="B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", key2="B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y"),
    dict(id="eurusd", name="EUR/USD reference rate", kind="ecb", flow="EXR", key="D.USD.EUR.SP00.A"),
    dict(id="neer", name="Euro nominal effective rate (EER-41)", kind="ecb", flow="EXR", key="M.E03.EUR.EN00.A"),
    dict(id="ciss", name="CISS systemic stress index, EA", kind="ecb", flow="CISS", key="D.U2.Z0Z.4F.EC.SS_CIN.IDX"),
    dict(id="m3", name="M3, annual growth %", kind="ecb", flow="BSI", key="M.U2.Y.V.M30.X.I.U2.2300.Z01.A"),
    dict(id="mortgage", name="Bank rate, new house purchase loans, %", kind="ecb", flow="MIR",
         key="M.U2.B.A2C.AM.R.A.2250.EUR.N"),
    dict(id="gov_debt", name="Government debt, % GDP", kind="eurostat", ds="gov_10q_ggdebt",
         f=dict(geo="EA21", sector="S13", na_item="GD", unit="PC_GDP")),
    dict(id="gov_bal", name="Government balance, % GDP (SCA)", kind="eurostat", ds="gov_10q_ggnfa",
         f=dict(geo="EA21", sector="S13", na_item="B9", unit="PC_GDP", s_adj="SCA")),
    dict(id="ca", name="Current account, EUR mn (NSA, monthly)", kind="eurostat", ds="ei_bpm6ca_m",
         f=dict(geo="EA21", bop_item="CA", stk_flow="BAL", partner="EXT_EA21")),
    dict(id="esi", name="Economic sentiment indicator", kind="eurostat", ds="ei_bssi_m_r2",
         f=dict(geo="EA21", s_adj="SA", indic="BS-ESI-I")),
    dict(id="cons_conf", name="Consumer confidence, balance", kind="eurostat", ds="ei_bssi_m_r2",
         f=dict(geo="EA21", s_adj="SA", indic="BS-CSMCI-BAL")),
    dict(id="indprod", name="Industrial production, m/m % (B-D, SCA)", kind="eurostat", ds="sts_inpr_m",
         f=dict(geo="EA21", indic_bt="PRD", nace_r2="B-D", s_adj="SCA", unit="PCH_PRE")),
    dict(id="retail", name="Retail trade volume, m/m % (SCA)", kind="eurostat", ds="sts_trtu_m",
         f=dict(geo="EA21", indic_bt="VOL_SLS", nace_r2="G47", s_adj="SCA", unit="PCH_PRE")),
    dict(id="indeed", name="Indeed job postings index, EA (SA, Feb-2020=100)", kind="indeed",
         country="EA", variable="total postings"),
]


def http_get(url, timeout=60, tries=3):
    """GET with gzip handling and retry on 5xx / timeouts. Returns (status, bytes, headers, secs)."""
    last = None
    global ATTEMPTS
    for attempt in range(tries):
        ATTEMPTS += 1
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body, hdr, status = r.read(), dict(r.headers), r.status
        except urllib.error.HTTPError as e:
            body, hdr, status = e.read() or b"", dict(e.headers), e.code
        except Exception as e:  # timeout, DNS, reset
            last = (None, repr(e).encode(), {}, round(time.time() - t0, 2))
            time.sleep(2 * (attempt + 1)); continue
        if body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
        res = (status, body, hdr, round(time.time() - t0, 2))
        if status in (500, 502, 503, 504):
            last = res; time.sleep(3 * (attempt + 1)); continue
        return res
    return last


ATTEMPTS = 0


def eurostat_url(ds, f, n=4):
    q = list(f.items()) + [("lastTimePeriod", n), ("format", "JSON"), ("lang", "EN")]
    return EUROSTAT + ds + "?" + urllib.parse.urlencode(q)


def parse_jsonstat_single(body):
    """Return (obs list [(period, value, flag)], updated). Expects all non-time dims of size 1."""
    d = json.loads(body)
    if "error" in d:
        raise RuntimeError(d["error"])
    if any(s != 1 for i, s in zip(d["id"], d["size"]) if i != "time"):
        raise RuntimeError(f"filters not unique or invalid: sizes {dict(zip(d['id'], d['size']))}")
    idx = d["dimension"]["time"]["category"]["index"]
    periods = sorted(idx, key=lambda k: idx[k]) if isinstance(idx, dict) else idx
    val, st = d.get("value", {}), d.get("status", {})
    if isinstance(val, list): val = {str(i): v for i, v in enumerate(val)}
    if isinstance(st, list): st = {str(i): v for i, v in enumerate(st)}
    obs = [(p, val[str(i)], st.get(str(i), "")) for i, p in enumerate(periods) if val.get(str(i)) is not None]
    return obs, d.get("updated", "")


def ecb_url(flow, key, n=4):
    return ECB + f"{flow}/{key}?" + urllib.parse.urlencode(
        {"lastNObservations": n, "format": "csvdata", "detail": "dataonly"})


def parse_ecb_csv(body):
    rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
    obs = [(r["TIME_PERIOD"], float(r["OBS_VALUE"]), r.get("OBS_STATUS", "")) for r in rows if r.get("OBS_VALUE")]
    return sorted(obs)


def period_end(p):
    """Last calendar day covered by a period string: 2026, 2026-Q3, 2026-09, 2026-11-06."""
    if len(p) == 4:
        return datetime.date(int(p), 12, 31)
    if "-Q" in p:
        y, q = int(p[:4]), int(p[-1])
        m = q * 3
        nxt = datetime.date(y + (m == 12), (m % 12) + 1, 1)
        return nxt - datetime.timedelta(days=1)
    if len(p) == 7:
        y, m = int(p[:4]), int(p[5:7])
        nxt = datetime.date(y + (m == 12), (m % 12) + 1, 1)
        return nxt - datetime.timedelta(days=1)
    return datetime.date.fromisoformat(p[:10])


def lag_text(days):
    if days < 45:
        return f"{days} d"
    return f"{days} d (~{days / 30.44:.1f} mo)"


def fetch(s, raw_dir):
    """Return dict with obs, url, status, secs, updated."""
    if s["kind"] == "eurostat":
        url = eurostat_url(s["ds"], s["f"])
        st, body, hdr, secs = http_get(url)
        open(os.path.join(raw_dir, s["id"] + ".json"), "wb").write(body)
        if st != 200:
            raise RuntimeError(f"HTTP {st}: {body[:200]!r}")
        obs, upd = parse_jsonstat_single(body)
        return dict(obs=obs, url=url, status=st, secs=secs, updated=upd, code=f"{s['ds']} {s['f']}")
    if s["kind"] in ("ecb", "ecb_spread"):
        keys = [s["key"]] + ([s["key2"]] if s["kind"] == "ecb_spread" else [])
        series, meta = [], {}
        for k in keys:
            url = ecb_url(s["flow"], k)
            st, body, hdr, secs = http_get(url)
            open(os.path.join(raw_dir, s["id"] + ("_2" if series else "") + ".csv"), "wb").write(body)
            if st != 200:
                raise RuntimeError(f"HTTP {st} for {k}")
            series.append(parse_ecb_csv(body))
            meta = dict(url=url, status=st, secs=secs, updated=hdr.get("Last-Modified", hdr.get("last-modified", "")))
        obs = series[0]
        if s["kind"] == "ecb_spread":
            b = {p: v for p, v, _ in series[1]}
            obs = [(p, round(v - b[p], 4), "") for p, v, _ in obs if p in b]
        return dict(obs=obs, code=f"{s['flow']}.{' minus '.join(keys)}", **meta)
    if s["kind"] == "indeed":
        url = INDEED + f"{s['country']}/aggregate_job_postings_{s['country']}.csv"
        st, body, hdr, secs = http_get(url)
        open(os.path.join(raw_dir, s["id"] + ".csv"), "wb").write(body)
        if st != 200:
            raise RuntimeError(f"HTTP {st}")
        rows = [r for r in csv.DictReader(io.StringIO(body.decode("utf-8-sig"))) if r["variable"] == s["variable"]]
        obs = sorted((r["date"], float(r["indeed_job_postings_index_SA"]), "") for r in rows)
        # weekly-ish cadence: compare with value 7 days earlier rather than the previous day
        return dict(obs=obs[-8::7] if len(obs) >= 8 else obs, url=url, status=st, secs=secs,
                    updated=hdr.get("Last-Modified", ""), code=f"{s['country']} / {s['variable']} / SA")
    raise ValueError(s["kind"])


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    today = datetime.date.today()
    if "--today" in sys.argv:
        today = datetime.date.fromisoformat(sys.argv[sys.argv.index("--today") + 1])
    raw_dir = os.path.join(out_dir, "raw"); os.makedirs(raw_dir, exist_ok=True)
    rows = []
    for s in SERIES:
        global ATTEMPTS
        ATTEMPTS, t0 = 0, time.time()
        try:
            r = fetch(s, raw_dir)
            if not r["obs"]:
                raise RuntimeError("no observations returned (check filter codes)")
            (p1, v1, f1) = r["obs"][-1]
            prev = r["obs"][-2] if len(r["obs"]) > 1 else ("", "", "")
            lag = (today - period_end(p1)).days
            lagt = lag_text(lag)
            if s.get("lag") == "in_force":
                lagt = "in force (last change)"
            elif s.get("lag") == "forward" or lag < 0:
                lagt = "forward-looking"
            rows.append(dict(series=s["name"], id=s["id"], source=s["kind"].replace("_spread", ""), code=r["code"],
                             latest_period=p1, latest_value=v1, flag=f1, previous_period=prev[0],
                             previous_value=prev[1], lag_days=lag, lag=lagt,
                             source_updated=r.get("updated", ""), http=r["status"], secs=round(time.time() - t0, 2), attempts=ATTEMPTS, error=""))
        except Exception as e:
            rows.append(dict(series=s["name"], id=s["id"], source=s["kind"], code="", latest_period="",
                             latest_value="", flag="", previous_period="", previous_value="", lag_days="",
                             lag="", source_updated="", http="", secs=round(time.time() - t0, 2), attempts=ATTEMPTS,
                             error=str(e)[:200]))
        if s["kind"] == "eurostat":
            time.sleep(0.5)  # be polite to Eurostat
    path = os.path.join(out_dir, "eu_vitals_snapshot.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    hdr = f"{'series':46} {'source':8} {'latest':11} {'value':>10} {'prev':>10} {'lag':>24}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        if r["error"]:
            print(f"{r['series'][:46]:46} {r['source']:8} ERROR {r['error'][:80]}"); continue
        fmt = lambda v: (f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v))
        print(f"{r['series'][:46]:46} {r['source']:8} {r['latest_period']:11} {fmt(r['latest_value']) + r['flag']:>10} "
              f"{fmt(r['previous_value']):>10} {r['lag']:>24}")
    print(f"\nwrote {path}  ({sum(1 for r in rows if not r['error'])}/{len(rows)} ok, as of {today})")


if __name__ == "__main__":
    main()

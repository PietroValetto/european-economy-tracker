# European Economy Tracker

**By [Popular Economics](https://populareconomics.substack.com/).** A running read on the euro area and
EU economy: growth, jobs, wages, inflation, financial conditions, the ECB, public finances and the
indicators that only Europe has, in one set of charts rebuilt automatically as the numbers come out.

Live site: https://pietrovaletto.github.io/european-economy-tracker/

## How it works

1. `pipeline/` (Python, standard library only) pulls every series in the registry from Eurostat,
   the ECB Data Portal, the European Commission and other public, keyless APIs.
2. It stores every vintage in `store/`, computes transforms, and writes one JSON bundle per chart to
   `site/data/`.
3. `site/` is a static website (no build step) that renders those bundles with Observable Plot in the
   Popular Economics house style.
4. GitHub Actions rebuilds the data every morning and polls on euro-indicator release mornings,
   then deploys to GitHub Pages.

See `CONTRACT.md` for the data and site contract and `ROADMAP.md` for what is planned but not built.

## Run locally

```bash
cd pipeline && python3 -m eet.build && python3 -m eet.check
cd ../site && python3 -m http.server 8000
```

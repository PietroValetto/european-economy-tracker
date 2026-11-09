"""The fixed page list (CONTRACT section 4). ``home`` has no entry in ``pages``."""

PAGES = [
    ("gdp", "GDP and growth", "Output in the euro area and the largest economies: quarterly growth, its components and the outlook."),
    ("labour", "Jobs", "Employment, unemployment, vacancies and job postings across the euro area."),
    ("wages", "Wages", "Negotiated wages, the ECB wage tracker, labour costs and productivity."),
    ("inflation", "Inflation", "Consumer prices in the euro area: headline, core, services and the ECB's underlying measures."),
    ("financial", "Financial conditions", "Bond yields and spreads, financial stress, the euro, and the cost and growth of credit."),
    ("ecb", "The ECB", "Policy rates, what forecasters and the bond curve expect, staff projections, the balance sheet and bank lending."),
    ("fiscal", "Public finances", "Government deficits and debt, country by country, and the EU fiscal rules."),
    ("international", "International", "The euro area next to the United States, the United Kingdom, Japan and other large economies."),
    ("europe", "Only in Europe", "Indicators with no US counterpart: fragmentation, energy and the European Commission's surveys."),
    ("calendar", "Release calendar", "Upcoming releases from Eurostat, the ECB and the European Commission."),
    ("methods", "Methods", "How every chart is built: sources, transforms and caveats."),
    ("about", "About", "What the European Economy Tracker is and who makes it."),
]

PAGE_IDS = [p[0] for p in PAGES]

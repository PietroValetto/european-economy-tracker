"""Country codes and names. Eurostat uses EL for Greece; the ECB uses GR and U2 for the euro area."""

NAMES = {
    "EA21": "Euro area", "EA": "Euro area", "EA20": "Euro area (20)", "U2": "Euro area",
    "EU27_2020": "EU27", "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CY": "Cyprus",
    "CZ": "Czechia", "DE": "Germany", "DK": "Denmark", "EE": "Estonia", "EL": "Greece", "GR": "Greece",
    "ES": "Spain", "FI": "Finland", "FR": "France", "HR": "Croatia", "HU": "Hungary", "IE": "Ireland",
    "IT": "Italy", "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MT": "Malta",
    "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SE": "Sweden",
    "SI": "Slovenia", "SK": "Slovakia", "UK": "United Kingdom", "US": "United States",
}

# Euro area members in 2026 (Bulgaria joined on 1 January 2026), Eurostat codes.
EURO_AREA = ["AT", "BE", "BG", "CY", "DE", "EE", "EL", "ES", "FI", "FR", "HR", "IE", "IT", "LT", "LU",
             "LV", "MT", "NL", "PT", "SI", "SK"]

# The fixed country strip used across the site (CONTRACT: index.json "countries").
STRIP = ["DE", "FR", "IT", "ES", "NL", "PL"]


def name(code):
    return NAMES.get(code, code)

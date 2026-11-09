"""Declarations used by registry section modules. Import them from ``eet.registry``.

A section module (``eet/registry/<name>.py``) defines any of these module-level lists:

    SERIES   = [Series(...), ...]    data to fetch and store
    DERIVED  = [Derived(...), ...]   series computed from others (spreads, averages, ...)
    SECTIONS = [Section(...), ...]   page sections the module's charts go into
    CHARTS   = [Chart(...), ...]     one chart bundle each
    TILES    = [Tile(...), ...]      home-page key-indicator tiles (home module only, normally)
    PAGES    = [Page(...), ...]      optional overrides of a page's title or description

See ``eet/registry/README.md`` for a worked example.
"""
from dataclasses import dataclass, field
from typing import Any, Callable

SOURCES = ("eurostat", "ecfin", "ecb", "bis", "oecd", "indeed", "csv")
FREQS = ("A", "Q", "M", "W", "D")
ROLES = ("story", "base", "context", "band")
CHART_TYPES = ("line", "bar", "bar-line", "stacked-bar", "contrib", "scatter", "heatmap", "table",
               "country-strip")
FORMATS = ("pct", "pp", "index", "eur_bn", "level")
COLUMN_FORMATS = ("pct", "pp", "index", "level", "eur_bn", "change")
MARKS = ("bar", "line")
CURVES = ("step-after",)
DIRECTIONS = ("up", "down", "none")
WINDOWS = ("1y", "5y", "10y", "max")

PUBLISHER = {"eurostat": "Eurostat", "ecfin": "European Commission (DG ECFIN)", "ecb": "European Central Bank",
             "bis": "Bank for International Settlements", "oecd": "OECD", "indeed": "Indeed Hiring Lab",
             "csv": ""}


@dataclass
class Series:
    """One series (or, with ``split``, a panel of series) fetched from a publisher.

    source    eurostat | ecfin | ecb | bis | oecd | indeed | csv
    dataset   Eurostat/ECFIN dataset code; ECB/BIS flow; OECD "AGENCY,DSD@DF,VERSION";
              Indeed country folder (EA, DE, ...); csv: the full URL
    key       ECB/BIS/OECD SDMX series key (one key per request at the ECB; "+" only inside one
              dimension)
    filters   Eurostat/ECFIN: {dimension: code}. With ``split``, the split dimension may hold a
              list of codes. csv/indeed: {column: value} row filter
    freq      A Q M W D (W and D both use YYYY-MM-DD periods)
    start     first period to request (Eurostat sinceTimePeriod, SDMX startPeriod)
    split     make a panel: Eurostat dimension name, or ECB key position (0-based) holding a
              wildcard/OR. Children are stored as ``<id>__<code>``
    keep      optional callable(code) -> bool to keep only some panel children
    labels    optional {code: label} for panel children
    scale     multiply every value (e.g. 0.001 to turn EUR millions into EUR billions)
    event     True for change-date series (policy rates): values hold until the next date
    """
    id: str
    source: str
    dataset: str = ""
    key: str = ""
    filters: dict = field(default_factory=dict)
    freq: str = "M"
    unit: str = "%"
    label: str = ""
    geo: str = "EA21"
    decimals: int = 1
    start: str | None = None
    split: str | int | None = None
    keep: Callable[[str], bool] | None = None
    labels: dict = field(default_factory=dict)
    scale: float = 1.0
    event: bool = False
    period_col: str = ""
    value_col: str = ""
    flag_col: str = ""
    source_name: str = ""
    source_url: str = ""
    notes: str = ""
    module: str = ""  # filled in by the registry loader


@dataclass
class Derived:
    """A series computed from others: ``fn(*input_obs) -> obs``.

    ``inputs`` are series ids (fetched or derived, any module). An input written ``"<panel>__*"``
    is passed as a dict ``{code: obs}`` of all children of that panel.
    """
    id: str
    inputs: list
    fn: Callable[..., list]
    freq: str = "M"
    unit: str = "%"
    label: str = ""
    geo: str = "EA21"
    decimals: int = 1
    source_name: str = ""
    source_url: str = ""
    notes: str = ""
    module: str = ""


@dataclass
class Ref:
    """A series drawn in a chart.

    key        bundle key (default: the series id); for country-strip use the geo code
    role       story (amber, at most one per chart) | base (green) | context | band
    transform  registry transform string (see eet.transforms), a callable(obs), or None
    start/end  trim after the transform
    mark       "bar" or "line" (bar-line charts: which series are bars)
    curve      "step-after" for step series; set automatically when the transform uses ``step``
    """
    series: str
    key: str = ""
    label: str = ""
    role: str = "base"
    transform: Any = None
    start: str | None = None
    end: str | None = None
    decimals: int | None = None
    mark: str | None = None
    curve: str | None = None


@dataclass
class Section:
    page: str
    id: str
    title: str
    intro: str = ""
    order: int = 100
    module: str = ""


@dataclass
class Chart:
    """One chart bundle, ``site/data/charts/<id>.json``.

    ``build`` (optional) is a callable(ctx, chart) -> dict that returns bundle fields to add or
    override: ``series`` (bundle-format dicts with raw values), ``rows``/``columns`` for tables,
    ``rows``/``columns``/``cells`` for heatmaps, and so on. Rounding is applied afterwards.
    ``what``, ``transform_text`` and ``caveats`` feed methods.json.
    """
    id: str
    page: str
    section: str
    order: int
    title: str
    subtitle: str
    kicker: str = ""
    type: str = "line"
    series: list = field(default_factory=list)
    units: str = "%"
    format: str = "pct"
    decimals: int | None = None
    frequency: str | None = None
    geo: str = "EA21"
    reference_lines: list = field(default_factory=list)
    markers: list = field(default_factory=list)
    y_domain: list | None = None
    default_window: str = "5y"
    total_key: str | None = None
    x_label: str | None = None
    y_label: str | None = None
    source: str = ""
    source_url: str = ""
    notes: str = ""
    what: str = ""
    transform_text: str = ""
    caveats: str = ""
    original: bool = False
    start: str | None = None
    build: Callable | None = None
    highlight: str | None = None
    extra: dict = field(default_factory=dict)
    module: str = ""


@dataclass
class Tile:
    """A home-page key-indicator tile (index.json ``strip``), in ``order``."""
    id: str
    label: str
    series: str
    unit: str
    chart_id: str
    page: str
    good_direction: str = "none"
    transform: Any = None
    decimals: int | None = None
    order: int = 100
    module: str = ""


@dataclass
class Page:
    """Override a page's title or description (page ids and order are fixed by the contract)."""
    id: str
    title: str | None = None
    description: str | None = None
    module: str = ""

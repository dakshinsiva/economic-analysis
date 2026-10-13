"""Curated registry of FRED series the agent should reach for first.

Why a registry instead of always searching FRED? FRED has ~800k series and
search returns many near-duplicates (SA vs NSA, levels vs rates, discontinued
series). Giving the model a small, well-described menu makes tool selection
far more reliable and makes the agent's behaviour easier to test.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeriesInfo:
    id: str
    title: str
    units: str
    frequency: str  # D, W, M, Q
    topic: str
    reading: str  # one line on how economists interpret it


REGISTRY: dict[str, SeriesInfo] = {
    s.id: s
    for s in [
        # --- Labor market / JOLTS ---
        SeriesInfo("JTSJOL", "Job Openings: Total Nonfarm (JOLTS)", "Thousands, SA", "M", "labor",
                   "Labor demand. Falling openings with low layoffs = cooling without pain."),
        SeriesInfo("JTSHIR", "Hires Rate: Total Nonfarm (JOLTS)", "Percent, SA", "M", "labor",
                   "Churn. Low hires rate means a 'low hire, low fire' frozen market."),
        SeriesInfo("JTSQUR", "Quits Rate: Total Nonfarm (JOLTS)", "Percent, SA", "M", "labor",
                   "Worker confidence. Quits fall when workers fear they cannot find a new job."),
        SeriesInfo("JTSLDL", "Layoffs and Discharges: Total Nonfarm (JOLTS)", "Thousands, SA", "M", "labor",
                   "Employer-driven separations. A rise here is the recessionary signal."),
        SeriesInfo("UNRATE", "Unemployment Rate", "Percent, SA", "M", "labor",
                   "Headline slack. Sahm rule: +0.5pp from 12-month low of 3mo avg flags recession."),
        SeriesInfo("PAYEMS", "All Employees: Total Nonfarm", "Thousands, SA", "M", "labor",
                   "Payroll jobs. Look at monthly change, not level; ~100k/mo is breakeven."),
        SeriesInfo("ICSA", "Initial Claims", "Number, SA", "W", "labor",
                   "Highest-frequency layoff gauge. Sustained >300k historically = trouble."),
        # --- Growth ---
        SeriesInfo("GDPC1", "Real Gross Domestic Product", "Billions of chained 2017 $, SAAR", "Q", "growth",
                   "Output level. Use the % change series for growth rates."),
        SeriesInfo("A191RL1Q225SBEA", "Real GDP: Percent Change from Preceding Period", "Percent, SAAR", "Q", "growth",
                   "Headline quarterly growth rate (annualized). Trend ~2%."),
        SeriesInfo("INDPRO", "Industrial Production Index", "Index 2017=100, SA", "M", "growth",
                   "Monthly goods-sector output. Early read on manufacturing cycles."),
        # --- Inflation ---
        SeriesInfo("CPIAUCSL", "CPI: All Items (Urban)", "Index 1982-84=100, SA", "M", "inflation",
                   "Headline inflation. Compute YoY % change; Fed target is ~2% on PCE."),
        SeriesInfo("CPILFESL", "CPI: All Items Less Food & Energy", "Index 1982-84=100, SA", "M", "inflation",
                   "Core CPI. Strips volatile components; what the Fed watches more closely."),
        SeriesInfo("PCEPILFE", "PCE Price Index Less Food & Energy", "Index 2017=100, SA", "M", "inflation",
                   "Core PCE. The Fed's official 2% target measure."),
        # --- Rates / yield curve ---
        SeriesInfo("DGS3MO", "3-Month Treasury Constant Maturity", "Percent", "D", "rates",
                   "Short end. Tracks expected Fed policy over the next quarter."),
        SeriesInfo("DGS2", "2-Year Treasury Constant Maturity", "Percent", "D", "rates",
                   "Market's view of Fed policy over the next two years."),
        SeriesInfo("DGS10", "10-Year Treasury Constant Maturity", "Percent", "D", "rates",
                   "Benchmark long rate. Growth + inflation expectations + term premium."),
        SeriesInfo("DGS30", "30-Year Treasury Constant Maturity", "Percent", "D", "rates",
                   "Long end. Sensitive to fiscal and term-premium concerns."),
        SeriesInfo("T10Y2Y", "10-Year Minus 2-Year Treasury Spread", "Percent", "D", "rates",
                   "Classic inversion gauge. Negative has preceded every recession since 1970s."),
        SeriesInfo("T10Y3M", "10-Year Minus 3-Month Treasury Spread", "Percent", "D", "rates",
                   "NY Fed's preferred recession-probability input."),
        SeriesInfo("FEDFUNDS", "Effective Federal Funds Rate", "Percent", "M", "rates",
                   "Actual policy rate. Compare with DGS2 to see market vs Fed."),
        # --- Other ---
        SeriesInfo("UMCSENT", "U. of Michigan Consumer Sentiment", "Index 1966Q1=100", "M", "other",
                   "Household mood. Weak link to spending, strong link to politics/prices."),
        SeriesInfo("HOUST", "Housing Starts: Total", "Thousands of units, SAAR", "M", "other",
                   "Most rate-sensitive sector. Leads the cycle."),
        SeriesInfo("RSAFS", "Advance Retail Sales: Retail Trade and Food Services", "Millions $, SA", "M", "other",
                   "Nominal consumer spending. Deflate with CPI for real growth."),
        SeriesInfo("USREC", "NBER Recession Indicator", "1 = recession", "M", "other",
                   "Official recession dating; use for context shading."),
    ]
}

TOPICS = sorted({s.topic for s in REGISTRY.values()})


def by_topic(topic: str | None = None) -> list[SeriesInfo]:
    if not topic or topic == "all":
        return list(REGISTRY.values())
    return [s for s in REGISTRY.values() if s.topic == topic.lower()]

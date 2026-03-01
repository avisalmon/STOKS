# STOKS — Value Investing Scanner

A **Graham-Buffett value investing stock screener** that scans 900+ US equities, applies a rigorous 6-stage analysis pipeline, and generates detailed reports + a beautiful static site dashboard.

> ⚠️ **Disclaimer:** This tool is for educational and research purposes only. It does NOT constitute financial advice. Always conduct your own due diligence.

---

## What It Does

STOKS automatically:

1. **Scans** the S&P 500 + S&P 400 MidCap (900+ stocks)
2. **Filters** with strict Graham-style hard criteria (P/E, D/E, current ratio, EPS/FCF history)
3. **Scores** business quality using Buffett-style metrics (ROIC, ROE, margins, FCF)
4. **Detects cyclicality** and normalizes earnings
5. **Values** each stock using dual methods (Earnings Power Value + Conservative DCF)
6. **Flags value traps** (secular decline, debt, FCF divergence)
7. **Ranks** candidates with a weighted composite score
8. **Generates** per-ticker Markdown/JSON reports with investment thesis
9. **Builds** a static HTML dashboard with sortable tables, signal badges, and sparkline charts

### Screening Philosophy

| Principle | Implementation |
|-----------|---------------|
| **Margin of Safety** | Buy only at ≥30% discount to intrinsic value |
| **Quality First** | ROIC > 12%, ROE > 15%, stable margins |
| **Balance Sheet Safety** | D/E ≤ 1.0, Current Ratio ≥ 1.5 |
| **Earnings Consistency** | EPS positive 5/7 years, FCF positive 4/5 years |
| **Avoid Traps** | Detect declining revenue, FCF/EPS divergence, over-leverage |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Internet access (Yahoo Finance API via yfinance)

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd STOKS

# Create and activate virtual environment
python -m venv env
# Windows:
& env\Scripts\Activate.ps1
# Unix:
source env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run a Scan

```bash
# Full S&P 500 + S&P 400 scan (~25 min, 900+ tickers)
python -m src.main -v

# Analyze specific tickers
python -m src.main -t AAPL -t MSFT -t JNJ -v

# Dry run — show universe without scanning
python -m src.main --dry-run

# Custom config
python -m src.main --config my_config.yaml -v
```

### View Results

- **Dashboard:** Open `index.html` in a browser
- **Reports:** `runs/<timestamp>/reports/<TICKER>/report.md`
- **Exports:** `runs/<timestamp>/exports/candidates.csv`

---

## Architecture

```
STOKS/
├── config.yaml              # All thresholds (P/E, D/E, MOS, weights, etc.)
├── index.html               # Generated dashboard (GitHub Pages entry point)
├── site/                    # Generated static site assets
│   ├── style.css            # Dark theme CSS
│   ├── app.js               # Client-side sorting/filtering
│   ├── methodology.html     # Methodology explanation page
│   └── ticker/              # Per-ticker detail pages
│       ├── AAPL.html
│       └── ...
├── src/
│   ├── main.py              # CLI entrypoint (Click)
│   ├── config.py            # Typed config with YAML loading
│   ├── universe.py          # Universe builder (S&P 500 + 400)
│   ├── run_manager.py       # Timestamped run folders
│   ├── log_setup.py         # Loguru configuration
│   ├── pipeline/
│   │   └── orchestrator.py  # 6-stage pipeline (A→B→C→D→E→F)
│   ├── providers/
│   │   ├── base.py          # DataProvider ABC
│   │   ├── yfinance_provider.py  # Yahoo Finance implementation
│   │   ├── cache.py         # File-based cache with TTL
│   │   └── rate_limiter.py  # Token bucket rate limiter
│   ├── reports/
│   │   ├── markdown_report.py  # Rich Markdown per-ticker reports
│   │   ├── json_report.py   # Machine-readable JSON reports
│   │   └── csv_export.py    # Candidates + rejected CSV exports
│   └── site_generator/
│       ├── generator.py     # Jinja2 static site generator
│       └── templates/       # HTML templates (index, ticker, methodology)
├── runs/                    # Timestamped scan outputs (gitignored)
├── docs/
│   ├── SPEC_v1.0.md         # Full technical specification
│   └── BACKLOG.md           # Sprint progress tracker
└── requirements.txt
```

---

## Pipeline Stages

### Stage A — Hard Filters (Graham)
Strict pass/fail criteria. Every stock must meet ALL:
- P/E (TTM) ≤ 15
- EPS positive in ≥ 5 of last 7 years
- FCF positive in ≥ 4 of last 5 years
- Debt-to-Equity ≤ 1.0
- Current Ratio ≥ 1.5
- Shares outstanding CAGR ≤ 3% (no excessive dilution)

### Stage B — Quality Score (Buffett)
Weighted quality score (0–100) from:
- ROIC (25%) — return on invested capital
- ROE (20%) — return on equity
- Margin stability (15%) — gross margin standard deviation
- Operating margin trend (15%) — not declining
- Revenue trend (15%) — not a multi-year decline
- FCF margin (10%) — cash conversion quality

### Stage C — Cyclicality Detection
Classifies businesses as LOW / MED / HIGH cyclicality based on margin volatility and revenue variability. Normalizes EPS for cyclical businesses.

### Stage D — Intrinsic Value & Margin of Safety
Two independent valuation methods:
1. **Earnings Power Value (EPV):** Normalized EPS × conservative multiple (10x, or 7x for cyclicals)
2. **Conservative DCF:** FCF-based with 11% discount rate, 2% growth cap, 10-year projection

Combines into [low, base, high] intrinsic value range. Calculates margin of safety as `1 - (price / base)`.

### Stage E — Value Trap Detection
Flags stocks that look cheap but may be deteriorating:
- Revenue + margin in secular decline
- FCF diverging from reported EPS
- Debt outpacing income growth
- Low interest coverage
- One-off earnings inflating metrics

Each flag has LOW / MED / HIGH severity with evidence strings.

### Stage F — Final Scoring & Signal
Weighted composite score:
| Component | Weight |
|-----------|--------|
| Valuation (MOS) | 30% |
| Earnings Quality | 25% |
| Balance Sheet | 20% |
| Stability | 15% |
| Moat Proxies | 10% |

**Signal Assignment:**
- **STRONG BUY** — Quality ≥ 75, MOS ≥ 45%, no HIGH trap flags
- **BUY** — Quality ≥ 65, MOS ≥ 30%
- **WATCH** — Passed hard filters but doesn't fully qualify
- **REJECT** — Failed hard filters or has HIGH severity traps

---

## Reports & Output

Each candidate gets:

### Markdown Report (`report.md`)
- Investment thesis narrative explaining WHY it's a value stock
- Research links (Yahoo Finance, Finviz, SEC EDGAR, Macrotrends, Simply Wall St)
- Key metrics table with Graham thresholds
- Stage-by-stage analysis (A through F)
- Top drivers, risks, and thesis invalidation triggers
- Financial history tables (income statement + cash flow)

### JSON Report (`report.json`)
- All raw metrics + computed scores
- Complete stage results
- Machine-readable for further analysis

### CSV Exports
- `candidates.csv` — all stocks that passed screening, ranked by score
- `rejected.csv` — all rejected stocks with reasons

### Static Site Dashboard
- Filterable, sortable candidate table
- Signal badges (color-coded)
- Score bars with visual indicators
- Inline sparkline charts (revenue/EPS/FCF trends)
- Per-ticker detail pages with full analysis
- Methodology page
- No CDN dependencies — fully self-contained

---

## Configuration

All thresholds are in `config.yaml`. Key settings:

```yaml
hard_filters:
  pe_max: 15             # Graham's Intelligent Investor criterion
  debt_to_equity_max: 1.0
  current_ratio_min: 1.5

quality:
  roic_min: 0.12         # 12%
  roe_min: 0.15          # 15%

valuation:
  mos_buy: 0.30          # 30% margin of safety for BUY
  mos_strong_buy: 0.45   # 45% for STRONG BUY
  discount_rate: 0.11    # 11% DCF discount rate
```

See [docs/SPEC_v1.0.md](docs/SPEC_v1.0.md) for the full specification.

---

## CLI Options

```
Usage: python -m src.main [OPTIONS]

Options:
  --config PATH         Path to config.yaml (default: config.yaml)
  -t, --ticker TEXT     Analyze specific ticker(s). Repeat: -t AAPL -t MSFT
  --sector-mode TEXT    Override sector mode: "simple" or "full"
  -v, --verbose         Enable DEBUG console output
  --dry-run             Show universe count without scanning
  --help                Show this message and exit
```

---

## Tech Stack

- **Python 3.11+** — core language
- **yfinance** — Yahoo Finance data (price, statements, metrics)
- **pandas / numpy** — financial data processing
- **Jinja2** — HTML template engine
- **Click** — CLI framework
- **loguru** — structured logging
- **lxml** — HTML parsing (Wikipedia S&P index lists)

---

## License

This project is for educational and research purposes. Not financial advice.

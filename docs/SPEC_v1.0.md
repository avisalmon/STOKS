# Value Investing Scanner & Analysis Pipeline (Spec v1.0)
Owner: Avi  
Goal: Build a quiet, automated stock scanning + analysis system implementing a Graham-to-Buffett value framework, producing **detailed per-company analysis files** and a **static HTML site** summarizing candidates and "buy signals".

> Important (non-negotiable):
> - This system must be **deterministic**, **repeatable**, and **explainable**.
> - Output must be **evidence-based** (numbers, sources, and assumptions).
> - Any "buy recommendation" must be expressed as a **signal** (e.g., *Strong Buy Signal / Watch / Reject*) with clear justification and risk flags. No hype language.
> - The system is for research/education; include a prominent disclaimer in outputs.

---

## 1) High-Level Overview

### 1.1 Purpose
Scan a defined universe of stocks, filter by hard value constraints (Graham-style), apply quality and durability checks (Buffett-style), compute intrinsic value ranges with conservative assumptions, detect value traps, rank candidates, and generate:
1) **Per-ticker detailed analysis reports** (Markdown + optional JSON)
2) **Aggregated index pages** (static HTML)
3) **Artifacts** suitable for later extension (CSV exports, scoring breakdowns, charts)

### 1.2 User's Investment Philosophy Encoded
- Prefers **quality businesses** in domains he understands (especially tech/industry infrastructure), but **only when priced attractively** due to temporary reasons.
- Emphasis on:
  - Margin of safety
  - Strong cash generation
  - Balance-sheet resilience
  - Durable economics (ROIC, stable margins)
  - Avoiding "cheap for a reason" traps

---

## 2) Core Requirements (Must Have)

### 2.1 Quiet Python Machine
- **All scanning, analysis, scoring, and report generation is implemented in Python.**
- Runs from CLI (no interactive prompts by default).
- Logs to file; minimal stdout.
- Produces deterministic outputs into a timestamped run folder.
- All dependencies listed in `requirements.txt` at project root (user installs manually).
- Must run inside the project virtual environment (`env/` directory).
  - Activation: `& env\Scripts\Activate.ps1` (Windows) or `source env/bin/activate` (Unix).

### 2.2 Outputs
- For every candidate ticker that passes initial screen:
  - `reports/<TICKER>/report.md` (human readable)
  - `reports/<TICKER>/report.json` (machine readable; full metrics + intermediate calculations)
- Aggregations:
  - **`index.html`** at repository root (GitHub Pages entry point — see §2.4)
  - `exports/candidates.csv` (ranked list)
  - `exports/rejected.csv` (failed filters + reasons)
  - `exports/metrics.parquet` or `.csv` (optional data lake)

### 2.3 "Buy Recommendations" as Signals
Per ticker, produce:
- `signal`: one of
  - `STRONG_BUY_SIGNAL`
  - `BUY_SIGNAL`
  - `WATCH`
  - `REJECT`
- Must include:
  - Why it got this signal (top 5 drivers)
  - Top risks (top 5)
  - What would invalidate the thesis (clear triggers)

### 2.4 Static Site (GitHub Pages)
- **`index.html` lives at the repository root** so it is served directly by GitHub Pages (root deployment).
- Supporting assets in `site/` subdirectory (CSS, JS, per-ticker pages).
- No backend. Pure HTML/CSS with vanilla JS for sorting/filtering/search.
- The Python pipeline **generates** `index.html` and all `site/` assets as its final step.
- Must include:
  - Ranked table with filters (sector, market cap, P/E, FCF yield, ROIC, margin of safety)
  - Per ticker detail pages: `site/ticker/<TICKER>.html`
  - A "Methodology" section/page documenting the protocol
- Must be beautifully crafted:
  - Modern, clean design (dark/light theme optional)
  - Responsive layout
  - All data self-contained — works fully offline
  - Prominent disclaimer banner

---

## 3) Universe Definition

### 3.1 Primary Universe (Default)
- US-listed equities (NYSE/Nasdaq)
- Market cap > $1B
- Exclude:
  - OTC/pink sheets
  - Funds/ETFs
  - Microcaps

### 3.2 Sector Handling
Two supported modes:
- `mode = "simple"`: exclude Financials + REITs by default (easier comparability)
- `mode = "full"`: include all, but apply sector-specific thresholds (especially for banks/insurers)

Config flag: `--sector-mode simple|full`

---

## 4) Screening Protocol (Algorithm)

### 4.1 Stage A: Hard Filters (Graham-ish "No Mercy")
A ticker must pass **all**:

- Market cap > $1B
- P/E (TTM) < 10  
  - If P/E is missing or negative: reject (unless `allow_turnarounds=true`, default false)
- EPS positive in at least **5 of last 7 years** (or 5 consecutive years if data supports)
- Free Cash Flow (FCF) positive in **>= 4 of last 5 years**
- Debt-to-Equity < 1.0 (sector-dependent if `sector-mode=full`)
- Current ratio > 1.5 (sector-dependent)
- No extreme dilution:
  - Shares outstanding CAGR (5y) <= +3% unless explicitly justified by M&A

Output requirement:
- If rejected, record `reject_reasons[]` with exact failing thresholds + values.

### 4.2 Stage B: Quality Filter (Buffett-style)
Pass threshold scoring (not necessarily all-or-nothing, but must exceed minimum):

Key metrics (5y preferred):
- ROIC > 12%
- ROE > 15% (warn if leverage-driven)
- Gross margin stability: stddev below configurable threshold (industry normalized)
- Operating margin not in structural decline
- Revenue trend: not a persistent multi-year decline (unless turnaround mode)
- FCF margin: positive and not collapsing

Define:
- `quality_score` (0–100)
- `quality_min` default 60 to proceed

### 4.3 Stage C: Cyclicality & Normalization
Detect cyclical businesses and normalize:
- Use 5–10y averages for EPS and FCF
- Identify "peak earnings" signals:
  - large deviation of current margin vs long-run mean
  - commodity-linked revenue flags (heuristics)
- If cyclical risk high:
  - tighten P/E threshold (e.g., require < 7)
  - or reduce intrinsic value multiples

Output:
- `cyclicality_flag`: LOW/MED/HIGH
- explanation text + supporting metrics

### 4.4 Stage D: Intrinsic Value & Margin of Safety
Compute intrinsic value using **at least two** conservative methods:

**Method 1: Conservative Earnings Power**
- normalized EPS (e.g., avg EPS 5y)
- conservative multiple (default 10; lower if cyclical)
- intrinsic_price_1 = normalized_EPS * conservative_multiple

**Method 2: Conservative DCF (FCF-based)**
- normalized FCF
- conservative growth (g) default 0–3%
- discount rate (r) default 10–12%
- terminal multiple conservative OR Gordon growth
- intrinsic_price_2 with a range (low/base/high)

Compute:
- `intrinsic_range = [low, base, high]`
- `margin_of_safety = 1 - (market_price / intrinsic_base)`
- Require MOS >= 30% for BUY_SIGNAL; >= 45% for STRONG_BUY_SIGNAL (configurable)

### 4.5 Stage E: Value Trap Detection
Hard red flags produce rejection or forced WATCH:
- 3-year downward trend in revenue + margins simultaneously
- FCF negative while EPS positive (possible accrual accounting issue)
- Net debt increasing faster than operating income
- Interest coverage deteriorating below threshold
- Structural industry decline heuristic (optional, conservative)
- One-off earnings inflating P/E

Output:
- `trap_flags[]` each with:
  - flag name
  - evidence (metric/value)
  - severity

### 4.6 Stage F: Final Scoring & Ranking
Compute final score:

Weights (default):
- Valuation (30%)
- Earnings & Cash Quality (25%)
- Balance Sheet (20%)
- Stability & Durability (15%)
- Moat/Qualitative proxies (10%) – only from measurable proxies (R&D intensity, pricing power via margins stability, etc.)

Outputs:
- `final_score` 0–100
- rank ordering by:
  1) signal category
  2) final_score desc
  3) margin_of_safety desc

---

## 5) Recommendation (Signal) Rules

### 5.1 STRONG_BUY_SIGNAL
- Pass Stage A
- quality_score >= 75
- MOS >= 45%
- trap_flags severity not HIGH
- balance sheet strong (net debt/FCF manageable)

### 5.2 BUY_SIGNAL
- Pass Stage A
- quality_score >= 65
- MOS >= 30%
- no HIGH severity traps

### 5.3 WATCH
- Pass Stage A but:
  - MOS < 30% OR quality_score borderline OR uncertainty elevated
- Or cyclical HIGH but cheap: requires monitoring and normalization

### 5.4 REJECT
- Fail Stage A OR
- trap_flags HIGH severity OR
- missing critical data

Every signal must include:
- "What would make this a BUY?" (for WATCH)
- "What would make this a REJECT?" (for BUY categories)

---

## 6) Report Format (Markdown)

### 6.1 `report.md` Template (Required Sections)
1) Header
   - Ticker, Company name, Sector/Industry, Market cap, Date, Data sources
2) Summary (5 bullets max)
   - Signal, Score, MOS, key thesis, top risk
3) Pass/Fail Screening Table
   - Stage A results with thresholds and actuals
4) Key Metrics Snapshot
   - P/E, Fwd P/E, P/B, EV/EBITDA, ROIC, ROE, margins, FCF yield, debt ratios
5) Durability & Quality
   - margin stability, ROIC trend, revenue trend, dilution, capex intensity
6) Valuation
   - Method 1 details + assumptions
   - Method 2 details + assumptions
   - Intrinsic value range
7) Risks & Trap Flags
   - enumerated list with severity + evidence
8) Thesis Validation Triggers
   - what metrics/events to monitor
9) Decision
   - "Why this signal" (top 5 drivers)
   - "Why not stronger/weaker" (constraints)
10) Disclaimer

### 6.2 JSON Output (`report.json`)
Must include:
- raw metrics
- computed metrics
- intermediate values (normalized EPS/FCF, discount rate, growth, multiples)
- flags and reasons
- final signal + score breakdown

---

## 7) Static Site Requirements (GitHub Pages)

### 7.1 Deployment Model
- GitHub Pages serves from the **repository root** (not `/docs` or `gh-pages` branch).
- Therefore **`index.html` must be at the repo root**.
- All other site assets live under `site/` (CSS, JS, ticker pages).
- The Python pipeline regenerates these files on every run.

### 7.2 Site Pages
- **`/index.html`** (repo root)
  - Hero summary: run date, total scanned, candidates found, top signal counts
  - Ranked candidates table (sortable, filterable by sector, signal, MOS, score)
  - Quick-glance cards for STRONG_BUY_SIGNAL tickers
  - Links to per-ticker detail pages
  - Methodology section (inline or linked)
  - Disclaimer banner
- **`/site/ticker/<TICKER>.html`**
  - Full analysis summary rendered from `report.json`
  - Key metrics dashboard
  - Valuation breakdown
  - Risk flags
  - Signal rationale
  - Link back to index

### 7.3 UI/UX
- Beautifully crafted, modern design
- Clean typography, good use of whitespace
- Responsive (desktop + mobile)
- No heavy frameworks — vanilla HTML/CSS/JS
- Inline SVG or CSS-based mini-charts (sparklines for trends)
- Color-coded signals (green/amber/red)
- Dark mode support (optional, nice-to-have)
- Must work fully offline (no CDN dependencies)

---

## 8) Configuration & Reproducibility

### 8.1 Config File
`config.yaml` defines:
- thresholds (P/E, MOS, ROIC, debt ratios)
- sector mode
- universe sources
- DCF assumptions (r, g)
- output paths
- caching policy
- API keys (via env vars)

### 8.2 Run Folder Structure
Example:
```
runs/2026-02-28_0930/
  config_resolved.yaml
  logs/run.log
  data/raw/...
  data/processed/...
  reports/<TICKER>/{report.md, report.json}
  exports/{candidates.csv,rejected.csv}
```

After a successful run, the pipeline **copies/generates** the site output to:
```
/index.html              ← GitHub Pages entry point
/site/style.css
/site/app.js
/site/ticker/<TICKER>.html
```

### 8.3 Determinism
- Pin library versions (requirements lock)
- Store resolved config
- Store data snapshots (or at least timestamps + source references)

---

## 9) Data Sources (Abstract Interface)

Define a data provider interface supporting:
- price + shares + market cap
- financial statements (income/balance/cashflow) 10y if possible
- derived ratios (or compute internally)
- sector/industry classification

Must support caching:
- avoid re-fetching unchanged data
- cache TTL configurable

Note: Provider can be swapped later (Yahoo/AlphaVantage/IEX/etc.). The spec requires a clean abstraction.

---

## 10) Error Handling & Edge Cases

- Missing key metrics → REJECT with reason `MISSING_DATA:<field>`
- Conflicting data between sources:
  - choose primary source
  - record discrepancy in report
- Negative earnings:
  - default reject unless `allow_turnarounds=true`
- Financials/REITs:
  - only if `sector-mode=full`, apply separate rules

---

## 11) Testing & Validation

### 11.1 Unit Tests
- metric computations (ROIC, FCF yield, MOS)
- DCF math
- rule evaluation (pass/fail reasons)
- trap flag triggers

### 11.2 Golden Tests (Regression)
- select a small set of tickers
- store expected outputs (or hashes)
- ensure changes are intentional

---

## 12) Deliverables Checklist

- [ ] CLI entrypoint: `scan_value`
- [ ] Config load + validation
- [ ] Provider interface + caching
- [ ] Universe builder
- [ ] Stage A filters + reject reasons
- [ ] Quality scoring
- [ ] Cyclicality detection + normalization
- [ ] Valuation methods + MOS
- [ ] Trap detection
- [ ] Final scoring + signal assignment
- [ ] Markdown + JSON report generation
- [ ] Exports (candidates/rejected)
- [ ] Static site generator
- [ ] Methodology page generator
- [ ] Logging + run folder management
- [ ] Tests

---

## 13) Non-Goals (For v1.0)
- No real-time trading
- No broker integration
- No portfolio optimization
- No personalized financial advice beyond signals based on defined rules

---

## 14) Success Criteria
- Produces a ranked list of candidates consistent with the protocol.
- Each recommendation is explainable and auditable.
- Static site makes it easy for Avi to review top opportunities quickly.
- Easy to extend with additional factors (dividend stability, insider buying, etc.).

---

## 15) Default Thresholds (Initial)
These are starting points; must be configurable:

- Market cap > $1B
- P/E < 10
- EPS positive: >= 5 of last 7 years
- FCF positive: >= 4 of last 5 years
- Debt/Equity < 1.0
- Current ratio > 1.5
- ROIC > 12%
- ROE > 15%
- MOS >= 30% for BUY_SIGNAL
- MOS >= 45% for STRONG_BUY_SIGNAL
- quality_min = 60
- discount rate r = 11%
- growth g = 2% (cap at 3%)

---

## 16) Disclaimer Text (Must Appear)
"This system provides research outputs based on predefined quantitative rules and public financial data. It is not financial advice. Markets involve risk, and past performance does not predict future results. Always verify data and consider consulting a licensed professional before making investment decisions."

---

## 17) Development Environment

### 17.1 Virtual Environment
- Python virtual environment lives in `env/` (already in `.gitignore`).
- **Always activate before running anything:**
  - Windows: `& env\Scripts\Activate.ps1`
  - Unix/macOS: `source env/bin/activate`
- Never install packages directly — add to `requirements.txt` and let the developer install.

### 17.2 Dependencies
- All Python dependencies listed in `requirements.txt` at project root.
- Developer installs with: `pip install -r requirements.txt`
- Pin versions for reproducibility.

### 17.3 Project Structure
```
STOKS/
├── index.html                  ← Generated by pipeline (GitHub Pages root)
├── site/                       ← Generated site assets
│   ├── style.css
│   ├── app.js
│   └── ticker/
│       └── <TICKER>.html
├── src/                        ← Python source code
│   ├── __init__.py
│   ├── main.py                 ← CLI entrypoint
│   ├── config.py               ← Config loader
│   ├── providers/              ← Data provider abstraction
│   ├── pipeline/               ← Screening stages A–F
│   ├── valuation/              ← Intrinsic value calculations
│   ├── scoring/                ← Quality + final scoring
│   ├── reports/                ← MD + JSON report generators
│   └── site_generator/         ← Static HTML generator
├── config.yaml                 ← User configuration
├── requirements.txt            ← Python dependencies
├── docs/                       ← Specs and documentation
│   └── SPEC_v1.0.md
├── tests/                      ← Unit + golden tests
├── runs/                       ← Timestamped run outputs
├── exports/                    ← CSV exports
├── .github/                    ← GitHub instructions
├── .copilot/                   ← Copilot skills
├── .gitignore
└── env/                        ← Virtual environment (git-ignored)
```

---

## 18) GitHub Pages Deployment
- Repository configured to serve GitHub Pages from the **root of the main branch**.
- `index.html` at root is the entry point.
- After each pipeline run, commit updated `index.html` + `site/` to publish fresh results.
- No build step required on GitHub's side — the Python pipeline produces ready-to-serve static files.

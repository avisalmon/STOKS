# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

This project uses a Python virtual environment in `env/`. **Always activate it before any Python work.**

```powershell
# Windows (PowerShell)
& env\Scripts\Activate.ps1
```

**Never install packages directly.** Add to `requirements.txt` first, then `pip install -r requirements.txt`.

## Commands

```bash
# Full scan (~25 min, 900+ tickers)
python -m src.main -v

# Analyze specific tickers
python -m src.main -t AAPL -t MSFT -v

# Dry run — show universe count only
python -m src.main --dry-run

# Custom config
python -m src.main --config my_config.yaml -v

# Run tests
python -m pytest tests/ -v

# Run tests with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

## Architecture

STOKS is a Graham-Buffett value investing screener. It scans the S&P 500 + S&P 400 MidCap universe through a 6-stage pipeline, then generates Markdown/JSON per-ticker reports and a self-contained static site dashboard deployed via GitHub Pages.

### Entry point flow

`src/main.py` (Click CLI) → `src/pipeline/orchestrator.py` → `src/reports/` → `src/site_generator/`

1. `load_config()` merges `config.yaml` over hardcoded DEFAULTS into a typed `AppConfig` dataclass tree
2. `RunManager` creates a timestamped folder under `runs/<YYYY-MM-DD_HHMM>/`
3. `YFinanceProvider` wraps yfinance with a file-based TTL cache (`.cache/`) and a token-bucket rate limiter
4. `UniverseBuilder` fetches the S&P 500 + 400 ticker lists from Wikipedia
5. `run_pipeline()` runs each ticker through stages A→F sequentially, returns `{candidates, rejected, errors}`
6. `generate_all_reports()` writes `report.md` + `report.json` per candidate
7. `generate_site()` uses Jinja2 to render `index.html` (repo root) and `site/ticker/<TICKER>.html`

### Pipeline stages (all in `src/pipeline/orchestrator.py`)

| Stage | Function | Purpose |
|-------|----------|---------|
| A | `_run_stage_a` | Hard Graham filters — pass/fail (P/E, EPS years, FCF years, D/E, current ratio, dilution) |
| B | `_run_stage_b` | Buffett quality score 0–100 (ROIC, ROE, margin stability, op margin trend, revenue trend, FCF margin) |
| C | `_run_stage_c` | Cyclicality classification LOW/MED/HIGH; normalizes EPS/FCF over 5 years |
| D | `_run_stage_d` | Intrinsic value via EPV (normalized EPS × multiple) + DCF; computes margin of safety |
| E | `_run_stage_e` | Value trap flags: revenue+margin decline, FCF/EPS divergence, debt outpacing income, interest coverage |
| F | `_run_stage_f` | Weighted composite score + signal: STRONG_BUY_SIGNAL / BUY_SIGNAL / WATCH / REJECT |

Stages are **not separated into individual files** — all six `_run_stage_*` functions live in `orchestrator.py`.

### Data model (`src/providers/base.py`)

`TickerData` bundles four dataclasses:
- `CompanyInfo` — ticker, name, sector, industry
- `PriceData` — current price, shares outstanding, market cap
- `FinancialStatements` — pandas DataFrames for `income`, `balance`, `cashflow` (rows = years, cols = metrics)
- `DerivedMetrics` — pre-computed ratios from yfinance (pe_ratio, roe, roic, debt_to_equity, current_ratio, beta, operating_margin)

The `DataProvider` ABC in `base.py` defines the interface; `YFinanceProvider` is the only implementation. New providers must implement `get_ticker_data(ticker) -> TickerData | None`.

### Configuration (`config.yaml` + `src/config.py`)

All thresholds live in `config.yaml` and map 1:1 to typed dataclasses in `src/config.py`. `load_config()` deep-merges YAML over hardcoded DEFAULTS, then validates. The resolved config is saved to `runs/<timestamp>/config_resolved.yaml` for reproducibility.

Key configurable knobs: `hard_filters.pe_max`, `valuation.mos_buy` / `mos_strong_buy`, `scoring.weights`, `provider.cache_ttl_hours`.

### Output & GitHub Pages

- `index.html` (repo root) + `site/` are **committed to `main`** — GitHub Pages serves from the root of `main`
- After a pipeline run: `git add index.html site/ && git commit -m "Scan YYYY-MM-DD" && git push origin main`
- `runs/` and `.cache/` are gitignored (ephemeral artifacts)

### Copilot skills

`.copilot/skills/scan-stocks.skill.yaml` and `analyze-stock.skill.yaml` contain step-by-step procedures and screening parameters. Read these before modifying pipeline logic.

## Key files

- [config.yaml](config.yaml) — all thresholds (edit this to tune screening)
- [src/pipeline/orchestrator.py](src/pipeline/orchestrator.py) — the entire 6-stage pipeline
- [src/providers/base.py](src/providers/base.py) — `TickerData` data model and `DataProvider` ABC
- [src/providers/yfinance_provider.py](src/providers/yfinance_provider.py) — Yahoo Finance data fetching
- [docs/SPEC_v1.0.md](docs/SPEC_v1.0.md) — full technical specification
- [docs/BACKLOG.md](docs/BACKLOG.md) — sprint planning and task tracking

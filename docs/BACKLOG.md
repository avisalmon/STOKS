# STOKS — Sprint Backlog & Progress Tracker

> **Last updated:** 2026-03-01  
> **Dashboard:** Open `docs/dashboard.html` in a browser for visual overview.

---

## Legend

| Status | Meaning |
|--------|---------|
| ⬜ TODO | Not started |
| 🔵 IN PROGRESS | Currently being worked on |
| ✅ DONE | Completed and verified |
| 🚫 BLOCKED | Blocked by dependency or issue |

---

## Sprint 0 — Project Setup ✅
> **Goal:** Repository, spec, tooling, and project scaffolding.  
> **Status:** COMPLETE

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 0.1 | Initialize git repository | ✅ DONE | |
| 0.2 | Create .gitignore | ✅ DONE | env/, __pycache__/, runs/, .cache/ |
| 0.3 | Write SPEC_v1.0.md | ✅ DONE | Full Graham-Buffett protocol |
| 0.4 | Create requirements.txt | ✅ DONE | yfinance, pandas, jinja2, click, lxml, etc. |
| 0.5 | Create .github/INSTRUCTIONS.md | ✅ DONE | Dev workflow, env rules |
| 0.6 | Create Copilot skills | ✅ DONE | scan-stocks + analyze-stock |
| 0.7 | Create backlog & dashboard | ✅ DONE | This file + dashboard.html |

---

## Sprint 1 — Foundation & Data Layer ✅
> **Goal:** Config system, data provider abstraction, caching, universe builder.  
> **Status:** COMPLETE

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 1.1 | Create `src/` package structure | ✅ DONE | Full package tree with subpackages |
| 1.2 | Implement `config.py` + `config.yaml` | ✅ DONE | Typed dataclasses, YAML loading, deep merge |
| 1.3 | Define data provider interface | ✅ DONE | `DataProvider` ABC in `providers/base.py` |
| 1.4 | Implement yfinance provider | ✅ DONE | Fetch info, price, statements, derived metrics |
| 1.5 | Implement caching layer | ✅ DONE | File-based cache with TTL in `providers/cache.py` |
| 1.6 | Implement rate limiter + retry logic | ✅ DONE | Token bucket rate limiter + exponential backoff |
| 1.7 | Build universe builder | ✅ DONE | S&P 500 + S&P 400 from Wikipedia, sector filtering |
| 1.8 | CLI entrypoint with Click | ✅ DONE | `--config`, `-t` (multiple), `--sector-mode`, `--verbose`, `--dry-run` |
| 1.9 | Logging setup (loguru) | ✅ DONE | File + console with configurable verbosity |
| 1.10 | Run folder management | ✅ DONE | Timestamped dirs: `runs/YYYY-MM-DD_HHMM/` |
| 1.11 | Unit tests for config + provider | ⬜ TODO | Future: add pytest coverage |

---

## Sprint 2 — Screening Pipeline (Stages A–C) ✅
> **Goal:** Hard filters, quality scoring, cyclicality detection.  
> **Status:** COMPLETE

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 2.1 | Stage A: Hard Filters (Graham) | ✅ DONE | P/E, EPS, FCF, D/E, CR, dilution with adaptive year scaling |
| 2.2 | Reject reasons tracking | ✅ DONE | Exact values vs thresholds per ticker |
| 2.3 | Stage B: Quality Scoring (Buffett) | ✅ DONE | ROIC, ROE, margins, revenue trend, FCF margin |
| 2.4 | Quality score computation (0–100) | ✅ DONE | 6 weighted sub-scores |
| 2.5 | Stage C: Cyclicality detection | ✅ DONE | Margin deviation, revenue volatility, sector flags |
| 2.6 | Earnings normalization (5–10y avg) | ✅ DONE | For cyclical businesses |
| 2.7 | Pipeline orchestrator (A→B→C) | ✅ DONE | Full chain with data passing |
| 2.8 | Unit tests for each stage | ⬜ TODO | Future: add pytest coverage |
| 2.9 | Integration test: small ticker set | ✅ DONE | Validated with AAPL, MSFT, JNJ, KO, HOG |

---

## Sprint 3 — Valuation & Trap Detection (Stages D–E) ✅
> **Goal:** Intrinsic value calculations, margin of safety, value trap flags.  
> **Status:** COMPLETE

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 3.1 | Method 1: Conservative Earnings Power | ✅ DONE | Normalized EPS × conservative multiple |
| 3.2 | Method 2: Conservative DCF | ✅ DONE | FCF-based, low/base/high range |
| 3.3 | Margin of Safety calculation | ✅ DONE | 1 - (price / intrinsic_base) |
| 3.4 | Intrinsic value range aggregation | ✅ DONE | Combine EPV + DCF into [low, base, high] |
| 3.5 | Stage E: Value Trap Detection | ✅ DONE | Revenue/margin decline, FCF divergence |
| 3.6 | Trap flag severity system | ✅ DONE | LOW / MED / HIGH with evidence strings |
| 3.7 | Interest coverage + debt growth checks | ✅ DONE | |
| 3.8 | One-off earnings detection | ✅ DONE | Heuristic for inflated P/E |
| 3.9 | Unit tests for valuation math | ⬜ TODO | Future: DCF, EPV, MOS edge cases |
| 3.10 | Unit tests for trap detection | ⬜ TODO | |

---

## Sprint 4 — Scoring, Signals & Reports (Stage F + Output) ✅
> **Goal:** Final scoring, signal assignment, markdown/JSON report generation.  
> **Status:** COMPLETE

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 4.1 | Stage F: Final weighted scoring | ✅ DONE | Valuation 30%, quality 25%, balance 20%, stability 15%, moat 10% |
| 4.2 | Signal assignment logic | ✅ DONE | STRONG_BUY / BUY / WATCH / REJECT |
| 4.3 | Signal drivers (top 5 why) | ✅ DONE | Rich narrative explanations per driver |
| 4.4 | Signal risks (top 5) | ✅ DONE | Detailed context per trap flag type |
| 4.5 | Thesis invalidation triggers | ✅ DONE | EPS drop, margin collapse, leverage, FCF, management actions |
| 4.6 | Markdown report generator | ✅ DONE | Full report with thesis narrative, research links, tables |
| 4.7 | JSON report generator | ✅ DONE | All raw + computed metrics |
| 4.8 | CSV exports (candidates + rejected) | ✅ DONE | candidates.csv + rejected.csv |
| 4.9 | Full pipeline integration test | ✅ DONE | A→F end-to-end validated |
| 4.10 | Golden tests (regression) | ⬜ TODO | Fixed tickers, expected outputs |

---

## Sprint 5 — Static Site Generator ✅
> **Goal:** Beautiful `index.html` at repo root + per-ticker pages for GitHub Pages.  
> **Status:** COMPLETE

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 5.1 | Jinja2 template: index.html | ✅ DONE | Stats strip, filterable candidate table, rejected section |
| 5.2 | Jinja2 template: ticker page | ✅ DONE | Metrics dashboard, valuation, stage details, financials |
| 5.3 | CSS design (site/style.css) | ✅ DONE | Dark theme, GitHub-inspired, modern design |
| 5.4 | JS: table sorting & filtering | ✅ DONE | Vanilla JS, sector/signal/search filters |
| 5.5 | Methodology section/page | ✅ DONE | Graham-Buffett methodology explanation |
| 5.6 | Disclaimer banner | ✅ DONE | Prominent, always visible on all pages |
| 5.7 | Sparklines / mini-charts (CSS/SVG) | ✅ DONE | Inline SVG with trend-colored polylines (green/red/yellow) |
| 5.8 | Color-coded signals | ✅ DONE | Green/amber/red signal badges + score bars |
| 5.9 | Mobile responsiveness | ✅ DONE | Responsive grid, stacking on mobile |
| 5.10 | Offline verification | ✅ DONE | No CDN dependencies — fully self-contained |
| 5.11 | Site generation integration | ✅ DONE | Pipeline Step 8 → index.html + site/ |
| 5.12 | Public research links | ✅ DONE | Yahoo Finance, Finviz, SEC EDGAR, Macrotrends, Simply Wall St |

---

## Sprint 6 — Polish, Testing & Documentation
> **Goal:** Hardening, edge cases, documentation, production validation.  
> **Status:** Core complete, tests deferred

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 6.1 | Error handling hardening | ✅ DONE | Missing data, API failures, edge cases handled |
| 6.2 | Partial-run resume capability | ⬜ TODO | Future: don't re-scan completed tickers |
| 6.3 | Full test suite pass | ⬜ TODO | Future: pytest unit + integration tests |
| 6.4 | README.md | ✅ DONE | Comprehensive docs: architecture, pipeline, CLI, config |
| 6.5 | GitHub Pages config verification | ⬜ TODO | Root deployment, index.html served |
| 6.6 | First full production run | ✅ DONE | 903 tickers → 20 candidates, 883 rejected, 0 errors |
| 6.7 | Review & tune thresholds | ✅ DONE | P/E adjusted to 15 (Graham's Intelligent Investor criterion) |
| 6.8 | Performance profiling | ✅ DONE | ~25 min for 903 tickers with caching |

---

## Backlog (Future — Not Scheduled)
> Ideas for v1.1+ after core is stable.

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| F.1 | Financial Modeling Prep (FMP) provider | Medium | Better data quality than yfinance |
| F.2 | Light mode toggle | Low | Currently dark — add light theme option |
| F.3 | Dividend analysis module | Medium | Yield, payout ratio, dividend growth |
| F.4 | Insider buying/selling signals | Medium | Additional quality indicator |
| F.5 | Sector-specific threshold profiles | Medium | Banks, REITs, energy separate rules |
| F.6 | GitHub Actions: scheduled auto-scan | High | Weekly automated runs |
| F.7 | Historical run comparison | Medium | Track how signals change over time |
| F.8 | Turnaround mode (`allow_turnarounds`) | Low | Special situations hunting |
| F.9 | Email/notification on new STRONG_BUY | Medium | Alert system |
| F.10 | Portfolio tracking overlay | Low | Track owned positions vs signals |
| F.11 | International markets (Europe, Asia) | Low | Expand universe beyond US |
| F.12 | Piotroski F-Score integration | Medium | Additional financial health metric |
| F.13 | Unit test suite (pytest) | Medium | Coverage for all stages, edge cases |
| F.14 | ~~Sparkline mini-charts~~ | ✅ DONE | Moved to Sprint 5.7 |

---

## Progress Summary

| Sprint | Tasks | Done | Progress |
|--------|-------|------|----------|
| Sprint 0 — Setup | 7 | 7 | ████████████████████ 100% |
| Sprint 1 — Foundation | 11 | 10 | ██████████████████░░ 91% |
| Sprint 2 — Pipeline A–C | 9 | 8 | █████████████████░░░ 89% |
| Sprint 3 — Valuation D–E | 10 | 8 | ████████████████░░░░ 80% |
| Sprint 4 — Scoring & Reports | 10 | 9 | ██████████████████░░ 90% |
| Sprint 5 — Static Site | 12 | 12 | ████████████████████ 100% |
| Sprint 6 — Polish | 8 | 5 | ████████████░░░░░░░░ 63% |
| **TOTAL** | **67** | **59** | **█████████████████░░░ 88%** |

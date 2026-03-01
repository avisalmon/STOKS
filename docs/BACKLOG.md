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
| 0.4 | Create requirements.txt | ✅ DONE | yfinance, pandas, jinja2, click, etc. |
| 0.5 | Create .github/INSTRUCTIONS.md | ✅ DONE | Dev workflow, env rules |
| 0.6 | Create Copilot skills | ✅ DONE | scan-stocks + analyze-stock |
| 0.7 | Create backlog & dashboard | ✅ DONE | This file + dashboard.html |

---

## Sprint 1 — Foundation & Data Layer
> **Goal:** Config system, data provider abstraction, caching, universe builder.  
> **Estimated effort:** Medium

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 1.1 | Create `src/` package structure | ⬜ TODO | __init__.py, main.py, subpackages |
| 1.2 | Implement `config.py` + `config.yaml` | ⬜ TODO | Load/validate YAML config with defaults |
| 1.3 | Define data provider interface | ⬜ TODO | Abstract base class for financial data |
| 1.4 | Implement yfinance provider | ⬜ TODO | Fetch statements, price, market cap, sector |
| 1.5 | Implement caching layer | ⬜ TODO | File-based cache with TTL |
| 1.6 | Implement rate limiter + retry logic | ⬜ TODO | Polite API usage, backoff |
| 1.7 | Build universe builder | ⬜ TODO | US-listed, >$1B, exclude OTC/ETFs |
| 1.8 | CLI entrypoint with Click | ⬜ TODO | `python -m src.main` with options |
| 1.9 | Logging setup (loguru) | ⬜ TODO | File + minimal stdout |
| 1.10 | Run folder management | ⬜ TODO | Timestamped output dirs |
| 1.11 | Unit tests for config + provider | ⬜ TODO | |

---

## Sprint 2 — Screening Pipeline (Stages A–C)
> **Goal:** Hard filters, quality scoring, cyclicality detection.  
> **Estimated effort:** Medium-High  
> **Depends on:** Sprint 1

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 2.1 | Stage A: Hard Filters (Graham) | ⬜ TODO | P/E, EPS, FCF, D/E, CR, dilution |
| 2.2 | Reject reasons tracking | ⬜ TODO | Exact values vs thresholds per ticker |
| 2.3 | Stage B: Quality Scoring (Buffett) | ⬜ TODO | ROIC, ROE, margins, revenue trend |
| 2.4 | Quality score computation (0–100) | ⬜ TODO | Weighted sub-scores |
| 2.5 | Stage C: Cyclicality detection | ⬜ TODO | Margin deviation, commodity flags |
| 2.6 | Earnings normalization (5–10y avg) | ⬜ TODO | For cyclical businesses |
| 2.7 | Pipeline orchestrator (A→B→C) | ⬜ TODO | Chain stages, pass data forward |
| 2.8 | Unit tests for each stage | ⬜ TODO | |
| 2.9 | Integration test: small ticker set | ⬜ TODO | End-to-end A→C with real data |

---

## Sprint 3 — Valuation & Trap Detection (Stages D–E)
> **Goal:** Intrinsic value calculations, margin of safety, value trap flags.  
> **Estimated effort:** Medium-High  
> **Depends on:** Sprint 2

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 3.1 | Method 1: Conservative Earnings Power | ⬜ TODO | normalized_EPS × conservative_multiple |
| 3.2 | Method 2: Conservative DCF | ⬜ TODO | FCF-based, low/base/high range |
| 3.3 | Margin of Safety calculation | ⬜ TODO | 1 - (price / intrinsic_base) |
| 3.4 | Intrinsic value range aggregation | ⬜ TODO | Combine methods into [low, base, high] |
| 3.5 | Stage E: Value Trap Detection | ⬜ TODO | Revenue/margin decline, FCF divergence |
| 3.6 | Trap flag severity system | ⬜ TODO | LOW / MED / HIGH with evidence |
| 3.7 | Interest coverage + debt growth checks | ⬜ TODO | |
| 3.8 | One-off earnings detection | ⬜ TODO | Heuristic for inflated P/E |
| 3.9 | Unit tests for valuation math | ⬜ TODO | DCF, EPV, MOS edge cases |
| 3.10 | Unit tests for trap detection | ⬜ TODO | |

---

## Sprint 4 — Scoring, Signals & Reports (Stage F + Output)
> **Goal:** Final scoring, signal assignment, markdown/JSON report generation.  
> **Estimated effort:** Medium  
> **Depends on:** Sprint 3

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 4.1 | Stage F: Final weighted scoring | ⬜ TODO | Valuation 30%, quality 25%, etc. |
| 4.2 | Signal assignment logic | ⬜ TODO | STRONG_BUY / BUY / WATCH / REJECT |
| 4.3 | Signal drivers (top 5 why) | ⬜ TODO | Per-ticker explanation |
| 4.4 | Signal risks (top 5) | ⬜ TODO | Per-ticker risk summary |
| 4.5 | Thesis invalidation triggers | ⬜ TODO | What to monitor |
| 4.6 | Markdown report generator | ⬜ TODO | Full template per spec §6.1 |
| 4.7 | JSON report generator | ⬜ TODO | All raw + computed metrics |
| 4.8 | CSV exports (candidates + rejected) | ⬜ TODO | |
| 4.9 | Full pipeline integration test | ⬜ TODO | A→F end-to-end |
| 4.10 | Golden tests (regression) | ⬜ TODO | Fixed tickers, expected outputs |

---

## Sprint 5 — Static Site Generator
> **Goal:** Beautiful `index.html` at repo root + per-ticker pages for GitHub Pages.  
> **Estimated effort:** Medium  
> **Depends on:** Sprint 4

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 5.1 | Jinja2 template: index.html | ⬜ TODO | Hero, ranked table, signal cards |
| 5.2 | Jinja2 template: ticker page | ⬜ TODO | Metrics dashboard, valuation, risks |
| 5.3 | CSS design (site/style.css) | ⬜ TODO | Modern, clean, responsive |
| 5.4 | JS: table sorting & filtering | ⬜ TODO | Vanilla JS, sector/signal/MOS filters |
| 5.5 | Methodology section/page | ⬜ TODO | Generated from config + spec |
| 5.6 | Disclaimer banner | ⬜ TODO | Prominent, always visible |
| 5.7 | Sparklines / mini-charts (CSS/SVG) | ⬜ TODO | Trend indicators for key metrics |
| 5.8 | Color-coded signals | ⬜ TODO | Green/amber/red visual system |
| 5.9 | Mobile responsiveness | ⬜ TODO | |
| 5.10 | Offline verification | ⬜ TODO | No CDN dependencies |
| 5.11 | Site generation integration | ⬜ TODO | Pipeline final step → index.html + site/ |

---

## Sprint 6 — Polish, Testing & Documentation
> **Goal:** Hardening, edge cases, documentation, GitHub Pages deployment.  
> **Estimated effort:** Low-Medium  
> **Depends on:** Sprint 5

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 6.1 | Error handling hardening | ⬜ TODO | Missing data, API failures, edge cases |
| 6.2 | Partial-run resume capability | ⬜ TODO | Don't re-scan completed tickers |
| 6.3 | Full test suite pass | ⬜ TODO | All unit + integration + golden tests |
| 6.4 | README.md | ⬜ TODO | Project overview, setup, usage |
| 6.5 | GitHub Pages config verification | ⬜ TODO | Root deployment, index.html served |
| 6.6 | First full production run | ⬜ TODO | Scan entire universe, review results |
| 6.7 | Review & tune thresholds | ⬜ TODO | Based on first run quality |
| 6.8 | Performance profiling | ⬜ TODO | Optimize slow API calls, caching |

---

## Backlog (Future — Not Scheduled)
> Ideas for v1.1+ after core is stable.

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| F.1 | Financial Modeling Prep (FMP) provider | Medium | Better data quality than yfinance |
| F.2 | Dark mode toggle | Low | Nice-to-have |
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

---

## Progress Summary

| Sprint | Tasks | Done | Progress |
|--------|-------|------|----------|
| Sprint 0 — Setup | 7 | 7 | ████████████████████ 100% |
| Sprint 1 — Foundation | 11 | 0 | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Sprint 2 — Pipeline A–C | 9 | 0 | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Sprint 3 — Valuation D–E | 10 | 0 | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Sprint 4 — Scoring & Reports | 10 | 0 | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Sprint 5 — Static Site | 11 | 0 | ░░░░░░░░░░░░░░░░░░░░ 0% |
| Sprint 6 — Polish | 8 | 0 | ░░░░░░░░░░░░░░░░░░░░ 0% |
| **TOTAL** | **66** | **7** | **11%** |

"""
Static site generator — produces index.html + per-ticker detail pages.

Generates a beautifully crafted static HTML site using Jinja2 templates.
The site is self-contained (no external CDN dependencies) and designed
for GitHub Pages deployment from the repository root.

Output structure:
    index.html          (main dashboard)
    site/
        style.css       (shared styles)
        app.js          (sorting/filtering/search)
        methodology.html
        ticker/<TICKER>.html
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup
from loguru import logger

from src.run_manager import RunManager

# Template directory relative to this file
TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_site(
    results: dict[str, Any],
    run_mgr: RunManager,
) -> Path:
    """
    Generate the complete static site.

    Args:
        results: Full pipeline results dict.
        run_mgr: Run folder manager.

    Returns:
        Path to generated index.html.
    """
    repo_root = Path.cwd()
    site_dir = repo_root / "site"
    ticker_dir = site_dir / "ticker"

    # Create directories
    site_dir.mkdir(exist_ok=True)
    ticker_dir.mkdir(exist_ok=True)

    # Setup Jinja2
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    env.filters["fmt_pct"] = _fmt_pct
    env.filters["fmt_num"] = _fmt_num
    env.filters["fmt_dollar"] = _fmt_dollar
    env.filters["signal_class"] = _signal_class
    env.filters["signal_label"] = _signal_label
    env.filters["sparkline"] = _sparkline_svg

    # Prepare template data
    candidates = results.get("candidates", [])
    rejected = results.get("rejected", [])
    errors = results.get("errors", [])
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    candidate_rows = [_build_candidate_row(c) for c in candidates]
    rejected_rows = [_build_rejected_row(r) for r in rejected]

    # Generate index.html at repo root
    index_tmpl = env.get_template("index.html")
    index_html = index_tmpl.render(
        candidates=candidate_rows,
        rejected=rejected_rows,
        errors=errors,
        total_scanned=len(candidates) + len(rejected) + len(errors),
        total_candidates=len(candidates),
        total_rejected=len(rejected),
        total_errors=len(errors),
        generated_at=generated_at,
        run_folder=str(run_mgr.run_dir),
    )
    index_path = repo_root / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    logger.info(f"Static site: index.html generated at {index_path}")

    # Generate per-ticker detail pages
    ticker_tmpl = env.get_template("ticker_detail.html")
    for c in candidates:
        try:
            ticker_data = _build_ticker_detail(c)
            ticker_html = ticker_tmpl.render(
                **ticker_data,
                generated_at=generated_at,
            )
            ticker_path = ticker_dir / f"{c['ticker']}.html"
            ticker_path.write_text(ticker_html, encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to generate ticker page for {c['ticker']}: {e}")

    # Generate methodology page
    method_tmpl = env.get_template("methodology.html")
    method_html = method_tmpl.render(generated_at=generated_at)
    method_path = site_dir / "methodology.html"
    method_path.write_text(method_html, encoding="utf-8")

    # Copy static assets
    _generate_css(site_dir / "style.css")
    _generate_js(site_dir / "app.js")

    total_pages = 1 + len(candidates) + 1  # index + tickers + methodology
    logger.info(f"Static site: {total_pages} pages generated")

    return index_path


# ---------------------------------------------------------------------------
# Data preparation helpers
# ---------------------------------------------------------------------------

def _build_candidate_row(c: dict) -> dict:
    """Build a flat dict for a candidate row in the index table."""
    data = c.get("data")
    return {
        "ticker": c["ticker"],
        "name": data.info.name if data else c["ticker"],
        "signal": c["signal"],
        "final_score": c.get("final_score", 0),
        "margin_of_safety": c.get("margin_of_safety", 0),
        "quality_score": c.get("quality_score", 0),
        "cyclicality": c.get("cyclicality", "UNKNOWN"),
        "trap_count": len(c.get("trap_flags", [])),
        "sector": data.info.sector if data else "",
        "industry": data.info.industry if data else "",
        "price": data.price.current_price if data else 0,
        "market_cap": data.price.market_cap if data else 0,
        "pe_ratio": data.metrics.pe_ratio if data else None,
        "roe": data.metrics.roe if data else None,
        "roic": data.metrics.roic if data else None,
        "fcf_yield": data.metrics.fcf_yield if data else None,
        "debt_to_equity": data.metrics.debt_to_equity if data else None,
        "intrinsic_low": _safe_min(c.get("intrinsic_range", {})),
        "intrinsic_high": _safe_max(c.get("intrinsic_range", {})),
        "sparklines": _extract_sparkline_data(data),
    }


def _build_rejected_row(r: dict) -> dict:
    """Build a flat dict for a rejected row."""
    data = r.get("data")
    return {
        "ticker": r["ticker"],
        "name": data.info.name if data else r["ticker"],
        "sector": data.info.sector if data else "",
        "reasons": r.get("reject_reasons", []),
        "reasons_str": "; ".join(r.get("reject_reasons", [])),
    }


def _build_ticker_detail(c: dict) -> dict:
    """Build detailed data dict for a ticker detail page."""
    data = c.get("data")
    stages = c.get("stages", {})

    detail = {
        "ticker": c["ticker"],
        "name": data.info.name if data else c["ticker"],
        "signal": c["signal"],
        "final_score": c.get("final_score", 0),
        "margin_of_safety": c.get("margin_of_safety", 0),
        "quality_score": c.get("quality_score", 0),
        "cyclicality": c.get("cyclicality", "UNKNOWN"),
        "trap_flags": c.get("trap_flags", []),
        "sector": data.info.sector if data else "",
        "industry": data.info.industry if data else "",
        "exchange": data.info.exchange if data else "",
        "country": data.info.country if data else "",
        "price": data.price.current_price if data else 0,
        "market_cap": data.price.market_cap if data else 0,
        "intrinsic_range": c.get("intrinsic_range", {}),
        "metrics": {},
        "stage_a": stages.get("a", {}),
        "stage_b": stages.get("b", {}),
        "stage_c": stages.get("c", {}),
        "stage_d": stages.get("d", {}),
        "stage_e": stages.get("e", {}),
        "stage_f": stages.get("f", {}),
        "income_history": [],
        "cashflow_history": [],
        "sparklines": _extract_sparkline_data(data),
    }

    if data and data.metrics:
        m = data.metrics
        detail["metrics"] = {
            "pe_ratio": m.pe_ratio,
            "forward_pe": m.forward_pe,
            "pb_ratio": m.pb_ratio,
            "ev_ebitda": m.ev_ebitda,
            "roe": m.roe,
            "roic": m.roic,
            "gross_margin": m.gross_margin,
            "operating_margin": m.operating_margin,
            "net_margin": m.net_margin,
            "fcf_yield": m.fcf_yield,
            "dividend_yield": m.dividend_yield,
            "debt_to_equity": m.debt_to_equity,
            "current_ratio": m.current_ratio,
            "interest_coverage": m.interest_coverage,
            "beta": m.beta,
        }

    # Financial history as list of dicts for easy template iteration
    if data and data.financials:
        inc = data.financials.income
        if inc is not None and not inc.empty:
            for year in sorted(inc.index):
                row = {"year": year}
                for col in inc.columns:
                    val = inc.loc[year, col]
                    row[col] = float(val) if pd.notna(val) else None
                detail["income_history"].append(row)

        cf = data.financials.cashflow
        if cf is not None and not cf.empty:
            for year in sorted(cf.index):
                row = {"year": year}
                for col in cf.columns:
                    val = cf.loc[year, col]
                    row[col] = float(val) if pd.notna(val) else None
                detail["cashflow_history"].append(row)

    return detail


# ---------------------------------------------------------------------------
# Jinja2 filter helpers
# ---------------------------------------------------------------------------

def _fmt_pct(v, decimals=1) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    return f"{v * 100:.{decimals}f}%"


def _fmt_num(v, decimals=2) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    return f"{v:,.{decimals}f}"


def _fmt_dollar(v, decimals=2) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    if abs(v) >= 1e12:
        return f"${v / 1e12:.1f}T"
    if abs(v) >= 1e9:
        return f"${v / 1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:.1f}M"
    return f"${v:,.{decimals}f}"


def _signal_class(signal: str) -> str:
    return {
        "STRONG_BUY_SIGNAL": "signal-strong-buy",
        "BUY_SIGNAL": "signal-buy",
        "WATCH": "signal-watch",
        "REJECT": "signal-reject",
    }.get(signal, "signal-unknown")


def _signal_label(signal: str) -> str:
    return {
        "STRONG_BUY_SIGNAL": "STRONG BUY",
        "BUY_SIGNAL": "BUY",
        "WATCH": "WATCH",
        "REJECT": "REJECT",
    }.get(signal, signal)


def _safe_min(d: dict) -> float | None:
    vals = [v for v in d.values() if v is not None and isinstance(v, (int, float))]
    return min(vals) if vals else None


def _safe_max(d: dict) -> float | None:
    vals = [v for v in d.values() if v is not None and isinstance(v, (int, float))]
    return max(vals) if vals else None


def _sparkline_svg(
    values: list,
    width: int = 80,
    height: int = 24,
    color: str = "#58a6ff",
    fill: bool = True,
) -> str:
    """Generate an inline SVG sparkline from a list of numeric values."""
    nums = [float(v) for v in values if v is not None and v == v]  # filter NaN
    if len(nums) < 2:
        return ""
    vmin = min(nums)
    vmax = max(nums)
    vrange = vmax - vmin if vmax != vmin else 1
    pad = 1  # 1px padding
    w = width - 2 * pad
    h = height - 2 * pad
    points = []
    for i, v in enumerate(nums):
        x = pad + (i / (len(nums) - 1)) * w
        y = pad + h - ((v - vmin) / vrange) * h
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    # Determine trend color: green if last > first, red if declining
    trend_color = color
    if nums[-1] > nums[0] * 1.02:
        trend_color = "#3fb950"  # green
    elif nums[-1] < nums[0] * 0.98:
        trend_color = "#f85149"  # red
    else:
        trend_color = "#d29922"  # yellow (flat)
    fill_path = ""
    if fill:
        fill_points = f"{pad:.1f},{pad + h:.1f} " + polyline + f" {pad + w:.1f},{pad + h:.1f}"
        fill_path = (
            f'<polygon points="{fill_points}" '
            f'fill="{trend_color}" fill-opacity="0.12" />'
        )
    svg = (
        f'<svg class="sparkline" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        f'{fill_path}'
        f'<polyline points="{polyline}" fill="none" '
        f'stroke="{trend_color}" stroke-width="1.5" stroke-linecap="round" '
        f'stroke-linejoin="round" />'
        f'<circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" '
        f'r="2" fill="{trend_color}" />'
        f'</svg>'
    )
    return Markup(svg)


def _extract_sparkline_data(data) -> dict[str, list]:
    """Extract sparkline-ready lists from TickerData financial history."""
    sparklines: dict[str, list] = {
        "revenue": [],
        "eps": [],
        "net_income": [],
        "fcf": [],
    }
    if data is None or data.financials is None:
        return sparklines
    inc = data.financials.income
    if inc is not None and not inc.empty:
        for year in sorted(inc.index):
            if "revenue" in inc.columns:
                v = inc.loc[year, "revenue"]
                sparklines["revenue"].append(float(v) if pd.notna(v) else None)
            if "eps" in inc.columns:
                v = inc.loc[year, "eps"]
                sparklines["eps"].append(float(v) if pd.notna(v) else None)
            if "net_income" in inc.columns:
                v = inc.loc[year, "net_income"]
                sparklines["net_income"].append(float(v) if pd.notna(v) else None)
    cf = data.financials.cashflow
    if cf is not None and not cf.empty:
        for year in sorted(cf.index):
            if "free_cash_flow" in cf.columns:
                v = cf.loc[year, "free_cash_flow"]
                sparklines["fcf"].append(float(v) if pd.notna(v) else None)
    return sparklines


# ---------------------------------------------------------------------------
# CSS & JS generation (self-contained, no CDN)
# ---------------------------------------------------------------------------

def _generate_css(path: Path) -> None:
    """Generate the shared CSS file."""
    css = _get_css_content()
    path.write_text(css, encoding="utf-8")


def _generate_js(path: Path) -> None:
    """Generate the shared JS file."""
    js = _get_js_content()
    js_path = path
    js_path.write_text(js, encoding="utf-8")


def _get_css_content() -> str:
    return """\
/* STOKS — Value Investing Scanner Styles */
:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --bg-card: #1c2128;
    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
    --text-muted: #6e7681;
    --border: #30363d;
    --accent: #58a6ff;
    --accent-hover: #79c0ff;
    --green: #3fb950;
    --green-dim: #238636;
    --yellow: #d29922;
    --yellow-dim: #9e6a03;
    --red: #f85149;
    --red-dim: #da3633;
    --orange: #db6d28;
    --purple: #bc8cff;
    --shadow: 0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2);
    --shadow-lg: 0 10px 30px rgba(0,0,0,0.4);
    --radius: 8px;
    --radius-lg: 12px;
    --transition: 0.2s ease;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    min-height: 100vh;
}

a { color: var(--accent); text-decoration: none; transition: color var(--transition); }
a:hover { color: var(--accent-hover); text-decoration: underline; }

/* Layout */
.container { max-width: 1400px; margin: 0 auto; padding: 0 24px; }

header {
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    padding: 20px 0;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(10px);
}
header .container { display: flex; align-items: center; justify-content: space-between; }
header h1 { font-size: 1.5rem; font-weight: 700; letter-spacing: -0.5px; }
header h1 span { color: var(--accent); }
header nav a { margin-left: 24px; color: var(--text-secondary); font-size: 0.875rem; }
header nav a:hover { color: var(--text-primary); }

/* Disclaimer Banner */
.disclaimer {
    background: linear-gradient(135deg, var(--yellow-dim), var(--orange));
    color: #fff;
    padding: 10px 20px;
    text-align: center;
    font-size: 0.8rem;
    font-weight: 500;
}

/* Stats Strip */
.stats-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    padding: 24px 0;
}
.stat-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    text-align: center;
    transition: all var(--transition);
}
.stat-card:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: var(--shadow); }
.stat-card .value { font-size: 2rem; font-weight: 700; color: var(--accent); }
.stat-card .label { font-size: 0.8rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

/* Section */
.section { padding: 32px 0; }
.section h2 {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}

/* Controls */
.controls {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
    align-items: center;
}
.search-box {
    flex: 1;
    min-width: 200px;
    padding: 8px 14px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text-primary);
    font-size: 0.875rem;
    outline: none;
    transition: border-color var(--transition);
}
.search-box:focus { border-color: var(--accent); }
.search-box::placeholder { color: var(--text-muted); }

select.filter-select {
    padding: 8px 14px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text-primary);
    font-size: 0.875rem;
    cursor: pointer;
    outline: none;
}
select.filter-select:focus { border-color: var(--accent); }

/* Table */
.table-wrapper {
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--bg-secondary);
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
}
thead { background: var(--bg-tertiary); }
th {
    padding: 12px 16px;
    text-align: left;
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
    position: relative;
}
th:hover { color: var(--accent); }
th.sort-asc::after { content: " ▲"; font-size: 0.65rem; }
th.sort-desc::after { content: " ▼"; font-size: 0.65rem; }

td {
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
}
tr:last-child td { border-bottom: none; }
tr:hover { background: rgba(88, 166, 255, 0.04); }

td.num { text-align: right; font-variant-numeric: tabular-nums; }

/* Signal Badges */
.signal-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.signal-strong-buy { background: var(--green-dim); color: var(--green); }
.signal-buy { background: rgba(63, 185, 80, 0.15); color: var(--green); }
.signal-watch { background: rgba(210, 153, 34, 0.15); color: var(--yellow); }
.signal-reject { background: rgba(248, 81, 73, 0.1); color: var(--red); }

/* Score Bar */
.score-bar {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-width: 80px;
}
.score-bar .bar {
    flex: 1;
    height: 6px;
    background: var(--bg-tertiary);
    border-radius: 3px;
    overflow: hidden;
    min-width: 40px;
}
.score-bar .bar .fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease;
}
.score-bar .value { font-size: 0.8rem; font-weight: 600; min-width: 24px; }

/* MOS Bar Colors */
.mos-high { background: var(--green); }
.mos-mid { background: var(--yellow); }
.mos-low { background: var(--red); }

/* Detail Page */
.detail-header {
    padding: 32px 0;
    border-bottom: 1px solid var(--border);
}
.detail-header h1 { font-size: 2rem; font-weight: 700; }
.detail-header .subtitle { color: var(--text-secondary); margin-top: 4px; }

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 12px;
    margin: 20px 0;
}
.metric-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px;
}
.metric-card .metric-label { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
.metric-card .metric-value { font-size: 1.2rem; font-weight: 600; margin-top: 4px; }

.stage-section {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 20px;
    margin: 16px 0;
}
.stage-section h3 { font-size: 1rem; font-weight: 600; margin-bottom: 12px; }

.flag-list { list-style: none; padding: 0; }
.flag-list li {
    padding: 6px 10px;
    margin: 4px 0;
    background: rgba(248, 81, 73, 0.08);
    border-left: 3px solid var(--red);
    border-radius: 0 var(--radius) var(--radius) 0;
    font-size: 0.85rem;
}

/* Footer */
footer {
    border-top: 1px solid var(--border);
    padding: 24px 0;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8rem;
    margin-top: 40px;
}

/* Empty state */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-secondary);
}
.empty-state .icon { font-size: 3rem; margin-bottom: 16px; }
.empty-state h3 { font-size: 1.2rem; margin-bottom: 8px; color: var(--text-primary); }

/* Sparkline */
.sparkline-cell { padding: 4px 8px; text-align: center; }
.sparkline-cell svg.sparkline { vertical-align: middle; }
.sparkline-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin: 20px 0; }
.sparkline-card { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; text-align: center; }
.sparkline-card .sparkline-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }
.sparkline-card .sparkline-chart { display: flex; justify-content: center; }
.sparkline-card svg.sparkline { display: block; }

/* Responsive */
@media (max-width: 768px) {
    .container { padding: 0 16px; }
    .stats-strip { grid-template-columns: repeat(2, 1fr); }
    .controls { flex-direction: column; }
    header .container { flex-direction: column; gap: 12px; }
    header nav a { margin-left: 0; margin-right: 16px; }
}
"""


def _get_js_content() -> str:
    return """\
/* STOKS — Table Sorting, Filtering & Search */
(function() {
    'use strict';

    // Table sorting
    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const table = th.closest('table');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const col = th.dataset.sort;
            const type = th.dataset.type || 'string';
            const currentDir = th.classList.contains('sort-asc') ? 'desc' : 'asc';

            // Clear all sort indicators
            table.querySelectorAll('th').forEach(t => t.classList.remove('sort-asc', 'sort-desc'));
            th.classList.add('sort-' + currentDir);

            rows.sort((a, b) => {
                let aVal = a.querySelector(`td[data-col="${col}"]`)?.dataset.value || '';
                let bVal = b.querySelector(`td[data-col="${col}"]`)?.dataset.value || '';

                if (type === 'number') {
                    aVal = parseFloat(aVal) || 0;
                    bVal = parseFloat(bVal) || 0;
                } else {
                    aVal = aVal.toLowerCase();
                    bVal = bVal.toLowerCase();
                }

                if (aVal < bVal) return currentDir === 'asc' ? -1 : 1;
                if (aVal > bVal) return currentDir === 'asc' ? 1 : -1;
                return 0;
            });

            rows.forEach(row => tbody.appendChild(row));
        });
    });

    // Search
    const searchBox = document.getElementById('search-box');
    if (searchBox) {
        searchBox.addEventListener('input', filterTable);
    }

    // Sector filter
    const sectorFilter = document.getElementById('sector-filter');
    if (sectorFilter) {
        sectorFilter.addEventListener('change', filterTable);
    }

    // Signal filter
    const signalFilter = document.getElementById('signal-filter');
    if (signalFilter) {
        signalFilter.addEventListener('change', filterTable);
    }

    function filterTable() {
        const search = (searchBox?.value || '').toLowerCase();
        const sector = sectorFilter?.value || '';
        const signal = signalFilter?.value || '';

        document.querySelectorAll('#candidates-table tbody tr').forEach(row => {
            const ticker = row.dataset.ticker?.toLowerCase() || '';
            const name = row.dataset.name?.toLowerCase() || '';
            const rowSector = row.dataset.sector || '';
            const rowSignal = row.dataset.signal || '';

            const matchSearch = !search || ticker.includes(search) || name.includes(search);
            const matchSector = !sector || rowSector === sector;
            const matchSignal = !signal || rowSignal === signal;

            row.style.display = (matchSearch && matchSector && matchSignal) ? '' : 'none';
        });
    }

    // Tab switching for rejected/errors
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            document.getElementById(target)?.classList.add('active');
        });
    });
})();
"""
